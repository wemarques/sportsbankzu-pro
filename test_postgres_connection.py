import os
import psycopg2

DB_CONFIG = {
    "host": os.getenv("PGHOST"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "port": int(os.getenv("PGPORT", "5432")),
}

if not DB_CONFIG["host"]:
    raise ValueError("PGHOST not set. Export PGHOST, PGUSER, PGPASSWORD first.")

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM audit_results")
print("Número de registros em audit_results:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM thresholds")
print("Número de registros em thresholds:", cursor.fetchone()[0])

conn.close()
