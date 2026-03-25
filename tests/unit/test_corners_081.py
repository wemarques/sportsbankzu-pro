"""Tests for champion_selector NB2 preference (#081)."""

import pytest

from backend.modeling.corners.champion_selector import (
    NB2_PREFERENCE_THRESHOLD,
    select_champion_for_line,
)


def _make_metrics(brier=0.15, logloss=0.40, ece=0.08, stability=0.15, roi=0.05, sample_size=50, drift=0.03):
    return {
        "brier": brier,
        "logloss": logloss,
        "ece": ece,
        "stability": stability,
        "roi_theoretical": roi,
        "sample_size": sample_size,
        "drift": drift,
    }


def test_nb2_wins_when_within_threshold():
    """NB2 should be swapped in when gap <= 2% of best score."""
    model_metrics = {
        "poisson": _make_metrics(brier=0.14, logloss=0.38),        # slightly better
        "negative_binomial": _make_metrics(brier=0.1405, logloss=0.381),  # within 2%
        "ml_regression": _make_metrics(brier=0.25, logloss=0.60),  # much worse
    }
    result = select_champion_for_line(model_metrics, 9.5, "test-league")

    assert result["champion_model"] == "negative_binomial"
    assert result["selection_method"] == "composite_score_nb2_preference"


def test_nb2_does_not_win_when_gap_too_large():
    """NB2 should NOT be swapped when gap > 2%."""
    model_metrics = {
        "poisson": _make_metrics(brier=0.12, logloss=0.35),        # clearly better
        "negative_binomial": _make_metrics(brier=0.20, logloss=0.55),  # much worse
        "ml_regression": _make_metrics(brier=0.25, logloss=0.60),
    }
    result = select_champion_for_line(model_metrics, 9.5, "test-league")

    assert result["champion_model"] == "poisson"
    assert result["selection_method"] == "composite_score"


def test_nb2_already_champion_no_swap():
    """When NB2 is already the best, no swap needed — method stays 'composite_score'."""
    model_metrics = {
        "poisson": _make_metrics(brier=0.20, logloss=0.55),
        "negative_binomial": _make_metrics(brier=0.12, logloss=0.35),  # clearly best
        "ml_regression": _make_metrics(brier=0.25, logloss=0.60),
    }
    result = select_champion_for_line(model_metrics, 9.5, "test-league")

    assert result["champion_model"] == "negative_binomial"
    assert result["selection_method"] == "composite_score"


def test_nb2_ineligible_not_considered():
    """Ineligible NB2 (ECE > 0.15) should NOT be swapped in."""
    model_metrics = {
        "poisson": _make_metrics(brier=0.14, logloss=0.38),
        "negative_binomial": _make_metrics(brier=0.1405, logloss=0.381, ece=0.20),  # ineligible: ECE > 0.15
        "ml_regression": _make_metrics(brier=0.25, logloss=0.60),
    }
    result = select_champion_for_line(model_metrics, 9.5, "test-league")

    assert result["champion_model"] == "poisson"
    assert result["selection_method"] == "composite_score"
