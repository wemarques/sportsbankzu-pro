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


from collections import defaultdict
from typing import Any, Dict

from backend.modeling.calibragem import (
    K_FIXO, MIN_CELULAS_PARA_ESTIMAR_K, MIN_N_JOGOS,
)


def contar_jogos(picks: Sequence) -> int:
    """`n_efetivo` da spec. Picks do mesmo jogo dividem o mesmo placar."""
    return len({p.match_id for p in picks})


def encolher(theta_proprio: Tuple[float, float],
             theta_pai: Tuple[float, float],
             n_efetivo: int, k: float) -> Tuple[float, float]:
    """peso = n/(n+k); theta = peso*proprio + (1-peso)*pai."""
    peso = n_efetivo / (n_efetivo + k) if (n_efetivo + k) > 0 else 0.0
    return (
        peso * theta_proprio[0] + (1.0 - peso) * theta_pai[0],
        peso * theta_proprio[1] + (1.0 - peso) * theta_pai[1],
    )


def estimar_k(celulas: Dict[Any, Sequence]) -> Tuple[float, bool]:
    """k = variancia dentro / variancia entre celulas. (k, caiu_no_fixo)."""
    acima = {ch: pk for ch, pk in celulas.items()
             if contar_jogos(pk) >= MIN_N_JOGOS}
    if len(acima) < MIN_CELULAS_PARA_ESTIMAR_K:
        return (float(K_FIXO), True)

    ajustes, ns = [], []
    for pk in acima.values():
        est = ajustar(pk)
        if est is not None:
            ajustes.append(est[0])          # variancia medida sobre `a`
            ns.append(contar_jogos(pk))
    if len(ajustes) < MIN_CELULAS_PARA_ESTIMAR_K:
        return (float(K_FIXO), True)

    media = sum(ajustes) / len(ajustes)
    var_entre = sum((x - media) ** 2 for x in ajustes) / (len(ajustes) - 1)
    n_medio = sum(ns) / len(ns)
    # Variancia da estimativa de `a` cai com n; var_dentro ~ c/n_medio, e a
    # constante se cancela na razao. Aproximacao deliberada: o que importa e a
    # ordem de grandeza de k, e o piso duro de 20 jogos ja protege o resto.
    var_dentro = 1.0 / max(n_medio, 1.0)
    if var_entre <= 0:
        return (float(K_FIXO), True)
    k = var_dentro / var_entre * n_medio
    return (max(1.0, min(k, 500.0)), False)


def ajustar_hierarquico(picks: Sequence) -> Dict[Tuple[str, str], dict]:
    """Global -> familia -> liga, cada nivel encolhido para o pai."""
    por_familia: Dict[str, list] = defaultdict(list)
    por_celula: Dict[Tuple[str, str], list] = defaultdict(list)
    for p in picks:
        por_familia[p.familia].append(p)
        por_celula[(p.familia, p.liga)].append(p)

    k, caiu_no_fixo = estimar_k(por_celula)
    saida: Dict[Tuple[str, str], dict] = {}

    global_est = ajustar(picks) or (0.0, 1.0)
    saida[("", "")] = {"a": global_est[0], "b": global_est[1],
                       "n_jogos": contar_jogos(picks), "origem": "global",
                       "k_fixo": caiu_no_fixo}

    for familia, pk in por_familia.items():
        n = contar_jogos(pk)
        proprio = ajustar(pk) if n >= MIN_N_JOGOS else None
        theta = encolher(proprio, global_est, n, k) if proprio else global_est
        saida[(familia, "")] = {"a": theta[0], "b": theta[1], "n_jogos": n,
                                "origem": "familia" if proprio else "global",
                                "k_fixo": caiu_no_fixo}

    for (familia, liga), pk in por_celula.items():
        if not liga:
            continue
        pai = (saida[(familia, "")]["a"], saida[(familia, "")]["b"])
        n = contar_jogos(pk)
        proprio = ajustar(pk) if n >= MIN_N_JOGOS else None
        theta = encolher(proprio, pai, n, k) if proprio else pai
        saida[(familia, liga)] = {"a": theta[0], "b": theta[1], "n_jogos": n,
                                  "origem": "liga" if proprio else "familia",
                                  "k_fixo": caiu_no_fixo}
    return saida
