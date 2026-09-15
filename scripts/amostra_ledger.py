# -*- coding: utf-8 -*-
"""#252 / #252-a / #252-b - validade da amostra lida do `prediction_ledger`.

Um modulo so para os tres consumidores (`comparar_com_mercado`,
`medir_inclinacao`, `grade_deflacao_por_familia`): reimplementar o filtro em
cada script e como ele diverge em silencio (proibicao 5).

- #252: so geracao publicada ANTES do apito e prognostico. `kickoff_utc` e
  nula no ledger, entao o kickoff sai do sufixo epoch do match_id; sem
  kickoff nenhum a linha SAI (falha fechada) e e contada.
- #252-a: `calibrated_prob` publicada em [inicio, fim) era a saida da camada
  #248, nao o modelo (#251). So essa coluna e cortada.

As linhas de entrada sao dicts com `match_id`, `published_at` e `kickoff_utc`.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

# Inicio = primeira versao (a,b) != (0,1) em calibragem_versoes; fim = Deploy
# Lambda de b2eec7d (#251). Mover so com nova medicao registrada.
JANELA_CONTAMINADA_251 = (
    datetime(2026, 9, 10, 23, 2, 6, tzinfo=timezone.utc),
    datetime(2026, 9, 14, 4, 50, 22, tzinfo=timezone.utc),
)

Linhas = Sequence[Dict[str, Any]]

# #252-c: a resolucao do kickoff tem UMA implementacao, no backend.
from backend.services.prediction_ledger import kickoff_da_linha  # noqa: E402,F401


def so_pre_jogo(linhas: Linhas) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Mantem `published_at < kickoff`; no apito tambem sai. Conta picks e
    jogos que SUMIRAM (nenhuma geracao deles sobreviveu)."""
    mantidas: List[Dict[str, Any]] = []
    pos, sem = [], []
    for ln in linhas:
        kickoff = kickoff_da_linha(ln.get("match_id"), ln.get("kickoff_utc"))
        if kickoff is None:
            sem.append(ln)
        elif ln.get("published_at") is None or ln["published_at"] >= kickoff:
            pos.append(ln)
        else:
            mantidas.append(ln)
    ficaram = {ln.get("match_id") for ln in mantidas}
    return mantidas, {
        "pos_kickoff": len(pos),
        "sem_kickoff": len(sem),
        "jogos_pos_kickoff": len({ln.get("match_id") for ln in pos} - ficaram),
        "jogos_sem_kickoff": len({ln.get("match_id") for ln in sem} - ficaram),
    }


def fora_da_janela_contaminada(linhas: Linhas, campo: str
                               ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Tira da serie `calibrated_prob` o publicado em [inicio, fim). As outras
    colunas nao passaram pela camada e ficam inteiras."""
    if campo != "calibrated_prob":
        return list(linhas), {"contaminados": 0, "jogos_contaminados": 0}
    ini, fim = JANELA_CONTAMINADA_251
    mantidas, fora = [], []
    for ln in linhas:
        pub = ln.get("published_at")
        (fora if pub is not None and ini <= pub < fim else mantidas).append(ln)
    ficaram = {ln.get("match_id") for ln in mantidas}
    return mantidas, {
        "contaminados": len(fora),
        "jogos_contaminados": len({ln.get("match_id") for ln in fora} - ficaram),
    }


def filtrar_amostra(linhas: Linhas, campo: str
                    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """#252 e depois #252-a, na ordem do gate. Devolve as duas contagens juntas."""
    mantidas, c1 = so_pre_jogo(linhas)
    mantidas, c2 = fora_da_janela_contaminada(mantidas, campo)
    return mantidas, {**c1, **c2}


def descrever(c: Dict[str, int]) -> str:
    """As duas linhas de relatorio. Filtro silencioso nao conta (#252, item 3)."""
    return (
        f"#252 so pre-kickoff: fora {c.get('pos_kickoff', 0)} picks publicados no/apos o apito "
        f"({c.get('jogos_pos_kickoff', 0)} jogos sumiram) e {c.get('sem_kickoff', 0)} sem kickoff "
        f"conhecido ({c.get('jogos_sem_kickoff', 0)} jogos sumiram)\n"
        f"#252-a janela contaminada da camada (#251): fora {c.get('contaminados', 0)} picks "
        f"pre-apito publicados entre 2026-09-10 23:02:06 e 2026-09-14 04:50:22 UTC "
        f"({c.get('jogos_contaminados', 0)} jogos sumiram)"
    )
