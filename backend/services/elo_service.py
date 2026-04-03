"""ELO rating service (#107d).

Tracks team strength via ELO ratings stored in PostgreSQL.
Updated post-match by the cron handler. NOT used for lambda adjustment yet —
collecting data first, will evaluate correlation after 100+ games.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger("sportsbankzu.elo")


def _get_conn():
    try:
        import psycopg2
        url = os.getenv("DATABASE_URL", "")
        if not url:
            return None
        return psycopg2.connect(url)
    except Exception:
        return None


def _ensure_table(conn) -> bool:
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_elo (
                id SERIAL PRIMARY KEY,
                team_name TEXT NOT NULL,
                league TEXT NOT NULL,
                elo_rating FLOAT DEFAULT 1500.0,
                last_updated TIMESTAMP DEFAULT NOW(),
                matches_played INTEGER DEFAULT 0,
                UNIQUE(team_name, league)
            )
        """)
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.debug(f"[ELO] ensure_table failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def get_elo(team_name: str, league: str) -> float:
    """Get ELO rating for a team. Returns 1500 if not found."""
    conn = _get_conn()
    if not conn:
        return 1500.0
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT elo_rating FROM team_elo WHERE team_name = %s AND league = %s",
            (team_name, league),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return float(row[0]) if row else 1500.0
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 1500.0


def update_elo_after_match(
    home_team: str,
    away_team: str,
    league: str,
    home_goals: int,
    away_goals: int,
    k_factor: float = 32.0,
) -> tuple:
    """Update ELO ratings after a match. Fire-and-forget.

    Returns (new_home_elo, new_away_elo) or (None, None) on failure.
    """
    conn = _get_conn()
    if not conn:
        return (None, None)
    try:
        _ensure_table(conn)
        home_elo = get_elo(home_team, league)
        away_elo = get_elo(away_team, league)

        # Expected scores
        exp_home = 1.0 / (1.0 + 10 ** ((away_elo - home_elo) / 400.0))
        exp_away = 1.0 - exp_home

        # Actual
        if home_goals > away_goals:
            act_h, act_a = 1.0, 0.0
        elif home_goals < away_goals:
            act_h, act_a = 0.0, 1.0
        else:
            act_h, act_a = 0.5, 0.5

        # Goal diff multiplier
        gd = abs(home_goals - away_goals)
        g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8.0)

        new_h = round(home_elo + k_factor * g * (act_h - exp_home), 1)
        new_a = round(away_elo + k_factor * g * (act_a - exp_away), 1)

        cur = conn.cursor()
        for team, elo in [(home_team, new_h), (away_team, new_a)]:
            cur.execute(
                """INSERT INTO team_elo (team_name, league, elo_rating, last_updated, matches_played)
                   VALUES (%s, %s, %s, %s, 1)
                   ON CONFLICT (team_name, league)
                   DO UPDATE SET elo_rating = %s, last_updated = %s,
                                 matches_played = team_elo.matches_played + 1""",
                (team, league, elo, datetime.utcnow(), elo, datetime.utcnow()),
            )
        conn.commit()
        cur.close()
        conn.close()
        return (new_h, new_a)
    except Exception as e:
        logger.debug(f"[ELO] update failed (non-blocking): {e}")
        try:
            conn.close()
        except Exception:
            pass
        return (None, None)
