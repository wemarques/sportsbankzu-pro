# -*- coding: utf-8 -*-
"""Teste 5 da spec — reversao fora da amostra, e o anti-oscilacao.

Os jogos que uma versao avalia sao OS QUE ELA SERVIU: adotada no ciclo t,
publica; os jogos liquidados ate t+1 nunca fizeram parte do ajuste dela.
"""
import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.governanca import avaliar_reversao, brier
from backend.modeling.calibragem.repositorio import Pick

BOA = {"a": 0.45, "b": 1.0}      # sobe a probabilidade
RUIM = {"a": -0.90, "b": 1.0}    # derruba


def _servidos(n=60, p_raw=0.60, y=1):
    return [Pick(f"j{i}", "Over/Under", "l", p_raw, y if i % 4 else 0)
            for i in range(n)]


def test_brier_de_previsao_perfeita_e_zero():
    assert brier([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


def test_brier_vazio_devolve_none():
    assert brier([]) is None


def test_vigente_melhor_mantem():
    r = avaliar_reversao(_servidos(), vigente=BOA, anterior=RUIM,
                         reversoes_seguidas=0)
    assert r["acao"] == "manter"


def test_vigente_pior_reverte():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=0)
    assert r["acao"] == "reverter"


def test_reversao_aperta_o_limite_do_proximo_ciclo():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=0)
    assert r["limite_proximo"] == pytest.approx(PASSO_MAXIMO_PP / 2)


def test_segunda_reversao_seguida_congela():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=1)
    assert r["acao"] == "congelar"
    assert "revisao humana" in r["motivo"]


def test_janela_curta_nao_reverte():
    """Sem 20 jogos na janela, nao ha o que concluir (#079)."""
    r = avaliar_reversao(_servidos(n=MIN_N_JOGOS - 1), vigente=RUIM,
                         anterior=BOA, reversoes_seguidas=0)
    assert r["acao"] == "manter"
    assert "janela" in r["motivo"]


def test_conta_jogos_nao_picks_na_janela():
    """40 picks de UM jogo nao formam janela."""
    picks = [Pick("jogo1", "Over/Under", "l", 0.6, 1) for _ in range(40)]
    r = avaliar_reversao(picks, vigente=RUIM, anterior=BOA, reversoes_seguidas=0)
    assert r["acao"] == "manter"
