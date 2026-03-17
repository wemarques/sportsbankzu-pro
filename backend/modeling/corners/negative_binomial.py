"""
Negative Binomial Model for Corner Predictions (Primary Baseline)

Captures overdispersion in corner counts better than Poisson.
The NB distribution has two parameters:
- mu (mean): expected total corners
- alpha (dispersion): controls variance beyond Poisson

Variance = mu + alpha * mu^2 (NB2 parameterization)

When alpha → 0, NB converges to Poisson.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.modeling.corners import CORNER_LINES

logger = logging.getLogger("sportsbankzu.corners.negative_binomial")


def _nb2_pmf(k: int, mu: float, alpha: float) -> float:
    """Negative Binomial PMF (NB2 parameterization).

    P(X=k) = Gamma(k + r) / (Gamma(r) * k!) * (r/(r+mu))^r * (mu/(r+mu))^k
    where r = 1/alpha
    """
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    if alpha <= 0:
        # Degenerate to Poisson
        try:
            return math.exp(-mu) * (mu ** k) / math.factorial(k)
        except Exception:
            return 0.0

    r = 1.0 / alpha
    p = r / (r + mu)

    try:
        log_pmf = (
            math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
            + r * math.log(p)
            + k * math.log(1 - p)
        )
        return math.exp(log_pmf)
    except (ValueError, OverflowError):
        return 0.0


def nb_cdf(threshold: int, mu: float, alpha: float) -> float:
    """Cumulative distribution P(X <= threshold)."""
    return sum(_nb2_pmf(k, mu, alpha) for k in range(threshold + 1))


def fit_negative_binomial(
    corner_counts: np.ndarray,
) -> Tuple[float, float]:
    """Fit NB2 parameters (mu, alpha) via method of moments.

    mu = mean(X)
    alpha = (var(X) - mu) / mu^2  (if var > mu, else small positive)

    Returns (mu, alpha).
    """
    if len(corner_counts) < 3:
        return (10.0, 0.1)

    mu = float(np.mean(corner_counts))
    var = float(np.var(corner_counts, ddof=1))

    if mu <= 0:
        mu = 10.0

    # alpha from NB2: Var = mu + alpha * mu^2
    if var > mu and mu > 0:
        alpha = (var - mu) / (mu ** 2)
    else:
        alpha = 0.01  # near-Poisson

    alpha = max(0.001, min(alpha, 5.0))  # clamp

    return (mu, alpha)


def predict_corners_nb(
    expected_total_corners: float,
    alpha: float = 0.15,
) -> Dict[str, float]:
    """Derive corner line probabilities from NB distribution.

    Args:
        expected_total_corners: mu parameter (expected total corners)
        alpha: dispersion parameter (higher = more variance)

    Returns:
        Dict with probabilities for each line, e.g. {"over_8.5": 0.65, ...}
    """
    mu = max(4.0, min(18.0, expected_total_corners))
    alpha = max(0.001, min(alpha, 5.0))

    result = {}
    for line in CORNER_LINES:
        threshold = int(line)  # e.g. 8.5 → P(X > 8.5) = P(X >= 9) = 1 - P(X <= 8)
        p_under = nb_cdf(threshold, mu, alpha)
        result[f"over_{line}"] = max(0.0, min(1.0, 1.0 - p_under))

    logger.debug(
        f"NB prediction: mu={mu:.1f}, alpha={alpha:.3f} → "
        + " ".join(f"O{l}={result[f'over_{l}']:.3f}" for l in CORNER_LINES)
    )

    return result


def train_league_nb(
    corner_data: List[Dict[str, Any]],
    league_id: str = "",
) -> Dict[str, Any]:
    """Train NB model for a league from historical corner data.

    Args:
        corner_data: List of match dicts with 'total_corners' field
        league_id: League identifier

    Returns:
        Training summary dict with fitted parameters and metrics.
    """
    counts = np.array(
        [d["total_corners"] for d in corner_data if d.get("total_corners", 0) > 0],
        dtype=np.float64,
    )

    if len(counts) < 10:
        return {
            "model": "negative_binomial",
            "league_id": league_id,
            "status": "insufficient_data",
            "sample_size": len(counts),
        }

    mu, alpha = fit_negative_binomial(counts)

    # Compute line hit rates (empirical) for validation
    line_metrics = {}
    for line in CORNER_LINES:
        hits = int(np.sum(counts > line))
        empirical_rate = hits / len(counts)
        predicted_rate = 1.0 - nb_cdf(int(line), mu, alpha)
        brier = float((predicted_rate - empirical_rate) ** 2)
        line_metrics[f"over_{line}"] = {
            "empirical_rate": round(empirical_rate, 4),
            "predicted_rate": round(predicted_rate, 4),
            "brier_component": round(brier, 6),
            "sample_size": len(counts),
            "hits": hits,
        }

    # Compute overall Brier score across all lines
    brier_scores = [m["brier_component"] for m in line_metrics.values()]
    avg_brier = float(np.mean(brier_scores))

    return {
        "model": "negative_binomial",
        "league_id": league_id,
        "status": "trained",
        "mu": round(mu, 4),
        "alpha": round(alpha, 4),
        "sample_size": len(counts),
        "mean_corners": round(float(np.mean(counts)), 2),
        "std_corners": round(float(np.std(counts, ddof=1)), 2),
        "variance_ratio": round(float(np.var(counts, ddof=1) / mu), 3) if mu > 0 else 0,
        "avg_brier": round(avg_brier, 6),
        "line_metrics": line_metrics,
    }
