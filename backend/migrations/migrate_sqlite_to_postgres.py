import os
import sqlite3
try:
    import psycopg2  # type: ignore
except Exception:
    psycopg2 = None  # type: ignore

def migrate(sqlite_path: str, pg_url: str) -> None:
    if not psycopg2:
        raise RuntimeError("psycopg2 não disponível")
    src = sqlite3.connect(sqlite_path)
    dst = psycopg2.connect(pg_url)  # type: ignore[arg-type]
    sc = src.cursor()
    dc = dst.cursor()
    sc.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in sc.fetchall()]
    for t in tables:
        sc.execute(f"SELECT * FROM {t}")
        rows = sc.fetchall()
        placeholders = ",".join(["%s"] * len(rows[0])) if rows else ""
        for row in rows:
            dc.execute(f"INSERT INTO {t} VALUES ({placeholders})", row)
    dst.commit()
    src.close()
    dst.close()
