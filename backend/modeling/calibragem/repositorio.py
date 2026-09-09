# -*- coding: utf-8 -*-
"""Unico modulo do pacote que toca o banco.

FONTE PROIBIDA: a tabela de auditoria recomputada pos-jogo (#200). A regra
#244 proibe usa-la como fonte de calibracao. Nao ha caminho de codigo para
ela aqui, e um teste guarda isso (inclusive contra o nome dela em comentario).
"""
import logging
import os
from typing import Any, Dict, List, NamedTuple, Optional

from backend.modeling.calibragem.curva import familia_do_mercado

logger = logging.getLogger("sportsbankzu.calibragem.repositorio")

DDL = """
CREATE TABLE IF NOT EXISTS calibragem_versoes (
    id                  BIGSERIAL PRIMARY KEY,
    criada_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    familia             TEXT NOT NULL,
    liga                TEXT NOT NULL DEFAULT '',
    versao              INTEGER NOT NULL,
    a                   DOUBLE PRECISION,
    b                   DOUBLE PRECISION,
    n_jogos             INTEGER NOT NULL DEFAULT 0,
    brier_validacao     DOUBLE PRECISION,
    origem              TEXT,
    status              TEXT NOT NULL,
    fator_encurtamento  DOUBLE PRECISION,
    motivo              TEXT,
    safe_ev             DOUBLE PRECISION,
    neutro_ev           DOUBLE PRECISION,
    safe_edge           DOUBLE PRECISION,
    neutro_edge         DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_calibragem_celula
    ON calibragem_versoes (familia, liga, versao DESC);
CREATE INDEX IF NOT EXISTS idx_calibragem_vigente
    ON calibragem_versoes (familia, liga) WHERE status = 'vigente';
"""


class Pick(NamedTuple):
    match_id: str
    familia: str
    liga: str
    p_raw: float
    y: int
    odd: Optional[float] = None


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ["DATABASE_URL"])


def garantir_tabela() -> bool:
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(DDL)
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] tabela nao garantida: %s", e)
        return False


def escolher_ultima_geracao(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Uma linha por (match_id, market, selection): a ultima ANTES do kickoff.

    O ledger e append-only com varias geracoes por jogo. A que vale e a que o
    operador viu por ultimo, e ela tem de ser anterior ao apito — geracao
    posterior ao kickoff nao e prognostico, e o defeito do #200.
    """
    melhor: Dict[tuple, Dict[str, Any]] = {}
    for ln in linhas:
        kickoff = ln.get("kickoff_utc")
        publicado = ln.get("published_at")
        if kickoff is not None and publicado is not None and publicado >= kickoff:
            continue
        chave = (ln.get("match_id"), ln.get("market"), ln.get("selection"))
        atual = melhor.get(chave)
        if atual is None or (publicado is not None
                             and atual.get("published_at") is not None
                             and publicado > atual["published_at"]):
            melhor[chave] = ln
    return list(melhor.values())


def carregar_amostra(desde: Optional[str] = None) -> List[Pick]:
    """Picks publicados PRE-JOGO com desfecho, prontos para o estimador."""
    sql = """
        SELECT l.match_id, l.league_id, l.market, l.selection,
               l.raw_prob, l.published_at, l.kickoff_utc, l.book_odd,
               o.outcome
          FROM prediction_ledger l
          JOIN ledger_outcomes o
            ON o.match_id  = l.match_id
           AND o.market    = l.market
           AND o.selection = l.selection
         WHERE l.raw_prob IS NOT NULL
           AND o.outcome IS NOT NULL
    """
    params: list = []
    if desde:
        sql += " AND l.published_at >= %s"
        params.append(desde)

    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        brutas = [
            {"match_id": r[0], "league_id": r[1] or "", "market": r[2],
             "selection": r[3], "raw_prob": float(r[4]), "published_at": r[5],
             "kickoff_utc": r[6],
             "book_odd": float(r[7]) if r[7] is not None else None,
             "outcome": r[8]}
            for r in cur.fetchall()
        ]

    saida: List[Pick] = []
    sem_familia = 0
    for ln in escolher_ultima_geracao(brutas):
        rotulo = f"{ln['market']} {ln['selection']}".strip()
        try:
            familia = familia_do_mercado(rotulo)
        except ValueError:
            sem_familia += 1
            continue
        saida.append(Pick(ln["match_id"], familia, ln["league_id"],
                          ln["raw_prob"], int(bool(int(ln["outcome"]))),
                          ln["book_odd"]))
    if sem_familia:
        logger.warning("[calibragem] %d picks sem familia reconhecida", sem_familia)
    return saida
