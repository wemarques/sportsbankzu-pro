# backend/ai/audit_log.py
"""
AI Audit Log — infraestrutura de medição da camada de IA (#188, Fase 1).

Grava um registro estruturado por jogo auditado (inputs, saída do modelo,
validade do JSON, latência, modelo/estágio) e reserva o campo actual_result
para preenchimento pós-jogo. Base de dados para o backtesting/calibração da
Fase 4 (comparação Mistral vs. cascata Qwen).

Storage:
- Primário: PostgreSQL via DATABASE_URL (mesmo padrão do brier_service #102).
- Fallback: SQLite local (backend/ai_audit_log.db; /tmp em Lambda — padrão do
  ai/cache_manager). Garante logs verificáveis em dev sem Postgres.

Contrato: NENHUMA função deste módulo levanta exceção para o chamador — a
instrumentação nunca pode derrubar o fluxo de produção (log-and-degrade).
psycopg2 é importado lazy (precedente #182: import top-level de dependência
da Layer quebrou /metrics/brier em produção).
"""
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sportsbankzu.ai.audit_log")

# THREAD-SAFETY (#188): conexões psycopg2 NÃO são thread-safe (threadsafety
# nível 2 — módulo sim, conexão não). No Lambda isso é inócuo (1 request por
# container), mas FORA dele (uvicorn local com threadpool, scripts, testes)
# a conexão module-level reutilizada poderia ser compartilhada entre threads.
# Todo acesso PG é serializado por este RLock (reentrante: _get_pg_conn e
# _reset_pg_conn também o adquirem quando chamados de dentro de regiões já
# travadas). O caminho SQLite abre conexão própria por chamada — não precisa.
_PG_LOCK = threading.RLock()

SCHEMA_VERSION = 1

# Estágios conhecidos (Fase 3 adiciona qwen_flash/qwen_plus/qwen_max + shadow)
STAGE_PRODUCTION = "production"          # saída consumida pela UI
STAGE_FALLBACK = "fallback_static"       # exceção → resposta estática
STAGE_ROUTE_FALLBACK = "route_fallback"  # falha antes do serviço (rota)


def _sqlite_path() -> str:
    if os.getenv("AI_AUDIT_SQLITE_PATH"):
        return os.environ["AI_AUDIT_SQLITE_PATH"]
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/ai_audit_log.db"
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai_audit_log.db")


def _use_postgres() -> bool:
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        import psycopg2  # noqa: F401 — lazy (#182)
        return True
    except Exception:
        return False


# =====================================================================
# VALIDADOR DE SCHEMA DA SAÍDA DO MODELO
# =====================================================================

# Mapeamento canônico → chave real no payload atual (Mistral v3.0).
# A Fase 3 (Qwen) passa um field_map próprio se o schema divergir.
# Nota: "auditOdds" não existe no payload do backend hoje — o frontend deriva
# esse valor de `confidence` (AIReviewDashboard). O validador o cobre de forma
# condicional: quando presente, deve ser numérico.
DEFAULT_FIELD_MAP = {
    "confidence": "confidence",
    "explanation": "resumo_analitico",
    "audit_odds": "auditOdds",
}


def validate_ai_output(
    output: Dict[str, Any],
    field_map: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str]]:
    """Valida o contrato mínimo da saída do modelo (#188, Fase 1).

    Regras:
    - confidence: numérico (int/float, não bool) em [0, 100] — obrigatório
    - explanation: string não vazia — obrigatório
    - audit_odds: numérico QUANDO presente (ausência não é erro)

    Returns (is_valid, errors). Nunca levanta exceção.
    """
    fm = {**DEFAULT_FIELD_MAP, **(field_map or {})}
    errors: List[str] = []

    if not isinstance(output, dict):
        return False, [f"output is not an object (got {type(output).__name__})"]

    conf = output.get(fm["confidence"])
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        errors.append(f"confidence not numeric (got {type(conf).__name__}: {conf!r})")
    elif not (0 <= float(conf) <= 100):
        errors.append(f"confidence out of range 0-100 (got {conf})")

    expl = output.get(fm["explanation"])
    if not isinstance(expl, str) or not expl.strip():
        errors.append(
            f"explanation ({fm['explanation']}) missing or empty "
            f"(got {type(expl).__name__})"
        )

    audit_odds = output.get(fm["audit_odds"])
    if audit_odds is not None and (
        isinstance(audit_odds, bool) or not isinstance(audit_odds, (int, float))
    ):
        errors.append(
            f"auditOdds present but not numeric (got {type(audit_odds).__name__}: {audit_odds!r})"
        )

    return (len(errors) == 0), errors


# =====================================================================
# STORAGE
# =====================================================================

_PG_COLUMNS = """
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    match_id TEXT,
    league_id TEXT,
    home_team TEXT,
    away_team TEXT,
    provider TEXT NOT NULL,
    model TEXT,
    stage TEXT NOT NULL,
    prompt_version TEXT,
    prompt_sha256 TEXT,
    prompt_chars INTEGER,
    inputs JSONB,
    output JSONB,
    confidence DOUBLE PRECISION,
    valid_json BOOLEAN NOT NULL,
    validation_errors JSONB,
    latency_ms INTEGER,
    error TEXT,
    from_cache BOOLEAN DEFAULT FALSE,
    actual_result JSONB,
    result_filled_at TIMESTAMPTZ,
    schema_version INTEGER NOT NULL
"""

_SQLITE_COLUMNS = """
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    match_id TEXT,
    league_id TEXT,
    home_team TEXT,
    away_team TEXT,
    provider TEXT NOT NULL,
    model TEXT,
    stage TEXT NOT NULL,
    prompt_version TEXT,
    prompt_sha256 TEXT,
    prompt_chars INTEGER,
    inputs TEXT,
    output TEXT,
    confidence REAL,
    valid_json INTEGER NOT NULL,
    validation_errors TEXT,
    latency_ms INTEGER,
    error TEXT,
    from_cache INTEGER DEFAULT 0,
    actual_result TEXT,
    result_filled_at TEXT,
    schema_version INTEGER NOT NULL
"""

_INSERT_FIELDS = [
    "match_id", "league_id", "home_team", "away_team", "provider", "model",
    "stage", "prompt_version", "prompt_sha256", "prompt_chars", "inputs",
    "output", "confidence", "valid_json", "validation_errors", "latency_ms",
    "error", "from_cache", "schema_version",
]


# Conexão PG reutilizada entre invocações warm do Lambda (container-level).
# psycopg2 não é thread-safe por conexão, mas o uso aqui é single-threaded:
# Lambda = 1 request por container; local, os writes rodam no event loop.
_pg_conn = None
_pg_table_ready = False
_sqlite_table_ready_path: Optional[str] = None


def _get_pg_conn():
    """Retorna conexão PG do container, reconectando se caiu/fechou.

    Sempre chamar com _PG_LOCK adquirido (ou deixar que este método adquira —
    RLock é reentrante).
    """
    global _pg_conn
    with _PG_LOCK:
        if _pg_conn is not None:
            try:
                if _pg_conn.closed:
                    _pg_conn = None
            except Exception:
                _pg_conn = None
        if _pg_conn is None:
            import psycopg2
            _pg_conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""))
        return _pg_conn


def _reset_pg_conn() -> None:
    global _pg_conn, _pg_table_ready
    with _PG_LOCK:
        try:
            if _pg_conn is not None:
                _pg_conn.close()
        except Exception:
            pass
        _pg_conn = None
        _pg_table_ready = False


def _ensure_pg_table(conn) -> None:
    """DDL idempotente, executado UMA vez por processo (não por insert)."""
    global _pg_table_ready
    if _pg_table_ready:
        return
    cur = conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS ai_audit_log ({_PG_COLUMNS})")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_match ON ai_audit_log (match_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_created ON ai_audit_log (created_at)"
    )
    conn.commit()
    _pg_table_ready = True


def _ensure_sqlite_table(conn) -> None:
    global _sqlite_table_ready_path
    path = _sqlite_path()
    if _sqlite_table_ready_path == path:
        return
    conn.execute(f"CREATE TABLE IF NOT EXISTS ai_audit_log ({_SQLITE_COLUMNS})")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_match ON ai_audit_log (match_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_audit_created ON ai_audit_log (created_at)"
    )
    conn.commit()
    _sqlite_table_ready_path = path


def log_ai_audit(
    *,
    provider: str,
    stage: str,
    match_id: Optional[str] = None,
    league_id: Optional[str] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    prompt_sha256: Optional[str] = None,
    prompt_chars: Optional[int] = None,
    inputs: Optional[Dict[str, Any]] = None,
    output: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    valid_json: bool = False,
    validation_errors: Optional[List[str]] = None,
    latency_ms: Optional[int] = None,
    error: Optional[str] = None,
    from_cache: bool = False,
) -> bool:
    """Grava um registro de auditoria de IA. Retorna False em falha (nunca levanta)."""
    record = {
        "match_id": match_id,
        "league_id": league_id,
        "home_team": home_team,
        "away_team": away_team,
        "provider": provider,
        "model": model,
        "stage": stage,
        "prompt_version": prompt_version,
        "prompt_sha256": prompt_sha256,
        "prompt_chars": prompt_chars,
        "inputs": inputs,
        "output": output,
        "confidence": confidence,
        "valid_json": valid_json,
        "validation_errors": validation_errors or [],
        "latency_ms": latency_ms,
        "error": error,
        "from_cache": from_cache,
        "schema_version": SCHEMA_VERSION,
    }
    try:
        if _use_postgres():
            return _insert_pg(record)
        return _insert_sqlite(record)
    except Exception as e:  # pragma: no cover — cinto de segurança final
        logger.warning(f"[ai-audit] log dropped ({provider}/{stage}): {e}")
        return False


def _insert_pg(record: Dict[str, Any]) -> bool:
    with _PG_LOCK:  # psycopg2: conexão não é thread-safe (#188)
        try:
            conn = _get_pg_conn()
        except Exception as e:
            logger.warning(f"[ai-audit] Postgres indisponível, usando SQLite: {e}")
            return _insert_sqlite(record)

        from psycopg2.extras import Json

        values = []
        for f in _INSERT_FIELDS:
            v = record[f]
            if f in ("inputs", "output", "validation_errors"):
                v = Json(v) if v is not None else None
            values.append(v)
        sql = (
            f"INSERT INTO ai_audit_log ({', '.join(_INSERT_FIELDS)}) "
            f"VALUES ({', '.join(['%s'] * len(_INSERT_FIELDS))})"
        )

        # 1 retry com reconexão: conexão warm pode ter sido dropada pelo RDS
        for attempt in (1, 2):
            try:
                _ensure_pg_table(conn)
                cur = conn.cursor()
                cur.execute(sql, values)
                conn.commit()
                return True
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if attempt == 1:
                    logger.info(f"[ai-audit] PG insert falhou (tentativa 1), reconectando: {e}")
                    _reset_pg_conn()
                    try:
                        conn = _get_pg_conn()
                    except Exception as e2:
                        logger.warning(f"[ai-audit] PG reconexão falhou, usando SQLite: {e2}")
                        return _insert_sqlite(record)
                else:
                    logger.warning(f"[ai-audit] PG insert falhou: {e}")
                    return False
        return False


def _insert_sqlite(record: Dict[str, Any]) -> bool:
    try:
        conn = sqlite3.connect(_sqlite_path())
        _ensure_sqlite_table(conn)
        values = []
        for f in _INSERT_FIELDS:
            v = record[f]
            if f in ("inputs", "output", "validation_errors"):
                v = json.dumps(v, ensure_ascii=False, default=str) if v is not None else None
            elif f in ("valid_json", "from_cache"):
                v = 1 if v else 0
            values.append(v)
        conn.execute(
            f"INSERT INTO ai_audit_log (created_at, {', '.join(_INSERT_FIELDS)}) "
            f"VALUES (?, {', '.join(['?'] * len(_INSERT_FIELDS))})",
            [datetime.now(timezone.utc).isoformat()] + values,
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"[ai-audit] SQLite insert falhou: {e}")
        return False


# =====================================================================
# ACTUAL RESULT (preenchido pós-jogo) + MÉTRICAS
# =====================================================================

def fill_actual_result(match_id: str, actual_result: Dict[str, Any]) -> int:
    """Preenche actual_result em TODOS os registros do jogo ainda sem resultado.

    Retorna o nº de linhas atualizadas (0 em falha — nunca levanta).
    Idempotente: só toca linhas com actual_result IS NULL.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        if _use_postgres():
            with _PG_LOCK:
                from psycopg2.extras import Json
                conn = _get_pg_conn()
                try:
                    _ensure_pg_table(conn)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE ai_audit_log SET actual_result = %s, result_filled_at = NOW() "
                        "WHERE match_id = %s AND actual_result IS NULL",
                        (Json(actual_result), match_id),
                    )
                    conn.commit()
                    return cur.rowcount
                except Exception:
                    conn.rollback()
                    raise
        conn = sqlite3.connect(_sqlite_path())
        _ensure_sqlite_table(conn)
        cur = conn.execute(
            "UPDATE ai_audit_log SET actual_result = ?, result_filled_at = ? "
            "WHERE match_id = ? AND actual_result IS NULL",
            (json.dumps(actual_result, ensure_ascii=False, default=str), now_iso, match_id),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return n
    except Exception as e:
        logger.warning(f"[ai-audit] fill_actual_result({match_id}) falhou: {e}")
        _reset_pg_conn()
        return 0


def get_invalid_json_rate(days: int = 7) -> Dict[str, Any]:
    """Taxa de JSON inválido por provider/stage nos últimos N dias.

    Returns {"total": int, "invalid": int, "rate": float, "by_stage": {...}}
    — zeros em falha (nunca levanta).
    """
    empty = {"total": 0, "invalid": 0, "rate": 0.0, "by_stage": {}}
    try:
        rows: List[Tuple[str, str, int, int]] = []
        if _use_postgres():
            with _PG_LOCK:
                conn = _get_pg_conn()
                _ensure_pg_table(conn)
                cur = conn.cursor()
                cur.execute(
                    "SELECT provider, stage, COUNT(*), "
                    "COUNT(*) FILTER (WHERE NOT valid_json) "
                    "FROM ai_audit_log "
                    "WHERE created_at >= NOW() - make_interval(days => %s) "
                    "GROUP BY provider, stage",
                    (days,),
                )
                rows = cur.fetchall()
        else:
            conn = sqlite3.connect(_sqlite_path())
            _ensure_sqlite_table(conn)
            cutoff = time.time() - days * 86400
            cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
            cur = conn.execute(
                "SELECT provider, stage, COUNT(*), "
                "SUM(CASE WHEN valid_json = 0 THEN 1 ELSE 0 END) "
                "FROM ai_audit_log WHERE created_at >= ? GROUP BY provider, stage",
                (cutoff_iso,),
            )
            rows = cur.fetchall()
            conn.close()

        total = sum(r[2] for r in rows)
        invalid = sum(int(r[3] or 0) for r in rows)
        return {
            "total": total,
            "invalid": invalid,
            "rate": round(invalid / total, 4) if total else 0.0,
            "by_stage": {
                f"{r[0]}/{r[1]}": {
                    "total": r[2],
                    "invalid": int(r[3] or 0),
                    "rate": round(int(r[3] or 0) / r[2], 4) if r[2] else 0.0,
                }
                for r in rows
            },
        }
    except Exception as e:
        logger.warning(f"[ai-audit] get_invalid_json_rate falhou: {e}")
        _reset_pg_conn()  # não deixar conexão compartilhada em estado abortado
        return empty


def get_pending_result_match_ids(limit: int = 500) -> List[str]:
    """match_ids com registros sem actual_result (para o script de backfill)."""
    try:
        if _use_postgres():
            with _PG_LOCK:
                conn = _get_pg_conn()
                _ensure_pg_table(conn)
                cur = conn.cursor()
                cur.execute(
                    "SELECT DISTINCT match_id FROM ai_audit_log "
                    "WHERE actual_result IS NULL AND match_id IS NOT NULL LIMIT %s",
                    (limit,),
                )
                return [r[0] for r in cur.fetchall()]
        conn = sqlite3.connect(_sqlite_path())
        _ensure_sqlite_table(conn)
        cur = conn.execute(
            "SELECT DISTINCT match_id FROM ai_audit_log "
            "WHERE actual_result IS NULL AND match_id IS NOT NULL LIMIT ?",
            (limit,),
        )
        out = [r[0] for r in cur.fetchall()]
        conn.close()
        return out
    except Exception as e:
        logger.warning(f"[ai-audit] get_pending_result_match_ids falhou: {e}")
        _reset_pg_conn()
        return []


def get_audit_stats(days: int = 7) -> Dict[str, Any]:
    """Resumo verificável do ai_audit_log (#188) — exposto em
    GET /api/ai/audit/stats. É o critério objetivo do baseline pré-Fase 2:
    volume por liga + hashes de prompt vistos (o baseline exige UM único
    prompt_sha256 do Mistral com volume antes da troca de prompt) + taxa de
    JSON inválido. Read-only; nunca levanta.
    """
    out: Dict[str, Any] = {
        "window_days": days,
        "totals": get_invalid_json_rate(days),
        "by_league": [],
        "by_prompt": [],
        "pending_results": 0,
    }
    try:
        if _use_postgres():
            with _PG_LOCK:
                conn = _get_pg_conn()
                _ensure_pg_table(conn)
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(league_id, '?'), COUNT(*) FROM ai_audit_log "
                    "WHERE created_at >= NOW() - make_interval(days => %s) "
                    "GROUP BY 1 ORDER BY 2 DESC",
                    (days,),
                )
                out["by_league"] = [
                    {"league_id": r[0], "n": r[1]} for r in cur.fetchall()
                ]
                cur.execute(
                    "SELECT COALESCE(prompt_sha256, '-'), provider, COUNT(*), "
                    "MIN(created_at), MAX(created_at) FROM ai_audit_log "
                    "WHERE created_at >= NOW() - make_interval(days => %s) "
                    "GROUP BY 1, 2 ORDER BY 3 DESC",
                    (days,),
                )
                out["by_prompt"] = [
                    {
                        "prompt_sha256": (r[0] or "-")[:12],
                        "provider": r[1],
                        "n": r[2],
                        "first_seen": str(r[3]),
                        "last_seen": str(r[4]),
                    }
                    for r in cur.fetchall()
                ]
                cur.execute(
                    "SELECT COUNT(DISTINCT match_id) FROM ai_audit_log "
                    "WHERE actual_result IS NULL AND match_id IS NOT NULL"
                )
                out["pending_results"] = cur.fetchone()[0]
            return out

        conn = sqlite3.connect(_sqlite_path())
        _ensure_sqlite_table(conn)
        cutoff_iso = datetime.fromtimestamp(
            time.time() - days * 86400, tz=timezone.utc
        ).isoformat()
        cur = conn.execute(
            "SELECT COALESCE(league_id, '?'), COUNT(*) FROM ai_audit_log "
            "WHERE created_at >= ? GROUP BY 1 ORDER BY 2 DESC",
            (cutoff_iso,),
        )
        out["by_league"] = [{"league_id": r[0], "n": r[1]} for r in cur.fetchall()]
        cur = conn.execute(
            "SELECT COALESCE(prompt_sha256, '-'), provider, COUNT(*), "
            "MIN(created_at), MAX(created_at) FROM ai_audit_log "
            "WHERE created_at >= ? GROUP BY 1, 2 ORDER BY 3 DESC",
            (cutoff_iso,),
        )
        out["by_prompt"] = [
            {
                "prompt_sha256": (r[0] or "-")[:12],
                "provider": r[1],
                "n": r[2],
                "first_seen": str(r[3]),
                "last_seen": str(r[4]),
            }
            for r in cur.fetchall()
        ]
        cur = conn.execute(
            "SELECT COUNT(DISTINCT match_id) FROM ai_audit_log "
            "WHERE actual_result IS NULL AND match_id IS NOT NULL"
        )
        out["pending_results"] = cur.fetchone()[0]
        conn.close()
        return out
    except Exception as e:
        logger.warning(f"[ai-audit] get_audit_stats falhou: {e}")
        _reset_pg_conn()
        return out


def purge_old_records(days: int = 90, keep_unresolved: bool = True) -> int:
    """Retenção (#188): apaga registros com mais de N dias (default 90).

    keep_unresolved=True preserva registros ainda sem actual_result (não
    perder amostra que o backfill pode resolver). Retorna nº de linhas
    apagadas (0 em falha — nunca levanta). NÃO é agendado automaticamente na
    Fase 1 — rodar manualmente ou acoplar ao cron na Fase 4, quando o
    relatório comparativo definir a janela mínima de amostra.
    """
    cond_unresolved = " AND actual_result IS NOT NULL" if keep_unresolved else ""
    try:
        if _use_postgres():
            with _PG_LOCK:
                conn = _get_pg_conn()
                _ensure_pg_table(conn)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "DELETE FROM ai_audit_log "
                        "WHERE created_at < NOW() - make_interval(days => %s)"
                        + cond_unresolved,
                        (days,),
                    )
                    conn.commit()
                    return cur.rowcount
                except Exception:
                    conn.rollback()
                    raise
        conn = sqlite3.connect(_sqlite_path())
        _ensure_sqlite_table(conn)
        cutoff_iso = datetime.fromtimestamp(
            time.time() - days * 86400, tz=timezone.utc
        ).isoformat()
        cur = conn.execute(
            "DELETE FROM ai_audit_log WHERE created_at < ?" + cond_unresolved,
            (cutoff_iso,),
        )
        conn.commit()
        n = cur.rowcount
        conn.close()
        return n
    except Exception as e:
        logger.warning(f"[ai-audit] purge_old_records falhou: {e}")
        _reset_pg_conn()
        return 0
