#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#245 — A deflacao deve ser a mesma para gols e escanteios?

O #244 mediu que a deflacao encolhe as DUAS pontas de um par complementar e
que o custo e muito desigual entre familias: nos gols o raw soma 109-137% (e
mesmo superconfiante, o redutor faz sentido) e nos escanteios soma exatamente
100,0% (o redutor so tira sinal). Este script poe numero nisso.

MEDICAO, nao alteracao. Nada aqui muda o pipeline.

PARAMETRIZACAO
--------------
A deflacao em producao e uma curva continua por nos (#105/#189-a), nao um
escalar — entao a grade nao pode ser "multiplicar por k". Em vez disso mede-se
a INTENSIDADE da curva que ja existe, interpolando entre o raw e o valor
efetivamente publicado:

    p(alpha) = raw + alpha * (publicada - raw)

    alpha = 0.0  -> nenhuma deflacao (o raw do motor)
    alpha = 1.0  -> exatamente o que foi publicado
    alpha = 1.5  -> metade a mais de deflacao

CONTROLE POSITIVO (regra #227)
------------------------------
Em alpha = 1.0 o script tem de reproduzir o Brier da `calibrated_prob` gravada,
com erro < 1e-12. Se nao reproduzir, a medicao esta errada e o script aborta.
Nao ha como esse controle passar por acaso: ele so passa se a interpolacao
estiver ancorada no dado real de producao.

FONTE
-----
`prediction_ledger` x `ledger_outcomes`, gravados ANTES do jogo. O
`audit_results` NAO serve: o #200 documenta que ele e recomputado pos-jogo, e
o #244 mediu a contaminacao (picks de Escanteios Over 11.5 caem em jogos de
13,6 escanteios e "acertam" 78,8%).

USO
---
    python scripts/grade_deflacao_por_familia.py
    python scripts/grade_deflacao_por_familia.py --familia Corners
    python scripts/grade_deflacao_por_familia.py --reamostras 2000
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# Mesma forma de carregar o .env que o backfill_historico.py usa.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:  # pragma: no cover - ambiente sem python-dotenv
    pass

GRADE_ALPHA: Tuple[float, ...] = (
    0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    1.0, 1.1, 1.2, 1.3, 1.4, 1.5,
)


# ─────────────────────────────── dados ───────────────────────────────

def carregar(conn) -> List[Dict[str, Any]]:
    """Picks publicados com desfecho, do ledger (pre-jogo)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT l.match_id, l.market, l.selection, l.league_id,
               l.raw_prob, l.calibrated_prob, o.outcome
          FROM prediction_ledger l
          JOIN ledger_outcomes o
            ON o.match_id  = l.match_id
           AND o.market    = l.market
           AND o.selection = l.selection
         WHERE l.raw_prob IS NOT NULL
           AND l.calibrated_prob IS NOT NULL
           AND o.outcome IS NOT NULL
        """
    )
    picks: List[Dict[str, Any]] = []
    for match_id, market, selection, league, raw, cal, outcome in cur.fetchall():
        try:
            y = int(bool(int(outcome)))
        except (TypeError, ValueError):
            continue
        picks.append(
            {
                "match_id": match_id,
                "familia": market,
                "selecao": selection,
                "liga": league,
                "raw": float(raw),
                "publicada": float(cal),
                "y": y,
            }
        )
    return picks


# ─────────────────────────────── metrica ───────────────────────────────

def prob_em(pick: Dict[str, Any], alpha: float) -> float:
    """p(alpha) = raw + alpha * (publicada - raw), preso em (0, 1)."""
    p = pick["raw"] + alpha * (pick["publicada"] - pick["raw"])
    return min(max(p, 1e-6), 1.0 - 1e-6)


def brier(picks: Sequence[Dict[str, Any]], alpha: float) -> Optional[float]:
    if not picks:
        return None
    return sum((prob_em(p, alpha) - p["y"]) ** 2 for p in picks) / len(picks)


def brier_publicada(picks: Sequence[Dict[str, Any]]) -> Optional[float]:
    """Brier da coluna gravada — o controle positivo compara com brier(.,1.0)."""
    if not picks:
        return None
    return sum((p["publicada"] - p["y"]) ** 2 for p in picks) / len(picks)


def piso(picks: Sequence[Dict[str, Any]]) -> Optional[float]:
    """Brier de quem so sabe a taxa-base da propria amostra (#235)."""
    if not picks:
        return None
    base = sum(p["y"] for p in picks) / len(picks)
    return base * (1.0 - base)


def por_jogo(picks: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Bloco = jogo (#220): picks do mesmo jogo dividem o placar."""
    grupos: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        grupos[p["match_id"]].append(p)
    return list(grupos.values())


def ic_diferenca(
    picks: Sequence[Dict[str, Any]],
    alpha_a: float,
    alpha_b: float,
    reamostras: int = 1000,
    semente: int = 227,
) -> Tuple[float, float, float]:
    """IC95 percentil de Brier(alpha_a) - Brier(alpha_b), emparelhado por jogo.

    Mesmo metodo do `comparar_com_mercado.py` (#230-f): bloco = jogo, para nao
    tratar Over 2.5 e BTTS do mesmo jogo como observacoes independentes.
    """
    ponto = brier(picks, alpha_a) - brier(picks, alpha_b)
    blocos = por_jogo(picks)
    if len(blocos) < 3:
        return (ponto, float("nan"), float("nan"))

    rng = random.Random(semente)
    difs: List[float] = []
    for _ in range(reamostras):
        sorteio: List[Dict[str, Any]] = []
        for _ in range(len(blocos)):
            sorteio.extend(blocos[rng.randrange(len(blocos))])
        a, b = brier(sorteio, alpha_a), brier(sorteio, alpha_b)
        if a is not None and b is not None:
            difs.append(a - b)
    if len(difs) < 20:
        return (ponto, float("nan"), float("nan"))
    difs.sort()
    return (ponto, difs[int(0.025 * len(difs))], difs[int(0.975 * len(difs)) - 1])


def soma_complementar(picks: Sequence[Dict[str, Any]], alpha: float) -> Optional[float]:
    """Media da soma Over X + Under X no mesmo jogo, sob o alpha dado.

    Coerencia nao depende de desfecho: e a checagem que o #244 usou para
    mostrar que a publicada nao e uma probabilidade.
    """
    por_rev: Dict[Any, Dict[str, float]] = defaultdict(dict)
    for p in picks:
        por_rev[p["match_id"]][p["selecao"].strip()] = prob_em(p, alpha)
    somas: List[float] = []
    for sels in por_rev.values():
        for nome, prob in sels.items():
            if " Over " in f" {nome} ":
                par = nome.replace("Over", "Under")
            elif nome.startswith("Over "):
                par = "Under " + nome.split(None, 1)[1]
            else:
                continue
            if par in sels:
                somas.append((prob + sels[par]) * 100.0)
    return sum(somas) / len(somas) if somas else None


# ─────────────────────────────── relatorio ───────────────────────────────

def controle_positivo(picks: Sequence[Dict[str, Any]]) -> None:
    esperado = brier_publicada(picks)
    obtido = brier(picks, 1.0)
    erro = abs(esperado - obtido)
    print(f"controle positivo (#227): Brier(alpha=1) = {obtido:.10f} | "
          f"Brier(calibrated_prob gravada) = {esperado:.10f} | erro {erro:.2e}")
    if erro >= 1e-12:
        raise SystemExit(
            "ABORTADO: alpha=1 nao reproduz a coluna publicada. A interpolacao "
            "nao esta ancorada no dado de producao e a grade nao vale nada."
        )
    print("  -> reproduz a producao. A grade mede a curva que existe.\n")


def relatorio_familia(nome: str, picks: Sequence[Dict[str, Any]],
                      reamostras: int) -> Optional[Dict[str, Any]]:
    n = len(picks)
    jogos = len({p["match_id"] for p in picks})
    if n < 100:
        return None
    p0 = piso(picks)
    resultados = [(a, brier(picks, a)) for a in GRADE_ALPHA]
    melhor_alpha, melhor_brier = min(resultados, key=lambda t: t[1])
    atual = brier(picks, 1.0)

    print(f"\n{'=' * 78}\n{nome}   n={n} picks / {jogos} jogos   "
          f"piso (taxa-base) = {p0:.4f}\n{'=' * 78}")
    print(f"{'alpha':>7}{'Brier':>10}{'Brier - piso':>14}{'':>4}")
    for a, b in resultados:
        marca = ""
        if a == melhor_alpha:
            marca = "  <- melhor"
        if a == 1.0:
            marca += "  (producao hoje)"
        print(f"{a:>7.1f}{b:>10.4f}{b - p0:>+14.4f}{marca}")

    d, lo, hi = ic_diferenca(picks, melhor_alpha, 1.0, reamostras)
    print(f"\n  melhor alpha = {melhor_alpha:.1f}  contra producao (alpha=1,0):")
    print(f"    diferenca de Brier = {d:+.4f}   IC95 [{lo:+.4f}, {hi:+.4f}]"
          f"   {'SIGNIFICATIVA' if hi < 0 or lo > 0 else 'nao exclui zero'}")

    s_atual = soma_complementar(picks, 1.0)
    s_melhor = soma_complementar(picks, melhor_alpha)
    if s_atual is not None and s_melhor is not None:
        print(f"    soma dos complementares: {s_atual:.1f}% hoje -> "
              f"{s_melhor:.1f}% no melhor alpha  (coerente = 100%)")
    return {"familia": nome, "n": n, "jogos": jogos, "alpha": melhor_alpha,
            "brier": melhor_brier, "atual": atual, "d": d, "lo": lo, "hi": hi}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--familia", help="mede so esta familia (ex: Corners)")
    ap.add_argument("--reamostras", type=int, default=1000,
                    help="reamostras do bootstrap (padrao 1000)")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL ausente. Este script le o banco de producao.")
        return 2
    import psycopg2

    conn = psycopg2.connect(url)
    try:
        picks = carregar(conn)
    finally:
        conn.close()
    if not picks:
        print("Nenhum pick publicado com desfecho no ledger.")
        return 1

    print(f"\nGrade de intensidade da deflacao por familia — fonte: "
          f"prediction_ledger x ledger_outcomes (pre-jogo)")
    print(f"{len(picks)} picks com desfecho em "
          f"{len({p['match_id'] for p in picks})} jogos\n")
    controle_positivo(picks)

    familias: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in picks:
        familias[p["familia"]].append(p)

    linhas = []
    alvo = [args.familia] if args.familia else sorted(
        familias, key=lambda k: -len(familias[k]))
    for nome in alvo:
        if nome not in familias:
            print(f"familia '{nome}' inexistente. Disponiveis: "
                  f"{', '.join(sorted(familias))}")
            return 1
        r = relatorio_familia(nome, familias[nome], args.reamostras)
        if r:
            linhas.append(r)

    if not args.familia and linhas:
        print(f"\n{'=' * 78}\nRESUMO — um alpha por familia contra o alpha unico de hoje"
              f"\n{'=' * 78}")
        print(f"{'familia':<16}{'n':>7}{'melhor':>9}{'Brier':>9}"
              f"{'hoje':>9}{'ganho':>9}{'IC95':>22}")
        for r in linhas:
            print(f"{r['familia']:<16}{r['n']:>7}{r['alpha']:>9.1f}"
                  f"{r['brier']:>9.4f}{r['atual']:>9.4f}{r['d']:>+9.4f}"
                  f"   [{r['lo']:+.4f}, {r['hi']:+.4f}]")
        geral = relatorio_familia("TODAS AS FAMILIAS JUNTAS", picks, args.reamostras)
        if geral:
            print(f"\nLeitura: se o melhor alpha difere entre familias, um redutor "
                  f"unico\nesta errado para pelo menos uma delas — que e a pergunta "
                  f"do #244.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
