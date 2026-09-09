# -*- coding: utf-8 -*-
"""A curva de dois parametros: identidade, monotonicidade, bordas, versao 0."""
import math

import pytest

from backend.modeling.calibragem import VERSAO_LEGADO
from backend.modeling.calibragem.curva import (
    aplicar, distancia_maxima, familia_do_mercado,
)


def test_a_zero_b_um_e_a_identidade():
    for p in (0.05, 0.2, 0.5, 0.734, 0.95):
        assert aplicar(p, 0.0, 1.0) == pytest.approx(p, abs=1e-12)


def test_a_positivo_sobe_a_probabilidade():
    assert aplicar(0.5, 0.4, 1.0) > 0.5


def test_b_menor_que_um_encolhe_os_extremos():
    """b < 1 puxa as pontas para o meio; o meio (p=0,5) fica parado."""
    assert aplicar(0.5, 0.0, 0.7) == pytest.approx(0.5, abs=1e-12)
    assert aplicar(0.9, 0.0, 0.7) < 0.9
    assert aplicar(0.1, 0.0, 0.7) > 0.1


def test_e_monotona_quando_b_positivo():
    anterior = -1.0
    for i in range(1, 1000):
        atual = aplicar(i / 1000.0, 0.3, 0.8)
        assert atual > anterior, i
        anterior = atual


def test_bordas_nao_estouram():
    """p=0 e p=1 dariam logit infinito; a funcao prende antes."""
    assert 0.0 < aplicar(0.0, 0.0, 1.0) < 0.001
    assert 0.999 < aplicar(1.0, 0.0, 1.0) < 1.0
    assert 0.0 < aplicar(1e-300, 2.0, 3.0) < 1.0


@pytest.mark.parametrize("market,esperado", [
    ("Over 2.5", "Over/Under"), ("Under 3.5", "Over/Under"),
    ("BTTS", "BTTS"),
    ("Escanteios Over 7.5", "Corners"), ("Escanteios Under 12.5", "Corners"),
    ("Cartoes Over 2.5", "Cards"), ("Cartoes Under 4.5", "Cards"),
    ("1X2 Home", "1X2"), ("1X2 Draw", "1X2"),
    ("DC 1X", "Double Chance"), ("DC X2", "Double Chance"),
])
def test_familia_do_mercado(market, esperado):
    assert familia_do_mercado(market) == esperado


def test_familia_desconhecida_levanta():
    """Mercado novo tem de quebrar aqui, nao virar silenciosamente 1X2."""
    with pytest.raises(ValueError, match="familia desconhecida"):
        familia_do_mercado("Handicap Asiatico -1.5")


def test_distancia_maxima_e_zero_para_parametros_iguais():
    assert distancia_maxima(0.3, 0.9, 0.3, 0.9) == pytest.approx(0.0, abs=1e-12)


def test_distancia_maxima_encontra_o_pior_ponto():
    d = distancia_maxima(0.0, 1.0, 0.4, 1.0)
    # a=0.4 em p=0.5 leva a sigmoid(0.4)=0.5987 -> 0.0987 de diferenca
    assert d == pytest.approx(0.0987, abs=0.002)


def test_versao_legado_e_zero():
    assert VERSAO_LEGADO == 0
