# backend/routes/ai_analysis.py
"""
Router para endpoints de analise AI com MISTRAL
"""
from fastapi import APIRouter, HTTPException, Query
import logging

from backend.services.mistral_analysis import MistralAnalysisService, AIAnalysisResponse

logger = logging.getLogger("sportsbank.routes.ai_analysis")

router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis"],
)


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    include_context: bool = Query(True, description="Incluir contexto adicional (forma, H2H)"),
):
    """
    Retorna analise completa de um jogo usando MISTRAL AI.

    - **match_id**: ID do jogo
    - **include_context**: Se deve incluir contexto adicional na analise
    """
    try:
        match_data = _get_match_data(match_id)
        service = MistralAnalysisService()

        analysis = await service.analyze_match(
            home_team=match_data["home_team"],
            away_team=match_data["away_team"],
            league=match_data["league"],
            match_stats=match_data["stats"],
            odds=match_data["odds"],
            context=match_data.get("context") if include_context else None,
        )

        return analysis
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Dados invalidos: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating analysis for match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar analise: {str(e)}")


@router.post("/match/{match_id}/analysis/regenerate", response_model=AIAnalysisResponse)
async def regenerate_match_analysis(match_id: str):
    """Forca regeneracao da analise AI para um jogo."""
    return await get_match_analysis(match_id, include_context=True)


@router.get("/batch-analysis")
async def get_batch_analysis(
    league: str = Query("", description="ID da liga"),
    date: str = Query("today", description="Data dos jogos (today/tomorrow/YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=50, description="Numero maximo de jogos"),
):
    """Retorna analises AI para multiplos jogos de uma liga."""
    try:
        matches = _get_matches_by_league_and_date(league, date, limit)
        service = MistralAnalysisService()
        analyses = []

        for match in matches:
            try:
                analysis = await service.analyze_match(
                    home_team=match["home_team"],
                    away_team=match["away_team"],
                    league=match["league"],
                    match_stats=match["stats"],
                    odds=match["odds"],
                    context=match.get("context"),
                )
                analyses.append(
                    {
                        "match_id": match["id"],
                        "home_team": match["home_team"],
                        "away_team": match["away_team"],
                        "start_time": match.get("start_time", ""),
                        "analysis": analysis.model_dump(),
                    }
                )
            except Exception as e:
                logger.error(f"Batch analysis failed for match {match['id']}: {e}")
                continue

        return {
            "league": league,
            "date": date,
            "total_matches": len(matches),
            "analyzed": len(analyses),
            "analyses": analyses,
        }
    except Exception as e:
        logger.error(f"Batch analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar analises em batch: {str(e)}")


# ===== HELPER FUNCTIONS =====

def _get_match_data(match_id: str) -> dict:
    """Fetch match data from the fixtures system, falling back to mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        result = fixtures_endpoint(leagues="", date="today")
        for m in result.get("matches", []):
            if str(m.get("id")) == str(match_id):
                return {
                    "id": m.get("id"),
                    "home_team": m.get("homeTeam", ""),
                    "away_team": m.get("awayTeam", ""),
                    "league": m.get("leagueName", ""),
                    "stats": m.get("stats", {}),
                    "odds": m.get("odds", {}),
                    "context": {
                        "home_form": ", ".join(m.get("homeForm", [])),
                        "away_form": ", ".join(m.get("awayForm", [])),
                        "h2h": f"Total: {m.get('h2h', {}).get('totalMatches', 0)} jogos",
                    },
                }
    except Exception as e:
        logger.warning(f"Could not fetch live fixtures for match {match_id}: {e}")

    # Mock data fallback
    return {
        "id": match_id,
        "home_team": "Deportivo Tachira",
        "away_team": "The Strongest",
        "league": "Copa Libertadores",
        "start_time": "2026-02-10T21:30:00",
        "stats": {
            "lambda_home": 1.45,
            "lambda_away": 1.22,
            "prob_home": 38.5,
            "prob_draw": 28.3,
            "prob_away": 33.2,
            "prob_over_25": 65.8,
            "prob_btts": 58.4,
        },
        "odds": {
            "home": 1.66,
            "draw": 3.60,
            "away": 4.75,
            "over_25": 2.07,
            "btts_yes": 2.00,
            "btts_no": 1.72,
        },
        "context": {
            "home_form": "V-V-E-V-D (70% aproveitamento)",
            "away_form": "V-D-V-V-E (60% aproveitamento)",
            "h2h": "Ultimos 5 confrontos: Casa venceu 3, Empate 1, Fora venceu 1",
            "absences": "Time visitante sem desfalques importantes",
        },
    }


def _get_matches_by_league_and_date(league: str, date: str, limit: int) -> list:
    """Fetch matches from fixtures, fallback to mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        result = fixtures_endpoint(leagues=league, date=date)
        matches = []
        for m in result.get("matches", [])[:limit]:
            matches.append(
                {
                    "id": m.get("id"),
                    "home_team": m.get("homeTeam", ""),
                    "away_team": m.get("awayTeam", ""),
                    "league": m.get("leagueName", ""),
                    "start_time": m.get("datetime", ""),
                    "stats": m.get("stats", {}),
                    "odds": m.get("odds", {}),
                    "context": {
                        "home_form": ", ".join(m.get("homeForm", [])),
                        "away_form": ", ".join(m.get("awayForm", [])),
                    },
                }
            )
        if matches:
            return matches
    except Exception as e:
        logger.warning(f"Could not fetch fixtures for batch: {e}")

    return [_get_match_data("1")][:limit]
