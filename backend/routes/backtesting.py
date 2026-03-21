"""Backtesting API routes for SportsBankZU Pro.

Reference: REGRAS #050 — backtesting, calibration, SAFE monitoring.
Reference: REGRAS #051 — lambda error null fix, by-league/by-market reports.
Reference: REGRAS #052 — per-league calibration.
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone, timedelta

router = APIRouter(tags=["backtesting"])


@router.get("/backtesting/run")
async def run_backtesting(
    league: Optional[str] = Query(None, description="Specific league or None for all"),
    market: Optional[str] = Query(None, description="Specific market or None for all"),
    days: int = Query(30, ge=7, le=180, description="Period in days"),
):
    """Run backtesting and return full metrics."""
    from backend.services.backtesting import run_backtest
    return run_backtest(league=league, market=market, days=days)


@router.get("/backtesting/safe-reactivation")
async def check_safe_reactivation():
    """Evaluate SAFE reactivation criteria (#043)."""
    from backend.services.backtesting import evaluate_safe_reactivation
    return evaluate_safe_reactivation()


@router.get("/backtesting/calibration-search")
async def calibration_search(
    league: str = Query(..., description="League to calibrate"),
    market: str = Query(..., description="Market to calibrate"),
    param: str = Query(..., description="Parameter (e.g. lambda_weight_season)"),
):
    """Grid search for a calibrable parameter for a league/market."""
    from backend.services.backtesting import calibration_grid_search

    PARAM_RANGES = {
        "lambda_weight_season": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75],
        "btts_weight_footystats": [0.20, 0.30, 0.40, 0.50, 0.60],
        "btts_weight_poisson": [0.20, 0.30, 0.40, 0.50],
        "corners_weight_direct": [0.40, 0.50, 0.60, 0.70, 0.80],
        "xg_blend_lambda": [0.50, 0.60, 0.70, 0.80],
        "safe_prob_1x2": [0.55, 0.58, 0.60, 0.62, 0.65, 0.68],
        "safe_prob_ou": [0.68, 0.70, 0.72, 0.75, 0.78, 0.80],
        "safe_prob_btts": [0.68, 0.70, 0.72, 0.75, 0.78],
        "safe_prob_corners": [0.65, 0.68, 0.70, 0.72, 0.75],
        "safe_prob_cards": [0.68, 0.70, 0.72, 0.75, 0.78],
    }

    param_range = PARAM_RANGES.get(param)
    if not param_range:
        return {"error": f"Parameter '{param}' not recognized. Valid: {list(PARAM_RANGES.keys())}"}

    return calibration_grid_search(league=league, market=market, param_name=param, param_range=param_range)


@router.post("/backtesting/backfill-lambda")
async def backfill_lambda_data():
    """Backfill lambda data into existing audit picks that lack it.

    Reads sibling picks of the same match and copies lambda/goals data.

    Reference: REGRAS #051
    """
    import json
    from backend.audit import _use_postgres, _pg_connect

    updated = 0
    skipped = 0
    errors = []

    try:
        if not _use_postgres():
            return {"error": "Backfill only supported with PostgreSQL", "updated": 0}

        conn = _pg_connect()
        cur = conn.cursor()
        # Find picks missing lambda data in context
        cur.execute("""
            SELECT match_id, context
            FROM audit_results
            WHERE context IS NOT NULL
            AND context NOT LIKE '%lambdaHome%'
            AND context NOT LIKE '%lambda_home%'
            AND actual_result IS NOT NULL
        """)
        rows = cur.fetchall()

        for match_id, ctx_raw in rows:
            try:
                ctx = json.loads(ctx_raw) if isinstance(ctx_raw, str) else ctx_raw or {}

                # match_id may contain market suffix — extract base id
                base_id = match_id.split(":")[0] if ":" in match_id else match_id

                # Look for a sibling pick of the same match that has lambda data
                cur.execute("""
                    SELECT context FROM audit_results
                    WHERE match_id LIKE %s
                    AND context LIKE '%%lambdaHome%%'
                    LIMIT 1
                """, (f"{base_id}%",))

                donor_row = cur.fetchone()
                if donor_row:
                    donor_ctx = json.loads(donor_row[0]) if isinstance(donor_row[0], str) else donor_row[0] or {}
                    for key in ["lambdaHome", "lambdaAway", "lambdaTotal",
                                "goals_home", "goals_away", "total_goals", "total_corners"]:
                        if key in donor_ctx and key not in ctx:
                            ctx[key] = donor_ctx[key]

                    cur.execute(
                        "UPDATE audit_results SET context = %s WHERE match_id = %s",
                        (json.dumps(ctx), match_id)
                    )
                    updated += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append(f"{match_id}: {str(e)[:80]}")

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        return {"error": str(e), "updated": updated, "skipped": skipped}

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:10],
        "note": "Lambda data backfilled from sibling picks. New picks will have data automatically."
    }


@router.get("/backtesting/by-league")
async def backtest_by_league(
    days: int = Query(30, ge=7, le=180),
):
    """Run backtesting per league, returning a comparison table.

    Identifies which leagues need calibration most urgently.
    """
    from backend.services.backtesting import run_backtest
    from backend.audit import _use_postgres, _pg_connect

    leagues = []
    try:
        if _use_postgres():
            conn = _pg_connect()
            cur = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            cur.execute(
                "SELECT DISTINCT league FROM audit_results WHERE timestamp >= %s AND actual_result IS NOT NULL",
                (cutoff,)
            )
            leagues = [row[0] for row in cur.fetchall() if row[0]]
            cur.close()
            conn.close()
    except Exception:
        pass

    if not leagues:
        return {"error": "No leagues with picks found", "leagues": []}

    results = []
    for lg in sorted(leagues):
        bt = run_backtest(league=lg, days=days)
        le = bt.get("lambda_error") or {}
        hr = bt.get("hit_rate") or {}
        roi = bt.get("roi") or {}
        results.append({
            "league": lg,
            "n_picks": bt.get("n_picks", 0),
            "brier": bt.get("brier"),
            "log_loss": bt.get("log_loss"),
            "hit_rate": hr.get("overall"),
            "lambda_error_mean": le.get("mean_error"),
            "roi_pct": roi.get("roi_pct"),
            "needs_calibration": (
                (bt.get("brier") or 1) > 0.25 or
                (le.get("mean_error") or 1) > 0.5 or
                (hr.get("overall") or 0) < 0.50
            ),
        })

    # Sort: worst leagues first (highest brier)
    results.sort(key=lambda x: -(x.get("brier") or 0))

    return {
        "period_days": days,
        "total_leagues": len(results),
        "leagues_needing_calibration": sum(1 for r in results if r.get("needs_calibration")),
        "results": results,
    }


@router.get("/backtesting/by-market")
async def backtest_by_market(
    league: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=180),
):
    """Run backtesting per market type, optionally filtered by league.

    Shows which markets need calibration within a league.
    """
    from backend.services.backtesting import run_backtest
    from backend.audit import _use_postgres, _pg_connect

    markets = []
    try:
        if _use_postgres():
            conn = _pg_connect()
            cur = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query = "SELECT DISTINCT market FROM audit_results WHERE timestamp >= %s AND actual_result IS NOT NULL"
            params = [cutoff]
            if league:
                query += " AND league = %s"
                params.append(league)
            cur.execute(query, params)
            markets = [row[0] for row in cur.fetchall() if row[0]]
            cur.close()
            conn.close()
    except Exception:
        pass

    if not markets:
        return {"error": "No markets with picks found", "markets": []}

    results = []
    for mkt in sorted(markets):
        bt = run_backtest(league=league, market=mkt, days=days)
        hr = bt.get("hit_rate") or {}
        roi = bt.get("roi") or {}
        results.append({
            "market": mkt,
            "league": league or "ALL",
            "n_picks": bt.get("n_picks", 0),
            "brier": bt.get("brier"),
            "hit_rate": hr.get("overall"),
            "roi_pct": roi.get("roi_pct"),
        })

    results.sort(key=lambda x: -(x.get("brier") or 0))

    return {
        "period_days": days,
        "league": league or "ALL",
        "total_markets": len(results),
        "results": results,
    }


@router.post("/backtesting/calibrate")
async def run_calibration(
    league: Optional[str] = Query(None, description="Liga específica ou None para todas"),
    n_seasons: int = Query(6, ge=2, le=8, description="Número de temporadas históricas"),
):
    """Run per-league calibration using historical match data.

    Fetches N seasons from FootyStats, runs grid search for optimal
    lambda deflation, BTTS deflation, corner factor, and lambda weights.
    Stores results in corrections DB.

    WARNING: This is slow — ~30s per league, ~15min for all leagues.
    Reference: REGRAS #052
    """
    from backend.services.league_calibrator import calibrate_league, calibrate_all_leagues, save_calibration

    if league:
        result = calibrate_league(league, n_seasons=n_seasons)
        if result.get("status") == "CALIBRATED" and result.get("params"):
            save_calibration(league, result["params"])
        return result
    else:
        return calibrate_all_leagues(n_seasons=n_seasons)


@router.post("/backtesting/recalibrate-all")
async def recalibrate_all(
    n_seasons: int = Query(6, ge=2, le=8, description="Número de temporadas históricas"),
    clear_previous: bool = Query(False, description="Limpar calibrações anteriores antes"),
):
    """Recalibrate all leagues with expanded grid and bias detection.

    After calibrating, checks for uniform bias (>70% of leagues hitting the same
    grid boundary), which indicates a systematic formula issue rather than
    per-league variation.

    Reference: REGRAS #053
    """
    from backend.services.league_calibrator import calibrate_league, save_calibration
    from backend.config.leagues_config import LEAGUES_CONFIG

    if clear_previous:
        try:
            from backend.audit import _use_postgres, _pg_connect
            if _use_postgres():
                conn = _pg_connect()
                cur = conn.cursor()
                cur.execute("DELETE FROM audit_corrections WHERE correction_type = 'calibration'")
                conn.commit()
                cur.close()
                conn.close()
        except Exception:
            pass

    results = {}
    for cfg in LEAGUES_CONFIG:
        league_id = cfg["id"]
        try:
            result = calibrate_league(league_id, n_seasons=n_seasons)
            if result.get("status") == "CALIBRATED" and result.get("params"):
                save_calibration(league_id, result["params"])
            results[league_id] = result
        except Exception as e:
            results[league_id] = {"league": league_id, "status": "ERROR", "error": str(e)}

    # Bias detection: check if >70% of leagues hit the same grid boundary
    from backend.services.league_calibrator import DEFLATION_GRID

    calibrated = [r for r in results.values() if r.get("status") == "CALIBRATED"]
    n_calibrated = len(calibrated)
    bias_report = {"detected": False}

    if n_calibrated >= 5:
        defl_values = [r["params"]["lambda_deflation_ou"] for r in calibrated if r.get("params")]
        if defl_values:
            grid_min = min(DEFLATION_GRID)
            grid_max = max(DEFLATION_GRID)
            at_ceiling = sum(1 for v in defl_values if v >= grid_max)
            at_floor = sum(1 for v in defl_values if v <= grid_min)

            if at_ceiling / n_calibrated > 0.70:
                bias_report = {
                    "detected": True,
                    "direction": "underestimation",
                    "pct_at_ceiling": round(at_ceiling / n_calibrated * 100, 1),
                    "grid_max": grid_max,
                    "recommendation": "Lambda formula may still underestimate. Consider further grid expansion or formula adjustment.",
                }
            elif at_floor / n_calibrated > 0.70:
                bias_report = {
                    "detected": True,
                    "direction": "overestimation",
                    "pct_at_floor": round(at_floor / n_calibrated * 100, 1),
                    "grid_min": grid_min,
                    "recommendation": "Lambda formula may overestimate. Consider grid expansion or formula adjustment.",
                }

    return {
        "total_leagues": len(results),
        "calibrated": n_calibrated,
        "insufficient_data": sum(1 for r in results.values() if r.get("status") == "INSUFFICIENT_DATA"),
        "errors": sum(1 for r in results.values() if r.get("status") == "ERROR"),
        "bias_report": bias_report,
        "grid_range": {"min": min(DEFLATION_GRID), "max": max(DEFLATION_GRID)},
        "results": results,
    }


@router.get("/backtesting/calibration-status")
async def calibration_status():
    """Show current calibration status for all leagues.

    Reads corrections DB to show which leagues have been calibrated
    and their current per-league parameters.
    """
    from backend.config.leagues_config import LEAGUES_CONFIG
    from backend.modeling.lambda_calculator import get_lambda_corrections

    results = []
    for cfg in LEAGUES_CONFIG:
        league_id = cfg["id"]
        try:
            corrections = get_lambda_corrections(league_id)
            has_calibration = any(
                c.get("type") == "calibration"
                for c in corrections.values()
                if isinstance(c, dict)
            )
            # Read safe_enabled as float (1.0=true, 0.0=false)
            _safe_raw = corrections.get("safe_enabled", {}).get("value")
            if _safe_raw is not None:
                try:
                    _safe = float(_safe_raw) >= 1.0
                except (ValueError, TypeError):
                    _safe = str(_safe_raw).lower() in ("true", "1", "yes")
                safe_display = str(_safe).lower()
            else:
                safe_display = "false (default)"

            results.append({
                "league": league_id,
                "name": cfg["name"],
                "calibrated": has_calibration,
                # Deflations
                "lambda_ou": corrections.get("lambda_multiplier", {}).get("value", "1.0 (default)"),
                "btts": corrections.get("btts_multiplier", {}).get("value", "1.0 (default)"),
                "1x2": corrections.get("1x2_multiplier", {}).get("value", "1.0 (default)"),
                "corners": corrections.get("corner_multiplier", {}).get("value", "1.0 (default)"),
                "cards": corrections.get("cards_multiplier", {}).get("value", "1.0 (default)"),
                # xG and BTTS weights
                "xg_blend": corrections.get("xg_blend_weight", {}).get("value", "0.30 (default)"),
                "btts_w_fs": corrections.get("btts_weight_footystats", {}).get("value", "0.40 (default)"),
                "btts_w_po": corrections.get("btts_weight_poisson", {}).get("value", "0.30 (default)"),
                "btts_w_ta": corrections.get("btts_weight_team_avg", {}).get("value", "0.30 (default)"),
                # Thresholds
                "safe_prob_ou": corrections.get("safe_prob_ou", {}).get("value", "0.75 (default)"),
                "safe_prob_1x2": corrections.get("safe_prob_1x2", {}).get("value", "0.62 (default)"),
                "safe_prob_corners": corrections.get("safe_prob_corners", {}).get("value", "0.72 (default)"),
                "safe_prob_cards": corrections.get("safe_prob_cards", {}).get("value", "0.75 (default)"),
                "safe_enabled": safe_display,
                # Brier diagnostic
                "brier_over": corrections.get("brier_over_avg", {}).get("value"),
                "brier_1x2": corrections.get("brier_1x2_avg", {}).get("value"),
                "brier_corners": corrections.get("brier_corners_avg", {}).get("value"),
                "brier_cards": corrections.get("brier_cards_avg", {}).get("value"),
            })
        except Exception as e:
            results.append({"league": league_id, "name": cfg["name"], "error": str(e)})

    calibrated = sum(1 for r in results if r.get("calibrated"))
    return {
        "total_leagues": len(results),
        "calibrated": calibrated,
        "uncalibrated": len(results) - calibrated,
        "leagues": results,
    }
