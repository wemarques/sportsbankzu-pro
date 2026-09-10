# -*- coding: utf-8 -*-
"""Teste 3 da spec — `n_efetivo` conta JOGOS, nao picks.

Escanteios tem 7.299 picks em 220 jogos. `Over 2.5` e `BTTS` do mesmo jogo
dividem o mesmo placar: nao sao observacoes independentes. Contar picks daria
autonomia quase total a celula em cima de 220 jogos de informacao real.

E a mesma classe de erro do #196 (pareou desfechos de jogos diferentes), do
#243 (comparou odd em escala errada) e do #244 (leu calibracao em fonte
recomputada pos-jogo). Todos foram contagem indevida.
"""
import pytest

from backend.modeling.calibragem import K_FIXO
from backend.modeling.calibragem.estimador import contar_jogos, encolher
from backend.modeling.calibragem.repositorio import Pick


def test_conta_jogos_nao_picks():
    picks = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    assert contar_jogos(picks) == 1


def test_quarenta_picks_de_um_jogo_pesam_como_dois_picks_de_um_jogo():
    """O teste que guarda o detalhe. Mesmo jogo = mesmo peso."""
    um_jogo_40 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    um_jogo_2 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(2)]
    proprio, pai = (0.5, 1.0), (0.0, 1.0)
    assert encolher(proprio, pai, contar_jogos(um_jogo_40), K_FIXO) == \
           encolher(proprio, pai, contar_jogos(um_jogo_2), K_FIXO)


def test_sem_amostra_fica_no_pai():
    assert encolher((9.0, 9.0), (0.1, 0.8), 0, K_FIXO) == (0.1, 0.8)


def test_amostra_igual_a_k_fica_na_metade_do_caminho():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), K_FIXO, K_FIXO)
    assert a == pytest.approx(0.5)
    assert b == pytest.approx(1.0)


def test_amostra_enorme_ignora_o_pai():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), 100000, K_FIXO)
    assert a == pytest.approx(1.0, abs=0.001)
    assert b == pytest.approx(2.0, abs=0.001)


def test_k_cai_no_fixo_com_poucas_celulas():
    from backend.modeling.calibragem.estimador import estimar_k
    k, caiu = estimar_k({("Corners", ""): []})
    assert caiu is True
    assert k == K_FIXO
