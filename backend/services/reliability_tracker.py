"""Reliability metrics tracker with PostgreSQL persistence (#102).

Fire-and-forget: INSERT failures never block the pipeline.
Reads aggregate from DB for the dashboard.
Falls back to in-memory counters when PostgreSQL is unavailable.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger("sportsbankzu.reliability")

# In-memory fallback (used when PostgreSQL unavailable)
_mem_counters: dict[str, int] = defaultdict(int)


def _get_conn():
    """Get a fresh PostgreSQL connection. Caller must close."""
    try:
        import psycopg2
    except ImportError:
        return None
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        logger.debug(f"[ReliabilityTracker] PG connect failed: {e}")
        return None


def _ensure_table(conn) -> bool:
    """Create table if not exists. Returns True on success."""
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reliability_events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                event_name VARCHAR(100) NOT NULL,
                event_value FLOAT DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_events_type_created
                ON reliability_events(event_type, created_at)
        """)
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.debug(f"[ReliabilityTracker] ensure_table failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def track_event(event_type: str, event_name: str, event_value: float = 1.0):
    """Fire-and-forget INSERT. NEVER raises."""
    _mem_counters[event_name] += int(event_value)
    conn = _get_conn()
    if not conn:
        return
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO reliability_events (event_type, event_name, event_value) VALUES (%s, %s, %s)",
            (event_type, event_name, event_value),
        )
        conn.commit()
        cur.close()
    except Exception as e:
        logger.debug(f"[ReliabilityTracker] INSERT failed (non-blocking): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def track_api_call(api_name: str, success: bool):
    """Track an API call result."""
    track_event("api_call", f"{api_name}_{'ok' if success else 'fail'}")


def track_safety(event_name: str, count: int = 1):
    """Track a safety event."""
    track_event("safety_block", event_name, float(count))


def track_duration(duration_ms: float):
    """Track Lambda execution duration."""
    track_event("duration", "lambda_duration_ms", duration_ms)


def get_stats(days: int = 30) -> dict:
    """Read aggregated stats from PostgreSQL. Falls back to memory. NEVER raises."""
    conn = _get_conn()
    if not conn:
        return dict(_mem_counters)
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        since = datetime.utcnow() - timedelta(days=days)

        # API call counts
        cur.execute(
            "SELECT event_name, COUNT(*) FROM reliability_events "
            "WHERE event_type = 'api_call' AND created_at >= %s GROUP BY event_name",
            (since,),
        )
        api_counts = dict(cur.fetchall())

        # Safety block counts
        cur.execute(
            "SELECT event_name, SUM(event_value)::int FROM reliability_events "
            "WHERE event_type = 'safety_block' AND created_at >= %s GROUP BY event_name",
            (since,),
        )
        safety_counts = dict(cur.fetchall())

        # Duration stats
        cur.execute(
            "SELECT AVG(event_value), "
            "       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY event_value), "
            "       STDDEV(event_value), "
            "       COUNT(*) "
            "FROM reliability_events "
            "WHERE event_type = 'duration' AND created_at >= %s",
            (since,),
        )
        row = cur.fetchone()
        avg_d, p95_d, std_d, n_d = row if row else (None, None, None, 0)
        n_d = n_d or 0

        cur.close()
        conn.close()

        cv = round(std_d / avg_d, 3) if avg_d and std_d and avg_d > 0 else None

        return {
            "api_football_ok": api_counts.get("api_football_ok", 0),
            "api_football_fail": api_counts.get("api_football_fail", 0),
            "footystats_ok": api_counts.get("footystats_ok", 0),
            "footystats_fail": api_counts.get("footystats_fail", 0),
            "mistral_ok": api_counts.get("mistral_ok", 0),
            "mistral_fail": api_counts.get("mistral_fail", 0),
            "complementares_bloqueados": safety_counts.get("complementares_bloqueados", 0),
            "acoes_bloqueadas": safety_counts.get("acoes_bloqueadas", 0),
            "mistral_contradicoes": safety_counts.get("mistral_contradicoes", 0),
            "fallbacks_ativados": safety_counts.get("fallbacks_ativados", 0),
            "avg_duration_ms": round(avg_d, 1) if avg_d else None,
            "p95_duration_ms": round(p95_d, 1) if p95_d else None,
            "cv_duration": cv,
            "duration_count": n_d,
        }

        # Picks per match
        try:
            conn2 = _get_conn()
            if conn2:
                cur2 = conn2.cursor()
                cur2.execute(
                    "SELECT AVG(event_value), STDDEV(event_value) FROM reliability_events "
                    "WHERE event_name = 'picks_per_match' AND created_at >= %s",
                    (since,),
                )
                ppm = cur2.fetchone()
                cur2.close()
                conn2.close()
                if ppm and ppm[0]:
                    result["picks_por_jogo_avg"] = round(ppm[0], 1)
                    if ppm[1] and ppm[0] > 0:
                        result["picks_por_jogo_cv"] = round(ppm[1] / ppm[0], 3)
        except Exception:
            pass

        return result

    except Exception as e:
        logger.debug(f"[ReliabilityTracker] get_stats failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return dict(_mem_counters)


def cleanup_old_events(days: int = 90):
    """Delete events older than N days. Call from cron."""
    conn = _get_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cutoff = datetime.utcnow() - timedelta(days=days)
        cur.execute("DELETE FROM reliability_events WHERE created_at < %s", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if deleted > 0:
            logger.info(f"[ReliabilityTracker] Cleanup: {deleted} old events removed")
    except Exception as e:
        logger.debug(f"[ReliabilityTracker] Cleanup failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
