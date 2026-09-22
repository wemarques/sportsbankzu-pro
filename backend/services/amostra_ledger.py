# -*- coding: utf-8 -*-
"""#255 - validade da amostra lida do `prediction_ledger` (movido de
`scripts/amostra_ledger.py`; a implementacao original e de #252/#252-a/#252-b).

Por que mora em `backend/services/` e nao em `scripts/`: o deploy da Lambda
so empacota `backend/` (`scripts/deploy_lambda.py:38`,
`.github/workflows/deploy-lambda.yml:97` — `cp -r backend lambda_build/backend`,
nada de `scripts/`). As rotas `/ledger/dia` e `/ledger/agregado` (#255,
`backend/services/ledger_leitura.py`) rodam DENTRO da Lambda em producao e
precisam destes filtros em runtime; um modulo em `scripts/` la dentro daria
`ModuleNotFoundError` na primeira chamada. `scripts/amostra_ledger.py`
continua existindo como reexportacao (mesmos objetos) para os tres
consumidores de script (`comparar_com_mercado.py`, `medir_inclinacao.py`,
`grade_deflacao_por_familia.py`) e para os testes #252b/#252c, que continuam
verdes sem alteracao.

- #252: so geracao publicada ANTES do apito e prognostico. `kickoff_utc` e
  nula no ledger, entao o kickoff sai do sufixo epoch do match_id; sem
  kickoff nenhum a linha SAI (falha fechada) e e contada.
- #252-a: `calibrated_prob` publicada em [inicio, fim) era a saida da camada
  #248, nao o modelo (#251). So essa coluna e cortada — qualquer outro campo
  (ex.: `published_prob`, usado por `ledger_leitura.py`) passa intacto, por
  desenho: ver Task 2 do plano #255 para o porque.

As linhas de entrada sao dicts com `match_id`, `published_at` e `kickoff_utc`.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

# #252-c: a resolucao do kickoff tem UMA implementacao, no proprio backend.
from backend.services.prediction_ledger import kickoff_da_linha  # noqa: F401

# Inicio = primeira versao (a,b) != (0,1) em calibragem_versoes; fim = Deploy
# Lambda de b2eec7d (#251). Mover so com nova medicao registrada.
JANELA_CONTAMINADA_251 = (
    datetime(2026, 9, 10, 23, 2, 6, tzinfo=timezone.utc),
    datetime(2026, 9, 14, 4, 50, 22, tzinfo=timezone.utc),
)

Linhas = Sequence[Dict[str, Any]]

logger = logging.getLogger("sportsbankzu.amostra_ledger")

# #260: janela maxima entre o kickoff da linha antiga e o da nova para
# considerar remarcacao. Acima disso, falso negativo deliberado (ver
# docstring de `remover_remarcados`).
_JANELA_REMARCACAO_DIAS = 14


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


def _base_e_epoch(match_id: Any) -> Tuple[Optional[str], Optional[float]]:
    """Base = tudo antes do sufixo epoch (`league_id-Casa-Fora-`); epoch = o
    sufixo, como numero. `None, None` quando o sufixo nao e um epoch (mesma
    guarda de `kickoff_da_linha`: `-todays-`, sufixo nao numerico, ou nao
    finito) — a linha nunca entra em `por_base` e portanto nunca e usada
    para remarcar, nem e candidata a remarcacao (proibicao 5: mesma
    convencao `rsplit("-", 1)` de `kickoff_da_linha`, nao reimplementada)."""
    s = str(match_id)
    if "-todays-" in s:
        return None, None
    partes = s.rsplit("-", 1)
    if len(partes) != 2:
        return None, None
    base, ts_str = partes
    try:
        ts = float(ts_str)
    except ValueError:
        return None, None
    if not math.isfinite(ts):
        return None, None
    return base, ts


def remover_remarcados(linhas: Linhas) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """#260 — jogo remarcado (FootyStats move o kickoff; o cron gera um
    match_id novo com epoch maior) deixa a linha do match_id ANTIGO
    pendente para sempre: o kickoff antigo nunca aconteceu, entao o cron de
    desfechos nunca a resolve. Mora aqui, ao lado de `filtrar_amostra` —
    mesmo padrao (par mantidas/descartadas sobre a mesma lista de dicts de
    linha, sem tocar o banco) — e nao em `ledger_leitura.py`, que so
    orquestra a consulta e a montagem do JSON de saida.

    Linha L sai quando existe outra linha M na mesma lista com:
      (a) a MESMA base de match_id (tudo antes do sufixo epoch);
      (b) epoch de M MAIOR que o de L (M e uma geracao mais nova);
      (c) kickoff de M no maximo `_JANELA_REMARCACAO_DIAS` dias DEPOIS do
          kickoff de L;
      (d) L SEM desfecho (`outcome` nulo).
    Com desfecho, L fica sempre — outcome preenchido significa que aquele
    kickoff aconteceu de verdade, entao e um jogo legitimo (ex.: ida/volta
    entre os mesmos times), nunca remarcacao.

    Bordas (spec #260): base sem epoch parseavel -> L nunca e remarcada, e
    nunca serve de M para remarcar outra linha (fica de fora de `por_base`);
    duas linhas com o MESMO epoch -> nao e remarcacao (mesma geracao, ex.:
    dois mercados do mesmo match_id); M fora da janela de
    `_JANELA_REMARCACAO_DIAS` -> L fica pendente (falso negativo deliberado,
    limitacao conhecida: uma remarcacao para mais de 14 dias no futuro nao e
    detectada — a regra prefere isso a arriscar fundir dois jogos
    genuinamente distintos).

    `kickoff_da_linha` (unica regra de kickoff, #252-c) resolve o kickoff de
    cada linha a partir de `kickoff_utc` ou do sufixo epoch — nao reimplementada
    aqui (proibicao 5)."""
    por_base: Dict[str, List[Dict[str, Any]]] = {}
    info: Dict[int, Tuple[Optional[str], Optional[float]]] = {}
    for ln in linhas:
        base, epoch = _base_e_epoch(ln.get("match_id"))
        info[id(ln)] = (base, epoch)
        if base is not None:
            por_base.setdefault(base, []).append(ln)

    mantidas: List[Dict[str, Any]] = []
    removidas: List[Dict[str, Any]] = []
    for ln in linhas:
        base, epoch = info[id(ln)]
        remarcada = False
        if base is not None and ln.get("outcome") is None:
            kickoff_l = kickoff_da_linha(ln.get("match_id"), ln.get("kickoff_utc"))
            if kickoff_l is not None:
                for outra in por_base[base]:
                    if outra is ln:
                        continue
                    _, epoch_m = info[id(outra)]
                    if epoch_m is None or epoch_m <= epoch:
                        continue
                    kickoff_m = kickoff_da_linha(outra.get("match_id"), outra.get("kickoff_utc"))
                    if kickoff_m is None:
                        continue
                    diff = kickoff_m - kickoff_l
                    if timedelta(0) < diff <= timedelta(days=_JANELA_REMARCACAO_DIAS):
                        remarcada = True
                        break
        (removidas if remarcada else mantidas).append(ln)
    return mantidas, removidas


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
