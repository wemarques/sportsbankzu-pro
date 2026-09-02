"""#219 - remocao de margem e a margem como detector de odd velha."""
import pytest

from backend.services.devig import (
    margem_pp, odds_utilizaveis, devig, devig_proporcional, devig_shin,
    devig_potencia, todos_os_metodos, prob_justa,
)
from backend.services.ev_classification import _overround_para_derivar

# 1X2 do card, Londrina x Juventude (odd velha) e o mesmo jogo na bet365.
ODD_VELHA = [2.88, 2.70, 2.17]
ODD_REAL = [3.75, 2.87, 2.20]


# ── margem ──────────────────────────────────────────────────────────────
def test_margem_reproduz_o_numero_do_214():
    assert margem_pp(ODD_VELHA) == pytest.approx(17.84, abs=0.01)
    assert margem_pp(ODD_REAL) == pytest.approx(6.96, abs=0.01)


@pytest.mark.parametrize("odds", [[1.0, 2.0], [0.5, 3.0], ["x", 2.0], [2.0], []])
def test_odd_invalida_devolve_none(odds):
    assert margem_pp(odds) is None
    assert devig(odds) is None


# ── gate de frescor ─────────────────────────────────────────────────────
def test_margem_de_178_e_reprovada():
    ok, m, motivo = odds_utilizaveis(ODD_VELHA)
    assert ok is False and motivo == "margem_fora_de_mercado"
    assert m == pytest.approx(17.84, abs=0.01)


def test_margem_de_bet365_passa():
    ok, m, motivo = odds_utilizaveis(ODD_REAL)
    assert ok is True and motivo == "ok"


def test_margem_negativa_e_odd_corrompida():
    ok, _m, motivo = odds_utilizaveis([3.0, 3.0, 3.0])   # soma 1.0 exata
    assert ok is False and motivo == "margem_abaixo_do_possivel"


# ── os tres metodos ─────────────────────────────────────────────────────
@pytest.mark.parametrize("fn", [devig_proporcional, devig_shin, devig_potencia])
@pytest.mark.parametrize("odds", [ODD_VELHA, ODD_REAL, [1.90, 1.90], [1.20, 5.50]])
def test_todo_metodo_soma_um(fn, odds):
    p = fn(odds)
    assert p is not None
    assert sum(p) == pytest.approx(1.0, abs=1e-9)
    assert all(0.0 < x < 1.0 for x in p)


@pytest.mark.parametrize("fn", [devig_proporcional, devig_shin, devig_potencia])
def test_ordem_preservada(fn):
    """De-vig nao pode reordenar favorito e azarao."""
    p = fn(ODD_REAL)
    assert p[0] < p[1] < p[2]


def test_shin_desconta_menos_do_favorito_que_o_proporcional():
    """E a razao de existirem tres. O favorito e o indice 2 (menor odd)."""
    prop = devig_proporcional(ODD_VELHA)
    shin = devig_shin(ODD_VELHA)
    assert shin[2] > prop[2]
    # divergencia medida, nao estimada
    assert (shin[2] - prop[2]) * 100 == pytest.approx(0.74, abs=0.05)


def test_divergencia_encolhe_com_margem_sadia():
    d_podre = (devig_shin(ODD_VELHA)[2] - devig_proporcional(ODD_VELHA)[2]) * 100
    d_sadia = (devig_shin(ODD_REAL)[2] - devig_proporcional(ODD_REAL)[2]) * 100
    assert d_sadia < d_podre


def test_sem_margem_os_metodos_convergem():
    justas = [3.0, 3.0, 3.0]
    for fn in (devig_proporcional, devig_shin, devig_potencia):
        assert fn(justas) == pytest.approx([1/3, 1/3, 1/3], abs=1e-6)


def test_todos_os_metodos_devolve_os_tres():
    r = todos_os_metodos(ODD_REAL)
    assert set(r) == {"proporcional", "shin", "potencia"}


def test_prob_justa_por_perna():
    assert prob_justa(ODD_REAL, 2, "shin") == pytest.approx(devig_shin(ODD_REAL)[2])
    assert prob_justa(ODD_REAL, 9) is None


# ── overround derivado ──────────────────────────────────────────────────
def test_desligado_mantem_a_constante(monkeypatch):
    monkeypatch.delenv("DEVIG_ENABLED", raising=False)
    odds = {"home": 3.75, "draw": 2.87, "away": 2.20}
    assert _overround_para_derivar(odds, 1.05) == 1.05


def test_ligado_usa_a_margem_medida(monkeypatch):
    monkeypatch.setenv("DEVIG_ENABLED", "1")
    odds = {"home": 3.75, "draw": 2.87, "away": 2.20}
    assert _overround_para_derivar(odds, 1.05) == pytest.approx(1.0696, abs=0.001)


def test_ligado_mas_com_margem_podre_volta_para_a_constante(monkeypatch):
    """Odd velha nao pode contaminar a derivacao de OUTRO mercado."""
    monkeypatch.setenv("DEVIG_ENABLED", "1")
    odds = {"home": 2.88, "draw": 2.70, "away": 2.17}
    assert _overround_para_derivar(odds, 1.05) == 1.05


def test_entrada_estranha_nunca_quebra(monkeypatch):
    monkeypatch.setenv("DEVIG_ENABLED", "1")
    for odds in (None, {}, {"home": 0}, {"home": "x", "draw": "y"}, []):
        assert _overround_para_derivar(odds, 1.06) == 1.06
