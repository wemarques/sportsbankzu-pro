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

logger = logging.getLogger("sportsbank.fixtures")
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
                    logger.info(f"Buscando dados da API para {lid} (Season: {season_id})")
                    matches_data = footstats.get_league_matches(season_id)
                    
                    if matches_data.get("success"):
                        # Converte para DataFrame usando o Mapper
                        matches_df = DataMapper.matches_to_df(matches_data.get("data", []))
                        
                        # Busca estatísticas da temporada para os Lambdas
                        season_stats = footstats.get_league_season_stats(season_id)
                        teams_df = None
                        if season_stats.get("success"):
                            # A API retorna clubes dentro de league-season
                            teams_df = DataMapper.teams_to_df(season_stats.get("data", [{}])[0].get("clubs", []))
                        
                        # Constrói registros usando o serviço existente
                        records = build_records_from_matches(
                            league_id=lid,
                            matches=matches_df,
                            teams=teams_df,
                            date_filter=date,
                        )
                        
                        if records:
                            # Adiciona tag de origem
                            for r in records:
                                r["dataSource"] = "FootyStats API (Tempo Real)"
                            out.extend(records)
                            found_via_api = True
            except Exception as e:
                logger.error(f"Falha ao integrar FootyStats para {lid}: {e}")

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
                # Tenta mock apenas se for premier-league (comportamento original)
                # ou se você quiser mock para todas as falhas:
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
