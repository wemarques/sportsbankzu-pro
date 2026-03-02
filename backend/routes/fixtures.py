from fastapi import APIRouter, Query
from typing import Dict, Any, List
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None
from backend.services.fixtures_service import build_records_from_matches
from backend.services.footstats_client import FootyStatsClient
from backend.services.data_mapper import DataMapper
from backend.config.leagues_config import get_league_config

logger = logging.getLogger("sportsbankzu.fixtures")
router = APIRouter(tags=["fixtures"])
footstats = FootyStatsClient()

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
                        logger.warning(f"[fixtures] {lid}: API OK but 0 records for date '{date}'")
                    found_via_api = True
                else:
                    logger.warning(f"[fixtures] {lid}: API success=False: {matches_data.get('message','')}")
            else:
                logger.warning(f"[fixtures] {lid}: could not resolve season_id for {league_config}")
        except Exception as e:
            logger.error(f"[fixtures] {lid}: {type(e).__name__}: {e}")

    # FALLBACK: CSV files
    if not found_via_api:
        from backend.main import resolve_league_dir, generate_mock_fixtures as gen_mock
        if pd is None or not os.path.isdir(base):
            return gen_mock(lid, date)

        league_dir = resolve_league_dir(base, lid)
        matches_path = os.path.join(league_dir, "matches.csv")
        teams_path = os.path.join(league_dir, "teams.csv")
        teams2_path = os.path.join(league_dir, "teams2.csv")
        league_path = os.path.join(league_dir, "league.csv")
        players_path = os.path.join(league_dir, "players.csv")

        if not os.path.exists(matches_path):
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
            from backend.main import generate_mock_fixtures as gen_mock2
            records = gen_mock2(lid, date)

    return records


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
        for m in raw_list:
            status = status_map(str(m.get("status", "")))
            if status not in ("live", "finished"):
                continue

            # Read goal count — try multiple field names (API returns camelCase
            # or snake_case depending on endpoint/version)
            home_goals = m.get("homeGoalCount")
            if home_goals is None:
                home_goals = m.get("home_team_goal_count")
            if home_goals is None:
                home_goals = m.get("home_goals")

            away_goals = m.get("awayGoalCount")
            if away_goals is None:
                away_goals = m.get("away_team_goal_count")
            if away_goals is None:
                away_goals = m.get("away_goals")

            # For live matches: never skip — default to 0 if goal fields are missing.
            # The match IS in progress so it should appear in the overlay.
            # For finished matches: skip if no goal data (incomplete record).
            if home_goals is None or away_goals is None:
                if status == "live":
                    home_goals = home_goals if home_goals is not None else 0
                    away_goals = away_goals if away_goals is not None else 0
                else:
                    continue

            try:
                home_goals = int(home_goals)
                away_goals = int(away_goals)
            except (ValueError, TypeError):
                home_goals, away_goals = 0, 0

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
            home_name = (m.get("home_name") or m.get("homeTeam") or "").strip()
            away_name = (m.get("away_name") or m.get("awayTeam") or "").strip()

            result.append({
                "id": m.get("id"),
                "homeTeam": home_name,
                "awayTeam": away_name,
                "status": status,
                "score": score,
                "period": period,
                "minute": minute,
            })
        logger.info(f"[live-scores] Returned {len(result)} matches (from {len(raw_list)} raw)")
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
