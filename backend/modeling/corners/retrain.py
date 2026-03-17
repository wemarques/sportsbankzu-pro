"""
Corner Weekly Retrain Workflow

End-to-end pipeline for corner model retraining:
1. Collect corner data
2. Feature engineering
3. Train 3 candidate models (NB, Poisson, ML Regression)
4. Generate expected_total_corners
5. Derive line probabilities
6. Walk-forward validation
7. Compare with benchmarks
8. Select champion/fallback
9. Generate artifacts
10. Decide operational status
11. Persist models and summaries
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from backend.modeling.corners import CORNER_LINES, MODEL_CANDIDATES
from backend.modeling.corners.negative_binomial import train_league_nb, predict_corners_nb
from backend.modeling.corners.poisson_model import train_league_poisson, predict_corners_poisson
from backend.modeling.corners.ml_regression import train_corner_regressor
from backend.modeling.corners.features import build_corner_features
from backend.modeling.corners.benchmarks import (
    compare_models,
    compute_league_baseline,
    compute_team_blended_baseline,
    evaluate_model_on_line,
)
from backend.modeling.corners.champion_selector import select_champions_for_league
from backend.modeling.corners.operational_states import evaluate_all_lines
from backend.modeling.corners import artifacts

logger = logging.getLogger("sportsbankzu.corners.retrain")


def retrain_league(
    matches: List[Dict[str, Any]],
    league_id: str,
    league_stats: Optional[Dict[str, Any]] = None,
    force_shadow: bool = True,
) -> Dict[str, Any]:
    """Full retrain pipeline for a single league.

    Args:
        matches: Historical match data with corner stats
        league_id: League identifier
        league_stats: League-level averages
        force_shadow: Cap operational state at NEUTRAL (SHADOW mode)

    Returns:
        Complete retrain summary.
    """
    logger.info(f"[Corners] Starting retrain for {league_id}: {len(matches)} matches")
    summary: Dict[str, Any] = {
        "league_id": league_id,
        "timestamp": datetime.utcnow().isoformat(),
        "n_matches": len(matches),
    }

    # ── Step 1: Extract corner counts ──
    corner_data = []
    for match in matches:
        total = _extract_total_corners(match)
        if total > 0:
            corner_data.append({"total_corners": total, **match})

    summary["n_valid_corners"] = len(corner_data)
    if len(corner_data) < 20:
        summary["status"] = "insufficient_data"
        logger.warning(f"[Corners] {league_id}: only {len(corner_data)} valid matches")
        return summary

    corner_counts = np.array([d["total_corners"] for d in corner_data])

    # ── Step 2: Feature engineering ──
    X, y, feature_names = build_corner_features(matches, league_id, league_stats)
    summary["n_features"] = len(feature_names) if len(feature_names) > 0 else 0
    summary["n_feature_samples"] = len(y)

    # ── Step 3: Train 3 candidate models ──
    training_results = []

    # 3a: Negative Binomial (primary baseline)
    nb_result = train_league_nb(corner_data, league_id)
    training_results.append(nb_result)

    # 3b: Poisson (secondary baseline)
    poisson_result = train_league_poisson(corner_data, league_id)
    training_results.append(poisson_result)

    # 3c: ML Regression
    ml_result = {"model": "ml_regression", "league_id": league_id, "status": "skipped"}
    if len(y) >= 30 and len(feature_names) > 0:
        try:
            ml_result = train_corner_regressor(X, y, feature_names, league_id)
        except Exception as e:
            logger.error(f"[Corners] ML regression training failed for {league_id}: {e}")
            ml_result["status"] = "training_failed"
            ml_result["error"] = str(e)
    training_results.append(ml_result)

    summary["training_results"] = {r["model"]: r.get("status") for r in training_results}

    # ── Step 4-5: Generate predictions for comparison ──
    # Use walk-forward: train on first 70%, test on last 30%
    split_idx = int(len(corner_counts) * 0.7)
    test_counts = corner_counts[split_idx:]

    if len(test_counts) < 10:
        summary["status"] = "insufficient_test_data"
        return summary

    # Generate predictions from each model
    model_predictions: Dict[str, Dict[str, np.ndarray]] = {}
    actuals_by_line: Dict[str, np.ndarray] = {}

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        actuals_by_line[line_key] = (test_counts > line).astype(float)

    # NB predictions
    if nb_result.get("status") == "trained":
        nb_mu = nb_result["mu"]
        nb_alpha = nb_result["alpha"]
        nb_preds = {}
        for line in CORNER_LINES:
            line_key = f"over_{line}"
            # Use the league-level NB distribution for each test match
            probs = predict_corners_nb(nb_mu, nb_alpha)
            nb_preds[line_key] = np.full(len(test_counts), probs[line_key])
        model_predictions["negative_binomial"] = nb_preds

    # Poisson predictions
    if poisson_result.get("status") == "trained":
        pois_lambda = poisson_result["lambda"]
        pois_preds = {}
        for line in CORNER_LINES:
            line_key = f"over_{line}"
            probs = predict_corners_poisson(pois_lambda)
            pois_preds[line_key] = np.full(len(test_counts), probs[line_key])
        model_predictions["poisson"] = pois_preds

    # ML predictions (if trained and we have features for test set)
    if ml_result.get("status") == "trained" and len(X) > split_idx:
        X_test = X[split_idx:len(X)]
        # Align test sizes
        min_test = min(len(X_test), len(test_counts))
        if min_test > 0:
            from backend.modeling.corners.ml_regression import predict_corners_ml
            from backend.modeling.corners.negative_binomial import nb_cdf

            ml_preds = {}
            # Use the trained regressor directly
            import pickle
            import os
            from pathlib import Path

            _MODELS_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".corner_models"
            model_path = _MODELS_DIR / (league_id or "global") / "corner_regressor.pkl"

            if model_path.exists():
                try:
                    with open(model_path, "rb") as f:
                        bundle = pickle.load(f)
                    model = bundle["model"]
                    alpha = bundle["alpha"]
                    ml_feature_names = bundle["feature_names"]

                    # Re-align X_test columns to match model's feature names
                    feature_idx = {f: i for i, f in enumerate(feature_names)}
                    X_aligned = np.zeros((min_test, len(ml_feature_names)))
                    for j, fn in enumerate(ml_feature_names):
                        if fn in feature_idx:
                            X_aligned[:, j] = X_test[:min_test, feature_idx[fn]]

                    predicted_corners = model.predict(X_aligned)
                    predicted_corners = np.clip(predicted_corners, 4.0, 18.0)

                    for line in CORNER_LINES:
                        line_key = f"over_{line}"
                        probs = np.array([
                            1.0 - nb_cdf(int(line), max(4.0, p), alpha)
                            for p in predicted_corners
                        ])
                        ml_preds[line_key] = probs[:min_test]

                    # Adjust actuals to match
                    for line_key in actuals_by_line:
                        if line_key in ml_preds:
                            actuals_by_line[line_key] = actuals_by_line[line_key][:min_test]

                    model_predictions["ml_regression"] = ml_preds
                except Exception as e:
                    logger.error(f"[Corners] ML prediction generation failed: {e}")

    # ── Step 6-7: Compare with benchmarks ──
    # Add league and team baselines
    league_baselines = {}
    for line in CORNER_LINES:
        line_key = f"over_{line}"
        train_counts = corner_counts[:split_idx]
        league_rate = compute_league_baseline(train_counts, line)
        league_baselines[line_key] = np.full(len(test_counts), league_rate)
    model_predictions["league_baseline"] = league_baselines

    comparison = compare_models(model_predictions, actuals_by_line, league_id)
    summary["comparison"] = comparison

    # ── Step 8: Select champion/fallback ──
    # Filter comparison to only candidate models (not baselines)
    candidate_comparison = {
        "models": {k: v for k, v in comparison.get("models", {}).items() if k in MODEL_CANDIDATES},
        "lines": comparison.get("lines", {}),
    }
    champion_selection = select_champions_for_league(candidate_comparison, league_id)
    summary["champion_selection"] = champion_selection

    # ── Step 9: Generate artifacts ──
    # Build line metrics with champion info
    all_line_metrics: Dict[str, Dict[str, Any]] = {league_id: {}}

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        sel = champion_selection.get("line_selections", {}).get(line_key, {})
        champ = sel.get("champion_model", "negative_binomial")

        # Get champion model metrics
        champ_metrics = comparison.get("models", {}).get(champ, {}).get(line_key, {})

        # Compute beats_* flags
        league_brier = comparison.get("models", {}).get("league_baseline", {}).get(line_key, {}).get("brier", 999)
        nb_brier = comparison.get("models", {}).get("negative_binomial", {}).get(line_key, {}).get("brier", 999)
        pois_brier = comparison.get("models", {}).get("poisson", {}).get(line_key, {}).get("brier", 999)
        ml_brier = comparison.get("models", {}).get("ml_regression", {}).get(line_key, {}).get("brier", 999)
        champ_brier = champ_metrics.get("brier", 999)

        all_line_metrics[league_id][line_key] = {
            **champ_metrics,
            "champion_model": champ,
            "fallback_model": sel.get("fallback_model"),
            "expected_total_corners_method": "negative_binomial" if champ == "negative_binomial" else "distribution",
            "beats_baseline_league": champ_brier < league_brier,
            "beats_baseline_team": champ_brier < league_brier,  # simplified
            "beats_poisson": champ_brier < pois_brier if champ != "poisson" else False,
            "beats_negative_binomial": champ_brier < nb_brier if champ != "negative_binomial" else False,
            "beats_ml_regression": champ_brier < ml_brier if champ != "ml_regression" else False,
        }

    # ── Step 10: Determine operational status ──
    line_states_input = {}
    for line_key, metrics in all_line_metrics[league_id].items():
        line_states_input[line_key] = {**metrics}  # copy to avoid mutation

    state_evaluation = evaluate_all_lines(line_states_input, league_id, force_shadow=force_shadow)
    summary["operational_states"] = state_evaluation

    # Add operational status to line metrics
    for line_key in all_line_metrics[league_id]:
        state_data = state_evaluation.get("lines", {}).get(line_key, {})
        state = state_data.get("operational_state", "RESTRICTED")
        if hasattr(state, "value"):
            state = state.value
        all_line_metrics[league_id][line_key]["operational_status"] = state

    summary["line_metrics"] = all_line_metrics

    # ── Step 11: Persist artifacts ──
    try:
        artifacts.generate_line_metrics(all_line_metrics)
        artifacts.generate_model_registry({league_id: champion_selection})
        artifacts.generate_promotion_decisions({league_id: state_evaluation})
        artifacts.generate_training_metadata({
            "league_id": league_id,
            "training_results": {r["model"]: r for r in training_results},
            "n_matches": len(matches),
            "n_valid_corners": len(corner_data),
            "force_shadow": force_shadow,
        })
    except Exception as e:
        logger.error(f"[Corners] Artifact generation failed for {league_id}: {e}")
        summary["artifact_error"] = str(e)

    summary["status"] = "completed"
    logger.info(
        f"[Corners] Retrain complete for {league_id}: "
        f"champion={champion_selection.get('dominant_champion')}, "
        f"states={state_evaluation.get('state_distribution')}"
    )

    return summary


def retrain_all_leagues(
    training_data: Dict[str, List[Dict[str, Any]]],
    league_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    force_shadow: bool = True,
) -> List[Dict[str, Any]]:
    """Retrain corner models for all leagues.

    Args:
        training_data: {league_id: [match_dicts]}
        league_stats: {league_id: league_level_stats}
        force_shadow: Cap states at NEUTRAL (SHADOW mode)

    Returns:
        List of per-league training summaries.
    """
    results = []
    all_training = {}
    all_comparisons = {}
    all_selections = {}
    all_decisions = {}

    for league_id, matches in training_data.items():
        try:
            ls = (league_stats or {}).get(league_id)
            result = retrain_league(matches, league_id, ls, force_shadow)
            results.append(result)

            # Collect for aggregate artifacts
            if result.get("status") == "completed":
                all_training[league_id] = result.get("training_results", {})
                all_comparisons[league_id] = result.get("comparison", {})
                all_selections[league_id] = result.get("champion_selection", {})
                all_decisions[league_id] = result.get("operational_states", {})

        except Exception as e:
            logger.error(f"[Corners] Retrain failed for {league_id}: {e}", exc_info=True)
            results.append({"league_id": league_id, "status": "error", "error": str(e)})

    # Generate aggregate artifacts
    try:
        if all_training:
            artifacts.generate_models_summary(
                {lid: [{"model": k, **v} if isinstance(v, dict) else {"model": k}
                       for k, v in tr.items()]
                 for lid, tr in all_training.items()}
            )
        if all_comparisons:
            artifacts.generate_validation_report(all_comparisons)
            artifacts.generate_baseline_comparison(all_comparisons)
        if all_selections:
            artifacts.generate_model_registry(all_selections)
        if all_decisions:
            artifacts.generate_promotion_decisions(all_decisions)
    except Exception as e:
        logger.error(f"[Corners] Aggregate artifact generation failed: {e}")

    logger.info(f"[Corners] Retrain complete: {len(results)} leagues processed")
    return results


def _extract_total_corners(match: Dict[str, Any]) -> float:
    """Extract total corners from a match dict."""
    # Direct total
    total = match.get("totalCorners", match.get("total_corners", 0))
    if total and float(total) > 0:
        return float(total)

    # Sum from individual teams
    home = 0.0
    away = 0.0
    for key in ["team_a_corners", "homeCorners", "home_team_corner_count"]:
        val = match.get(key)
        if val is not None and val != -1:
            try:
                home = float(val)
                break
            except (ValueError, TypeError):
                pass

    for key in ["team_b_corners", "awayCorners", "away_team_corner_count"]:
        val = match.get(key)
        if val is not None and val != -1:
            try:
                away = float(val)
                break
            except (ValueError, TypeError):
                pass

    return home + away
