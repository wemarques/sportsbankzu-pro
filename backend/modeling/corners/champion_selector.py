"""
Champion Model Selection Logic for Corners

Selects the best model (champion) and fallback per league and per line,
based on explicit criteria:

Selection criteria (in priority order):
1. Calibration (ECE) — model must be reasonably calibrated
2. Brier Score / LogLoss — primary accuracy metric
3. Temporal stability — model shouldn't degrade over time
4. Sample adequacy — enough data to trust the model
5. Drift — acceptable drift
6. ROI theoretical — secondary criterion, not dominant

Champion can be: negative_binomial | poisson | ml_regression
Fallback: different from champion, second-best performer

Selection is registered per league and per line in artifacts.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.modeling.corners import MODEL_CANDIDATES, CORNER_LINES

logger = logging.getLogger("sportsbankzu.corners.champion_selector")

# Thresholds for selection
MAX_ECE_FOR_CHAMPION = 0.15  # ECE must be below this
MAX_BRIER_FOR_CHAMPION = 0.30  # Brier must be below this
MAX_DRIFT_FOR_CHAMPION = 0.10  # Drift must be below this
MIN_SAMPLE_SIZE = 30  # Minimum samples for model to be eligible
MAX_STABILITY_CV = 0.40  # Stability coefficient of variation

# NB2 preference: corners exhibit overdispersion (variance > mean),
# making negative binomial the statistically appropriate distribution.
# When NB2 composite score is within this threshold of best, prefer NB2.
NB2_PREFERENCE_THRESHOLD = 0.02

# Weight for composite score
SELECTION_WEIGHTS = {
    "brier": 0.35,
    "logloss": 0.25,
    "ece": 0.20,
    "stability": 0.10,
    "roi_theoretical": 0.10,
}


def _compute_composite_score(metrics: Dict[str, Any]) -> float:
    """Compute weighted composite score (lower = better).

    Normalizes each metric to 0-1 scale where 0 is best.
    """
    if not metrics or metrics.get("status") == "no_data":
        return 999.0

    # All metrics where lower is better (except ROI where higher is better)
    brier = metrics.get("brier", 1.0)
    logloss = metrics.get("logloss", 5.0)
    ece = metrics.get("ece", 1.0)
    stability = metrics.get("stability", 1.0)
    roi = metrics.get("roi_theoretical", 0.0)

    # Normalize to 0-1 (approximate ranges)
    brier_norm = min(brier / 0.30, 1.0)
    logloss_norm = min(logloss / 1.0, 1.0)
    ece_norm = min(ece / 0.15, 1.0)
    stability_norm = min(stability / 0.40, 1.0)
    roi_norm = 1.0 - max(0.0, min(roi / 0.20, 1.0))  # inverted: higher ROI = lower score

    score = (
        SELECTION_WEIGHTS["brier"] * brier_norm
        + SELECTION_WEIGHTS["logloss"] * logloss_norm
        + SELECTION_WEIGHTS["ece"] * ece_norm
        + SELECTION_WEIGHTS["stability"] * stability_norm
        + SELECTION_WEIGHTS["roi_theoretical"] * roi_norm
    )

    return round(score, 6)


def _is_eligible(metrics: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Check if a model is eligible for champion selection.

    Returns (is_eligible, list_of_disqualification_reasons).
    """
    reasons = []

    if not metrics or metrics.get("status") == "no_data":
        return False, ["no_data"]

    sample_size = metrics.get("sample_size", 0)
    if sample_size < MIN_SAMPLE_SIZE:
        reasons.append(f"sample_size={sample_size} < {MIN_SAMPLE_SIZE}")

    ece = metrics.get("ece", 1.0)
    if ece > MAX_ECE_FOR_CHAMPION:
        reasons.append(f"ece={ece:.4f} > {MAX_ECE_FOR_CHAMPION}")

    brier = metrics.get("brier", 1.0)
    if brier > MAX_BRIER_FOR_CHAMPION:
        reasons.append(f"brier={brier:.4f} > {MAX_BRIER_FOR_CHAMPION}")

    drift = metrics.get("drift", 0.0)
    if drift > MAX_DRIFT_FOR_CHAMPION:
        reasons.append(f"drift={drift:.4f} > {MAX_DRIFT_FOR_CHAMPION}")

    return len(reasons) == 0, reasons


def select_champion_for_line(
    model_metrics: Dict[str, Dict[str, Any]],
    line: float,
    league_id: str = "",
) -> Dict[str, Any]:
    """Select champion and fallback model for a specific line.

    Args:
        model_metrics: {model_name: {metrics_dict}} for a specific line
        line: Corner line (e.g. 9.5)
        league_id: League identifier

    Returns:
        Selection result with champion_model, fallback_model, and reasoning.
    """
    eligible_models = {}
    all_scores = {}
    eligibility_details = {}

    for model_name, metrics in model_metrics.items():
        is_elig, reasons = _is_eligible(metrics)
        eligibility_details[model_name] = {
            "eligible": is_elig,
            "reasons": reasons,
        }

        score = _compute_composite_score(metrics)
        all_scores[model_name] = score

        if is_elig:
            eligible_models[model_name] = score

    result = {
        "league_id": league_id,
        "line": line,
        "champion_model": None,
        "fallback_model": None,
        "champion_score": None,
        "fallback_score": None,
        "selection_method": "composite_score",
        "eligibility": eligibility_details,
        "all_scores": {k: round(v, 6) for k, v in all_scores.items()},
    }

    if not eligible_models:
        # No model eligible — use best ineligible as fallback with degraded trust
        if all_scores:
            best = min(all_scores, key=all_scores.get)
            result["champion_model"] = best
            result["champion_score"] = all_scores[best]
            result["selection_method"] = "best_ineligible_fallback"
            logger.warning(
                f"No eligible champion for {league_id} over_{line}. "
                f"Using best ineligible: {best}"
            )

            # Second best as fallback
            remaining = {k: v for k, v in all_scores.items() if k != best}
            if remaining:
                fallback = min(remaining, key=remaining.get)
                result["fallback_model"] = fallback
                result["fallback_score"] = remaining[fallback]

        return result

    # Sort eligible by score (ascending = better)
    sorted_eligible = sorted(eligible_models.items(), key=lambda x: x[1])

    champion_name, champion_score = sorted_eligible[0]

    # NB2 preference tiebreaker: if NB2 is eligible and within 2% of best,
    # prefer it due to statistical appropriateness for overdispersed corner data
    if champion_name != "negative_binomial" and "negative_binomial" in eligible_models:
        nb2_score = eligible_models["negative_binomial"]
        if champion_score > 0 and (nb2_score - champion_score) / champion_score <= NB2_PREFERENCE_THRESHOLD:
            logger.info(
                f"NB2 preference applied for {league_id} over_{line}: "
                f"gap={(nb2_score - champion_score) / champion_score:.4f} <= {NB2_PREFERENCE_THRESHOLD}"
            )
            champion_name = "negative_binomial"
            champion_score = nb2_score
            result["selection_method"] = "composite_score_nb2_preference"

    result["champion_model"] = champion_name
    result["champion_score"] = champion_score

    # Fallback: second-best eligible, or best ineligible
    if len(sorted_eligible) > 1:
        result["fallback_model"] = sorted_eligible[1][0]
        result["fallback_score"] = sorted_eligible[1][1]
    else:
        # Fallback from ineligible models
        remaining = {k: v for k, v in all_scores.items() if k != champion_name}
        if remaining:
            fallback = min(remaining, key=remaining.get)
            result["fallback_model"] = fallback
            result["fallback_score"] = remaining[fallback]

    logger.info(
        f"Champion for {league_id} over_{line}: {champion_name} "
        f"(score={champion_score:.4f}), fallback={result['fallback_model']}"
    )

    return result


def select_champions_for_league(
    comparison: Dict[str, Any],
    league_id: str = "",
) -> Dict[str, Any]:
    """Select champion and fallback for all lines in a league.

    Args:
        comparison: Output from benchmarks.compare_models()
        league_id: League identifier

    Returns:
        Dict with selections per line and league-level summary.
    """
    selections = {}

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        line_data = comparison.get("lines", {}).get(line_key, {})

        # Gather metrics per model for this line
        model_metrics = {}
        for model_name in MODEL_CANDIDATES:
            metrics = comparison.get("models", {}).get(model_name, {}).get(line_key)
            if metrics:
                model_metrics[model_name] = metrics

        if model_metrics:
            selection = select_champion_for_line(model_metrics, line, league_id)
            selections[line_key] = selection

    # League-level dominant champion (most frequently selected)
    champion_counts = {}
    for sel in selections.values():
        champ = sel.get("champion_model")
        if champ:
            champion_counts[champ] = champion_counts.get(champ, 0) + 1

    dominant_champion = max(champion_counts, key=champion_counts.get) if champion_counts else None

    return {
        "league_id": league_id,
        "line_selections": selections,
        "dominant_champion": dominant_champion,
        "champion_distribution": champion_counts,
    }
