"""Production inference module for ML predictions.

Loads trained XGBoost models and generates probability predictions
for upcoming matches. Falls back to Poisson-based predictions if ML
models are unavailable or underperform.

Champion/Challenger logic:
    - ML prediction is the "Challenger"
    - Poisson (lambda_calculator) is the "Champion"
    - ML only activates if validation Brier Score < 0.60

Supports two loading modes:
    1. Native XGBoost format (.json) — no sklearn needed (Lambda production)
    2. Pickle format (.pkl) with RF+XGB ensemble — requires sklearn (local dev)
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

try:
    import xgboost as xgb
except ImportError:
    xgb = None  # type: ignore

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"

# Cache loaded models in memory
_model_cache: Dict[str, Dict[str, Any]] = {}

# Track S3 download failures to avoid repeated attempts
_s3_failed: set = set()


def _download_from_s3(league_id: str) -> bool:
    """Download model files from S3 to local disk. Returns True if successful."""
    if league_id in _s3_failed:
        return False

    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        return False

    try:
        import boto3
    except ImportError:
        return False

    # Try native format first (xgb_model.json), then pkl
    files_to_try = ["xgb_model.json", "metadata.json", "rf_model.pkl", "xgb_model.pkl"]

    local_dir = Path("/tmp/.ml_models") / league_id
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        s3 = boto3.client("s3")

        downloaded = []
        for filename in files_to_try:
            s3_key = f".ml_models/{league_id}/{filename}"
            local_path = local_dir / filename
            try:
                s3.download_file(bucket, s3_key, str(local_path))
                downloaded.append(filename)
            except Exception:
                pass

        # Need at least xgb_model.json + metadata.json OR xgb_model.pkl + metadata.json
        has_metadata = "metadata.json" in downloaded
        has_native = "xgb_model.json" in downloaded
        has_pkl = "xgb_model.pkl" in downloaded

        if has_metadata and (has_native or has_pkl):
            logger.info(f"Models downloaded from S3 for {league_id}: {downloaded}")
            return True

        _s3_failed.add(league_id)
        return False

    except Exception as e:
        logger.debug(f"S3 download failed for {league_id}: {e}")
        _s3_failed.add(league_id)
        return False


def _load_xgb_native(model_path: Path) -> Optional[Any]:
    """Load XGBoost model from native JSON format (no sklearn needed)."""
    if xgb is None:
        return None
    try:
        booster = xgb.Booster()
        booster.load_model(str(model_path))
        return booster
    except Exception as e:
        logger.debug(f"Failed to load native XGBoost from {model_path}: {e}")
        return None


def _load_models(league_id: str) -> Optional[Dict[str, Any]]:
    """Load trained models and metadata for a league from disk or S3."""
    if league_id in _model_cache:
        return _model_cache[league_id]

    # Check multiple possible locations
    candidates = [
        _MODELS_DIR / league_id,
        Path("/tmp/.ml_models") / league_id,
    ]

    league_dir = None
    for d in candidates:
        meta = d / "metadata.json"
        has_model = (d / "xgb_model.json").exists() or (d / "xgb_model.pkl").exists()
        if meta.exists() and has_model:
            league_dir = d
            break

    # If not found locally, try downloading from S3
    if league_dir is None:
        if _download_from_s3(league_id):
            league_dir = Path("/tmp/.ml_models") / league_id
        elif league_id != "global":
            return _load_models("global")
        else:
            return None

    try:
        with open(league_dir / "metadata.json", "r") as f:
            metadata = json.load(f)

        feature_names = metadata.get("feature_names", [])
        bundle: Dict[str, Any] = {
            "metadata": metadata,
            "feature_names": feature_names,
            "ensemble_weights": metadata.get("ensemble_weights", {"rf": 0.40, "xgb": 0.60}),
            "mode": "xgb_only",  # default
        }

        # Try native XGBoost format first (no sklearn needed)
        xgb_native_path = league_dir / "xgb_model.json"
        if xgb_native_path.exists():
            booster = _load_xgb_native(xgb_native_path)
            if booster:
                bundle["xgb_booster"] = booster
                bundle["mode"] = "xgb_native"
                logger.info(f"XGBoost native model loaded for {league_id}")

        # Try pickle format (RF + XGB ensemble, requires sklearn)
        rf_path = league_dir / "rf_model.pkl"
        xgb_pkl_path = league_dir / "xgb_model.pkl"
        if rf_path.exists() and xgb_pkl_path.exists():
            try:
                with open(rf_path, "rb") as f:
                    bundle["rf"] = pickle.load(f)
                with open(xgb_pkl_path, "rb") as f:
                    bundle["xgb"] = pickle.load(f)
                bundle["mode"] = "ensemble"
                logger.info(f"Full ensemble (RF+XGB) loaded for {league_id}")
            except Exception as e:
                # sklearn not available — that's OK, use native XGBoost
                logger.debug(f"Pickle load failed for {league_id} (sklearn not available): {e}")

        if bundle.get("mode") == "xgb_only" and "xgb_booster" not in bundle:
            # No model loaded at all
            logger.warning(f"No usable model found for {league_id}")
            if league_id != "global":
                return _load_models("global")
            return None

        _model_cache[league_id] = bundle
        logger.info(
            f"Models loaded for {league_id} (mode={bundle['mode']}, "
            f"trained {metadata.get('trained_at', '?')})"
        )
        return bundle

    except Exception as e:
        logger.error(f"Failed to load models for {league_id}: {e}")
        return None


def is_ml_available(league_id: str) -> bool:
    """Check if ML models are available and validated for a league.

    Checks:
    - Brier < 0.60 (absolute threshold for 3-class)
    - Not explicitly deactivated (Brier >= 0.63, improvement #3)
    - Market efficiency gating (improvement #4): ML only if market is inefficient
    """
    if np is None:
        return False
    bundle = _load_models(league_id)
    if not bundle:
        return False

    meta = bundle.get("metadata", {})

    # Improvement #3: explicit deactivation flag
    if meta.get("ml_deactivated"):
        return False

    val_brier = meta.get("validation_brier")
    if val_brier is None:
        return True  # No validation data = trust the model

    # ML Brier must be < 0.60 (absolute threshold for 3-class)
    if val_brier >= 0.60:
        return False

    # Improvement #4: if market is very efficient AND odds add minimal value,
    # prefer Poisson to avoid just copying the market
    market_eff = meta.get("market_efficiency_r2")
    odds_value = meta.get("odds_value_added")
    if market_eff is not None and market_eff > 0.15:
        if odds_value is not None and abs(odds_value) < 0.01:
            logger.info(
                f"[{league_id}] ML suppressed: market efficient (R²={market_eff}) "
                f"and odds add minimal value (diff={odds_value})"
            )
            return False

    return True


def predict_1x2(
    features: Dict[str, float],
    league_id: str = "global",
) -> Optional[Dict[str, float]]:
    """Generate 1X2 probability prediction using ML.

    Uses full RF+XGB ensemble if sklearn is available,
    otherwise XGBoost-only via native format.
    """
    bundle = _load_models(league_id)
    if not bundle:
        return None

    feature_names = bundle["feature_names"]
    mode = bundle.get("mode", "xgb_only")

    # Build feature vector in correct order
    X = np.array([[features.get(f, 0.0) for f in feature_names]], dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    try:
        if mode == "ensemble" and "rf" in bundle and "xgb" in bundle:
            # Full ensemble: RF (40%) + XGB (60%)
            weights = bundle["ensemble_weights"]
            rf_probs = bundle["rf"].predict_proba(X)[0]
            xgb_probs = bundle["xgb"].predict_proba(X)[0]

            w_rf = weights.get("rf", 0.40)
            w_xgb = weights.get("xgb", 0.60)
            ensemble_probs = (rf_probs * w_rf + xgb_probs * w_xgb) / (w_rf + w_xgb)
            source = "ml_ensemble"

        elif "xgb_booster" in bundle:
            # XGBoost-only via native Booster (no sklearn needed)
            dmatrix = xgb.DMatrix(X, feature_names=feature_names)
            ensemble_probs = bundle["xgb_booster"].predict(dmatrix)[0]
            source = "ml_xgboost"

        else:
            return None

        # Normalize to sum to 1
        total = ensemble_probs.sum()
        if total > 0:
            ensemble_probs = ensemble_probs / total

        return {
            "home_win": round(float(ensemble_probs[0]) * 100, 1),
            "draw": round(float(ensemble_probs[1]) * 100, 1),
            "away_win": round(float(ensemble_probs[2]) * 100, 1),
            "source": source,
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

    Improvement #8: uses dedicated market models (O/U, BTTS) when available,
    falling back to Poisson-derived estimates otherwise.

    Returns dict with all market probabilities (0-100 scale).
    """
    result = {}

    # 1X2 from ML
    p1x2 = predict_1x2(features, league_id)
    if p1x2:
        result["homeWinProb"] = p1x2["home_win"]
        result["drawProb"] = p1x2["draw"]
        result["awayWinProb"] = p1x2["away_win"]
        result["_ml_source"] = p1x2.get("source", "ml")
    else:
        result["_ml_source"] = "fallback_poisson"
        return result

    # Improvement #8: try dedicated market models first
    try:
        from backend.ml.market_models import predict_market as predict_market_model

        market_mapping = {
            # Goals
            "over05": "over05Prob",
            "over15": "over15Prob",
            "over25": "over25Prob",
            "over35": "over35Prob",
            "over45": "over45Prob",
            "btts": "bttsProb",
            # Corners
            "corners_over45": "cornersOver45Prob",
            "corners_over55": "cornersOver55Prob",
            "corners_over65": "cornersOver65Prob",
            "corners_over75": "cornersOver75Prob",
            "corners_over85": "cornersOver85Prob",
            "corners_over95": "cornersOver95Prob",
            "corners_over105": "cornersOver105Prob",
            "corners_over115": "cornersOver115Prob",
            # Cards
            "cards_over05": "cardsOver05Prob",
            "cards_over15": "cardsOver15Prob",
            "cards_over25": "cardsOver25Prob",
            "cards_over35": "cardsOver35Prob",
            "cards_over45": "cardsOver45Prob",
            "cards_over55": "cardsOver55Prob",
        }
        ml_markets_used = []
        for market_key, prob_key in market_mapping.items():
            ml_prob = predict_market_model(features, market_key, league_id)
            if ml_prob is not None:
                result[prob_key] = ml_prob
                ml_markets_used.append(market_key)

        # Derive under from over
        for over_key, under_key in [("over15Prob", "under15Prob"),
                                     ("over35Prob", "under35Prob"),
                                     ("over45Prob", "under45Prob")]:
            if over_key in result and under_key not in result:
                result[under_key] = round(100.0 - result[over_key], 1)

        if ml_markets_used:
            result["_market_source"] = "ml_dedicated"
            logger.debug(f"Used dedicated ML models for markets: {ml_markets_used}")
            # If all key markets covered, return early
            if "over25Prob" in result and "bttsProb" in result:
                return result

    except ImportError:
        pass

    # Fallback: derive Over/Under from goal expectation features via Poisson
    home_goals_avg = features.get("home_goals_scored_avg_r5", 1.3)
    away_goals_avg = features.get("away_goals_scored_avg_r5", 1.0)
    expected_total = home_goals_avg + away_goals_avg

    try:
        from backend.services.math_service import poisson_cdf

        for threshold, key in [(0.5, "over05"), (1.5, "over15"), (2.5, "over25"), (3.5, "over35"), (4.5, "over45")]:
            prob_key = f"{key}Prob"
            if prob_key not in result:  # don't overwrite ML model predictions
                over_prob = 1.0 - poisson_cdf(int(threshold), expected_total)
                result[prob_key] = round(over_prob * 100, 1)

        for threshold, key in [(1.5, "under15"), (3.5, "under35"), (4.5, "under45")]:
            prob_key = f"{key}Prob"
            if prob_key not in result:
                under_prob = poisson_cdf(int(threshold), expected_total)
                result[prob_key] = round(under_prob * 100, 1)

        # Poisson fallback for corners
        home_corners_avg = features.get("home_corners_avg_r5", 4.5)
        away_corners_avg = features.get("away_corners_avg_r5", 4.0)
        expected_corners = home_corners_avg + away_corners_avg
        for threshold in [4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]:
            key = f"cornersOver{str(threshold).replace('.', '')}Prob"
            if key not in result:
                over_prob = 1.0 - poisson_cdf(int(threshold), expected_corners)
                result[key] = round(over_prob * 100, 1)

        # Poisson fallback for cards
        home_cards_avg = features.get("home_cards_avg_r5", 1.8)
        away_cards_avg = features.get("away_cards_avg_r5", 1.8)
        expected_cards = home_cards_avg + away_cards_avg
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            key = f"cardsOver{str(threshold).replace('.', '')}Prob"
            if key not in result:
                over_prob = 1.0 - poisson_cdf(int(threshold), expected_cards)
                result[key] = round(over_prob * 100, 1)

    except ImportError:
        pass

    # BTTS fallback from team-level goal averages
    if "bttsProb" not in result:
        home_score_prob = 1.0 - (2.718 ** (-home_goals_avg))
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
    info = {
        "league_id": league_id,
        "n_samples": meta.get("n_samples"),
        "n_features": meta.get("n_features"),
        "trained_at": meta.get("trained_at"),
        "validation_brier": meta.get("validation_brier"),
        "validation_accuracy": meta.get("validation_accuracy"),
        "validation_ece": meta.get("validation_ece"),
        "ensemble_weights": meta.get("ensemble_weights"),
        "inference_mode": bundle.get("mode", "unknown"),
        "top_features": list(meta.get("rf_importance_top20", {}).keys())[:10],
        "class_distribution": meta.get("class_distribution"),
        "adaptive_params": meta.get("adaptive_params"),
        "ml_deactivated": meta.get("ml_deactivated", False),
        "market_efficiency_r2": meta.get("market_efficiency_r2"),
        "odds_value_added": meta.get("odds_value_added"),
        "no_odds_variant": meta.get("no_odds_variant"),
        "reliability_diagram": meta.get("reliability_diagram"),
    }
    # Remove None values for cleaner output
    return {k: v for k, v in info.items() if v is not None}


def clear_model_cache():
    """Clear in-memory model cache (for retraining scenarios)."""
    _model_cache.clear()
    _s3_failed.clear()
    logger.info("ML model cache cleared")


def champion_vs_challenger(
    poisson_probs: Dict[str, float],
    ml_probs: Optional[Dict[str, float]],
    league_id: str = "global",
) -> Dict[str, float]:
    """Champion/Challenger model selection.

    Returns ML predictions if available and validated, otherwise Poisson.
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

    return {**ml_probs, "_source": ml_probs.get("source", "ml_ensemble")}
