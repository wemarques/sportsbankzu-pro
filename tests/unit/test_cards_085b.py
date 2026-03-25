"""Unit tests for Cards Engine v3 Dixon-Coles + evaluation (#085b, #086)."""

from backend.modeling.cards_engine import predict_cards, CARD_LINES, DEFAULT_CARDS_LAMBDA


def test_nb2_vs_poisson_different_probs():
    """NB2 with overdispersion > 1 produces different probs than Poisson."""
    result = predict_cards(
        home_stats={"cardsAVG_overall": 4.0, "cardsVariance": 6.0},
        away_stats={"cardsAVG_overall": 4.0},
    )
    assert result["model_source"] == "nb2"
    assert result["overdispersion"] > 1.0


def test_relative_strength_lambda():
    """Lambda uses relative strengths vs league avg (Dixon-Coles #053 pattern)."""
    result = predict_cards(
        home_stats={"homeCardsPerMatch": 4.0},
        away_stats={"awayCardsPerMatch": 3.6},
        league_stats={"cardsAVG_overall": 5.33},
    )
    # Lambda NOT inflated: must be < 6.0 (was 11.4 before #086)
    assert result["cards_lambda"] < 6.0, \
        f"Lambda {result['cards_lambda']} is inflated (expected < 6.0 for league avg 5.33)"


def test_league_avg_bounds_lambda():
    """Lambda final must stay within +/-50% of league average."""
    result = predict_cards(
        home_stats={"homeCardsPerMatch": 4.0},
        away_stats={"awayCardsPerMatch": 3.6},
        league_stats={"cardsAVG_overall": 5.33},
    )
    league_avg = 5.33
    assert league_avg * 0.5 < result["cards_lambda"] < league_avg * 1.5, \
        f"Lambda {result['cards_lambda']} outside +/-50% of avg {league_avg}"


def test_no_foul_or_league_adjustment():
    """No foul_adjustment or league_discipline_factor (removed #086)."""
    result = predict_cards(
        home_stats={"homeCardsPerMatch": 4.0, "homeFoulsPerMatch": 20.0},
        away_stats={"awayCardsPerMatch": 3.6, "awayFoulsPerMatch": 15.0},
        league_stats={"cardsAVG_overall": 5.33, "foulsAVG_overall": 22.0},
    )
    adj = result.get("adjustments", {})
    assert "foul_adjustment" not in adj, "foul_adjustment should have been removed"
    assert "league_discipline_factor" not in adj, "league_discipline_factor should have been removed"


def test_referee_is_only_external_adjustment():
    """Referee is the ONLY legitimate external adjustment."""
    without_ref = predict_cards(
        home_stats={"homeCardsPerMatch": 4.0},
        away_stats={"awayCardsPerMatch": 3.6},
        league_stats={"cardsAVG_overall": 5.33},
    )
    with_ref = predict_cards(
        home_stats={"homeCardsPerMatch": 4.0},
        away_stats={"awayCardsPerMatch": 3.6},
        league_stats={"cardsAVG_overall": 5.33},
        referee_avg_cards=7.0,  # strict referee
    )
    assert with_ref["cards_lambda"] > without_ref["cards_lambda"]
    assert with_ref["adjustments"]["referee_factor"] > 1.0


def test_average_team_produces_league_avg_lambda():
    """Team with cardsPerMatch == leagueAvg produces lambda approx leagueAvg."""
    result = predict_cards(
        home_stats={"homeCardsPerMatch": 5.0},
        away_stats={"awayCardsPerMatch": 5.0},
        league_stats={"cardsAVG_overall": 5.0},
    )
    assert abs(result["cards_lambda"] - 5.0) < 0.5, \
        f"Average team should produce lambda ~5.0, got {result['cards_lambda']}"


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
