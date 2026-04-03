"""Unit tests for Cards Engine (#085)."""

from backend.modeling.cards_engine import predict_cards, CARD_LINES, DEFAULT_CARDS_LAMBDA


def test_predict_cards_basic():
    """Basic card projection works."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.5},
        away_stats={"cardsAVG_overall": 3.8},
    )
    assert result["projected_total_cards"] > 0
    assert "over_3.5" in result["lines"]
    assert "under_3.5" in result["lines"]
    assert abs(result["lines"]["over_3.5"]["prob"] + result["lines"]["under_3.5"]["prob"] - 1.0) < 0.01


def test_predict_cards_complement():
    """P(Over) + P(Under) = 1.0 for all lines."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    for line in CARD_LINES:
        over = result["lines"][f"over_{line}"]["prob"]
        under = result["lines"][f"under_{line}"]["prob"]
        assert abs(over + under - 1.0) < 0.001, f"Line {line}: {over} + {under} != 1.0"


def test_predict_cards_fallback_default():
    """Without data, uses DEFAULT_CARDS_LAMBDA."""
    result = predict_cards(
        home_stats={},
        away_stats={},
    )
    assert abs(result["cards_lambda"] - DEFAULT_CARDS_LAMBDA) < 0.01


def test_predict_cards_multiplier():
    """Cards multiplier is applied to lambda."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
        league_id="test-league",
    )
    # No calibrated multiplier → defaults to 1.0
    assert result["cards_multiplier"] == 1.0
    assert result["cards_lambda"] == result["cards_lambda_raw"]


def test_card_lines_correct():
    """Card lines expanded 1.5-6.5 (#110)."""
    assert CARD_LINES == [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]


def test_high_lambda_favors_over():
    """High lambda → Over more probable."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 6.0},
        away_stats={"cardsAVG_overall": 6.0},
    )
    # With lambda ~6, Over 3.5 should have prob > 80%
    assert result["lines"]["over_3.5"]["prob"] > 0.80


def test_low_lambda_favors_under():
    """Low lambda → Under more probable."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 2.0},
        away_stats={"cardsAVG_overall": 2.0},
    )
    # With lambda ~2, Under 3.5 should have prob > 70%
    assert result["lines"]["under_3.5"]["prob"] > 0.70
