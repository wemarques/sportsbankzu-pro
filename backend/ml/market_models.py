"""ML models for Over/Under and BTTS market predictions.

Extends the 1X2 ensemble with dedicated models for:
    - Over/Under 1.5, 2.5, 3.5, 4.5 goals
    - BTTS (Both Teams To Score)

Uses the same feature engineering pipeline but with binary classification
targets instead of 3-class.
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"

# Market definitions: (market_name, target_extractor_fn_name)
MARKET_CONFIGS = {
    "over15": {"threshold": 1.5, "description": "Over 1.5 goals"},
    "over25": {"threshold": 2.5, "description": "Over 2.5 goals"},
    "over35": {"threshold": 3.5, "description": "Over 3.5 goals"},
    "over45": {"threshold": 4.5, "description": "Over 4.5 goals"},
    "btts": {"threshold": None, "description": "Both Teams To Score"},
}


def _extract_market_target(
    match: Dict[str, Any],
    market: str,
) -> Optional[int]:
    """Extract binary target (0/1) for a market from match data.

    Returns 1 if the market outcome occurred, 0 otherwise, None if data missing.
    """
    home_goals = match.get("homeGoalCount", match.get("home_goals"))
    away_goals = match.get("awayGoalCount", match.get("away_goals"))

    if home_goals is None or away_goals is None:
        return None
    try:
        hg = int(home_goals)
        ag = int(away_goals)
    except (ValueError, TypeError):
        return None

    if hg < 0 or ag < 0:
        return None

    total = hg + ag

    if market == "btts":
        return 1 if hg > 0 and ag > 0 else 0

    config = MARKET_CONFIGS.get(market)
    if config and config["threshold"] is not None:
        return 1 if total > config["threshold"] else 0

    return None


def build_market_targets(
    matches: List[Dict[str, Any]],
    market: str,
) -> np.ndarray:
    """Build binary target vector for a market.

    Returns numpy array of 0/1 labels, aligned with feature matrix rows.
    Matches with missing data get target -1 (to be filtered out).
    """
    targets = []
    for match in matches:
        t = _extract_market_target(match, market)
        targets.append(t if t is not None else -1)
    return np.array(targets, dtype=np.int32)


def train_market_model(
    X: np.ndarray,
    y: np.ndarray,
    sample_weights: Optional[np.ndarray] = None,
    market: str = "over25",
) -> Dict[str, Any]:
    """Train RF + XGBoost ensemble for a binary market.

    Args:
        X: Feature matrix
        y: Binary target vector (0/1, entries with -1 are filtered)
        sample_weights: Temporal decay weights
        market: Market name

    Returns:
        Dict with trained models and metadata
    """
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier

    # Filter out invalid entries
    valid_mask = y >= 0
    X_valid = X[valid_mask]
    y_valid = y[valid_mask]
    w_valid = sample_weights[valid_mask] if sample_weights is not None else None

    if len(y_valid) < 50:
        logger.warning(f"Insufficient data for {market}: {len(y_valid)} samples")
        return {"status": "insufficient_data", "market": market}

    # Train/val split (chronological)
    split = int(len(X_valid) * 0.85)
    X_train, X_val = X_valid[:split], X_valid[split:]
    y_train, y_val = y_valid[:split], y_valid[split:]
    w_train = w_valid[:split] if w_valid is not None else None

    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_split=15,
        min_samples_leaf=8,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train, sample_weight=w_train)

    # XGBoost
    xgb = XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        objective="binary:logistic",
        eval_metric="logloss",
        early_stopping_rounds=30,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    xgb.fit(
        X_train, y_train,
        sample_weight=w_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Evaluate on validation set
    rf_probs = rf.predict_proba(X_val)[:, 1]
    xgb_probs = xgb.predict_proba(X_val)[:, 1]
    ensemble_probs = rf_probs * 0.40 + xgb_probs * 0.60

    # Brier score (binary)
    brier = float(np.mean((ensemble_probs - y_val) ** 2))
    accuracy = float(np.mean((ensemble_probs >= 0.5).astype(int) == y_val))

    # Class distribution
    positive_rate = float(np.mean(y_valid))
    positive_rate_val = float(np.mean(y_val))

    # Quality gate: compute baseline Brier (constant predictor = base rate)
    # A model that always predicts the base rate gets Brier = p * (1 - p)
    brier_baseline = float(positive_rate_val * (1 - positive_rate_val))
    beats_baseline = brier < brier_baseline

    logger.info(
        f"Market {market}: Brier={brier:.4f} (baseline={brier_baseline:.4f}, "
        f"{'BEATS' if beats_baseline else 'WORSE'}), Acc={accuracy:.4f}, "
        f"positive_rate={positive_rate:.3f}, n={len(y_valid)}"
    )

    return {
        "status": "success",
        "market": market,
        "rf": rf,
        "xgb": xgb,
        "brier": round(brier, 4),
        "brier_baseline": round(brier_baseline, 4),
        "beats_baseline": beats_baseline,
        "accuracy": round(accuracy, 4),
        "positive_rate": round(positive_rate, 3),
        "n_samples": len(y_valid),
    }


def train_all_markets(
    X: np.ndarray,
    matches: List[Dict[str, Any]],
    sample_weights: Optional[np.ndarray] = None,
    feature_names: Optional[List[str]] = None,
    league_id: str = "global",
) -> Dict[str, Any]:
    """Train models for all markets and save to disk.

    Args:
        X: Feature matrix (aligned with matches that produced features)
        matches: Raw match dicts (for target extraction)
        sample_weights: Temporal decay weights
        feature_names: Feature column names
        league_id: League identifier for model storage
    """
    results = {}
    league_dir = _MODELS_DIR / league_id
    league_dir.mkdir(parents=True, exist_ok=True)

    for market in MARKET_CONFIGS:
        try:
            y_market = build_market_targets(matches, market)

            # Align targets with feature matrix
            # (feature_engineering skips first few matches for rolling warmup)
            if len(y_market) > len(X):
                y_market = y_market[len(y_market) - len(X):]
            elif len(y_market) < len(X):
                # Pad with -1 (will be filtered)
                pad = np.full(len(X) - len(y_market), -1, dtype=np.int32)
                y_market = np.concatenate([pad, y_market])

            result = train_market_model(
                X, y_market,
                sample_weights=sample_weights,
                market=market,
            )
            results[market] = result

            if result["status"] == "success":
                # Save models with validation metadata for quality gate
                model_path = league_dir / f"{market}_models.pkl"
                with open(model_path, "wb") as f:
                    pickle.dump({
                        "rf": result["rf"],
                        "xgb": result["xgb"],
                        "feature_names": feature_names,
                        "brier": result["brier"],
                        "brier_baseline": result["brier_baseline"],
                        "beats_baseline": result["beats_baseline"],
                        "accuracy": result["accuracy"],
                        "market": market,
                    }, f)
                if result["beats_baseline"]:
                    logger.info(f"Saved {market} model to {model_path} (ACTIVE — beats baseline)")
                else:
                    logger.warning(
                        f"Saved {market} model to {model_path} (INACTIVE — "
                        f"Brier {result['brier']:.4f} >= baseline {result['brier_baseline']:.4f})"
                    )

        except Exception as e:
            logger.error(f"Failed to train {market} for {league_id}: {e}")
            results[market] = {"status": "error", "error": str(e)}

    # Save summary
    summary = {
        market: {
            "status": r.get("status"),
            "brier": r.get("brier"),
            "brier_baseline": r.get("brier_baseline"),
            "beats_baseline": r.get("beats_baseline"),
            "accuracy": r.get("accuracy"),
            "positive_rate": r.get("positive_rate"),
            "n_samples": r.get("n_samples"),
        }
        for market, r in results.items()
    }
    with open(league_dir / "market_models_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return results


def predict_market(
    features: Dict[str, float],
    market: str,
    league_id: str = "global",
) -> Optional[float]:
    """Predict probability for a binary market.

    Returns probability (0-100 scale) or None if model unavailable or
    failed quality gate (doesn't beat baseline Brier).
    Falls back to None (caller uses Poisson) when:
    - No .pkl exists
    - Model failed validation (beats_baseline=False)
    - No validation metadata present (legacy models without gate)
    """
    if np is None:
        return None
    league_dir = _MODELS_DIR / league_id
    model_path = league_dir / f"{market}_models.pkl"

    # Try league-specific, then global
    if not model_path.exists():
        model_path = _MODELS_DIR / "global" / f"{market}_models.pkl"
    if not model_path.exists():
        return None

    try:
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)

        # Quality gate: only use model if it beat the baseline in validation
        if not bundle.get("beats_baseline", False):
            logger.debug(
                f"Market {market}/{league_id}: model exists but failed quality gate "
                f"(Brier={bundle.get('brier')}, baseline={bundle.get('brier_baseline')}). "
                f"Falling back to Poisson."
            )
            return None

        feature_names = bundle["feature_names"]
        X = np.array([[features.get(f, 0.0) for f in feature_names]], dtype=np.float64)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        rf_prob = bundle["rf"].predict_proba(X)[0, 1]
        xgb_prob = bundle["xgb"].predict_proba(X)[0, 1]
        ensemble_prob = rf_prob * 0.40 + xgb_prob * 0.60

        return round(float(ensemble_prob) * 100, 1)

    except Exception as e:
        logger.error(f"Market prediction failed for {market}/{league_id}: {e}")
        return None


def predict_all_markets(
    features: Dict[str, float],
    league_id: str = "global",
) -> Dict[str, Optional[float]]:
    """Predict probabilities for all markets.

    Returns dict of market_name -> probability (0-100 scale).
    """
    return {
        market: predict_market(features, market, league_id)
        for market in MARKET_CONFIGS
    }
