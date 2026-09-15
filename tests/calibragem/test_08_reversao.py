# -*- coding: utf-8 -*-
"""Teste 5 da spec — reversao fora da amostra, e o anti-oscilacao.

#253: a janela abre na ANCORA e cada pick e pontuado pela versao que o
serviu (`curva_servida`). Aqui a vigencia e UMA versao desde antes da janela,
entao "servido" = vigente e os Briers conferem a mao; o giro de versoes esta
em `test_15_governanca_por_ancora.py`.
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.governanca import avaliar_reversao, brier
from backend.modeling.calibragem.repositorio import Pick

BOA = {"a": 0.45, "b": 1.0}      # sobe a probabilidade
RUIM = {"a": -0.90, "b": 1.0}    # derruba
ADOCAO = datetime(2026, 9, 1, tzinfo=timezone.utc)
DEPOIS = ADOCAO + timedelta(days=1)


def _vigencia(curva):
    return [(ADOCAO, curva["a"], curva["b"])]


def _servidos(n=60, p_raw=0.60, y=1):
    # #248 (composicao): o Brier da reversao e medido sobre a probabilidade
    # PUBLICADA, `aplicar(p_legado, a, b)`. `p_legado=p_raw` mantem este
    # cenario com o legado na identidade, isolando o criterio de reversao.
    return [Pick(f"j{i}", "Over/Under", "l", p_raw, y if i % 4 else 0,
                 publicado_em=DEPOIS, p_legado=p_raw)
            for i in range(n)]


def _avaliar(servida, ancora, reversoes=0, picks=None):
    return avaliar_reversao(picks if picks is not None else _servidos(),
                            _vigencia(servida), ancora, servida, reversoes)


def test_brier_de_previsao_perfeita_e_zero():
    assert brier([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


def test_brier_vazio_devolve_none():
    assert brier([]) is None


def test_servida_melhor_que_a_ancora_ancora():
    r = _avaliar(servida=BOA, ancora=RUIM)
    assert r["acao"] == "ancorar"


def test_servida_igual_a_ancora_mantem():
    r = _avaliar(servida=BOA, ancora=BOA)
    assert r["acao"] == "manter" and "ja e a ancora" in r["motivo"]


def test_servida_pior_reverte():
    r = _avaliar(servida=RUIM, ancora=BOA)
    assert r["acao"] == "reverter"


def test_reversao_aperta_o_limite_do_proximo_ciclo():
    r = _avaliar(servida=RUIM, ancora=BOA)
    assert r["limite_proximo"] == pytest.approx(PASSO_MAXIMO_PP / 2)


def test_segunda_reversao_seguida_congela():
    r = _avaliar(servida=RUIM, ancora=BOA, reversoes=1)
    assert r["acao"] == "congelar"
    assert "revisao humana" in r["motivo"]


def test_janela_curta_nao_reverte():
    """Sem 20 jogos na janela, nao ha o que concluir (#079)."""
    r = _avaliar(servida=RUIM, ancora=BOA, picks=_servidos(n=MIN_N_JOGOS - 1))
    assert r["acao"] == "manter"
    assert "janela" in r["motivo"]


def test_conta_jogos_nao_picks_na_janela():
    """40 picks de UM jogo nao formam janela."""
    picks = [Pick("jogo1", "Over/Under", "l", 0.6, 1, publicado_em=DEPOIS,
                  p_legado=0.6) for _ in range(40)]
    r = _avaliar(servida=RUIM, ancora=BOA, picks=picks)
    assert r["acao"] == "manter"


def test_cada_pick_e_julgado_pela_versao_que_o_serviu():
    """Metade dos picks servida pela BOA, metade pela RUIM: Brier servido
    0,2589, entre a BOA (0,1898) e a RUIM (0,3253). Contra uma ancora no meio
    (a=-0,60, Brier ~0,277), julgar tudo pela vigente atual (RUIM) reverteria;
    julgando cada pick pela versao que o serviu, a curva nao perdeu."""
    troca = DEPOIS + timedelta(hours=12)
    vigencia = [(ADOCAO, BOA["a"], BOA["b"]), (troca, RUIM["a"], RUIM["b"])]
    picks = ([p._replace(publicado_em=DEPOIS) for p in _servidos(30)]
             + [p._replace(match_id=f"k{i}", publicado_em=troca + timedelta(hours=1))
                for i, p in enumerate(_servidos(30))])
    media = {"a": -0.60, "b": 1.0}
    pela_servida = avaliar_reversao(picks, vigencia, media, RUIM, 0)
    pela_vigente = avaliar_reversao(picks, [(ADOCAO, RUIM["a"], RUIM["b"])], media, RUIM, 0)
    assert pela_vigente["acao"] == "reverter"
    assert pela_servida["acao"] == "ancorar", pela_servida["motivo"]
