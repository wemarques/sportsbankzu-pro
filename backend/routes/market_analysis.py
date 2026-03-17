"""
Market Analysis API Route

Provides the new unified market analysis endpoint that integrates all 5 layers:
- Layer 1: Data governance + quality score
- Layer 2: Poisson matrix + corners engine
- Layer 3: EV + classification
- Layer 4: Bankroll computation
- Layer 5: Correlation + multiples eligibility
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger("sportsbankzu.routes.market_analysis")
router = APIRouter(prefix="/analysis", tags=["market-analysis"])


class MarketAnalysisRequest(BaseModel):
    match_data: Dict[str, Any]
    league_id: str = ""
    regime: str = "NORMAL"
    bankroll: Optional[float] = None


class BatchAnalysisRequest(BaseModel):
    matches: List[Dict[str, Any]]
    league_id: str = ""
    regime: str = "NORMAL"
    bankroll: Optional[float] = None


@router.post("/match")
async def analyze_match(req: MarketAnalysisRequest):
    """Analyze a single match through the full 5-layer pipeline."""
    try:
        from backend.services.ev_classification import evaluate_match_markets
        from backend.services.bankroll_engine import compute_stake

        bundle = evaluate_match_markets(
            req.match_data,
            league_id=req.league_id,
            regime=req.regime,
        )

        result = {
            "match_id": bundle.match_id,
            "home_team": bundle.home_team,
            "away_team": bundle.away_team,
            "data_quality_score": bundle.data_quality_score,
            "eligible_for_multiples": bundle.eligible_for_multiples,
            "reason_codes": [rc.value for rc in bundle.reason_codes],
            "markets": [],
        }

        for market in bundle.markets:
            m = market.to_legacy_mercado()

            # Add bankroll info if requested
            if req.bankroll and req.bankroll > 0:
                stake_info = compute_stake(m, req.bankroll)
                m["stake"] = stake_info["stake"]
                m["stake_info"] = stake_info

            result["markets"].append(m)

        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Market analysis failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.post("/batch")
async def analyze_batch(req: BatchAnalysisRequest):
    """Analyze multiple matches and return market bundles + multiples suggestions."""
    try:
        from backend.services.ev_classification import evaluate_match_markets
        from backend.services.correlation_matrix import (
            filter_eligible_for_multiples,
            select_picks_for_game,
            build_multiples,
        )
        from backend.services.bankroll_engine import compute_stake

        results = []
        all_eligible_picks = []

        for match_data in req.matches:
            bundle = evaluate_match_markets(
                match_data,
                league_id=req.league_id,
                regime=req.regime,
            )

            match_result = {
                "match_id": bundle.match_id,
                "home_team": bundle.home_team,
                "away_team": bundle.away_team,
                "data_quality_score": bundle.data_quality_score,
                "eligible_for_multiples": bundle.eligible_for_multiples,
                "markets": [],
            }

            for market in bundle.markets:
                m = market.to_legacy_mercado()
                m["match_id"] = bundle.match_id

                if req.bankroll and req.bankroll > 0:
                    stake_info = compute_stake(m, req.bankroll)
                    m["stake"] = stake_info["stake"]

                match_result["markets"].append(m)

            results.append(match_result)

            # Collect eligible picks for multiples
            eligible = filter_eligible_for_multiples(match_result["markets"])
            selected = select_picks_for_game(eligible)
            all_eligible_picks.extend(selected)

        # Build multiples from eligible picks
        multiples = build_multiples(all_eligible_picks)

        return {
            "success": True,
            "matches": results,
            "total_matches": len(results),
            "multiples": multiples[:16],
            "total_eligible_picks": len(all_eligible_picks),
        }

    except Exception as e:
        logger.error(f"Batch analysis failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.get("/correlation")
async def get_correlation_matrix():
    """Return the market correlation matrix for reference."""
    from backend.services.correlation_matrix import CORRELATION_MATRIX, REDUNDANT_PAIRS

    matrix = {}
    for pair, corr in CORRELATION_MATRIX.items():
        key = " + ".join(sorted(pair))
        matrix[key] = corr

    redundant = [" + ".join(sorted(pair)) for pair in REDUNDANT_PAIRS]

    return {
        "correlation_matrix": matrix,
        "redundant_pairs": redundant,
        "max_correlation_same_game": 0.60,
        "max_selections_per_game": 2,
    }
