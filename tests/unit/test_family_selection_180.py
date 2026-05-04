"""Test #180 — family pick selection."""
import os
import importlib


def _pick(market, classification="VIÁVEL", ev=0.0, prob_central=0.55, delta_brier=0.0):
    return {
        "mercado": market,
        "classification": classification,
        "ev_pct": ev,
        "delta_brier": delta_brier,
        "prob_central": prob_central,
    }


def _reload_module():
    import backend.services.family_selection as fs
    importlib.reload(fs)
    return fs


def test_two_goals_picks_only_one_winner():
    os.environ["ENABLE_FAMILY_SELECTION_180"] = "true"
    fs = _reload_module()
    picks = [
        _pick("Over 1.5 gols", ev=2.0, prob_central=0.68),
        _pick("Under 3.5 gols", ev=5.0, prob_central=0.57),
    ]
    fs.select_family_winners(picks)
    winners = [p for p in picks if p["family_winner"]]
    assert len(winners) == 1
    assert winners[0]["mercado"] == "Under 3.5 gols"  # higher EV


def test_different_families_all_winners():
    os.environ["ENABLE_FAMILY_SELECTION_180"] = "true"
    fs = _reload_module()
    picks = [
        _pick("Over 1.5 gols", ev=2.0),
        _pick("Escanteios Over 8.5", ev=3.0),
        _pick("Cartoes Over 2.5", ev=1.5),
    ]
    fs.select_family_winners(picks)
    assert all(p["family_winner"] for p in picks)


def test_disabled_flag_marks_all_winners():
    os.environ["ENABLE_FAMILY_SELECTION_180"] = "false"
    fs = _reload_module()
    picks = [
        _pick("Over 1.5 gols", ev=2.0),
        _pick("Under 3.5 gols", ev=5.0),
    ]
    fs.select_family_winners(picks)
    assert all(p["family_winner"] for p in picks)


def test_btts_is_in_goals_family():
    os.environ["ENABLE_FAMILY_SELECTION_180"] = "true"
    fs = _reload_module()
    picks = [
        _pick("Over 1.5 gols", ev=2.0),
        _pick("BTTS — SIM", ev=5.0),
    ]
    fs.select_family_winners(picks)
    winners = [p for p in picks if p["family_winner"]]
    assert len(winners) == 1
    assert "BTTS" in winners[0]["mercado"]


def test_safe_beats_neutro_qualificado():
    os.environ["ENABLE_FAMILY_SELECTION_180"] = "true"
    fs = _reload_module()
    picks = [
        _pick("Over 2.5 gols", classification="NEUTRO_QUALIFICADO", ev=10.0),
        _pick("Under 3.5 gols", classification="SAFE", ev=2.0),
    ]
    fs.select_family_winners(picks)
    winners = [p for p in picks if p["family_winner"]]
    assert winners[0]["classification"] == "SAFE"  # cls beats EV


def test_market_family_wrapper_works():
    """Verify public wrapper of _market_family is importable and equivalent."""
    from backend.services.bankroll_engine import market_family, _market_family
    for m in ("Over 2.5 gols", "Escanteios Over 9.5", "Cartoes Over 2.5", "Casa", "Empate", "BTTS Sim"):
        assert market_family(m) == _market_family(m)
