"""
Corners Engine v2 — Layer D: Bidirectional Price Ladder

Prices both Over and Under for the full line ladder using the
NB/Poisson distribution derived from expected_total_corners.

No default side bias: Over and Under are symmetric candidates.
The ladder evaluates edge, fair odds, and confidence-adjusted
probability for every line and both sides.

Output: list of PricedLine dicts, plus selection of optimal market.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.modeling.corners import CORNER_LINES, CORNER_LINES_LEGACY
from backend.modeling.corners.negative_binomial import nb_cdf, _nb2_pmf

logger = logging.getLogger("sportsbankzu.corners.price_ladder")


def _poisson_cdf(threshold: int, lam: float) -> float:
    """Cumulative P(X <= threshold) for Poisson."""
    total = 0.0
    for k in range(threshold + 1):
        try:
            total += math.exp(-lam) * (lam ** k) / math.factorial(k)
        except (OverflowError, ValueError):
            break
    return min(1.0, total)


def compute_line_probabilities(
    expected_ft: float,
    alpha: float,
    distribution: str = "negative_binomial",
    lines: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Compute Over and Under probabilities for all lines.

    Args:
        expected_ft: Projected total corners (mu).
        alpha: NB dispersion parameter (ignored for Poisson).
        distribution: "negative_binomial" or "poisson".
        lines: Lines to price (defaults to full CORNER_LINES).

    Returns:
        List of dicts with line, p_over, p_under, fair_over, fair_under.
    """
    lines = lines or CORNER_LINES
    mu = max(4.0, min(18.0, expected_ft))
    alpha = max(0.001, min(alpha, 5.0))

    result = []
    for line in lines:
        threshold = int(line)  # 8.5 → P(X > 8.5) = P(X >= 9) = 1 - P(X <= 8)

        if distribution == "negative_binomial":
            p_under_eq = nb_cdf(threshold, mu, alpha)
        else:
            p_under_eq = _poisson_cdf(threshold, mu)

        p_over = max(0.001, min(0.999, 1.0 - p_under_eq))
        p_under = max(0.001, min(0.999, p_under_eq))

        fair_over = round(1.0 / p_over, 3) if p_over > 0.001 else None
        fair_under = round(1.0 / p_under, 3) if p_under > 0.001 else None

        result.append({
            "line": line,
            "p_over": round(p_over, 5),
            "p_under": round(p_under, 5),
            "fair_over": fair_over,
            "fair_under": fair_under,
        })

    return result


def attach_odds_and_edge(
    priced: List[Dict[str, Any]],
    odds: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Attach bookmaker odds and compute edge for each line/side.

    Args:
        priced: Output from compute_line_probabilities.
        odds: Dict with keys like "cornersOver85", "cornersUnder85", etc.

    Returns:
        Same list enriched with book_odd_over, book_odd_under,
        edge_over, edge_under fields.
    """
    for item in priced:
        line = item["line"]
        line_tag = str(line).replace(".", "")  # "8.5" → "85"

        # Try various naming conventions
        book_over = _extract_odd(odds, f"cornersOver{line_tag}", f"corners_over_{line_tag}")
        book_under = _extract_odd(odds, f"cornersUnder{line_tag}", f"corners_under_{line_tag}")

        # If we have Over but not Under, derive Under from Over implied
        if book_over and not book_under and item["p_over"] > 0:
            implied_over = 1.0 / book_over
            implied_under = max(0.01, 1.0 - implied_over)
            book_under = round(1.0 / implied_under, 3) if implied_under > 0.01 else None

        item["book_odd_over"] = book_over
        item["book_odd_under"] = book_under
        item["edge_over"] = _compute_edge(item["p_over"], book_over)
        item["edge_under"] = _compute_edge(item["p_under"], book_under)

    return priced


def apply_quality_discount(
    priced: List[Dict[str, Any]],
    data_quality_tier: str,
    model_divergence: float = 0.0,
) -> List[Dict[str, Any]]:
    """Reduce confidence on edges based on data quality and model divergence.

    A quality discount reduces the effective edge to account for
    uncertainty in the underlying projection.
    """
    discount_map = {
        "HIGH": 0.0,
        "MEDIUM": 0.02,
        "LOW": 0.05,
        "INSUFFICIENT": 0.10,
    }
    discount = discount_map.get(data_quality_tier, 0.05)
    # Additional discount for model divergence
    discount += min(0.05, model_divergence * 0.5)

    for item in priced:
        if item.get("edge_over") is not None:
            item["edge_over_adjusted"] = round(item["edge_over"] - discount, 5)
        else:
            item["edge_over_adjusted"] = None
        if item.get("edge_under") is not None:
            item["edge_under_adjusted"] = round(item["edge_under"] - discount, 5)
        else:
            item["edge_under_adjusted"] = None
        item["quality_discount"] = round(discount, 4)

    return priced


def select_best_market(
    priced: List[Dict[str, Any]],
    expected_ft: float,
    alpha: float,
    data_quality_tier: str,
    min_edge: float = 0.02,
    min_prob: float = 0.35,
    max_prob: float = 0.85,
) -> Dict[str, Any]:
    """Select the best line + side or return NO_BET.

    Rules:
    - Over and Under are equal-status candidates.
    - If expected_ft is close to a line AND dispersion is high → NO_BET.
    - Edge must exceed min_edge after quality discount.
    - Probability must be in [min_prob, max_prob] sweet spot.

    Returns:
        Dict with selected_line, selected_side, modeled_probability,
        fair_odds, edge, or no_bet_reason.
    """
    candidates = []

    # Dispersion measure: coefficient of variation from NB
    variance = expected_ft + alpha * expected_ft ** 2
    std_dev = math.sqrt(max(variance, 0.01))

    for item in priced:
        line = item["line"]
        distance_from_mean = abs(expected_ft - line)
        # Penalize lines too close to the mean with high dispersion
        proximity_ratio = distance_from_mean / std_dev if std_dev > 0 else 0

        for side in ["over", "under"]:
            prob = item[f"p_{side}"]
            edge_adj = item.get(f"edge_{side}_adjusted")
            book_odd = item.get(f"book_odd_{side}")
            fair_odd = item.get(f"fair_{side}")

            if edge_adj is None or prob is None:
                continue

            if prob < min_prob or prob > max_prob:
                continue

            if edge_adj < min_edge:
                continue

            # Confidence score: higher edge + reasonable proximity + good prob
            confidence = (
                edge_adj * 10.0
                + proximity_ratio * 2.0
                + (0.5 - abs(prob - 0.55)) * 3.0  # prefer probs near 55%
            )

            candidates.append({
                "line": line,
                "side": side.upper(),
                "market_label": f"{'Over' if side == 'over' else 'Under'} {line}",
                "modeled_probability": round(prob, 5),
                "fair_odds": fair_odd,
                "book_odd": book_odd,
                "edge": round(edge_adj, 5),
                "edge_raw": item.get(f"edge_{side}"),
                "confidence_score": round(confidence, 4),
                "proximity_ratio": round(proximity_ratio, 3),
                "distance_from_mean": round(distance_from_mean, 2),
            })

    if not candidates:
        return _no_bet("no_qualifying_candidate", expected_ft, std_dev)

    # Sort by confidence descending
    candidates.sort(key=lambda c: c["confidence_score"], reverse=True)
    best = candidates[0]

    # Safety: if best line is too close to mean with high dispersion, NO_BET
    if best["proximity_ratio"] < 0.3 and data_quality_tier in ("LOW", "INSUFFICIENT"):
        return _no_bet("line_too_close_to_mean_with_low_quality", expected_ft, std_dev)

    # Attach runner-up for transparency
    best["runner_up"] = candidates[1] if len(candidates) > 1 else None
    best["total_candidates"] = len(candidates)

    return best


def price_full_ladder(
    expected_ft: float,
    alpha: float,
    odds: Dict[str, Any],
    data_quality_tier: str = "MEDIUM",
    model_divergence: float = 0.0,
    distribution: str = "negative_binomial",
    lines: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """End-to-end pricing: compute probs → attach odds → apply quality → select best.

    This is the main entry point for Layer D.
    """
    priced = compute_line_probabilities(expected_ft, alpha, distribution, lines)
    priced = attach_odds_and_edge(priced, odds)
    priced = apply_quality_discount(priced, data_quality_tier, model_divergence)

    best = select_best_market(
        priced, expected_ft, alpha, data_quality_tier,
    )

    # Compute prediction interval
    variance = expected_ft + alpha * expected_ft ** 2
    std_dev = math.sqrt(max(variance, 0.01))

    return {
        "ladder": priced,
        "selected": best,
        "expected_ft": round(expected_ft, 2),
        "alpha": round(alpha, 4),
        "std_dev": round(std_dev, 2),
        "prediction_interval_low": round(max(0, expected_ft - 1.645 * std_dev), 1),
        "prediction_interval_high": round(expected_ft + 1.645 * std_dev, 1),
        "distribution": distribution,
        "data_quality_tier": data_quality_tier,
    }


# ─── Helpers ───

def _extract_odd(odds: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        val = odds.get(key)
        if val is not None:
            try:
                v = float(val)
                return v if v > 1.0 else None
            except (ValueError, TypeError):
                pass
    return None


def _compute_edge(modeled_prob: float, book_odd: Optional[float]) -> Optional[float]:
    if book_odd is None or book_odd <= 1.0:
        return None
    implied_prob = 1.0 / book_odd
    return round(modeled_prob - implied_prob, 5)


def _no_bet(reason: str, expected_ft: float, std_dev: float) -> Dict[str, Any]:
    return {
        "line": None,
        "side": None,
        "market_label": None,
        "modeled_probability": None,
        "fair_odds": None,
        "book_odd": None,
        "edge": None,
        "no_bet": True,
        "no_bet_reason": reason,
        "expected_ft": round(expected_ft, 2),
        "std_dev": round(std_dev, 2),
    }
