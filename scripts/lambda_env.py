# -*- coding: utf-8 -*-
"""#228 - altera UMA variavel de ambiente da Lambda sem apagar as outras.

`aws lambda update-function-configuration --environment Variables={K=V}`
SUBSTITUI o bloco inteiro: sobe uma variavel e apaga MISTRAL_API_KEY,
DATABASE_URL e todas as outras. Este script le, mescla, grava — e mostra o
diff antes de gravar, com valores mascarados.

    python scripts/lambda_env.py --show
    python scripts/lambda_env.py --set PREDICTION_LEDGER_ENABLED=1
    python scripts/lambda_env.py --unset PREDICTION_LEDGER_ENABLED
    python scripts/lambda_env.py --set A=1 --set B=2 --dry-run

Usa o `aws` CLI ja configurado na maquina (mesmo caminho do deploy_lambda.py).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional

FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "sportsbank-pro-backend")
REGION = os.getenv("AWS_REGION", "us-east-1")
_SENSIVEL = ("KEY", "SECRET", "PASSWORD", "TOKEN", "URL", "DSN")


def _aws(*args: str) -> str:
    r = subprocess.run(["aws", *args, "--region", REGION, "--output", "json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"aws falhou ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _mascarar(chave: str, valor: str) -> str:
    if any(t in chave.upper() for t in _SENSIVEL) and len(valor) > 6:
        return valor[:3] + "…" + valor[-2:] + f" ({len(valor)} chars)"
    return valor


def ler() -> Dict[str, str]:
    cfg = json.loads(_aws("lambda", "get-function-configuration",
                          "--function-name", FUNCTION_NAME))
    return dict((cfg.get("Environment") or {}).get("Variables") or {})


def estado() -> Dict[str, str]:
    cfg = json.loads(_aws("lambda", "get-function-configuration",
                          "--function-name", FUNCTION_NAME))
    return {"State": cfg.get("State"), "LastUpdateStatus": cfg.get("LastUpdateStatus")}


def esperar_ativa(tentativas: int = 20) -> bool:
    for _ in range(tentativas):
        e = estado()
        if e["State"] == "Active" and e["LastUpdateStatus"] == "Successful":
            return True
        print(f"  aguardando: {e}")
        time.sleep(3)
    return False


def mesclar(atual: Dict[str, str], sets: List[str], unsets: List[str]) -> Dict[str, str]:
    novo = dict(atual)
    for item in sets:
        if "=" not in item:
            raise SystemExit(f"--set espera K=V, recebeu {item!r}")
        k, v = item.split("=", 1)
        novo[k.strip()] = v
    for k in unsets:
        novo.pop(k.strip(), None)
    return novo


def gravar(variaveis: Dict[str, str]) -> None:
    # file:// evita o parser de Variables={...}, que quebra com virgula e igual
    # dentro de valor (DATABASE_URL tem os dois).
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump({"Variables": variaveis}, f)
        caminho = f.name
    try:
        _aws("lambda", "update-function-configuration",
             "--function-name", FUNCTION_NAME,
             "--environment", f"file://{caminho}")
    finally:
        os.unlink(caminho)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="K=V")
    ap.add_argument("--unset", action="append", default=[], metavar="K")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    atual = ler()
    if args.show or not (args.set or args.unset):
        print(f"{FUNCTION_NAME} ({REGION}): {len(atual)} variavel(is)")
        for k in sorted(atual):
            print(f"  {k} = {_mascarar(k, atual[k])}")
        return 0

    novo = mesclar(atual, args.set, args.unset)
    mudou = False
    for k in sorted(set(atual) | set(novo)):
        a, n = atual.get(k), novo.get(k)
        if a == n:
            continue
        mudou = True
        if a is None:
            print(f"  + {k} = {_mascarar(k, n)}")
        elif n is None:
            print(f"  - {k}  (era {_mascarar(k, a)})")
        else:
            print(f"  ~ {k}: {_mascarar(k, a)} -> {_mascarar(k, n)}")
    intactas = len(set(atual) & set(novo)) - sum(1 for k in atual if k in novo and atual[k] != novo[k])
    print(f"  = {intactas} variavel(is) preservada(s)")
    if not mudou:
        print("nada a alterar")
        return 0
    if args.dry_run:
        print("dry-run: nada gravado")
        return 0

    if not esperar_ativa():
        raise SystemExit("Lambda nao esta Active/Successful — nao gravo por cima de update em andamento")
    gravar(novo)
    print("gravado. aguardando a Lambda ficar Active...")
    print("ok" if esperar_ativa() else "timeout aguardando — confira com --show")
    return 0


if __name__ == "__main__":
    sys.exit(main())
