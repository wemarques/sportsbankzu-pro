"""Unit tests for Metrics Integration (#084)."""

from backend.services.backtesting import (
    compute_implied_odds_brier,
    compute_sharpe_ratio,
    compute_calibration_bins,
    compute_roi,
)


def test_implied_odds_brier_model_better():
    """When model predicts better than odds, model_vs_house is negative."""
    picks = [
        {"odd": 2.0, "prob": 0.60, "outcome": True},   # model 60%, house 50%
        {"odd": 2.0, "prob": 0.60, "outcome": True},
        {"odd": 2.0, "prob": 0.60, "outcome": False},
        {"odd": 2.0, "prob": 0.40, "outcome": False},   # model 40%, house 50%
    ]
    result = compute_implied_odds_brier(picks)
    assert result["model_beats_house"] is True
    assert result["model_vs_house"] < 0
    assert result["n"] == 4


def test_implied_odds_brier_empty():
    """No valid picks returns None."""
    result = compute_implied_odds_brier([])
    assert result["brier_implied"] is None
    assert result["n"] == 0


def test_sharpe_in_batch_summary():
    """Sharpe works with cron format picks."""
    picks = [{"odd": 2.0, "outcome": True, "stake": 1.0}] * 30 + \
            [{"odd": 2.0, "outcome": False, "stake": 1.0}] * 30
    result = compute_sharpe_ratio(picks)
    assert result["n_bets"] == 60
    assert result["sharpe"] is not None


def test_calibration_bins_with_cron_format():
    """Calibration bins works with list[dict] format."""
    import random
    random.seed(42)
    preds = []
    for _ in range(50):
        p = random.uniform(0.4, 0.8)
        outcome = 1 if random.random() < p else 0
        preds.append({"prob": p, "outcome": outcome})
    result = compute_calibration_bins(preds)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "predicted_avg" in result[0]
    assert "actual_avg" in result[0]
    assert "count" in result[0]


def test_roi_with_cron_format():
    """ROI works with cron format picks."""
    picks = [
        {"odd": 2.0, "outcome": True, "stake": 1.0},
        {"odd": 2.0, "outcome": False, "stake": 1.0},
        {"odd": 3.0, "outcome": True, "stake": 1.0},
    ]
    result = compute_roi(picks)
    assert result["n_bets"] == 3
    assert result["roi_pct"] is not None
    # 2 wins (2.0 + 3.0 = 5.0 returned) vs 3.0 staked = 66.67% ROI
    assert result["roi_pct"] > 0


def test_model_worse_than_house_pattern():
    """When model is worse than house, pattern is detected."""
    from backend.services.post_match_diagnostic import detect_patterns
    batch_summary = {
        "odds_baseline": {
            "brier_model": 0.220,
            "brier_implied": 0.200,
            "model_vs_house": 0.020,
            "model_beats_house": False,
            "n": 50,
        }
    }
    report = detect_patterns([], batch_summary=batch_summary)
    types = [p["type"] for p in report.get("patterns", [])]
    assert "MODEL_WORSE_THAN_HOUSE" in types
