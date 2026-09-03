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


def _piso(picks: Sequence[Dict[str, Any]]) -> Optional[float]:
    """Brier de prever sempre a taxa-base da celula (liga x mercado), desta amostra."""
    grupos: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for p in picks:
        grupos[(str(p.get("league_id", "?")), str(p.get("market", "?")))].append(p["outcome"])
    soma = 0.0
    total = 0
    for desfechos in grupos.values():
        taxa = sum(desfechos) / len(desfechos)
        soma += sum((taxa - y) ** 2 for y in desfechos)
        total += len(desfechos)
    return soma / total if total else None


def _skill(valor: Optional[float], piso: Optional[float]) -> Optional[float]:
    if valor is None or not piso:
        return None
    return (piso - valor) / piso * 100


def _por_liga(picks: Sequence[Dict[str, Any]], reamostras: int) -> None:
    """#227-d: a tabela que responde "regra ou excecao?" — uma linha por liga."""
    ligas: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        ligas[str(p.get("league_id", "?"))].append(p)
    if len(ligas) < 2:
        return
    print("\n── POR LIGA (Brier; skill = ganho sobre o piso da propria liga) ──")
    print(f"{'liga':<22}{'n':>6}{'modelo':>9}{'mercado':>9}{'piso':>8}"
          f"{'skill mod':>11}{'skill mkt':>11}{'dif':>9}{'IC95 da dif':>22}  leitura")
    linhas = []
    for liga, grupo in ligas.items():
        bm, bk, pi = _brier(grupo, "prob_modelo"), _brier(grupo, "prob"), _piso(grupo)
        dif = _ic_da_diferenca(grupo, _brier, reamostras)
        if bm is None or bk is None or pi is None or dif is None:
            continue
        linhas.append((liga, len(grupo), bm, bk, pi, _skill(bm, pi), _skill(bk, pi), dif))
    # da pior para a melhor skill do modelo
    linhas.sort(key=lambda r: r[5])
    for liga, n, bm, bk, pi, sm, sk, (d, lo, hi) in linhas:
        if math.isnan(lo):
            leitura = "IC indisponivel"
        elif lo > 0:
            leitura = "MERCADO melhor"
        elif hi < 0:
            leitura = "MODELO melhor"
        else:
            leitura = "empate"
        abaixo = "  <- abaixo do piso" if sm < 0 else ""
        print(f"{liga[:21]:<22}{n:>6}{bm:>9.4f}{bk:>9.4f}{pi:>8.4f}"
              f"{sm:>+10.2f}%{sk:>+10.2f}%{d:>+9.4f}  [{lo:+.4f}, {hi:+.4f}]  "
              f"{leitura}{abaixo}")
    abaixo = sum(1 for r in linhas if r[5] < 0)
    mkt = sum(1 for r in linhas if r[7][1] > 0)
    print(f"\n{len(linhas)} liga(s): modelo abaixo do piso em {abaixo}; "
          f"mercado melhor (IC exclui 0) em {mkt}.")


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
    #
    # #227-c: a taxa-base aqui e a DA PROPRIA AMOSTRA — o melhor constante
    # possivel para estes jogos, que ninguem conheceria antes deles. E um piso
    # otimista de proposito: quem passa dele carrega informacao por jogo de
    # verdade; quem fica abaixo esta piorando o palpite trivial. Na
    # championship o mercado passou por 0.30% e o modelo ficou 7.26% abaixo.
    print("\n── PISO: prever sempre a taxa-base da celula (taxa DESTA amostra) ──")
    piso = _piso(picks)
    bm = _brier(picks, "prob_modelo")
    bk = _brier(picks, "prob")
    print(f"piso (taxa-base) {piso:.4f} | modelo {bm:.4f} | mercado {bk:.4f}")
    for nome, val in (("modelo", bm), ("mercado", bk)):
        ganho = _skill(val, piso)
        print(f"  {nome:8s} skill score vs piso: {ganho:+.2f}%"
              + ("   <- pior que nao saber nada" if ganho < 0 else ""))

    _por_liga(picks, args.reamostras)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
