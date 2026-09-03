# -*- coding: utf-8 -*-
"""#227-b - modelo contra mercado, nos MESMOS picks, sem depender de variancia.

    python scripts/backfill_historico.py --liga championship --prob-de mercado --saida mercado.json
    python scripts/comparar_com_mercado.py --arquivo mercado.json

## Por que a inclinacao nao fecha a conta

Inclinacao de calibracao e estimada pela variancia de `logit(p)`: previsor que
varia pouco produz IC largo mesmo estando certo. Foi o que apareceu na
championship — mercado com inclinacao 0.983 e IC [-0.06, 2.23], rotulado "sem
resolucao" quando o ponto estava em cima de 1. O rotulo era artefato (#227-b
consertou o veredito), mas o IC largo continua la: com aquele n, a inclinacao
nao decide entre modelo e mercado.

Brier e log-loss nao tem esse problema. Sao medidas de ERRO por pick, sem
binning e sem depender de espalhamento. E como os dois previsores olham as
MESMAS partidas, a comparacao pode ser **emparelhada**: reamostra-se o jogo, e
os dois vao juntos. A diferenca emparelhada tem IC muito mais estreito que as
duas medidas separadas, porque o ruido comum a dupla se cancela.

## O que sai

Diferenca `modelo - mercado`. Positiva = modelo erra MAIS. IC que exclui zero =
diferenca real na amostra medida.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_EPS = 1e-9


def _brier(picks: Sequence[Dict[str, Any]], campo: str) -> Optional[float]:
    vals = [(p[campo] - p["outcome"]) ** 2 for p in picks if p.get(campo) is not None]
    return sum(vals) / len(vals) if vals else None


def _logloss(picks: Sequence[Dict[str, Any]], campo: str) -> Optional[float]:
    vals = []
    for p in picks:
        prob = p.get(campo)
        if prob is None:
            continue
        prob = min(max(prob, 1e-6), 1 - 1e-6)
        y = p["outcome"]
        vals.append(-(y * math.log(prob) + (1 - y) * math.log(1 - prob)))
    return sum(vals) / len(vals) if vals else None


def _por_jogo(picks: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Bloco = jogo (#220). Over 2.5 e BTTS do mesmo jogo dividem o placar."""
    grupos: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        grupos[p.get("match_id")].append(p)
    return list(grupos.values())


def _ic_da_diferenca(picks: Sequence[Dict[str, Any]], metrica,
                     reamostras: int = 1000, semente: int = 227
                     ) -> Optional[Tuple[float, float, float]]:
    """(diferenca, ic_baixo, ic_alto) para `modelo - mercado`, emparelhado."""
    a = metrica(picks, "prob_modelo")
    b = metrica(picks, "prob")
    if a is None or b is None:
        return None
    blocos = _por_jogo(picks)
    if len(blocos) < 3:
        return (a - b, float("nan"), float("nan"))

    rng = random.Random(semente)
    difs: List[float] = []
    for _ in range(reamostras):
        sorteio: List[Dict[str, Any]] = []
        for _ in range(len(blocos)):
            sorteio.extend(blocos[rng.randrange(len(blocos))])
        x = metrica(sorteio, "prob_modelo")
        y = metrica(sorteio, "prob")
        if x is not None and y is not None:
            difs.append(x - y)
    if len(difs) < 20:
        return (a - b, float("nan"), float("nan"))
    difs.sort()
    return (a - b, difs[int(0.025 * len(difs))],
            difs[min(len(difs) - 1, int(0.975 * len(difs)))])


def _linha(rotulo: str, picks: Sequence[Dict[str, Any]], reamostras: int) -> None:
    n = len(picks)
    bm = _brier(picks, "prob_modelo")
    bk = _brier(picks, "prob")
    dif = _ic_da_diferenca(picks, _brier, reamostras)
    if bm is None or bk is None or dif is None:
        print(f"{rotulo[:29]:<30}{n:>6}  sem par comparavel")
        return
    d, lo, hi = dif
    if math.isnan(lo):
        marca = "IC indisponivel"
    elif lo > 0:
        marca = "MERCADO melhor"
    elif hi < 0:
        marca = "MODELO melhor"
    else:
        marca = "empate (IC cobre 0)"
    print(f"{rotulo[:29]:<30}{n:>6}{bm:>9.4f}{bk:>9.4f}{d:>+9.4f}"
          f"  [{lo:+.4f}, {hi:+.4f}]  {marca}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo", required=True,
                    help="saida de backfill_historico.py --prob-de mercado")
    ap.add_argument("--reamostras", type=int, default=600)
    args = ap.parse_args()

    with open(args.arquivo, encoding="utf-8") as f:
        picks = json.load(f)

    faltando = [p for p in picks if p.get("prob_modelo") is None]
    if faltando:
        print(f"{len(faltando)} pick(s) sem `prob_modelo` — o arquivo tem de vir de "
              f"`--prob-de mercado`, que guarda as duas probabilidades",
              file=sys.stderr)
        if len(faltando) == len(picks):
            return 2

    picks = [p for p in picks if p.get("prob_modelo") is not None
             and p.get("prob") is not None]
    if not picks:
        print("nada a comparar", file=sys.stderr)
        return 1

    print("modelo x mercado, MESMOS picks, bootstrap emparelhado por jogo")
    print("diferenca = modelo - mercado. Positiva = o modelo erra mais.\n")

    print("── BRIER (erro quadratico, menor e melhor) ──")
    print(f"{'celula':<30}{'n':>6}{'modelo':>9}{'mercado':>9}{'dif':>9}"
          f"{'IC95 da dif':>22}  leitura")
    _linha("TODAS", picks, args.reamostras)
    celulas: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        celulas[str(p.get("market", "?"))].append(p)
    for mercado in sorted(celulas, key=lambda m: -len(celulas[m])):
        _linha(mercado, celulas[mercado], args.reamostras)

    print("\n── LOG-LOSS (menor e melhor) ──")
    dif = _ic_da_diferenca(picks, _logloss, args.reamostras)
    if dif:
        d, lo, hi = dif
        print(f"modelo {_logloss(picks, 'prob_modelo'):.4f} | "
              f"mercado {_logloss(picks, 'prob'):.4f} | "
              f"dif {d:+.4f}  IC95 [{lo:+.4f}, {hi:+.4f}]")

    # Referencia de piso: prever sempre a taxa-base da celula. Um previsor que
    # nao bate isto nao esta usando informacao nenhuma sobre o jogo.
    print("\n── PISO: prever sempre a taxa-base da celula ──")
    piso = 0.0
    total = 0
    for mercado, grupo in celulas.items():
        taxa = sum(p["outcome"] for p in grupo) / len(grupo)
        piso += sum((taxa - p["outcome"]) ** 2 for p in grupo)
        total += len(grupo)
    piso /= total
    bm = _brier(picks, "prob_modelo")
    bk = _brier(picks, "prob")
    print(f"piso (taxa-base) {piso:.4f} | modelo {bm:.4f} | mercado {bk:.4f}")
    for nome, val in (("modelo", bm), ("mercado", bk)):
        ganho = (piso - val) / piso * 100
        print(f"  {nome:8s} skill score vs piso: {ganho:+.2f}%"
              + ("   <- pior que nao saber nada" if ganho < 0 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
