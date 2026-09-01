#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#215 - roda o comparador contra a producao ou um arquivo.

    python scripts/comparar_ancora.py --ligas championship,league-one
    python scripts/comparar_ancora.py --arquivo rodada.json

Confronta, por linha de mercado, a probabilidade CRUA e a CALIBRADA contra a
contagem empirica da FootyStats. Serve para decidir a quarentena dos .pkl com
medida, nao com opiniao.
"""
import argparse
import json
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from backend.services.comparador_ancora import comparar  # noqa: E402

BASE = "https://sportsbankzu-pro-well.vercel.app/api/matches/fetch"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ligas", default="championship,league-one")
    ap.add_argument("--data", default="today")
    ap.add_argument("--arquivo")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    jogos = []
    if a.arquivo:
        b = json.load(open(a.arquivo, encoding="utf-8"))
        jogos = b.get("matches", b) if isinstance(b, dict) else b
    else:
        for lg in [x.strip() for x in a.ligas.split(",") if x.strip()]:
            try:
                with urllib.request.urlopen(f"{BASE}?leagues={lg}&date={a.data}", timeout=150) as r:
                    jogos.extend(json.load(r).get("matches", []))
            except Exception as e:
                print(f"  ! {lg}: {type(e).__name__}: {e}", file=sys.stderr)

    c = comparar(jogos)
    if a.json:
        print(json.dumps({"resumo": c.resumo(), "veredito": c.veredito(),
                          "linhas": [vars(l) for l in c.linhas]},
                         ensure_ascii=False, indent=2, default=str))
        return 0

    for l in c.linhas:
        print("  " + l.linha())
    r = c.resumo()
    print(f"\n{r['linhas']} linhas comparadas ({r['sem_ancora']} mercados sem ancora empirica)")
    for nome in ("crua", "calibrada"):
        b = r[nome]
        if b:
            print(f"  {nome:<10} vies medio {b['vies_medio']:+6.1f}pp | "
                  f"erro absoluto medio {b['erro_absoluto_medio']:5.1f}pp | n={b['n']}")
    print(f"\n=> {c.veredito()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
