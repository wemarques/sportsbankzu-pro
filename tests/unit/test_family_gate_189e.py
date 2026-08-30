"""#189-e — gate de stake por família, alias de deflação, calibração hierárquica.

Base: decomposição de 5.505 picks auditados (29-30/08/2026) — gols/BTTS
com Δ Brier positivo vs mercado em toda liga; cartões Δ≈-0,2% uniforme;
escanteios com edge apenas em linhas extremas. Brasileirão A permanece
ativo sob a mesma política (modo correção).
"""
import pickle

import numpy as np
import pytest

from backend.services.bankroll_engine import (
    compute_stake,
    compute_stake_oportunidade,
    family_stake_allowed,
)
from backend.services.ev_classification import (
    _league_deflation_factor,
    apply_probability_deflation,
)
from backend.modeling import calibrator as cal


BANK = 1000.0


def _mercado(label, prob=0.60, odd=1.90, classification="NEUTRO_QUALIFICADO"):
    return {
        "market_type": label,
        "classification": classification,
        "odds_available": True,
        "book_odd": odd,
        "calibrated_probability": prob,
        "reason_codes": [],
        "data_quality_score": 1.0,
    }


# ── política por família ─────────────────────────────────────────────

def test_politica_familias():
    assert family_stake_allowed("Over 2.5 gols") == (True, "goals")
    assert family_stake_allowed("BTTS — SIM") == (True, "goals")
    assert family_stake_allowed("DC 1X") == (True, "1x2")
    assert family_stake_allowed("Cartoes Over 2.5") == (False, "cards")
    assert family_stake_allowed("Cartoes Under 4.5") == (False, "cards")
    assert family_stake_allowed("Escanteios Over 7.5") == (False, "corners")
    assert family_stake_allowed("Escanteios Over 10.5") == (True, "corners")
    assert family_stake_allowed("Escanteios Over 11.5") == (True, "corners")
    assert family_stake_allowed("Escanteios Under 9.5") == (True, "corners")
    assert family_stake_allowed("Escanteios Under 12.5") == (False, "corners")


def test_cartoes_bloqueado_mesmo_com_ev_positivo():
    r = compute_stake(_mercado("Cartoes Over 2.5", prob=0.65, odd=1.90), BANK)
    assert r["stake"] == 0.0
    assert r["stake_reason"] == "family_gate_cards"
    r2 = compute_stake_oportunidade(_mercado("Cartoes Over 2.5", prob=0.65, odd=1.90), BANK)
    assert r2["stake"] == 0.0
    assert r2["stake_reason"] == "family_gate_cards"


def test_escanteio_linha_media_bloqueado_extrema_liberado():
    mid = compute_stake(_mercado("Escanteios Over 7.5", prob=0.60, odd=2.00), BANK)
    assert mid["stake_reason"] == "family_gate_corners"
    ext = compute_stake(_mercado("Escanteios Over 10.5", prob=0.60, odd=2.00), BANK)
    assert ext["stake"] > 0


def test_gols_stake_pleno():
    r = compute_stake(_mercado("Over 2.5 gols", prob=0.60, odd=1.90), BANK)
    assert r["stake"] > 0
    assert r["stake_reason"] == "kelly_calculated"


# ── alias de deflação por liga (#185 no _LEAGUE_DEFLATION) ───────────

def test_alias_brasileirao_aplica_fator():
    assert _league_deflation_factor("brazil-serie-a") == pytest.approx(0.90)
    assert _league_deflation_factor("brasileirao-serie-a") == pytest.approx(0.90)
    assert _league_deflation_factor("premier-league") == pytest.approx(1.0)
    # o alias do frontend deve produzir a MESMA deflacao do id canonico
    a = apply_probability_deflation(0.70, "brazil-serie-a")
    b = apply_probability_deflation(0.70, "brasileirao-serie-a")
    assert a == pytest.approx(b)
    assert a < apply_probability_deflation(0.70, "")  # fator 0.90 aplicado


# ── calibração hierárquica família→liga ──────────────────────────────

def test_cartoes_no_calibrated_markets():
    assert "Cartoes Over 2.5" in cal.CALIBRATED_MARKETS
    assert "Cartoes Under 5.5" in cal.CALIBRATED_MARKETS


def test_market_family_label():
    assert cal._market_family_label("Cartoes Over 2.5") == "cartoes"
    assert cal._market_family_label("Escanteios Under 9.5") == "escanteios"
    assert cal._market_family_label("Over 2.5") == "gols"
    assert cal._market_family_label("BTTS") == "btts"
    assert cal._market_family_label("Double Chance 1X") == "x1x2_dc"


def test_fallback_para_modelo_de_familia(tmp_path, monkeypatch):
    """Sem modelo mercado|liga, calibrate_prob deve cair no pool da família."""
    from sklearn.isotonic import IsotonicRegression

    monkeypatch.setattr(cal, "_MODELS_DIR", tmp_path)
    iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    # calibracao sintetica: desloca +0.10
    X = np.linspace(0.3, 0.8, 40)
    iso.fit(X, np.clip(X + 0.10, 0, 1))
    key = cal._model_key(f"{cal._FAMILY_PREFIX} cartoes", "", "")
    with open(tmp_path / f"{key}.pkl", "wb") as f:
        pickle.dump(iso, f)

    out = cal.calibrate_prob(0.55, "Cartoes Over 2.5", "brasileirao-serie-a", "")
    assert out == pytest.approx(0.65, abs=0.02)  # usou o pool da familia

    # mercado de outra familia sem modelo -> passthrough
    assert cal.calibrate_prob(0.55, "Over 2.5", "brasileirao-serie-a", "") == pytest.approx(0.55)


def test_modelo_de_liga_vence_familia(tmp_path, monkeypatch):
    from sklearn.isotonic import IsotonicRegression

    monkeypatch.setattr(cal, "_MODELS_DIR", tmp_path)
    X = np.linspace(0.3, 0.8, 40)
    fam = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    fam.fit(X, np.clip(X + 0.10, 0, 1))
    liga = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    liga.fit(X, np.clip(X - 0.05, 0, 1))
    with open(tmp_path / f"{cal._model_key(cal._FAMILY_PREFIX + ' cartoes', '', '')}.pkl", "wb") as f:
        pickle.dump(fam, f)
    with open(tmp_path / f"{cal._model_key('Cartoes Over 2.5', 'brasileirao-serie-a', '')}.pkl", "wb") as f:
        pickle.dump(liga, f)

    out = cal.calibrate_prob(0.55, "Cartoes Over 2.5", "brasileirao-serie-a", "")
    assert out == pytest.approx(0.50, abs=0.02)  # celula especifica tem prioridade
