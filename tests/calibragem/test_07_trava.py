# -*- coding: utf-8 -*-
"""Teste 4 da spec — a trava encurta a proposta, nunca a rejeita."""
import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.curva import distancia_maxima
from backend.modeling.calibragem.governanca import avaliar_proposta

VIGENTE = {"a": 0.0, "b": 1.0}


def test_proposta_perto_e_adotada_inteira():
    r = avaliar_proposta({"a": 0.01, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "adotada"
    assert r["a"] == pytest.approx(0.01)
    assert r["fator_encurtamento"] is None


def test_proposta_longe_e_encurtada_ate_caber():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "encurtada"
    d = distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"])
    assert d <= PASSO_MAXIMO_PP + 1e-6, d
    assert 0.0 < r["fator_encurtamento"] < 1.0


def test_encurtamento_anda_na_direcao_da_proposta():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert 0.0 < r["a"] < 2.0


def test_abaixo_do_piso_nao_muda_nada():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=MIN_N_JOGOS - 1)
    assert r["status"] == "abaixo_do_piso"
    assert (r["a"], r["b"]) == (VIGENTE["a"], VIGENTE["b"])


def test_b_nao_positivo_e_rejeitado():
    r = avaliar_proposta({"a": 0.01, "b": 0.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "rejeitada"
    assert "b" in r["motivo"]
    assert (r["a"], r["b"]) == (VIGENTE["a"], VIGENTE["b"])
    r2 = avaliar_proposta({"a": 0.01, "b": -0.5}, VIGENTE, n_jogos=100)
    assert r2["status"] == "rejeitada"


def test_proposta_identica_sai_como_inalterada():
    r = avaliar_proposta({"a": 0.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "inalterada"


def test_limite_reduzido_aperta_a_trava():
    """Apos uma reversao o limite da celula cai pela metade (Task 8)."""
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100,
                         limite=PASSO_MAXIMO_PP / 2)
    d = distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"])
    assert d <= PASSO_MAXIMO_PP / 2 + 1e-6
