from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
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
                # Resolve season_id dinamicamente
                season_id = footstats.resolve_season_id(league_config["country"], league_config["name"])
                if season_id:
                    matches_data = footstats.get_league_matches(season_id)

                    if matches_data.get("success"):
                        # Converte para DataFrame usando o Mapper
                        matches_df = DataMapper.matches_to_df(matches_data.get("data", []))

                        # Busca estatísticas da temporada para os Lambdas
                        season_stats = footstats.get_league_season_stats(season_id)
                        teams_df = None
                        league_season_data = None
                        if season_stats.get("success"):
                            season_data = season_stats.get("data", {})
                            if isinstance(season_data, dict):
                                league_season_data = season_data

                        # Constrói league_df a partir de season stats para enriquecer cálculos
                        league_df = None
                        if league_season_data:
                            league_df = pd.DataFrame([{
                                "league_name": league_config.get("name", lid),
                                "average_goals_per_match": league_season_data.get("seasonAVG_overall", 2.5),
                                "average_corners_per_match": league_season_data.get("cornersAVG_overall", 10.0),
                                "average_cards_per_match": league_season_data.get("cardsAVG_overall", 4.0),
                            }])

                        # Constrói registros usando o serviço existente
                        records = build_records_from_matches(
                            league_id=lid,
                            matches=matches_df,
                            teams=teams_df,
                            teams2=None,
                            league_df=league_df,
                            players=None,
                            date_filter=date,
                        )

                        if records:
                            # Adiciona tag de origem
                            for r in records:
                                r["dataSource"] = "FootyStats API (Tempo Real)"
                            out.extend(records)
                        else:
                            logger.warning(f"[fixtures] {lid}: API OK but 0 records for date '{date}'")
                        # Mark API as found even with 0 records to avoid mock fallback
                        found_via_api = True
                    else:
                        logger.warning(f"[fixtures] {lid}: API success=False: {matches_data.get('message','')}")
                else:
                    logger.warning(f"[fixtures] {lid}: could not resolve season_id for {league_config}")
            except Exception as e:
                logger.error(f"[fixtures] {lid}: {type(e).__name__}: {e}")
            # League is configured for FootyStats — never fall back to mock
            found_via_api = True

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
        season_id = footstats.resolve_season_id(league_config["country"], league_config["name"])
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
