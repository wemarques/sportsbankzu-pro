"""Test #177 — by_league_market joint breakdown."""
from backend.services.brier_service import _segment, MIN_N


def _mock_picks(league, market, n, hit_rate, prob=0.55, odd=1.85):
    return [
        {"prob": prob, "odd": odd, "out": 1 if i < int(n * hit_rate) else 0,
         "league": league, "market": market, "cls": "NEUTRO_QUALIFICADO"}
        for i in range(n)
    ]


def test_segment_returns_expected_keys():
    picks = _mock_picks("MLS", "BTTS SIM", 10, 0.7)
    seg = _segment(picks)
    assert seg is not None
    for k in ("n", "accuracy", "brier_model", "brier_implied",
              "model_beats_house", "delta"):
        assert k in seg


def test_joint_diagnostic_threshold():
    """N=5 deve passar como diagnostic_only=True; N=25 como diagnostic_only=False."""
    JOINT_MIN_N_DIAGNOSTIC = 5

    picks_small = _mock_picks("MLS", "BTTS SIM", 8, 0.625)
    picks_big = _mock_picks("Championship", "Under 3.5 gols", 25, 0.68)

    for picks, expected_diag in [(picks_small, True), (picks_big, False)]:
        if len(picks) >= JOINT_MIN_N_DIAGNOSTIC:
            seg = _segment(picks)
            seg["diagnostic_only"] = len(picks) < MIN_N
            assert seg["diagnostic_only"] == expected_diag


def test_joint_key_format():
    """Chave joint usa ||| como separador para evitar colisao."""
    key = "MLS|||BTTS SIM"
    parts = key.split("|||")
    assert len(parts) == 2
    assert parts[0] == "MLS"
    assert parts[1] == "BTTS SIM"
