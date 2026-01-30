from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
import os
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None
from backend.services.fixtures_service import build_records_from_matches

router = APIRouter(tags=["fixtures"])

@router.get("/fixtures")
def fixtures(leagues: str = Query(""), date: str = Query("today")) -> Dict[str, Any]:
    from backend.main import resolve_league_dir, get_data_dir, generate_mock_fixtures
    league_ids = [s for s in leagues.split(",") if s]
    out: List[Dict[str, Any]] = []
    base = get_data_dir()
    for lid in league_ids:
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
            out.extend(build_records_from_matches(
                league_id=lid,
                matches=matches_df,
                teams=teams_df,
                teams2=teams2_df,
                league_df=league_df,
                players=players_df,
                date_filter=date,
            ))
        except Exception:
            out.extend(generate_mock_fixtures(lid, date))
    return {"matches": out}
