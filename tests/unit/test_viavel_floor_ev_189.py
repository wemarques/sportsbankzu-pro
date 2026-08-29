"""#189-d — floor do VIÁVEL condicionado a EV >= 0 + estado "aguarde odd".

Auditoria 2026-08-29: o floor #148 apostava 0,5%/0,1% da banca sempre que o
Kelly dava <= 0 — o que ocorre EXATAMENTE quando EV < 0 na odd atual
(verificado: NEUTRO 52% @ odd 1.51 recebia stake com EV -21%). Agora,
EV < 0 devolve stake 0 com stake_reason="await_min_odd" e min_odd = fair
(1/prob): o pick vira ordem-limite, não aposta a mercado. O mesmo vale
para o modo Oportunidade, cujo "desconto por EV negativo" também apostava
com valor esperado negativo.
"""
import pytest

from backend.services.bankroll_engine import (
    VIAVEL_FLOOR_PCT,
    compute_stake,
    compute_stake_oportunidade,
)


def _mercado(prob, odd, classification="NEUTRO"):
    return {
        "classification": classification,
        "odds_available": True,
        "book_odd": odd,
        "calibrated_probability": prob,
        "reason_codes": [],
        "data_quality_score": 1.0,
    }


BANK = 1000.0


# ── modo Kelly (compute_stake) ────────────────────────────────────────

def test_viavel_ev_negativo_vira_await_min_odd():
    """O caso da auditoria: 52% @ 1.51 (EV -21%) não recebe mais stake."""
    r = compute_stake(_mercado(0.52, 1.51), BANK)
    assert r["stake"] == 0.0
    assert r["stake_reason"] == "await_min_odd"
    assert r["min_odd"] == pytest.approx(round(1 / 0.52, 2))
    assert r["ev"] < 0


def test_viavel_ev_levemente_negativo_tambem_aguarda():
    """Direction-rescue (EV entre -5% e 0) também não aposta a mercado."""
    r = compute_stake(_mercado(0.52, 1.90), BANK)  # EV -1.2%
    assert r["stake"] == 0.0
    assert r["stake_reason"] == "await_min_odd"


def test_viavel_ev_zero_mantem_floor():
    """Odd exatamente na fair (EV = 0): floor #148 preservado."""
    prob = 0.52
    r = compute_stake(_mercado(prob, 1 / prob), BANK)
    assert r["stake"] == pytest.approx(BANK * VIAVEL_FLOOR_PCT, abs=0.01)
    assert r["stake_reason"] == "quarter_kelly_viavel"


def test_viavel_ev_positivo_kelly_normal():
    r = compute_stake(_mercado(0.56, 1.90), BANK)  # EV +6.4%
    assert r["stake"] > 0
    assert r["stake_reason"] == "quarter_kelly_viavel"
    assert r["kelly_raw"] > 0


def test_safe_ev_positivo_inalterado():
    r = compute_stake(_mercado(0.62, 1.80, "SAFE"), BANK)  # EV +11.6%
    assert r["stake"] > 0
    assert r["stake_reason"] == "kelly_calculated"


# ── modo Oportunidade (compute_stake_oportunidade) ───────────────────

def test_oportunidade_ev_negativo_vira_await_min_odd():
    r = compute_stake_oportunidade(_mercado(0.55, 1.60, "NEUTRO_QUALIFICADO"), BANK)  # EV -12%
    assert r["stake"] == 0.0
    assert r["stake_reason"] == "await_min_odd"
    assert r["min_odd"] == pytest.approx(round(1 / 0.55, 2))


def test_oportunidade_ev_positivo_stake_normal():
    r = compute_stake_oportunidade(_mercado(0.58, 1.90, "NEUTRO_QUALIFICADO"), BANK)  # EV +10.2%
    assert r["stake"] > 0
    assert r["stake_reason"] == "oportunidade"
    assert r["desconto_ev"] == pytest.approx(1.0)


def test_oportunidade_sem_odd_continua_bloqueado():
    m = _mercado(0.58, None, "NEUTRO_QUALIFICADO")
    m["odds_available"] = False
    r = compute_stake_oportunidade(m, BANK)
    assert r["stake"] == 0.0
    assert r["stake_reason"] == "no_real_odds"
