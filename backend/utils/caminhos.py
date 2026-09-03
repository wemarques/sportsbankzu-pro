# -*- coding: utf-8 -*-
"""#226 - onde o processo pode ESCREVER.

`Path(os.getenv("DATA_ROOT", "."))` funciona no notebook e falha na Lambda: o
diretorio do pacote (`/var/task`) e **somente leitura**, entao o primeiro
`mkdir` do retrain levanta `OSError: Read-only file system`. O projeto ja
resolve isso para o cache SQLite (`footstats_client` usa `/tmp/api_cache.db`
quando `AWS_LAMBDA_FUNCTION_NAME` esta setado); aqui e a mesma regra, num lugar
so.

Precedencia: `DATA_ROOT` explicito > `/tmp` na Lambda > diretorio corrente.
"""
from __future__ import annotations

import os
from pathlib import Path


def raiz_de_dados() -> Path:
    """Raiz gravavel para artefatos e modelos treinados."""
    definido = os.getenv("DATA_ROOT")
    if definido:
        return Path(definido)
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp")
    return Path(".")
