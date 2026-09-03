# -*- coding: utf-8 -*-
"""#225-c / #226 - reescreve a cadeia de fallback morta.

    X.get("a", Y.get("b", padrao))  ->  primeiro_valido(X.get("a"), Y.get("b"), padrao=padrao)

Substitui apenas o span exato de cada ocorrencia, entao comentarios e
formatacao do resto do arquivo ficam intactos.

CUIDADO QUE CUSTOU UM BUG (#226): `ast.get_source_segment` de
`(league_stats or {})` devolve `league_stats or {}` — **sem os parenteses**.
Emitir isso direto produz `league_stats or {}.get("x")`, que o Python le como
`league_stats or ({}.get("x"))`: se `league_stats` for verdadeiro, a expressao
inteira vira o proprio dicionario em vez do valor da chave. Receptor que nao
seja atomico e reparentetizado.

    python scripts/codemod_fallback.py arquivo.py [outro.py ...]
    python scripts/codemod_fallback.py --conferir arquivo.py   # so relata
"""
from __future__ import annotations

import argparse
import ast
import sys
from typing import Any, List, Optional, Tuple

# Receptores que ja sao atomicos: `d`, `d.x`, `d[0]`, `f()`, `"lit"`.
_ATOMICOS = (ast.Name, ast.Attribute, ast.Subscript, ast.Call, ast.Constant)


def _fonte_receptor(src: str, no: ast.AST) -> str:
    """Codigo do receptor, reparentetizado quando nao for atomico."""
    texto = ast.get_source_segment(src, no) or ""
    if isinstance(no, _ATOMICOS):
        return texto
    return f"({texto})"


def _cadeia(no: ast.Call) -> Tuple[List[Tuple[ast.AST, ast.AST]], Optional[ast.AST]]:
    """Desmonta a cadeia aninhada: ([(receptor, chave)], no_do_padrao)."""
    partes: List[Tuple[ast.AST, ast.AST]] = []
    atual: Any = no
    while (isinstance(atual, ast.Call) and isinstance(atual.func, ast.Attribute)
           and atual.func.attr == "get" and len(atual.args) == 2):
        partes.append((atual.func.value, atual.args[0]))
        atual = atual.args[1]
    if (isinstance(atual, ast.Call) and isinstance(atual.func, ast.Attribute)
            and atual.func.attr == "get" and len(atual.args) == 1):
        partes.append((atual.func.value, atual.args[0]))
        atual = None
    return partes, atual


def _alvos(arvore: ast.AST) -> List[ast.Call]:
    todos = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        and no.func.attr == "get" and len(no.args) == 2
        and isinstance(no.args[1], ast.Call)
        and isinstance(no.args[1].func, ast.Attribute)
        and no.args[1].func.attr == "get"
    ]
    spans = {(a.lineno, a.col_offset, a.end_lineno, a.end_col_offset) for a in todos}

    def aninhado(a: ast.Call) -> bool:
        meu = (a.lineno, a.col_offset, a.end_lineno, a.end_col_offset)
        for outro in spans:
            if outro == meu:
                continue
            if outro[:2] <= meu[:2] and meu[2:] <= outro[2:]:
                return True
        return False

    return [a for a in todos if not aninhado(a)]


def processar(caminho: str, conferir: bool = False) -> int:
    src = open(caminho, encoding="utf-8").read()
    externos = _alvos(ast.parse(src))

    linhas = src.splitlines(keepends=True)
    inicios = [0]
    for linha in linhas[:-1]:
        inicios.append(inicios[-1] + len(linha))

    edicoes = []
    for alvo in externos:
        partes, padrao = _cadeia(alvo)
        if len(partes) < 2:
            continue
        args = ", ".join(
            f"{_fonte_receptor(src, receptor)}.get({ast.get_source_segment(src, chave)})"
            for receptor, chave in partes
        )
        if padrao is not None and not (isinstance(padrao, ast.Constant) and padrao.value is None):
            args += f", padrao={ast.get_source_segment(src, padrao)}"
        edicoes.append((
            inicios[alvo.lineno - 1] + alvo.col_offset,
            inicios[alvo.end_lineno - 1] + alvo.end_col_offset,
            f"primeiro_valido({args})",
        ))

    if conferir:
        for _, _, novo in edicoes:
            print(f"  {novo}")
        return len(edicoes)

    for inicio, fim, novo in sorted(edicoes, reverse=True):
        src = src[:inicio] + novo + src[fim:]

    if edicoes and "from backend.utils.valores import primeiro_valido" not in src:
        linhas2 = src.splitlines(keepends=True)
        idx = 0
        for i, linha in enumerate(linhas2):
            if linha.startswith(("import ", "from ")):
                idx = i + 1
        linhas2.insert(idx, "from backend.utils.valores import primeiro_valido  # #225-c\n")
        src = "".join(linhas2)

    ast.parse(src)  # nao grava arquivo que nao compila
    open(caminho, "w", encoding="utf-8").write(src)
    return len(edicoes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivos", nargs="+")
    ap.add_argument("--conferir", action="store_true",
                    help="mostra o que seria escrito, sem gravar")
    args = ap.parse_args()
    for caminho in args.arquivos:
        n = processar(caminho, conferir=args.conferir)
        print(f"{caminho}: {n} ocorrencias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
