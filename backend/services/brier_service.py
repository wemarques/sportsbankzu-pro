"""Brier Score calculation and persistence (#109).

Calculates segmented Brier after each batch audit and persists to PostgreSQL.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("sportsbankzu.brier")

MIN_N = 20  # REGRA #079


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ.get("DATABASE_URL", ""))


def _ensure_table():
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS brier_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT NOW(),
                total_picks INTEGER NOT NULL,
                brier_model FLOAT,
                brier_implied FLOAT,
                model_beats_house BOOLEAN,
                delta FLOAT,
                accuracy FLOAT,
                by_league JSONB,
                by_market JSONB,
                by_band JSONB,
                by_classification JSONB,
                new_picks INTEGER DEFAULT 0,
                audit_date TEXT
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.debug(f"[Brier] ensure_table: {e}")


def _brier(probs, outcomes):
    if not probs:
        return None
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def _segment(picks):
    n = len(picks)
    if n == 0:
        return None
    probs = [p["prob"] for p in picks]
    outs = [p["out"] for p in picks]
    bm = _brier(probs, outs)
    acc = sum(outs) / n * 100
    odds = [p["odd"] for p in picks if p.get("odd")]
    bi = _brier([1.0 / o for o in odds], outs[: len(odds)]) if len(odds) >= n * 0.5 else None
    beats = bm < bi if bm is not None and bi is not None else None
    delta = bi - bm if bm is not None and bi is not None else None
    return {
        "n": n,
        "accuracy": round(acc, 1),
        "brier_model": round(bm, 4) if bm else None,
        "brier_implied": round(bi, 4) if bi else None,
        "model_beats_house": beats,
        "delta": round(delta, 4) if delta else None,
    }


def calculate_snapshot(audit_date: str = None) -> Optional[Dict]:
    """Calculate complete Brier snapshot from all picks."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT market, league, actual_result, predicted_probs, context, pick_type "
            "FROM audit_results WHERE pick_type != 'AUDIT'"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"[Brier] fetch failed: {e}")
        return None

    picks = []
    for market, league, result, pp_raw, ctx_raw, ptype in rows:
        outcome = 1 if result == "hit" else (0 if result == "miss" else None)
        if outcome is None:
            continue
        pp = json.loads(pp_raw) if isinstance(pp_raw, str) else (pp_raw or {})
        ctx = json.loads(ctx_raw) if isinstance(ctx_raw, str) else (ctx_raw or {})
        prob = pp.get("prob")
        if prob is None:
            continue
        prob = float(prob)
        if prob > 1:
            prob /= 100
        odd = pp.get("book_odd") or pp.get("odd")
        odd = float(odd) if odd and float(odd) > 1 else None
        cls = ctx.get("pick_classification", ptype or "?")
        picks.append({"prob": prob, "odd": odd, "out": outcome, "league": league, "market": market, "cls": cls})

    if not picks:
        return None

    gl = _segment(picks)

    # By league
    by_league = {}
    lg = defaultdict(list)
    for p in picks:
        lg[p["league"]].append(p)
    for k, v in lg.items():
        if len(v) >= MIN_N:
            by_league[k] = _segment(v)

    # By market
    by_market = {}
    mk = defaultdict(list)
    for p in picks:
        mk[p["market"]].append(p)
    for k, v in mk.items():
        if len(v) >= MIN_N:
            by_market[k] = _segment(v)

    # By band
    by_band = {}
    for lo, hi, label in [(0, 0.5, "<50%"), (0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"), (0.7, 0.8, "70-80%"), (0.8, 1.01, "80%+")]:
        bp = [p for p in picks if lo <= p["prob"] < hi]
        if bp:
            ap = sum(p["prob"] for p in bp) / len(bp)
            ao = sum(p["out"] for p in bp) / len(bp)
            by_band[label] = {"n": len(bp), "avg_prob": round(ap, 3), "avg_outcome": round(ao, 3), "gap": round(ap - ao, 3), "calibrated": abs(ap - ao) < 0.05}

    # By classification
    by_cls = {}
    cg = defaultdict(list)
    for p in picks:
        cg[p["cls"]].append(p)
    for k, v in cg.items():
        by_cls[k] = _segment(v)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_picks": len(picks),
        "audit_date": audit_date or datetime.utcnow().strftime("%Y-%m-%d"),
        **gl,
        "by_league": by_league,
        "by_market": by_market,
        "by_band": by_band,
        "by_classification": by_cls,
    }


def persist_snapshot(snapshot: Dict, new_picks: int = 0) -> bool:
    """Save snapshot to PostgreSQL."""
    try:
        _ensure_table()
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO brier_history (total_picks,brier_model,brier_implied,model_beats_house,"
            "delta,accuracy,by_league,by_market,by_band,by_classification,new_picks,audit_date) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                snapshot["total_picks"], snapshot.get("brier_model"), snapshot.get("brier_implied"),
                snapshot.get("model_beats_house"), snapshot.get("delta"), snapshot.get("accuracy"),
                json.dumps(snapshot.get("by_league", {})), json.dumps(snapshot.get("by_market", {})),
                json.dumps(snapshot.get("by_band", {})), json.dumps(snapshot.get("by_classification", {})),
                new_picks, snapshot.get("audit_date"),
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"[Brier] Snapshot saved: {snapshot['total_picks']} picks, beats={snapshot.get('model_beats_house')}")
        return True
    except Exception as e:
        logger.error(f"[Brier] persist failed: {e}")
        return False


def run_after_audit(new_picks: int = 0, audit_date: str = None) -> Optional[Dict]:
    """Full cycle: calculate + persist. Called by cron."""
    snap = calculate_snapshot(audit_date)
    if snap:
        persist_snapshot(snap, new_picks)
    return snap


def get_history(limit: int = 30) -> List[Dict]:
    """Fetch recent snapshots for trend display."""
    try:
        conn = _conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id,timestamp,total_picks,brier_model,brier_implied,model_beats_house,"
            "delta,accuracy,by_league,by_market,by_band,by_classification,new_picks,audit_date "
            "FROM brier_history ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        conn.close()
        for r in rows:
            if r.get("timestamp"):
                r["timestamp"] = str(r["timestamp"])
        return rows
    except Exception as e:
        logger.error(f"[Brier] history failed: {e}")
        return []
