# backend/routes/ai_analysis.py
"""
Router para endpoints de analise AI com MISTRAL — v3.0
Conectado ao pipeline real de dados (fixtures_service + API-Football).
"""
import asyncio
import logging
from datetime import datetime as _dt
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, List, Any

from backend.services.mistral_analysis import (
    MistralAnalysisService,
    AIAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis v3.0"]
)


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    include_context: bool = Query(
        True, description="Incluir contexto adicional (forma, H2H, lesoes titulares)"
    ),
):
    """
    Analise completa v3.0 — 24 mercados.

    Retorna: 1X2, Double Chance, Over/Under 0.5-4.5, BTTS,
    Escanteios Over/Under 8.5-11.5, lesoes de titulares, alertas.
    """
    try:
        match_data = await _get_match_data(match_id)
        service = MistralAnalysisService()

        analysis = await service.analyze_match(
            home_team=match_data['home_team'],
            away_team=match_data['away_team'],
            league=match_data['league'],
            match_stats=match_data['stats'],
            odds=match_data['odds'],
            context=match_data.get('context') if include_context else None,
        )
        return analysis

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Dados invalidos: {e}")
    except Exception as e:
        logger.error(f"[ai_analysis] Erro analise match {match_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro analise: {e}")


@router.get("/match/{match_id}/analysis/legacy")
async def get_match_analysis_legacy(match_id: str):
    """Formato legado para MatchDetailCard.tsx (summary, keyPoints, etc)."""
    analysis = await get_match_analysis(match_id, include_context=True)
    return MistralAnalysisService.to_legacy_format(analysis)


@router.post(
    "/match/{match_id}/analysis/regenerate",
    response_model=AIAnalysisResponse,
)
async def regenerate_match_analysis(match_id: str):
    """Forca regeneracao da analise (quando odds mudam)."""
    return await get_match_analysis(match_id, include_context=True)


@router.get("/batch-analysis")
async def get_batch_analysis(
    league: str = Query(..., description="ID da liga"),
    date: str = Query("today", description="today/tomorrow/YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50),
):
    """Analises v3.0 em batch para multiplos jogos."""
    try:
        matches = await _get_matches_by_league_and_date(league, date, limit)
        service = MistralAnalysisService()
        analyses = []

        for match in matches:
            try:
                analysis = await service.analyze_match(
                    home_team=match['home_team'],
                    away_team=match['away_team'],
                    league=match['league'],
                    match_stats=match['stats'],
                    odds=match['odds'],
                    context=match.get('context'),
                )
                analyses.append({
                    'match_id': match['id'],
                    'home_team': match['home_team'],
                    'away_team': match['away_team'],
                    'start_time': match['start_time'],
                    'analysis': analysis.model_dump(),
                })
            except Exception as e:
                print(f"[BatchV3] Erro jogo {match['id']}: {e}")
                continue

        return {
            'version': MistralAnalysisService.VERSION,
            'league': league,
            'date': date,
            'total_matches': len(matches),
            'analyzed': len(analyses),
            'analyses': analyses,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro batch: {e}")


# =====================================================================
# REAL DATA PIPELINE — replaces mock functions
# =====================================================================

def _extract_league_id(match_id: str) -> str:
    """Extract league_id from composite match_id by prefix-matching known leagues.

    Match IDs have format: "{league_id}-{home}-{away}-{timestamp}"
    League IDs are slugs like "premier-league", "brasileirao-serie-a".
    """
    from backend.config.leagues_config import LEAGUES_CONFIG
    known_ids = sorted(
        [lg["id"] for lg in LEAGUES_CONFIG],
        key=len, reverse=True,  # longest first to avoid partial matches
    )
    for lid in known_ids:
        if match_id.startswith(lid + "-"):
            return lid
    raise ValueError(
        f"Liga nao identificada no match_id: {match_id[:60]}..."
    )


def _extract_date_from_id(match_id: str) -> str:
    """Extract date (YYYY-MM-DD) from Unix timestamp at end of match_id."""
    # ID format: "league-id-Home Team-Away Team-1711202400.0"
    # The timestamp is a float after the last '-'
    last_segment = match_id.rsplit("-", 1)[-1]
    try:
        ts = float(last_segment)
        dt = _dt.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError):
        logger.warning(
            f"[ai_analysis] Could not parse date from match_id '{match_id[:60]}', using 'today'"
        )
        return "today"


def _format_injuries_str(injuries_list: list) -> str:
    """Format API-Football injuries list into human-readable string for Mistral."""
    if not injuries_list:
        return "Sem desfalques entre titulares"
    parts = []
    for inj in injuries_list:
        if not isinstance(inj, dict):
            continue
        player = inj.get("player", {})
        name = player.get("name", "Desconhecido") if isinstance(player, dict) else str(player)
        reason = inj.get("reason", "lesao")
        parts.append(f"{name} [FORA] - {reason}")
    return "; ".join(parts) if parts else "Sem desfalques entre titulares"


def _format_h2h_str(h2h: Any) -> str:
    """Format h2h dict into human-readable string for Mistral."""
    if isinstance(h2h, str):
        return h2h
    if not isinstance(h2h, dict):
        return "Dado nao disponivel"
    total = h2h.get("totalMatches", 0)
    hw = h2h.get("homeWins", 0)
    dr = h2h.get("draws", 0)
    aw = h2h.get("awayWins", 0)
    avg = h2h.get("avgGoals", 0)
    if total == 0:
        return "Sem confrontos diretos recentes"
    return f"Ultimos {total}: Casa {hw}V, {dr}E, {aw}D. Media {avg:.1f} gols/jogo"


def _map_record_to_v3(record: Dict[str, Any]) -> Dict[str, Any]:
    """Map a pipeline record (fixtures_service) to v3.0 format expected by MistralAnalysisService.

    The Mistral prompt uses snake_case for some stats (lambda_home, prob_home)
    while the pipeline produces camelCase (lambdaHome, homeWinProb).
    This function adds the expected aliases so both naming conventions work.
    """
    stats = dict(record.get("stats", {}))  # shallow copy
    odds = dict(record.get("odds", {}))    # shallow copy

    # --- Stats: add snake_case aliases for fields the prompt expects ---
    stats["lambda_home"] = stats.get("lambdaHome", "N/A")
    stats["lambda_away"] = stats.get("lambdaAway", "N/A")
    stats["prob_home"] = stats.get("homeWinProb", "N/A")
    stats["prob_draw"] = stats.get("drawProb", "N/A")
    stats["prob_away"] = stats.get("awayWinProb", "N/A")
    stats["prob_over_05"] = stats.get("over05Prob", "N/A")
    stats["prob_over_15"] = stats.get("over15Prob", "N/A")
    stats["prob_over_25"] = stats.get("over25Prob", "N/A")
    stats["prob_over_35"] = stats.get("over35Prob", "N/A")
    stats["prob_over_45"] = stats.get("over45Prob", "N/A")
    stats["prob_btts"] = stats.get("bttsProb", "N/A")
    stats["homeXg"] = stats.get("homeXgForAvg", stats.get("homeXg", "N/A"))
    stats["awayXg"] = stats.get("awayXgForAvg", stats.get("awayXg", "N/A"))

    # --- Odds: add underscore aliases for fields the prompt expects ---
    odds["over_05"] = odds.get("over05", "N/A")
    odds["over_15"] = odds.get("over15", "N/A")
    odds["over_25"] = odds.get("over25", "N/A")
    odds["over_35"] = odds.get("over35", "N/A")
    odds["over_45"] = odds.get("over45", "N/A")
    odds["under_25"] = odds.get("under25", "N/A")
    odds["under_35"] = odds.get("under35", "N/A")
    odds["under_45"] = odds.get("under45", "N/A")
    odds["btts_yes"] = odds.get("bttsYes", "N/A")
    odds["btts_no"] = odds.get("bttsNo", "N/A")
    # DC odds not in pipeline — will show as N/A (acceptable)

    # --- Context: build from _mistral_context + stats ---
    ctx = record.get("_mistral_context", {}) or {}
    injuries = ctx.get("injuries", {}) or {}
    home_injuries = injuries.get("home", []) if isinstance(injuries, dict) else []
    away_injuries = injuries.get("away", []) if isinstance(injuries, dict) else []

    home_pos = stats.get("homeLeaguePosition")
    away_pos = stats.get("awayLeaguePosition")

    context = {
        "home_form": ctx.get("home_form") or record.get("homeForm", "N/A"),
        "away_form": ctx.get("away_form") or record.get("awayForm", "N/A"),
        "h2h": _format_h2h_str(ctx.get("h2h") or record.get("h2h")),
        "home_position": f"{home_pos}o lugar" if home_pos else "N/A",
        "away_position": f"{away_pos}o lugar" if away_pos else "N/A",
        "home_injuries_starters": _format_injuries_str(home_injuries),
        "away_injuries_starters": _format_injuries_str(away_injuries),
    }

    # --- Team names ---
    home_team_obj = record.get("homeTeam", {})
    away_team_obj = record.get("awayTeam", {})
    home_name = home_team_obj.get("name", "") if isinstance(home_team_obj, dict) else str(home_team_obj)
    away_name = away_team_obj.get("name", "") if isinstance(away_team_obj, dict) else str(away_team_obj)

    return {
        "id": record.get("id", ""),
        "home_team": home_name,
        "away_team": away_name,
        "league": record.get("leagueName", record.get("leagueId", "")),
        "start_time": record.get("datetime", ""),
        "stats": stats,
        "odds": odds,
        "context": context,
    }


async def _get_match_data(match_id: str) -> dict:
    """Fetch real match data from the fixtures pipeline by match_id."""
    from backend.routes.fixtures import _process_single_league
    from backend.main import get_data_dir

    league_id = _extract_league_id(match_id)
    date_str = _extract_date_from_id(match_id)
    base = get_data_dir()

    logger.info(f"[ai_analysis] Fetching {league_id} / {date_str} for match {match_id[:60]}")
    records = await asyncio.to_thread(_process_single_league, league_id, date_str, base)

    record = next((r for r in records if r["id"] == match_id), None)
    if not record:
        available = [r["id"] for r in records[:5]]
        raise ValueError(
            f"Jogo '{match_id}' nao encontrado na liga {league_id} ({date_str}). "
            f"Disponiveis: {available}"
        )

    return _map_record_to_v3(record)


async def _get_matches_by_league_and_date(league: str, date: str, limit: int) -> list:
    """Fetch real match data for a league/date from the fixtures pipeline."""
    from backend.routes.fixtures import _process_single_league
    from backend.main import get_data_dir

    base = get_data_dir()
    records = await asyncio.to_thread(_process_single_league, league, date, base)
    return [_map_record_to_v3(r) for r in records[:limit]]
