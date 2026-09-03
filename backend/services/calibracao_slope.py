"""Inclinacao e intercepto de calibracao (#220).

Por que este instrumento, e nao a decomposicao de Brier
-------------------------------------------------------
A decomposicao de Murphy (incerteza / resolucao / confiabilidade) e a resposta
de manual, mas precisa de binning, e com n entre 25 e 200 por celula o termo de
confiabilidade fica dominado por ruido de bin. A inclinacao de calibracao nao
precisa de bin nenhum: e a regressao logistica do desfecho sobre logit(p).

    y ~ a + b * logit(p)

    b ~ 1  -> a forma esta certa
    b < 1  -> as previsoes variam mais que a realidade (falta RESOLUCAO)
    b > 1  -> as previsoes variam menos que a realidade
    a != 0 -> vies constante para cima ou para baixo

Um numero, sem bin, funcionando a n=100.

O que ele deve confirmar ou derrubar
------------------------------------
Nos dois pontos que temos hoje - previu 54,9% e aconteceu 71,5%; previu 83,6% e
aconteceu 76,4% - a previsao varia 28,7pp e a realidade 4,9pp. Isso e uma
inclinacao de ~0,17. Se confirmar com n de verdade, a conclusao nao e "calibrar
melhor": nenhum metodo de calibracao conserta resolucao, porque todos sao
transformacoes monotonas de UMA dimensao. Isotonica, Platt e Beta aplicados a
um sinal de inclinacao 0,17 devolvem um sinal igualmente cego, so que rotulado
com honestidade - as probabilidades colapsam perto da media da liga, o EV vai a
zero e o sistema para de publicar. Convem saber que e esse o resultado
esperado, senao a leitura vira "o calibrador quebrou".

Duas armadilhas que este modulo evita de proposito
--------------------------------------------------
1. **Bootstrap por JOGO, nao por pick.** Over 2.5 e BTTS do mesmo jogo nao sao
   observacoes independentes. Reamostrar picks infla a significancia.
2. **Correcao para multiplos testes.** 22 ligas x ~20 mercados = 440 celulas.
   A 95%, ~22 saem "significativas" por puro acaso. Benjamini-Hochberg.
"""

from __future__ import annotations

import logging
import math
import random
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("sportsbankzu.calibracao")

MIN_N = 30          # abaixo disso a inclinacao e ruido; reportamos mesmo assim, marcada
_EPS = 1e-6
_INCLINACAO_MAXIMA = 25.0   # acima disso e separacao completa, nao sinal


def _logit(p: float) -> float:
    p = min(max(float(p), _EPS), 1.0 - _EPS)
    return math.log(p / (1.0 - p))


def _ha_separacao_completa(x: Sequence[float], y: Sequence[int]) -> bool:
    """Existe um corte em x que separa perfeitamente 0 de 1?

    Nesse caso a maxima verossimilhanca nao existe (a inclinacao vai a
    infinito) e o IRLS para num numero arbitrario que PARECE uma inclinacao
    normal. Detectar pela geometria e exato; detectar por magnitude do
    coeficiente nao e.
    """
    pares = sorted(zip(x, y))
    ys = [yi for _x, yi in pares]
    # sem sobreposicao = todos os 0 de um lado e todos os 1 do outro
    trocas = sum(1 for i in range(1, len(ys)) if ys[i] != ys[i - 1])
    if trocas <= 1:
        return True
    return False


def _log_verossimilhanca(x, y, a: float, b: float) -> float:
    total = 0.0
    for xi, yi in zip(x, y):
        eta = min(max(a + b * xi, -35.0), 35.0)
        total += (yi * eta) - math.log1p(math.exp(eta)) if eta < 30 else (yi * eta) - eta
    return total


def ajustar_logistica(x: Sequence[float], y: Sequence[int],
                      max_iter: int = 100, tol: float = 1e-8
                      ) -> Optional[Tuple[float, float]]:
    """IRLS com meio-passo. Devolve (intercepto, inclinacao) ou None.

    Sem sklearn e sem scipy de proposito: o #182 registra que o import de scipy
    no topo quebrou a Lambda de producao. Isto e aritmetica de duas variaveis.

    O meio-passo (step halving) nao e enfeite. Com poucos valores distintos de
    x e bem separados - que e exatamente o formato de um mercado de duas linhas
    - o passo de Newton puro salta longe demais, a matriz fica singular na
    iteracao seguinte e o ajuste devolve None num caso que TEM solucao. Aceitar
    o passo so quando ele melhora a verossimilhanca resolve.
    """
    n = len(x)
    if n < 3 or len(y) != n:
        return None
    if len(set(y)) < 2:
        return None                      # so 0 ou so 1: inclinacao indefinida
    if _ha_separacao_completa(x, y):
        return None                      # MV nao existe; ver docstring
    a, b = 0.0, 0.0                      # comeca no modelo nulo, nao em b=1
    ll = _log_verossimilhanca(x, y, a, b)
    for _ in range(max_iter):
        s00 = s01 = s11 = 0.0
        g0 = g1 = 0.0
        for xi, yi in zip(x, y):
            eta = min(max(a + b * xi, -35.0), 35.0)
            mu = 1.0 / (1.0 + math.exp(-eta))
            w = max(mu * (1.0 - mu), 1e-10)
            r = yi - mu
            g0 += r
            g1 += r * xi
            s00 += w
            s01 += w * xi
            s11 += w * xi * xi
        det = s00 * s11 - s01 * s01
        if abs(det) < 1e-12:
            break
        da = (s11 * g0 - s01 * g1) / det
        db = (s00 * g1 - s01 * g0) / det

        passo = 1.0
        aceito = False
        for _ in range(30):
            na, nb = a + passo * da, b + passo * db
            nll = _log_verossimilhanca(x, y, na, nb)
            if nll >= ll - 1e-12:
                a, b, ll_novo = na, nb, nll
                aceito = True
                break
            passo /= 2.0
        if not aceito:
            break
        delta = abs(passo * da) + abs(passo * db)
        ll = ll_novo
        if delta < tol:
            break
    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    if abs(b) > _INCLINACAO_MAXIMA:      # cinto e suspensorio
        return None
    return a, b


def inclinacao(picks: Sequence[Dict[str, Any]],
               campo_prob: str = "prob") -> Optional[Dict[str, Any]]:
    """Inclinacao e intercepto de um conjunto de picks resolvidos.

    Cada pick: {"prob": float, "outcome": 0|1, "match_id": str}
    """
    xs, ys = [], []
    for p in picks:
        prob, out = p.get(campo_prob), p.get("outcome")
        if prob is None or out is None:
            continue
        xs.append(_logit(float(prob)))
        ys.append(1 if int(out) else 0)
    if not xs:
        return None
    fit = ajustar_logistica(xs, ys)
    if fit is None:
        return None
    a, b = fit
    return {
        "n": len(xs),
        "intercepto": round(a, 4),
        "inclinacao": round(b, 4),
        "abaixo_de_min_n": len(xs) < MIN_N,
        "prob_media": round(sum(1.0 / (1.0 + math.exp(-v)) for v in xs) / len(xs), 4),
        "freq_observada": round(sum(ys) / len(ys), 4),
    }


def _por_jogo(picks: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    grupos: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        grupos[str(p.get("match_id", id(p)))].append(p)
    return list(grupos.values())


def inclinacao_com_ic(picks: Sequence[Dict[str, Any]], reamostras: int = 1000,
                      alpha: float = 0.05, semente: int = 42,
                      campo_prob: str = "prob") -> Optional[Dict[str, Any]]:
    """Inclinacao com IC por bootstrap de BLOCO — o bloco e o jogo.

    Over 2.5 e BTTS do mesmo jogo compartilham o placar. Reamostrar picks
    trataria os dois como evidencia independente e estreitaria o IC
    artificialmente. O bloco corrige isso.
    """
    base = inclinacao(picks, campo_prob)
    if base is None:
        return None
    blocos = _por_jogo(picks)
    if len(blocos) < 3:
        base["ic95"] = None
        base["jogos"] = len(blocos)
        return base

    rng = random.Random(semente)
    amostras: List[float] = []
    for _ in range(reamostras):
        sorteio: List[Dict[str, Any]] = []
        for _ in range(len(blocos)):
            sorteio.extend(blocos[rng.randrange(len(blocos))])
        r = inclinacao(sorteio, campo_prob)
        if r is not None:
            amostras.append(r["inclinacao"])
    if len(amostras) < 20:
        base["ic95"] = None
    else:
        amostras.sort()
        lo = amostras[int((alpha / 2) * len(amostras))]
        hi = amostras[min(len(amostras) - 1, int((1 - alpha / 2) * len(amostras)))]
        base["ic95"] = [round(lo, 4), round(hi, 4)]
        # "1 esta fora do IC" e o unico teste que interessa: a forma esta errada?
        base["difere_de_1"] = not (lo <= 1.0 <= hi)
        # e o teste que importa de verdade: existe ALGUMA resolucao?
        base["difere_de_0"] = not (lo <= 0.0 <= hi)
    base["jogos"] = len(blocos)
    base["reamostras"] = len(amostras)
    return base


def benjamini_hochberg(pvalores: Sequence[float], q: float = 0.05) -> List[bool]:
    """Controle de FDR. 440 celulas a 95% dao ~22 falsos positivos sem isto."""
    n = len(pvalores)
    if n == 0:
        return []
    ordem = sorted(range(n), key=lambda i: pvalores[i])
    corte = -1
    for posicao, i in enumerate(ordem, start=1):
        if pvalores[i] <= q * posicao / n:
            corte = posicao
    resultado = [False] * n
    for posicao, i in enumerate(ordem, start=1):
        if posicao <= corte:
            resultado[i] = True
    return resultado


def por_celula(picks: Sequence[Dict[str, Any]], reamostras: int = 400,
               campo_prob: str = "prob") -> List[Dict[str, Any]]:
    """Uma leitura por (liga, mercado), ordenada da inclinacao mais baixa."""
    celulas: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        celulas[(str(p.get("league_id", "?")), str(p.get("market", "?")))].append(p)
    saida = []
    for (liga, mercado), grupo in celulas.items():
        r = inclinacao_com_ic(grupo, reamostras=reamostras, campo_prob=campo_prob)
        if r is None:
            continue
        r["liga"] = liga
        r["mercado"] = mercado
        saida.append(r)
    saida.sort(key=lambda r: r["inclinacao"])
    return saida


def veredito(r: Dict[str, Any]) -> str:
    """Traducao curta da inclinacao para quem le o relatorio."""
    b = r.get("inclinacao")
    if b is None:
        return "sem leitura"
    if r.get("abaixo_de_min_n"):
        return f"n={r['n']} insuficiente (min {MIN_N})"
    if r.get("difere_de_0") is False:
        # #227-b: "IC inclui zero" nao e uma coisa, sao duas.
        #
        # Se o IC inclui 0 E TAMBEM 1, a medicao nao distingue previsor
        # perfeito de previsor cego — falta precisao, nao resolucao. Foi o que
        # aconteceu com o mercado na championship: inclinacao 0.983 com IC
        # [-0.06, 2.23] saiu rotulada "SEM RESOLUCAO", quando o ponto estava
        # em cima de 1. A casa de apostas nao e cega; o IC e largo porque as
        # probabilidades dela variam pouco, e inclinacao se estima com a
        # variancia de logit(p).
        #
        # Evidencia CONTRA resolucao exige o IC excluir 1: ai o dado esta
        # dizendo que a forma nao e a de um previsor com resolucao.
        if r.get("difere_de_1") is False:
            return "INCONCLUSIVO — IC cobre 0 e 1, nao da para distinguir"
        return "SEM RESOLUCAO — a previsao nao separa o que acontece"
    if b < 0:
        return "INVERTIDA — previsao mais alta acerta menos"
    if b < 0.5:
        return "resolucao muito baixa — calibrar nao resolve"
    if b < 0.8:
        return "previsoes extremas demais"
    if b <= 1.25:
        return "forma adequada"
    return "previsoes conservadoras demais"
