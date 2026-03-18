"""
ML Regression Model for Corner Predictions (Supervised Candidate)

Predicts expected_total_corners directly from features using
gradient boosting regression (XGBoost / sklearn).

The predicted value is then converted to line probabilities using
the fitted Negative Binomial distribution parameters from the same
training data (alpha parameter captures overdispersion).

Method for converting regression prediction to line probabilities:
1. Train regressor to predict expected_total_corners
2. From training data, estimate alpha (overdispersion) via method of moments
3. At inference: use NB(mu=predicted_value, alpha=estimated_alpha) to derive
   P(X > line) for each corner line

This ensures the regression prediction integrates smoothly with the
statistical framework while allowing the ML model to capture nonlinear
feature interactions that count models cannot.
"""

import logging
import math
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.modeling.corners import CORNER_LINES, CORNER_LINES_LEGACY
from backend.modeling.corners.negative_binomial import nb_cdf, fit_negative_binomial

logger = logging.getLogger("sportsbankzu.corners.ml_regression")

_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".corner_models"


def train_corner_regressor(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    league_id: str = "",
    n_folds: int = 3,
) -> Dict[str, Any]:
    """Train ML regression model for expected_total_corners.

    Uses XGBoost regressor with walk-forward validation.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Target vector (total corners per match)
        feature_names: Feature column names
        league_id: League identifier
        n_folds: Number of walk-forward folds

    Returns:
        Training summary dict with model metrics.
    """
    from sklearn.ensemble import GradientBoostingRegressor

    n_samples = len(y)
    if n_samples < 30:
        return {
            "model": "ml_regression",
            "league_id": league_id,
            "status": "insufficient_data",
            "sample_size": n_samples,
        }

    # Estimate alpha from training data for probability conversion
    _, alpha = fit_negative_binomial(y)

    # Walk-forward validation
    fold_size = n_samples // (n_folds + 1)
    fold_results = []
    all_preds = []
    all_actuals = []

    for fold in range(n_folds):
        train_end = fold_size * (fold + 1)
        test_start = train_end
        test_end = min(test_start + fold_size, n_samples)

        if test_end <= test_start:
            continue

        X_train, y_train = X[:train_end], y[:train_end]
        X_test, y_test = X[test_start:test_end], y[test_start:test_end]

        try:
            model = GradientBoostingRegressor(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=10,
                random_state=42,
            )
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            preds = np.clip(preds, 4.0, 18.0)

            mae = float(np.mean(np.abs(preds - y_test)))
            rmse = float(np.sqrt(np.mean((preds - y_test) ** 2)))

            # Brier score per line (using NB conversion)
            line_briers = {}
            for line in CORNER_LINES:
                pred_probs = np.array([
                    1.0 - nb_cdf(int(line), max(4.0, p), alpha) for p in preds
                ])
                actuals = (y_test > line).astype(float)
                brier = float(np.mean((pred_probs - actuals) ** 2))
                line_briers[f"over_{line}"] = round(brier, 6)

            fold_results.append({
                "fold": fold + 1,
                "train_size": len(X_train),
                "test_size": len(X_test),
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "line_briers": line_briers,
            })

            all_preds.extend(preds.tolist())
            all_actuals.extend(y_test.tolist())

        except Exception as e:
            logger.error(f"ML regression fold {fold + 1} failed: {e}")
            fold_results.append({"fold": fold + 1, "error": str(e)})

    if not fold_results or all(f.get("error") for f in fold_results):
        return {
            "model": "ml_regression",
            "league_id": league_id,
            "status": "training_failed",
            "sample_size": n_samples,
        }

    # Aggregate metrics
    valid_folds = [f for f in fold_results if "mae" in f]
    avg_mae = np.mean([f["mae"] for f in valid_folds]) if valid_folds else 999.0
    avg_rmse = np.mean([f["rmse"] for f in valid_folds]) if valid_folds else 999.0

    # Aggregate line Brier scores
    line_metrics = {}
    for line in CORNER_LINES:
        key = f"over_{line}"
        briers = [f["line_briers"][key] for f in valid_folds if key in f.get("line_briers", {})]
        if briers:
            line_metrics[key] = {
                "avg_brier": round(float(np.mean(briers)), 6),
                "sample_size": n_samples,
            }

    avg_brier = float(np.mean([m["avg_brier"] for m in line_metrics.values()])) if line_metrics else 1.0

    # Train final model on all data
    final_model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=10,
        random_state=42,
    )
    final_model.fit(X, y)

    # Feature importance
    importances = dict(
        sorted(
            zip(feature_names, final_model.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )[:15]
    )

    # Save model
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    league_dir = _MODELS_DIR / (league_id or "global")
    league_dir.mkdir(parents=True, exist_ok=True)

    model_path = league_dir / "corner_regressor.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": final_model,
            "alpha": alpha,
            "feature_names": feature_names,
            "league_id": league_id,
        }, f)

    return {
        "model": "ml_regression",
        "league_id": league_id,
        "status": "trained",
        "sample_size": n_samples,
        "alpha": round(alpha, 4),
        "avg_mae": round(float(avg_mae), 4),
        "avg_rmse": round(float(avg_rmse), 4),
        "avg_brier": round(avg_brier, 6),
        "line_metrics": line_metrics,
        "feature_importance_top10": {k: round(v, 4) for k, v in list(importances.items())[:10]},
        "folds": fold_results,
        "model_path": str(model_path),
    }


def predict_corners_ml(
    features: Dict[str, float],
    league_id: str = "",
) -> Optional[Dict[str, float]]:
    """Predict corner line probabilities using trained ML regression model.

    Returns None if model unavailable.
    """
    league_dir = _MODELS_DIR / (league_id or "global")
    model_path = league_dir / "corner_regressor.pkl"

    if not model_path.exists():
        # Try global fallback
        if league_id and league_id != "global":
            return predict_corners_ml(features, league_id="global")
        return None

    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)

        model = bundle["model"]
        alpha = bundle["alpha"]
        feature_names = bundle["feature_names"]

        X = np.array([[features.get(f, 0.0) for f in feature_names]], dtype=np.float64)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        predicted_corners = float(model.predict(X)[0])
        predicted_corners = max(4.0, min(18.0, predicted_corners))

        # Convert to line probabilities via NB distribution (full ladder)
        result = {"expected_total_corners": predicted_corners}
        for line in CORNER_LINES:
            threshold = int(line)
            p_under = nb_cdf(threshold, predicted_corners, alpha)
            p_over = 1.0 - p_under
            result[f"over_{line}"] = max(0.0, min(1.0, p_over))
            result[f"under_{line}"] = max(0.0, min(1.0, p_under))

        return result

    except Exception as e:
        logger.error(f"ML corner prediction failed for {league_id}: {e}")
        return None


def get_ml_model_info(league_id: str = "") -> Optional[Dict[str, Any]]:
    """Return metadata about the trained corner ML model."""
    league_dir = _MODELS_DIR / (league_id or "global")
    model_path = league_dir / "corner_regressor.pkl"

    if not model_path.exists():
        return None

    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        return {
            "league_id": bundle.get("league_id", league_id),
            "alpha": bundle.get("alpha"),
            "n_features": len(bundle.get("feature_names", [])),
        }
    except Exception:
        return None
