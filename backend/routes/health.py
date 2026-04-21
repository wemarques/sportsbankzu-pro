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
        recent = run_backtest(days=30)  # #119d — expanded from 7 to match SAFE reactivation window
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
            "period_days": 30,
        },
        "deflation_mode": "per_league",
        "shadow_mode": {
            "enabled": True,  # #129c
            "description": "SAFE computed internally but displayed as NQ. Logged for accuracy tracking.",
            "reactivation": "Set SAFE_SHADOW_MODE=false when shadow accuracy > 50% (N >= 50)",
        },
        "note": "Deflation is now per-league from calibration DB (#052). Use GET /api/backtesting/calibration-status for details.",
        "reference": "REGRAS #052, #129c (shadow mode)",
    }


@router.get("/health/shadow-safe")
async def shadow_safe_status():
    """Shadow SAFE accuracy tracking (#129c/#129d).

    Queries audit_results for picks with SAFE_CIRCUIT_BREAKER in context.reason_codes.
    Returns shadow-specific accuracy, not overall stats.
    """
    import json as _json
    from datetime import datetime, timedelta, timezone

    MIN_SHADOW = 50
    MIN_ACCURACY = 0.50

    try:
        from backend.audit import _use_postgres, _pg_connect, _db_path

        cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        rows = []

        if _use_postgres():
            conn = _pg_connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT actual_result, context FROM audit_results WHERE timestamp >= %s AND context LIKE %s",
                [cutoff, "%SAFE_CIRCUIT_BREAKER%"],
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
        else:
            import sqlite3
            conn_s = sqlite3.connect(_db_path())
            cur_s = conn_s.cursor()
            cur_s.execute(
                "SELECT actual_result, context FROM audit_results WHERE timestamp >= ? AND context LIKE ?",
                [cutoff, "%SAFE_CIRCUIT_BREAKER%"],
            )
            rows = cur_s.fetchall()
            cur_s.close()
            conn_s.close()

        total_shadow = len(rows)
        evaluated = 0
        hits = 0
        for actual, ctx_raw in rows:
            if actual is not None:
                evaluated += 1
                if str(actual).lower() in ("true", "1", "yes", "win", "hit"):
                    hits += 1

        accuracy = round(hits / evaluated, 4) if evaluated > 0 else None
        ready = evaluated >= MIN_SHADOW and accuracy is not None and accuracy > MIN_ACCURACY

        return {
            "shadow_mode_enabled": True,
            "total_shadow_picks": total_shadow,
            "evaluated": evaluated,
            "hits": hits,
            "accuracy": accuracy,
            "ready_to_activate": ready,
            "threshold": {"min_picks": MIN_SHADOW, "min_accuracy": MIN_ACCURACY},
            "activation": "Set SAFE_SHADOW_MODE=false when ready_to_activate=true",
            "email": "wpjct991@gmail.com",
        }
    except Exception as e:
        return {"error": str(e), "total_shadow_picks": None}


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
        "deflation_mode": "per_league",
        "deflation_note": "Uniform deflation replaced by per-league calibration (#052). Use GET /api/backtesting/calibration-status.",
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


@router.get("/health/reliability")
async def reliability_metrics():
    """Princeton AI Agent Reliability framework — 4 dimensions (#101)."""
    from backend.services.reliability_tracker import get_stats
    from backend import audit as audit_db

    stats = get_stats(days=30)

    # --- Predictability: from accumulated Brier snapshot (#159) ---
    pred_data: dict = {"brier_score": None, "n_total": 0, "suficiente": False}
    try:
        from backend.services.brier_service import calculate_snapshot
        snapshot = calculate_snapshot()
        if snapshot:
            pred_data["brier_score"] = snapshot.get("brier_model")
            pred_data["n_total"] = snapshot.get("total_picks", 0)
            pred_data["suficiente"] = pred_data["n_total"] >= 20
    except Exception:
        # Fallback to last cron batch if brier_service unavailable
        try:
            recent = audit_db.get_recent_audit_results(days=7, limit=1)
            if recent:
                import json as _json
                ctx = recent[0].get("data") or recent[0].get("context") or {}
                if isinstance(ctx, str):
                    ctx = _json.loads(ctx)
                pred_data["brier_score"] = ctx.get("avg_brier_score")
                pred_data["n_total"] = ctx.get("total_matches", 0)
                pred_data["suficiente"] = pred_data["n_total"] >= 20
        except Exception:
            pass

    # --- Safety ---
    safety = {
        "complementares_bloqueados": stats.get("complementares_bloqueados", 0),
        "acoes_bloqueadas": stats.get("acoes_bloqueadas", 0),
        "mistral_contradicoes": stats.get("mistral_contradicoes", 0),
        "compliance_rate": 1.0,
    }

    # --- Robustness ---
    af_ok = stats.get("api_football_ok", 0)
    af_fail = stats.get("api_football_fail", 0)
    fs_ok = stats.get("footystats_ok", 0)
    fs_fail = stats.get("footystats_fail", 0)
    mi_ok = stats.get("mistral_ok", 0)
    mi_fail = stats.get("mistral_fail", 0)
    robustness = {
        "api_football_success_rate": round(af_ok / max(af_ok + af_fail, 1), 3),
        "footystats_success_rate": round(fs_ok / max(fs_ok + fs_fail, 1), 3),
        "mistral_success_rate": round(mi_ok / max(mi_ok + mi_fail, 1), 3),
        "fallbacks_ativados": stats.get("fallbacks_ativados", 0),
    }

    # --- Consistency ---
    consistency = {
        "lambda_duration_avg_ms": stats.get("avg_duration_ms"),
        "lambda_duration_cv": stats.get("cv_duration"),
        "lambda_duration_p95_ms": stats.get("p95_duration_ms"),
        "picks_por_jogo_avg": stats.get("picks_por_jogo_avg"),
        "picks_por_jogo_cv": stats.get("picks_por_jogo_cv"),
    }

    return {
        "framework": "Princeton AI Agent Reliability (Rabanser et al., 2026)",
        "predictability": pred_data,
        "safety": safety,
        "robustness": robustness,
        "consistency": consistency,
        "defesas_ativas": {
            "anti_alucinacao_mistral": 6,
            "circuit_breaker_safe": True,
            "min_n_brier": 20,
            "contrato_mistral_082": True,
        },
        "tracker_started_at": stats.get("started_at"),
    }


@router.get("/metrics/lambda-error")
async def get_lambda_error(days: int = Query(30), group_by: str = Query("")):
    """Lambda Erro Medio — canonical measurement (#128i).

    Args:
        group_by: "" for global only, "league" to include per-league breakdown with xg_blend_weight.
    """
    try:
        from backend.services.backtesting import measure_lambda_error
        result = measure_lambda_error(days=days)

        if group_by == "league" and result.get("lambda_error_mean") is not None:
            # Enrich by_league with xg_blend_weight from calibration DB
            from backend.services.backtesting import run_backtest
            bt = run_backtest(days=days)
            by_league = (bt.get("lambda_error") or {}).get("by_league", {})

            try:
                from backend.modeling.lambda_calculator import get_lambda_corrections
                for league_id, info in by_league.items():
                    corr = get_lambda_corrections(league_id)
                    xg_w = corr.get("xg_blend_weight", {})
                    info["xg_blend_weight"] = float(xg_w.get("value", 0)) if isinstance(xg_w, dict) else float(xg_w or 0)
            except Exception:
                pass

            result["by_league"] = by_league

        return result
    except Exception as e:
        return {"error": str(e), "lambda_error_mean": None}


@router.get("/metrics/brier")
async def get_brier_metrics():
    """Current Brier snapshot — calculates on demand."""
    try:
        from backend.services.brier_service import calculate_snapshot
        snap = calculate_snapshot()
        if not snap:
            return {"error": "No data", "total_picks": 0}
        return snap
    except Exception as e:
        return {"error": str(e), "total_picks": 0}


@router.get("/metrics/brier/history")
async def get_brier_history(limit: int = 30):
    """Brier trend over time."""
    try:
        from backend.services.brier_service import get_history
        h = get_history(limit)
        return {"history": h, "count": len(h)}
    except Exception as e:
        return {"history": [], "count": 0, "error": str(e)}
