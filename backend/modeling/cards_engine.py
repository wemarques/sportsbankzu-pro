"""Cards projection engine — Poisson-based card probability calculator (#085).

Calculates Over/Under probabilities for card markets using Poisson distribution.
Uses cardsAVG from FootyStats + cards_multiplier from per-league calibration.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger("sportsbankzu.cards_engine")

# Card lines for betting markets
CARD_LINES = [2.5, 3.5, 4.5, 5.5]

# Default cards lambda when data is unavailable
DEFAULT_CARDS_LAMBDA = 4.0  # ~4 cards per match is typical


def _poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass function."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def predict_cards(
    home_stats: dict,
    away_stats: dict,
    league_id: str = "",
    league_stats: Optional[dict] = None,
) -> dict:
    """Project total cards for a match and compute Over/Under probabilities.

    Args:
        home_stats: stats do time da casa
        away_stats: stats do time visitante
        league_id: ID da liga para buscar cards_multiplier
        league_stats: medias da liga (opcional)

    Returns:
        {
            "projected_total_cards": float,
            "cards_lambda": float,
            "model_source": "poisson",
            "lines": {
                "over_2.5": {"prob": float, "prob_pct": float},
                "under_2.5": {"prob": float, "prob_pct": float},
                ...
            }
        }
    """
    cards_lambda = _estimate_cards_lambda(home_stats, away_stats, league_stats)

    cards_multiplier = _get_cards_multiplier(league_id)
    cards_lambda_adjusted = cards_lambda * cards_multiplier

    lines = {}
    for line in CARD_LINES:
        k_max = int(line)
        p_under = sum(_poisson_pmf(k, cards_lambda_adjusted) for k in range(k_max + 1))
        p_over = 1 - p_under

        lines[f"over_{line}"] = {
            "prob": round(p_over, 4),
            "prob_pct": round(p_over * 100, 1),
        }
        lines[f"under_{line}"] = {
            "prob": round(p_under, 4),
            "prob_pct": round(p_under * 100, 1),
        }

    return {
        "projected_total_cards": round(cards_lambda_adjusted, 1),
        "cards_lambda": round(cards_lambda_adjusted, 3),
        "cards_lambda_raw": round(cards_lambda, 3),
        "cards_multiplier": cards_multiplier,
        "model_source": "poisson",
        "lines": lines,
    }


def _estimate_cards_lambda(
    home_stats: dict,
    away_stats: dict,
    league_stats: Optional[dict] = None,
) -> float:
    """Estimate cards lambda combining home and away data.

    3-layer strategy (same pattern as corners_engine):
    1. Average of team cards/match
    2. Fallback: league average
    3. Fallback: DEFAULT_CARDS_LAMBDA
    """
    # Try per-venue averages first (home team's home cards + away team's away cards)
    home_cards = _safe_float(home_stats.get("homeCardsPerMatch",
                  home_stats.get("cardsAVG_home",
                  home_stats.get("home_cards_avg",
                  home_stats.get("cards_per_match_home")))))

    away_cards = _safe_float(away_stats.get("awayCardsPerMatch",
                  away_stats.get("cardsAVG_away",
                  away_stats.get("away_cards_avg",
                  away_stats.get("cards_per_match_away")))))

    if home_cards is not None and away_cards is not None and home_cards > 0 and away_cards > 0:
        return home_cards + away_cards

    # Try overall average (cardsAVG_overall = total cards in the match, not per team)
    home_cards_overall = _safe_float(home_stats.get("cardsPerMatch",
                         home_stats.get("cardsAVG_overall",
                         home_stats.get("cards_per_match"))))

    away_cards_overall = _safe_float(away_stats.get("cardsPerMatch",
                         away_stats.get("cardsAVG_overall",
                         away_stats.get("cards_per_match"))))

    if home_cards_overall is not None and away_cards_overall is not None:
        return (home_cards_overall + away_cards_overall) / 2

    if home_cards_overall is not None:
        return home_cards_overall

    if away_cards_overall is not None:
        return away_cards_overall

    # League average fallback
    if league_stats:
        league_cards = _safe_float(league_stats.get("avg_cards",
                       league_stats.get("cardsAVG_overall",
                       league_stats.get("league_cards_avg",
                       league_stats.get("average_cards_per_match")))))
        if league_cards is not None and league_cards > 0:
            return league_cards

    logger.debug(f"[cards] No card data available, using default {DEFAULT_CARDS_LAMBDA}")
    return DEFAULT_CARDS_LAMBDA


def _get_cards_multiplier(league_id: str) -> float:
    """Fetch calibrated cards_multiplier from corrections DB."""
    if not league_id:
        return 1.0
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        val = corrections.get("cards_multiplier", {})
        if isinstance(val, dict):
            return float(val.get("value", 1.0))
        return float(val) if val else 1.0
    except Exception:
        return 1.0


def _safe_float(val) -> Optional[float]:
    """Safely convert to float."""
    if val is None or val == "N/A" or val == -1:
        return None
    try:
        v = float(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None
