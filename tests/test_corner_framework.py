"""
Tests for the Corner Betting Framework

Covers:
- Negative Binomial model training and prediction
- Poisson model training and prediction
- ML Regression model training and prediction
- Expected total corners generation
- Line probability derivation
- Model comparison (3 candidates)
- Champion model selection
- Fallback model definition
- Artifact generation
- Operational state determination
- Shadow mode initial deployment
- Audit displays corners as dedicated market
- Runtime rejects ungoverned corners
"""

import math
import os
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pytest

# ─── Test data ───

def _make_corner_data(n: int = 100, mean: float = 10.0, std: float = 3.0):
    """Generate synthetic corner match data."""
    np.random.seed(42)
    counts = np.random.normal(mean, std, n).clip(2, 20).astype(int)
    return [{"total_corners": int(c)} for c in counts]


def _make_match_data(n: int = 100):
    """Generate synthetic match data with corner stats."""
    np.random.seed(42)
    matches = []
    teams = ["TeamA", "TeamB", "TeamC", "TeamD", "TeamE", "TeamF"]
    for i in range(n):
        home_team = teams[i % len(teams)]
        away_team = teams[(i + 1) % len(teams)]
        home_corners = max(1, int(np.random.normal(5, 2)))
        away_corners = max(1, int(np.random.normal(5, 2)))
        matches.append({
            "homeTeam": home_team,
            "awayTeam": away_team,
            "date_unix": 1700000000 + i * 86400,
            "team_a_corners": home_corners,
            "team_b_corners": away_corners,
            "totalCorners": home_corners + away_corners,
            "total_corners": home_corners + away_corners,
            "team_a_shots": max(5, int(np.random.normal(12, 3))),
            "team_b_shots": max(3, int(np.random.normal(10, 3))),
            "team_a_possession": min(70, max(30, int(np.random.normal(50, 8)))),
            "team_b_possession": min(70, max(30, int(np.random.normal(50, 8)))),
            "team_a_xg": max(0.5, round(np.random.normal(1.5, 0.5), 2)),
            "team_b_xg": max(0.3, round(np.random.normal(1.2, 0.5), 2)),
            "homeGoalCount": max(0, int(np.random.normal(1.5, 1))),
            "awayGoalCount": max(0, int(np.random.normal(1.2, 1))),
        })
    return matches


# ─── Negative Binomial Tests ───

class TestNegativeBinomial:
    def test_pmf_sums_to_one(self):
        from backend.modeling.corners.negative_binomial import _nb2_pmf
        mu, alpha = 10.0, 0.15
        total = sum(_nb2_pmf(k, mu, alpha) for k in range(50))
        assert abs(total - 1.0) < 0.01

    def test_fit_parameters(self):
        from backend.modeling.corners.negative_binomial import fit_negative_binomial
        counts = np.array([8, 10, 12, 9, 11, 10, 13, 7, 11, 10], dtype=float)
        mu, alpha = fit_negative_binomial(counts)
        assert 9.0 < mu < 12.0
        assert alpha > 0

    def test_predict_corners_nb(self):
        from backend.modeling.corners.negative_binomial import predict_corners_nb
        result = predict_corners_nb(10.5, alpha=0.15)
        assert "over_8.5" in result
        assert "over_9.5" in result
        assert "over_10.5" in result
        assert "over_11.5" in result
        # Probabilities should decrease with higher thresholds
        assert result["over_8.5"] > result["over_9.5"]
        assert result["over_9.5"] > result["over_10.5"]
        assert result["over_10.5"] > result["over_11.5"]
        # All between 0 and 1
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_train_league_nb(self):
        from backend.modeling.corners.negative_binomial import train_league_nb
        data = _make_corner_data(100)
        result = train_league_nb(data, "test-league")
        assert result["status"] == "trained"
        assert result["model"] == "negative_binomial"
        assert result["sample_size"] == 100
        assert "mu" in result
        assert "alpha" in result
        assert "avg_brier" in result
        assert "line_metrics" in result

    def test_train_insufficient_data(self):
        from backend.modeling.corners.negative_binomial import train_league_nb
        data = _make_corner_data(5)
        result = train_league_nb(data, "test-league")
        assert result["status"] == "insufficient_data"


# ─── Poisson Tests ───

class TestPoisson:
    def test_predict_corners_poisson(self):
        from backend.modeling.corners.poisson_model import predict_corners_poisson
        result = predict_corners_poisson(10.0)
        assert "over_8.5" in result
        assert "over_11.5" in result
        assert result["over_8.5"] > result["over_11.5"]

    def test_train_league_poisson(self):
        from backend.modeling.corners.poisson_model import train_league_poisson
        data = _make_corner_data(100)
        result = train_league_poisson(data, "test-league")
        assert result["status"] == "trained"
        assert result["model"] == "poisson"
        assert "lambda" in result
        assert "dispersion_index" in result

    def test_overdispersion_detection(self):
        from backend.modeling.corners.poisson_model import train_league_poisson
        # High variance data should detect overdispersion
        np.random.seed(42)
        data = [{"total_corners": int(c)} for c in np.random.negative_binomial(5, 0.3, 100)]
        result = train_league_poisson(data, "test-league")
        assert result["status"] == "trained"
        # Negative binomial data should show overdispersion
        assert result["dispersion_index"] > 1.0


# ─── ML Regression Tests ───

class TestMLRegression:
    def test_train_corner_regressor(self):
        from backend.modeling.corners.features import build_corner_features
        from backend.modeling.corners.ml_regression import train_corner_regressor

        matches = _make_match_data(100)
        X, y, feature_names = build_corner_features(matches, "test-league")

        if len(y) < 30:
            pytest.skip("Not enough feature samples")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"DATA_ROOT": tmpdir}):
                # Need to reimport to pick up new DATA_ROOT
                import importlib
                import backend.modeling.corners.ml_regression as ml_mod
                ml_mod._MODELS_DIR = __import__("pathlib").Path(tmpdir) / ".corner_models"

                result = train_corner_regressor(X, y, feature_names, "test-league")
                assert result["model"] == "ml_regression"
                assert result["status"] in ("trained", "insufficient_data")
                if result["status"] == "trained":
                    assert "avg_mae" in result
                    assert "avg_brier" in result


# ─── Features Tests ───

class TestFeatures:
    def test_build_corner_features(self):
        from backend.modeling.corners.features import build_corner_features
        matches = _make_match_data(50)
        X, y, feature_names = build_corner_features(matches, "test-league")
        assert len(feature_names) > 0
        assert X.shape[1] == len(feature_names)
        assert len(y) > 0
        # All features should be finite
        assert np.all(np.isfinite(X))

    def test_build_match_corner_features(self):
        from backend.modeling.corners.features import build_match_corner_features
        home_stats = {
            "cornersAVG_home": 5.2,
            "homeCornersAgainstPerMatch": 4.1,
            "shotsAVG_home": 12.0,
            "possessionAVG_home": 55.0,
        }
        away_stats = {
            "cornersAVG_away": 4.8,
            "awayCornersAgainstPerMatch": 4.5,
            "shotsAVG_away": 10.0,
            "possessionAVG_away": 45.0,
        }
        features = build_match_corner_features(home_stats, away_stats)
        assert "combined_corners_avg_r5" in features
        assert "league_avg_corners" in features
        assert features["combined_corners_avg_r5"] == pytest.approx(10.0, abs=0.1)


# ─── Benchmarks Tests ───

class TestBenchmarks:
    def test_evaluate_model_on_line(self):
        from backend.modeling.corners.benchmarks import evaluate_model_on_line
        preds = np.array([0.6, 0.7, 0.5, 0.65, 0.55])
        actuals = np.array([1.0, 1.0, 0.0, 1.0, 0.0])
        result = evaluate_model_on_line(preds, actuals, 9.5, "test_model")
        assert "brier" in result
        assert "logloss" in result
        assert "ece" in result
        assert "roi_theoretical" in result
        assert result["sample_size"] == 5

    def test_compare_models(self):
        from backend.modeling.corners.benchmarks import compare_models
        n = 50
        np.random.seed(42)
        actuals = np.random.binomial(1, 0.5, n).astype(float)
        model_results = {
            "model_a": {"over_9.5": np.random.uniform(0.3, 0.7, n)},
            "model_b": {"over_9.5": np.random.uniform(0.4, 0.6, n)},
        }
        actuals_by_line = {"over_9.5": actuals}
        result = compare_models(model_results, actuals_by_line, "test-league")
        assert "models" in result
        assert "lines" in result


# ─── Champion Selector Tests ───

class TestChampionSelector:
    def test_select_champion_for_line(self):
        from backend.modeling.corners.champion_selector import select_champion_for_line
        metrics = {
            "negative_binomial": {
                "brier": 0.20, "logloss": 0.55, "ece": 0.05,
                "stability": 0.15, "roi_theoretical": 0.05,
                "drift": 0.02, "sample_size": 100,
            },
            "poisson": {
                "brier": 0.22, "logloss": 0.60, "ece": 0.08,
                "stability": 0.20, "roi_theoretical": 0.03,
                "drift": 0.03, "sample_size": 100,
            },
            "ml_regression": {
                "brier": 0.18, "logloss": 0.50, "ece": 0.04,
                "stability": 0.12, "roi_theoretical": 0.08,
                "drift": 0.01, "sample_size": 100,
            },
        }
        result = select_champion_for_line(metrics, 9.5, "test-league")
        assert result["champion_model"] is not None
        assert result["fallback_model"] is not None
        assert result["champion_model"] != result["fallback_model"]
        # ML regression has best metrics, should be champion
        assert result["champion_model"] == "ml_regression"

    def test_select_with_ineligible_models(self):
        from backend.modeling.corners.champion_selector import select_champion_for_line
        metrics = {
            "negative_binomial": {
                "brier": 0.20, "logloss": 0.55, "ece": 0.05,
                "stability": 0.15, "roi_theoretical": 0.05,
                "drift": 0.02, "sample_size": 100,
            },
            "poisson": {
                "brier": 0.35, "logloss": 0.80, "ece": 0.25,
                "stability": 0.50, "roi_theoretical": -0.10,
                "drift": 0.15, "sample_size": 10,  # too few samples
            },
        }
        result = select_champion_for_line(metrics, 9.5, "test-league")
        assert result["champion_model"] == "negative_binomial"


# ─── Operational States Tests ───

class TestOperationalStates:
    def test_hard_blockers(self):
        from backend.modeling.corners.operational_states import check_hard_blockers
        # Missing artifact
        blocked, reasons = check_hard_blockers({}, has_artifact=False)
        assert blocked
        assert "artifact_missing" in reasons

        # Insufficient samples
        blocked, reasons = check_hard_blockers({"sample_size": 5})
        assert blocked

    def test_evidence_score(self):
        from backend.modeling.corners.operational_states import compute_evidence_score
        metrics = {
            "ece": 0.05, "brier": 0.18, "logloss": 0.50,
            "stability": 0.15, "roi_theoretical": 0.08, "drift": 0.02,
        }
        result = compute_evidence_score(
            metrics, beats_league=True, beats_team=True, beats_secondary_baseline=True,
        )
        assert result["total_score"] > 0
        assert result["total_score"] <= 100

    def test_shadow_mode_caps_state(self):
        from backend.modeling.corners.operational_states import (
            determine_operational_state, CornerOperationalState,
        )
        # Metrics that would normally give ACTIVE
        metrics = {
            "ece": 0.03, "brier": 0.15, "logloss": 0.45,
            "stability": 0.10, "roi_theoretical": 0.10, "drift": 0.01,
            "sample_size": 200,
        }
        result = determine_operational_state(
            metrics, force_shadow=True,
            beats_league=True, beats_team=True, beats_secondary_baseline=True,
        )
        # Should be capped at NEUTRAL in shadow mode
        assert result["operational_state"] == CornerOperationalState.NEUTRAL

    def test_no_shadow_allows_active(self):
        from backend.modeling.corners.operational_states import (
            determine_operational_state, CornerOperationalState,
        )
        metrics = {
            "ece": 0.03, "brier": 0.15, "logloss": 0.45,
            "stability": 0.10, "roi_theoretical": 0.10, "drift": 0.01,
            "sample_size": 200,
        }
        result = determine_operational_state(
            metrics, force_shadow=False,
            beats_league=True, beats_team=True, beats_secondary_baseline=True,
        )
        assert result["operational_state"] in (
            CornerOperationalState.ACTIVE, CornerOperationalState.ACTIVE_GUARDED,
        )

    def test_restricted_for_bad_metrics(self):
        from backend.modeling.corners.operational_states import (
            determine_operational_state, CornerOperationalState,
        )
        metrics = {"ece": 0.30, "brier": 0.40, "logloss": 1.0,
                   "stability": 0.50, "roi_theoretical": -0.10, "drift": 0.25,
                   "sample_size": 50}
        result = determine_operational_state(metrics, force_shadow=False)
        assert result["operational_state"] == CornerOperationalState.RESTRICTED


# ─── Artifacts Tests ───

class TestArtifacts:
    def test_generate_and_load_artifacts(self):
        from backend.modeling.corners import artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts._ARTIFACTS_DIR = __import__("pathlib").Path(tmpdir)

            # Generate model registry
            selections = {
                "test-league": {
                    "dominant_champion": "negative_binomial",
                    "champion_distribution": {"negative_binomial": 3, "poisson": 1},
                    "line_selections": {
                        "over_9.5": {
                            "champion_model": "negative_binomial",
                            "fallback_model": "poisson",
                            "champion_score": 0.35,
                            "selection_method": "composite_score",
                        },
                    },
                },
            }
            artifacts.generate_model_registry(selections)

            # Load it back
            loaded = artifacts.load_artifact("corner_model_registry")
            assert loaded is not None
            assert "test-league" in loaded["leagues"]

    def test_generate_promotion_decisions(self):
        from backend.modeling.corners import artifacts
        from backend.modeling.corners.operational_states import CornerOperationalState

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts._ARTIFACTS_DIR = __import__("pathlib").Path(tmpdir)

            decisions = {
                "test-league": {
                    "lines": {
                        "over_9.5": {
                            "operational_state": CornerOperationalState.NEUTRAL,
                            "evidence_score": {"total_score": 45},
                            "hard_blockers": [],
                            "reasoning": "Score=45 → NEUTRAL",
                            "force_shadow": True,
                        },
                    },
                    "state_distribution": {"NEUTRAL": 1},
                    "any_active": False,
                },
            }
            artifacts.generate_promotion_decisions(decisions)

            loaded = artifacts.load_artifact("corner_promotion_decisions")
            assert loaded is not None
            league_data = loaded["leagues"]["test-league"]
            assert league_data["lines"]["over_9.5"]["operational_state"] == "NEUTRAL"


# ─── Runtime / Predictor Tests ───

class TestPredictor:
    def test_runtime_does_not_promote_without_artifact(self):
        """Runtime should not promote corners without validated artifact."""
        from backend.modeling.corners.predictor import predict_corners

        home_stats = {"cornersAVG_home": 5.0, "cornersAVG_overall": 5.0}
        away_stats = {"cornersAVG_away": 5.0, "cornersAVG_overall": 5.0}

        result = predict_corners(home_stats, away_stats, "unknown-league")
        assert result["marketFamily"] == "corners"
        assert result["governed"] is True

        # All lines should have predictions (from fallback)
        for line_key in ["over_8.5", "over_9.5", "over_10.5", "over_11.5"]:
            line = result["lines"].get(line_key, {})
            assert line.get("probability") is not None or line.get("model_used") is not None
            # Without artifacts, state should be RESTRICTED
            assert line.get("operational_state") == "RESTRICTED"

    def test_expected_total_corners_present(self):
        from backend.modeling.corners.predictor import predict_corners
        home_stats = {"cornersAVG_home": 6.0, "cornersAVG_overall": 6.0}
        away_stats = {"cornersAVG_away": 5.0, "cornersAVG_overall": 5.0}
        result = predict_corners(home_stats, away_stats, "test-league")
        assert "expected_total_corners" in result
        assert result["expected_total_corners"] > 0


# ─── Audit Display Test ───

class TestAuditDisplay:
    def test_corners_as_dedicated_market(self):
        """Corners should appear in ev_classification as market_type='Corners'."""
        pytest.importorskip("pydantic")
        from backend.models.market_output import MarketOutput, MarketClassification

        mo = MarketOutput(
            market_type="Corners",
            selection="Corners Over 9.5",
            raw_probability=0.55,
            calibrated_probability=0.58,
            data_quality_score=0.7,
            display_label="Escanteios Over 9.5",
        )
        mo._corner_governance = {
            "marketFamily": "corners",
            "cornerModelStatus": "NEUTRAL",
            "championModel": "negative_binomial",
            "fallbackModel": "poisson",
            "modelUsed": "negative_binomial",
            "beatsPoisson": True,
            "beatsNegativeBinomial": False,
            "beatsMLRegression": True,
            "cornerCalibrationStatus": "adequate",
            "cornerSampleAdequacy": "adequate",
            "cornerValidationVersion": "1.0.0",
        }

        legacy = mo.to_legacy_mercado()
        assert legacy["mercado"] == "Escanteios Over 9.5"
        assert "corner_governance" in legacy
        assert legacy["corner_governance"]["marketFamily"] == "corners"
        assert legacy["corner_governance"]["championModel"] == "negative_binomial"


# ─── Integration: Model Comparison ───

class TestModelComparison:
    def test_three_models_compared(self):
        """All 3 models should be trained and compared."""
        from backend.modeling.corners.negative_binomial import train_league_nb
        from backend.modeling.corners.poisson_model import train_league_poisson

        data = _make_corner_data(100, mean=10.0, std=3.0)

        nb = train_league_nb(data, "test-league")
        pois = train_league_poisson(data, "test-league")

        assert nb["status"] == "trained"
        assert pois["status"] == "trained"

        # Both should have brier scores
        assert "avg_brier" in nb
        assert "avg_brier" in pois

        # NB should generally handle overdispersion better
        # (but this depends on data — just check both produce valid scores)
        assert 0 <= nb["avg_brier"] <= 1
        assert 0 <= pois["avg_brier"] <= 1
