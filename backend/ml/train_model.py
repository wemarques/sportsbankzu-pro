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

# Brier threshold: ML deactivated if avg_brier >= this value
BRIER_DEACTIVATION_THRESHOLD = 0.63

# Adaptive hyperparameters based on sample size (improvement #5)
SMALL_LEAGUE_THRESHOLD = 600  # samples

# Temporal decay: half-life in weeks (improvement #6 v2)
TEMPORAL_DECAY_HALF_LIFE_WEEKS = 26  # ~6 months
MIN_TEMPORAL_WEIGHT = 0.05  # floor to prevent effective sample collapse


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


def _expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Compute Expected Calibration Error (ECE) and reliability diagram data.

    Improvement #7: provides visibility into probability calibration quality.

    Returns dict with:
        - ece: float (0-1, lower is better)
        - bins: list of {avg_confidence, avg_accuracy, count} for reliability diagram
    """
    n_samples = len(y_true)
    if n_samples == 0:
        return {"ece": 1.0, "bins": []}

    # Use the predicted probability of the predicted class
    predicted_class = np.argmax(y_prob, axis=1)
    confidences = np.array([y_prob[i, c] for i, c in enumerate(predicted_class)])
    correctness = (predicted_class == y_true).astype(float)

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bins_data = []

    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        mask = (confidences > lo) & (confidences <= hi)
        count = int(mask.sum())

        if count == 0:
            bins_data.append({"bin_lo": round(lo, 2), "bin_hi": round(hi, 2),
                              "avg_confidence": 0.0, "avg_accuracy": 0.0, "count": 0})
            continue

        avg_conf = float(confidences[mask].mean())
        avg_acc = float(correctness[mask].mean())
        ece += (count / n_samples) * abs(avg_acc - avg_conf)

        bins_data.append({
            "bin_lo": round(lo, 2),
            "bin_hi": round(hi, 2),
            "avg_confidence": round(avg_conf, 4),
            "avg_accuracy": round(avg_acc, 4),
            "count": count,
        })

    return {"ece": round(ece, 4), "bins": bins_data}


def _compute_temporal_weights(
    n_samples: int,
    match_timestamps: Optional[np.ndarray] = None,
    half_life_weeks: float = TEMPORAL_DECAY_HALF_LIFE_WEEKS,
    min_weight: float = MIN_TEMPORAL_WEIGHT,
) -> np.ndarray:
    """Compute temporal decay weights with configurable half-life.

    Improvement #6 v2: uses real match timestamps when available, with
    exponential decay (half-life based) and a minimum weight floor to
    prevent effective sample collapse.

    Args:
        n_samples: Number of samples
        match_timestamps: Unix timestamps per sample (from feature engineering).
            If provided and valid, weeks_ago is computed from real dates.
        half_life_weeks: Half-life for exponential decay (default 26 = ~6 months).
            After half_life_weeks, a sample retains 50% of its weight.
        min_weight: Minimum weight floor before normalization (default 0.05).
    """
    if (
        match_timestamps is not None
        and len(match_timestamps) == n_samples
        and match_timestamps[-1] > 0
    ):
        # Real timestamps: compute actual weeks_ago from most recent match
        most_recent = match_timestamps[-1]
        seconds_ago = most_recent - match_timestamps
        weeks_ago = np.maximum(seconds_ago, 0.0) / (7 * 24 * 3600)
    else:
        # Fallback: ~1 match per team per week across the dataset
        weeks_ago = np.linspace(n_samples / 15, 0, n_samples)

    # Exponential decay: weight = 2^(-weeks_ago / half_life)
    decay_rate = np.log(2) / half_life_weeks
    weights = np.exp(-decay_rate * weeks_ago)

    # Apply minimum weight floor to prevent sample collapse
    weights = np.maximum(weights, min_weight)

    # Normalize so mean weight = 1.0
    weights = weights / weights.mean()
    return weights


def _compute_market_efficiency(
    y_true: np.ndarray,
    implied_probs: Optional[np.ndarray],
) -> Optional[float]:
    """Compute market efficiency as R-squared of implied odds vs outcome.

    Improvement #4: used as gating — ML only activates if market is inefficient.
    Returns R-squared (0-1), or None if implied_probs unavailable.
    Higher R² = more efficient market = less opportunity for ML.
    """
    if implied_probs is None or len(implied_probs) == 0:
        return None

    n_samples = len(y_true)
    n_classes = implied_probs.shape[1] if implied_probs.ndim > 1 else 3

    y_onehot = np.zeros((n_samples, n_classes))
    for i, label in enumerate(y_true):
        if 0 <= label < n_classes:
            y_onehot[i, label] = 1.0

    # Brier of implied odds (market baseline)
    brier_market = float(np.mean(np.sum((implied_probs - y_onehot) ** 2, axis=1)))
    # Brier of uniform baseline (1/3 each)
    brier_uniform = float(np.mean(np.sum((np.full_like(y_onehot, 1.0 / 3) - y_onehot) ** 2, axis=1)))

    if brier_uniform == 0:
        return None

    # R² = 1 - (BS_market / BS_uniform); higher = market captures more info
    r_squared = 1.0 - (brier_market / brier_uniform)
    return round(max(0.0, r_squared), 4)


def _get_adaptive_params(n_samples: int) -> Dict[str, Any]:
    """Return adaptive hyperparameters based on dataset size (improvement #5).

    Smaller leagues get shallower trees to reduce variance.
    """
    if n_samples < SMALL_LEAGUE_THRESHOLD:
        return {
            "rf_max_depth": 8,
            "rf_min_samples_split": 25,
            "rf_min_samples_leaf": 15,
            "xgb_max_depth": 4,
            "xgb_min_child_weight": 8,
        }
    return {
        "rf_max_depth": 12,
        "rf_min_samples_split": 20,
        "rf_min_samples_leaf": 10,
        "xgb_max_depth": 6,
        "xgb_min_child_weight": 5,
    }


def train_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    sample_weights: Optional[np.ndarray] = None,
    n_total_samples: int = 0,
) -> Any:
    """Train a Random Forest classifier for 1X2 prediction."""
    from sklearn.ensemble import RandomForestClassifier

    params = _get_adaptive_params(n_total_samples or len(X_train))

    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=params["rf_max_depth"],
        min_samples_split=params["rf_min_samples_split"],
        min_samples_leaf=params["rf_min_samples_leaf"],
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train, sample_weight=sample_weights)
    logger.info(
        f"Random Forest trained: {rf.n_estimators} trees, {X_train.shape[1]} features, "
        f"max_depth={params['rf_max_depth']}"
    )
    return rf


def train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    sample_weights: Optional[np.ndarray] = None,
    n_total_samples: int = 0,
) -> Any:
    """Train an XGBoost classifier for 1X2 prediction with early stopping."""
    from xgboost import XGBClassifier

    params = _get_adaptive_params(n_total_samples or len(X_train))

    xgb = XGBClassifier(
        n_estimators=1000,
        max_depth=params["xgb_max_depth"],
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=params["xgb_min_child_weight"],
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
    logger.info(
        f"XGBoost trained: best_iteration={best_iter}, {X_train.shape[1]} features, "
        f"max_depth={params['xgb_max_depth']}"
    )
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
    n_total_samples: int = 0,
    match_timestamps: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Walk-forward time-series cross-validation.

    Splits data chronologically into n_folds, training on past and
    testing on the next segment.

    Returns validation metrics including per-fold Brier, ECE, and reliability data.
    """
    n_samples = len(y)
    fold_size = n_samples // (n_folds + 1)
    total = n_total_samples or n_samples

    if fold_size < 50:
        logger.warning(f"Very small fold size ({fold_size}). Results may be unreliable.")

    # Improvement #6 v2: apply temporal decay using real timestamps when available
    temporal_weights = _compute_temporal_weights(n_samples, match_timestamps=match_timestamps)

    results = []
    all_probs = []
    all_y_test = []

    for fold in range(n_folds):
        # Train on all data up to the test fold
        train_end = fold_size * (fold + 1)
        test_start = train_end
        test_end = min(test_start + fold_size, n_samples)

        if test_end <= test_start:
            continue

        X_train = X[:train_end]
        y_train = y[:train_end]
        # Combine original season weights with temporal decay
        w_train = sample_weights[:train_end] * temporal_weights[:train_end]
        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]

        # Split train into train/val for XGBoost early stopping
        val_split = int(len(X_train) * 0.85)
        X_tr, X_val = X_train[:val_split], X_train[val_split:]
        y_tr, y_val = y_train[:val_split], y_train[val_split:]
        w_tr = w_train[:val_split]

        try:
            rf = train_random_forest(X_tr, y_tr, sample_weights=w_tr, n_total_samples=total)
            xgb = train_xgboost(X_tr, y_tr, X_val=X_val, y_val=y_val,
                                sample_weights=w_tr, n_total_samples=total)

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

            # Improvement #7: ECE per fold
            ece_data = _expected_calibration_error(y_test, probs)

            fold_result = {
                "fold": fold + 1,
                "train_size": len(X_tr),
                "test_size": len(X_test),
                "brier_ensemble": round(brier, 4),
                "brier_rf": round(brier_rf, 4),
                "brier_xgb": round(brier_xgb, 4),
                "accuracy": round(accuracy, 4),
                "ece": ece_data["ece"],
            }
            results.append(fold_result)
            all_probs.append(probs)
            all_y_test.append(y_test)
            logger.info(f"Fold {fold + 1}: Brier={brier:.4f}, Acc={accuracy:.4f}, ECE={ece_data['ece']:.4f}")

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
    avg_ece = (
        sum(r["ece"] for r in valid_results) / len(valid_results)
        if valid_results else 1.0
    )

    # Improvement #7: aggregate reliability diagram across all folds
    reliability_diagram = {}
    if all_probs and all_y_test:
        combined_probs = np.concatenate(all_probs, axis=0)
        combined_y = np.concatenate(all_y_test, axis=0)
        reliability_diagram = _expected_calibration_error(combined_y, combined_probs)

    return {
        "status": "completed",
        "n_folds": len(valid_results),
        "avg_brier": round(avg_brier, 4),
        "avg_accuracy": round(avg_accuracy, 4),
        "avg_ece": round(avg_ece, 4),
        "reliability_diagram": reliability_diagram.get("bins", []),
        "folds": results,
    }


def _train_no_odds_variant(
    X: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    feature_names: List[str],
    n_total_samples: int = 0,
    match_timestamps: Optional[np.ndarray] = None,
) -> Optional[Dict[str, Any]]:
    """Train a variant without implied odds features (improvement #1).

    Returns validation Brier score for comparison, or None on failure.
    """
    from backend.ml.feature_engineering import ODDS_FEATURES

    odds_indices = [i for i, f in enumerate(feature_names) if f in ODDS_FEATURES]
    if not odds_indices:
        return None  # no odds features to remove

    keep_indices = [i for i in range(len(feature_names)) if i not in odds_indices]
    X_no_odds = X[:, keep_indices]

    try:
        val_results = walk_forward_validate(
            X_no_odds, y, sample_weights, n_total_samples=n_total_samples,
            match_timestamps=match_timestamps,
        )
        if val_results["status"] == "completed":
            return {
                "avg_brier": val_results["avg_brier"],
                "avg_accuracy": val_results["avg_accuracy"],
                "avg_ece": val_results.get("avg_ece"),
                "n_features": len(keep_indices),
                "removed_features": [feature_names[i] for i in odds_indices],
            }
    except Exception as e:
        logger.warning(f"No-odds variant failed: {e}")

    return None


def train_and_save(
    X: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    feature_names: List[str],
    league_id: str = "global",
    validate: bool = True,
    match_timestamps: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Full training pipeline: validate, train final models, save to disk.

    Includes improvements #1-7:
    - #1: No-odds variant comparison
    - #3: Auto-deactivation for high Brier leagues
    - #4: Market efficiency gating
    - #5: Adaptive hyperparameters
    - #6: Temporal decay weights
    - #7: ECE and reliability diagram
    """
    n_total = len(y)
    summary: Dict[str, Any] = {
        "league_id": league_id,
        "n_samples": n_total,
        "n_features": X.shape[1] if X.ndim > 1 else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if n_total < 100:
        summary["status"] = "insufficient_data"
        logger.warning(f"Only {n_total} samples for {league_id} — skipping training")
        return summary

    # Walk-forward validation
    if validate:
        val_results = walk_forward_validate(
            X, y, sample_weights, n_total_samples=n_total,
            match_timestamps=match_timestamps,
        )
        summary["validation"] = val_results

        if val_results["status"] != "completed":
            summary["status"] = "validation_failed"
            return summary

        # Improvement #3: auto-deactivation for high Brier leagues
        avg_brier = val_results.get("avg_brier", 1.0)
        if avg_brier >= BRIER_DEACTIVATION_THRESHOLD:
            summary["ml_deactivated"] = True
            summary["deactivation_reason"] = (
                f"avg_brier={avg_brier:.4f} >= threshold={BRIER_DEACTIVATION_THRESHOLD}"
            )
            logger.warning(
                f"[{league_id}] ML deactivated: Brier {avg_brier:.4f} >= {BRIER_DEACTIVATION_THRESHOLD}"
            )

        # Improvement #1: train no-odds variant and compare
        no_odds = _train_no_odds_variant(
            X, y, sample_weights, feature_names, n_total,
            match_timestamps=match_timestamps,
        )
        if no_odds:
            summary["no_odds_variant"] = no_odds
            brier_diff = avg_brier - no_odds["avg_brier"]
            summary["odds_value_added"] = round(brier_diff, 4)
            if abs(brier_diff) < 0.03:
                logger.info(
                    f"[{league_id}] Odds add marginal value: "
                    f"with_odds={avg_brier:.4f}, without={no_odds['avg_brier']:.4f}, "
                    f"diff={brier_diff:.4f}"
                )

        # Improvement #4: market efficiency
        odds_cols = ["implied_odds_ft_1", "implied_odds_ft_x", "implied_odds_ft_2"]
        odds_indices = [i for i, f in enumerate(feature_names) if f in odds_cols]
        if len(odds_indices) == 3:
            implied_probs = X[:, odds_indices].copy()
            # Normalize implied probabilities (they're in 0-100 scale from feature eng)
            row_sums = implied_probs.sum(axis=1, keepdims=True)
            row_sums = np.where(row_sums > 0, row_sums, 1.0)
            implied_probs = implied_probs / row_sums
            market_eff = _compute_market_efficiency(y, implied_probs)
            if market_eff is not None:
                summary["market_efficiency_r2"] = market_eff
                # If market is very efficient (R² > 0.15), flag it
                if market_eff > 0.15:
                    summary["market_efficient"] = True
                    logger.info(
                        f"[{league_id}] Market is efficient (R²={market_eff:.4f}). "
                        f"ML may not add value."
                    )

    # Train final models on full dataset with temporal decay
    temporal_weights = _compute_temporal_weights(n_total, match_timestamps=match_timestamps)
    combined_weights = sample_weights * temporal_weights

    val_split = int(len(X) * 0.85)
    X_train, X_val = X[:val_split], X[val_split:]
    y_train, y_val = y[:val_split], y[val_split:]
    w_train = combined_weights[:val_split]

    rf = train_random_forest(X_train, y_train, sample_weights=w_train, n_total_samples=n_total)
    xgb = train_xgboost(X_train, y_train, X_val=X_val, y_val=y_val,
                         sample_weights=w_train, n_total_samples=n_total)

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

    # Save XGBoost in native JSON format (loads without sklearn on Lambda)
    xgb_native_path = league_dir / "xgb_model.json"
    xgb.get_booster().save_model(str(xgb_native_path))

    # Feature importance (top 20)
    rf_importance = dict(
        sorted(
            zip(feature_names, rf.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )[:20]
    )

    # Adaptive params used (for traceability)
    adaptive_params = _get_adaptive_params(n_total)

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
        "adaptive_params": adaptive_params,
    }

    if validate and "validation" in summary:
        metadata["validation_brier"] = summary["validation"].get("avg_brier")
        metadata["validation_accuracy"] = summary["validation"].get("avg_accuracy")
        metadata["validation_ece"] = summary["validation"].get("avg_ece")
        metadata["reliability_diagram"] = summary["validation"].get("reliability_diagram", [])
        # Improvement #3: persist deactivation status
        if summary.get("ml_deactivated"):
            metadata["ml_deactivated"] = True
            metadata["deactivation_reason"] = summary.get("deactivation_reason", "")
        # Improvement #1: no-odds comparison
        if summary.get("no_odds_variant"):
            metadata["no_odds_variant"] = summary["no_odds_variant"]
            metadata["odds_value_added"] = summary.get("odds_value_added")
        # Improvement #4: market efficiency
        if summary.get("market_efficiency_r2") is not None:
            metadata["market_efficiency_r2"] = summary["market_efficiency_r2"]

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
            X, y, feature_names, timestamps = build_features_from_matches(matches, league_id=league_id)
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
                match_timestamps=timestamps,
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Training failed for {league_id}: {e}", exc_info=True)
            results.append({"league_id": league_id, "status": "error", "error": str(e)})

    logger.info(f"Training complete: {len(results)} leagues processed")
    return results
