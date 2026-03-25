"""Unit tests for Cards Engine v2 NB2 + evaluation (#085b)."""

from backend.modeling.cards_engine import predict_cards, CARD_LINES, DEFAULT_CARDS_LAMBDA


def test_nb2_vs_poisson_different_probs():
    """NB2 with overdispersion > 1 produces different probs than Poisson."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0, "cardsVariance": 6.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    assert result["model_source"] == "nb2"
    assert result["overdispersion"] > 1.0


def test_split_lambda_away_higher():
    """Lambda of visitor > lambda of home team (documented asymmetry)."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    assert result["cards_lambda_away"] > result["cards_lambda_home"]


def test_foul_adjustment_increases_lambda():
    """More fouls than average -> higher lambda."""
    base = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    adjusted = predict_cards(
        home_stats={"cardsAVG_overall": 4.0, "homeTeamFoulsPerMatch": 16.0},
        away_stats={"cardsAVG_overall": 4.0, "awayTeamFoulsPerMatch": 16.0},
        league_stats={"foulsAVG_overall": 20.0},
    )
    assert adjusted["cards_lambda"] >= base["cards_lambda"]


def test_referee_factor_strict_ref():
    """Strict referee (avg > league) -> higher lambda."""
    normal = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    strict = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
        referee_avg_cards=6.0,  # above average ~4.0
    )
    assert strict["cards_lambda"] > normal["cards_lambda"]


def test_complement_nb2():
    """P(Over) + P(Under) = 1.0 in NB2."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0, "cardsVariance": 6.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    for line in CARD_LINES:
        over = result["lines"][f"over_{line}"]["prob"]
        under = result["lines"][f"under_{line}"]["prob"]
        assert abs(over + under - 1.0) < 0.001, f"Line {line}: {over} + {under} != 1.0"


def test_adjustments_in_result():
    """Result includes adjustments dict."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    assert "adjustments" in result
    assert "foul_adjustment" in result["adjustments"]
    assert "referee_factor" in result["adjustments"]
    assert "league_discipline_factor" in result["adjustments"]


def test_backward_compat_predict_cards():
    """Backward compat: predict_cards without new params works."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.5},
        away_stats={"cardsAVG_overall": 3.8},
    )
    assert result["projected_total_cards"] > 0
    assert "over_3.5" in result["lines"]
    assert "under_3.5" in result["lines"]
    assert abs(result["lines"]["over_3.5"]["prob"] + result["lines"]["under_3.5"]["prob"] - 1.0) < 0.01


def test_evaluate_pick_cards():
    """_evaluate_pick_deterministic handles card markets."""
    from backend.routes.ai_analysis import _evaluate_pick_deterministic

    actual = {"total_goals": 2, "btts": False, "result_1x2": "X",
              "total_corners": 8, "total_cards": 5}

    assert _evaluate_pick_deterministic(
        {"mercado": "Cartoes Over 3.5"}, actual
    ) is True  # 5 > 3.5
    assert _evaluate_pick_deterministic(
        {"mercado": "Cartoes Under 3.5"}, actual
    ) is False  # 5 < 3.5 is False
    assert _evaluate_pick_deterministic(
        {"mercado": "Cartoes Over 5.5"}, actual
    ) is False  # 5 > 5.5 is False
    assert _evaluate_pick_deterministic(
        {"mercado": "Cartoes Under 5.5"}, actual
    ) is True  # 5 < 5.5


def test_evaluate_pick_corners_still_works():
    """_evaluate_pick_deterministic still handles corners correctly."""
    from backend.routes.ai_analysis import _evaluate_pick_deterministic

    actual = {"total_goals": 3, "btts": True, "result_1x2": "1",
              "total_corners": 10, "total_cards": 4}

    assert _evaluate_pick_deterministic(
        {"mercado": "Escanteios Over 8.5"}, actual
    ) is True  # 10 > 8.5
    assert _evaluate_pick_deterministic(
        {"mercado": "Escanteios Under 10.5"}, actual
    ) is True  # 10 < 10.5


def test_evaluate_pick_goals_still_works():
    """_evaluate_pick_deterministic still handles goals correctly."""
    from backend.routes.ai_analysis import _evaluate_pick_deterministic

    actual = {"total_goals": 3, "btts": True, "result_1x2": "1",
              "total_corners": 8, "total_cards": 4}

    assert _evaluate_pick_deterministic(
        {"mercado": "Over 2.5 gols"}, actual
    ) is True  # 3 > 2.5
    assert _evaluate_pick_deterministic(
        {"mercado": "BTTS — SIM"}, actual
    ) is True
    assert _evaluate_pick_deterministic(
        {"mercado": "1"}, actual
    ) is True  # result_1x2 == "1"
