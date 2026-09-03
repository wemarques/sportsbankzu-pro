#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#220 - mede a inclinacao de calibracao por liga e mercado.

    python scripts/medir_inclinacao.py --arquivo picks.json
    python scripts/medir_inclinacao.py --ledger --desde 2026-09-01

O JSON e uma lista de {"prob", "outcome", "match_id", "league_id", "market"}.
Com --ledger, le do prediction_ledger (#218) juntando ledger_outcomes.

A pergunta que este script responde nao e "o calibrador esta bom" e sim "existe
resolucao para calibrar". Inclinacao perto de zero significa que a previsao nao
separa o que acontece do que nao acontece, e nesse caso nenhum calibrador
ajuda: todos sao transformacoes monotonas de uma dimensao.
"""
import argparse
import json
import os
import sys

# #216/#220 - dirname duas vezes funciona no Windows; rsplit("/scripts/") nao.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.calibracao_slope import (   # noqa: E402
    por_celula, inclinacao_com_ic, veredito, MIN_N,
)


def _do_ledger(desde: str, campo: str):
    import psycopg2
    conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""))
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT l.match_id, l.league_id,
               l.market || ' ' || COALESCE(l.selection, '') AS market,
               l.{campo}, o.outcome
          FROM prediction_ledger l
          JOIN ledger_outcomes o
            ON o.match_id = l.match_id
           AND o.market = l.market
           AND o.selection = COALESCE(l.selection, '')   -- #228: por selecao
         WHERE l.published_at >= %s AND l.{campo} IS NOT NULL
        """,
        (desde,),
    )
    linhas = [
        {"match_id": r[0], "league_id": r[1], "market": r[2],
         "prob": float(r[3]), "outcome": int(r[4])}
        for r in cur.fetchall()
    ]
    cur.close()
    conn.close()
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--desde", default="2026-01-01")
    ap.add_argument("--campo", default="calibrated_prob",
                    choices=["raw_prob", "iso_prob", "calibrated_prob"],
                    help="qual das tres colunas do #216 medir")
    ap.add_argument("--reamostras", type=int, default=1000)
    args = ap.parse_args()

    if args.ledger:
        picks = _do_ledger(args.desde, args.campo)
    elif args.arquivo:
        with open(args.arquivo, encoding="utf-8") as f:
            picks = json.load(f)
    else:
        ap.error("use --arquivo ou --ledger")
        return 2

    if not picks:
        print("nenhum pick resolvido no periodo.")
        return 1

    geral = inclinacao_com_ic(picks, reamostras=args.reamostras)
    print(f"\n=== GERAL ({args.campo}) ===")
    print(f"  n={geral['n']} picks em {geral['jogos']} jogos")
    print(f"  inclinacao = {geral['inclinacao']}  IC95 {geral.get('ic95')}")
    print(f"  intercepto = {geral['intercepto']}")
    print(f"  prob media {geral['prob_media']} vs frequencia {geral['freq_observada']}")
    print(f"  -> {veredito(geral)}")

    print(f"\n=== POR CELULA (liga x mercado, min n={MIN_N}) ===")
    linhas = por_celula(picks, reamostras=max(200, args.reamostras // 4),
                        campo_prob="prob")
    print(f"{'liga':<22}{'mercado':<22}{'n':>5}{'incl':>8}{'IC95':>20}  veredito")
    for r in linhas:
        ic = r.get("ic95")
        ics = f"[{ic[0]:.2f}, {ic[1]:.2f}]" if ic else "-"
        print(f"{r['liga'][:21]:<22}{r['mercado'][:21]:<22}{r['n']:>5}"
              f"{r['inclinacao']:>8.3f}{ics:>20}  {veredito(r)}")

    # #227-b: separar as duas leituras que antes vinham somadas. IC que cobre
    # 0 E 1 nao e evidencia contra resolucao — e ausencia de precisao, e
    # tratar as duas como a mesma coisa foi o que quase fez o mercado (ponto
    # em cima de 1) ser lido como previsor cego.
    validas = [r for r in linhas if not r["abaixo_de_min_n"]]
    sem_resolucao = [r for r in validas
                     if r.get("difere_de_0") is False and r.get("difere_de_1") is True]
    inconclusivas = [r for r in validas
                     if r.get("difere_de_0") is False and r.get("difere_de_1") is False]
    if sem_resolucao:
        print(f"\n{len(sem_resolucao)} celula(s) SEM RESOLUCAO (o IC exclui 1). "
              "Calibrar nao resolve nenhuma delas.")
    if inconclusivas:
        print(f"{len(inconclusivas)} celula(s) INCONCLUSIVAS (o IC cobre 0 e 1) — "
              "falta precisao, nao resolucao. Mais jogos estreitam; calibrar nao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
