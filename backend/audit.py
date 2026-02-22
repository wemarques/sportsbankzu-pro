import json
import logging
import os
import sqlite3
from datetime import datetime
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

APP_VERSION = os.getenv("SPORTSBANK_VERSION", "pro V2.7")

audit_logger = logging.getLogger("sportsbank.audit")
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
    match_id TEXT PRIMARY KEY,
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
    market TEXT PRIMARY KEY,
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

    conn.commit()
    return conn


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
            f"WHERE league = {ph} AND status = 'applied' ORDER BY created_at DESC",
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

    for market, avg_brier in markets:
        if market not in defaults:
            continue
        if avg_brier > 0.25:
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
