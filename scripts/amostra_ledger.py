# -*- coding: utf-8 -*-
"""#255 - reexportacao. A implementacao mora em
`backend/services/amostra_ledger.py` (deploy da Lambda so empacota
`backend/`; as rotas `/ledger/*` precisam destes filtros em runtime — ver a
docstring de la). Os tres consumidores de script (`comparar_com_mercado.py`,
`medir_inclinacao.py`, `grade_deflacao_por_familia.py`) continuam importando
DAQUI e recebem os MESMOS objetos
(`tests/test_252b_consumidores_do_ledger.py::test_filtro_existe_em_um_modulo_so`,
`tests/test_255_amostra_ledger_no_backend.py`).
"""
from backend.services.amostra_ledger import (  # noqa: F401
    JANELA_CONTAMINADA_251,
    Linhas,
    descrever,
    filtrar_amostra,
    fora_da_janela_contaminada,
    kickoff_da_linha,
    so_pre_jogo,
)
