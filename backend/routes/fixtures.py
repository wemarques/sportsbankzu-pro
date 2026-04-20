from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
import os
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None
from backend.services.fixtures_service import build_records_from_matches
from backend.services.footstats_client import FootyStatsClient
from backend.services.api_football_client import APIFootballClient
from backend.services.data_mapper import DataMapper
from backend.services.util_service import team_name
from backend.services.live_score_merge import (
    merge_live_scores, ScoreCandidate,
    SOURCE_TODAYS_MATCHES, SOURCE_MATCH_DETAIL, SOURCE_API_FOOTBALL,
)
from backend.config.leagues_config import get_league_config, get_api_football_league_id, get_season_for_league

logger = logging.getLogger("sportsbankzu.fixtures")
router = APIRouter(tags=["fixtures"])
footstats = FootyStatsClient()
_afc = APIFootballClient()

# Max threads for parallel league processing within a single request.
# Keeps API call volume reasonable while dramatically reducing latency.
_MAX_LEAGUE_WORKERS = 4


def _deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate fixture records that refer to the same match.

    Uses alias-aware team name matching from APIFootballClient.
    When duplicates are found, keeps the record with richer data
    (more non-zero odds, predictions, or live score).
    """
    if len(records) <= 1:
        return records

    def _canon(name: str) -> str:
        """Canonical form for dedup key: resolve alias + normalize."""
        return _afc._resolve_alias(name)

    def _team_key(rec: dict) -> str:
        ht = rec.get("homeTeam")
        at = rec.get("awayTeam")
        home = ht.get("name", "") if isinstance(ht, dict) else str(ht or "")
        away = at.get("name", "") if isinstance(at, dict) else str(at or "")
        return f"{_canon(home)}||{_canon(away)}"

    def _richness(rec: dict) -> int:
        """Score how much useful data a record has (higher = keep)."""
        score = 0
        # Prefer records with predictions/recommendations
        if rec.get("predictions"):
            score += 100
        if rec.get("recommendations"):
            score += 100
        # Prefer records with non-zero odds
        odds = rec.get("odds", {})
        if isinstance(odds, dict):
            score += sum(1 for v in odds.values() if isinstance(v, (int, float)) and v > 0)
        # Prefer records with stats
        stats = rec.get("stats", {})
        if isinstance(stats, dict):
            score += sum(1 for v in stats.values() if isinstance(v, (int, float)) and v > 0)
        # Prefer records with live score
        s = rec.get("score", {})
        if isinstance(s, dict) and ((s.get("home") or 0) + (s.get("away") or 0)) > 0:
            score += 50
        # Prefer records with apiFootballFixtureId (enriched)
        if rec.get("apiFootballFixtureId"):
            score += 10
        return score

    seen: dict = {}  # team_key → (index, richness)
    result: List[Dict[str, Any]] = []
    dropped = 0

    for rec in records:
        key = _team_key(rec)
        rich = _richness(rec)

        if key in seen:
            prev_idx, prev_rich = seen[key]
            if rich > prev_rich:
                # Current record is richer — replace previous
                ht_prev = result[prev_idx].get("homeTeam")
                home_prev = ht_prev.get("name", "") if isinstance(ht_prev, dict) else str(ht_prev or "")
                ht_cur = rec.get("homeTeam")
                home_cur = ht_cur.get("name", "") if isinstance(ht_cur, dict) else str(ht_cur or "")
                logger.info(
                    f"[fixtures] dedup: replacing '{home_prev}' (richness={prev_rich}) "
                    f"with '{home_cur}' (richness={rich})"
                )
                # Merge live score from the dropped record if the kept one lacks it
                prev_score = result[prev_idx].get("score", {})
                cur_score = rec.get("score", {})
                if isinstance(prev_score, dict) and isinstance(cur_score, dict):
                    prev_total = (prev_score.get("home") or 0) + (prev_score.get("away") or 0)
                    cur_total = (cur_score.get("home") or 0) + (cur_score.get("away") or 0)
                    if prev_total > 0 and cur_total == 0:
                        rec["score"] = prev_score
                    # Also merge halftime score
                    if prev_score.get("halftime") and not cur_score.get("halftime"):
                        rec.setdefault("score", {})["halftime"] = prev_score["halftime"]
                # Merge live status/period/minute from the dropped record
                if result[prev_idx].get("status") == "live" and rec.get("status") != "live":
                    rec["status"] = result[prev_idx]["status"]
                    for field in ("period", "minute", "apiFootballFixtureId"):
                        if result[prev_idx].get(field) and not rec.get(field):
                            rec[field] = result[prev_idx][field]
                result[prev_idx] = rec
                seen[key] = (prev_idx, rich)
            else:
                # Previous record is richer — keep it but merge live data from current
                cur_score = rec.get("score", {})
                prev_score = result[prev_idx].get("score", {})
                if isinstance(cur_score, dict) and isinstance(prev_score, dict):
                    cur_total = (cur_score.get("home") or 0) + (cur_score.get("away") or 0)
                    prev_total = (prev_score.get("home") or 0) + (prev_score.get("away") or 0)
                    if cur_total > 0 and prev_total == 0:
                        result[prev_idx]["score"] = cur_score
                if rec.get("status") == "live" and result[prev_idx].get("status") != "live":
                    result[prev_idx]["status"] = rec["status"]
                    for field in ("period", "minute", "apiFootballFixtureId"):
                        if rec.get(field) and not result[prev_idx].get(field):
                            result[prev_idx][field] = rec[field]
                logger.info(
                    f"[fixtures] dedup: dropped duplicate (richness={rich} vs {prev_rich})"
                )
            dropped += 1
        else:
            seen[key] = (len(result), rich)
            result.append(rec)

    if dropped:
        logger.info(f"[fixtures] dedup: removed {dropped} duplicate(s), {len(result)} unique records remain")

    return result


def _process_single_league(lid: str, date: str, base: str) -> List[Dict[str, Any]]:
    """Process a single league: API fetch → build records. Thread-safe."""
    from backend.main import resolve_league_dir, generate_mock_fixtures
    from backend.config.leagues_config import LEAGUE_ID_ALIASES

    league_config = get_league_config(lid)
    # Resolve alias so match IDs always use the canonical league_id (#091)
    lid = LEAGUE_ID_ALIASES.get(lid, lid)
    records: List[Dict[str, Any]] = []
    found_via_api = False

    if league_config:
        try:
            # #064: resolve up to 2 seasons for prev-season fallback
            _season_ids = footstats.resolve_season_ids(
                league_config["country"], league_config["name"],
                alt_names=league_config.get("alt_names"),
                n_seasons=2,
            )
            season_id = _season_ids[0][0] if _season_ids else None
            prev_season_id = _season_ids[1][0] if len(_season_ids) > 1 else None
            if season_id:
                # #119b — Fetch matches, season-stats, and teams in parallel
                from concurrent.futures import ThreadPoolExecutor as _TPE
                with _TPE(max_workers=3) as _pool:
                    _f_matches = _pool.submit(footstats.get_all_league_matches, season_id)  # #154: all pages
                    _f_stats = _pool.submit(footstats.get_league_season_stats, season_id)
                    _f_teams = _pool.submit(footstats.get_league_teams, season_id)

                    try:
                        matches_data = _f_matches.result(timeout=45)  # #154: more time for multi-page fetch
                    except Exception as e:
                        logger.error(f"[fixtures] {lid}: get_all_league_matches failed: {e}")
                        matches_data = {"success": False}

                if matches_data.get("success"):
                    raw_list = matches_data.get("data", [])
                    if not raw_list:
                        logger.warning(f"[fixtures] {lid}: API success but empty data list")
                        return []

                    # #154-diag: log total matches from all pages
                    logger.info(f"[fixtures] {lid}: league-matches returned {len(raw_list)} total matches (season_id={season_id})")

                    try:
                        matches_df = DataMapper.matches_to_df(raw_list)
                    except Exception as e:
                        logger.error(f"[fixtures] {lid}: matches_to_df crashed: {e}")
                        return []

                    if matches_df.empty:
                        logger.warning(f"[fixtures] {lid}: matches_to_df returned empty DataFrame")
                        return []

                    teams_df = None
                    league_season_data = None
                    try:
                        season_stats = _f_stats.result(timeout=5)
                        if season_stats.get("success"):
                            season_data = season_stats.get("data", {})
                            if isinstance(season_data, dict):
                                league_season_data = season_data
                    except Exception as e:
                        logger.warning(f"[fixtures] {lid}: failed to load season-stats: {e}")

                    try:
                        teams_data = _f_teams.result(timeout=5)
                        if teams_data.get("success"):
                            raw_teams = teams_data.get("data", [])
                            if raw_teams:
                                teams_df = DataMapper.teams_to_df(raw_teams)
                                logger.info(f"[fixtures] {lid}: loaded {len(teams_df)} teams with stats (cols: {list(teams_df.columns)[:10]})")
                            else:
                                logger.warning(f"[fixtures] {lid}: league-teams success but empty data")
                        else:
                            logger.warning(f"[fixtures] {lid}: league-teams success=False: {teams_data.get('message','')}")
                    except Exception as e:
                        logger.warning(f"[fixtures] {lid}: failed to load league-teams: {e}", exc_info=True)

                    if teams_df is None:
                        try:
                            tables_data = footstats.get_league_tables(season_id)
                            if tables_data.get("success"):
                                raw_tables = tables_data.get("data", [])
                                if raw_tables:
                                    rows = []
                                    for pos, t in enumerate(raw_tables, 1):
                                        name = t.get("team_name") or t.get("name") or t.get("cleanName", "")
                                        played = int(t.get("matchesPlayed", 0) or 0)
                                        wins = int(t.get("seasonWins_overall", t.get("wins", 0)) or 0)
                                        cs = int(t.get("seasonCS_overall", t.get("cleanSheets", 0)) or 0)
                                        btts = int(t.get("seasonBTTS_overall", t.get("btts", 0)) or 0)
                                        rows.append({
                                            "team_name": name,
                                            "league_position": pos,
                                            "win_percentage": round(wins / played * 100, 1) if played > 0 else None,
                                            "clean_sheet_percentage": round(cs / played * 100, 1) if played > 0 else None,
                                            "btts_percentage": round(btts / played * 100, 1) if played > 0 else None,
                                        })
                                    if rows:
                                        teams_df = pd.DataFrame(rows)
                                        logger.info(f"[fixtures] {lid}: fallback league-tables loaded {len(teams_df)} teams")
                        except Exception as e:
                            logger.warning(f"[fixtures] {lid}: fallback league-tables also failed: {e}")

                    # #064: Load previous season teams as fallback for early-season blending
                    prev_teams_df = None
                    if teams_df is not None and prev_season_id:
                        try:
                            from backend.services.util_service import pick_column
                            mp_col = pick_column(teams_df, ["matches_played", "games_played", "matches"])
                            needs_prev = False
                            if mp_col:
                                low_count = int((pd.to_numeric(teams_df[mp_col], errors="coerce").fillna(0) < 5).sum())
                                needs_prev = low_count > len(teams_df) * 0.3
                            else:
                                needs_prev = True
                            if needs_prev:
                                prev_data = footstats.get_league_teams(prev_season_id)
                                if prev_data.get("success"):
                                    raw_prev = prev_data.get("data", [])
                                    if raw_prev:
                                        prev_teams_df = DataMapper.teams_to_df(raw_prev)
                                        logger.warning(
                                            f"[fixtures] {lid}: loaded {len(prev_teams_df)} "
                                            f"prev-season teams as fallback (prev_sid={prev_season_id})"
                                        )
                        except Exception as e:
                            logger.warning(f"[fixtures] {lid}: prev-season teams fallback failed: {e}")

                    league_df = None
                    if league_season_data:
                        try:
                            league_df = pd.DataFrame([{
                                "league_name": league_config.get("name", lid),
                                "average_goals_per_match": league_season_data.get("seasonAVG_overall", 2.5),
                                "average_scored_home_team": league_season_data.get("seasonHomeAVG_overall",
                                    league_season_data.get("averageScoredHomeTeam", None)),
                                "average_scored_away_team": league_season_data.get("seasonAwayAVG_overall",
                                    league_season_data.get("averageScoredAwayTeam", None)),
                                "average_corners_per_match": league_season_data.get("cornersAVG_overall", 10.0),
                                "average_corners_per_match_home_team": league_season_data.get("cornersAVG_home",
                                    league_season_data.get("averageCornersPerMatchHomeTeam", None)),
                                "average_cards_per_match": league_season_data.get("cardsAVG_overall", 4.0),
                                "average_cards_per_match_home_team": league_season_data.get("cardsAVG_home",
                                    league_season_data.get("averageCardsPerMatchHomeTeam", None)),
                                "average_cards_per_match_away_team": league_season_data.get("cardsAVG_away",
                                    league_season_data.get("averageCardsPerMatchAwayTeam", None)),
                                "average_fouls_per_match": league_season_data.get("foulsAVG_overall", 22.0),
                                "average_shots_per_match": league_season_data.get("shotsAVG_overall", 24.0),
                                "home_advantage_percentage": league_season_data.get("homeAdvantagePercentage",
                                    league_season_data.get("home_advantage_percentage", None)),
                                "home_scored_advantage_percentage": league_season_data.get("homeScoredAdvantagePercentage", None),
                                "home_defence_advantage_percentage": league_season_data.get("homeDefenceAdvantagePercentage", None),
                                "clean_sheets_percentage": league_season_data.get("cleanSheetsPercentage",
                                    league_season_data.get("clean_sheets_percentage", None)),
                                "over_05_percentage": league_season_data.get("over05Percentage", None),
                                "over_15_percentage": league_season_data.get("over15Percentage", None),
                                "over_25_percentage": league_season_data.get("over25Percentage", None),
                                "over_35_percentage": league_season_data.get("over35Percentage", None),
                                "over_45_percentage": league_season_data.get("over45Percentage", None),
                                "under_25_percentage": league_season_data.get("under25Percentage", None),
                                "xg_avg": league_season_data.get("xgAVG",
                                    league_season_data.get("xg_avg", None)),
                                "prediction_risk": league_season_data.get("predictionRisk",
                                    league_season_data.get("prediction_risk", None)),
                                "matches_completed": league_season_data.get("matchesCompleted",
                                    league_season_data.get("matches_completed", None)),
                                "total_matches": league_season_data.get("totalMatches",
                                    league_season_data.get("total_matches", None)),
                            }])
                        except Exception as e:
                            logger.warning(f"[fixtures] {lid}: failed to build league_df: {e}")

                    try:
                        records = build_records_from_matches(
                            league_id=lid,
                            matches=matches_df,
                            teams=teams_df,
                            teams2=prev_teams_df,
                            league_df=league_df,
                            players=None,
                            date_filter=date,
                            season_id=season_id,  # #141: enables referee lookup
                        )
                    except Exception as e:
                        logger.error(f"[fixtures] {lid}: build_records_from_matches crashed: {type(e).__name__}: {e}")
                        records = []

                    # #154-diag: log how many matches survived date filter
                    logger.info(
                        f"[fixtures] {lid}: build_records → {len(records)} records for date='{date}' "
                        f"(from {len(matches_df)} rows in DataFrame)"
                    )

                    if records:
                        for r in records:
                            r["dataSource"] = "FootyStats API (Tempo Real)"

                    # #153 — Complement with todays-matches to catch fixtures
                    # missing from page 1 of league-matches (pagination by season,
                    # not by date — leagues deep into their season may have today's
                    # matches on page 2+).
                    _todays_complement = _fallback_todays_matches(lid, league_config, date, season_id=season_id)
                    if _todays_complement:
                        if not records:
                            # No rich records at all — use todays-matches as primary
                            records = _todays_complement
                            logger.info(f"[fixtures] {lid}: todays-matches provided all {len(records)} records (no page-1 matches)")
                        else:
                            # Merge: add any matches from todays-matches that are NOT already
                            # in the rich records (matched by normalized team names).
                            _existing_teams = set()
                            for r in records:
                                _h = r.get("homeTeam", {})
                                _a = r.get("awayTeam", {})
                                _hn = (_h.get("name") or _h) if isinstance(_h, (dict, str)) else ""
                                _an = (_a.get("name") or _a) if isinstance(_a, (dict, str)) else ""
                                if isinstance(_hn, str) and isinstance(_an, str):
                                    _existing_teams.add((_hn.strip().lower(), _an.strip().lower()))

                            _added = 0
                            for tr in _todays_complement:
                                _th = tr.get("homeTeam", {})
                                _ta = tr.get("awayTeam", {})
                                _thn = (_th.get("name", "") if isinstance(_th, dict) else str(_th)).strip().lower()
                                _tan = (_ta.get("name", "") if isinstance(_ta, dict) else str(_ta)).strip().lower()
                                if (_thn, _tan) not in _existing_teams:
                                    records.append(tr)
                                    _existing_teams.add((_thn, _tan))
                                    _added += 1
                            if _added:
                                logger.info(
                                    f"[fixtures] {lid}: todays-matches complement added {_added} "
                                    f"missing matches (total now {len(records)}) (#153)"
                                )
                    elif not records:
                        logger.warning(f"[fixtures] {lid}: API OK but 0 records for date '{date}', no todays-matches available")
                    found_via_api = True
                else:
                    logger.warning(f"[fixtures] {lid}: API success=False: {matches_data.get('message','')}")
                    # Fallback to todays-matches when league-matches fails
                    records = _fallback_todays_matches(lid, league_config, date, season_id=season_id)
                    if records:
                        logger.info(f"[fixtures] {lid}: todays-matches fallback (after league-matches fail) found {len(records)} records")
                        found_via_api = True
            else:
                logger.warning(f"[fixtures] {lid}: could not resolve season_id for {league_config}")
                # Try todays-matches even without season_id (name-based matching)
                records = _fallback_todays_matches(lid, league_config, date, season_id=None)
                if records:
                    logger.info(f"[fixtures] {lid}: todays-matches fallback (no season_id) found {len(records)} records")
                    found_via_api = True
        except Exception as e:
            logger.error(f"[fixtures] {lid}: {type(e).__name__}: {e}")

    # API-Football enrichment: overlay live scores + fallback data source
    records = _enrich_with_api_football(lid, records, found_via_api, date)

    # API-Football odds enrichment (#120) — runs AFTER _enrich_with_api_football
    # so that apiFootballFixtureId is available on each record.
    _enrich_odds_from_api_football(records)

    # Final deduplication: remove duplicate matches that slipped through
    # team-name matching (e.g. "Wolves" vs "Wolverhampton Wanderers")
    records = _deduplicate_records(records)

    # FALLBACK: CSV files (skip mock data in production to avoid poisoning batches)
    _is_production = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("VERCEL"))
    if not found_via_api:
        from backend.main import resolve_league_dir, generate_mock_fixtures as gen_mock
        if pd is None or not os.path.isdir(base):
            if _is_production:
                logger.info(f"[fixtures] {lid}: no data available, returning empty (production mode)")
                return []
            return gen_mock(lid, date)

        league_dir = resolve_league_dir(base, lid)
        matches_path = os.path.join(league_dir, "matches.csv")
        teams_path = os.path.join(league_dir, "teams.csv")
        teams2_path = os.path.join(league_dir, "teams2.csv")
        league_path = os.path.join(league_dir, "league.csv")
        players_path = os.path.join(league_dir, "players.csv")

        if not os.path.exists(matches_path):
            if _is_production:
                logger.info(f"[fixtures] {lid}: no CSV data, returning empty (production mode)")
                return []
            return gen_mock(lid, date)

        try:
            matches_df = pd.read_csv(matches_path)
            teams_df = pd.read_csv(teams_path) if os.path.exists(teams_path) else None
            teams2_df = pd.read_csv(teams2_path) if os.path.exists(teams2_path) else None
            league_df = pd.read_csv(league_path) if os.path.exists(league_path) else None
            players_df = pd.read_csv(players_path) if os.path.exists(players_path) else None

            records = build_records_from_matches(
                league_id=lid,
                matches=matches_df,
                teams=teams_df,
                teams2=teams2_df,
                league_df=league_df,
                players=players_df,
                date_filter=date,
            )
            if records:
                for r in records:
                    r["dataSource"] = "Arquivos CSV (Histórico)"
        except Exception as e:
            logger.error(f"Erro ao ler CSV para {lid}: {e}")
            if not _is_production:
                from backend.main import generate_mock_fixtures as gen_mock2
                records = gen_mock2(lid, date)

    return records


def _enrich_odds_from_api_football(records: List[Dict[str, Any]]) -> None:
    """Enrich fixture records with odds from API-Football (#120).

    Runs AFTER _enrich_with_api_football() so apiFootballFixtureId is available.
    Only fills odds that are None/missing — never overwrites FootyStats odds.
    """
    if not _afc.is_configured:
        return
    enriched_count = 0
    for rec in records:
        af_id = rec.get("apiFootballFixtureId")
        if not af_id:
            continue
        odds_dict = rec.get("odds")
        if not isinstance(odds_dict, dict):
            continue
        try:
            af_odds = _afc.get_odds(int(af_id), ttl_minutes=180)
            if not af_odds:
                continue
            best = _afc.extract_best_odds(af_odds)
            if not best:
                continue
            filled = []
            # O/U goals: all lines (#120)
            ou_map = {
                "over_05": "over05", "over_15": "over15", "over_25": "over25",
                "over_35": "over35", "over_45": "over45", "over_55": "over55",
                "under_05": "under05", "under_15": "under15", "under_25": "under25",
                "under_35": "under35", "under_45": "under45", "under_55": "under55",
            }
            for af_key, odds_key in ou_map.items():
                if best.get(af_key) and not odds_dict.get(odds_key):
                    odds_dict[odds_key] = best[af_key]
                    filled.append(odds_key)
            # 1X2
            for sel in ("home", "draw", "away"):
                if best.get(sel) and not odds_dict.get(sel):
                    odds_dict[sel] = best[sel]
                    filled.append(sel)
            # BTTS
            if best.get("btts_yes") and not odds_dict.get("bttsYes"):
                odds_dict["bttsYes"] = best["btts_yes"]
                filled.append("bttsYes")
            if best.get("btts_no") and not odds_dict.get("bttsNo"):
                odds_dict["bttsNo"] = best["btts_no"]
                filled.append("bttsNo")
            # Double Chance
            for dc_key in ("dc_1x", "dc_12", "dc_x2"):
                if best.get(dc_key) and not odds_dict.get(dc_key):
                    odds_dict[dc_key] = best[dc_key]
                    filled.append(dc_key)
            # Cards
            for line_sfx in ("15", "25", "35", "45", "55", "65"):
                for side in ("over", "under"):
                    af_key = f"cards_{side}_{line_sfx}"
                    line_dot = f"{line_sfx[0]}.{line_sfx[1]}"
                    odds_key = f"cards_{side}_{line_dot}"
                    if best.get(af_key) and not odds_dict.get(odds_key):
                        odds_dict[odds_key] = best[af_key]
                        filled.append(odds_key)
            if filled:
                rec.setdefault("source_flags", []).append("api_football_odds")
                enriched_count += 1
                _ht = rec.get("homeTeam")
                home = _ht.get("name", "") if isinstance(_ht, dict) else str(_ht or "")
                logger.info(f"[odds-enrich] {home}: +{len(filled)} odds from API-Football ({', '.join(filled[:5])}{'...' if len(filled) > 5 else ''})")
        except Exception as e:
            logger.debug(f"[odds-enrich] af_id={af_id} skipped: {e}")
    if enriched_count:
        logger.info(f"[odds-enrich] Enriched {enriched_count}/{len(records)} records with API-Football odds")


def _current_season() -> int:
    """Infer the current football season year."""
    from datetime import timezone as _tz
    now = datetime.now(_tz.utc)
    return now.year if now.month >= 7 else now.year - 1


def _enrich_with_api_football(
    lid: str, records: list, found_via_api: bool, date_str: str
) -> list:
    """Enrich fixture records with API-Football live data, or use as fallback.

    1. If records exist: overlay live scores/status from API-Football
    2. If no records and API-Football is configured: fetch fixtures as fallback
    """
    if not _afc.is_configured:
        return records

    af_league_id = get_api_football_league_id(lid)
    if af_league_id is None:
        return records

    # Use league-aware season: calendar-year leagues (Brazil, Japan, etc.)
    # use current year; European mid-year leagues use previous year before July.
    season = get_season_for_league(lid)

    # CASE 1: Records exist — enrich with live data overlay
    if records:
        try:
            # Determine the actual date for API-Football query
            from datetime import timezone as _tz
            BRT = _tz(timedelta(hours=-3))
            now_brt = datetime.now(BRT)
            if date_str == "tomorrow":
                af_date = (now_brt + timedelta(days=1)).strftime("%Y-%m-%d")
            elif date_str == "today":
                af_date = now_brt.strftime("%Y-%m-%d")
            else:
                af_date = date_str

            af_fixtures = _afc.get_fixtures_by_date(af_league_id, season, af_date, ttl_minutes=30)
            if not af_fixtures:
                # Season fallback: try season+1 or season-1 in case our convention is wrong.
                # Handles leagues where API-Football season param differs from our calculation
                # (e.g., some Middle Eastern leagues may use calendar year instead of start year).
                alt_season = season + 1
                af_fixtures = _afc.get_fixtures_by_date(af_league_id, alt_season, af_date, ttl_minutes=30)
                if af_fixtures:
                    logger.warning(
                        f"[fixtures] {lid}: season={season} returned 0, but season={alt_season} "
                        f"returned {len(af_fixtures)} — using fallback season"
                    )
                    season = alt_season
                else:
                    logger.info(
                        f"[fixtures] {lid}: API-Football returned 0 fixtures "
                        f"(league={af_league_id}, season={season}, date={af_date}, "
                        f"also tried season={alt_season})"
                    )
                    return records

            logger.info(
                f"[fixtures] {lid}: API-Football returned {len(af_fixtures)} fixtures "
                f"(league={af_league_id}, season={season}, date={af_date})"
            )
            enriched = 0
            for rec in records:
                # homeTeam can be a dict {"name": ...} or a plain string
                _ht = rec.get("homeTeam")
                _at = rec.get("awayTeam")
                home = _ht.get("name", "") if isinstance(_ht, dict) else str(_ht or "")
                away = _at.get("name", "") if isinstance(_at, dict) else str(_at or "")

                # Use robust matching from APIFootballClient (unicode, prefixes, token overlap)
                matched_fx = None
                for fx in af_fixtures:
                    fx_home = fx.get("teams", {}).get("home", {}).get("name", "")
                    fx_away = fx.get("teams", {}).get("away", {}).get("name", "")
                    if _afc._team_names_match(home, fx_home) and _afc._team_names_match(away, fx_away):
                        matched_fx = fx
                        break

                if matched_fx:
                    _afc.enrich_fixture_record(rec, matched_fx)
                    enriched += 1
                else:
                    af_names = [(fx.get("teams", {}).get("home", {}).get("name", ""), fx.get("teams", {}).get("away", {}).get("name", "")) for fx in af_fixtures[:5]]
                    logger.warning(
                        f"[fixtures] {lid}: No API-Football match for '{home}' vs '{away}' "
                        f"(AF has: {af_names})"
                    )

            if enriched:
                logger.info(f"[fixtures] {lid}: API-Football enriched {enriched}/{len(records)} records")
            else:
                logger.warning(f"[fixtures] {lid}: API-Football enriched 0/{len(records)} records — name matching failed for all")

            # CASE 1b: Inject live/finished matches from API-Football that
            # FootyStats dropped (e.g. match moved off page-1, status changed
            # to "complete" mid-game, or timezone edge case filtered it out).
            matched_af_ids: set = set()
            for rec in records:
                af_id = rec.get("apiFootballFixtureId")
                if af_id:
                    matched_af_ids.add(af_id)

            injected = 0
            for fx in af_fixtures:
                fx_id = fx.get("fixture", {}).get("id")
                if fx_id in matched_af_ids:
                    continue
                # Only inject live or finished matches — don't duplicate scheduled ones
                status_short = fx.get("fixture", {}).get("status", {}).get("short", "NS")
                live_statuses = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "SUSP", "INT"}
                finished_statuses = {"FT", "AET", "PEN"}
                if status_short not in live_statuses and status_short not in finished_statuses:
                    continue
                # Check this fixture wasn't already matched by team name
                fx_home = fx.get("teams", {}).get("home", {}).get("name", "")
                fx_away = fx.get("teams", {}).get("away", {}).get("name", "")
                already_present = False
                for rec in records:
                    _ht = rec.get("homeTeam")
                    _at = rec.get("awayTeam")
                    rh = _ht.get("name", "") if isinstance(_ht, dict) else str(_ht or "")
                    ra = _at.get("name", "") if isinstance(_at, dict) else str(_at or "")
                    if _afc._team_names_match(rh, fx_home) and _afc._team_names_match(ra, fx_away):
                        already_present = True
                        break
                if already_present:
                    continue
                # Convert to record and inject
                new_records = _afc.fixtures_to_records([fx], lid)
                if new_records:
                    records.extend(new_records)
                    injected += 1
            if injected:
                logger.info(
                    f"[fixtures] {lid}: injected {injected} live/finished matches "
                    f"from API-Football that FootyStats dropped"
                )

        except Exception as e:
            logger.warning(f"[fixtures] {lid}: API-Football enrichment failed: {e}", exc_info=True)

        return records

    # CASE 2: No records and not found via any API — use API-Football as fallback
    if not found_via_api:
        try:
            from datetime import timezone as _tz
            BRT = _tz(timedelta(hours=-3))
            now_brt = datetime.now(BRT)
            if date_str == "tomorrow":
                af_date = (now_brt + timedelta(days=1)).strftime("%Y-%m-%d")
            elif date_str == "today":
                af_date = now_brt.strftime("%Y-%m-%d")
            else:
                af_date = date_str

            af_fixtures = _afc.get_fixtures_by_date(af_league_id, season, af_date, ttl_minutes=30)
            if not af_fixtures:
                # Season fallback
                af_fixtures = _afc.get_fixtures_by_date(af_league_id, season + 1, af_date, ttl_minutes=30)
            if af_fixtures:
                records = _afc.fixtures_to_records(af_fixtures, lid)
                logger.info(f"[fixtures] {lid}: API-Football fallback provided {len(records)} records")

        except Exception as e:
            logger.warning(f"[fixtures] {lid}: API-Football fallback failed: {e}")

    return records


def _fallback_todays_matches(lid: str, league_config: dict, date: str, season_id: int = None) -> List[Dict[str, Any]]:
    """Use todays-matches endpoint to get ALL matches for a league on a given date.
    This endpoint returns all matches across all leagues for today/tomorrow/ISO-date in one call,
    so we filter by competition_id (season_id) or country+league name to extract only the relevant ones.

    Supports date values: "today", "tomorrow", or ISO date string "YYYY-MM-DD" (#153).
    """
    import re as _re
    # Accept "today", "tomorrow", or ISO date strings (YYYY-MM-DD) (#153)
    _is_iso_date = bool(_re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""))
    if date not in ("today", "tomorrow") and not _is_iso_date:
        return []
    try:
        from backend.services.util_service import status_map
        import time as _time
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz

        # Always pass explicit BRT date to the API to avoid UTC/BRT day boundary mismatch.
        # Without an explicit date, the API uses its own timezone (likely UTC) to determine
        # "today", which after 21:00 BRT (00:00 UTC) would return next-day matches.
        BRT = _tz(timedelta(hours=-3))
        now_brt = _dt.now(BRT)
        if _is_iso_date:
            date_param = date  # Already in YYYY-MM-DD format
        elif date == "tomorrow":
            date_param = (now_brt + _td(days=1)).strftime("%Y-%m-%d")
        else:
            date_param = now_brt.strftime("%Y-%m-%d")

        todays_data = footstats.get_todays_matches(date=date_param)
        if not todays_data.get("success"):
            return []

        raw_list = todays_data.get("data", [])
        if not raw_list:
            return []

        country = league_config["country"].lower()
        name = league_config["name"].lower()
        alt_names = [n.lower() for n in league_config.get("alt_names", [])]
        names_to_match = [name] + alt_names

        matched = []
        for m in raw_list:
            # Primary matching: by competition_id / league_id (most reliable)
            if season_id is not None:
                m_comp_id = m.get("competition_id") or m.get("league_id")
                if m_comp_id is not None:
                    try:
                        if int(m_comp_id) == int(season_id):
                            matched.append(m)
                            continue
                    except (ValueError, TypeError):
                        pass

            # Secondary matching: by country + competition name (string-based)
            # Try multiple field name patterns (API returns vary)
            comp_raw = m.get("competition_name") or m.get("league_name") or ""
            if not comp_raw and isinstance(m.get("competition"), dict):
                comp_raw = m["competition"].get("name", "")
            if not comp_raw:
                comp_raw = m.get("name") or ""
            comp = comp_raw.lower()
            # Also check "country" field if available
            m_country = (m.get("country") or "").lower()
            country_match = country in comp or country == m_country
            if not country_match:
                continue
            if not any(n in comp for n in names_to_match):
                continue
            matched.append(m)

        if not matched:
            # Log sample competition names for debugging
            sample_comps = set()
            for m in raw_list[:20]:
                cn = m.get("competition_name") or m.get("league_name") or ""
                if not cn and isinstance(m.get("competition"), dict):
                    cn = m["competition"].get("name", "")
                if cn:
                    sample_comps.add(cn)
            logger.warning(
                f"[fixtures] {lid}: todays-matches fallback found 0 matches "
                f"(season_id={season_id}, country={country}, names={names_to_match}, "
                f"total_raw={len(raw_list)}, sample_comps={list(sample_comps)[:10]})"
            )
            return []

        # Date guard: filter matched results by BRT date range to prevent
        # next-day matches from leaking into "today" results.
        from backend.main import date_range
        range_start, range_end = date_range(date)
        date_guarded = []
        for m in matched:
            du = m.get("date_unix")
            if du:
                try:
                    match_dt = _dt.fromtimestamp(int(du), tz=_tz.utc)
                    if not (range_start <= match_dt <= range_end):
                        continue
                except (ValueError, TypeError):
                    pass
            date_guarded.append(m)

        if len(date_guarded) < len(matched):
            logger.info(
                f"[fixtures] {lid}: date guard filtered {len(matched) - len(date_guarded)} "
                f"out-of-range matches from todays-matches fallback"
            )
        matched = date_guarded

        logger.info(f"[fixtures] {lid}: todays-matches matched {len(matched)} fixtures (season_id={season_id})")

        # Build minimal records from todays-matches data
        records = []
        for m in matched:
            home = team_name(m.get("home_name") or m.get("homeTeam") or "").strip()
            away = team_name(m.get("away_name") or m.get("awayTeam") or "").strip()
            if not home or not away:
                continue

            raw_status = str(m.get("status", "scheduled"))
            match_status = status_map(raw_status)

            # Guard kickoff time for live status
            kickoff_ts = m.get("date_unix")
            if match_status == "live" and kickoff_ts:
                try:
                    elapsed = (int(_time.time()) - int(kickoff_ts)) // 60
                    if elapsed < -2:
                        match_status = "scheduled"
                except (ValueError, TypeError):
                    pass

            dt_unix = m.get("date_unix")
            dt_str = ""
            if dt_unix:
                try:
                    dt_str = datetime.utcfromtimestamp(int(dt_unix)).strftime("%Y-%m-%dT%H:%M:%SZ")
                except (ValueError, TypeError):
                    dt_str = ""

            # Read odds
            odds_home = _safe_float(m.get("odds_ft_1"))
            odds_draw = _safe_float(m.get("odds_ft_x"))
            odds_away = _safe_float(m.get("odds_ft_2"))
            odds_over25 = _safe_float(m.get("odds_ft_over25"))
            odds_under25 = _safe_float(m.get("odds_ft_under25"))
            odds_btts_yes = _safe_float(m.get("odds_btts_yes"))
            odds_btts_no = _safe_float(m.get("odds_btts_no"))

            # Basic probability from odds (implied)
            from backend.services.math_service import implied_probs
            probs = implied_probs(odds_home, odds_draw, odds_away)

            # Compute over25/btts probabilities from odds (implied probability)
            over25_prob = 0.0
            btts_prob = 0.0
            if odds_over25 > 0:
                raw_over25 = 1.0 / odds_over25
                # Normalize with under25 if available
                if odds_under25 > 0:
                    raw_under25 = 1.0 / odds_under25
                    total = raw_over25 + raw_under25
                    over25_prob = round(raw_over25 / total * 100.0, 1) if total > 0 else 0.0
                else:
                    over25_prob = round(raw_over25 * 100.0, 1)
            if odds_btts_yes > 0:
                raw_btts = 1.0 / odds_btts_yes
                if odds_btts_no > 0:
                    raw_btts_no = 1.0 / odds_btts_no
                    total = raw_btts + raw_btts_no
                    btts_prob = round(raw_btts / total * 100.0, 1) if total > 0 else 0.0
                else:
                    btts_prob = round(raw_btts * 100.0, 1)

            # Extract score for live/finished matches (sanitize -1 sentinel)
            def _valid_goal_fb(val):
                if val is None:
                    return None
                try:
                    v = int(val)
                    return v if v >= 0 else None
                except (ValueError, TypeError):
                    return None

            def _count_goal_timings(val) -> Optional[int]:
                """Count goals from homeGoals/awayGoals field.

                FootyStats API returns goal timings as:
                  - JSON string: '["13","55"]' or '[]' (todays-matches)
                  - Python list: ["13","55"] (league-matches)
                The number of elements = number of goals scored.
                """
                if val is None:
                    return None
                if isinstance(val, str):
                    val = val.strip()
                    if val in ("[]", "", "null"):
                        return 0
                    try:
                        import json as _json
                        parsed = _json.loads(val)
                        if isinstance(parsed, list):
                            return len(parsed)
                    except (ValueError, TypeError):
                        pass
                    return None
                if isinstance(val, list):
                    return len(val)
                return None

            # Primary: homeGoalCount / awayGoalCount (reliable for finished matches)
            _home_goals = _valid_goal_fb(m.get("homeGoalCount"))
            _away_goals = _valid_goal_fb(m.get("awayGoalCount"))

            # Secondary: count goal timings from homeGoals/awayGoals arrays.
            # During live matches, homeGoalCount may stay 0 while homeGoals
            # array gets updated with goal timings (e.g. ["13", "55"] = 2 goals).
            _home_from_timings = _count_goal_timings(m.get("homeGoals"))
            _away_from_timings = _count_goal_timings(m.get("awayGoals"))

            # Tertiary: totalGoalCount as cross-check
            _total_goal_count = _valid_goal_fb(m.get("totalGoalCount"))

            # For finished matches: prefer homeGoalCount, fallback to timings
            if match_status != "live":
                if _home_goals is None and _home_from_timings is not None:
                    _home_goals = _home_from_timings
                if _away_goals is None and _away_from_timings is not None:
                    _away_goals = _away_from_timings

            # HT scores (from todays-matches — may be 0/null for live)
            _ht_home = _valid_goal_fb(m.get("ht_goals_team_a")) or _valid_goal_fb(m.get("home_team_goal_count_half_time"))
            _ht_away = _valid_goal_fb(m.get("ht_goals_team_b")) or _valid_goal_fb(m.get("away_team_goal_count_half_time"))

            # ALWAYS fetch individual match details for live matches.
            # The todays-matches endpoint returns homeGoalCount=0, awayGoalCount=0,
            # homeGoals="[]" for ALL incomplete/live matches — it NEVER updates
            # during the match. Only the individual /match endpoint has live scores.
            _has_goals_fb = _home_goals is not None and _away_goals is not None
            if match_status == "live":
                _fb_id = m.get("id")
                if _fb_id is not None:
                    try:
                        _fb_detail = footstats.get_match_live_details(int(_fb_id))
                        if _fb_detail.get("success"):
                            _fb_dd = _fb_detail.get("data", {})
                            if isinstance(_fb_dd, list) and _fb_dd:
                                _fb_dd = _fb_dd[0]
                            _fb_h = _valid_goal_fb(_fb_dd.get("homeGoalCount"))
                            _fb_a = _valid_goal_fb(_fb_dd.get("awayGoalCount"))
                            _fb_h_timings = _count_goal_timings(_fb_dd.get("homeGoals"))
                            _fb_a_timings = _count_goal_timings(_fb_dd.get("awayGoals"))
                            _fb_h_vals = [v for v in [_fb_h, _fb_h_timings] if v is not None]
                            _fb_a_vals = [v for v in [_fb_a, _fb_a_timings] if v is not None]
                            _fb_h_final = max(_fb_h_vals) if _fb_h_vals else None
                            _fb_a_final = max(_fb_a_vals) if _fb_a_vals else None
                            # FootyStats may return null goals for recently
                            # started live matches — default to 0 when the
                            # match detail endpoint confirms the match exists.
                            if _fb_h_final is None:
                                _fb_h_final = 0
                            if _fb_a_final is None:
                                _fb_a_final = 0
                            if _fb_h_final is not None and _fb_a_final is not None:
                                _home_goals = _fb_h_final
                                _away_goals = _fb_a_final
                                _has_goals_fb = True
                                _fb_ht_h = _valid_goal_fb(_fb_dd.get("ht_goals_team_a")) or _valid_goal_fb(_fb_dd.get("home_team_goal_count_half_time"))
                                _fb_ht_a = _valid_goal_fb(_fb_dd.get("ht_goals_team_b")) or _valid_goal_fb(_fb_dd.get("away_team_goal_count_half_time"))
                                if _fb_ht_h is not None and _fb_ht_a is not None:
                                    _ht_home = _fb_ht_h
                                    _ht_away = _fb_ht_a
                                logger.info(
                                    f"[fixtures] match-detail for {home} vs {away}: {_fb_h_final}-{_fb_a_final}"
                                )
                    except Exception as _fb_err:
                        logger.debug(f"[fixtures] match-detail failed for {home} vs {away}: {_fb_err}")

            # Default score for live matches: 0-0 (will be overwritten by
            # API-Football enrichment or match detail if available).
            match_score = {"home": 0, "away": 0} if match_status == "live" else None
            if match_status in ("finished", "live") and _has_goals_fb:
                match_score = {"home": _home_goals, "away": _away_goals}
                if _ht_home is not None and _ht_away is not None:
                    match_score["halftime"] = {"home": _ht_home, "away": _ht_away}

            # Compute period/minute for live matches
            period_fb = None
            minute_fb = None
            if match_status == "live" and kickoff_ts:
                try:
                    elapsed = max(0, (int(_time.time()) - int(kickoff_ts)) // 60)
                    has_ht = match_score and match_score.get("halftime") is not None
                    if elapsed <= 47:
                        period_fb = "1T"
                        minute_fb = min(elapsed, 45)
                    elif elapsed <= 62:
                        period_fb = "HT"
                        minute_fb = None
                    else:
                        period_fb = "2T"
                        minute_fb = min(elapsed - 15, 90)
                    if has_ht and period_fb == "1T":
                        period_fb = "2T"
                except (ValueError, TypeError):
                    pass

            record = {
                "id": f"{lid}-todays-{m.get('id', '')}",
                "footystatsId": m.get("id"),
                "leagueId": lid,
                "leagueName": league_config["name"],
                "homeTeam": {"name": home, "logo": "", "form": [], "rating": 0},
                "awayTeam": {"name": away, "logo": "", "form": [], "rating": 0},
                "datetime": dt_str,
                "match_date": dt_str,
                "venue": m.get("stadium", "") or "",
                "stadium": m.get("stadium", "") or "",
                "status": match_status,
                "score": match_score,
                "period": period_fb,
                "minute": minute_fb,
                "odds": {
                    "home": odds_home, "draw": odds_draw, "away": odds_away,
                    "over25": odds_over25, "under25": odds_under25,
                    "bttsYes": odds_btts_yes, "bttsNo": odds_btts_no,
                    "over15": _safe_float(m.get("odds_ft_over15")),
                    "over35": _safe_float(m.get("odds_ft_over35")),
                    "over45": _safe_float(m.get("odds_ft_over45")),
                },
                "stats": {
                    "homeWinProb": round(probs[0], 1) if probs else 0,
                    "drawProb": round(probs[1], 1) if probs else 0,
                    "awayWinProb": round(probs[2], 1) if probs else 0,
                    "avgGoals": 0,
                    "bttsProb": btts_prob,
                    "over25Prob": over25_prob,
                },
                "h2h": {"totalMatches": 0, "homeWins": 0, "draws": 0, "awayWins": 0, "avgGoals": 0},
                "source": "footystats",
                "dataSource": "FootyStats API (Jogos do Dia)",
                "lastUpdated": datetime.utcnow().isoformat() + "Z",
            }
            records.append(record)

        return records
    except Exception as e:
        logger.error(f"[fixtures] {lid}: todays-matches fallback error: {e}")
        return []


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


@router.get("/fixtures")
def fixtures(leagues: str = Query(""), date: str = Query("today")) -> Dict[str, Any]:
    from backend.main import get_data_dir
    league_ids = [lid.strip() for lid in leagues.split(",") if lid.strip()]
    if not league_ids:
        return {"matches": []}

    base = get_data_dir()

    # Single league: process directly (no thread overhead)
    if len(league_ids) == 1:
        records = _process_single_league(league_ids[0], date, base)
        return {"matches": records}

    # Multiple leagues: process in parallel threads
    out: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(_MAX_LEAGUE_WORKERS, len(league_ids))) as executor:
        futures = {
            executor.submit(_process_single_league, lid, date, base): lid
            for lid in league_ids
        }
        for future in as_completed(futures):
            lid = futures[future]
            try:
                records = future.result()
                if records:
                    out.extend(records)
            except Exception as e:
                logger.error(f"[fixtures] {lid}: thread crashed: {type(e).__name__}: {e}")

    # Sort by league order (request order) to avoid non-deterministic thread completion
    # mixing leagues (e.g. Danish Superliga between Premier League games)
    league_order = {lid: i for i, lid in enumerate(league_ids)}
    out.sort(key=lambda r: (league_order.get(r.get("leagueId", ""), 999), r.get("datetime", "")))

    return {"matches": out}


# ── Last-known live scores cache (#060) ──────────────────────────────
# When both FootyStats and API-Football fail (rate limit, outage),
# serve the last successful live-scores response instead of empty [].
# Expires after 5 minutes to avoid serving extremely stale data.
_LIVE_CACHE_TTL = 300  # seconds
_last_live_scores: Dict[str, Any] = {"matches": [], "ts": 0}


@router.get("/live-scores")
def live_scores() -> Dict[str, Any]:
    """Retorna placares ao vivo dos jogos do dia (cache de 1 min)."""
    import time as _time
    from backend.services.util_service import status_map
    try:
        data = footstats.get_live_scores()
        if not data.get("success"):
            # Serve cached data if FootyStats fails entirely (#060)
            _now_fail = int(_time.time())
            _age_fail = _now_fail - _last_live_scores["ts"]
            if _last_live_scores["matches"] and _age_fail < _LIVE_CACHE_TTL:
                logger.warning(
                    f"[live-scores] FootyStats failed → serving cached data "
                    f"({len(_last_live_scores['matches'])} matches, age={_age_fail}s)"
                )
                return {
                    "matches": _last_live_scores["matches"],
                    "nextUpdate": 30,
                    "stale": True,
                    "cacheAge": _age_fail,
                }
            return {"matches": [], "error": "Falha ao buscar placares"}
        raw_list = data.get("data", [])

        # ── API-Football as PRIMARY source when FootyStats is empty ─────
        # FootyStats todays-matches often returns [] for certain leagues.
        # API-Football get_live_fixtures() is the reliable source for live
        # scores, so use it directly when FootyStats has no data.
        if not raw_list and _afc.is_configured:
            try:
                af_live = _afc.get_live_fixtures()
                if af_live:
                    af_result = []
                    period_map = {"1H": "1T", "HT": "HT", "2H": "2T", "ET": "ET", "BT": "HT", "P": "PEN"}
                    for fx in af_live:
                        ld = _afc.extract_live_data(fx)
                        teams = fx.get("teams", {})
                        home_name = teams.get("home", {}).get("name", "")
                        away_name = teams.get("away", {}).get("name", "")
                        if not home_name or not away_name:
                            continue
                        fx_status = ld["status"]
                        live_statuses = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}
                        finished_statuses = {"FT", "AET", "PEN"}
                        if fx_status not in live_statuses and fx_status not in finished_statuses:
                            continue
                        status = "live" if fx_status in live_statuses else "finished"
                        score: Dict[str, Any] = {
                            "home": ld["goals_home"] if ld["goals_home"] is not None else 0,
                            "away": ld["goals_away"] if ld["goals_away"] is not None else 0,
                        }
                        if ld["halftime_home"] is not None:
                            score["halftime"] = {"home": ld["halftime_home"], "away": ld["halftime_away"]}
                        # Corner kicks total (home + away)
                        current_corners: int | None = None
                        current_cards: int | None = None
                        if ld.get("home_corners") is not None and ld.get("away_corners") is not None:
                            current_corners = ld["home_corners"] + ld["away_corners"]
                        elif ld.get("home_corners") is not None:
                            current_corners = ld["home_corners"]
                        elif ld.get("away_corners") is not None:
                            current_corners = ld["away_corners"]
                        # Fallback: inline stats may be missing for some leagues (e.g. Brazilian Serie A)
                        if (current_corners is None or current_cards is None) and ld.get("fixture_id") is not None:
                            try:
                                _raw_stats = _afc.get_fixture_statistics(int(ld["fixture_id"]), ttl_minutes=5)
                                if _raw_stats:
                                    if current_corners is None:
                                        _hc, _ac = _afc._extract_corners_from_stats(_raw_stats)
                                        if _hc is not None and _ac is not None:
                                            current_corners = int(_hc) + int(_ac)
                                    _parsed = _afc.parse_fixture_statistics(_raw_stats)
                                    if current_corners is None:
                                        _hc = _parsed.get("home", {}).get("corner_kicks")
                                        _ac = _parsed.get("away", {}).get("corner_kicks")
                                        if _hc is not None and _ac is not None:
                                            current_corners = int(_hc) + int(_ac)
                                    # Cards: yellow + red (#149b)
                                    if current_cards is None:
                                        _hy = _parsed.get("home", {}).get("yellow_cards")
                                        _ay = _parsed.get("away", {}).get("yellow_cards")
                                        _hr = _parsed.get("home", {}).get("red_cards")
                                        _ar = _parsed.get("away", {}).get("red_cards")
                                        if _hy is not None and _ay is not None:
                                            current_cards = int(_hy or 0) + int(_ay or 0) + int(_hr or 0) + int(_ar or 0)
                                    if current_corners is None:
                                        _sample = list(_raw_stats[0].keys()) if _raw_stats and isinstance(_raw_stats[0], dict) else "non-dict"
                                        logger.info(
                                            f"[live-scores] corners fallback: fixture_id={ld['fixture_id']}, "
                                            f"raw_stats_len={len(_raw_stats)}, first_block_keys={_sample}"
                                        )
                            except Exception as _stat_err:
                                logger.info(f"[live-scores] corners fallback failed fixture_id={ld['fixture_id']}: {_stat_err}")

                        entry: Dict[str, Any] = {
                            "id": ld["fixture_id"],
                            "homeTeam": home_name,
                            "awayTeam": away_name,
                            "status": status,
                            "score": score,
                            "period": period_map.get(fx_status),
                            "minute": ld["minute"],
                            "dateUnix": fx.get("fixture", {}).get("timestamp"),
                        }
                        if current_corners is not None:
                            entry["currentCorners"] = current_corners
                        if current_cards is not None:
                            entry["currentCards"] = current_cards
                        af_result.append(entry)
                    if af_result:
                        logger.info(
                            f"[live-scores] FootyStats empty → API-Football primary: "
                            f"{len(af_result)} matches"
                        )
                        # Cache successful result (#060)
                        _last_live_scores["matches"] = af_result
                        _last_live_scores["ts"] = int(_time.time())
                        return {"matches": af_result, "nextUpdate": 30}
            except Exception as _af_err:
                logger.warning(f"[live-scores] API-Football primary fallback failed: {_af_err}")

        if not raw_list:
            # Both APIs failed — serve last-known scores if fresh enough (#060)
            _now = int(_time.time())
            _age = _now - _last_live_scores["ts"]
            if _last_live_scores["matches"] and _age < _LIVE_CACHE_TTL:
                logger.warning(
                    f"[live-scores] Both APIs empty → serving cached data "
                    f"({len(_last_live_scores['matches'])} matches, age={_age}s)"
                )
                return {
                    "matches": _last_live_scores["matches"],
                    "nextUpdate": 30,
                    "stale": True,
                    "cacheAge": _age,
                }
            return {"matches": []}
        now_ts = int(_time.time())
        result = []
        skipped_statuses: Dict[str, int] = {}
        for m in raw_list:
            raw_status = str(m.get("status", ""))
            status = status_map(raw_status)

            kickoff_ts = m.get("date_unix")
            elapsed_min = None
            if kickoff_ts:
                try:
                    elapsed_min = (now_ts - int(kickoff_ts)) // 60
                except (ValueError, TypeError):
                    pass

            # Guard: if API reports "live" but kickoff is in the future, demote to "scheduled".
            # FootyStats sometimes returns "incomplete"/"live" for matches not yet started.
            if status == "live" and elapsed_min is not None and elapsed_min < -2:
                logger.info(
                    f"[live-scores] Overriding 'live' → 'scheduled': "
                    f"{m.get('home_name')} vs {m.get('away_name')} "
                    f"(raw_status={raw_status!r}, kickoff in {abs(elapsed_min)} min)"
                )
                status = "scheduled"

            # Detect live matches by checking if kickoff time has passed.
            # Cap at 120 min (90' + 15' HT + 15' extra) to avoid promoting
            # finished matches that the API reports as "incomplete".
            if status == "scheduled" and elapsed_min is not None and 0 <= elapsed_min < 120:
                status = "live"
                logger.info(
                    f"[live-scores] Inferred live from kickoff: "
                    f"{m.get('home_name')} vs {m.get('away_name')} "
                    f"(raw_status={raw_status!r}, elapsed={elapsed_min}min)"
                )

            if status not in ("live", "finished"):
                skipped_statuses[raw_status] = skipped_statuses.get(raw_status, 0) + 1
                continue

            # Read goal count from FootyStats API fields.
            # Per API docs, todays-matches returns:
            #   homeGoalCount (int, 0 default), homeGoals (JSON string of timing array)
            # For live matches, homeGoalCount may stay 0 while homeGoals array
            # gets populated with goal timings. We use both sources.
            def _valid_goal(val):
                """Return int if val is a valid goal count (>= 0), else None."""
                if val is None:
                    return None
                try:
                    v = int(val)
                    return v if v >= 0 else None
                except (ValueError, TypeError):
                    return None

            def _count_goal_timings_ls(val) -> Optional[int]:
                """Count goals from homeGoals/awayGoals timing arrays."""
                if val is None:
                    return None
                if isinstance(val, str):
                    val = val.strip()
                    if val in ("[]", "", "null"):
                        return 0
                    try:
                        import json as _json
                        parsed = _json.loads(val)
                        if isinstance(parsed, list):
                            return len(parsed)
                    except (ValueError, TypeError):
                        pass
                    return None
                if isinstance(val, list):
                    return len(val)
                return None

            # ── Build ScoreCandidate from todays-matches data ──
            _tm_home = _valid_goal(m.get("homeGoalCount"))
            _tm_away = _valid_goal(m.get("awayGoalCount"))
            _tm_h_t = _count_goal_timings_ls(m.get("homeGoals"))
            _tm_a_t = _count_goal_timings_ls(m.get("awayGoals"))
            _h_all = [v for v in [_tm_home, _tm_h_t] if v is not None]
            _a_all = [v for v in [_tm_away, _tm_a_t] if v is not None]
            _tm_home = max(_h_all) if _h_all else None
            _tm_away = max(_a_all) if _a_all else None

            # If individual goal fields are missing, try HT data as fallback
            _total = _valid_goal(m.get("totalGoalCount"))
            if (_tm_home is None or _tm_away is None) and _total is not None and _total > 0:
                _ht_h = _valid_goal(m.get("ht_goals_team_a")) or _valid_goal(m.get("home_team_goal_count_half_time"))
                _ht_a = _valid_goal(m.get("ht_goals_team_b")) or _valid_goal(m.get("away_team_goal_count_half_time"))
                if _ht_h is not None and _ht_a is not None:
                    _tm_home = _tm_home if _tm_home is not None else _ht_h
                    _tm_away = _tm_away if _tm_away is not None else _ht_a

            todays_candidate = ScoreCandidate(
                home=_tm_home, away=_tm_away,
                source=SOURCE_TODAYS_MATCHES,
                has_data=_tm_home is not None and _tm_away is not None,
            )

            _match_label = f"{m.get('home_name', '?')} vs {m.get('away_name', '?')}"
            detail_candidate = None

            # ALWAYS fetch individual match details for live matches.
            # The todays-matches endpoint often returns stale 0-0 for live games.
            if status == "live":
                _raw_id = m.get("id")
                if _raw_id is not None:
                    try:
                        detail = footstats.get_match_live_details(int(_raw_id))
                        if detail.get("success"):
                            dd = detail.get("data", {})
                            if isinstance(dd, list) and dd:
                                dd = dd[0]
                            _fb_home = _valid_goal(dd.get("homeGoalCount"))
                            _fb_away = _valid_goal(dd.get("awayGoalCount"))
                            _fb_h_t = _count_goal_timings_ls(dd.get("homeGoals"))
                            _fb_a_t = _count_goal_timings_ls(dd.get("awayGoals"))
                            _fb_h_vals = [v for v in [_fb_home, _fb_h_t] if v is not None]
                            _fb_a_vals = [v for v in [_fb_away, _fb_a_t] if v is not None]
                            _fb_home = max(_fb_h_vals) if _fb_h_vals else None
                            _fb_away = max(_fb_a_vals) if _fb_a_vals else None

                            # Null goals from a successful response → treat as 0-0
                            if _fb_home is None:
                                _fb_home = 0
                            if _fb_away is None:
                                _fb_away = 0

                            detail_candidate = ScoreCandidate(
                                home=_fb_home, away=_fb_away,
                                source=SOURCE_MATCH_DETAIL,
                                has_data=True,
                            )
                    except Exception as _fb_err:
                        logger.warning(f"[live-scores] match-detail failed for id={_raw_id}: {_fb_err}")
                else:
                    logger.warning(f"[live-scores] match has no id — cannot fetch detail for {_match_label}")
            elif status != "finished":
                continue

            # Merge scores (API-Football will be applied later in the enrichment pass)
            merge_result = merge_live_scores(
                todays=todays_candidate,
                detail=detail_candidate,
                api_football=None,  # applied in enrichment pass below
                match_label=_match_label,
            )
            home_goals = merge_result.home
            away_goals = merge_result.away
            _score_source = merge_result.source
            _score_conflict = merge_result.conflict_detected

            # Diagnostic logging: trace every score source per live match
            if status == "live":
                logger.info(
                    f"[live-scores][diag] {_match_label} | "
                    f"todays={todays_candidate.home}-{todays_candidate.away} "
                    f"detail={detail_candidate.home}-{detail_candidate.away if detail_candidate else 'N/A'} "
                    f"merge={merge_result.home}-{merge_result.away} "
                    f"source={merge_result.source} "
                    f"conflict={merge_result.conflict_detected} "
                    f"candidates={merge_result.candidates_seen}"
                )

            # _valid_goal already returns int, but ensure type safety
            home_goals = int(home_goals)
            away_goals = int(away_goals)

            ht_home = m.get("home_team_goal_count_half_time")
            ht_away = m.get("away_team_goal_count_half_time")
            halftime = None
            has_ht = False
            if ht_home is not None and ht_away is not None:
                try:
                    _hth, _hta = int(ht_home), int(ht_away)
                    if _hth >= 0 and _hta >= 0:
                        halftime = {"home": _hth, "away": _hta}
                        has_ht = True
                except (ValueError, TypeError):
                    pass
            score = {"home": home_goals, "away": away_goals}
            if halftime:
                score["halftime"] = halftime
            # Determine period and approximate minute for live matches
            period = None
            minute = None
            if status == "live":
                kickoff_ts = m.get("date_unix")
                if kickoff_ts:
                    try:
                        elapsed = max(0, (now_ts - int(kickoff_ts)) // 60)
                        if elapsed <= 47:
                            period = "1T"
                            minute = min(elapsed, 45)
                        elif elapsed <= 62:
                            period = "HT"
                            minute = None
                        else:
                            period = "2T"
                            minute = min(elapsed - 15, 90)
                    except (ValueError, TypeError):
                        pass
                # Override: if halftime data exists, at least 2nd half
                if has_ht and period == "1T":
                    period = "2T"

            # Normalize team names: strip whitespace for reliable frontend matching
            home_name = team_name(m.get("home_name") or m.get("homeTeam") or "").strip()
            away_name = team_name(m.get("away_name") or m.get("awayTeam") or "").strip()

            _raw_id = m.get("id")

            # FootyStats corner data (#070 — was never read in /live-scores)
            _fs_hc = m.get("team_a_corners")
            _fs_ac = m.get("team_b_corners")
            _fs_corners: int | None = None
            if _fs_hc is not None and _fs_ac is not None:
                try:
                    _fhc, _fac = int(_fs_hc), int(_fs_ac)
                    if _fhc >= 0 and _fac >= 0:
                        _fs_corners = _fhc + _fac
                except (ValueError, TypeError):
                    pass

            _rec: Dict[str, Any] = {
                "id": int(_raw_id) if _raw_id is not None else None,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "status": status,
                "score": score,
                "period": period,
                "minute": minute,
                "dateUnix": m.get("date_unix"),
                # Observability fields
                "scoreSourceFinal": _score_source,
                "scoreConflictDetected": _score_conflict,
            }
            if _fs_corners is not None:
                _rec["currentCorners"] = _fs_corners
            result.append(_rec)
        if skipped_statuses:
            logger.info(f"[live-scores] Skipped statuses: {skipped_statuses}")

        # ── API-Football as PRIMARY when FootyStats had data but all filtered (#075) ──
        # FootyStats may return matches from other leagues (all "scheduled") while
        # the Argentine/Colombian league matches are only in API-Football.
        # In this case raw_list is non-empty but result is empty after filtering.
        if not result and _afc.is_configured:
            try:
                af_live = _afc.get_live_fixtures()
                if af_live:
                    af_result = []
                    period_map = {"1H": "1T", "HT": "HT", "2H": "2T", "ET": "ET", "BT": "HT", "P": "PEN"}
                    for fx in af_live:
                        ld = _afc.extract_live_data(fx)
                        teams = fx.get("teams", {})
                        home_name = teams.get("home", {}).get("name", "")
                        away_name = teams.get("away", {}).get("name", "")
                        if not home_name or not away_name:
                            continue
                        fx_status = ld["status"]
                        live_statuses = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}
                        finished_statuses = {"FT", "AET", "PEN"}
                        if fx_status not in live_statuses and fx_status not in finished_statuses:
                            continue
                        _af_status = "live" if fx_status in live_statuses else "finished"
                        score_entry: Dict[str, Any] = {
                            "home": ld["goals_home"] if ld["goals_home"] is not None else 0,
                            "away": ld["goals_away"] if ld["goals_away"] is not None else 0,
                        }
                        if ld["halftime_home"] is not None:
                            score_entry["halftime"] = {"home": ld["halftime_home"], "away": ld["halftime_away"]}
                        current_corners: int | None = None
                        current_cards: int | None = None
                        if ld.get("home_corners") is not None and ld.get("away_corners") is not None:
                            current_corners = ld["home_corners"] + ld["away_corners"]
                        elif ld.get("home_corners") is not None:
                            current_corners = ld["home_corners"]
                        elif ld.get("away_corners") is not None:
                            current_corners = ld["away_corners"]
                        if (current_corners is None or current_cards is None) and ld.get("fixture_id") is not None:
                            try:
                                _raw_stats = _afc.get_fixture_statistics(int(ld["fixture_id"]), ttl_minutes=5)
                                if _raw_stats:
                                    if current_corners is None:
                                        _hc, _ac = _afc._extract_corners_from_stats(_raw_stats)
                                        if _hc is not None and _ac is not None:
                                            current_corners = int(_hc) + int(_ac)
                                    _parsed = _afc.parse_fixture_statistics(_raw_stats)
                                    if current_corners is None:
                                        _hc = _parsed.get("home", {}).get("corner_kicks")
                                        _ac = _parsed.get("away", {}).get("corner_kicks")
                                        if _hc is not None and _ac is not None:
                                            current_corners = int(_hc) + int(_ac)
                                    # Cards: yellow + red (#149b)
                                    if current_cards is None:
                                        _hy = _parsed.get("home", {}).get("yellow_cards")
                                        _ay = _parsed.get("away", {}).get("yellow_cards")
                                        _hr = _parsed.get("home", {}).get("red_cards")
                                        _ar = _parsed.get("away", {}).get("red_cards")
                                        if _hy is not None and _ay is not None:
                                            current_cards = int(_hy or 0) + int(_ay or 0) + int(_hr or 0) + int(_ar or 0)
                            except Exception as _stat_err:
                                logger.info(f"[live-scores] corners/cards fallback failed fixture_id={ld['fixture_id']}: {_stat_err}")
                        entry: Dict[str, Any] = {
                            "id": ld["fixture_id"],
                            "homeTeam": home_name,
                            "awayTeam": away_name,
                            "status": _af_status,
                            "score": score_entry,
                            "period": period_map.get(fx_status),
                            "minute": ld["minute"],
                            "dateUnix": fx.get("fixture", {}).get("timestamp"),
                        }
                        if current_corners is not None:
                            entry["currentCorners"] = current_corners
                        if current_cards is not None:
                            entry["currentCards"] = current_cards
                        af_result.append(entry)
                    if af_result:
                        logger.info(
                            f"[live-scores] FootyStats filtered to 0 → API-Football primary: "
                            f"{len(af_result)} matches"
                        )
                        result = af_result
            except Exception as _af_err:
                logger.warning(f"[live-scores] API-Football post-filter fallback failed: {_af_err}")

        # ── API-Football enrichment for live matches ──────────────────────
        # FootyStats often returns 0-0 for live matches even via the
        # individual /match endpoint.  API-Football provides reliable
        # real-time scores, so we overlay them on top.
        _af_enriched = 0
        if _afc.is_configured:
            try:
                af_live = _afc.get_live_fixtures()  # 1-min cache
                if af_live:
                    for rec in result:
                        if rec["status"] != "live":
                            continue
                        rh = str(rec.get("homeTeam") or "")
                        ra = str(rec.get("awayTeam") or "")

                        # Use robust matching (unicode normalization, prefix removal, token overlap)
                        matched_fx = None
                        af_swapped = False
                        for fx in af_live:
                            fx_home = fx.get("teams", {}).get("home", {}).get("name", "")
                            fx_away = fx.get("teams", {}).get("away", {}).get("name", "")
                            if _afc._team_names_match(rh, fx_home) and _afc._team_names_match(ra, fx_away):
                                matched_fx = fx
                                break

                        # Pass 2: swapped order (#069, same pattern as find_fixture in api_football_client.py)
                        if not matched_fx:
                            for fx in af_live:
                                fx_home = fx.get("teams", {}).get("home", {}).get("name", "")
                                fx_away = fx.get("teams", {}).get("away", {}).get("name", "")
                                if _afc._team_names_match(rh, fx_away) and _afc._team_names_match(ra, fx_home):
                                    matched_fx = fx
                                    af_swapped = True
                                    logger.info(f"[live-scores] AF match found via SWAP for {rh} vs {ra}")
                                    break

                        if not matched_fx:
                            # Log unmatched live matches for debugging (esp. Arabic teams)
                            af_sample = [
                                (fx.get("teams", {}).get("home", {}).get("name", ""),
                                 fx.get("teams", {}).get("away", {}).get("name", ""))
                                for fx in af_live[:8]
                            ]
                            logger.warning(
                                f"[live-scores] No AF match for '{rh}' vs '{ra}' "
                                f"(norm: '{_afc._normalize_team_name(rh)}' vs '{_afc._normalize_team_name(ra)}') "
                                f"| AF live sample: {af_sample}"
                            )
                            continue

                        ld = _afc.extract_live_data(matched_fx)
                        if ld["goals_home"] is None:
                            logger.warning(
                                f"[live-scores] AF match found for {rh} vs {ra} but goals=null "
                                f"(fixture_id={matched_fx.get('fixture', {}).get('id')}). "
                                f"Skipping AF overlay."
                            )
                            continue

                        # Overlay score from API-Football via merge function
                        # When matched via swap (#069), invert goals to match our home/away
                        af_home_g = ld["goals_away"] if af_swapped else ld["goals_home"]
                        af_away_g = ld["goals_home"] if af_swapped else ld["goals_away"]

                        cur_score = rec.get("score") or {}
                        cur_home = cur_score.get("home", 0) if isinstance(cur_score, dict) else 0
                        cur_away = cur_score.get("away", 0) if isinstance(cur_score, dict) else 0

                        # Use merge function with existing score as "current" and AF as overlay
                        _current_candidate = ScoreCandidate(
                            home=cur_home, away=cur_away,
                            source=rec.get("scoreSourceFinal", SOURCE_TODAYS_MATCHES),
                            has_data=True,
                        )
                        _af_candidate = ScoreCandidate(
                            home=af_home_g, away=af_away_g,
                            source=SOURCE_API_FOOTBALL,
                            has_data=True,
                        )
                        af_merge = merge_live_scores(
                            todays=_current_candidate,
                            api_football=_af_candidate,
                            match_label=f"{rec.get('homeTeam', '?')} vs {rec.get('awayTeam', '?')}",
                        )

                        if af_merge.source == SOURCE_API_FOOTBALL:
                            new_score: Dict[str, Any] = {"home": af_merge.home, "away": af_merge.away}
                            if ld["halftime_home"] is not None:
                                new_score["halftime"] = {"home": ld["halftime_home"], "away": ld["halftime_away"]}
                            elif isinstance(cur_score, dict) and cur_score.get("halftime"):
                                new_score["halftime"] = cur_score["halftime"]
                            rec["score"] = new_score

                        rec["scoreSourceFinal"] = af_merge.source
                        rec["scoreConflictDetected"] = af_merge.conflict_detected or rec.get("scoreConflictDetected", False)
                        rec["apiFootballOverlayApplied"] = af_merge.source == SOURCE_API_FOOTBALL

                        # Diagnostic: trace API-Football overlay decision
                        logger.info(
                            f"[live-scores][diag-af] {rec.get('homeTeam', '?')} vs {rec.get('awayTeam', '?')} | "
                            f"before={cur_home}-{cur_away}({rec.get('scoreSourceFinal','?')}) "
                            f"af={af_home_g}-{af_away_g} "
                            f"after={af_merge.home}-{af_merge.away}({af_merge.source}) "
                            f"overlay={af_merge.source == SOURCE_API_FOOTBALL} "
                            f"conflict={af_merge.conflict_detected}"
                        )

                        # Always update minute/period from API-Football (more accurate)
                        if ld["minute"] is not None:
                            rec["minute"] = ld["minute"]
                        af_status = ld["status"]
                        period_map = {"1H": "1T", "HT": "HT", "2H": "2T"}
                        if af_status in period_map:
                            rec["period"] = period_map[af_status]

                        # Overlay corner kicks and cards from API-Football
                        _corners: int | None = None
                        _cards: int | None = None
                        if ld.get("home_corners") is not None and ld.get("away_corners") is not None:
                            _corners = ld["home_corners"] + ld["away_corners"]
                        elif ld.get("home_corners") is not None:
                            _corners = ld["home_corners"]
                        elif ld.get("away_corners") is not None:
                            _corners = ld["away_corners"]
                        # Fallback: /fixtures?live=all may not include inline statistics for some
                        # leagues (e.g. Brazilian Serie A). Fetch /fixtures/statistics explicitly.
                        if _corners is None or _cards is None:
                            _fx_id = matched_fx.get("fixture", {}).get("id")
                            if _fx_id is not None:
                                try:
                                    _raw_stats = _afc.get_fixture_statistics(int(_fx_id), ttl_minutes=5)
                                    if _raw_stats:
                                        if _corners is None:
                                            _hc, _ac = _afc._extract_corners_from_stats(_raw_stats)
                                            if _hc is not None and _ac is not None:
                                                _corners = int(_hc) + int(_ac)
                                        _parsed = _afc.parse_fixture_statistics(_raw_stats)
                                        if _corners is None:
                                            _hc = _parsed.get("home", {}).get("corner_kicks")
                                            _ac = _parsed.get("away", {}).get("corner_kicks")
                                            if _hc is not None and _ac is not None:
                                                _corners = int(_hc) + int(_ac)
                                        # Cards: yellow + red (#149b)
                                        if _cards is None:
                                            _hy = _parsed.get("home", {}).get("yellow_cards")
                                            _ay = _parsed.get("away", {}).get("yellow_cards")
                                            _hr = _parsed.get("home", {}).get("red_cards")
                                            _ar = _parsed.get("away", {}).get("red_cards")
                                            if _hy is not None and _ay is not None:
                                                _cards = int(_hy or 0) + int(_ay or 0) + int(_hr or 0) + int(_ar or 0)
                                        if _corners is None:
                                            _sample = list(_raw_stats[0].keys()) if _raw_stats and isinstance(_raw_stats[0], dict) else "non-dict"
                                            logger.info(
                                                f"[live-scores] corners fallback: fixture_id={_fx_id}, "
                                                f"raw_stats_len={len(_raw_stats)}, first_block_keys={_sample}"
                                            )
                                except Exception as _stat_err:
                                    logger.info(f"[live-scores] corners/cards fallback failed fixture_id={_fx_id}: {_stat_err}")
                        if _corners is not None:
                            rec["currentCorners"] = _corners
                        elif rec.get("currentCorners") is None:
                            # Camada 2 (#070): warn when no corner source found for live match
                            logger.warning(
                                f"[live-scores][corners] No corner data for live match "
                                f"{rh} vs {ra} (AF=none, FS pre-enrich=none)"
                            )
                        if _cards is not None:
                            rec["currentCards"] = _cards

                        _af_enriched += 1

                if _af_enriched:
                    logger.info(f"[live-scores] API-Football enriched {_af_enriched} live matches")
            except Exception as _af_err:
                logger.warning(f"[live-scores] API-Football enrichment failed: {_af_err}")

        # Cache successful live scores for resilience (#060)
        if result:
            _last_live_scores["matches"] = result
            _last_live_scores["ts"] = int(_time.time())

        logger.info(
            f"[live-scores] Returned {len(result)} matches (from {len(raw_list)} raw) "
            f"| scores: {[(r['homeTeam'][:12], r['score']['home'] if r.get('score') else '?', r['score']['away'] if r.get('score') else '?') for r in result[:5]]}"
        )
        return {"matches": result, "nextUpdate": 60}
    except Exception as e:
        logger.error(f"[live-scores] Error: {e}")
        # Serve cached data on exception too (#060)
        import time as _t2
        _now = int(_t2.time())
        _age = _now - _last_live_scores["ts"]
        if _last_live_scores["matches"] and _age < _LIVE_CACHE_TTL:
            logger.warning(
                f"[live-scores] Exception → serving cached data "
                f"({len(_last_live_scores['matches'])} matches, age={_age}s)"
            )
            return {
                "matches": _last_live_scores["matches"],
                "nextUpdate": 30,
                "stale": True,
                "cacheAge": _age,
                "error": str(e),
            }
        return {"matches": [], "error": str(e)}


@router.get("/standings")
def standings(league: str = Query("")) -> Dict[str, Any]:
    """Retorna a tabela de classificação de uma liga via FootyStats API."""
    if not league:
        return {"standings": [], "error": "Parâmetro 'league' é obrigatório"}
    league_config = get_league_config(league)
    if not league_config:
        return {"standings": [], "error": f"Liga '{league}' não configurada"}
    try:
        season_id = footstats.resolve_season_id(
            league_config["country"], league_config["name"],
            alt_names=league_config.get("alt_names"),
        )
        if not season_id:
            return {"standings": [], "error": "Season não encontrada"}
        data = footstats.get_league_tables(season_id)
        if not data.get("success"):
            return {"standings": [], "error": "Falha ao buscar classificação"}
        # FootyStats returns a dict with league_table, all_matches_table_*, etc.
        raw = data.get("data", {})
        table = (raw.get("league_table") or []) if isinstance(raw, dict) else (raw or [])
        # Normalize field names for the frontend
        standings_list = []
        for team in table:
            standings_list.append({
                **team,
                "won": team.get("seasonWins_overall", 0),
                "drawn": team.get("seasonDraws_overall", 0),
                "lost": team.get("seasonLosses_overall", 0),
                "played": team.get("matchesPlayed", 0),
            })
        return {"standings": standings_list, "leagueId": league}
    except Exception as e:
        logger.error(f"Erro ao buscar standings para {league}: {e}")
        return {"standings": [], "error": str(e)}
