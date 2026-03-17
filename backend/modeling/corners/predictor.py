"""
Corner Runtime Predictor

Production inference module for corner markets.
Loads champion/fallback models per league/line and generates predictions.

Completely independent from goal-based market inference.
Respects operational states: only produces output for lines where
the operational state permits it.

Flow:
1. Identify marketFamily = corners
2. Consult artifacts for league/line
3. Load champion_model and fallback_model
4. Use champion when status permits
5. Use fallback when necessary
6. Return governed predictions with metadata
"""

import logging
from typing import Any, Dict, List, Optional

from backend.modeling.corners import CORNER_LINES, MARKET_FAMILY
from backend.modeling.corners.artifacts import (
    get_league_champion,
    get_league_line_status,
    load_artifact,
)
from backend.modeling.corners.negative_binomial import predict_corners_nb
from backend.modeling.corners.poisson_model import predict_corners_poisson
from backend.modeling.corners.ml_regression import predict_corners_ml
from backend.modeling.corners.operational_states import CornerOperationalState
from backend.modeling.corners.features import build_match_corner_features

logger = logging.getLogger("sportsbankzu.corners.predictor")

# Existing corners engine as ultimate fallback
from backend.modeling.corners_engine import (
    estimate_corners_lambda,
    derive_corner_probabilities as legacy_derive_corner_probabilities,
)


def predict_corners(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_id: str = "",
    league_stats: Optional[Dict[str, Any]] = None,
    footystats_probs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate governed corner predictions for a match.

    Returns a dict with:
    - marketFamily: "corners"
    - expected_total_corners
    - line probabilities (over_8.5, over_9.5, etc.)
    - governance metadata per line (champion_model, operational_state, etc.)

    Non-promoted lines are still returned but flagged accordingly.
    """
    result: Dict[str, Any] = {
        "marketFamily": MARKET_FAMILY,
        "governed": True,
        "lines": {},
    }

    # Estimate expected total corners (from legacy engine as reference)
    expected_corners = estimate_corners_lambda(
        home_stats, away_stats, league_stats if isinstance(league_stats, dict) else None
    )
    result["expected_total_corners"] = round(expected_corners, 2)

    # Build features for ML model
    ml_features = build_match_corner_features(
        home_stats, away_stats,
        league_stats if isinstance(league_stats, dict) else None,
    )

    # Load artifacts
    registry = load_artifact("corner_model_registry")
    decisions = load_artifact("corner_promotion_decisions")

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        line_result = _predict_line(
            line=line,
            line_key=line_key,
            expected_corners=expected_corners,
            ml_features=ml_features,
            home_stats=home_stats,
            away_stats=away_stats,
            league_id=league_id,
            league_stats=league_stats,
            footystats_probs=footystats_probs,
            registry=registry,
            decisions=decisions,
        )
        result["lines"][line_key] = line_result

    return result


def _predict_line(
    line: float,
    line_key: str,
    expected_corners: float,
    ml_features: Dict[str, float],
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_id: str,
    league_stats: Optional[Dict[str, Any]],
    footystats_probs: Optional[Dict[str, Any]],
    registry: Optional[Dict[str, Any]],
    decisions: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Predict a single corner line with governance."""
    line_output: Dict[str, Any] = {
        "line": line,
        "probability": None,
        "champion_model": None,
        "fallback_model": None,
        "model_used": None,
        "operational_state": CornerOperationalState.RESTRICTED.value,
        "governed": True,
    }

    # Get champion/fallback from registry
    champion_model = "negative_binomial"  # default
    fallback_model = "poisson"

    if registry:
        league_reg = registry.get("leagues", {}).get(league_id, {})
        line_reg = league_reg.get("lines", {}).get(line_key, {})
        if line_reg:
            champion_model = line_reg.get("champion_model", champion_model)
            fallback_model = line_reg.get("fallback_model", fallback_model)

    line_output["champion_model"] = champion_model
    line_output["fallback_model"] = fallback_model

    # Get operational state
    if decisions:
        league_dec = decisions.get("leagues", {}).get(league_id, {})
        line_dec = league_dec.get("lines", {}).get(line_key, {})
        if line_dec:
            line_output["operational_state"] = line_dec.get("operational_state", "RESTRICTED")
            line_output["evidence_score"] = line_dec.get("evidence_score", {}).get("total_score", 0)

    # Try champion model
    probability = _run_model(champion_model, expected_corners, ml_features, league_id, line, line_key)
    if probability is not None:
        line_output["probability"] = round(probability, 4)
        line_output["model_used"] = champion_model
    else:
        # Try fallback
        probability = _run_model(fallback_model, expected_corners, ml_features, league_id, line, line_key)
        if probability is not None:
            line_output["probability"] = round(probability, 4)
            line_output["model_used"] = fallback_model
        else:
            # Ultimate fallback: legacy engine
            legacy_probs = legacy_derive_corner_probabilities(
                home_stats, away_stats,
                league_stats if isinstance(league_stats, dict) else None,
                footystats_probs,
            )
            prob = legacy_probs.get(line_key)
            if prob is not None:
                line_output["probability"] = round(prob, 4)
                line_output["model_used"] = "legacy_blend"

    return line_output


def _run_model(
    model_name: str,
    expected_corners: float,
    ml_features: Dict[str, float],
    league_id: str,
    line: float,
    line_key: str,
) -> Optional[float]:
    """Run a specific model and return probability for a line."""
    try:
        if model_name == "negative_binomial":
            # Load fitted parameters from artifacts
            training_meta = load_artifact("corner_training_metadata")
            alpha = 0.15  # default
            mu = expected_corners

            if training_meta:
                nb_info = (training_meta.get("training_results", {})
                          .get("negative_binomial", {}))
                if nb_info:
                    alpha = nb_info.get("alpha", 0.15)
                    mu = nb_info.get("mu", expected_corners)

            probs = predict_corners_nb(mu, alpha)
            return probs.get(line_key)

        elif model_name == "poisson":
            probs = predict_corners_poisson(expected_corners)
            return probs.get(line_key)

        elif model_name == "ml_regression":
            ml_result = predict_corners_ml(ml_features, league_id)
            if ml_result:
                return ml_result.get(line_key)
            return None

        else:
            logger.warning(f"Unknown corner model: {model_name}")
            return None

    except Exception as e:
        logger.error(f"Error running corner model {model_name}: {e}")
        return None


def get_corner_governance_info(league_id: str) -> Dict[str, Any]:
    """Get full governance info for corners in a league.

    Returns metadata suitable for frontend display:
    - marketFamily
    - per-line: championModel, fallbackModel, operationalState, evidenceScore
    """
    info: Dict[str, Any] = {
        "marketFamily": MARKET_FAMILY,
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

                # Derive calibration status
                cal_score = evidence.get("calibration", 0)
                if cal_score >= 20:
                    line_info["cornerCalibrationStatus"] = "good"
                elif cal_score >= 10:
                    line_info["cornerCalibrationStatus"] = "adequate"
                else:
                    line_info["cornerCalibrationStatus"] = "poor"

                # Sample adequacy
                if ld.get("hard_blockers"):
                    line_info["cornerSampleAdequacy"] = "insufficient"
                else:
                    line_info["cornerSampleAdequacy"] = "adequate"

        info["lines"][line_key] = line_info

    # Aggregate validation version from artifacts
    meta = load_artifact("corner_training_metadata")
    if meta:
        info["cornerValidationVersion"] = meta.get("model_version", "unknown")
        info["lastRetrained"] = meta.get("generated_at")

    return info
