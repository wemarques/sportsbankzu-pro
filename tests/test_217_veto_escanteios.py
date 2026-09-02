"""#217 - o veto do motor de escanteios passa a ter consumidor, e a ausencia
de contagem de jogos deixa de se disfarcar de inicio de temporada."""
import os
import pytest

from backend.models.market_output import (
    MarketOutput, MarketClassification, ReasonCode,
)
from backend.services.ev_classification import (
    aplicar_veto_do_motor_de_escanteios, _linha_e_lado_do_rotulo,
)
from backend.services import data_governance as dg


def _pick(selection, tipo="Corners"):
    return MarketOutput(
        market_type=tipo,
        selection=selection,
        raw_probability=0.80,
        calibrated_probability=0.70,
        classification=MarketClassification.SAFE,
    )


# ── rotulo ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("rotulo,esperado", [
    ("Corners Over 9.5", (9.5, "OVER")),
    ("Corners Under 10.5", (10.5, "UNDER")),
    ("Over 2.5", (None, None)),
    ("", (None, None)),
])
def test_linha_e_lado(rotulo, esperado):
    assert _linha_e_lado_do_rotulo(rotulo) == esperado


# ── veto de familia ─────────────────────────────────────────────────────
def test_restricted_market_veta_todos_os_escanteios():
    picks = [_pick("Corners Over 9.5"), _pick("Corners Under 10.5"),
             _pick("Over 2.5", tipo="Over/Under")]
    n = aplicar_veto_do_motor_de_escanteios(picks, {"decision": {
        "no_bet": True, "no_bet_reason": "restricted_market",
        "reason_codes": ["GOVERNANCE_RESTRICTED"], "governance_state": "RESTRICTED",
    }})
    assert n == 2
    assert picks[0].classification is MarketClassification.NO_BET
    assert picks[1].classification is MarketClassification.NO_BET
    # mercado de gols nao e afetado
    assert picks[2].classification is MarketClassification.SAFE


def test_insufficient_data_veta_a_familia():
    picks = [_pick("Corners Over 8.5")]
    assert aplicar_veto_do_motor_de_escanteios(picks, {"decision": {
        "no_bet": True, "no_bet_reason": "insufficient_data",
    }}) == 1
    assert ReasonCode.CORNER_ENGINE_NO_BET in picks[0].reason_codes


# ── veto de linha ───────────────────────────────────────────────────────
def test_filtro_h2h_veta_so_a_linha_e_o_lado():
    picks = [_pick("Corners Over 9.5"), _pick("Corners Under 9.5"),
             _pick("Corners Over 10.5")]
    n = aplicar_veto_do_motor_de_escanteios(picks, {"decision": {
        "no_bet": True, "no_bet_reason": "h2h_avg_corners (7.2) < line (9.5)",
        "line": 9.5, "side": "OVER", "reason_codes": ["H2H_CORNER_FILTER"],
    }})
    assert n == 1
    assert picks[0].classification is MarketClassification.NO_BET
    assert picks[1].classification is MarketClassification.SAFE
    assert picks[2].classification is MarketClassification.SAFE


# ── o pick vetado continua visivel ──────────────────────────────────────
def test_pick_vetado_nao_some_do_payload():
    picks = [_pick("Corners Over 9.5")]
    aplicar_veto_do_motor_de_escanteios(picks, {"decision": {
        "no_bet": True, "no_bet_reason": "restricted_market",
        "governance_state": "RESTRICTED", "reason_codes": ["GOVERNANCE_RESTRICTED"],
    }})
    d = picks[0].to_legacy_mercado()
    assert d["corner_veto"]["noBet"] is True
    assert d["corner_veto"]["reason"] == "restricted_market"
    assert d["corner_veto"]["scope"] == "family"
    assert "CORNER_ENGINE_NO_BET" in d["reason_codes"]


def test_sem_veto_nada_muda():
    picks = [_pick("Corners Over 9.5")]
    assert aplicar_veto_do_motor_de_escanteios(picks, {"decision": {"no_bet": False}}) == 0
    assert picks[0].classification is MarketClassification.SAFE
    assert aplicar_veto_do_motor_de_escanteios(picks, {}) == 0
    assert aplicar_veto_do_motor_de_escanteios(picks, None) == 0


# ── estado da temporada ─────────────────────────────────────────────────
def test_tres_estados_distintos():
    assert dg.season_data_state(None) == dg.ESTADO_TEMPORADA_DESCONHECIDO
    assert dg.season_data_state({"matchesCompleted": 3}) == dg.ESTADO_TEMPORADA_INICIO
    assert dg.season_data_state({"matchesCompleted": 24}) == dg.ESTADO_TEMPORADA_OK


def test_desconhecido_nao_muda_numero_por_padrao(monkeypatch):
    monkeypatch.delenv("EARLY_SEASON_REQUIRES_COUNT", raising=False)
    assert dg.detect_early_season(None) is True     # comportamento historico


def test_flag_desliga_o_encolhimento_por_dado_ausente(monkeypatch):
    monkeypatch.setenv("EARLY_SEASON_REQUIRES_COUNT", "1")
    assert dg.detect_early_season(None) is False
    assert dg.detect_early_season({"matchesCompleted": 3}) is True
    assert dg.detect_early_season({"matchesCompleted": 24}) is False


def test_contagem_corrompida_e_desconhecida():
    assert dg.season_data_state({"matchesCompleted": "vinte"}) == dg.ESTADO_TEMPORADA_DESCONHECIDO
