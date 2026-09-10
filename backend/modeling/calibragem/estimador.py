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
    # Variancia da estimativa de `a` cai com n: var_dentro ~ 1/n_medio. O que
    # se cancela na conta abaixo NAO e "a constante" — e o proprio `n_medio`:
    #     k = var_dentro / var_entre * n_medio = (1/n_medio) / var_entre * n_medio
    #       = 1 / var_entre
    # ou seja, `k` e o INVERSO da dispersao entre celulas, e nao uma contagem
    # de jogos, apesar de ser comparado com `n_efetivo` (que e). A escala
    # implicita esta na constante de proporcionalidade que foi tomada como 1.
    # Aproximacao deliberada: o que importa e a ordem de grandeza de `k`, o
    # resultado e preso em [1, 500] logo abaixo, e o piso duro de 20 jogos
    # (#079) protege o resto.
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


from backend.modeling.calibragem import (
    MIN_PICKS_PARA_VALIDAR_SEMENTE, N_PRIOR_NAO_VALIDADA, TETO_N_PRIOR,
    TOLERANCIA_CONCORDANCIA,
)


def medir_concordancia(semente: Sequence, ledger: Sequence) -> Tuple[float, int]:
    """Fracao dos picks sobrepostos em que as duas fontes ficam a < 2 pontos.

    Sobreposicao e por (match_id, familia, liga, selecao) — a chave completa
    do pick, agora que `Pick.selecao` existe (rodada de correcao 1). Sem a
    selecao, duas linhas do mesmo jogo e familia (ex.: "Corners Over 1.5" e
    "Corners Over 2.5") cairiam no mesmo balde e o pareamento escolheria a
    `p_raw` mais proxima em vez de comparar a mesma aposta — e mais
    candidatos no balde so ajudam a achar um mais proximo, entao a
    concordancia nunca cairia, so subiria. Com a chave completa o balde vira
    unitario no caso normal, e cada candidato casado e CONSUMIDO (`.pop`) para
    que nenhum valor do ledger seja usado duas vezes.
    """
    idx = defaultdict(list)
    for p in ledger:
        idx[(p.match_id, p.familia, p.liga, p.selecao)].append(p.p_raw)

    total = concordantes = 0
    for p in semente:
        candidatos = idx.get((p.match_id, p.familia, p.liga, p.selecao))
        if not candidatos:
            continue
        total += 1
        distancias = [abs(p.p_raw - q) for q in candidatos]
        i_mais_proximo = distancias.index(min(distancias))
        if distancias[i_mais_proximo] < TOLERANCIA_CONCORDANCIA:
            concordantes += 1
        candidatos.pop(i_mais_proximo)
    if total == 0:
        return (0.0, 0)
    return (concordantes / total, total)


def n_prior_da_concordancia(concordancia: float, n_sobrepostos: int) -> Tuple[int, str]:
    """(n_prior, status). Nada bloqueia: a semente entra de qualquer forma."""
    if n_sobrepostos < MIN_PICKS_PARA_VALIDAR_SEMENTE:
        return (N_PRIOR_NAO_VALIDADA, "semente_nao_validada")
    n = int(round(TETO_N_PRIOR * max(0.0, min(1.0, concordancia))))
    return (n, "semente_validada")


def aplicar_semente(ajuste_ledger: Dict[Tuple[str, str], dict],
                    ajuste_semente: Dict[Tuple[str, str], dict],
                    n_prior: int) -> Dict[Tuple[str, str], dict]:
    """theta = (n_ledger*ledger + n_prior*semente) / (n_ledger + n_prior).

    O decaimento da semente nao e um mecanismo separado: e a propria
    aritmetica da media ponderada. Conforme `n_jogos` do ledger cresce, o
    peso de `n_prior` encolhe sozinho — nao ha fator de decaimento explicito
    a manter em dia.
    """
    saida: Dict[Tuple[str, str], dict] = {}
    for chave in set(ajuste_ledger) | set(ajuste_semente):
        no_ledger = ajuste_ledger.get(chave)
        na_semente = ajuste_semente.get(chave)
        if no_ledger is None:
            saida[chave] = dict(na_semente, origem="semente")
            continue
        if na_semente is None or n_prior <= 0:
            saida[chave] = dict(no_ledger)
            continue
        n_l = no_ledger["n_jogos"]
        peso = n_l / (n_l + n_prior)
        saida[chave] = dict(
            no_ledger,
            a=peso * no_ledger["a"] + (1 - peso) * na_semente["a"],
            b=peso * no_ledger["b"] + (1 - peso) * na_semente["b"],
            origem=f"{no_ledger['origem']}+semente",
        )
    return saida
