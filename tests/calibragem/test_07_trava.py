# -*- coding: utf-8 -*-
"""Teste 4 da spec — a trava encurta a proposta, nunca a rejeita.

#248, Task 13: `VIGENTE = (0, 1)` deixou de ser um valor de conveniencia e
passou a ser A VERSAO 0. Com a composicao
(`p' = sigmoide(a + b*logit(legado(p)))`), `(a=0, b=1)` devolve o proprio
legado, entao medir a distancia a partir dele e medir a distancia ate a
curva que o painel publicou na vespera — exata, no primeiro ciclo.

Antes, esta constante media contra a IDENTIDADE: a trava reportava 1,39pp
enquanto a probabilidade publicada de cartoes andava 24,03pp, e a proposta
saia `adotada`. Era o Critico C1.
"""
import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.curva import aplicar, distancia_maxima
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


# ─── a trava e EXATA no primeiro ciclo (#248, Task 13) ──────────────────────

def test_primeiro_ciclo_parte_da_versao_zero_sem_aproximacao():
    """`VIGENTE` E a versao 0: `aplicar(p, 0, 1) == p` na faixa inteira.

    A prova de que a referencia nao e uma aproximacao — se fosse, esta
    igualdade teria um erro de 8,14pp a 15,47pp (a tabela de
    `linha_base.py`, apagado nesta tarefa).
    """
    p = 0.02
    pior = 0.0
    while p <= 0.98 + 1e-12:
        pior = max(pior, abs(aplicar(p, VIGENTE["a"], VIGENTE["b"]) - p))
        p += 0.001
    assert pior < 1e-9, pior


@pytest.mark.parametrize("proposta", [
    {"a": 0.45, "b": 1.0},      # o salto medido no ledger real
    {"a": 2.0, "b": 1.0},
    {"a": -0.90, "b": 0.70},
    {"a": 0.0, "b": 1.60},
    {"a": 0.31, "b": 0.88},
])
def test_o_primeiro_ciclo_nunca_anda_mais_que_a_trava(proposta):
    """Qualquer proposta, partindo da versao 0, sai dentro dos 2pp.

    Este e o teste que NAO podia existir antes da composicao: a distancia
    entre a proposta e a curva realmente publicada era de dois digitos, e
    nenhum ajuste de `(a, b)` a fechava (piso de Chebyshev de 5,89pp na meia
    banda e 9,35pp na banda inteira, porque o legado satura e a logistica
    nao).
    """
    r = avaliar_proposta(proposta, VIGENTE, n_jogos=100)
    assert r["status"] in ("adotada", "encurtada"), r
    andou = distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"])
    assert andou <= PASSO_MAXIMO_PP + 1e-6, (proposta, andou)


def test_o_encurtamento_nao_zera_a_celula():
    """A patologia do #247 pelo avesso: a trava exata nao pode travar tudo.

    Se a referencia fosse a FUNCAO legado, o proprio `t=0` ja distaria
    5,89pp e o fator convergiria para 0 — toda celula sairia `encurtada` sem
    andar. Com a composicao o fator e positivo e a celula ANDA.
    """
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "encurtada"
    assert r["fator_encurtamento"] > 0.0
    assert distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"]) > 0.01
