#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#209 - roda o auditor de premissas contra a producao ou contra um arquivo.

    python scripts/auditar_premissas.py --ligas championship,league-one
    python scripts/auditar_premissas.py --arquivo rodada.json --json

Sai com codigo 1 se houver violacao CRITICA - entao serve direto no CI e como
acao de cron. Nao depende de resultado de jogo: audita a coerencia interna da
saida, e por isso pode rodar antes da bola rolar.
"""
import argparse
import json
import os
import sys
import urllib.request

# #220 - o rsplit("/scripts/") nao casa com barra invertida: no Windows o
# sys.path recebia o caminho do ARQUIVO e o import de `backend` falhava.
# O #216 corrigiu comparar_ancora.py e verificar_manifesto.py e passou
# por este. dirname duas vezes funciona nos dois sistemas.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.auditor_premissas import auditar, SEV_CRITICO  # noqa: E402

BASE = "https://sportsbankzu-pro-well.vercel.app/api/matches/fetch"


def baixar(ligas, data):
    jogos = []
    for liga in ligas:
        url = f"{BASE}?leagues={liga}&date={data}"
        try:
            with urllib.request.urlopen(url, timeout=150) as r:
                jogos.extend(json.load(r).get("matches", []))
        except Exception as e:
            print(f"  ! {liga}: {type(e).__name__}: {e}", file=sys.stderr)
    return jogos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ligas", default="championship,league-one")
    ap.add_argument("--data", default="today")
    ap.add_argument("--arquivo", help="JSON com {'matches': [...]} ou uma lista de jogos")
    ap.add_argument("--json", action="store_true", help="saida em JSON")
    a = ap.parse_args()

    if a.arquivo:
        bruto = json.load(open(a.arquivo, encoding="utf-8"))
        jogos = bruto.get("matches", bruto) if isinstance(bruto, dict) else bruto
    else:
        jogos = baixar([x.strip() for x in a.ligas.split(",") if x.strip()], a.data)

    rel = auditar(jogos)

    if a.json:
        print(json.dumps(rel.para_dict(), ensure_ascii=False, indent=2))
    else:
        print(rel.resumo())
        ordem = {"critico": 0, "alto": 1, "medio": 2}
        for v in sorted(rel.violacoes, key=lambda x: ordem.get(x.severidade, 9)):
            print("  " + v.linha())

    return 1 if any(v.severidade == SEV_CRITICO for v in rel.violacoes) else 0


if __name__ == "__main__":
    sys.exit(main())
