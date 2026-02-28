from fastapi import APIRouter, Query
from typing import Dict, Any, List
import os
import logging
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

@router.get("/fixtures")
def fixtures(leagues: str = Query(""), date: str = Query("today")) -> Dict[str, Any]:
    from backend.main import resolve_league_dir, get_data_dir, generate_mock_fixtures
    league_ids = [lid.strip() for lid in leagues.split(",") if lid.strip()]
    out: List[Dict[str, Any]] = []
    base = get_data_dir()

    # Se nenhuma liga for selecionada, não retorna nada para evitar sobrecarga
    if not league_ids:
        return {"matches": []}

    for lid in league_ids:
        # 1. TENTA API FOOTYSTATS PRIMEIRO
        league_config = get_league_config(lid)
        found_via_api = False

        if league_config:
            try:
                # Resolve season_id dinamicamente (with alt_names for leagues like Portugal)
                season_id = footstats.resolve_season_id(
                    league_config["country"], league_config["name"],
                    alt_names=league_config.get("alt_names"),
                )
                if season_id:
                    matches_data = footstats.get_league_matches(season_id)

                    if matches_data.get("success"):
                        # Converte para DataFrame usando o Mapper
                        raw_list = matches_data.get("data", [])
                        if not raw_list:
                            logger.warning(f"[fixtures] {lid}: API success but empty data list")
                            found_via_api = True
                            continue
                        try:
                            matches_df = DataMapper.matches_to_df(raw_list)
                        except Exception as e:
                            logger.error(f"[fixtures] {lid}: matches_to_df crashed: {e}")
                            continue

                        if matches_df.empty:
                            logger.warning(f"[fixtures] {lid}: matches_to_df returned empty DataFrame")
                            found_via_api = True
                            continue

                        # Busca estatísticas da temporada para os Lambdas
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

                        # Busca dados de times com stats (cards, fouls, shots, etc.)
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

                        # Fallback: se teams_df falhou, tenta league-tables para posição e win%
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

                        # Constrói league_df a partir de season stats para enriquecer cálculos
                        # Baseado no League CSV - 49 Data Columns
                        league_df = None
                        if league_season_data:
                            try:
                                league_df = pd.DataFrame([{
                                    "league_name": league_config.get("name", lid),
                                    # Core goals
                                    "average_goals_per_match": league_season_data.get("seasonAVG_overall", 2.5),
                                    "average_scored_home_team": league_season_data.get("seasonHomeAVG_overall",
                                        league_season_data.get("averageScoredHomeTeam", None)),
                                    "average_scored_away_team": league_season_data.get("seasonAwayAVG_overall",
                                        league_season_data.get("averageScoredAwayTeam", None)),
                                    # Corners
                                    "average_corners_per_match": league_season_data.get("cornersAVG_overall", 10.0),
                                    "average_corners_per_match_home_team": league_season_data.get("cornersAVG_home",
                                        league_season_data.get("averageCornersPerMatchHomeTeam", None)),
                                    # Cards
                                    "average_cards_per_match": league_season_data.get("cardsAVG_overall", 4.0),
                                    "average_cards_per_match_home_team": league_season_data.get("cardsAVG_home",
                                        league_season_data.get("averageCardsPerMatchHomeTeam", None)),
                                    "average_cards_per_match_away_team": league_season_data.get("cardsAVG_away",
                                        league_season_data.get("averageCardsPerMatchAwayTeam", None)),
                                    # Fouls & Shots
                                    "average_fouls_per_match": league_season_data.get("foulsAVG_overall", 22.0),
                                    "average_shots_per_match": league_season_data.get("shotsAVG_overall", 24.0),
                                    # Home advantage
                                    "home_advantage_percentage": league_season_data.get("homeAdvantagePercentage",
                                        league_season_data.get("home_advantage_percentage", None)),
                                    "home_scored_advantage_percentage": league_season_data.get("homeScoredAdvantagePercentage", None),
                                    "home_defence_advantage_percentage": league_season_data.get("homeDefenceAdvantagePercentage", None),
                                    # Clean sheets
                                    "clean_sheets_percentage": league_season_data.get("cleanSheetsPercentage",
                                        league_season_data.get("clean_sheets_percentage", None)),
                                    # Over/Under percentages (league-level benchmarks)
                                    "over_05_percentage": league_season_data.get("over05Percentage", None),
                                    "over_15_percentage": league_season_data.get("over15Percentage", None),
                                    "over_25_percentage": league_season_data.get("over25Percentage", None),
                                    "over_35_percentage": league_season_data.get("over35Percentage", None),
                                    "over_45_percentage": league_season_data.get("over45Percentage", None),
                                    "under_25_percentage": league_season_data.get("under25Percentage", None),
                                    # xG
                                    "xg_avg": league_season_data.get("xgAVG",
                                        league_season_data.get("xg_avg", None)),
                                    # Prediction risk
                                    "prediction_risk": league_season_data.get("predictionRisk",
                                        league_season_data.get("prediction_risk", None)),
                                    # Progress
                                    "matches_completed": league_season_data.get("matchesCompleted",
                                        league_season_data.get("matches_completed", None)),
                                    "total_matches": league_season_data.get("totalMatches",
                                        league_season_data.get("total_matches", None)),
                                }])
                            except Exception as e:
                                logger.warning(f"[fixtures] {lid}: failed to build league_df: {e}")

                        # Constrói registros usando o serviço existente
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
                            # Adiciona tag de origem
                            for r in records:
                                r["dataSource"] = "FootyStats API (Tempo Real)"
                            out.extend(records)
                        else:
                            logger.warning(f"[fixtures] {lid}: API OK but 0 records for date '{date}'")
                        # Mark API as found — even 0 records means API worked (no matches today)
                        found_via_api = True
                    else:
                        logger.warning(f"[fixtures] {lid}: API success=False: {matches_data.get('message','')}")
                else:
                    logger.warning(f"[fixtures] {lid}: could not resolve season_id for {league_config}")
            except Exception as e:
                logger.error(f"[fixtures] {lid}: {type(e).__name__}: {e}")

        # 2. FALLBACK: ARQUIVOS CSV LOCAIS (Se não encontrou via API ou se lid não está na config)
        if not found_via_api:
            if pd is None or not os.path.isdir(base):
                out.extend(generate_mock_fixtures(lid, date))
                continue

            league_dir = resolve_league_dir(base, lid)
            matches_path = os.path.join(league_dir, "matches.csv")
            teams_path = os.path.join(league_dir, "teams.csv")
            teams2_path = os.path.join(league_dir, "teams2.csv")
            league_path = os.path.join(league_dir, "league.csv")
            players_path = os.path.join(league_dir, "players.csv")

            if not os.path.exists(matches_path):
                out.extend(generate_mock_fixtures(lid, date))
                continue

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
                    out.extend(records)
            except Exception as e:
                logger.error(f"Erro ao ler CSV para {lid}: {e}")
                out.extend(generate_mock_fixtures(lid, date))

    return {"matches": out}


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
