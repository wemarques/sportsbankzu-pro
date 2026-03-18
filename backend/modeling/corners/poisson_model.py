"""
Poisson Model for Corner Predictions (Secondary Baseline)

Simple Poisson distribution applied to total corners.
Used as a benchmark against the Negative Binomial and ML models.

When var(corners) ≈ mean(corners), Poisson is adequate.
When var >> mean (overdispersion), NB should outperform.
"""

import logging
import math
from typing import Any, Dict, List

import numpy as np

from backend.modeling.corners import CORNER_LINES, CORNER_LINES_LEGACY

logger = logging.getLogger("sportsbankzu.corners.poisson_model")


def _poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability mass function."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def poisson_cdf(threshold: int, lam: float) -> float:
    """Cumulative P(X <= threshold)."""
    return sum(_poisson_pmf(k, lam) for k in range(threshold + 1))


def predict_corners_poisson(
    expected_total_corners: float,
    lines: list = None,
) -> Dict[str, float]:
    """Derive corner line probabilities from Poisson distribution.

    Args:
        expected_total_corners: lambda parameter
        lines: Lines to predict (defaults to full CORNER_LINES)

    Returns:
        Dict with probabilities for each line (over and under).
    """
    target_lines = lines or CORNER_LINES
    lam = max(4.0, min(18.0, expected_total_corners))

    result = {}
    for line in target_lines:
        threshold = int(line)
        p_under = poisson_cdf(threshold, lam)
        p_over = max(0.0, min(1.0, 1.0 - p_under))
        result[f"over_{line}"] = p_over
        result[f"under_{line}"] = max(0.0, min(1.0, p_under))

    logger.debug(
        f"Poisson prediction: lambda={lam:.1f} → "
        + " ".join(f"O{l}={result[f'over_{l}']:.3f}" for l in target_lines)
    )

    return result


def train_league_poisson(
    corner_data: List[Dict[str, Any]],
    league_id: str = "",
) -> Dict[str, Any]:
    """Train Poisson model for a league from historical corner data.

    Args:
        corner_data: List of match dicts with 'total_corners' field
        league_id: League identifier

    Returns:
        Training summary dict with fitted parameter and metrics.
    """
    counts = np.array(
        [d["total_corners"] for d in corner_data if d.get("total_corners", 0) > 0],
        dtype=np.float64,
    )

    if len(counts) < 10:
        return {
            "model": "poisson",
            "league_id": league_id,
            "status": "insufficient_data",
            "sample_size": len(counts),
        }

    lam = float(np.mean(counts))

    # Compute line hit rates for validation
    line_metrics = {}
    for line in CORNER_LINES:
        hits = int(np.sum(counts > line))
        empirical_rate = hits / len(counts)
        predicted_rate = 1.0 - poisson_cdf(int(line), lam)
        brier = float((predicted_rate - empirical_rate) ** 2)
        line_metrics[f"over_{line}"] = {
            "empirical_rate": round(empirical_rate, 4),
            "predicted_rate": round(predicted_rate, 4),
            "brier_component": round(brier, 6),
            "sample_size": len(counts),
            "hits": hits,
        }

    brier_scores = [m["brier_component"] for m in line_metrics.values()]
    avg_brier = float(np.mean(brier_scores))

    # Check overdispersion: var/mean ratio (> 1 means Poisson is inadequate)
    variance = float(np.var(counts, ddof=1))
    dispersion_index = variance / lam if lam > 0 else 0

    return {
        "model": "poisson",
        "league_id": league_id,
        "status": "trained",
        "lambda": round(lam, 4),
        "sample_size": len(counts),
        "mean_corners": round(float(np.mean(counts)), 2),
        "std_corners": round(float(np.std(counts, ddof=1)), 2),
        "dispersion_index": round(dispersion_index, 3),
        "overdispersed": dispersion_index > 1.2,
        "avg_brier": round(avg_brier, 6),
        "line_metrics": line_metrics,
    }
