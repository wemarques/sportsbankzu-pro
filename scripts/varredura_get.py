# -*- coding: utf-8 -*-
"""#225-c - varredura de fallback morto: `.get(k, alternativa)` encadeado.

`d.get(k, alt)` so usa `alt` quando a chave esta AUSENTE. Quando ela existe
valendo `None` — a regra num pipeline onde o produtor monta o dicionario
inteiro — o `get` devolve `None` e a alternativa nunca e alcancada.

Esta varredura NAO le a intencao do codigo: monta os records de referencia
REAIS (os tres cenarios do contrato do #223), descobre quais chaves o produtor
cria em todos eles, e marca como CONFIRMADA toda cadeia cujo primeiro nome
esta nessa lista — nesses casos a alternativa e inalcancavel por construcao,
nao por probabilidade.

    python scripts/varredura_get.py            # resumo
    python scripts/varredura_get.py --detalhe  # arquivo:linha de cada confirmada
"""
from __future__ import annotations

import argparse
import ast
import logging
import pathlib
import sys
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

RAIZ = pathlib.Path("backend")


def _cadeias() -> Tuple[int, List[Tuple[str, int, str]], int]:
    """(total de gets com default, cadeias com nome literal, cadeias no total)."""
    total = 0
    encadeadas = 0
    literais: List[Tuple[str, int, str]] = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                    and no.func.attr == "get" and len(no.args) == 2):
                continue
            total += 1
            padrao = no.args[1]
            if not (isinstance(padrao, ast.Call) and isinstance(padrao.func, ast.Attribute)
                    and padrao.func.attr == "get"):
                continue
            encadeadas += 1
            chave = no.args[0]
            if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
                literais.append((str(arquivo), no.lineno, chave.value))
    return total, literais, encadeadas


def _chaves_do_record() -> Tuple[Set[str], Set[str]]:
    """(criadas em TODOS os cenarios, dessas as vistas valendo None)."""
    from backend.config import contrato_record

    cenarios: List[Tuple[Set[str], Dict[str, Any]]] = []
    for registro in contrato_record._cenarios():
        chaves = set(registro)
        chaves |= set(registro.get("stats") or {})
        chaves |= set(registro.get("league_stats") or {})
        cenarios.append((chaves, registro))

    sempre = set.intersection(*[c for c, _ in cenarios]) if cenarios else set()

    def valor(registro: Dict[str, Any], chave: str) -> Any:
        for portador in (registro, registro.get("stats") or {},
                         registro.get("league_stats") or {}):
            if chave in portador:
                return portador[chave]
        return "AUSENTE"

    nulas = {c for c in sempre if any(valor(r, c) is None for _, r in cenarios)}
    return sempre, nulas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    logging.disable(logging.CRITICAL)
    total, literais, encadeadas = _cadeias()
    sempre, nulas = _chaves_do_record()
    logging.disable(logging.NOTSET)

    confirmadas = [(f, l, c) for f, l, c in literais if c in sempre]

    print(f".get(chave, default) em backend/ .................. {total}")
    print(f"  encadeados (default e outro .get) ............... {encadeadas}")
    print(f"  desses, com primeiro nome literal ............... {len(literais)}")
    print(f"chaves criadas em TODOS os cenarios do record ..... {len(sempre)}")
    print(f"  dessas, vistas valendo None ..................... {len(nulas)}")
    print(f"CONFIRMADAS (alternativa inalcancavel) ............ {len(confirmadas)}")
    print(f"  com o nome ja visto None ........................ "
          f"{len([1 for _, _, c in confirmadas if c in nulas])}")

    por_arquivo: Dict[str, List[str]] = {}
    for arquivo, linha, chave in confirmadas:
        por_arquivo.setdefault(arquivo, []).append(f"{chave}:{linha}")
    for arquivo in sorted(por_arquivo):
        itens = por_arquivo[arquivo]
        print(f"  {len(itens):3d}  {arquivo}")
        if args.detalhe:
            for item in itens:
                print(f"         {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
