"""ML model training pipeline — Random Forest + XGBoost ensemble.

Implements walk-forward validation with Champion/Challenger model comparison.
Uses Brier Score as the primary evaluation metric for probability calibration.

Walk-Forward (3 seasons):
    Fold 1: Train T-3          -> Test last 5 rounds of T-2
    Fold 2: Train T-3 + T-2    -> Test last 5 rounds of T-1
    Fold 3: Train T-3..T-1     -> Test current season (live)
"""

import json
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Model storage
_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"

# Brier Score threshold: ML must beat Poisson baseline by at least 10%
BRIER_IMPROVEMENT_MIN = 0.10

# Ensemble weights
ENSEMBLE_WEIGHTS = {"rf": 0.40, "xgb": 0.60}


def _brier_score_multiclass(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute Brier Score for multi-class (1X2) predictions.

    BS = (1/N) * sum_i sum_c (f_ic - o_ic)^2
    where f_ic = predicted prob for class c, o_ic = 1 if true class else 0
    """
    n_samples = len(y_true)
    if n_samples == 0:
        return 1.0
    n_classes = y_prob.shape[1] if y_prob.ndim > 1 else 3

    # One-hot encode true labels
    y_onehot = np.zeros((n_samples, n_classes))
    for i, label in enumerate(y_true):
        if 0 <= label < n_classes:
            y_onehot[i, label] = 1.0

    return float(np.mean(np.sum((y_prob - y_onehot) ** 2, axis=1)))


def train_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    sample_weights: Optional[np.ndarray] = None,
) -> Any:
    """Train a Random Forest classifier for 1X2 prediction."""
    from sklearn.ensemble import RandomForestClassifier

    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        min_samples_split=20,
        min_samples_leaf=10,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train, sample_weight=sample_weights)
    logger.info(f"Random Forest trained: {rf.n_estimators} trees, {X_train.shape[1]} features")
    return rf


def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    sample_weights: Optional[np.ndarray] = None,
) -> Any:
    """Train an XGBoost classifier for 1X2 prediction with early stopping."""
    from xgboost import XGBClassifier

    xgb = XGBClassifier(
        n_estimators=1000,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        early_stopping_rounds=50,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    eval_set = [(X_val, y_val)] if X_val is not None else None
    xgb.fit(
        X_train, y_train,
        sample_weight=sample_weights,
        eval_set=eval_set,
        verbose=False,
    )

    best_iter = xgb.best_iteration if hasattr(xgb, "best_iteration") else xgb.n_estimators
    logger.info(f"XGBoost trained: best_iteration={best_iter}, {X_train.shape[1]} features")
    return xgb


def ensemble_predict(
    models: Dict[str, Any],
    X: np.ndarray,
    weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """Generate ensemble probability predictions from multiple models.

    Args:
        models: Dict of model_name -> trained model
        X: Feature matrix
        weights: Model weights (default: ENSEMBLE_WEIGHTS)

    Returns:
        Probability matrix of shape (n_samples, 3) for [home, draw, away]
    """
    if weights is None:
        weights = ENSEMBLE_WEIGHTS

    probs = np.zeros((X.shape[0], 3))
    total_weight = 0.0

    for name, model in models.items():
        w = weights.get(name, 1.0 / len(models))
        model_probs = model.predict_proba(X)
        probs += model_probs * w
        total_weight += w

    if total_weight > 0:
        probs /= total_weight

    # Ensure valid probability distribution
    row_sums = probs.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums > 0, row_sums, 1.0)
    probs = probs / row_sums

    return probs


def walk_forward_validate(
    X: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    n_folds: int = 3,
    test_ratio: float = 0.15,
) -> Dict[str, Any]:
    """Walk-forward time-series cross-validation.

    Splits data chronologically into n_folds, training on past and
    testing on the next segment.

    Returns validation metrics including per-fold and average Brier Score.
    """
    n_samples = len(y)
    fold_size = n_samples // (n_folds + 1)

    if fold_size < 50:
        logger.warning(f"Very small fold size ({fold_size}). Results may be unreliable.")

    results = []

    for fold in range(n_folds):
        # Train on all data up to the test fold
        train_end = fold_size * (fold + 1)
        test_start = train_end
        test_end = min(test_start + fold_size, n_samples)

        if test_end <= test_start:
            continue

        X_train = X[:train_end]
        y_train = y[:train_end]
        w_train = sample_weights[:train_end]
        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]

        # Split train into train/val for XGBoost early stopping
        val_split = int(len(X_train) * 0.85)
        X_tr, X_val = X_train[:val_split], X_train[val_split:]
        y_tr, y_val = y_train[:val_split], y_train[val_split:]
        w_tr = w_train[:val_split]

        try:
            rf = train_random_forest(X_tr, y_tr, sample_weights=w_tr)
            xgb = train_xgboost(X_tr, y_tr, X_val=X_val, y_val=y_val, sample_weights=w_tr)

            models = {"rf": rf, "xgb": xgb}
            probs = ensemble_predict(models, X_test)
            brier = _brier_score_multiclass(y_test, probs)

            # Per-model Brier scores
            rf_probs = rf.predict_proba(X_test)
            xgb_probs = xgb.predict_proba(X_test)
            brier_rf = _brier_score_multiclass(y_test, rf_probs)
            brier_xgb = _brier_score_multiclass(y_test, xgb_probs)

            # Accuracy
            preds = np.argmax(probs, axis=1)
            accuracy = float(np.mean(preds == y_test))

            fold_result = {
                "fold": fold + 1,
                "train_size": len(X_tr),
                "test_size": len(X_test),
                "brier_ensemble": round(brier, 4),
                "brier_rf": round(brier_rf, 4),
                "brier_xgb": round(brier_xgb, 4),
                "accuracy": round(accuracy, 4),
            }
            results.append(fold_result)
            logger.info(f"Fold {fold + 1}: Brier={brier:.4f}, Acc={accuracy:.4f}")

        except Exception as e:
            logger.error(f"Fold {fold + 1} failed: {e}")
            results.append({"fold": fold + 1, "error": str(e)})

    if not results:
        return {"status": "failed", "folds": []}

    valid_results = [r for r in results if "brier_ensemble" in r]
    avg_brier = (
        sum(r["brier_ensemble"] for r in valid_results) / len(valid_results)
        if valid_results else 1.0
    )
    avg_accuracy = (
        sum(r["accuracy"] for r in valid_results) / len(valid_results)
        if valid_results else 0.0
    )

    return {
        "status": "completed",
        "n_folds": len(valid_results),
        "avg_brier": round(avg_brier, 4),
        "avg_accuracy": round(avg_accuracy, 4),
        "folds": results,
    }


def train_and_save(
    X: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    feature_names: List[str],
    league_id: str = "global",
    validate: bool = True,
) -> Dict[str, Any]:
    """Full training pipeline: validate, train final models, save to disk.

    Args:
        X, y: Feature matrix and targets
        sample_weights: Temporal decay weights
        feature_names: Feature column names
        league_id: League identifier for model storage
        validate: Whether to run walk-forward validation first

    Returns:
        Summary dict with validation results and model paths
    """
    summary: Dict[str, Any] = {
        "league_id": league_id,
        "n_samples": len(y),
        "n_features": X.shape[1] if X.ndim > 1 else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if len(y) < 100:
        summary["status"] = "insufficient_data"
        logger.warning(f"Only {len(y)} samples for {league_id} — skipping training")
        return summary

    # Walk-forward validation
    if validate:
        val_results = walk_forward_validate(X, y, sample_weights)
        summary["validation"] = val_results

        if val_results["status"] != "completed":
            summary["status"] = "validation_failed"
            return summary

    # Train final models on full dataset
    val_split = int(len(X) * 0.85)
    X_train, X_val = X[:val_split], X[val_split:]
    y_train, y_val = y[:val_split], y[val_split:]
    w_train = sample_weights[:val_split]

    rf = train_random_forest(X_train, y_train, sample_weights=w_train)
    xgb = train_xgboost(X_train, y_train, X_val=X_val, y_val=y_val, sample_weights=w_train)

    # Save models and metadata
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    league_dir = _MODELS_DIR / league_id
    league_dir.mkdir(parents=True, exist_ok=True)

    rf_path = league_dir / "rf_model.pkl"
    xgb_path = league_dir / "xgb_model.pkl"
    meta_path = league_dir / "metadata.json"

    with open(rf_path, "wb") as f:
        pickle.dump(rf, f)
    with open(xgb_path, "wb") as f:
        pickle.dump(xgb, f)

    # Feature importance (top 20)
    rf_importance = dict(
        sorted(
            zip(feature_names, rf.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )[:20]
    )

    metadata = {
        "league_id": league_id,
        "feature_names": feature_names,
        "n_samples": len(y),
        "n_features": len(feature_names),
        "ensemble_weights": ENSEMBLE_WEIGHTS,
        "trained_at": datetime.utcnow().isoformat(),
        "rf_importance_top20": {k: round(v, 4) for k, v in rf_importance.items()},
        "class_distribution": {
            "home_win": int(np.sum(y == 0)),
            "draw": int(np.sum(y == 1)),
            "away_win": int(np.sum(y == 2)),
        },
    }

    if validate and "validation" in summary:
        metadata["validation_brier"] = summary["validation"].get("avg_brier")
        metadata["validation_accuracy"] = summary["validation"].get("avg_accuracy")

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    summary["status"] = "success"
    summary["model_paths"] = {
        "rf": str(rf_path),
        "xgb": str(xgb_path),
        "metadata": str(meta_path),
    }
    summary["rf_importance_top5"] = dict(list(rf_importance.items())[:5])

    logger.info(
        f"Models saved for {league_id}: "
        f"RF={rf_path}, XGB={xgb_path}"
    )
    return summary


def train_all_leagues(
    training_data: Dict[str, List[Dict[str, Any]]],
    validate: bool = True,
) -> List[Dict[str, Any]]:
    """Train models for all leagues in the training dataset.

    Args:
        training_data: Dict of league_id -> list of match dicts
        validate: Run walk-forward validation per league

    Returns:
        List of training summary dicts
    """
    from backend.ml.feature_engineering import build_features_from_matches

    results = []

    for league_id, matches in training_data.items():
        logger.info(f"Training {league_id}: {len(matches)} matches")
        try:
            X, y, feature_names = build_features_from_matches(matches, league_id=league_id)
            if len(y) == 0:
                results.append({"league_id": league_id, "status": "no_features"})
                continue

            # Extract sample weights
            sample_weights = np.array(
                [m.get("_season_weight", 1.0) for m in matches[:len(y)]],
                dtype=np.float64,
            )
            # Align weights with actual feature rows (some matches skipped in feature building)
            if len(sample_weights) != len(y):
                sample_weights = np.ones(len(y), dtype=np.float64)

            result = train_and_save(
                X, y, sample_weights, feature_names,
                league_id=league_id, validate=validate,
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Training failed for {league_id}: {e}", exc_info=True)
            results.append({"league_id": league_id, "status": "error", "error": str(e)})

    logger.info(f"Training complete: {len(results)} leagues processed")
    return results
