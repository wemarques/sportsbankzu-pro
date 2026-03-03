"""
FastAPI route for the Safe Bets Engine.

Endpoints:
  POST /safe-bets/evaluate       — Evaluate safe bets for a list of matches
  GET  /safe-bets/league-dna     — Get League DNA profiles for all or specific leagues
  GET  /safe-bets/leagues        — List all 33 monitored leagues
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Query

from backend.config.league_dna import (
    LEAGUE_DNA_MATRIX,
    get_league_dna,
    get_enabled_markets,
)
from backend.config.leagues_config import LEAGUES_CONFIG
from backend.models.safe_bets import (
    SafeBetsMatchInput,
    SafeBetsResult,
    SafeBetsResponse,
    LeagueSeasonStats,
    TeamSafeBetsStats,
)
from backend.services.safe_bets_service import evaluate_safe_bets, evaluate_batch

logger = logging.getLogger("sportsbankzu.routes.safe_bets")

router = APIRouter(prefix="/safe-bets", tags=["Safe Bets"])


@router.post("/evaluate", response_model=SafeBetsResponse)
async def evaluate_safe_bets_endpoint(matches: List[SafeBetsMatchInput]):
    """Evaluate safe bets for a batch of matches.

    Accepts an array of match inputs with league/team stats pre-attached.
    Returns tags (UNDER_35, BTTS_NO, SAFE_CORNERS, TIMING_2H) or NO_BET.
    """
    results = evaluate_batch(matches)

    safe_count = sum(1 for r in results if r.risk_level.value == "SAFE")
    blocked_count = sum(1 for r in results if r.blocked)

    return SafeBetsResponse(
        success=True,
        total_matches=len(results),
        safe_count=safe_count,
        blocked_count=blocked_count,
        results=results,
    )


@router.get("/league-dna")
async def get_league_dna_endpoint(
    league_id: Optional[str] = Query(None, description="Filter by specific league ID"),
):
    """Get League DNA profiles.

    Returns the static categorization (DEFENSIVE/BALANCED/OFFENSIVE) and
    enabled markets for each league.
    """
    if league_id:
        dna = get_league_dna(league_id)
        if not dna:
            return {"success": False, "error": f"League '{league_id}' not found in DNA matrix"}
        return {
            "success": True,
            "league_id": dna.league_id,
            "category": dna.category,
            "is_aggressive": dna.is_aggressive,
            "markets_enabled": dna.markets_enabled,
            "avg_goals": dna.avg_goals,
            "avg_corners": dna.avg_corners,
            "avg_cards": dna.avg_cards,
            "btts_pct": dna.btts_pct,
        }

    # Return all leagues
    profiles = []
    for lid, dna in LEAGUE_DNA_MATRIX.items():
        profiles.append({
            "league_id": dna.league_id,
            "category": dna.category,
            "is_aggressive": dna.is_aggressive,
            "markets_enabled": dna.markets_enabled,
            "avg_goals": dna.avg_goals,
            "avg_corners": dna.avg_corners,
            "avg_cards": dna.avg_cards,
            "btts_pct": dna.btts_pct,
        })
    return {"success": True, "total": len(profiles), "profiles": profiles}


@router.get("/leagues")
async def list_all_leagues():
    """List all 33 monitored leagues with their configuration."""
    leagues = []
    for league in LEAGUES_CONFIG:
        dna = get_league_dna(league["id"])
        entry = {
            "id": league["id"],
            "country": league["country"],
            "name": league["name"],
            "alt_names": league.get("alt_names", []),
        }
        if dna:
            entry["dna"] = {
                "category": dna.category,
                "is_aggressive": dna.is_aggressive,
                "markets_enabled": dna.markets_enabled,
            }
        leagues.append(entry)
    return {"success": True, "total": len(leagues), "leagues": leagues}
