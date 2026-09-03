# -*- coding: utf-8 -*-
"""#226-a - QUAL chave carrega a contagem de escanteios na linha de partida.

O #225-a mediu `home_team_corner_count` em **0/48** na championship e eu conclui
dali que "escanteios estao fora" do backfill. O retrain do #226 achou **605**
partidas com contagem nas mesmas ligas. As duas medicoes nao podem estar certas
sobre a mesma coisa — e nao estao: `_extract_total_corners` le
`team_a_corners` ANTES de `home_team_corner_count`, e o #225-a so olhou o
segundo nome.

Este script nao chuta nome: varre **todas** as chaves da linha de partida cujo
nome contenha "corner" e conta quantas partidas finalizadas trazem valor util
(`None` e `-1` da FootyStats sao ausencia; `0` e resultado).

    python scripts/diagnostico_chaves_escanteios.py --liga championship
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from collections import Counter
from typing import Any, Dict, List

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
_RAIZ = pathlib.Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv
    for _nome in (".env", "backend/.env"):
        if (_RAIZ / _nome).exists():
            load_dotenv(_RAIZ / _nome, override=False)
except ImportError:
    pass


def _finalizada(partida: Dict[str, Any]) -> bool:
    return str(partida.get("status", "")).lower() in {"complete", "finished", "ft"}


def _util(valor: Any) -> bool:
    """`0` conta — zero escanteio e um resultado. `None` e `-1` nao contam."""
    return valor is not None and valor != -1 and valor != ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", default="championship")
    ap.add_argument("--temporadas", type=int, default=2)
    ap.add_argument("--verboso", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO if args.verboso else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    from backend.config.leagues_config import LEAGUES_CONFIG
    from backend.cron_handler import coletar_partidas_escanteios

    ligas = [l for l in LEAGUES_CONFIG if l.get("id") == args.liga]
    if not ligas:
        print(f"liga desconhecida: {args.liga}", file=sys.stderr)
        return 2

    dados = coletar_partidas_escanteios(ligas=ligas, n_temporadas=args.temporadas)
    partidas: List[Dict[str, Any]] = dados.get(args.liga) or []
    if not partidas:
        print("coleta vazia — rode com --verboso para ver o motivo", file=sys.stderr)
        return 1

    finalizadas = [p for p in partidas if _finalizada(p)]
    print(f"liga={args.liga}  partidas={len(partidas)}  finalizadas={len(finalizadas)}")
    if not finalizadas:
        print("nenhuma finalizada — nada a medir")
        return 1

    # Nomes DESCOBERTOS, nao presumidos.
    nomes = sorted({c for p in finalizadas for c in p if "corner" in c.lower()})
    if not nomes:
        print("nenhuma chave com 'corner' no nome — o endpoint nao traz escanteio")
        return 1

    print(f"\n{'chave':42s} {'preenchida':>12s}  {'%':>5s}   exemplo")
    print("-" * 82)
    for nome in nomes:
        preenchidas = [p[nome] for p in finalizadas if _util(p.get(nome))]
        pct = len(preenchidas) * 100 // len(finalizadas)
        exemplo = preenchidas[0] if preenchidas else "-"
        marca = "  <<<" if pct >= 50 else ""
        print(f"{nome:42s} {len(preenchidas):6d}/{len(finalizadas):<5d} {pct:4d}%   {exemplo!r}{marca}")

    # O que o retrain de fato usa, na ordem em que le.
    from backend.modeling.corners.retrain import _extract_total_corners
    com_total = sum(1 for p in finalizadas if _extract_total_corners(p) > 0)
    print(f"\n_extract_total_corners > 0 em {com_total}/{len(finalizadas)} finalizadas "
          f"({com_total * 100 // len(finalizadas)}%)")

    por_status = Counter(str(p.get("status", "?")) for p in partidas)
    print(f"status das {len(partidas)} partidas: {dict(por_status)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
