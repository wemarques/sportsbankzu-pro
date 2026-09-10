# -*- coding: utf-8 -*-
"""Teste 2 da spec — o estimador recupera parametros que ele mesmo gerou.

Se nao recupera o sintetico, nao recupera o real. Este e o controle negativo
do estimador, e vem antes de qualquer numero de producao.
"""
import random

import pytest

from backend.modeling.calibragem.curva import aplicar
from backend.modeling.calibragem.estimador import ajustar
from backend.modeling.calibragem.repositorio import Pick


def _sintetico(a, b, n=8000, semente=227):
    """Gera picks cujo desfecho segue EXATAMENTE a curva (a, b).

    #248 (composicao): o REGRESSOR do estimador e `p_legado`, nao `p_raw`.
    Aqui os dois sao iguais de proposito -- o cenario sintetico e "o legado e
    a identidade", que isola a matematica do ajuste do que o legado faz. O
    controle negativo continua provando exatamente o que provava: se nao
    recupera (a, b) do sintetico, nao recupera do real.
    """
    rng = random.Random(semente)
    picks = []
    for i in range(n):
        p_raw = rng.uniform(0.05, 0.95)
        p_real = aplicar(p_raw, a, b)
        y = 1 if rng.random() < p_real else 0
        picks.append(Pick(f"jogo{i}", "Over/Under", "liga", p_raw, y,
                          p_legado=p_raw))
    return picks


@pytest.mark.parametrize("a,b", [(0.0, 1.0), (0.45, 1.0), (0.0, 0.7), (0.3, 1.2), (-0.2, 0.9)])
def test_recupera_os_parametros_sinteticos(a, b):
    est = ajustar(_sintetico(a, b))
    assert est is not None
    a_est, b_est = est
    assert a_est == pytest.approx(a, abs=0.08), f"a: {a_est} vs {a}"
    assert b_est == pytest.approx(b, abs=0.10), f"b: {b_est} vs {b}"


def test_amostra_degenerada_devolve_none():
    """Todos os desfechos iguais: a verossimilhanca nao tem maximo finito."""
    picks = [Pick(f"j{i}", "BTTS", "liga", 0.5, 1) for i in range(100)]
    assert ajustar(picks) is None


def test_amostra_minuscula_devolve_none():
    assert ajustar([Pick("j1", "BTTS", "liga", 0.5, 1)]) is None
    assert ajustar([]) is None


def test_nao_usa_numpy_nem_scipy():
    """A Layer do Lambda ja falhou em silencio (B-014). Sem dependencia."""
    import pathlib
    fonte = pathlib.Path("backend/modeling/calibragem/estimador.py").read_text(encoding="utf-8")
    for proibido in ("numpy", "scipy", "sklearn", "pandas"):
        assert proibido not in fonte, proibido
