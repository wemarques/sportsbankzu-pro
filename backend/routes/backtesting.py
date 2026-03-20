"""Backtesting API routes for SportsBankZU Pro.

Reference: REGRAS #050 — backtesting, calibration, SAFE monitoring.
"""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(tags=["backtesting"])


@router.get("/backtesting/run")
async def run_backtesting(
    league: Optional[str] = Query(None, description="Specific league or None for all"),
    market: Optional[str] = Query(None, description="Specific market or None for all"),
    days: int = Query(30, ge=7, le=180, description="Period in days"),
):
    """Run backtesting and return full metrics."""
    from backend.services.backtesting import run_backtest
    return run_backtest(league=league, market=market, days=days)


@router.get("/backtesting/safe-reactivation")
async def check_safe_reactivation():
    """Evaluate SAFE reactivation criteria (#043)."""
    from backend.services.backtesting import evaluate_safe_reactivation
    return evaluate_safe_reactivation()


@router.get("/backtesting/calibration-search")
async def calibration_search(
    league: str = Query(..., description="League to calibrate"),
    market: str = Query(..., description="Market to calibrate"),
    param: str = Query(..., description="Parameter (e.g. lambda_weight_season)"),
):
    """Grid search for a calibrable parameter for a league/market."""
    from backend.services.backtesting import calibration_grid_search

    PARAM_RANGES = {
        "lambda_weight_season": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75],
        "btts_weight_footystats": [0.20, 0.30, 0.40, 0.50, 0.60],
        "btts_weight_poisson": [0.20, 0.30, 0.40, 0.50],
        "corners_weight_direct": [0.40, 0.50, 0.60, 0.70, 0.80],
        "xg_blend_lambda": [0.50, 0.60, 0.70, 0.80],
        "safe_prob_1x2": [0.55, 0.58, 0.60, 0.62, 0.65, 0.68],
        "safe_prob_ou": [0.68, 0.70, 0.72, 0.75, 0.78, 0.80],
        "safe_prob_btts": [0.68, 0.70, 0.72, 0.75, 0.78],
        "safe_prob_corners": [0.65, 0.68, 0.70, 0.72, 0.75],
        "safe_prob_cards": [0.68, 0.70, 0.72, 0.75, 0.78],
    }

    param_range = PARAM_RANGES.get(param)
    if not param_range:
        return {"error": f"Parameter '{param}' not recognized. Valid: {list(PARAM_RANGES.keys())}"}

    return calibration_grid_search(league=league, market=market, param_name=param, param_range=param_range)
