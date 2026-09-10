# -*- coding: utf-8 -*-
"""Teste 6 da spec — o volume publicado fica constante.

A classificacao usa prob RAW (proibicao 11), entao `safe_prob` e `neutro_prob`
nao se movem. O volume sobe por `ev` e `edge`, que consomem a corrigida:
medido, os picks de EV positivo vao de 13,8% para 25,2% (1,8x).
"""
from backend.modeling.calibragem.limiares import contar_por_classe, rederivar
from backend.modeling.calibragem.linha_base import linha_base


class P:
    def __init__(self, familia, p_raw, odd):
        self.familia, self.p_raw, self.odd = familia, p_raw, odd


ATUAIS = {"Over/Under": {"safe_ev": 0.06, "neutro_ev": 0.00,
                         "safe_edge": 0.05, "neutro_edge": 0.02}}

# ATENCAO (#248, C1): esta NAO e a linha de base da versao 0. A identidade
# `(a=0, b=1)` e so um par sintetico, usado aqui para exercitar a matematica
# de `rederivar` com numeros faceis de conferir a mao. A versao 0 real delega
# a `legado.calibrar_legado`, que fica 12-25 pontos ABAIXO da identidade --
# a suposicao contraria e exatamente o defeito C1. O teste que prova a
# propriedade que interessa em producao (volume preservado CONTRA A VERSAO 0)
# esta no fim deste arquivo e usa `linha_base`.
SINTETICO = {"Over/Under": {"a": 0.0, "b": 1.0}}
NOVO = {"Over/Under": {"a": 0.45, "b": 1.0}}     # sobe ~10 pontos


def _amostra(n=400):
    return [P("Over/Under", 0.30 + (i % 60) / 100.0, 1.70 + (i % 9) / 10.0)
            for i in range(n)]


def test_sem_rederivacao_o_volume_sobe():
    picks = _amostra()
    antes = contar_por_classe(picks, SINTETICO, ATUAIS)["Over/Under"]
    depois = contar_por_classe(picks, NOVO, ATUAIS)["Over/Under"]
    # "Volume publicado" e o TOTAL, nao a faixa do meio: quando a probabilidade
    # sobe, picks migram de `neutro` para `safe` e outros entram em `neutro` por
    # baixo — os fluxos se cancelam e o balde intermediario empata (medido:
    # safe 230->311, neutro 21->21, total 251->332).
    assert sum(depois.values()) > sum(antes.values())


def test_rederivacao_devolve_o_volume_ao_que_era():
    picks = _amostra()
    antes = contar_por_classe(picks, SINTETICO, ATUAIS)
    novos = rederivar(picks, SINTETICO, NOVO, ATUAIS)
    depois = contar_por_classe(picks, NOVO, novos)
    for classe in ("safe", "neutro"):
        assert abs(depois["Over/Under"][classe] - antes["Over/Under"][classe]) <= 2, \
            (classe, antes, depois)


def test_familia_sem_odd_nao_move_limiar():
    """Cartoes tem 88,3% das linhas sem odd — nao ha volume a manter."""
    picks = [P("Cards", 0.60, None) for _ in range(50)]
    atuais = {"Cards": {"safe_ev": 0.06, "neutro_ev": 0.0,
                        "safe_edge": 0.05, "neutro_edge": 0.02}}
    novos = rederivar(picks, {"Cards": {"a": 0.0, "b": 1.0}},
                      {"Cards": {"a": 0.5, "b": 1.0}}, atuais)
    assert novos["Cards"] == atuais["Cards"]


def test_familia_ausente_da_amostra_e_preservada():
    novos = rederivar([], SINTETICO, NOVO, ATUAIS)
    assert novos["Over/Under"] == ATUAIS["Over/Under"]


# ─── C1: o volume tem de ser preservado contra a VERSAO 0, nao contra a
# identidade ───────────────────────────────────────────────────────────────
#
# A propriedade que a spec promete (D4, secao 5.5) e "o painel publica o
# mesmo VOLUME que publicava na vespera". A vespera e o legado, e a linha de
# base dele fica 12-25pp abaixo da identidade. Provar a preservacao contra
# `{a:0, b:1}` prova a propriedade errada: mede contra uma curva que nunca
# publicou nada. Medido antes da correcao, com a identidade como referencia,
# o volume SAFE de Corners ia de 106 para 306 no primeiro ciclo -- passando
# por um teste verde.

LEGADO_OU = {"Over/Under": dict(zip(("a", "b"), linha_base("Over/Under")))}


def test_a_linha_de_base_do_legado_nao_e_a_identidade():
    """A premissa do resto deste bloco, medida em vez de suposta."""
    a, b = linha_base("Over/Under")
    assert (a, b) != (0.0, 1.0)
    assert a < 0.0, a          # o legado publica ABAIXO do raw
    assert 0.0 < b < 1.0, b    # e achata os extremos


def test_rederivacao_preserva_o_volume_contra_a_linha_de_base_do_legado():
    """A mesma propriedade do teste sintetico, agora contra a curva que a
    versao 0 de fato serve."""
    picks = _amostra()
    antes = contar_por_classe(picks, LEGADO_OU, ATUAIS)
    novos = rederivar(picks, LEGADO_OU, NOVO, ATUAIS)
    depois = contar_por_classe(picks, NOVO, novos)
    for classe in ("safe", "neutro"):
        assert abs(depois["Over/Under"][classe] - antes["Over/Under"][classe]) <= 2, \
            (classe, antes, depois)


def test_a_referencia_errada_subestima_o_salto_de_volume():
    """Por que a correcao importa, em numeros MEDIDOS nesta amostra:

        base            volume antes   volume depois   fator
        legado (v0)          194            332        1,71x
        identidade           251            332        1,32x

    Partindo da referencia errada, o mesmo `NOVO` parece um salto de 1,3x
    quando na pratica e de 1,7x -- e e o volume da linha de cima que o painel
    de fato publicava na vespera. A re-derivacao segura o salto, mas so
    segura o salto CERTO se medir da base certa.
    """
    picks = _amostra()
    de_legado = sum(contar_por_classe(picks, LEGADO_OU, ATUAIS)["Over/Under"].values())
    de_identidade = sum(contar_por_classe(picks, SINTETICO, ATUAIS)["Over/Under"].values())
    depois = sum(contar_por_classe(picks, NOVO, ATUAIS)["Over/Under"].values())

    assert de_legado < de_identidade, (de_legado, de_identidade)
    assert depois / de_legado > depois / de_identidade
    assert depois / de_legado > 1.6, (de_legado, depois)
