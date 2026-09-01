#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#210 - confronta o manifesto da FootyStats com o codigo.

    python scripts/verificar_manifesto.py           # relatorio
    python scripts/verificar_manifesto.py --fila    # so a divida de dados

Sai com codigo 1 quando algo bloqueia: campo mapeado sem declaracao, ou campo
declarado CONSUMIDO que perdeu o consumidor. Serve como passo de CI.
"""
import argparse
import sys

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from backend.config.footystats_manifest import (  # noqa: E402
    verificar, resumo, fila_de_trabalho, CAMPOS, PLANEJADO,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fila", action="store_true", help="lista os campos PLANEJADO")
    a = ap.parse_args()

    r = resumo()
    print(f"Manifesto FootyStats: {r['TOTAL']} campos "
          f"({r['CONSUMIDO']} consumidos, {r['PLANEJADO']} planejados, {r['DESCARTADO']} descartados)")

    if a.fila:
        print(f"\nFila de trabalho — {len(fila_de_trabalho())} campos mapeados sem consumidor:\n")
        for campo, motivo in fila_de_trabalho():
            print(f"  {campo:<38} {motivo}")
        return 0

    v = verificar()
    for linha in v["bloqueia"]:
        print(f"  BLOQUEIA  {linha}")
    for linha in v["avisa"]:
        print(f"  aviso     {linha}")

    if not v["bloqueia"] and not v["avisa"]:
        print("  manifesto e codigo estao de acordo.")
    if v["bloqueia"]:
        print(f"\n{len(v['bloqueia'])} pendencia(s) bloqueante(s).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
