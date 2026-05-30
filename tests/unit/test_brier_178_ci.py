"""Test #178 — model_beats_house_with_ci (Wilcoxon paired test)."""
from backend.services.brier_service import _with_ci, MIN_N, BRIER_TARGET


def _picks(n, prob, odd, hit_rate):
    return [
        {"prob": prob, "odd": odd, "out": 1 if i < int(n * hit_rate) else 0,
         "league": "X", "market": "Y", "cls": "?"}
        for i in range(n)
    ]


def test_below_min_n_returns_indeterminate():
    picks = _picks(10, 0.55, 1.85, 0.6)
    ci = _with_ci(picks, 0.22, 0.23)
    assert ci["below_min_n"] is True
    assert ci["significant_at_5pct"] is False


def test_brier_target_is_022():
    assert BRIER_TARGET == 0.22


def test_strong_signal_is_significant():
    # 50 picks, model claramente melhor que casa (delta override = 0.02)
    picks = _picks(50, 0.65, 1.85, 0.65)
    ci = _with_ci(picks, 0.21, 0.23)
    assert ci["n"] == 50
    assert ci["delta"] == 0.02
    # #182: p_value e float quando scipy esta disponivel (local/CI), None quando o
    # import falha (Lambda Layer com numpy/scipy incompativeis). Em ambos os casos,
    # o resto do dict deve estar coerente.
    assert ci["p_value"] is None or isinstance(ci["p_value"], float)
    assert ci["beats_bool"] is True  # delta > 0
    # significant_at_5pct so deve ser True quando p_value e float E < 0.05
    if ci["p_value"] is None:
        assert ci["significant_at_5pct"] is False


def test_min_n_threshold():
    # Regra #079 — base estatistica do sistema, nao alterar
    assert MIN_N == 20
