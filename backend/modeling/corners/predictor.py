"""
Corners Engine v2 — Orchestrator / Runtime Predictor

Main entry point for corner market predictions. Replaces the v1
Over-only predictor with a full bidirectional engine:

1. Data Quality Assessment (Layer A)
2. Feature Building + Baseline Priors (Layer B)
3. Expected Corners Projection FT/1H/2H (Layer C)
4. Bidirectional Price Ladder — Over + Under (Layer D)
5. Decision Engine + Mistral Review (Layer E)

The engine does NOT anchor on Over 8.5. It first estimates the
distribution, then prices all lines symmetrically.
"""

import logging
import math
from typing import Any, Dict, List, Optional

from backend.modeling.corners import (
    CORNER_LINES,
    CORNER_LINES_LEGACY,
    ENGINE_VERSION,
    MARKET_FAMILY,
    MODEL_CANDIDATES,
)
from backend.modeling.corners.artifacts import (
    get_league_champion,
    get_league_line_status,
    load_artifact,
)
from backend.modeling.corners.data_quality import compute_corners_data_quality
from backend.modeling.corners.features import (
    build_match_corner_features,
    build_v2_match_features,
    compute_matchup_pressure_index,
)
from backend.modeling.corners.negative_binomial import (
    fit_negative_binomial,
    nb_cdf,
    predict_corners_nb,
)
from backend.modeling.corners.poisson_model import predict_corners_poisson
from backend.modeling.corners.ml_regression import predict_corners_ml
from backend.modeling.corners.operational_states import CornerOperationalState
from backend.modeling.corners.price_ladder import price_full_ladder
from backend.modeling.corners.mistral_review import (
    apply_mistral_adjustment,
    review_corners_with_mistral,
)

# Legacy engine as ultimate fallback
from backend.modeling.corners_engine import (
    estimate_corners_lambda,
    derive_corner_probabilities as legacy_derive_corner_probabilities,
)

logger = logging.getLogger("sportsbankzu.corners.predictor")

# ─── Projection weights (configurable, versioned) ───
# Weights for TOTAL-scale components (direct, cross, league, pressure) — #104
WEIGHTS = {
    "league_prior": 0.15,
    "direct_estimate": 0.35,
    "cross_estimate": 0.25,
    "pressure_index": 0.10,
    "league_prior_2": 0.15,  # second league anchor for stability
}

# Shrinkage bounds
MIN_SHRINKAGE = 0.05  # strong data → low shrinkage
MAX_SHRINKAGE = 0.60  # weak data → high shrinkage

# ─── Corner Deflation — Per-League from Calibration DB (#052) ───
# Uniform deflation (#043) replaced by per-league factor from calibration.
_DEFAULT_CORNER_FACTOR = 1.0


def _get_corner_factor(league_id: str | None) -> float:
    """Get per-league corner factor from calibration DB."""
    if not league_id:
        return _DEFAULT_CORNER_FACTOR
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        return float(corrections.get("corner_multiplier", {}).get("value", _DEFAULT_CORNER_FACTOR))
    except Exception:
        return _DEFAULT_CORNER_FACTOR


def predict_corners(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_id: str = "",
    league_stats: Optional[Dict[str, Any]] = None,
    footystats_probs: Optional[Dict[str, Any]] = None,
    odds: Optional[Dict[str, Any]] = None,
    include_mistral: bool = False,
) -> Dict[str, Any]:
    """Generate governed corner predictions for a match (v2).

    This is the main entry point. Returns a complete engine output dict.
    """
    result: Dict[str, Any] = {
        "marketFamily": MARKET_FAMILY,
        "engineVersion": ENGINE_VERSION,
        "governed": True,
    }

    # ── Layer A: Data Quality ──
    data_quality = compute_corners_data_quality(
        home_stats, away_stats, league_stats,
    )
    result["data_quality"] = data_quality

    if data_quality["data_quality_tier"] == "INSUFFICIENT":
        # Fallback to legacy for minimal output
        fallback_proj = _fallback_projection(home_stats, away_stats, league_stats)
        result["projection"] = fallback_proj
        result["expected_total_corners"] = fallback_proj["expected_total_corners_ft"]
        result["lines"] = _build_legacy_lines(home_stats, away_stats, league_stats, footystats_probs)
        result["pricing"] = {}
        result["decision"] = {"no_bet": True, "no_bet_reason": "insufficient_data"}
        return result

    # ── Layer B+C: Features + Projection ──
    v2_features = build_v2_match_features(home_stats, away_stats, league_stats)
    pressure_index = compute_matchup_pressure_index(v2_features)
    v2_features["matchup_pressure_index"] = pressure_index

    projection = _project_expected_corners(v2_features, league_id, data_quality)
    result["projection"] = projection

    # ── Load champion model params ──
    alpha = projection.get("alpha", 0.15)
    expected_ft = projection["expected_total_corners_ft"]

    # ── Layer D: Price Ladder ──
    pricing = price_full_ladder(
        expected_ft=expected_ft,
        alpha=alpha,
        odds=odds or {},
        data_quality_tier=data_quality["data_quality_tier"],
        model_divergence=projection.get("model_divergence", 0.0),
    )
    result["pricing"] = pricing

    # ── Build per-line output (backwards compat with v1) ──
    result["lines"] = _build_lines_from_pricing(pricing, league_id)
    result["expected_total_corners"] = round(expected_ft, 2)

    # ── Layer E: Decision ──
    selected = pricing.get("selected", {})
    decision = {**selected}
    decision["reason_codes"] = []

    # ── H2H corner filter: block Over when historical average < threshold ──
    h2h_avg_corners = home_stats.get("h2h_avg_corners")
    league_avg_corners = (league_stats or {}).get("avg_corners_per_match") if league_stats else None
    selected_line = decision.get("line", 9.5)

    if h2h_avg_corners is not None:
        try:
            h2h_avg = float(h2h_avg_corners)
            if h2h_avg < selected_line and decision.get("side") == "OVER":
                decision["no_bet"] = True
                decision["no_bet_reason"] = f"h2h_avg_corners ({h2h_avg:.1f}) < line ({selected_line})"
                decision["reason_codes"].append("H2H_CORNER_FILTER")
                logger.info(f"[Corners] H2H filter blocked Over {selected_line}: avg={h2h_avg:.1f}")
        except (ValueError, TypeError):
            pass

    if league_avg_corners is not None and not decision.get("no_bet"):
        try:
            lg_avg = float(league_avg_corners)
            if lg_avg < selected_line * 0.85 and decision.get("side") == "OVER":
                decision["no_bet"] = True
                decision["no_bet_reason"] = f"league_avg_corners ({lg_avg:.1f}) too low for Over {selected_line}"
                decision["reason_codes"].append("LEAGUE_CORNER_FILTER")
                logger.info(f"[Corners] League filter blocked Over {selected_line}: lg_avg={lg_avg:.1f}")
        except (ValueError, TypeError):
            pass

    # Apply governance gates
    governance_state = _determine_governance_state(league_id, data_quality)
    decision["governance_state"] = governance_state

    if governance_state == "RESTRICTED":
        decision["no_bet"] = True
        decision["no_bet_reason"] = "restricted_market"
        decision["reason_codes"].append("GOVERNANCE_RESTRICTED")
    elif governance_state == "NEUTRAL" and decision.get("edge") is not None:
        # In NEUTRAL, require higher edge
        if (decision.get("edge") or 0) < 0.03:
            decision["no_bet"] = True
            decision["no_bet_reason"] = "edge_insufficient_for_neutral"
            decision["reason_codes"].append("NEUTRAL_EDGE_GATE")

    # ── Mistral review (optional, non-blocking) ──
    if include_mistral and not decision.get("no_bet"):
        try:
            mistral_review = review_corners_with_mistral(result)
            decision = apply_mistral_adjustment(decision, mistral_review)
        except Exception as e:
            logger.warning(f"Mistral review skipped: {e}")
            decision["mistral_review"] = {"recommendation_adjustment": "maintain", "error": str(e)}

    result["decision"] = decision

    return result


def _project_expected_corners(
    features: Dict[str, Any],
    league_id: str,
    data_quality: Dict[str, Any],
) -> Dict[str, Any]:
    """Layer C: Project expected_total_corners FT, 1H, 2H.

    Uses weighted combination of components + dynamic shrinkage.
    """
    league_prior = features.get("league_corner_mean_ft", 10.0)

    # Component contributions — ALL at match-total scale (#104)
    home_attack = features.get("home_corners_for_pm", 0)
    away_attack = features.get("away_corners_for_pm", 0)
    direct = features.get("direct_estimate_ft", home_attack + away_attack)
    cross = features.get("cross_estimate_ft", 0)
    pressure = features.get("matchup_pressure_index", 0)

    if direct > 0:
        raw = (
            WEIGHTS["league_prior"] * league_prior
            + WEIGHTS["direct_estimate"] * direct
            + WEIGHTS["cross_estimate"] * (cross if cross > 0 else direct)
            + WEIGHTS["pressure_index"] * (league_prior + pressure * 1.5)
            + WEIGHTS["league_prior_2"] * league_prior
        )
    else:
        raw = league_prior

    # ── Dynamic shrinkage ──
    shrinkage = _compute_dynamic_shrinkage(features, data_quality)

    expected_ft = shrinkage * league_prior + (1.0 - shrinkage) * raw

    # ── Context risk penalty ──
    risk_penalty = _compute_context_risk_penalty(features, data_quality)
    expected_ft = max(4.0, min(18.0, expected_ft - risk_penalty))

    # ── Get NB alpha from training artifacts or fit from features ──
    alpha = _get_alpha(league_id, expected_ft)

    # ── Model comparison (NB vs Poisson vs ML) ──
    nb_pred = expected_ft  # NB uses our projection as mu
    pois_pred = expected_ft  # Poisson uses same lambda
    ml_pred = _get_ml_prediction(features, league_id)

    predictions = [nb_pred, pois_pred]
    if ml_pred is not None:
        predictions.append(ml_pred)
        # If ML disagrees significantly, blend
        if abs(ml_pred - expected_ft) < 3.0:
            expected_ft = expected_ft * 0.6 + ml_pred * 0.4
        else:
            # Large divergence — trust statistical more
            expected_ft = expected_ft * 0.8 + ml_pred * 0.2

    model_divergence = _compute_divergence(predictions)

    # Apply per-league corner factor from calibration (#052)
    expected_ft = expected_ft * _get_corner_factor(league_id)

    expected_ft = max(4.0, min(18.0, expected_ft))

    # ── FH / 2H decomposition ──
    expected_1h, expected_2h = _decompose_halves(features, expected_ft)

    return {
        "expected_total_corners_ft": round(expected_ft, 2),
        "expected_total_corners_1h": round(expected_1h, 2),
        "expected_total_corners_2h": round(expected_2h, 2),
        "raw_projection": round(raw, 2),
        "shrinkage": round(shrinkage, 4),
        "risk_penalty": round(risk_penalty, 3),
        "alpha": round(alpha, 4),
        "model_divergence": round(model_divergence, 4),
        "nb_prediction": round(nb_pred, 2),
        "poisson_prediction": round(pois_pred, 2),
        "ml_prediction": round(ml_pred, 2) if ml_pred is not None else None,
        "league_prior": round(league_prior, 2),
        "pressure_index": round(features.get("matchup_pressure_index", 0), 4),
        "weights_version": "v2.0",
    }


def _compute_dynamic_shrinkage(
    features: Dict[str, Any],
    data_quality: Dict[str, Any],
) -> float:
    """Compute shrinkage weight toward league mean.

    Higher shrinkage = more trust in league average, less in team-specific.
    """
    sample_adequacy = data_quality.get("sample_adequacy_score", 0.5)
    coverage = data_quality.get("coverage_score", 0.5)
    league_risk = features.get("league_prediction_risk", 50)

    # Base shrinkage from sample quality
    base = 0.5 - (sample_adequacy * 0.3)  # good sample → lower shrinkage

    # Adjust for coverage
    base -= (coverage - 0.5) * 0.2  # good coverage → lower

    # Adjust for league risk
    base += max(0, (league_risk - 50)) / 200.0  # high risk → more shrinkage

    return max(MIN_SHRINKAGE, min(MAX_SHRINKAGE, base))


def _compute_context_risk_penalty(
    features: Dict[str, Any],
    data_quality: Dict[str, Any],
) -> float:
    """Compute penalty to subtract from expected corners for risk factors."""
    penalty = 0.0

    # High prediction risk
    risk = features.get("league_prediction_risk", 50)
    if risk > 70:
        penalty += 0.3
    elif risk > 60:
        penalty += 0.1

    # Low sample
    tier = data_quality.get("data_quality_tier", "MEDIUM")
    if tier == "LOW":
        penalty += 0.2
    elif tier == "INSUFFICIENT":
        penalty += 0.5

    # No corners-against data (less reliable projection)
    if not features.get("_has_against", False):
        penalty += 0.15

    return min(1.0, penalty)


def _get_alpha(league_id: str, expected_ft: float) -> float:
    """Get NB alpha from training artifacts, or estimate."""
    training_meta = load_artifact("corner_training_metadata")
    if training_meta:
        nb_info = training_meta.get("training_results", {}).get("negative_binomial", {})
        if nb_info and nb_info.get("alpha"):
            return max(0.001, min(5.0, nb_info["alpha"]))

    # Default estimation: typical football corner overdispersion
    return 0.15


def _get_ml_prediction(features: Dict[str, Any], league_id: str) -> Optional[float]:
    """Try to get ML model prediction for expected_total_corners."""
    try:
        ml_features = build_match_corner_features(
            features, features, None,
        )
        result = predict_corners_ml(ml_features, league_id)
        if result and "expected_total_corners" in result:
            return result["expected_total_corners"]
    except Exception:
        pass
    return None


def _compute_divergence(predictions: List[float]) -> float:
    """Compute coefficient of variation across model predictions."""
    if len(predictions) < 2:
        return 0.0
    mean = sum(predictions) / len(predictions)
    if mean <= 0:
        return 0.0
    variance = sum((p - mean) ** 2 for p in predictions) / len(predictions)
    return math.sqrt(variance) / mean


def _decompose_halves(
    features: Dict[str, Any],
    expected_ft: float,
) -> tuple:
    """Decompose expected FT into 1H and 2H projections.

    Maintains: expected_1h + expected_2h ≈ expected_ft (within tolerance).
    """
    fh_combined = features.get("combined_fh", 0)
    sh_combined = features.get("combined_2h", 0)
    has_timing = features.get("_has_timing", False)

    if has_timing and fh_combined > 0 and sh_combined > 0:
        total_halves = fh_combined + sh_combined
        scale = expected_ft / total_halves if total_halves > 0 else 1.0
        expected_1h = fh_combined * scale
        expected_2h = sh_combined * scale
    else:
        # Default split: ~45% FH, ~55% 2H (typical football pattern)
        expected_1h = expected_ft * 0.45
        expected_2h = expected_ft * 0.55

    # Ensure consistency
    total = expected_1h + expected_2h
    if abs(total - expected_ft) > 0.1:
        adjustment = expected_ft / total if total > 0 else 1.0
        expected_1h *= adjustment
        expected_2h *= adjustment

    return (max(0, expected_1h), max(0, expected_2h))


def _build_lines_from_pricing(
    pricing: Dict[str, Any],
    league_id: str,
) -> Dict[str, Any]:
    """Build per-line output dict from pricing ladder for backwards compat."""
    lines = {}
    ladder = pricing.get("ladder", [])

    for item in ladder:
        line = item["line"]
        line_key = f"over_{line}"
        lines[line_key] = {
            "line": line,
            "probability": item.get("p_over"),
            "probability_under": item.get("p_under"),
            "fair_over": item.get("fair_over"),
            "fair_under": item.get("fair_under"),
            "book_odd_over": item.get("book_odd_over"),
            "book_odd_under": item.get("book_odd_under"),
            "edge_over": item.get("edge_over_adjusted"),
            "edge_under": item.get("edge_under_adjusted"),
            "champion_model": None,
            "fallback_model": None,
            "model_used": "corners_engine_v2",
            "operational_state": "NEUTRAL",
            "governed": True,
        }

        # Enrich with governance from artifacts if available
        champ_info = get_league_champion(league_id, line)
        if champ_info:
            lines[line_key]["champion_model"] = champ_info.get("champion_model")
            lines[line_key]["fallback_model"] = champ_info.get("fallback_model")

        status_info = get_league_line_status(league_id, line)
        if status_info:
            lines[line_key]["operational_state"] = status_info.get("operational_state", "NEUTRAL")

    return lines


def _determine_governance_state(
    league_id: str,
    data_quality: Dict[str, Any],
) -> str:
    """Determine overall governance state for this prediction."""
    tier = data_quality.get("data_quality_tier", "LOW")

    if tier == "INSUFFICIENT":
        return "RESTRICTED"

    # Check artifact-based state
    decisions = load_artifact("corner_promotion_decisions")
    if decisions:
        league_dec = decisions.get("leagues", {}).get(league_id, {})
        states = []
        for line_data in league_dec.get("lines", {}).values():
            states.append(line_data.get("operational_state", "RESTRICTED"))
        if states:
            # Use the most permissive state across lines
            state_order = ["RESTRICTED", "NEUTRAL", "ACTIVE_GUARDED", "ACTIVE"]
            best = max(states, key=lambda s: state_order.index(s) if s in state_order else 0)
            return best

    # Default based on quality
    if tier == "HIGH":
        return "ACTIVE_GUARDED"
    elif tier == "MEDIUM":
        return "NEUTRAL"
    return "RESTRICTED"


def _fallback_projection(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Minimal projection using legacy engine."""
    expected = estimate_corners_lambda(
        home_stats, away_stats,
        league_stats if isinstance(league_stats, dict) else None,
    )
    return {
        "expected_total_corners_ft": round(expected, 2),
        "expected_total_corners_1h": round(expected * 0.45, 2),
        "expected_total_corners_2h": round(expected * 0.55, 2),
        "alpha": 0.15,
        "model_divergence": 0.0,
        "league_prior": 10.0,
        "weights_version": "legacy_fallback",
    }


def _build_legacy_lines(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]],
    footystats_probs: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build lines dict from legacy engine for fallback."""
    legacy_probs = legacy_derive_corner_probabilities(
        home_stats, away_stats,
        league_stats if isinstance(league_stats, dict) else None,
        footystats_probs,
    )
    lines = {}
    for key, prob in legacy_probs.items():
        lines[key] = {
            "line": float(key.replace("over_", "")),
            "probability": prob,
            "probability_under": round(1.0 - prob, 5) if prob else None,
            "model_used": "legacy_blend",
            "operational_state": "RESTRICTED",
            "governed": False,
        }
    return lines


def get_corner_governance_info(league_id: str) -> Dict[str, Any]:
    """Get full governance info for corners in a league (v2 compatible).

    Returns metadata suitable for frontend display.
    """
    info: Dict[str, Any] = {
        "marketFamily": MARKET_FAMILY,
        "engineVersion": ENGINE_VERSION,
        "league_id": league_id,
        "lines": {},
    }

    registry = load_artifact("corner_model_registry")
    decisions = load_artifact("corner_promotion_decisions")

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        line_info: Dict[str, Any] = {
            "line": line,
            "championModel": "negative_binomial",
            "fallbackModel": "poisson",
            "operationalState": "RESTRICTED",
            "evidenceScore": 0,
            "cornerCalibrationStatus": "uncalibrated",
            "cornerSampleAdequacy": "unknown",
        }

        if registry:
            lr = registry.get("leagues", {}).get(league_id, {}).get("lines", {}).get(line_key, {})
            if lr:
                line_info["championModel"] = lr.get("champion_model", "negative_binomial")
                line_info["fallbackModel"] = lr.get("fallback_model", "poisson")

        if decisions:
            ld = decisions.get("leagues", {}).get(league_id, {}).get("lines", {}).get(line_key, {})
            if ld:
                line_info["operationalState"] = ld.get("operational_state", "RESTRICTED")
                evidence = ld.get("evidence_score", {})
                line_info["evidenceScore"] = evidence.get("total_score", 0)

                cal_score = evidence.get("calibration", 0)
                if cal_score >= 20:
                    line_info["cornerCalibrationStatus"] = "good"
                elif cal_score >= 10:
                    line_info["cornerCalibrationStatus"] = "adequate"
                else:
                    line_info["cornerCalibrationStatus"] = "poor"

                if ld.get("hard_blockers"):
                    line_info["cornerSampleAdequacy"] = "insufficient"
                else:
                    line_info["cornerSampleAdequacy"] = "adequate"

        info["lines"][line_key] = line_info

    meta = load_artifact("corner_training_metadata")
    if meta:
        info["cornerValidationVersion"] = meta.get("model_version", ENGINE_VERSION)
        info["lastRetrained"] = meta.get("generated_at")

    return info
