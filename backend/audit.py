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

logging.basicConfig(
    filename="decisions.log",
    level=logging.INFO,
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _db_path() -> str:
    if os.getenv("AUDIT_DB_PATH"):
        return os.getenv("AUDIT_DB_PATH")  # type: ignore[return-value]
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/audit.db"
    return DEFAULT_DB_PATH


def _use_postgres() -> bool:
    if not psycopg2:
        return False
    if os.getenv("DATABASE_URL"):
        return True
    return all(DEFAULT_PG_CONFIG.get(k) for k in ("host", "database", "user", "password"))


def _pg_connect():
    if os.getenv("DATABASE_URL"):
        return psycopg2.connect(os.getenv("DATABASE_URL"))  # type: ignore[arg-type]
    return psycopg2.connect(**DEFAULT_PG_CONFIG)


def _ensure_columns(cursor: sqlite3.Cursor, table: str, columns: dict) -> None:
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    if _use_postgres():
        conn = _pg_connect()
    else:
        conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()

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
        },
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

    conn.commit()
    return conn


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
                """
            UPDATE thresholds
            SET safe_threshold = safe_threshold + 0.05,
                last_updated = ?
            WHERE market = ?
            """,
                (datetime.now(), market),
            )
            logging.info(
                f"Ajustado threshold SAFE para {market} de {current:.2f} → {current + 0.05:.2f}. "
                f"Motivo: Brier Score = {avg_brier:.2f}"
            )
        elif avg_brier < 0.18:
            current = get_current_threshold(conn, market, "SAFE") or defaults[market]["SAFE"]
            cursor.execute(
                """
            UPDATE thresholds
            SET safe_threshold = safe_threshold - 0.02,
                last_updated = ?
            WHERE market = ?
            """,
                (datetime.now(), market),
            )
            logging.info(
                f"Ajustado threshold SAFE para {market} de {current:.2f} → {current - 0.02:.2f}. "
                f"Motivo: Brier Score = {avg_brier:.2f}"
            )

    conn.commit()
    conn.close()
