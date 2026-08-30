"""#189-e — unifica os IDs/rótulos de liga fragmentados no audit_results.

Problema (auditoria 29-30/08/2026): o histórico do Brasileirão A estava
partido em dois rótulos ("Brasileirao Serie A" n=396 + "Brazil Serie A"
n=24) e o mesmo ocorria com League One ("League One" + "England League
One"). A fragmentação dilui as células de treino do calibrador e fez os
primeiros 24 picks (46% acc) calibrarem sozinhos o fator de deflação
estático da liga.

Idempotente: rodar duas vezes não altera nada. Suporta Postgres (via
backend.audit) e SQLite (fallback local).

Uso:
    python -m backend.migrations.migrate_189e_unify_league_ids
"""
import logging

logger = logging.getLogger("sportsbankzu.migrations.189e")

# rótulo_antigo -> rótulo_canônico (cobre id-style e display-style)
LEAGUE_LABEL_MERGES = {
    # Brasileirão Série A
    "brazil-serie-a": "brasileirao-serie-a",
    "Brazil Serie A": "Brasileirao Serie A",
    # Brasileirão Série B
    "brazil-serie-b": "brasileirao-serie-b",
    "Brazil Serie B": "Brasileirao Serie B",
    # League One
    "england-league-one": "league-one",
    "England League One": "League One",
    # League Two
    "england-league-two": "league-two",
    "England League Two": "League Two",
}

TABLES_WITH_LEAGUE = [
    ("audit_results", "league"),
]


def run() -> dict:
    from backend.audit import init_db, _use_postgres

    summary = {"backend": "postgres" if _use_postgres() else "sqlite", "updated": {}}

    if _use_postgres():
        from backend.audit import _pg_connect
        conn = _pg_connect()
        cur = conn.cursor()
        for table, col in TABLES_WITH_LEAGUE:
            for old, new in LEAGUE_LABEL_MERGES.items():
                cur.execute(
                    f"UPDATE {table} SET {col} = %s WHERE {col} = %s", (new, old)
                )
                if cur.rowcount:
                    summary["updated"][f"{table}.{col}: {old}->{new}"] = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
    else:
        conn = init_db()
        for table, col in TABLES_WITH_LEAGUE:
            for old, new in LEAGUE_LABEL_MERGES.items():
                cur = conn.execute(
                    f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new, old)
                )
                if cur.rowcount:
                    summary["updated"][f"{table}.{col}: {old}->{new}"] = cur.rowcount
        conn.commit()
        conn.close()

    logger.info(f"[189e] league label migration: {summary}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
