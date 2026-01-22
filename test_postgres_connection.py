import os
import psycopg2

DB_CONFIG = {
    "host": os.getenv("PGHOST", "seu_host_postgres"),
    "database": os.getenv("PGDATABASE", "audit_db"),
    "user": os.getenv("PGUSER", "seu_usuario"),
    "password": os.getenv("PGPASSWORD", "sua_senha"),
    "port": int(os.getenv("PGPORT", "5432")),
}

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM audit_results")
print("Número de registros em audit_results:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM thresholds")
print("Número de registros em thresholds:", cursor.fetchone()[0])

conn.close()
