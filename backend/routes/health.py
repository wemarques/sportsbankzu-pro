from fastapi import APIRouter, Query
from datetime import datetime, timezone
import os

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/health/db")
async def db_health():
    """Check PostgreSQL / SQLite connectivity and return status."""
    from backend.audit import _use_postgres, _pg_connect, _db_path

    result: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pg_host_set": bool(os.getenv("PGHOST")),
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }

    if _use_postgres():
        result["backend"] = "postgresql"
        try:
            conn = _pg_connect()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            conn.close()
            result["status"] = "ok"
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"{type(e).__name__}: {e}"
    else:
        result["backend"] = "sqlite"
        result["path"] = _db_path()
        try:
            import sqlite3
            conn = sqlite3.connect(_db_path())
            conn.execute("SELECT 1")
            conn.close()
            result["status"] = "ok"
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"{type(e).__name__}: {e}"

    return result


@router.get("/health/db/diag")
async def db_diagnostics():
    """Query audit tables for diagnostic info."""
    from backend.audit import _use_postgres, _pg_connect

    if not _use_postgres():
        return {"error": "Not using PostgreSQL"}

    try:
        conn = _pg_connect()
        cur = conn.cursor()

        # Table row counts
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        tables = {}
        for (tname,) in cur.fetchall():
            cur.execute(f'SELECT COUNT(*) FROM "{tname}"')
            tables[tname] = cur.fetchone()[0]

        # Leagues in audit_results
        leagues = []
        if "audit_results" in tables:
            cur.execute("SELECT DISTINCT league FROM audit_results ORDER BY league")
            leagues = [r[0] for r in cur.fetchall()]

            # Columns in audit_results
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_results' ORDER BY ordinal_position")
            audit_cols = [r[0] for r in cur.fetchall()]

            # Confidence stats — column may not exist
            if "confidence" in audit_cols:
                cur.execute("SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM audit_results WHERE confidence IS NOT NULL")
                conf = cur.fetchone()
            else:
                conf = (None, None, None)
        else:
            conf = (None, None, None)

        # Sample recent audit
        recent = []
        audit_cols_list = audit_cols if "audit_results" in tables else []
        if "audit_results" in tables:
            # Use timestamp column (may be named created_at or timestamp)
            ts_col = "created_at" if "created_at" in audit_cols else "timestamp" if "timestamp" in audit_cols else None
            order = f"ORDER BY {ts_col} DESC" if ts_col else ""
            cur.execute(f"SELECT * FROM audit_results {order} LIMIT 3")
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                recent.append(dict(zip(cols, [str(v) if v is not None else None for v in row])))

        cur.close()
        conn.close()

        return {
            "tables": tables,
            "leagues": leagues,
            "audit_columns": audit_cols_list,
            "confidence": {"avg": conf[0], "min": conf[1], "max": conf[2]},
            "recent_audits": recent,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@router.get("/health/safe-status")
async def safe_status():
    """Return SAFE circuit breaker state and reactivation metrics.

    Reference: REGRAS #043 — circuit breaker SAFE.
    """
    from backend.services.ev_classification import SAFE_CIRCUIT_BREAKER_ENABLED
    from backend.services.backtesting import evaluate_safe_reactivation, run_backtest

    try:
        reactivation = evaluate_safe_reactivation()
        recent = run_backtest(days=7)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "circuit_breaker_enabled": True}

    return {
        "circuit_breaker_enabled": SAFE_CIRCUIT_BREAKER_ENABLED,
        "reactivation": reactivation,
        "recent_metrics": {
            "brier": recent.get("brier"),
            "lambda_error": (recent.get("lambda_error") or {}).get("mean_error"),
            "hit_rate": (recent.get("hit_rate") or {}).get("overall"),
            "n_picks": recent.get("n_picks", 0),
            "period_days": 7,
        },
        "deflations_active": {
            "lambda_ou": 0.85,
            "lambda_btts": 0.80,
            "corners_reduction": 0.20,
        },
        "reference": "REGRAS #043",
    }


@router.get("/health/calibration-params")
async def calibration_params():
    """Return all current calibrable parameters.

    Reference: CLAUDE.md section 'Parâmetros Calibráveis'.
    """
    from backend.modeling.lambda_calculator import PESOS_LAMBDA, LAMBDA_MIN, LAMBDA_MAX
    from backend.services.ev_classification import (
        DEFAULT_THRESHOLDS, NEUTRO_QUALIFICADO_THRESHOLDS, SAFE_CIRCUIT_BREAKER_ENABLED
    )

    return {
        "lambda": {
            "pesos": PESOS_LAMBDA,
            "limits": {"min": LAMBDA_MIN, "max": LAMBDA_MAX},
        },
        "btts_fusion": {
            "weights_3_sources": {"footystats": 0.40, "poisson": 0.30, "team_avg": 0.30},
            "weights_2_sources": {"source1": 0.60, "source2": 0.40},
            "note": "Fixed in fixtures_service.py — need per-league backtesting",
        },
        "corners": {
            "direct_weight": 0.60,
            "cross_weight": 0.30,
            "league_weight": 0.10,
            "blend_footystats": 0.60,
            "blend_poisson": 0.40,
            "under_margin": 0.06,
            "note": "Fixed in corners_engine.py — need per-league backtesting",
        },
        "xg_blend": {
            "lambda_weight": 0.70,
            "xg_weight": 0.30,
            "note": "Fixed in fixtures_service.py",
        },
        "thresholds": DEFAULT_THRESHOLDS,
        "neutro_qualificado": NEUTRO_QUALIFICADO_THRESHOLDS,
        "circuit_breaker": SAFE_CIRCUIT_BREAKER_ENABLED,
        "deflations": {
            "lambda_ou": 0.85,
            "lambda_btts": 0.80,
            "corners": -0.20,
            "reference": "#043 — remove when criteria met",
        },
    }


@router.get("/health/diag")
async def diagnostics(league: str = Query("premier-league")):
    """Diagnostic endpoint to debug FootyStats API integration."""
    from backend.config.leagues_config import get_league_config
    from backend.services.footstats_client import FootyStatsClient

    result: dict = {
        "league_input": league,
        "api_key_set": bool(os.getenv("FOOTYSTATS_API_KEY")),
        "api_key_preview": (os.getenv("FOOTYSTATS_API_KEY", ""))[:6] + "...",
    }

    config = get_league_config(league)
    result["league_config"] = config

    if not config:
        result["error"] = "League config not found"
        return result

    try:
        fs = FootyStatsClient()
        # Step 1: resolve season
        season_id = fs.resolve_season_id(config["country"], config["name"], alt_names=config.get("alt_names"))
        result["season_id"] = season_id

        if not season_id:
            # Debug: check league list
            leagues_data = fs.get_league_list(chosen_only=False)
            result["league_list_success"] = leagues_data.get("success")
            result["league_list_count"] = len(leagues_data.get("data", []))
            result["error"] = "Could not resolve season_id"
            return result

        # Step 2: get matches
        matches_data = fs.get_league_matches(season_id)
        result["matches_success"] = matches_data.get("success")
        result["matches_count"] = len(matches_data.get("data", []))

        if matches_data.get("data"):
            m = matches_data["data"][0]
            result["sample_match"] = {
                "home_name": m.get("home_name"),
                "away_name": m.get("away_name"),
                "date_unix": m.get("date_unix"),
                "status": m.get("status"),
            }
    except Exception as e:
        result["exception"] = f"{type(e).__name__}: {e}"

    return result
