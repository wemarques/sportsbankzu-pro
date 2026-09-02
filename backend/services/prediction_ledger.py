"""Ledger imutavel de prognosticos (#218).

Por que existe
--------------
Os calibradores eram treinados a partir de `audit_results`, que e escrita com
`INSERT OR REPLACE` (audit_service.py:29). Cada reprocessamento pos-jogo
sobrescreve a linha, entao a tabela guarda o prognostico RECOMPUTADO depois do
resultado, nao o que foi publicado antes dele. Treinar calibrador nisso e
aprender com dados do futuro; foi o que o #200 fechou colocando o retreino
atras de um gate.

Este modulo e a fonte limpa que faltava. Duas regras, e so duas:

1. **So insere.** Nao existe UPDATE nem DELETE aqui. O desfecho do jogo entra
   em `ledger_outcomes`, uma segunda tabela, e as metricas saem de um JOIN.
   Uma linha do ledger, uma vez escrita, descreve para sempre o que o sistema
   sabia no momento em que publicou.
2. **Grava as ENTRADAS, nao so a saida.** Probabilidade sem os lambdas, sem o
   tamanho da amostra e sem a idade do dado registra o erro sem permitir
   explica-lo. Foi exatamente a lacuna que fez o #216 precisar de uma quarta
   coluna para descobrir que a isotonica estava inerte.

O que este modulo NAO faz
-------------------------
Nao decide nada. Nenhum caminho de publicacao le o ledger. Ele so observa, e
falha aberto: qualquer excecao vira log de debug e o pedido segue. Um site em
producao nao pode cair porque a telemetria caiu.

Desligado por padrao (`PREDICTION_LEDGER_ENABLED=0`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("sportsbankzu.ledger")

# Versao do conjunto de regras que produziu a linha. Sobe quando o calculo muda,
# para que o walk-forward do #221 nao misture geracoes do modelo.
LEDGER_MODEL_VERSION = os.getenv("LEDGER_MODEL_VERSION", "2026.09.02+217")

_MAX_LINHAS_POR_LOTE = 500


def ledger_habilitado() -> bool:
    return os.getenv("PREDICTION_LEDGER_ENABLED", "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ.get("DATABASE_URL", ""))


_DDL_LEDGER = """
CREATE TABLE IF NOT EXISTS prediction_ledger (
    id              BIGSERIAL PRIMARY KEY,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    match_id        TEXT NOT NULL,
    league_id       TEXT,
    kickoff_utc     TIMESTAMPTZ,
    market          TEXT NOT NULL,
    selection       TEXT,
    model_version   TEXT NOT NULL,
    raw_prob        DOUBLE PRECISION,
    iso_prob        DOUBLE PRECISION,
    calibrated_prob DOUBLE PRECISION,
    band_type       TEXT,
    book_odd        DOUBLE PRECISION,
    odd_source      TEXT,
    overround       DOUBLE PRECISION,
    ev              DOUBLE PRECISION,
    classification  TEXT,
    stake           DOUBLE PRECISION,
    reason_codes    JSONB,
    governance      JSONB,
    inputs          JSONB,
    payload_hash    TEXT NOT NULL
);
"""

# A unicidade e por CONTEUDO, nao por (jogo, mercado). Republicar o mesmo pick
# identico nao cria linha nova (o /fixtures e chamado dezenas de vezes por dia);
# republicar com qualquer numero diferente cria. Assim o ledger fica com o
# historico das REVISOES do prognostico sem virar log de acesso.
_DDL_INDICES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_ledger_conteudo "
    "ON prediction_ledger (match_id, market, payload_hash)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_liga_mercado "
    "ON prediction_ledger (league_id, market, published_at)",
]

_DDL_OUTCOMES = """
CREATE TABLE IF NOT EXISTS ledger_outcomes (
    id            BIGSERIAL PRIMARY KEY,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    match_id      TEXT NOT NULL,
    market        TEXT NOT NULL,
    outcome       INTEGER NOT NULL,
    detail        JSONB,
    UNIQUE (match_id, market)
);
"""


def garantir_tabelas() -> bool:
    """Cria as duas tabelas. Idempotente. Devolve False se nao deu (falha aberta)."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(_DDL_LEDGER)
        for ddl in _DDL_INDICES:
            cur.execute(ddl)
        cur.execute(_DDL_OUTCOMES)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] garantir_tabelas: %s", e)
        return False


def _hash(linha: Dict[str, Any]) -> str:
    """Hash do conteudo que define 'e o mesmo prognostico'.

    De proposito NAO inclui published_at: o carimbo de tempo mudaria a cada
    chamada e o ledger viraria um log de requisicoes.
    """
    campos = (
        "match_id", "league_id", "market", "selection", "model_version",
        "raw_prob", "iso_prob", "calibrated_prob", "band_type",
        "book_odd", "odd_source", "overround", "ev", "classification",
        "stake", "reason_codes", "governance", "inputs",
    )
    bruto = json.dumps(
        {k: linha.get(k) for k in campos}, sort_keys=True, default=str,
    )
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def montar_linha(
    *,
    match_id: str,
    league_id: Optional[str],
    market: str,
    selection: Optional[str] = None,
    kickoff_utc: Optional[datetime] = None,
    raw_prob: Optional[float] = None,
    iso_prob: Optional[float] = None,
    calibrated_prob: Optional[float] = None,
    band_type: Optional[str] = None,
    book_odd: Optional[float] = None,
    odd_source: Optional[str] = None,
    overround: Optional[float] = None,
    ev: Optional[float] = None,
    classification: Optional[str] = None,
    stake: Optional[float] = None,
    reason_codes: Optional[Iterable[str]] = None,
    governance: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    linha = {
        "match_id": str(match_id),
        "league_id": league_id,
        "kickoff_utc": kickoff_utc,
        "market": market,
        "selection": selection,
        "model_version": LEDGER_MODEL_VERSION,
        "raw_prob": raw_prob,
        "iso_prob": iso_prob,
        "calibrated_prob": calibrated_prob,
        "band_type": band_type,
        "book_odd": book_odd,
        "odd_source": odd_source,
        "overround": overround,
        "ev": ev,
        "classification": classification,
        "stake": stake,
        "reason_codes": sorted(str(c) for c in (reason_codes or [])),
        "governance": governance or {},
        "inputs": inputs or {},
    }
    linha["payload_hash"] = _hash(linha)
    return linha


_COLUNAS = (
    "match_id", "league_id", "kickoff_utc", "market", "selection",
    "model_version", "raw_prob", "iso_prob", "calibrated_prob", "band_type",
    "book_odd", "odd_source", "overround", "ev", "classification", "stake",
    "reason_codes", "governance", "inputs", "payload_hash",
)


def registrar(linhas: List[Dict[str, Any]]) -> int:
    """Anexa linhas ao ledger. Devolve quantas entraram de fato.

    Falha aberta em qualquer erro — o pedido do usuario nunca pode quebrar
    porque a telemetria quebrou.
    """
    if not linhas or not ledger_habilitado():
        return 0
    if len(linhas) > _MAX_LINHAS_POR_LOTE:
        logger.warning("[#218] lote de %d linhas truncado em %d",
                       len(linhas), _MAX_LINHAS_POR_LOTE)
        linhas = linhas[:_MAX_LINHAS_POR_LOTE]
    try:
        from psycopg2.extras import Json, execute_values

        valores = [
            tuple(
                Json(l.get(c)) if c in ("reason_codes", "governance", "inputs")
                else l.get(c)
                for c in _COLUNAS
            )
            for l in linhas
        ]
        conn = _conn()
        cur = conn.cursor()
        execute_values(
            cur,
            f"INSERT INTO prediction_ledger ({', '.join(_COLUNAS)}) VALUES %s "
            f"ON CONFLICT (match_id, market, payload_hash) DO NOTHING",
            valores,
        )
        gravadas = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        conn.commit()
        cur.close()
        conn.close()
        logger.info("[#218] ledger: %d de %d linha(s) novas", gravadas, len(linhas))
        return gravadas
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] registrar falhou (falha aberta): %s", e)
        return 0


def registrar_desfecho(match_id: str, market: str, outcome: int,
                       detail: Optional[Dict[str, Any]] = None) -> bool:
    """Anexa o desfecho real. Tabela separada, nunca toca o ledger."""
    if not ledger_habilitado():
        return False
    try:
        from psycopg2.extras import Json
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ledger_outcomes (match_id, market, outcome, detail) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (match_id, market) DO NOTHING",
            (str(match_id), market, int(outcome), Json(detail or {})),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.debug("[#218] registrar_desfecho falhou: %s", e)
        return False


def linhas_do_bundle(bundle, match_data: Optional[Dict[str, Any]] = None,
                     stats: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Traduz um MarketBundle ja classificado em linhas do ledger.

    As ENTRADAS que acompanham cada linha sao as que explicam o numero:
    os dois lambdas, o lambda de cartoes e o de escanteios, o tamanho da
    amostra de cada lado e a idade do dado. Sem elas o ledger registra o erro
    sem permitir diagnostica-lo.
    """
    stats = stats or {}
    match_data = match_data or {}
    # #223 - MEDIDO contra um record real: 6 destas 10 entradas vinham NULAS.
    # O ledger existe para "registrar o erro permitindo explica-lo", e estava
    # gravando `None` justamente nas entradas que explicam. As chaves lidas nao
    # existiam com aquele nome:
    #
    #   homeMatchesPlayed/awayMatchesPlayed -> matchesPlayed_home/_away
    #   leagueMatchesCompleted              -> vive em league_stats, nao em stats
    #   cardsLambda / expectedTotalCorners  -> nao existem em lugar nenhum;
    #                                          gravamos os componentes que existem
    #   dataAgeHours                        -> nao existe; lacuna real, ver abaixo
    #
    # Foi a terceira vez que o mesmo defeito passou — desta vez DENTRO do patch
    # escrito para corrigir essa classe de defeito. Por isso o contrato do #223
    # e um teste, nao um paragrafo.
    _ls = (match_data.get("league_stats") or {}) if isinstance(match_data, dict) else {}
    entradas_comuns = {
        "lambda_home": stats.get("lambdaHome"),
        "lambda_away": stats.get("lambdaAway"),
        "lambda_total": stats.get("lambdaTotal"),
        # Nao ha lambda de cartoes nem total esperado de escanteios no record;
        # o que existe sao os componentes de onde eles sairiam. Gravar os
        # componentes e verdadeiro; gravar um None chamado "cards_lambda" seria
        # registrar uma ausencia com nome de medida.
        "cards_home_pm": stats.get("homeCardsPerMatch"),
        "cards_away_pm": stats.get("awayCardsPerMatch"),
        "cards_league_avg": stats.get("leagueAvgCards"),
        "corners_home_pm": stats.get("homeCornersPerMatch"),
        "corners_away_pm": stats.get("awayCornersPerMatch"),
        "corners_league_avg": stats.get("leagueAvgCorners"),
        "home_matches": stats.get("matchesPlayed_home"),
        "away_matches": stats.get("matchesPlayed_away"),
        "league_matches_completed": _ls.get("matches_completed"),
        # LACUNA CONHECIDA: a idade do dado nao e registrada em lugar nenhum do
        # record. Fica fora do ledger ate existir de verdade — um campo sempre
        # nulo e pior que campo ausente, porque parece medicao.
        "chaos_detected": stats.get("chaosDetected"),
        "data_quality_score": getattr(bundle, "data_quality_score", None),
    }
    linhas: List[Dict[str, Any]] = []
    for m in getattr(bundle, "markets", []) or []:
        gov = {}
        if getattr(m, "corner_governance", None):
            gov["corner"] = m.corner_governance
        if getattr(m, "corner_veto", None):
            gov["veto"] = m.corner_veto
        linhas.append(montar_linha(
            match_id=getattr(bundle, "match_id", "") or match_data.get("id", ""),
            league_id=getattr(bundle, "league_id", None),
            market=getattr(m, "market_type", "") or "",
            selection=getattr(m, "selection", None),
            raw_prob=getattr(m, "raw_probability", None),
            iso_prob=getattr(m, "iso_probability", None),
            calibrated_prob=getattr(m, "calibrated_probability", None),
            band_type=getattr(m, "deflation_band_type", None),
            book_odd=getattr(m, "book_odd", None),
            ev=getattr(m, "ev", None),
            classification=getattr(getattr(m, "classification", None), "value", None),
            reason_codes=[getattr(rc, "value", str(rc)) for rc in (getattr(m, "reason_codes", []) or [])],
            governance=gov,
            inputs=entradas_comuns,
        ))
    return linhas
