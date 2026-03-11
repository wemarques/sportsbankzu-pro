from fastapi import APIRouter, Query
from typing import Dict, Any, List
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
from backend.config.leagues_config import get_league_config, get_api_football_league_id

logger = logging.getLogger("sportsbankzu.fixtures")
router = APIRouter(tags=["fixtures"])
footstats = FootyStatsClient()
_afc = APIFootballClient()

# Max threads for parallel league processing within a single request.
# Keeps API call volume reasonable while dramatically reducing latency.
_MAX_LEAGUE_WORKERS = 4


def _process_single_league(lid: str, date: str, base: str) -> List[Dict[str, Any]]:
    """Process a single league: API fetch → build records. Thread-safe."""
    from backend.main import resolve_league_dir, generate_mock_fixtures

    league_config = get_league_config(lid)
    records: List[Dict[str, Any]] = []
    found_via_api = False

    if league_config:
        try:
            season_id = footstats.resolve_season_id(
                league_config["country"], league_config["name"],
                alt_names=league_config.get("alt_names"),
            )
            if season_id:
                matches_data = footstats.get_league_matches(season_id)

                if matches_data.get("success"):
                    raw_list = matches_data.get("data", [])
                    if not raw_list:
                        logger.warning(f"[fixtures] {lid}: API success but empty data list")
                        return []
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
                        season_stats = footstats.get_league_season_stats(season_id)
                        if season_stats.get("success"):
                            season_data = season_stats.get("data", {})
                            if isinstance(season_data, dict):
                                league_season_data = season_data
                    except Exception as e:
                        logger.warning(f"[fixtures] {lid}: failed to load season-stats: {e}")

                    try:
                        teams_data = footstats.get_league_teams(season_id)
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
                            teams2=None,
                            league_df=league_df,
                            players=None,
                            date_filter=date,
                        )
                    except Exception as e:
                        logger.error(f"[fixtures] {lid}: build_records_from_matches crashed: {type(e).__name__}: {e}")
                        records = []

                    if records:
                        for r in records:
                            r["dataSource"] = "FootyStats API (Tempo Real)"
                    else:
                        logger.warning(f"[fixtures] {lid}: API OK but 0 records for date '{date}', trying todays-matches fallback")
                        # Fallback: league-matches may not include today's fixtures on page 1
                        # (pagination issue for leagues deep into their season).
                        # Use the todays-matches endpoint which returns all of today's matches.
                        records = _fallback_todays_matches(lid, league_config, date, season_id=season_id)
                        if records:
                            logger.info(f"[fixtures] {lid}: todays-matches fallback found {len(records)} records")
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

    season = _current_season()

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

            af_fixtures = _afc.get_fixtures_by_date(af_league_id, season, af_date, ttl_minutes=2)
            if not af_fixtures:
                return records

            # Build a lookup by team name for matching
            af_by_home: dict = {}
            for fx in af_fixtures:
                home = (fx.get("teams", {}).get("home", {}).get("name") or "").lower().strip()
                if home:
                    af_by_home[home] = fx

            enriched = 0
            for rec in records:
                home = (rec.get("homeTeam") or "").lower().strip()
                away = (rec.get("awayTeam") or "").lower().strip()

                # Try exact match first, then substring match
                matched_fx = af_by_home.get(home)
                if not matched_fx:
                    for af_home, fx in af_by_home.items():
                        if (home in af_home or af_home in home):
                            af_away = (fx.get("teams", {}).get("away", {}).get("name") or "").lower().strip()
                            if away in af_away or af_away in away:
                                matched_fx = fx
                                break

                if matched_fx:
                    _afc.enrich_fixture_record(rec, matched_fx)
                    enriched += 1

            if enriched:
                logger.info(f"[fixtures] {lid}: API-Football enriched {enriched}/{len(records)} records")

        except Exception as e:
            logger.warning(f"[fixtures] {lid}: API-Football enrichment failed: {e}")

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

            af_fixtures = _afc.get_fixtures_by_date(af_league_id, season, af_date, ttl_minutes=5)
            if af_fixtures:
                records = _afc.fixtures_to_records(af_fixtures, lid)
                logger.info(f"[fixtures] {lid}: API-Football fallback provided {len(records)} records")

        except Exception as e:
            logger.warning(f"[fixtures] {lid}: API-Football fallback failed: {e}")

    return records


def _fallback_todays_matches(lid: str, league_config: dict, date: str, season_id: int = None) -> List[Dict[str, Any]]:
    """Fallback: use todays-matches endpoint when league-matches has no records for today.
    This endpoint returns all matches across all leagues for today in one call,
    so we filter by competition_id (season_id) or country+league name to extract only the relevant ones."""
    if date not in ("today", "tomorrow"):
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
        if date == "tomorrow":
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

    return {"matches": out}


@router.get("/live-scores")
def live_scores() -> Dict[str, Any]:
    """Retorna placares ao vivo dos jogos do dia (cache de 1 min)."""
    import time as _time
    from backend.services.util_service import status_map
    try:
        data = footstats.get_live_scores()
        if not data.get("success"):
            return {"matches": [], "error": "Falha ao buscar placares"}
        raw_list = data.get("data", [])
        if not raw_list:
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
            if status == "scheduled" and elapsed_min is not None and 0 <= elapsed_min < 150:
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

            # Primary: homeGoalCount/awayGoalCount
            home_goals = _valid_goal(m.get("homeGoalCount"))
            away_goals = _valid_goal(m.get("awayGoalCount"))
            # Secondary: count goal timings from homeGoals/awayGoals arrays
            _home_timings = _count_goal_timings_ls(m.get("homeGoals"))
            _away_timings = _count_goal_timings_ls(m.get("awayGoals"))
            # Take MAX between count and timings (one may lag behind the other)
            _h_all = [v for v in [home_goals, _home_timings] if v is not None]
            _a_all = [v for v in [away_goals, _away_timings] if v is not None]
            home_goals = max(_h_all) if _h_all else None
            away_goals = max(_a_all) if _a_all else None

            _total = _valid_goal(m.get("totalGoalCount"))

            # If individual goal fields are missing, try totalGoalCount as evidence
            _has_goal_data = home_goals is not None and away_goals is not None
            if not _has_goal_data:
                if _total is not None and _total > 0:
                    # Try HT data as fallback
                    _ht_h = _valid_goal(m.get("ht_goals_team_a")) or _valid_goal(m.get("home_team_goal_count_half_time"))
                    _ht_a = _valid_goal(m.get("ht_goals_team_b")) or _valid_goal(m.get("away_team_goal_count_half_time"))
                    if _ht_h is not None and _ht_a is not None:
                        home_goals = home_goals if home_goals is not None else _ht_h
                        away_goals = away_goals if away_goals is not None else _ht_a
                        _has_goal_data = True
                        logger.info(
                            f"[live-scores] Using HT data as fallback for "
                            f"{m.get('home_name')} vs {m.get('away_name')} "
                            f"(totalGoalCount={_total}, ht={_ht_h}-{_ht_a})"
                        )

            # ALWAYS fetch individual match details for live matches.
            # The todays-matches endpoint returns homeGoalCount=0, awayGoalCount=0,
            # homeGoals="[]" for ALL incomplete/live matches — it NEVER updates
            # during the match. Only the individual /match endpoint has live scores.
            if status == "live":
                _raw_id = m.get("id")
                _detail_ok = False
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
                            if _fb_home is not None and _fb_away is not None:
                                home_goals = _fb_home
                                away_goals = _fb_away
                                _has_goal_data = True
                                _detail_ok = True
                                _fb_ht_h = _valid_goal(dd.get("ht_goals_team_a")) or _valid_goal(dd.get("home_team_goal_count_half_time"))
                                _fb_ht_a = _valid_goal(dd.get("ht_goals_team_b")) or _valid_goal(dd.get("away_team_goal_count_half_time"))
                                logger.info(
                                    f"[live-scores] match-detail OK for "
                                    f"{m.get('home_name')} vs {m.get('away_name')} "
                                    f"(id={_raw_id}, score={_fb_home}-{_fb_away})"
                                )
                    except Exception as _fb_err:
                        logger.warning(f"[live-scores] match-detail failed for id={_raw_id}: {_fb_err}")

                if not _detail_ok:
                    # Match detail endpoint failed — emit with score=null
                    # so frontend keeps any valid score it already has.
                    logger.warning(
                        f"[live-scores] No live score for "
                        f"{m.get('home_name')} vs {m.get('away_name')} "
                        f"(id={_raw_id}, raw_status={raw_status!r})"
                    )
                    home_name = team_name(m.get("home_name") or m.get("homeTeam") or "").strip()
                    away_name = team_name(m.get("away_name") or m.get("awayTeam") or "").strip()
                    _ng_period = None
                    _ng_minute = None
                    if elapsed_min is not None and elapsed_min >= 0:
                        if elapsed_min <= 47:
                            _ng_period = "1T"
                            _ng_minute = min(elapsed_min, 45)
                        elif elapsed_min <= 62:
                            _ng_period = "HT"
                            _ng_minute = None
                        else:
                            _ng_period = "2T"
                            _ng_minute = min(elapsed_min - 15, 90)
                    result.append({
                        "id": int(_raw_id) if _raw_id is not None else None,
                        "homeTeam": home_name,
                        "awayTeam": away_name,
                        "status": status,
                        "score": None,
                        "period": _ng_period,
                        "minute": _ng_minute,
                        "dateUnix": m.get("date_unix"),
                    })
                    continue
            elif status != "finished":
                continue

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
            result.append({
                "id": int(_raw_id) if _raw_id is not None else None,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "status": status,
                "score": score,
                "period": period,
                "minute": minute,
                "dateUnix": m.get("date_unix"),
            })
        if skipped_statuses:
            logger.info(f"[live-scores] Skipped statuses: {skipped_statuses}")

        # ── API-Football enrichment for live matches ──────────────────────
        # FootyStats often returns 0-0 for live matches even via the
        # individual /match endpoint.  API-Football provides reliable
        # real-time scores, so we overlay them on top.
        _af_enriched = 0
        if _afc.is_configured:
            try:
                af_live = _afc.get_live_fixtures()  # 1-min cache
                if af_live:
                    # Build lookup: normalised home team name → fixture
                    _af_lookup: Dict[str, Dict] = {}
                    for fx in af_live:
                        _h = (fx.get("teams", {}).get("home", {}).get("name") or "").lower().strip()
                        if _h:
                            _af_lookup[_h] = fx

                    for rec in result:
                        if rec["status"] != "live":
                            continue
                        rh = rec["homeTeam"].lower().strip()
                        ra = rec["awayTeam"].lower().strip()

                        # Try exact, then substring match
                        matched_fx = _af_lookup.get(rh)
                        if not matched_fx:
                            for af_h, fx in _af_lookup.items():
                                if (rh in af_h or af_h in rh):
                                    af_a = (fx.get("teams", {}).get("away", {}).get("name") or "").lower().strip()
                                    if ra in af_a or af_a in ra:
                                        matched_fx = fx
                                        break

                        if not matched_fx:
                            continue

                        ld = _afc.extract_live_data(matched_fx)
                        if ld["goals_home"] is None:
                            continue

                        # Overlay score from API-Football
                        af_home_g = ld["goals_home"]
                        af_away_g = ld["goals_away"]

                        # Guard: never overwrite a higher FootyStats score with
                        # a lower API-Football score (API-Football may lag on
                        # rare occasions).
                        cur_score = rec.get("score")
                        cur_total = 0
                        if cur_score and isinstance(cur_score, dict):
                            cur_total = (cur_score.get("home") or 0) + (cur_score.get("away") or 0)
                        af_total = af_home_g + (af_away_g or 0)

                        if af_total >= cur_total:
                            new_score: Dict[str, Any] = {"home": af_home_g, "away": af_away_g}
                            if ld["halftime_home"] is not None:
                                new_score["halftime"] = {"home": ld["halftime_home"], "away": ld["halftime_away"]}
                            elif cur_score and isinstance(cur_score, dict) and cur_score.get("halftime"):
                                new_score["halftime"] = cur_score["halftime"]
                            rec["score"] = new_score

                        # Always update minute/period from API-Football (more accurate)
                        if ld["minute"] is not None:
                            rec["minute"] = ld["minute"]
                        af_status = ld["status"]
                        period_map = {"1H": "1T", "HT": "HT", "2H": "2T"}
                        if af_status in period_map:
                            rec["period"] = period_map[af_status]

                        _af_enriched += 1

                if _af_enriched:
                    logger.info(f"[live-scores] API-Football enriched {_af_enriched} live matches")
            except Exception as _af_err:
                logger.warning(f"[live-scores] API-Football enrichment failed: {_af_err}")

        logger.info(
            f"[live-scores] Returned {len(result)} matches (from {len(raw_list)} raw) "
            f"| scores: {[(r['homeTeam'][:12], r['score']['home'] if r.get('score') else '?', r['score']['away'] if r.get('score') else '?') for r in result[:5]]}"
        )
        return {"matches": result, "nextUpdate": 60}
    except Exception as e:
        logger.error(f"[live-scores] Error: {e}")
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
        table = raw.get("league_table", []) if isinstance(raw, dict) else raw
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
