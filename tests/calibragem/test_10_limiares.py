# -*- coding: utf-8 -*-
"""Teste 6 da spec — o volume publicado fica constante.

A classificacao usa prob RAW (proibicao 11), entao `safe_prob` e `neutro_prob`
nao se movem. O volume sobe por `ev` e `edge`, que consomem a corrigida:
medido, os picks de EV positivo vao de 13,8% para 25,2% (1,8x).
"""
import pytest

from backend.modeling.calibragem.limiares import contar_por_classe, rederivar


class P:
    def __init__(self, familia, p_raw, odd):
        self.familia, self.p_raw, self.odd = familia, p_raw, odd


ATUAIS = {"Over/Under": {"safe_ev": 0.06, "neutro_ev": 0.00,
                         "safe_edge": 0.05, "neutro_edge": 0.02}}
ANTIGO = {"Over/Under": {"a": 0.0, "b": 1.0}}
NOVO = {"Over/Under": {"a": 0.45, "b": 1.0}}     # sobe ~10 pontos


def _amostra(n=400):
    return [P("Over/Under", 0.30 + (i % 60) / 100.0, 1.70 + (i % 9) / 10.0)
            for i in range(n)]


def test_sem_rederivacao_o_volume_sobe():
    picks = _amostra()
    antes = contar_por_classe(picks, ANTIGO, ATUAIS)["Over/Under"]
    depois = contar_por_classe(picks, NOVO, ATUAIS)["Over/Under"]
    # "Volume publicado" e o TOTAL, nao a faixa do meio: quando a probabilidade
    # sobe, picks migram de `neutro` para `safe` e outros entram em `neutro` por
    # baixo — os fluxos se cancelam e o balde intermediario empata (medido:
    # safe 230->311, neutro 21->21, total 251->332).
    assert sum(depois.values()) > sum(antes.values())


def test_rederivacao_devolve_o_volume_ao_que_era():
    picks = _amostra()
    antes = contar_por_classe(picks, ANTIGO, ATUAIS)
    novos = rederivar(picks, ANTIGO, NOVO, ATUAIS)
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
    novos = rederivar([], ANTIGO, NOVO, ATUAIS)
    assert novos["Over/Under"] == ATUAIS["Over/Under"]
