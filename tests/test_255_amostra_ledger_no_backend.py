# -*- coding: utf-8 -*-
"""#255 — os filtros do ledger tem de estar DENTRO de backend/, porque o
deploy da Lambda so empacota backend/ (`scripts/deploy_lambda.py:38`,
`.github/workflows/deploy-lambda.yml:97`) e as rotas `/ledger/*` (#255,
`backend/services/ledger_leitura.py`) os usam em runtime. Antes desta tarefa
a implementacao morava em `scripts/amostra_ledger.py`, invisivel para a
Lambda.
"""
import importlib
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]


def test_implementacao_mora_em_backend_services():
    from backend.services.amostra_ledger import (
        JANELA_CONTAMINADA_251, descrever, filtrar_amostra,
        fora_da_janela_contaminada, kickoff_da_linha, so_pre_jogo,
    )
    assert callable(filtrar_amostra) and callable(so_pre_jogo)
    assert callable(fora_da_janela_contaminada) and callable(descrever)
    assert callable(kickoff_da_linha)
    assert JANELA_CONTAMINADA_251[0].year == 2026


def test_scripts_amostra_ledger_e_um_shim():
    """`scripts/amostra_ledger.py` so reexporta. Sem isso, dois lugares
    implementariam o mesmo filtro (proibicao 5) e um deles ficaria fora do
    pacote que a Lambda empacota — o proprio defeito que esta tarefa fecha."""
    src = (_RAIZ / "scripts" / "amostra_ledger.py").read_text(encoding="utf-8")
    assert "def so_pre_jogo" not in src
    assert "def fora_da_janela_contaminada" not in src
    assert "def filtrar_amostra" not in src
    assert "from backend.services.amostra_ledger import" in src


def test_mesmos_objetos_dos_dois_caminhos():
    sys.path.insert(0, str(_RAIZ))
    from backend.services import amostra_ledger as B
    A = importlib.import_module("scripts.amostra_ledger")
    assert A.so_pre_jogo is B.so_pre_jogo
    assert A.fora_da_janela_contaminada is B.fora_da_janela_contaminada
    assert A.filtrar_amostra is B.filtrar_amostra
    assert A.descrever is B.descrever
    assert A.kickoff_da_linha is B.kickoff_da_linha
    assert A.JANELA_CONTAMINADA_251 == B.JANELA_CONTAMINADA_251
