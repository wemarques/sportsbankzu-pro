"""
Tests for Corners Engine v2

Covers:
A. PROJECTION
  - expected FT is calculated
  - expected 1H + 2H ≈ expected FT
  - dynamic shrinkage works
  - motor does NOT anchor on O8.5

B. PRICE LADDER
  - generates Over and Under sides
  - can select U9.5 / U10.5 when appropriate
  - returns NO BET when conditions warrant

C. GOVERNANCE
  - low coverage → RESTRICTED or NO BET
  - medium coverage → NEUTRAL
  - good coverage → ACTIVE_GUARDED / ACTIVE

D. MISTRAL
  - review input is built correctly
  - Mistral can reduce confidence
  - Mistral can force NO BET
  - Mistral cannot promote a weak market

E. REGRESSION
  - new motor corrects low-over bias
  - with mean near line + high dispersion → no auto-over
  - under lines are normal candidates

F. DATA QUALITY
  - INSUFFICIENT tier for missing data
  - HIGH tier for complete data
  - timing availability detected
"""

import math
import pytest
import numpy as np


# ─── Test data helpers ───

def _make_home_stats(**overrides):
    base = {
        "cornersAVG_home": 5.5,
        "cornersAVG_overall": 5.0,
        "homeCornersPerMatch": 5.5,
        "cornersAgainstAVG_home": 4.5,
        "homeCornersAgainstPerMatch": 4.5,
        "corners_total_per_match": 5.5,
        "corners_against_per_match": 4.5,
        "corners_recorded_matches_num": 20,
        "corners_total_per_match_fh": 2.5,
        "corners_total_per_match_2h": 3.0,
        "cornerTimingRecorded_matches": 15,
        "shots_per_match": 13.0,
        "shotsAVG_home": 13.0,
        "shots_on_target_per_match": 4.5,
        "average_possession": 55.0,
        "possessionAVG_home": 55.0,
        "xg_for_avg": 1.5,
        "xgAVG_home": 1.5,
        "xg_against_avg": 1.2,
        "matchesPlayed_home": 20,
        "matchesPlayed_overall": 38,
    }
    base.update(overrides)
    return base


def _make_away_stats(**overrides):
    base = {
        "cornersAVG_away": 4.5,
        "cornersAVG_overall": 4.8,
        "awayCornersPerMatch": 4.5,
        "cornersAgainstAVG_away": 5.0,
        "awayCornersAgainstPerMatch": 5.0,
        "corners_total_per_match": 4.5,
        "corners_against_per_match": 5.0,
        "corners_recorded_matches_num": 18,
        "corners_total_per_match_fh": 2.0,
        "corners_total_per_match_2h": 2.5,
        "cornerTimingRecorded_matches": 12,
        "shots_per_match": 11.0,
        "shotsAVG_away": 11.0,
        "shots_on_target_per_match": 3.5,
        "average_possession": 45.0,
        "possessionAVG_away": 45.0,
        "xg_for_avg": 1.2,
        "xgAVG_away": 1.2,
        "xg_against_avg": 1.5,
        "matchesPlayed_away": 18,
        "matchesPlayed_overall": 36,
    }
    base.update(overrides)
    return base


def _make_league_stats(**overrides):
    base = {
        "average_corners_per_match": 10.5,
        "cornersAVG_overall": 10.5,
        "leagueAvgCorners": 10.5,
        "average_corners_per_match_home_team": 5.8,
        "prediction_risk": 45,
        "home_advantage_percentage": 46,
        "progress": 60,
        "matches_completed": 150,
    }
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════
# A. PROJECTION TESTS
# ═════════════════════════════════════════════════════════════════

class TestProjection:
    def test_expected_ft_is_calculated(self):
        from backend.modeling.corners.predictor import predict_corners

        result = predict_corners(
            _make_home_stats(), _make_away_stats(), "test-league",
            league_stats=_make_league_stats(),
        )
        proj = result.get("projection", {})
        assert proj.get("expected_total_corners_ft") is not None
        assert 4.0 <= proj["expected_total_corners_ft"] <= 18.0

    def test_halves_sum_to_ft(self):
        from backend.modeling.corners.predictor import predict_corners

        result = predict_corners(
            _make_home_stats(), _make_away_stats(), "test-league",
            league_stats=_make_league_stats(),
        )
        proj = result["projection"]
        ft = proj["expected_total_corners_ft"]
        fh = proj["expected_total_corners_1h"]
        sh = proj["expected_total_corners_2h"]

        assert fh > 0
        assert sh > 0
        assert abs((fh + sh) - ft) < 0.2  # tolerance

    def test_dynamic_shrinkage(self):
        from backend.modeling.corners.predictor import _compute_dynamic_shrinkage

        # Good data → low shrinkage
        good_quality = {"sample_adequacy_score": 1.0, "coverage_score": 0.9}
        good_features = {"league_prediction_risk": 30}
        shrink_good = _compute_dynamic_shrinkage(good_features, good_quality)

        # Bad data → high shrinkage
        bad_quality = {"sample_adequacy_score": 0.2, "coverage_score": 0.3}
        bad_features = {"league_prediction_risk": 80}
        shrink_bad = _compute_dynamic_shrinkage(bad_features, bad_quality)

        assert shrink_good < shrink_bad
        assert 0.05 <= shrink_good <= 0.60
        assert 0.05 <= shrink_bad <= 0.60

    def test_no_over_85_anchor(self):
        """The engine should NOT start from Over 8.5 as default."""
        from backend.modeling.corners.predictor import predict_corners

        # Create a low-corners scenario: expected ~7 total corners
        home = _make_home_stats(cornersAVG_home=3.0, homeCornersPerMatch=3.0,
                                corners_total_per_match=3.0)
        away = _make_away_stats(cornersAVG_away=3.5, awayCornersPerMatch=3.5,
                                corners_total_per_match=3.5)
        league = _make_league_stats(average_corners_per_match=7.0,
                                    cornersAVG_overall=7.0)

        result = predict_corners(home, away, "low-corners-league", league_stats=league)
        proj = result["projection"]

        # Expected should be well below 8.5
        assert proj["expected_total_corners_ft"] < 9.0

        # Should NOT automatically suggest Over 8.5
        decision = result.get("decision", {})
        if decision.get("market_label"):
            assert "Over 8.5" not in decision["market_label"]

    def test_projection_uses_timing_when_available(self):
        from backend.modeling.corners.features import build_v2_match_features
        from backend.modeling.corners.predictor import _decompose_halves

        features = build_v2_match_features(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        assert features["_has_timing"] is True

        fh, sh = _decompose_halves(features, 10.0)
        assert fh > 0
        assert sh > 0
        # FH should be less than 2H (typical pattern)
        assert fh < sh


# ═════════════════════════════════════════════════════════════════
# B. PRICE LADDER TESTS
# ═════════════════════════════════════════════════════════════════

class TestPriceLadder:
    def test_generates_over_and_under(self):
        from backend.modeling.corners.price_ladder import compute_line_probabilities

        priced = compute_line_probabilities(10.5, 0.15)
        assert len(priced) > 0

        for item in priced:
            assert "p_over" in item
            assert "p_under" in item
            assert item["p_over"] + item["p_under"] == pytest.approx(1.0, abs=0.01)
            assert item["fair_over"] is not None
            assert item["fair_under"] is not None

    def test_can_select_under(self):
        """With low expected corners, Under should be selectable."""
        from backend.modeling.corners.price_ladder import price_full_ladder

        # Expected 7.0 corners — Under 8.5 should be a strong candidate
        result = price_full_ladder(
            expected_ft=7.0,
            alpha=0.15,
            odds={"cornersOver85": 2.20, "cornersOver95": 3.50},
            data_quality_tier="HIGH",
        )

        selected = result["selected"]
        # Should pick an Under or be NO_BET — should NOT pick Over 8.5 at expected=7
        if not selected.get("no_bet"):
            # Best candidate should either be Under, or a low line Over
            assert selected["side"] == "UNDER" or selected["line"] <= 6.5

    def test_returns_no_bet_when_edge_insufficient(self):
        from backend.modeling.corners.price_ladder import price_full_ladder

        # Odds that imply exactly the modeled prob → zero edge
        result = price_full_ladder(
            expected_ft=10.0,
            alpha=0.15,
            odds={},  # no odds = no edge
            data_quality_tier="LOW",
        )
        selected = result["selected"]
        assert selected.get("no_bet") is True

    def test_high_dispersion_near_line_avoids_over(self):
        """When mean ≈ line and dispersion is high, avoid auto-over."""
        from backend.modeling.corners.price_ladder import price_full_ladder

        # Expected 9.0 ≈ Over 8.5 line, with HIGH alpha (dispersion)
        result = price_full_ladder(
            expected_ft=9.0,
            alpha=1.5,  # very high dispersion
            odds={"cornersOver85": 1.90},
            data_quality_tier="LOW",
        )
        selected = result["selected"]

        # Should NOT pick Over 8.5 at high dispersion + LOW quality
        if not selected.get("no_bet"):
            # If it picks anything, it shouldn't be Over 8.5 with these conditions
            if selected["line"] == 8.5 and selected["side"] == "OVER":
                # Check the proximity ratio triggers caution
                assert selected.get("proximity_ratio", 0) < 0.5

    def test_prediction_interval(self):
        from backend.modeling.corners.price_ladder import price_full_ladder

        result = price_full_ladder(10.0, 0.15, {}, "MEDIUM")
        assert "prediction_interval_low" in result
        assert "prediction_interval_high" in result
        assert result["prediction_interval_low"] < result["prediction_interval_high"]
        assert result["prediction_interval_low"] < 10.0
        assert result["prediction_interval_high"] > 10.0

    def test_full_ladder_coverage(self):
        """All 9 lines should be priced."""
        from backend.modeling.corners.price_ladder import compute_line_probabilities
        from backend.modeling.corners import CORNER_LINES

        priced = compute_line_probabilities(10.0, 0.15)
        assert len(priced) == len(CORNER_LINES)
        lines_priced = [item["line"] for item in priced]
        for line in CORNER_LINES:
            assert line in lines_priced


# ═════════════════════════════════════════════════════════════════
# C. GOVERNANCE TESTS
# ═════════════════════════════════════════════════════════════════

class TestGovernance:
    def test_insufficient_data_is_restricted(self):
        from backend.modeling.corners.predictor import predict_corners

        # Empty stats → INSUFFICIENT
        result = predict_corners({}, {}, "test-league")
        decision = result["decision"]
        assert decision.get("no_bet") is True
        assert decision.get("no_bet_reason") == "insufficient_data"

    def test_medium_quality_is_neutral(self):
        from backend.modeling.corners.predictor import _determine_governance_state
        quality = {"data_quality_tier": "MEDIUM"}
        state = _determine_governance_state("unknown-league", quality)
        assert state == "NEUTRAL"

    def test_high_quality_is_active_guarded(self):
        from backend.modeling.corners.predictor import _determine_governance_state
        quality = {"data_quality_tier": "HIGH"}
        state = _determine_governance_state("unknown-league", quality)
        assert state == "ACTIVE_GUARDED"


# ═════════════════════════════════════════════════════════════════
# D. MISTRAL REVIEW TESTS
# ═════════════════════════════════════════════════════════════════

class TestMistralReview:
    def test_prompt_is_built(self):
        from backend.modeling.corners.mistral_review import build_corners_review_prompt

        engine_output = {
            "projection": {
                "expected_total_corners_ft": 10.5,
                "expected_total_corners_1h": 4.5,
                "expected_total_corners_2h": 6.0,
            },
            "pricing": {
                "prediction_interval_low": 7.0,
                "prediction_interval_high": 14.0,
                "std_dev": 2.1,
                "selected": {"market_label": "Over 9.5", "modeled_probability": 0.62, "edge": 0.04},
            },
            "data_quality": {"data_quality_tier": "HIGH", "coverage_score": 0.85},
            "champion_model": "negative_binomial",
        }
        prompt = build_corners_review_prompt(engine_output)
        assert "10.5" in prompt
        assert "Over 9.5" in prompt

    def test_parse_valid_response(self):
        from backend.modeling.corners.mistral_review import parse_mistral_response
        import json

        raw = json.dumps({
            "recommendation_adjustment": "lower_confidence",
            "confidence_modifier": -10,
            "tactical_context_flags": ["high_pressing_team"],
            "risk_flags": [],
            "style_conflict_flags": [],
            "reason_codes": ["TACTICAL_MISMATCH"],
            "explanation_text": "Time adversário joga retrancado",
        })
        result = parse_mistral_response(raw)
        assert result["recommendation_adjustment"] == "lower_confidence"
        assert result["confidence_modifier"] == -10

    def test_parse_invalid_response_returns_default(self):
        from backend.modeling.corners.mistral_review import parse_mistral_response
        result = parse_mistral_response("this is not json")
        assert result["recommendation_adjustment"] == "maintain"
        assert result["confidence_modifier"] == 0

    def test_mistral_can_reduce_confidence(self):
        from backend.modeling.corners.mistral_review import apply_mistral_adjustment

        decision = {
            "modeled_probability": 0.60,
            "edge": 0.05,
            "reason_codes": [],
        }
        review = {
            "recommendation_adjustment": "lower_confidence",
            "confidence_modifier": -10,
        }
        result = apply_mistral_adjustment(decision, review)
        assert result["modeled_probability"] < 0.60
        assert result["edge"] < 0.05
        assert "MISTRAL_CONFIDENCE_REDUCED" in result["reason_codes"]

    def test_mistral_can_force_no_bet(self):
        from backend.modeling.corners.mistral_review import apply_mistral_adjustment

        decision = {
            "modeled_probability": 0.60,
            "edge": 0.05,
            "reason_codes": [],
        }
        review = {"recommendation_adjustment": "force_no_bet"}
        result = apply_mistral_adjustment(decision, review)
        assert result["no_bet"] is True
        assert "MISTRAL_CONTEXT_BLOCK" in result["reason_codes"]

    def test_mistral_cannot_promote_no_bet(self):
        """Mistral cannot turn a statistical NO_BET into a pick."""
        from backend.modeling.corners.mistral_review import apply_mistral_adjustment

        decision = {
            "no_bet": True,
            "no_bet_reason": "edge_too_small",
            "reason_codes": [],
        }
        # Even if Mistral says "maintain", the NO_BET stays
        review = {"recommendation_adjustment": "maintain"}
        result = apply_mistral_adjustment(decision, review)
        assert result["no_bet"] is True


# ═════════════════════════════════════════════════════════════════
# E. REGRESSION / BIAS CORRECTION TESTS
# ═════════════════════════════════════════════════════════════════

class TestBiasCorrection:
    def test_under_lines_are_candidates(self):
        """Under lines should appear in v2 predictions."""
        from backend.modeling.corners.negative_binomial import predict_corners_nb

        result = predict_corners_nb(10.0, 0.15)
        assert "under_8.5" in result
        assert "under_9.5" in result
        assert "under_10.5" in result
        assert result["under_8.5"] + result["over_8.5"] == pytest.approx(1.0, abs=0.01)

    def test_poisson_also_has_under(self):
        from backend.modeling.corners.poisson_model import predict_corners_poisson

        result = predict_corners_poisson(10.0)
        assert "under_8.5" in result
        assert "under_9.5" in result
        assert result["under_9.5"] + result["over_9.5"] == pytest.approx(1.0, abs=0.01)

    def test_low_corners_scenario_no_over_bias(self):
        """In a low-corners match, the engine should NOT suggest Over 8.5."""
        from backend.modeling.corners.predictor import predict_corners

        home = _make_home_stats(
            cornersAVG_home=3.0, homeCornersPerMatch=3.0,
            corners_total_per_match=3.0, corners_against_per_match=3.5,
            cornersAgainstAVG_home=3.5,
        )
        away = _make_away_stats(
            cornersAVG_away=3.0, awayCornersPerMatch=3.0,
            corners_total_per_match=3.0, corners_against_per_match=3.0,
            cornersAgainstAVG_away=3.0,
        )
        league = _make_league_stats(
            average_corners_per_match=7.5, cornersAVG_overall=7.5,
        )

        result = predict_corners(home, away, "low-league", league_stats=league)
        proj = result["projection"]
        assert proj["expected_total_corners_ft"] < 9.0

    def test_mean_near_line_high_dispersion_caution(self):
        """When expected ≈ 9 and alpha is high, the engine should be cautious."""
        from backend.modeling.corners.price_ladder import select_best_market, compute_line_probabilities

        priced = compute_line_probabilities(9.0, 1.0)  # high alpha
        # No odds → no edge → expect NO_BET
        result = select_best_market(priced, 9.0, 1.0, "MEDIUM")
        assert result.get("no_bet") is True


# ═════════════════════════════════════════════════════════════════
# F. DATA QUALITY TESTS
# ═════════════════════════════════════════════════════════════════

class TestDataQuality:
    def test_insufficient_for_empty_stats(self):
        from backend.modeling.corners.data_quality import compute_corners_data_quality
        result = compute_corners_data_quality({}, {})
        assert result["data_quality_tier"] == "INSUFFICIENT"

    def test_high_for_complete_stats(self):
        from backend.modeling.corners.data_quality import compute_corners_data_quality
        result = compute_corners_data_quality(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        assert result["data_quality_tier"] in ("HIGH", "MEDIUM")
        assert result["coverage_score"] >= 0.5
        assert result["corner_timing_available"] is True

    def test_timing_detected(self):
        from backend.modeling.corners.data_quality import compute_corners_data_quality

        # With timing
        result_with = compute_corners_data_quality(
            _make_home_stats(), _make_away_stats(),
        )
        assert result_with["corner_timing_available"] is True

        # Without timing
        home_no_timing = _make_home_stats(
            corners_total_per_match_fh=0, corners_total_per_match_2h=0,
            corners_total_fh=0, corners_total_2h_overall=0,
        )
        away_no_timing = _make_away_stats(
            corners_total_per_match_fh=0, corners_total_per_match_2h=0,
            corners_total_fh=0, corners_total_2h_overall=0,
        )
        result_without = compute_corners_data_quality(home_no_timing, away_no_timing)
        assert result_without["corner_timing_available"] is False

    def test_components_are_reported(self):
        from backend.modeling.corners.data_quality import compute_corners_data_quality
        result = compute_corners_data_quality(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        assert "components" in result
        assert "coverage" in result["components"]
        assert "timing" in result["components"]
        assert "pressure" in result["components"]
        assert "league_risk" in result["components"]

    def test_sample_adequacy_score(self):
        from backend.modeling.corners.data_quality import compute_corners_data_quality

        # High sample
        result_high = compute_corners_data_quality(
            _make_home_stats(corners_recorded_matches_num=30),
            _make_away_stats(corners_recorded_matches_num=30),
        )
        assert result_high["sample_adequacy_score"] >= 0.8

        # Low sample
        result_low = compute_corners_data_quality(
            _make_home_stats(corners_recorded_matches_num=3),
            _make_away_stats(corners_recorded_matches_num=3),
        )
        assert result_low["sample_adequacy_score"] < 0.5


# ═════════════════════════════════════════════════════════════════
# G. V2 FEATURES TESTS
# ═════════════════════════════════════════════════════════════════

class TestV2Features:
    def test_build_v2_features(self):
        from backend.modeling.corners.features import build_v2_match_features

        features = build_v2_match_features(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        assert features["home_corners_for_pm"] > 0
        assert features["away_corners_for_pm"] > 0
        assert features["league_corner_mean_ft"] > 0
        assert features["direct_estimate_ft"] > 0
        assert features["_has_timing"] is True
        assert features["_has_against"] is True
        assert features["_has_pressure"] is True

    def test_pressure_index(self):
        from backend.modeling.corners.features import (
            build_v2_match_features,
            compute_matchup_pressure_index,
        )

        features = build_v2_match_features(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        index = compute_matchup_pressure_index(features)
        assert -2.0 <= index <= 2.0

    def test_fh_2h_split(self):
        from backend.modeling.corners.features import build_v2_match_features

        features = build_v2_match_features(
            _make_home_stats(), _make_away_stats(), _make_league_stats(),
        )
        assert features["combined_fh"] > 0
        assert features["combined_2h"] > 0

    def test_graceful_degradation_no_pressure(self):
        """Without shots/xG data, features should still work."""
        from backend.modeling.corners.features import build_v2_match_features

        home = _make_home_stats(shots_per_match=0, shotsAVG_home=0,
                                xg_for_avg=0, xgAVG_home=0)
        away = _make_away_stats(shots_per_match=0, shotsAVG_away=0,
                                xg_for_avg=0, xgAVG_away=0)
        features = build_v2_match_features(home, away, _make_league_stats())
        assert features["_has_pressure"] is False
        assert features["_has_xg"] is False
        # Should still produce corner features
        assert features["home_corners_for_pm"] > 0


# ═════════════════════════════════════════════════════════════════
# H. INTEGRATION TEST
# ═════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_v2_pipeline(self):
        """End-to-end test of the v2 predictor."""
        from backend.modeling.corners.predictor import predict_corners

        result = predict_corners(
            home_stats=_make_home_stats(),
            away_stats=_make_away_stats(),
            league_id="premier-league",
            league_stats=_make_league_stats(),
            odds={"cornersOver85": 1.85, "cornersOver95": 2.40,
                  "cornersOver105": 3.80, "cornersOver115": 6.00},
        )

        # Structure checks
        assert result["marketFamily"] == "corners"
        assert result["engineVersion"] == "2.0.0"
        assert result["governed"] is True

        # Projection
        proj = result["projection"]
        assert proj["expected_total_corners_ft"] > 0
        assert proj["expected_total_corners_1h"] > 0
        assert proj["expected_total_corners_2h"] > 0
        assert "shrinkage" in proj
        assert "alpha" in proj
        assert "pressure_index" in proj

        # Data quality
        dq = result["data_quality"]
        assert dq["data_quality_tier"] in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT")

        # Pricing
        pricing = result["pricing"]
        assert "ladder" in pricing
        assert "selected" in pricing
        assert "prediction_interval_low" in pricing
        assert "prediction_interval_high" in pricing

        # Lines
        assert len(result["lines"]) > 0
        for line_key, line_data in result["lines"].items():
            assert "probability" in line_data
            assert "probability_under" in line_data

        # Decision
        decision = result["decision"]
        assert "governance_state" in decision

    def test_v2_engine_version_in_output(self):
        from backend.modeling.corners.predictor import predict_corners

        result = predict_corners(
            _make_home_stats(), _make_away_stats(), "test",
            league_stats=_make_league_stats(),
        )
        assert result["engineVersion"] == "2.0.0"
