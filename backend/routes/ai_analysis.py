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
    home_team: str = Query(None, description="Nome do time da casa (para busca precisa)"),
    away_team: str = Query(None, description="Nome do time visitante (para busca precisa)"),
    include_context: bool = Query(True, description="Incluir contexto adicional (forma, H2H)"),
):
    """
    Retorna analise completa de um jogo usando MISTRAL AI.

    - **match_id**: ID do jogo
    - **home_team**: Nome do time da casa (opcional, para busca precisa)
    - **away_team**: Nome do time visitante (opcional, para busca precisa)
    - **include_context**: Se deve incluir contexto adicional na analise
    """
    try:
        match_data = _get_match_data(match_id, home_team=home_team, away_team=away_team)
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

def _extract_league_id(match_id: str) -> str:
    """Extract league ID from match_id format 'premier-league-mock-0'."""
    # Remove trailing '-mock-N' or '-m-N' suffix to get league id
    parts = match_id.rsplit("-mock-", 1)
    if len(parts) == 2:
        return parts[0]
    parts = match_id.rsplit("-m", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    # Fallback: try all known league prefixes
    from backend.config.leagues_config import LEAGUE_ID_ALIASES
    for alias in LEAGUE_ID_ALIASES:
        if match_id.startswith(alias):
            return alias
    return ""


def _match_to_ai_input(m: dict) -> dict:
    """Convert a fixtures match object to the dict expected by AI analysis."""
    stats = m.get("stats", {})
    home_form = stats.get("homeForm") or m.get("homeForm") or []
    away_form = stats.get("awayForm") or m.get("awayForm") or []
    h2h = m.get("h2h", {})
    return {
        "id": m.get("id"),
        "home_team": m.get("homeTeam", ""),
        "away_team": m.get("awayTeam", ""),
        "league": m.get("leagueName", ""),
        "stats": stats,
        "odds": m.get("odds", {}),
        "context": {
            "home_form": ", ".join(home_form) if isinstance(home_form, list) else str(home_form),
            "away_form": ", ".join(away_form) if isinstance(away_form, list) else str(away_form),
            "h2h": f"Total: {h2h.get('totalMatches', 0)} jogos, Casa: {h2h.get('homeWins', 0)}, Empates: {h2h.get('draws', 0)}, Fora: {h2h.get('awayWins', 0)}, Media gols: {h2h.get('avgGoals', 0)}",
        },
    }


def _get_match_data(match_id: str, home_team: str = None, away_team: str = None) -> dict:
    """Fetch match data from the fixtures system, falling back to mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        # Extract league from match_id so the fixtures endpoint returns data
        league_id = _extract_league_id(match_id)

        # Try today first, then week as fallback
        for date_filter in ("today", "week"):
            if not league_id:
                break
            result = fixtures_endpoint(leagues=league_id, date=date_filter)
            # 1. Try exact ID match
            for m in result.get("matches", []):
                if str(m.get("id")) == str(match_id):
                    logger.info(f"Found match {match_id} via fixtures (date={date_filter})")
                    return _match_to_ai_input(m)

            # 2. Try matching by team names (handles ID format mismatches)
            if home_team and away_team:
                for m in result.get("matches", []):
                    h = str(m.get("homeTeam", ""))
                    a = str(m.get("awayTeam", ""))
                    if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
                       (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
                        logger.info(f"Found match by team names: {h} vs {a} (date={date_filter})")
                        return _match_to_ai_input(m)

        # If no league could be extracted but we have team names, try all leagues
        if home_team and away_team and not league_id:
            from backend.config.leagues_config import LEAGUE_ID_ALIASES
            for alias in LEAGUE_ID_ALIASES:
                try:
                    result = fixtures_endpoint(leagues=alias, date="today")
                    for m in result.get("matches", []):
                        h = str(m.get("homeTeam", ""))
                        a = str(m.get("awayTeam", ""))
                        if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
                           (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
                            logger.info(f"Found match by team names in {alias}: {h} vs {a}")
                            return _match_to_ai_input(m)
                except Exception:
                    continue

    except Exception as e:
        logger.warning(f"Could not fetch live fixtures for match {match_id}: {e}")

    # Fallback — use generic data with descriptive names instead of hardcoded mock
    logger.warning(f"Using fallback mock data for match {match_id}")
    return {
        "id": match_id,
        "home_team": "Home Team",
        "away_team": "Away Team",
        "league": "Unknown League",
        "stats": {
            "homeWinProb": 40.0,
            "drawProb": 30.0,
            "awayWinProb": 30.0,
            "avgGoals": 2.5,
            "bttsProb": 52.0,
            "lambdaHome": 1.3,
            "lambdaAway": 1.2,
        },
        "odds": {
            "home": 2.10,
            "draw": 3.30,
            "away": 3.40,
            "over25": 1.85,
            "bttsYes": 1.80,
        },
        "context": {
            "home_form": "Dados indisponiveis",
            "away_form": "Dados indisponiveis",
            "h2h": "Dados indisponiveis",
        },
    }


def _get_matches_by_league_and_date(league: str, date: str, limit: int) -> list:
    """Fetch matches from fixtures, fallback to week then mock."""
    try:
        from backend.routes.fixtures import fixtures as fixtures_endpoint

        # Try requested date first, then week as fallback
        for date_filter in (date, "week"):
            if not league:
                break
            result = fixtures_endpoint(leagues=league, date=date_filter)
            matches = []
            for m in result.get("matches", [])[:limit]:
                data = _match_to_ai_input(m)
                data["start_time"] = m.get("datetime", "")
                matches.append(data)
            if matches:
                return matches
    except Exception as e:
        logger.warning(f"Could not fetch fixtures for batch: {e}")

    return [_get_match_data("fallback-0")][:limit]
