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


def _numero(valor: Any):
    """Float quando der, `None` quando nao — sem transformar texto em 0."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _soma(a, b):
    return None if a is None or b is None else a + b


def _util(valor: Any) -> bool:
    """`0` conta — zero escanteio e um resultado. `None` e `-1` nao contam."""
    return valor is not None and valor != -1 and valor != ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", default="championship")
    ap.add_argument("--temporadas", type=int, default=2)
    ap.add_argument("--contem", default="corner",
                    help="#230-g: substring do nome da chave a varrer (padrao "
                         "'corner'; use 'odds_' para ver toda odd que a "
                         "FootyStats manda, e saber quais unders existem)")
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
    nomes = sorted({c for p in finalizadas for c in p if args.contem.lower() in c.lower()})
    if not nomes:
        print(f"nenhuma chave com '{args.contem}' no nome")
        return 1

    # #226-b: "preenchida" e "nao-zero" sao perguntas diferentes. Numa CONTAGEM,
    # 0 e resultado legitimo. Num campo de POTENCIAL/projecao, 0 quase sempre e
    # enchimento — e `corners_potential` alimenta `footystats_corners_potential`,
    # que o #123 chama de "ancora de projecao independente". Ancora de zero nao
    # ancora nada, e as duas colunas juntas denunciam isso sem precisar supor.
    print(f"\n{'chave':42s} {'preenchida':>12s} {'%':>5s} {'nao-zero':>10s} {'%':>5s}   exemplo")
    print("-" * 100)
    n = len(finalizadas)
    for nome in nomes:
        preenchidas = [p[nome] for p in finalizadas if _util(p.get(nome))]
        nao_zero = [v for v in preenchidas if _numero(v) not in (None, 0.0)]
        exemplo = next((v for v in nao_zero), preenchidas[0] if preenchidas else "-")
        marca = "  <<<" if len(nao_zero) * 100 // n >= 50 else ""
        if preenchidas and not nao_zero:
            marca = "   TODOS ZERO"
        print(f"{nome:42s} {len(preenchidas):6d}/{n:<5d} {len(preenchidas) * 100 // n:4d}% "
              f"{len(nao_zero):6d}/{n:<5d} {len(nao_zero) * 100 // n:4d}%   {exemplo!r}{marca}")

    # O que o retrain de fato usa, na ordem em que le.
    from backend.modeling.corners.retrain import _extract_total_corners
    com_total = sum(1 for p in finalizadas if _extract_total_corners(p) > 0)
    print(f"\n_extract_total_corners > 0 em {com_total}/{n} finalizadas "
          f"({com_total * 100 // n}%)")

    # #226-b: `_extract_total_corners` procura `totalCorners` e `total_corners`,
    # que NAO existem — chega no numero certo pela soma dos times, por sorte do
    # terceiro candidato. Antes de promover `totalCornerCount` a primeiro nome,
    # medir se ele concorda com a soma. Discordancia = os dois medem coisas
    # diferentes (prorrogacao? escanteios nao atribuidos?) e a troca nao e neutra.
    pares = [(_numero(p.get("totalCornerCount")),
              _soma(_numero(p.get("team_a_corners")), _numero(p.get("team_b_corners"))))
             for p in finalizadas]
    pares = [(t, s) for t, s in pares if t is not None and s is not None]
    if pares:
        divergem = [(t, s) for t, s in pares if t != s]
        print(f"totalCornerCount vs (team_a + team_b): concordam em "
              f"{len(pares) - len(divergem)}/{len(pares)}"
              + (f" | divergem em {len(divergem)}, ex: {divergem[:3]}" if divergem else ""))
    else:
        print("totalCornerCount vs soma: sem par comparavel")

    por_status = Counter(str(p.get("status", "?")) for p in partidas)
    print(f"status das {len(partidas)} partidas: {dict(por_status)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
