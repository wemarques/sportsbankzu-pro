# -*- coding: utf-8 -*-
"""Teste 5 da spec — reversao fora da amostra, e o anti-oscilacao.

#253/#253-a: a janela abre na ANCORA da familia e cada pick e pontuado pela
versao que o serviu. Aqui a familia tem UMA celula e a vigencia e uma versao
desde antes da janela, entao "servido" = vigente e os Briers conferem a mao;
o giro de versoes e as varias ligas estao em `test_15` e `test_16`.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.governanca import brier, julgar_familia
from backend.modeling.calibragem.repositorio import Pick

CELULA = ("Over/Under", "l")
BOA = {"a": 0.45, "b": 1.0}      # sobe a probabilidade
RUIM = {"a": -0.90, "b": 1.0}    # derruba
ADOCAO = datetime(2026, 9, 1, tzinfo=timezone.utc)
DEPOIS = ADOCAO + timedelta(days=1)


def _servidos(n=60, p_raw=0.60, y=1):
    # #248 (composicao): o Brier e medido sobre a probabilidade PUBLICADA,
    # `aplicar(p_legado, a, b)`. `p_legado=p_raw` mantem o legado na
    # identidade, isolando o criterio.
    return [Pick(f"j{i}", "Over/Under", "l", p_raw, y if i % 4 else 0,
                 publicado_em=DEPOIS, p_legado=p_raw)
            for i in range(n)]


def _julgar(servida, ancora, reversoes=0, picks=None, vigencia=None):
    return julgar_familia(
        picks if picks is not None else _servidos(),
        vigencia if vigencia is not None else {CELULA: [(ADOCAO, servida["a"], servida["b"])]},
        {CELULA: dict(ancora, desde=ADOCAO)},
        {CELULA: servida}, reversoes)


def test_brier_de_previsao_perfeita_e_zero():
    assert brier([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


def test_brier_vazio_devolve_none():
    assert brier([]) is None


def test_servida_melhor_que_a_ancora_ancora():
    assert _julgar(servida=BOA, ancora=RUIM)["acao"] == "ancorar"


def test_servida_igual_a_ancora_mantem():
    r = _julgar(servida=BOA, ancora=BOA)
    assert r["acao"] == "manter" and "ja estao na ancora" in r["motivo"]


def test_servida_pior_reverte():
    assert _julgar(servida=RUIM, ancora=BOA)["acao"] == "reverter"


def test_reversao_aperta_o_limite_do_proximo_ciclo():
    r = _julgar(servida=RUIM, ancora=BOA)
    assert r["limite_proximo"] == pytest.approx(PASSO_MAXIMO_PP / 2)


def test_segunda_reversao_seguida_congela():
    r = _julgar(servida=RUIM, ancora=BOA, reversoes=1)
    assert r["acao"] == "congelar"
    assert "revisao humana" in r["motivo"]


def test_janela_curta_nao_reverte():
    """Sem 20 jogos na janela, nao ha o que concluir (#079)."""
    r = _julgar(servida=RUIM, ancora=BOA, picks=_servidos(n=MIN_N_JOGOS - 1))
    assert r["acao"] == "manter"
    assert "janela da familia com 19 jogos" in r["motivo"]


def test_conta_jogos_nao_picks_na_janela():
    """40 picks de UM jogo nao formam janela."""
    picks = [Pick("jogo1", "Over/Under", "l", 0.6, 1, publicado_em=DEPOIS,
                  p_legado=0.6) for _ in range(40)]
    assert _julgar(servida=RUIM, ancora=BOA, picks=picks)["acao"] == "manter"


def test_cada_pick_e_julgado_pela_versao_que_o_serviu():
    """Metade dos picks servida pela BOA, metade pela RUIM: Brier servido
    0,2589, entre a BOA (0,1898) e a RUIM (0,3253). Contra uma ancora no meio
    (a=-0,60, Brier ~0,277), julgar tudo pela vigente atual (RUIM) reverteria;
    julgando cada pick pela versao que o serviu, a curva nao perdeu."""
    troca = DEPOIS + timedelta(hours=12)
    vigencia = {CELULA: [(ADOCAO, BOA["a"], BOA["b"]), (troca, RUIM["a"], RUIM["b"])]}
    picks = ([p._replace(publicado_em=DEPOIS) for p in _servidos(30)]
             + [p._replace(match_id=f"k{i}", publicado_em=troca + timedelta(hours=1))
                for i, p in enumerate(_servidos(30))])
    media = {"a": -0.60, "b": 1.0}
    pela_servida = _julgar(RUIM, media, picks=picks, vigencia=vigencia)
    pela_vigente = _julgar(RUIM, media, picks=picks)
    assert pela_vigente["acao"] == "reverter"
    assert pela_servida["acao"] == "ancorar", pela_servida["motivo"]
