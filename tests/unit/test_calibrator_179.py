"""Test #179 — band 50-60% shadow recalibration."""
import importlib
import os


def _reload_ev():
    """Re-import ev_classification so the SHADOW_BAND_50_60_V179 module-level
    constant picks up the current env value.
    """
    import backend.services.ev_classification as ev
    importlib.reload(ev)
    return ev


def test_shadow_disabled_returns_identical():
    """When env flag is false, shadow output == current output for every band."""
    os.environ.pop("SHADOW_BAND_50_60_V179", None)
    ev = _reload_ev()

    for p in [0.30, 0.45, 0.55, 0.65, 0.75, 0.85]:
        cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
        assert abs(cur - shadow) < 1e-9, f"prob={p} expected identical, got cur={cur}, shadow={shadow}"


def test_shadow_enabled_diverges_in_band_50_60():
    """When enabled, shadow > current for prob in [0.50, 0.60); magnitude matches spec."""
    os.environ["SHADOW_BAND_50_60_V179"] = "true"
    try:
        ev = _reload_ev()

        cur, shadow = ev.apply_probability_deflation_with_shadow(0.55, "")
        assert shadow > cur, f"shadow={shadow} should be > current={cur}"

        # Magnitude: shadow uses 0.05 deflation, current uses 0.12.
        expected_shadow = 0.55 * (1 - 0.05)
        expected_current = 0.55 * (1 - 0.12)
        assert abs(shadow - expected_shadow) < 1e-9
        assert abs(cur - expected_current) < 1e-9
    finally:
        os.environ.pop("SHADOW_BAND_50_60_V179", None)
        _reload_ev()


def test_shadow_enabled_identical_outside_band():
    """For prob >=0.60 or <0.50, shadow == current even when enabled."""
    os.environ["SHADOW_BAND_50_60_V179"] = "true"
    try:
        ev = _reload_ev()

        for p in [0.45, 0.65, 0.75, 0.85]:
            cur, shadow = ev.apply_probability_deflation_with_shadow(p, "")
            assert abs(cur - shadow) < 1e-9, f"prob={p} should be identical (got cur={cur}, shadow={shadow})"
    finally:
        os.environ.pop("SHADOW_BAND_50_60_V179", None)
        _reload_ev()


def test_min_n_floor_in_endpoint():
    """Endpoint must respect MIN_N=20 (regra #079) before reporting improvement."""
    from backend.services.brier_service import MIN_N
    assert MIN_N == 20  # regra #079 preserved
