import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
try:
    import psycopg2  # type: ignore
except Exception:
    psycopg2 = None  # type: ignore

DEFAULT_DB_PATH = "audit.db"
DEFAULT_PG_CONFIG = {
    "host": os.getenv("PGHOST"),
    "database": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "port": int(os.getenv("PGPORT", "5432")),
}

from backend.config.version import APP_VERSION as _DEFAULT_VERSION
APP_VERSION = os.getenv("SPORTSBANK_VERSION", _DEFAULT_VERSION)

audit_logger = logging.getLogger("sportsbankzu.audit")
audit_logger.setLevel(logging.INFO)

# On Lambda the filesystem is read-only except /tmp
_log_path = "/tmp/decisions.log" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "decisions.log"
try:
    _audit_handler = logging.FileHandler(_log_path)
    _audit_handler.setLevel(logging.INFO)
    _audit_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    audit_logger.addHandler(_audit_handler)
except OSError:
    # Fallback: if file handler fails, use stream handler (stdout)
    _stream_handler = logging.StreamHandler()
    _stream_handler.setLevel(logging.INFO)
    _stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    audit_logger.addHandler(_stream_handler)


def _db_path() -> str:
    if os.getenv("AUDIT_DB_PATH"):
        return os.getenv("AUDIT_DB_PATH")  # type: ignore[return-value]
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/audit.db"
    return DEFAULT_DB_PATH


# ── S3 persistence for calibrations (#059) ─────────────────────────────
# On Lambda, /tmp/audit.db is wiped on every deployment. Calibration
# corrections are persisted to S3 and auto-loaded on cold start.

_S3_CALIBRATION_KEY = "calibrations/corrections.json"
_s3_imported = False  # guard: import only once per container lifecycle

logger = logging.getLogger("sportsbankzu.audit")


def _s3_bucket() -> str | None:
    return os.getenv("S3_BUCKET") or None


def export_corrections_to_s3() -> bool:
    """Export all calibration corrections to S3 as JSON.

    Called after save_calibration() to persist across Lambda deploys.
    """
    bucket = _s3_bucket()
    if not bucket:
        return False
    try:
        import boto3
        conn = sqlite3.connect(_db_path())
        cursor = conn.cursor()
        cursor.execute(
            "SELECT match_id, league, correction_type, parameter_name, "
            "old_value, new_value, suggested_by, applied_by, "
            "audit_confidence, reason, status, created_at "
            "FROM corrections WHERE status = 'applied' AND correction_type = 'calibration'"
        )
        rows = cursor.fetchall()
        conn.close()

        corrections = []
        for row in rows:
            corrections.append({
                "match_id": row[0], "league": row[1],
                "correction_type": row[2], "parameter_name": row[3],
                "old_value": row[4], "new_value": row[5],
                "suggested_by": row[6], "applied_by": row[7],
                "audit_confidence": row[8], "reason": row[9],
                "status": row[10], "created_at": str(row[11]),
            })

        payload = json.dumps(corrections, ensure_ascii=False)
        s3 = boto3.client("s3")
        s3.put_object(Bucket=bucket, Key=_S3_CALIBRATION_KEY, Body=payload.encode("utf-8"))
        logger.info(f"[S3] Exported {len(corrections)} calibration corrections to s3://{bucket}/{_S3_CALIBRATION_KEY}")
        return True
    except Exception as e:
        logger.warning(f"[S3] Failed to export corrections: {e}")
        return False


def _import_corrections_from_s3(conn) -> int:
    """Import calibration corrections from S3 into local SQLite.

    Called on Lambda cold start when corrections table is empty.
    Returns number of corrections imported.
    """
    global _s3_imported
    if _s3_imported:
        return 0

    bucket = _s3_bucket()
    if not bucket:
        _s3_imported = True
        return 0

    try:
        import boto3
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=_S3_CALIBRATION_KEY)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        if not data:
            _s3_imported = True
            return 0

        cursor = conn.cursor()
        count = 0
        for c in data:
            cursor.execute(
                "INSERT INTO corrections "
                "(match_id, league, correction_type, parameter_name, old_value, "
                "new_value, suggested_by, applied_by, audit_confidence, reason, "
                "status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (c["match_id"], c["league"], c["correction_type"],
                 c["parameter_name"], c["old_value"], c["new_value"],
                 c.get("suggested_by", "calibration"),
                 c.get("applied_by", "system"),
                 c.get("audit_confidence", 0), c.get("reason", ""),
                 c.get("status", "applied"), c.get("created_at", "")),
            )
            count += 1
        conn.commit()
        _s3_imported = True
        logger.info(f"[S3] Imported {count} calibration corrections from s3://{bucket}/{_S3_CALIBRATION_KEY}")
        return count
    except Exception as e:
        _s3_imported = True
        logger.info(f"[S3] No calibrations to import (first deploy?): {e}")
        return 0


_PG_PLACEHOLDER_VALUES = {"seu_host_postgres", "seu_usuario", "sua_senha", "localhost", ""}


def _use_postgres() -> bool:
    if not psycopg2:
        return False
    if os.getenv("DATABASE_URL"):
        return True
    # Reject placeholder values that would cause DNS resolution failure
    host = DEFAULT_PG_CONFIG.get("host") or ""
    user = DEFAULT_PG_CONFIG.get("user") or ""
    password = DEFAULT_PG_CONFIG.get("password") or ""
    if host in _PG_PLACEHOLDER_VALUES or user in _PG_PLACEHOLDER_VALUES:
        return False
    return all(DEFAULT_PG_CONFIG.get(k) for k in ("host", "database", "user", "password"))


def _pg_connect():
    if os.getenv("DATABASE_URL"):
        return psycopg2.connect(os.getenv("DATABASE_URL"))  # type: ignore[arg-type]
    return psycopg2.connect(**DEFAULT_PG_CONFIG)


def _ensure_columns(cursor, table: str, columns: dict, is_pg: bool = False) -> None:
    if is_pg:
        # PostgreSQL: query information_schema for column names
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        existing = {row[0] for row in cursor.fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                # Quote column name to handle reserved words like "user"
                col_name = f'"{name}"' if name in ("user",) else name
                col_type = ddl.split(" ", 1)[1] if " " in ddl else ddl
                try:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}')
                except Exception:
                    pass  # Column may already exist
    else:
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    is_pg = _use_postgres()
    if is_pg:
        conn = _pg_connect()
    else:
        conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()

    if is_pg:
        cursor.execute(
            """
CREATE TABLE IF NOT EXISTS audit_results (
    match_id TEXT,
    league TEXT,
    market TEXT,
    predicted_probs TEXT,
    actual_result TEXT,
    pick_type TEXT,
    brier_score REAL,
    ev REAL,
    context TEXT,
    "timestamp" TIMESTAMP,
    "user" TEXT DEFAULT 'system',
    version TEXT
)
"""
        )
    else:
        cursor.execute(
            """
CREATE TABLE IF NOT EXISTS audit_results (
    match_id TEXT PRIMARY KEY,
    league TEXT,
    market TEXT,
    predicted_probs TEXT,
    actual_result TEXT,
    pick_type TEXT,
    brier_score REAL,
    ev REAL,
    context TEXT,
    timestamp DATETIME
)
"""
        )

    _ensure_columns(
        cursor,
        "audit_results",
        {
            "market": "market TEXT",
            "predicted_probs": "predicted_probs TEXT",
            "actual_result": "actual_result TEXT",
            "pick_type": "pick_type TEXT",
            "brier_score": "brier_score REAL",
            "ev": "ev REAL",
            "context": "context TEXT",
            "timestamp": "timestamp DATETIME",
            "user": "user TEXT DEFAULT 'system'",
            "version": "version TEXT",
        },
        is_pg=is_pg,
    )

    cursor.execute(
        """
CREATE TABLE IF NOT EXISTS thresholds (
    market TEXT,
    safe_threshold REAL,
    neutro_threshold REAL,
    last_updated DATETIME
)
"""
    )

    if is_pg:
        cursor.execute(
            """
CREATE TABLE IF NOT EXISTS corrections (
    id SERIAL PRIMARY KEY,
    match_id TEXT,
    league TEXT,
    correction_type TEXT,
    parameter_name TEXT,
    old_value REAL,
    new_value REAL,
    suggested_by TEXT DEFAULT 'mistral_audit',
    applied_by TEXT DEFAULT 'user',
    audit_confidence INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'applied',
    created_at TIMESTAMP,
    reverted_at TIMESTAMP
)
"""
        )
    else:
        cursor.execute(
            """
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    league TEXT,
    correction_type TEXT,
    parameter_name TEXT,
    old_value REAL,
    new_value REAL,
    suggested_by TEXT DEFAULT 'mistral_audit',
    applied_by TEXT DEFAULT 'user',
    audit_confidence INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'applied',
    created_at DATETIME,
    reverted_at DATETIME
)
"""
        )

    # PostgreSQL: ensure UNIQUE constraints exist for ON CONFLICT clauses
    # Tables may have been created without PRIMARY KEY by older code versions.
    # Steps: (1) deduplicate existing rows, (2) create unique index idempotently.
    if is_pg:
        _ensure_pg_unique_constraints(cursor)

    conn.commit()

    # Auto-import calibrations from S3 on Lambda cold start (#059)
    if not is_pg and os.getenv("AWS_LAMBDA_FUNCTION_NAME") and not _s3_imported:
        try:
            cursor.execute("SELECT COUNT(*) FROM corrections WHERE correction_type = 'calibration'")
            if cursor.fetchone()[0] == 0:
                _import_corrections_from_s3(conn)
        except Exception:
            pass

    return conn


def _ensure_pg_unique_constraints(cursor) -> None:
    """Create UNIQUE indexes on PostgreSQL tables if they don't exist.

    Handles the case where tables were created without PRIMARY KEY constraints,
    causing ON CONFLICT to fail. Deduplicates existing data before creating indexes.
    """
    # --- audit_results: unique on match_id ---
    try:
        # Check if unique constraint already exists
        cursor.execute("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'audit_results'
              AND (indexdef LIKE '%UNIQUE%match_id%' OR indexdef LIKE '%PRIMARY%')
            LIMIT 1
        """)
        if not cursor.fetchone():
            # Deduplicate: keep latest row per match_id (by timestamp)
            cursor.execute("""
                DELETE FROM audit_results a
                USING audit_results b
                WHERE a.ctid < b.ctid AND a.match_id = b.match_id
            """)
            deduped = cursor.rowcount
            if deduped:
                audit_logger.info(f"[audit] Deduplicated {deduped} rows from audit_results")
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_results_match_id
                ON audit_results (match_id)
            """)
            audit_logger.info("[audit] Created UNIQUE index on audit_results(match_id)")
    except Exception as e:
        audit_logger.warning(f"[audit] Failed to ensure audit_results unique constraint: {e}")

    # --- thresholds: unique on market ---
    try:
        cursor.execute("""
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'thresholds'
              AND (indexdef LIKE '%UNIQUE%market%' OR indexdef LIKE '%PRIMARY%')
            LIMIT 1
        """)
        if not cursor.fetchone():
            cursor.execute("""
                DELETE FROM thresholds a
                USING thresholds b
                WHERE a.ctid < b.ctid AND a.market = b.market
            """)
            deduped = cursor.rowcount
            if deduped:
                audit_logger.info(f"[audit] Deduplicated {deduped} rows from thresholds")
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_thresholds_market
                ON thresholds (market)
            """)
            audit_logger.info("[audit] Created UNIQUE index on thresholds(market)")
    except Exception as e:
        audit_logger.warning(f"[audit] Failed to ensure thresholds unique constraint: {e}")


def log_audit_result(
    match_id: str,
    league: str,
    audit_data: dict,
    match_status: str,
    user: str = "system",
    version: str | None = None,
) -> None:
    """Store full audit result from MistralAuditor with user/version tracking."""
    ver = version or APP_VERSION
    conn = init_db()
    cursor = conn.cursor()
    record_id = f"{match_id}:audit"
    now = datetime.now()
    if _use_postgres():
        cursor.execute(
            """
            INSERT INTO audit_results
            (match_id, league, market, predicted_probs, actual_result, pick_type, context, timestamp, "user", version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id) DO UPDATE
            SET context = EXCLUDED.context, timestamp = EXCLUDED.timestamp,
                "user" = EXCLUDED."user", version = EXCLUDED.version
            """,
            (record_id, league, "audit", json.dumps(audit_data), match_status,
             "AUDIT", json.dumps(audit_data), now, user, ver),
        )
    else:
        cursor.execute(
            """
            INSERT OR REPLACE INTO audit_results
            (match_id, league, market, predicted_probs, actual_result, pick_type, context, timestamp, user, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, league, "audit", json.dumps(audit_data), match_status,
             "AUDIT", json.dumps(audit_data), now, user, ver),
        )
    conn.commit()
    conn.close()

    # Structured decisions.log entry
    brier = audit_data.get("avg_brier_score", audit_data.get("brier_score", ""))
    ev = audit_data.get("ev", "")
    audit_logger.info(
        f"Auditoria registrada: match_id={match_id}, league={league}, "
        f"brier_score={brier}, ev={ev}, "
        f"context={json.dumps(audit_data, ensure_ascii=False)}, "
        f"user={user}, version={ver}"
    )


def log_correction(
    match_id: str,
    league: str,
    correction_type: str,
    parameter_name: str,
    old_value: float,
    new_value: float,
    suggested_by: str = "mistral_audit",
    applied_by: str = "user",
    audit_confidence: int = 0,
    reason: str = "",
) -> None:
    """Store a correction applied from an audit suggestion."""
    conn = init_db()
    cursor = conn.cursor()
    if _use_postgres():
        cursor.execute(
            """
            INSERT INTO corrections
            (match_id, league, correction_type, parameter_name, old_value, new_value,
             suggested_by, applied_by, audit_confidence, reason, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied', %s)
            """,
            (match_id, league, correction_type, parameter_name, old_value, new_value,
             suggested_by, applied_by, audit_confidence, reason, datetime.now()),
        )
    else:
        cursor.execute(
            """
            INSERT INTO corrections
            (match_id, league, correction_type, parameter_name, old_value, new_value,
             suggested_by, applied_by, audit_confidence, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'applied', ?)
            """,
            (match_id, league, correction_type, parameter_name, old_value, new_value,
             suggested_by, applied_by, audit_confidence, reason, datetime.now()),
        )
    conn.commit()
    conn.close()
    audit_logger.info(
        f"Correcao aplicada: parameter={parameter_name}, old={old_value:.4f}, new={new_value:.4f}, "
        f"league={league}, type={correction_type}, confidence={audit_confidence}%, "
        f"suggested_by={suggested_by}, applied_by={applied_by}, version={APP_VERSION}"
    )


def get_active_corrections(league: str | None = None) -> list:
    """Fetch active corrections, optionally filtered by league."""
    conn = init_db()
    cursor = conn.cursor()
    if league:
        ph = "%s" if _use_postgres() else "?"
        cursor.execute(
            f"SELECT parameter_name, new_value, correction_type, reason FROM corrections "
            f"WHERE (league = {ph} OR league = 'ALL') AND status = 'applied' ORDER BY created_at DESC",
            (league,),
        )
    else:
        cursor.execute(
            "SELECT parameter_name, new_value, correction_type, reason FROM corrections "
            "WHERE status = 'applied' ORDER BY created_at DESC"
        )
    rows = cursor.fetchall()
    conn.close()
    corrections = {}
    for row in rows:
        param = row[0]
        if param not in corrections:
            corrections[param] = {"value": row[1], "type": row[2], "reason": row[3]}
    return corrections


def ensure_thresholds(conn, defaults: dict) -> None:
    cursor = conn.cursor()
    for market, thresholds in defaults.items():
        if _use_postgres():
            cursor.execute(
                """
                INSERT INTO thresholds (market, safe_threshold, neutro_threshold, last_updated)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (market) DO NOTHING
                """,
                (market, thresholds["SAFE"], thresholds["NEUTRO"], datetime.now()),
            )
        else:
            cursor.execute(
                """
                INSERT OR IGNORE INTO thresholds (market, safe_threshold, neutro_threshold, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                (market, thresholds["SAFE"], thresholds["NEUTRO"], datetime.now()),
            )
    conn.commit()


def calculate_brier(prob: float, outcome: bool) -> float:
    return (prob - (1 if outcome else 0)) ** 2


def get_current_threshold(conn, market: str, pick_type: str) -> float | None:
    cursor = conn.cursor()
    if _use_postgres():
        cursor.execute(
            f"SELECT {pick_type.lower()}_threshold FROM thresholds WHERE market = %s",
            (market,),
        )
    else:
        cursor.execute(
            f"SELECT {pick_type.lower()}_threshold FROM thresholds WHERE market = ?",
            (market,),
        )
    row = cursor.fetchone()
    return row[0] if row else None


def log_pick(
    match_id: str,
    league: str,
    market: str,
    predicted_probs: dict,
    pick_type: str,
    ev: float | None,
    context: dict | None = None,
    actual_result: str | None = None,
) -> None:
    conn = init_db()
    cursor = conn.cursor()

    record_id = f"{match_id}:{market}"
    brier_score = None
    if actual_result and actual_result in predicted_probs:
        brier_score = calculate_brier(float(predicted_probs.get(actual_result, 0.0)), True)

    if _use_postgres():
        cursor.execute(
            """
        INSERT INTO audit_results
        (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO UPDATE
        SET league = EXCLUDED.league,
            market = EXCLUDED.market,
            predicted_probs = EXCLUDED.predicted_probs,
            actual_result = EXCLUDED.actual_result,
            pick_type = EXCLUDED.pick_type,
            brier_score = EXCLUDED.brier_score,
            ev = EXCLUDED.ev,
            context = EXCLUDED.context,
            timestamp = EXCLUDED.timestamp
        """,
            (
                record_id,
                league,
                market,
                json.dumps(predicted_probs),
                actual_result,
                pick_type,
                brier_score,
                ev,
                json.dumps(context or {}),
                datetime.now(),
            ),
        )
    else:
        cursor.execute(
            """
        INSERT OR REPLACE INTO audit_results
        (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record_id,
                league,
                market,
                json.dumps(predicted_probs),
                actual_result,
                pick_type,
                brier_score,
                ev,
                json.dumps(context or {}),
                datetime.now(),
            ),
        )
    conn.commit()
    conn.close()


def adjust_thresholds(defaults: dict) -> None:
    conn = init_db()
    ensure_thresholds(conn, defaults)
    cursor = conn.cursor()
    is_pg = _use_postgres()
    ph = "%s" if is_pg else "?"
    cursor.execute(
        """
        SELECT market, AVG(brier_score) as avg_brier
        FROM audit_results
        WHERE brier_score IS NOT NULL
        GROUP BY market
        """
    )
    markets = cursor.fetchall()

    from backend.services.brier_service import BRIER_TARGET  # #178
    for market, avg_brier in markets:
        if market not in defaults:
            continue
        if avg_brier > BRIER_TARGET:
            current = get_current_threshold(conn, market, "SAFE") or defaults[market]["SAFE"]
            cursor.execute(
                f"""
            UPDATE thresholds
            SET safe_threshold = safe_threshold + 0.05,
                last_updated = {ph}
            WHERE market = {ph}
            """,
                (datetime.now(), market),
            )
            audit_logger.info(
                f"Threshold ajustado: market={market}, parameter=safe_threshold, "
                f"old={current:.2f}, new={current + 0.05:.2f}, "
                f"reason=brier_score_alto({avg_brier:.2f}), user=system, version={APP_VERSION}"
            )
        elif avg_brier < 0.18:
            current = get_current_threshold(conn, market, "SAFE") or defaults[market]["SAFE"]
            cursor.execute(
                f"""
            UPDATE thresholds
            SET safe_threshold = safe_threshold - 0.02,
                last_updated = {ph}
            WHERE market = {ph}
            """,
                (datetime.now(), market),
            )
            audit_logger.info(
                f"Threshold ajustado: market={market}, parameter=safe_threshold, "
                f"old={current:.2f}, new={current - 0.02:.2f}, "
                f"reason=brier_score_bom({avg_brier:.2f}), user=system, version={APP_VERSION}"
            )

    conn.commit()
    conn.close()


# --- Read functions for audit status endpoint ---


def get_recent_audit_results(days: int = 7, limit: int = 10) -> list:
    """Fetch recent batch audit results (cron runs)."""
    conn = init_db()
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    is_pg = _use_postgres()
    ph = "%s" if is_pg else "?"
    ts_col = '"timestamp"' if is_pg else "timestamp"
    user_col = '"user"' if is_pg else "user"
    query = (
        f"SELECT match_id, league, context, {ts_col}, "
        f"{user_col}, version "
        f"FROM audit_results WHERE pick_type = 'AUDIT' AND {ts_col} >= {ph} "
        f"ORDER BY {ts_col} DESC LIMIT {ph}"
    )
    cursor.execute(query, (cutoff, limit))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        ctx = {}
        try:
            ctx = json.loads(r[2]) if r[2] else {}
        except Exception:
            pass
        ts = r[3]
        results.append({
            "match_id": r[0],
            "league": r[1],
            "data": ctx,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "user": r[4],
            "version": r[5],
        })
    return results


def get_recent_corrections(days: int = 7, limit: int = 20) -> list:
    """Fetch recent corrections (applied and rejected)."""
    conn = init_db()
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    ph = "%s" if _use_postgres() else "?"
    cursor.execute(
        f"SELECT match_id, league, correction_type, parameter_name, old_value, "
        f"new_value, suggested_by, applied_by, audit_confidence, reason, status, "
        f"created_at FROM corrections WHERE created_at >= {ph} "
        f"ORDER BY created_at DESC LIMIT {ph}",
        (cutoff, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "match_id": r[0],
            "league": r[1],
            "type": r[2],
            "parameter": r[3],
            "old_value": r[4],
            "new_value": r[5],
            "suggested_by": r[6],
            "applied_by": r[7],
            "confidence": r[8],
            "reason": r[9],
            "status": r[10],
            "created_at": r[11].isoformat() if hasattr(r[11], "isoformat") else str(r[11]),
        }
        for r in rows
    ]


# --- Safety limits for automatic adjustments ---

ADJUSTMENT_LIMITS = {
    "THRESHOLD": {"min": 0.40, "max": 0.95, "max_delta": 0.10},
    "LAMBDA_WEIGHT": {"min": 0.10, "max": 0.90, "max_delta": 0.15},
    "MARKET_FILTER": {"min": 0.0, "max": 1.0, "max_delta": 0.20},
    "AI_PROMPT": {"min": 0.0, "max": 1.0, "max_delta": 0.30},
    "BTTS_THRESHOLD": {"min": 0.40, "max": 0.95, "max_delta": 0.12},
    "CORNER_THRESHOLD": {"min": 0.30, "max": 0.95, "max_delta": 0.12},
    "CORNER_MULTIPLIER": {"min": 0.70, "max": 1.40, "max_delta": 0.15},
    "BTTS_MULTIPLIER": {"min": 0.70, "max": 1.40, "max_delta": 0.15},
    # #171: Lambda deflation has its own range — NOT a probability threshold!
    # Without this entry, validate_adjustment fell back to "THRESHOLD" (range
    # 0.40-0.95), which let aggressive deflations like 0.84 pass while normal
    # values 1.0 were rejected. Cause of the auto-correction cascade that
    # produced the P0 50%-bankroll incident on 2026-04-26/27.
    "lambda_deflation": {"min": 0.80, "max": 1.20, "max_delta": 0.08},
    "lambda_calibration": {"min": 0.10, "max": 0.90, "max_delta": 0.10},
}


def validate_adjustment(
    correction_type: str, parameter: str, old_value: float, new_value: float
) -> tuple:
    """Validate that an adjustment is within safety limits.

    Returns (is_valid: bool, reason: str).
    """
    # Block market_reference_signal from automatic corrections (v1 governance)
    if correction_type == "MARKET_REFERENCE_SIGNAL" or "market_reference" in parameter.lower():
        return False, "market_reference_signal nao e ajustavel por correcao automatica (v1)"

    limits = ADJUSTMENT_LIMITS.get(correction_type, ADJUSTMENT_LIMITS.get("THRESHOLD"))
    if limits is None:
        return False, f"Unknown correction type: {correction_type}"
    if new_value < limits["min"] or new_value > limits["max"]:
        return False, (
            f"Valor {new_value} fora do range [{limits['min']}, {limits['max']}]"
        )
    delta = abs(new_value - old_value)
    if delta > limits["max_delta"]:
        return False, (
            f"Delta {delta:.4f} excede maximo {limits['max_delta']}"
        )
    return True, "OK"


# ---------------------------------------------------------------------------
# Mistral feedback loop storage (REGRAS #050)
# ---------------------------------------------------------------------------

def _ensure_mistral_predictions_table():
    """Create mistral_predictions table if not exists."""
    is_pg = _use_postgres()
    if is_pg:
        conn = _pg_connect()
    else:
        conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    if is_pg:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mistral_predictions (
                id SERIAL PRIMARY KEY,
                match_id TEXT,
                league TEXT,
                market TEXT,
                mistral_confidence INTEGER,
                recommended_market TEXT,
                recommended_odd REAL,
                actual_result TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mistral_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                league TEXT,
                market TEXT,
                mistral_confidence INTEGER,
                recommended_market TEXT,
                recommended_odd REAL,
                actual_result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    cursor.close()
    conn.close()


def log_mistral_prediction(
    match_id: str,
    league: str,
    market: str,
    mistral_confidence: int,
    recommended_market: str,
    recommended_odd: float | None = None,
    actual_result: str | None = None,
) -> None:
    """Store Mistral prediction for feedback loop.

    Reference: REGRAS #050 section 5.2E — Mistral feedback loop.
    """
    try:
        _ensure_mistral_predictions_table()
        is_pg = _use_postgres()
        if is_pg:
            conn = _pg_connect()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO mistral_predictions (match_id, league, market, mistral_confidence, recommended_market, recommended_odd, actual_result) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (match_id, league, market, mistral_confidence, recommended_market, recommended_odd, actual_result),
            )
        else:
            conn = sqlite3.connect(_db_path())
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO mistral_predictions (match_id, league, market, mistral_confidence, recommended_market, recommended_odd, actual_result) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (match_id, league, market, mistral_confidence, recommended_market, recommended_odd, actual_result),
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        audit_logger.error(f"Failed to log Mistral prediction: {e}")


def get_mistral_accuracy(league: str, days: int = 30) -> dict:
    """Return Mistral accuracy by league and market.

    Used to include in prompt: "In the last N analyses for this league, we hit X%"
    """
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    cutoff = (_dt.now(_tz.utc) - _td(days=days)).isoformat()
    result = {
        "league": league,
        "period_days": days,
        "total_predictions": 0,
        "overall_accuracy": 0.0,
        "by_market": {},
        "confidence_calibration": {
            "high_confidence_accuracy": 0.0,
            "low_confidence_accuracy": 0.0,
        },
    }

    try:
        _ensure_mistral_predictions_table()
        is_pg = _use_postgres()
        if is_pg:
            conn = _pg_connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT market, mistral_confidence, recommended_market, actual_result "
                "FROM mistral_predictions WHERE league = %s AND created_at >= %s AND actual_result IS NOT NULL",
                (league, cutoff),
            )
        else:
            conn = sqlite3.connect(_db_path())
            cur = conn.cursor()
            cur.execute(
                "SELECT market, mistral_confidence, recommended_market, actual_result "
                "FROM mistral_predictions WHERE league = ? AND created_at >= ? AND actual_result IS NOT NULL",
                (league, cutoff),
            )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return result

        total = 0
        correct = 0
        by_market: dict = {}
        high_conf_total, high_conf_correct = 0, 0
        low_conf_total, low_conf_correct = 0, 0

        for mkt, confidence, rec_market, actual in rows:
            total += 1
            hit = str(actual).lower() in ("true", "1", "yes", "win", "hit", "correct")
            if hit:
                correct += 1

            by_market.setdefault(mkt, {"total": 0, "correct": 0})
            by_market[mkt]["total"] += 1
            if hit:
                by_market[mkt]["correct"] += 1

            conf = int(confidence) if confidence else 0
            if conf >= 70:
                high_conf_total += 1
                if hit:
                    high_conf_correct += 1
            elif conf < 50:
                low_conf_total += 1
                if hit:
                    low_conf_correct += 1

        for mkt_stats in by_market.values():
            mkt_stats["accuracy"] = round(mkt_stats["correct"] / mkt_stats["total"], 4) if mkt_stats["total"] > 0 else 0.0

        result["total_predictions"] = total
        result["overall_accuracy"] = round(correct / total, 4) if total > 0 else 0.0
        result["by_market"] = by_market
        result["confidence_calibration"] = {
            "high_confidence_accuracy": round(high_conf_correct / high_conf_total, 4) if high_conf_total > 0 else 0.0,
            "low_confidence_accuracy": round(low_conf_correct / low_conf_total, 4) if low_conf_total > 0 else 0.0,
        }

    except Exception as e:
        audit_logger.error(f"Failed to get Mistral accuracy: {e}")

    return result


def increment_version() -> str:
    """Increment the patch component of APP_VERSION (e.g. 'pro V2.7' -> 'pro V2.8')."""
    global APP_VERSION
    import re as _re

    m = _re.search(r"(\d+)\.(\d+)", APP_VERSION)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        new_ver = APP_VERSION.replace(f"{major}.{minor}", f"{major}.{minor + 1}")
        APP_VERSION = new_ver
        os.environ["SPORTSBANK_VERSION"] = new_ver
        audit_logger.info(f"Versao incrementada: {new_ver}")
        return new_ver
    return APP_VERSION
