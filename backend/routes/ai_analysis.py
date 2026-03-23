# backend/routers/ai_analysis.py
"""
Router para endpoints de análise AI com MISTRAL — v3.0
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.services.mistral_analysis import (
    MistralAnalysisService,
    AIAnalysisResponse,
)


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Analysis v3.0"]
)


@router.get("/match/{match_id}/analysis", response_model=AIAnalysisResponse)
async def get_match_analysis(
    match_id: str,
    include_context: bool = Query(
        True, description="Incluir contexto adicional (forma, H2H, lesões titulares)"
    ),
):
    """
    Análise completa v3.0 — 24 mercados.

    Retorna: 1X2, Double Chance, Over/Under 0.5-4.5, BTTS,
    Escanteios Over/Under 8.5-11.5, lesões de titulares, alertas.
    """
    try:
        match_data = _get_match_data(match_id)
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
        raise HTTPException(status_code=400, detail=f"Dados inválidos: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro análise: {e}")


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
    """Força regeneração da análise (quando odds mudam)."""
    return await get_match_analysis(match_id, include_context=True)


@router.get("/batch-analysis")
async def get_batch_analysis(
    league: str = Query(..., description="ID da liga"),
    date: str = Query("today", description="today/tomorrow/YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50),
):
    """Análises v3.0 em batch para múltiplos jogos."""
    try:
        matches = _get_matches_by_league_and_date(league, date, limit)
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


# ===== MOCK — substituir por dados reais =====

def _get_match_data(match_id: str) -> dict:
    """Mock v3.0 com todos os campos"""
    mock_data = {
        '1': {
            'id': '1',
            'home_team': 'Deportivo Táchira',
            'away_team': 'The Strongest',
            'league': 'Copa Libertadores',
            'start_time': '2026-02-10T21:30:00',
            'stats': {
                'lambda_home': 1.45,
                'lambda_away': 1.22,
                'prob_home': 38.5,
                'prob_draw': 28.3,
                'prob_away': 33.2,
                'prob_over_05': 93.2,
                'prob_over_15': 82.3,
                'prob_over_25': 65.8,
                'prob_over_35': 40.1,
                'prob_over_45': 18.7,
                'prob_btts': 58.4,
                'homeCornersPerMatch': 5.2,
                'awayCornersPerMatch': 4.8,
                'homeCornersAgainstPerMatch': 4.5,
                'awayCornersAgainstPerMatch': 5.1,
                'cornerOver85Prob': 72.0,
                'cornerOver95Prob': 55.0,
                'cornerOver105Prob': 38.0,
                'leagueAvgCorners': 10.2,
                'homeXg': 1.35,
                'awayXg': 1.10,
                'homeXgAgainstAvg': 0.95,
                'awayXgAgainstAvg': 1.22,
                'homeCleanSheetPct': 35.0,
                'awayCleanSheetPct': 20.0,
                'homeFtsPercentage': 15.0,
                'awayFtsPercentage': 25.0,
                'homeBttsPercentage': 55.0,
                'awayBttsPercentage': 60.0,
                'homeOver25Percentage': 60.0,
                'awayOver25Percentage': 65.0,
                'homeWinPercentage': 70.0,
                'awayWinPercentage': 40.0,
                'homeCardsPerMatch': 2.1,
                'awayCardsPerMatch': 2.5,
                'homeFoulsPerMatch': 14.2,
                'awayFoulsPerMatch': 15.8,
                'homeAvgTotalGoals': 2.8,
                'awayAvgTotalGoals': 2.5,
                'leagueAvgCards': 4.3,
                'leagueAvgFouls': 28.5,
                'leagueCleanSheetsPct': 25.0,
                'leagueOver25Pct': 58.0,
                'leagueHomeAdvantage': 48.0,
            },
            'odds': {
                'home': 1.66, 'draw': 3.60, 'away': 4.75,
                'over_05': 1.05, 'over_15': 1.35, 'over_25': 2.07,
                'over_35': 3.50, 'over_45': 7.00,
                'under_25': 1.75, 'under_35': 1.30, 'under_45': 1.10,
                'btts_yes': 2.00, 'btts_no': 1.72,
                'dc_1x': 1.18, 'dc_12': 1.28, 'dc_x2': 2.20,
            },
            'context': {
                'home_form': 'V-V-E-V-D (70% aproveitamento)',
                'away_form': 'V-D-V-V-E (60% aproveitamento)',
                'h2h': 'Últimos 5: Casa 3V, 1E, 1D. Média 2.8 gols/jogo',
                'home_position': '3º lugar',
                'away_position': '5º lugar',
                'home_injuries_starters': (
                    'Carlos Pérez (ATA) [FORA] - lesão muscular; '
                    'Juan García (DEF) [DÚVIDA] - desconforto no joelho'
                ),
                'away_injuries_starters': 'Sem desfalques entre titulares',
            },
        }
    }

    if match_id not in mock_data:
        raise ValueError(f"Jogo {match_id} não encontrado")
    return mock_data[match_id]


def _get_matches_by_league_and_date(league: str, date: str, limit: int):
    return [_get_match_data('1')][:limit]
