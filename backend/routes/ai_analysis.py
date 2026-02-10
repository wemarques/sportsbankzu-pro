from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import logging

from backend.services.mistral_analysis import MistralAnalysisService, AIAnalysisResponse

logger = logging.getLogger("sportsbank.routes.ai_analysis")
router = APIRouter(prefix="/api/ai", tags=["ai-analysis"])

analysis_service = MistralAnalysisService()


def _get_match_data(match_id: str) -> Dict[str, Any]:
    """Fetch match data from the fixtures system.

    Tries the live fixtures endpoint first, then falls back to mock data
    so the AI analysis endpoints always return something useful.
    """
    try:
        from backend.main import generate_mock_fixtures
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        result = fixtures_endpoint(leagues="", date="today")
        matches = result.get("matches", [])
        for m in matches:
            if str(m.get("id")) == str(match_id):
                return m
    except Exception as e:
        logger.warning(f"Could not fetch live fixtures for match {match_id}: {e}")

    # Fallback: return mock data for the given match_id
    return {
        "id": match_id,
        "homeTeam": "Deportivo Tachira",
        "awayTeam": "The Strongest",
        "leagueName": "Copa Libertadores",
        "stats": {
            "lambdaHome": 1.45,
            "lambdaAway": 1.22,
            "homeWinProb": 38.5,
            "drawProb": 28.3,
            "awayWinProb": 33.2,
            "over25Prob": 65.8,
            "bttsProb": 58.4,
        },
        "odds": {
            "home": 1.66,
            "draw": 3.60,
            "away": 4.75,
            "over25": 2.07,
            "bttsYes": 2.00,
        },
        "h2h": {
            "totalMatches": 4,
            "homeWins": 2,
            "draws": 1,
            "awayWins": 1,
            "avgGoals": 2.5,
        },
    }


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
def get_match_analysis(match_id: str):
    """Return AI analysis for a single match. Uses cache when available."""
    try:
        match_data = _get_match_data(match_id)
        result = analysis_service.analyze_match(match_data)
        return result
    except Exception as e:
        logger.error(f"Error generating analysis for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match/{match_id}/analysis/regenerate", response_model=AIAnalysisResponse)
def regenerate_match_analysis(match_id: str):
    """Force-regenerate the AI analysis for a match (bypasses cache)."""
    try:
        match_data = _get_match_data(match_id)
        home = match_data.get("homeTeam") or match_data.get("home_team", "Home")
        away = match_data.get("awayTeam") or match_data.get("away_team", "Away")

        # Invalidate cache by overwriting with None-like entry, then regenerate
        analysis_service.cache.set("analysis", home, away, {})
        result = analysis_service.analyze_match(match_data)
        return result
    except Exception as e:
        logger.error(f"Error regenerating analysis for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-analysis")
def batch_analysis(
    league: str = Query("", description="League ID to filter matches"),
    date: str = Query("today", description="Date filter (today, tomorrow, or YYYY-MM-DD)"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of analyses to return"),
):
    """Return AI analyses for multiple matches in a league."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        result = fixtures_endpoint(leagues=league, date=date)
        matches = result.get("matches", [])[:limit]

        analyses = []
        for match in matches:
            mid = match.get("id", "unknown")
            try:
                analysis = analysis_service.analyze_match(match)
                analyses.append(
                    {
                        "match_id": mid,
                        "home_team": match.get("homeTeam", ""),
                        "away_team": match.get("awayTeam", ""),
                        "analysis": analysis.model_dump(),
                    }
                )
            except Exception as e:
                logger.error(f"Batch analysis failed for match {mid}: {e}")
                analyses.append(
                    {
                        "match_id": mid,
                        "home_team": match.get("homeTeam", ""),
                        "away_team": match.get("awayTeam", ""),
                        "analysis": None,
                        "error": str(e),
                    }
                )

        return {"total": len(analyses), "analyses": analyses}
    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
