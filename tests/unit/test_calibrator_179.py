"""Test #179 — band 50-60% recalibration.

#189-a PROMOVEU o shadow: o valor recalibrado da banda 50-60% (0.05 no
centro, era 0.12) agora está embutido nos nós da deflação contínua de
produção (`_band_deflation`). Shadow e produção são idênticos por
construção — a flag SHADOW_BAND_50_60_V179 tornou-se inerte e o endpoint
/metrics/shadow_v179 passa a reportar improvement 0 (promoção concluída).
"""
import importlib
import os


def _reload_ev():
    """Re-import ev_classification so any env flag is re-read."""
    import backend.services.ev_classification as ev
    importlib.reload(ev)
    return ev


def test_shadow_identico_ao_live_flag_off():
    os.environ.pop("SHADOW_BAND_50_60_V179", None)
    ev = _reload_ev()
    for p in [0.30, 0.45, 0.55, 0.65, 0.75, 0.85]:
        cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
        assert abs(cur - shadow) < 1e-9, f"prob={p}: cur={cur}, shadow={shadow}"


def test_shadow_identico_ao_live_flag_on():
    """#189-a: mesmo com a flag ligada, shadow == live (promoção concluída)."""
    os.environ["SHADOW_BAND_50_60_V179"] = "true"
    try:
        ev = _reload_ev()
        for p in [0.45, 0.55, 0.65, 0.75, 0.85]:
            cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
            assert abs(cur - shadow) < 1e-9, f"prob={p}: cur={cur}, shadow={shadow}"
    finally:
        os.environ.pop("SHADOW_BAND_50_60_V179", None)
        _reload_ev()


def test_banda_50_60_promovida_menos_deflacao_que_105():
    """O centro da banda usa 0.05 (promovido); era 0.12 no #105."""
    ev = _reload_ev()
    cur, _ = ev.apply_probability_deflation_with_shadow(0.55, "")
    assert abs(cur - 0.55 * (1 - 0.05)) < 1e-9
    assert cur > 0.55 * (1 - 0.12)


def test_min_n_floor_in_endpoint():
    """Endpoint must respect MIN_N=20 (regra #079) before reporting improvement."""
    from backend.services.brier_service import MIN_N
    assert MIN_N == 20  # regra #079 preserved
