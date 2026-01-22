import json
import os
import sqlite3
import psycopg2

SQLITE_DB = os.getenv("SQLITE_DB", "audit.db")

POSTGRES_CONFIG = {
    "host": os.getenv("PGHOST", "seu_host_postgres"),
    "database": os.getenv("PGDATABASE", "audit_db"),
    "user": os.getenv("PGUSER", "seu_usuario"),
    "password": os.getenv("PGPASSWORD", "sua_senha"),
    "port": int(os.getenv("PGPORT", "5432")),
}


def migrate_sqlite_to_postgres():
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()

    postgres_conn = psycopg2.connect(**POSTGRES_CONFIG)
    postgres_cursor = postgres_conn.cursor()

    postgres_cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS audit_results (
        match_id TEXT PRIMARY KEY,
        league TEXT,
        market TEXT,
        predicted_probs JSONB,
        actual_result TEXT,
        pick_type TEXT,
        brier_score REAL,
        ev REAL,
        context JSONB,
        timestamp TIMESTAMP
    )
    """
    )

    postgres_cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS thresholds (
        market TEXT PRIMARY KEY,
        safe_threshold REAL,
        neutro_threshold REAL,
        last_updated TIMESTAMP
    )
    """
    )

    sqlite_cursor.execute("SELECT * FROM audit_results")
    audit_results = sqlite_cursor.fetchall()

    for row in audit_results:
        match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp = row
        predicted_probs = json.dumps(json.loads(predicted_probs)) if predicted_probs else None
        context = json.dumps(json.loads(context)) if context else None

        postgres_cursor.execute(
            """
        INSERT INTO audit_results (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (match_id) DO NOTHING
        """,
            (match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp),
        )

    sqlite_cursor.execute("SELECT * FROM thresholds")
    thresholds = sqlite_cursor.fetchall()

    for row in thresholds:
        market, safe_threshold, neutro_threshold, last_updated = row
        postgres_cursor.execute(
            """
        INSERT INTO thresholds (market, safe_threshold, neutro_threshold, last_updated)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (market) DO NOTHING
        """,
            (market, safe_threshold, neutro_threshold, last_updated),
        )

    postgres_conn.commit()
    sqlite_conn.close()
    postgres_conn.close()

    print("Migração concluída com sucesso!")


if __name__ == "__main__":
    migrate_sqlite_to_postgres()
