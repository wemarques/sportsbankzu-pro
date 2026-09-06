#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#231 - gera o artefato de taxas-base por (liga, mercado, selecao).

Entrada: o `picks_historicos.json` do backfill (#227,
`scripts/backfill_historico.py --todas`). Cada pick traz `league_id`,
`market` (rotulo do backfill) e `outcome` (0/1). A taxa-base e a media dos
desfechos na celula; o under e o complemento do over, BTTS No o do BTTS Yes.

Saida: backend/config/taxas_base.json, lido por
`backend/services/ancora_mercado.py` quando `PROB_SOURCE=mercado` e a
selecao nao tem par de odds em fonte nenhuma (cartoes, escanteios 4.5;
inventario #230-h). O artefato NAO entra no repo — vem da chave da
FootyStats.

    python scripts/backfill_historico.py --todas --saida picks_historicos.json
    python scripts/gerar_taxas_base.py --entrada picks_historicos.json
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.ancora_mercado import MIN_N_TAXA_BASE, chave_celula  # noqa: E402

_RE_GOLS = re.compile(r"^Over (\d+\.5) gols$")
_RE_ESC = re.compile(r"^Escanteios Over (\d+\.5)$")
_RE_CART = re.compile(r"^Cartoes Over (\d+\.5)$")


def traduzir(rotulo: str):
    """Rotulo do backfill -> ((mercado, selecao), (mercado, complemento)).

    Nomes de producao medidos em ev_classification.py (market_type/selection),
    nao presumidos."""
    r = (rotulo or "").strip()
    m = _RE_GOLS.match(r)
    if m:
        return ("Over/Under", f"Over {m.group(1)}"), ("Over/Under", f"Under {m.group(1)}")
    m = _RE_ESC.match(r)
    if m:
        return ("Corners", f"Corners Over {m.group(1)}"), ("Corners", f"Corners Under {m.group(1)}")
    m = _RE_CART.match(r)
    if m:
        return ("Cards", f"Over {m.group(1)}"), ("Cards", f"Under {m.group(1)}")
    if r == "BTTS Yes":
        return ("BTTS", "BTTS Yes"), ("BTTS", "BTTS No")
    return None


def gerar(picks, min_n: int = MIN_N_TAXA_BASE):
    soma = defaultdict(float)
    n = defaultdict(int)
    ignorados = 0
    for p in picks:
        par = traduzir(p.get("market", ""))
        if par is None or p.get("outcome") not in (0, 1, True, False):
            ignorados += 1
            continue
        liga = str(p.get("league_id") or "?")
        (mk, sel), (mk2, sel2) = par
        y = int(p["outcome"])
        for nivel in (liga, "*"):
            soma[(nivel, mk, sel)] += y
            n[(nivel, mk, sel)] += 1
            soma[(nivel, mk2, sel2)] += 1 - y
            n[(nivel, mk2, sel2)] += 1
    celulas = defaultdict(dict)
    for (nivel, mk, sel), k in n.items():
        celulas[nivel][chave_celula(mk, sel)] = {"taxa": round(soma[(nivel, mk, sel)] / k, 6), "n": k}
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": "backfill_historico (#227)",
        "min_n": min_n,
        "picks_lidos": len(picks),
        "picks_ignorados": ignorados,
        "celulas": dict(celulas),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="picks_historicos.json")
    ap.add_argument("--saida", default=str(Path(__file__).resolve().parents[1]
                                          / "backend" / "config" / "taxas_base.json"))
    ap.add_argument("--min-n", type=int, default=MIN_N_TAXA_BASE)
    args = ap.parse_args()
    with open(args.entrada, "r", encoding="utf-8") as f:
        picks = json.load(f)
    if isinstance(picks, dict):
        picks = picks.get("picks", [])
    art = gerar(picks, args.min_n)
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(art, f, ensure_ascii=False, indent=1)
    ligas = [k for k in art["celulas"] if k != "*"]
    print(f"picks lidos: {art['picks_lidos']}  ignorados: {art['picks_ignorados']}")
    print(f"ligas: {len(ligas)}  celulas totais (*): {len(art['celulas'].get('*', {}))}")
    for chave, cel in sorted(art["celulas"].get("*", {}).items()):
        print(f"  {chave:<32} taxa={cel['taxa']:.3f}  n={cel['n']}")
    print(f"\nartefato: {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
