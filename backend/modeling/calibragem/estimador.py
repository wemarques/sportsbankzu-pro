# -*- coding: utf-8 -*-
"""Ajuste de (a, b) por celula. Sem I/O e sem dependencia externa.

O modelo e regressao logistica com intercepto e UM regressor, logit(p_raw).
Com dois parametros, a matriz de informacao e 2x2 e a inversa se escreve a
mao — nao ha motivo para dependencia de algebra linear ou cientifica externa,
e a Layer do Lambda ja falhou em silencio uma vez (B-014, NB2 de cartoes
caindo para Poisson sem aviso).
"""
import logging
import math
from typing import Optional, Sequence, Tuple

from backend.modeling.calibragem.curva import _logit, _sigmoide

logger = logging.getLogger("sportsbankzu.calibragem.estimador")

_MAX_ITER = 50
_TOL = 1e-9
_RIDGE = 1e-6      # regularizacao minima: impede matriz singular em amostra rala


def ajustar(picks: Sequence) -> Optional[Tuple[float, float]]:
    """(a, b) por maxima verossimilhanca. None se degenerado ou nao converge."""
    if len(picks) < 2:
        return None
    ys = {p.y for p in picks}
    if len(ys) < 2:
        return None    # todos 0 ou todos 1: sem maximo finito

    xs = [_logit(p.p_raw) for p in picks]
    yv = [float(p.y) for p in picks]

    a, b = 0.0, 1.0
    for _ in range(_MAX_ITER):
        # Gradiente e Hessiana da log-verossimilhanca.
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, yv):
            mu = _sigmoide(a + b * x)
            r = y - mu
            w = mu * (1.0 - mu)
            g0 += r
            g1 += r * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        h00 += _RIDGE
        h11 += _RIDGE

        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-14:
            logger.info("[calibragem] Hessiana singular; ajuste abortado")
            return None

        # Passo de Newton: theta += H^-1 g, com H^-1 de uma 2x2 escrita a mao.
        da = (h11 * g0 - h01 * g1) / det
        db = (h00 * g1 - h01 * g0) / det
        a += da
        b += db

        if abs(da) < _TOL and abs(db) < _TOL:
            break
    else:
        logger.info("[calibragem] IRLS nao convergiu em %d iteracoes", _MAX_ITER)
        return None

    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    return (a, b)
