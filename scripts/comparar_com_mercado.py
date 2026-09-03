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


def _ic_par(picks, campo_a: str, campo_b: str, metrica, reamostras: int, semente: int = 229):
    """(dif, lo, hi) de `campo_a - campo_b`, emparelhado por jogo."""
    a, b = metrica(picks, campo_a), metrica(picks, campo_b)
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
        x, y = metrica(sorteio, campo_a), metrica(sorteio, campo_b)
        if x is not None and y is not None:
            difs.append(x - y)
    if len(difs) < 20:
        return (a - b, float("nan"), float("nan"))
    difs.sort()
    return (a - b, difs[int(0.025 * len(difs))],
            difs[min(len(difs) - 1, int(0.975 * len(difs)))])


def _decompor(picks: Sequence[Dict[str, Any]], campo: str) -> Optional[Dict[str, float]]:
    """#229-a - Brier = piso + ESPALHAMENTO - 2*SINAL, por celula (liga x mercado).

        (p - y)^2 = (p - ybar)^2  -  2 (p - ybar)(y - ybar)  +  (y - ybar)^2
                    espalhamento     sinal (covariancia)       piso

    Dois previsores sem resolucao (sinal ~ 0) diferem em Brier SO pelo
    espalhamento: ganha o que varia menos em torno da taxa-base. Chamar isso
    de "extrai algo" seria confundir encolher ruido com achar informacao — e
    foi exatamente o rotulo que a primeira versao deste script imprimiu para
    os escanteios na rodada real. `sinal` e a unica coluna que mede
    informacao; `espalhamento` mede quanto o previsor se afasta do piso, com
    ou sem motivo.
    """
    grupos: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        if p.get(campo) is None:
            continue
        grupos[(str(p.get("league_id", "?")), str(p.get("market", "?")))].append(p)
    esp = sinal = 0.0
    n = 0
    for grupo in grupos.values():
        ybar = sum(p["outcome"] for p in grupo) / len(grupo)
        for p in grupo:
            dp, dy = p[campo] - ybar, p["outcome"] - ybar
            esp += dp * dp
            sinal += dp * dy
            n += 1
    if not n:
        return None
    return {"espalhamento": esp / n, "sinal": sinal / n}


def _motor_x_ingenuo(picks: Sequence[Dict[str, Any]], reamostras: int) -> None:
    """#229 - isola o MOTOR do INSUMO.

    Os tres previsores veem as mesmas partidas. `prob_modelo` e o motor sobre
    medias moveis; `prob_ingenuo` e um Poisson direto sobre as MESMAS medias.
    A diferenca entre os dois e o que o motor faz — nada mais entra.
    """
    trio = [p for p in picks if p.get("prob_ingenuo") is not None
            and p.get("prob_modelo") is not None]
    if not trio:
        print("\n(sem prob_ingenuo no arquivo — gere de novo com o backfill atual)")
        return
    piso = _piso(trio)
    bm, bi, bk = (_brier(trio, "prob_modelo"), _brier(trio, "prob_ingenuo"),
                  _brier(trio, "prob"))
    print("\n── MOTOR x INGENUO (mesmas medias moveis; a diferenca e so o motor) ──")
    print(f"{'':<30}{'n':>6}{'Brier':>9}{'skill vs piso':>15}")
    for nome, val in (("motor (producao)", bm), ("ingenuo (Poisson direto)", bi),
                      ("mercado", bk)):
        sk = _skill(val, piso)
        print(f"{nome:<30}{len(trio):>6}{val:>9.4f}{sk:>+14.2f}%"
              + ("   <- abaixo do piso" if sk < 0 else ""))
    dif = _ic_par(trio, "prob_modelo", "prob_ingenuo", _brier, reamostras)
    if dif:
        d, lo, hi = dif
        if math.isnan(lo):
            leitura = "IC indisponivel"
        elif lo > 0:
            leitura = "MOTOR PIOR que o ingenuo em Brier"
        elif hi < 0:
            leitura = "motor MELHOR que o ingenuo em Brier"
        else:
            leitura = "empate em Brier"
        print(f"\nmotor - ingenuo = {d:+.4f}  IC95 [{lo:+.4f}, {hi:+.4f}]  -> {leitura}")

    # #229-a: Brier menor pode ser MAIS SINAL ou MENOS ESPALHAMENTO. So a
    # decomposicao diz qual — e a resposta muda o que se faz com o motor.
    print(f"\n{'decomposicao (Brier - piso = espalhamento - 2*sinal)':<52}"
          f"{'espalh.':>9}{'sinal':>9}{'Brier-piso':>12}")
    for nome, campo in (("motor", "prob_modelo"), ("ingenuo", "prob_ingenuo"),
                        ("mercado", "prob")):
        dec = _decompor(trio, campo)
        if not dec:
            continue
        b = _brier(trio, campo)
        excesso = b - piso if b is not None and piso is not None else float("nan")
        print(f"  {nome:<50}{dec['espalhamento']:>9.4f}{dec['sinal']:>+9.4f}{excesso:>+12.4f}")
    dm, di = _decompor(trio, "prob_modelo"), _decompor(trio, "prob_ingenuo")
    if dm and di:
        ganho_sinal = 2 * (dm["sinal"] - di["sinal"])
        ganho_esp = di["espalhamento"] - dm["espalhamento"]
        print(f"\n  de onde vem a diferenca motor - ingenuo ({d:+.4f}):")
        print(f"    por SINAL (o motor acha mais informacao) ....... {-ganho_sinal:+.4f}")
        print(f"    por ESPALHAMENTO (o motor varia menos) ......... {-ganho_esp:+.4f}")
        if abs(ganho_sinal) < 0.15 * abs(ganho_esp) and ganho_esp > 0:
            print("    -> o motor ganha por ENCOLHER, nao por enxergar: sem resolucao nos dois,"
                  " Brier menor e so menos ruido")
        elif ganho_sinal > 0.15 * max(abs(ganho_esp), 1e-9):
            print("    -> o motor ganha por SINAL: extrai informacao que o ingenuo nao tem")

    celulas: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in trio:
        celulas[str(p.get("market", "?"))].append(p)
    print(f"\n{'celula':<30}{'n':>6}{'motor':>9}{'ingenuo':>9}{'dif':>9}{'IC95':>22}")
    for mercado in sorted(celulas, key=lambda m: -len(celulas[m])):
        g = celulas[mercado]
        r = _ic_par(g, "prob_modelo", "prob_ingenuo", _brier, reamostras)
        if not r:
            continue
        d, lo, hi = r
        marca = "motor pior" if lo > 0 else ("motor melhor" if hi < 0 else "empate")
        print(f"{mercado[:29]:<30}{len(g):>6}{_brier(g, 'prob_modelo'):>9.4f}"
              f"{_brier(g, 'prob_ingenuo'):>9.4f}{d:>+9.4f}  [{lo:+.4f}, {hi:+.4f}]  {marca}")


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
    _motor_x_ingenuo(picks, args.reamostras)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
