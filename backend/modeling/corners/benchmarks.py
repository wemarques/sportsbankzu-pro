"""
Corner Benchmarks and Model Comparison Framework

Implements formal comparison between:
- League historical line rate (naive benchmark)
- Team blended historical rate
- Poisson baseline (secondary)
- Negative Binomial baseline (primary)
- ML Regression projection

Metrics per league and per line:
- Brier Score
- LogLoss
- ECE / calibration
- ROI (theoretical)
- Sample size
- Stability per window
- Drift
"""

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

from backend.modeling.corners import CORNER_LINES, MODEL_CANDIDATES

logger = logging.getLogger("sportsbankzu.corners.benchmarks")


def _logloss(predicted: float, actual: float) -> float:
    """Binary log loss for a single prediction."""
    p = max(1e-15, min(1 - 1e-15, predicted))
    if actual == 1:
        return -math.log(p)
    return -math.log(1 - p)


def _brier(predicted: float, actual: float) -> float:
    """Brier score for a single binary prediction."""
    return (predicted - actual) ** 2


def _ece(predictions: np.ndarray, actuals: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    if len(predictions) == 0:
        return 1.0

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(predictions)

    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (predictions > lo) & (predictions <= hi)
        count = int(mask.sum())
        if count == 0:
            continue
        avg_pred = float(predictions[mask].mean())
        avg_actual = float(actuals[mask].mean())
        ece += (count / n) * abs(avg_actual - avg_pred)

    return ece


def _roi_theoretical(predictions: np.ndarray, actuals: np.ndarray, fair_margin: float = 0.05) -> float:
    """Theoretical ROI assuming fair odds with margin.

    Simulates betting when predicted probability > implied probability from fair odds.
    """
    if len(predictions) == 0:
        return 0.0

    total_staked = 0.0
    total_return = 0.0

    for pred, actual in zip(predictions, actuals):
        if pred > 0.5 + fair_margin:  # Only bet when edge > margin
            fair_odd = 1.0 / pred
            total_staked += 1.0
            if actual == 1:
                total_return += fair_odd

    if total_staked == 0:
        return 0.0

    return (total_return - total_staked) / total_staked


def _compute_stability(predictions: np.ndarray, window: int = 20) -> float:
    """Stability of predictions over rolling windows (lower = more stable).

    Measures coefficient of variation of rolling mean predictions.
    """
    if len(predictions) < window * 2:
        return 1.0

    rolling_means = []
    for i in range(0, len(predictions) - window + 1, window // 2):
        segment = predictions[i:i + window]
        rolling_means.append(float(segment.mean()))

    if len(rolling_means) < 2:
        return 0.0

    arr = np.array(rolling_means)
    mean = arr.mean()
    if mean <= 0:
        return 1.0
    return float(arr.std() / mean)


def _compute_drift(predictions: np.ndarray, actuals: np.ndarray, split_ratio: float = 0.5) -> float:
    """Drift: difference in calibration between first half and second half of data."""
    if len(predictions) < 20:
        return 0.0

    split = int(len(predictions) * split_ratio)
    early_preds, late_preds = predictions[:split], predictions[split:]
    early_acts, late_acts = actuals[:split], actuals[split:]

    early_bias = float(early_preds.mean() - early_acts.mean())
    late_bias = float(late_preds.mean() - late_acts.mean())

    return abs(late_bias - early_bias)


def evaluate_model_on_line(
    predictions: np.ndarray,
    actuals: np.ndarray,
    line: float,
    model_name: str,
) -> Dict[str, Any]:
    """Compute all metrics for a single model on a single line.

    Args:
        predictions: Array of predicted probabilities (0-1) for this line
        actuals: Array of binary outcomes (1 if over, 0 if under)
        line: The corner line (e.g. 9.5)
        model_name: Name of the model

    Returns:
        Dict with all evaluation metrics.
    """
    n = len(predictions)
    if n == 0:
        return {"model": model_name, "line": line, "status": "no_data", "sample_size": 0}

    brier_scores = np.array([_brier(p, a) for p, a in zip(predictions, actuals)])
    logloss_scores = np.array([_logloss(p, a) for p, a in zip(predictions, actuals)])

    return {
        "model": model_name,
        "line": line,
        "sample_size": n,
        "brier": round(float(brier_scores.mean()), 6),
        "logloss": round(float(logloss_scores.mean()), 6),
        "ece": round(_ece(predictions, actuals), 6),
        "roi_theoretical": round(_roi_theoretical(predictions, actuals), 4),
        "stability": round(_compute_stability(predictions), 4),
        "drift": round(_compute_drift(predictions, actuals), 4),
        "mean_prediction": round(float(predictions.mean()), 4),
        "empirical_rate": round(float(actuals.mean()), 4),
        "calibration_bias": round(float(predictions.mean() - actuals.mean()), 4),
    }


def compare_models(
    model_results: Dict[str, Dict[str, np.ndarray]],
    actuals_by_line: Dict[str, np.ndarray],
    league_id: str = "",
) -> Dict[str, Any]:
    """Compare all candidate models across all lines.

    Args:
        model_results: {model_name: {line_key: predictions_array}}
        actuals_by_line: {line_key: binary_outcomes_array}
        league_id: League identifier

    Returns:
        Comprehensive comparison report with beats_* fields and champion selection hints.
    """
    comparison = {
        "league_id": league_id,
        "models": {},
        "lines": {},
    }

    # Evaluate each model on each line
    for model_name, line_preds in model_results.items():
        model_metrics = {}
        for line_key, preds in line_preds.items():
            actuals = actuals_by_line.get(line_key, np.array([]))
            if len(actuals) == 0 or len(preds) == 0:
                continue
            # Align lengths
            min_len = min(len(preds), len(actuals))
            preds = preds[:min_len]
            actuals = actuals[:min_len]

            line_val = float(line_key.replace("over_", ""))
            metrics = evaluate_model_on_line(preds, actuals, line_val, model_name)
            model_metrics[line_key] = metrics

        comparison["models"][model_name] = model_metrics

    # Build per-line comparison
    for line in CORNER_LINES:
        line_key = f"over_{line}"
        line_comparison = {}

        model_briers = {}
        for model_name in model_results:
            metrics = comparison["models"].get(model_name, {}).get(line_key)
            if metrics and "brier" in metrics:
                model_briers[model_name] = metrics["brier"]
                line_comparison[model_name] = metrics

        if not model_briers:
            continue

        # Determine beats_* relationships
        beats = {}
        for model_a in model_briers:
            for model_b in model_briers:
                if model_a != model_b:
                    beats[f"{model_a}_beats_{model_b}"] = model_briers[model_a] < model_briers[model_b]

        # Determine best model for this line
        if model_briers:
            best_model = min(model_briers, key=model_briers.get)
            line_comparison["best_model"] = best_model
            line_comparison["beats"] = beats

        comparison["lines"][line_key] = line_comparison

    return comparison


def compute_league_baseline(
    corner_counts: np.ndarray,
    line: float,
) -> float:
    """Simple league historical hit rate for a line (naive benchmark)."""
    if len(corner_counts) == 0:
        return 0.5
    return float(np.mean(corner_counts > line))


def compute_team_blended_baseline(
    home_team_counts: np.ndarray,
    away_team_counts: np.ndarray,
    line: float,
    league_rate: float,
    weights: tuple = (0.35, 0.35, 0.30),
) -> float:
    """Blended baseline using home team rate, away team rate, and league rate."""
    w_home, w_away, w_league = weights

    home_rate = float(np.mean(home_team_counts > line)) if len(home_team_counts) > 0 else league_rate
    away_rate = float(np.mean(away_team_counts > line)) if len(away_team_counts) > 0 else league_rate

    return w_home * home_rate + w_away * away_rate + w_league * league_rate
