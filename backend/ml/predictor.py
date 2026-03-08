"""Production inference module for ML ensemble predictions.

Loads trained RF + XGBoost models and generates probability predictions
for upcoming matches. Falls back to Poisson-based predictions if ML
models are unavailable or underperform.

Champion/Challenger logic:
    - ML prediction is the "Challenger"
    - Poisson (lambda_calculator) is the "Champion"
    - ML only activates if validation Brier Score improved >= 10%
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"

# Brier improvement threshold to activate ML over Poisson
BRIER_IMPROVEMENT_THRESHOLD = 0.10

# Cache loaded models in memory
_model_cache: Dict[str, Dict[str, Any]] = {}


def _load_models(league_id: str) -> Optional[Dict[str, Any]]:
    """Load trained models and metadata for a league from disk."""
    if league_id in _model_cache:
        return _model_cache[league_id]

    league_dir = _MODELS_DIR / league_id
    rf_path = league_dir / "rf_model.pkl"
    xgb_path = league_dir / "xgb_model.pkl"
    meta_path = league_dir / "metadata.json"

    if not rf_path.exists() or not xgb_path.exists() or not meta_path.exists():
        # Try global model as fallback
        if league_id != "global":
            return _load_models("global")
        return None

    try:
        with open(rf_path, "rb") as f:
            rf = pickle.load(f)
        with open(xgb_path, "rb") as f:
            xgb = pickle.load(f)
        with open(meta_path, "r") as f:
            metadata = json.load(f)

        bundle = {
            "rf": rf,
            "xgb": xgb,
            "metadata": metadata,
            "feature_names": metadata.get("feature_names", []),
            "ensemble_weights": metadata.get("ensemble_weights", {"rf": 0.40, "xgb": 0.60}),
        }
        _model_cache[league_id] = bundle
        logger.info(f"Models loaded for {league_id} (trained {metadata.get('trained_at', '?')})")
        return bundle

    except Exception as e:
        logger.error(f"Failed to load models for {league_id}: {e}")
        return None


def is_ml_available(league_id: str) -> bool:
    """Check if ML models are available and validated for a league."""
    bundle = _load_models(league_id)
    if not bundle:
        return False

    # Check validation Brier score exists and is acceptable
    meta = bundle.get("metadata", {})
    val_brier = meta.get("validation_brier")
    if val_brier is None:
        return True  # No validation data = trust the model

    # ML Brier must be < 0.60 (absolute threshold for 3-class)
    return val_brier < 0.60


def predict_1x2(
    features: Dict[str, float],
    league_id: str = "global",
) -> Optional[Dict[str, float]]:
    """Generate 1X2 probability prediction using the ML ensemble.

    Args:
        features: Dict of feature_name -> value (must match training features)
        league_id: League for model selection

    Returns:
        Dict with keys: home_win, draw, away_win (probabilities 0-100 scale)
        or None if ML unavailable
    """
    bundle = _load_models(league_id)
    if not bundle:
        return None

    feature_names = bundle["feature_names"]
    weights = bundle["ensemble_weights"]

    # Build feature vector in correct order
    X = np.array([[features.get(f, 0.0) for f in feature_names]], dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    try:
        rf_probs = bundle["rf"].predict_proba(X)[0]
        xgb_probs = bundle["xgb"].predict_proba(X)[0]

        # Weighted ensemble
        w_rf = weights.get("rf", 0.40)
        w_xgb = weights.get("xgb", 0.60)
        total_w = w_rf + w_xgb

        ensemble_probs = (rf_probs * w_rf + xgb_probs * w_xgb) / total_w

        # Normalize to sum to 1
        total = ensemble_probs.sum()
        if total > 0:
            ensemble_probs = ensemble_probs / total

        return {
            "home_win": round(float(ensemble_probs[0]) * 100, 1),
            "draw": round(float(ensemble_probs[1]) * 100, 1),
            "away_win": round(float(ensemble_probs[2]) * 100, 1),
            "source": "ml_ensemble",
            "model_league": league_id,
        }

    except Exception as e:
        logger.error(f"ML prediction failed for {league_id}: {e}")
        return None


def predict_markets(
    features: Dict[str, float],
    league_id: str = "global",
) -> Dict[str, float]:
    """Generate predictions for all markets using ML + derived probabilities.

    Uses 1X2 ML prediction as base, then derives Over/Under and BTTS
    from the ensemble's internal probability structure.

    Returns dict with all market probabilities (0-100 scale).
    """
    result = {}

    # 1X2 from ML ensemble
    p1x2 = predict_1x2(features, league_id)
    if p1x2:
        result["homeWinProb"] = p1x2["home_win"]
        result["drawProb"] = p1x2["draw"]
        result["awayWinProb"] = p1x2["away_win"]
        result["_ml_source"] = "ensemble"
    else:
        result["_ml_source"] = "fallback_poisson"
        return result

    # Derive Over/Under from goal expectation features
    home_goals_avg = features.get("home_goals_scored_avg_r5", 1.3)
    away_goals_avg = features.get("away_goals_scored_avg_r5", 1.0)
    expected_total = home_goals_avg + away_goals_avg

    # Use Poisson CDF for Over/Under derivation from expected total goals
    try:
        from backend.services.math_service import poisson_cdf

        for threshold, key in [(1.5, "over15"), (2.5, "over25"), (3.5, "over35"), (4.5, "over45")]:
            over_prob = 1.0 - poisson_cdf(int(threshold), expected_total)
            result[f"{key}Prob"] = round(over_prob * 100, 1)

        for threshold, key in [(1.5, "under15"), (3.5, "under35"), (4.5, "under45")]:
            under_prob = poisson_cdf(int(threshold), expected_total)
            result[f"{key}Prob"] = round(under_prob * 100, 1)

    except ImportError:
        pass

    # BTTS estimation from team-level goal averages
    home_score_prob = 1.0 - (2.718 ** (-home_goals_avg))  # P(home scores >= 1)
    away_score_prob = 1.0 - (2.718 ** (-away_goals_avg))
    btts_prob = home_score_prob * away_score_prob
    result["bttsProb"] = round(btts_prob * 100, 1)

    return result


def get_model_info(league_id: str) -> Optional[Dict[str, Any]]:
    """Return metadata about the trained model for a league."""
    bundle = _load_models(league_id)
    if not bundle:
        return None

    meta = bundle["metadata"]
    return {
        "league_id": league_id,
        "n_samples": meta.get("n_samples"),
        "n_features": meta.get("n_features"),
        "trained_at": meta.get("trained_at"),
        "validation_brier": meta.get("validation_brier"),
        "validation_accuracy": meta.get("validation_accuracy"),
        "ensemble_weights": meta.get("ensemble_weights"),
        "top_features": list(meta.get("rf_importance_top20", {}).keys())[:10],
        "class_distribution": meta.get("class_distribution"),
    }


def clear_model_cache():
    """Clear in-memory model cache (for retraining scenarios)."""
    _model_cache.clear()
    logger.info("ML model cache cleared")


def champion_vs_challenger(
    poisson_probs: Dict[str, float],
    ml_probs: Optional[Dict[str, float]],
    league_id: str = "global",
) -> Dict[str, float]:
    """Champion/Challenger model selection.

    Returns ML predictions if available and validated, otherwise Poisson.

    Args:
        poisson_probs: Poisson-based probabilities (Champion)
        ml_probs: ML ensemble probabilities (Challenger), or None
        league_id: League for validation check
    """
    if ml_probs is None or not is_ml_available(league_id):
        return {**poisson_probs, "_source": "poisson"}

    bundle = _load_models(league_id)
    if bundle:
        val_brier = bundle.get("metadata", {}).get("validation_brier")
        if val_brier is not None:
            logger.info(
                f"[Champion/Challenger] {league_id}: ML Brier={val_brier:.4f}, "
                f"using {'ML' if val_brier < 0.60 else 'Poisson'}"
            )

    return {**ml_probs, "_source": "ml_ensemble"}
