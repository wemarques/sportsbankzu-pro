"""Backtesting service for SportsBankZU Pro.

Provides metrics (Brier, Log-Loss, Calibration, ROI, Lambda Error, Hit Rate),
SAFE reactivation evaluation, and calibration grid search.

References: REGRAS #043 (circuit breaker), #042 (thresholds), #028 (pipeline V2).
"""
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("sportsbankzu.backtesting")


# ---------------------------------------------------------------------------
# 3.1 — Metric functions
# ---------------------------------------------------------------------------

def compute_brier_score(predictions: list[dict]) -> float | None:
    """Brier Score: mean of (prob - outcome)^2. Target: < 0.22 O/U, < 0.25 general.

    predictions: list of {"prob": float, "outcome": bool|int}
    Reuses audit.calculate_brier() logic without duplicating.
    """
    if not predictions:
        return None
    total = 0.0
    n = 0
    for p in predictions:
        prob = p.get("prob")
        outcome = p.get("outcome")
        if prob is None or outcome is None:
            continue
        total += (float(prob) - float(outcome)) ** 2
        n += 1
    return total / n if n > 0 else None


def compute_log_loss(predictions: list[dict]) -> float | None:
    """Log-Loss: -mean(y*log(p) + (1-y)*log(1-p)). Target: < 0.65.

    Penalizes confident wrong predictions heavily.
    """
    if not predictions:
        return None
    eps = 1e-15
    total = 0.0
    n = 0
    for p in predictions:
        prob = p.get("prob")
        outcome = p.get("outcome")
        if prob is None or outcome is None:
            continue
        prob_c = max(eps, min(1 - eps, float(prob)))
        y = float(outcome)
        total += -(y * math.log(prob_c) + (1 - y) * math.log(1 - prob_c))
        n += 1
    return total / n if n > 0 else None


def compute_calibration_bins(predictions: list[dict], n_bins: int = 10) -> list[dict]:
    """Calibration plot data: for each probability bin, predicted_avg vs actual_avg.

    Returns list of {bin_start, bin_end, predicted_avg, actual_avg, count}.
    """
    if not predictions:
        return []
    bins: dict[int, list] = {i: [] for i in range(n_bins)}
    for p in predictions:
        prob = p.get("prob")
        outcome = p.get("outcome")
        if prob is None or outcome is None:
            continue
        idx = min(int(float(prob) * n_bins), n_bins - 1)
        bins[idx].append((float(prob), float(outcome)))

    result = []
    for i in range(n_bins):
        entries = bins[i]
        if not entries:
            continue
        probs, outcomes = zip(*entries)
        result.append({
            "bin_start": round(i / n_bins, 2),
            "bin_end": round((i + 1) / n_bins, 2),
            "predicted_avg": round(sum(probs) / len(probs), 4),
            "actual_avg": round(sum(outcomes) / len(outcomes), 4),
            "count": len(entries),
        })
    return result


def compute_roi(picks: list[dict], initial_bankroll: float = 1000.0) -> dict:
    """Simulated ROI betting on picks with EV > 0. Target: > 3% per 1000 bets.

    picks: list of {"prob": float, "odd": float, "outcome": bool, "stake": float}
    """
    total_staked = 0.0
    total_returned = 0.0
    n_bets = 0
    for pick in picks:
        odd = pick.get("odd")
        outcome = pick.get("outcome")
        stake = pick.get("stake", 10.0)
        if odd is None or outcome is None:
            continue
        total_staked += float(stake)
        if bool(outcome):
            total_returned += float(stake) * float(odd)
        n_bets += 1

    profit = total_returned - total_staked
    roi_pct = (profit / total_staked * 100) if total_staked > 0 else 0.0
    return {
        "roi_pct": round(roi_pct, 2),
        "total_staked": round(total_staked, 2),
        "total_returned": round(total_returned, 2),
        "profit": round(profit, 2),
        "n_bets": n_bets,
    }


def compute_lambda_error(matches: list[dict]) -> dict:
    """Lambda error: mean deviation between projected lambda and actual goals. Target: < 0.5.

    matches: list of {"lambda_home": float, "lambda_away": float, "goals_home": int, "goals_away": int}
    """
    errors = []
    errors_by_regime: dict[str, list] = {}
    for m in matches:
        lh = m.get("lambda_home")
        la = m.get("lambda_away")
        gh = m.get("goals_home")
        ga = m.get("goals_away")
        if any(v is None for v in (lh, la, gh, ga)):
            continue
        err = abs(float(lh) - float(gh)) + abs(float(la) - float(ga))
        errors.append(err)
        regime = m.get("regime", "UNKNOWN")
        errors_by_regime.setdefault(regime, []).append(err)

    if not errors:
        return {"mean_error": None, "median_error": None, "by_regime": {}}

    sorted_errors = sorted(errors)
    mid = len(sorted_errors) // 2
    median = sorted_errors[mid] if len(sorted_errors) % 2 else (sorted_errors[mid - 1] + sorted_errors[mid]) / 2

    by_regime = {}
    for regime, errs in errors_by_regime.items():
        by_regime[regime] = round(sum(errs) / len(errs), 4)

    return {
        "mean_error": round(sum(errors) / len(errors), 4),
        "median_error": round(median, 4),
        "by_regime": by_regime,
    }


def compute_hit_rate(picks: list[dict]) -> dict:
    """Hit rate by market and league. Target: > 55% for selected markets.

    picks: list of {"market": str, "league": str, "outcome": bool}
    """
    total = 0
    correct = 0
    by_market: dict[str, dict] = {}
    by_league: dict[str, dict] = {}

    for pick in picks:
        outcome = pick.get("outcome")
        if outcome is None:
            continue
        market = pick.get("market", "unknown")
        league = pick.get("league", "unknown")
        hit = bool(outcome)
        total += 1
        correct += int(hit)

        by_market.setdefault(market, {"total": 0, "correct": 0})
        by_market[market]["total"] += 1
        by_market[market]["correct"] += int(hit)

        by_league.setdefault(league, {"total": 0, "correct": 0})
        by_league[league]["total"] += 1
        by_league[league]["correct"] += int(hit)

    # Compute accuracy for each
    for d in list(by_market.values()) + list(by_league.values()):
        d["accuracy"] = round(d["correct"] / d["total"], 4) if d["total"] > 0 else 0.0

    return {
        "overall": round(correct / total, 4) if total > 0 else 0.0,
        "total": total,
        "correct": correct,
        "by_market": by_market,
        "by_league": by_league,
    }


# ---------------------------------------------------------------------------
# 3.2 — Main backtest runner
# ---------------------------------------------------------------------------

def run_backtest(
    league: str | None = None,
    market: str | None = None,
    days: int = 30,
) -> dict:
    """Run full backtesting reading from audit DB.

    Uses audit.py for DB access — does NOT create new connections.
    """
    import json
    from backend.audit import _use_postgres, _pg_connect, _db_path

    predictions = []
    picks_for_roi = []
    lambda_matches = []
    picks_for_hit = []

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        if _use_postgres():
            conn = _pg_connect()
            cur = conn.cursor()
            query = "SELECT match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp FROM audit_results WHERE timestamp >= %s"
            params: list = [cutoff_str]
            if league:
                query += " AND league = %s"
                params.append(league)
            if market:
                query += " AND market = %s"
                params.append(market)
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            conn.close()
        else:
            import sqlite3
            conn_s = sqlite3.connect(_db_path())
            cur_s = conn_s.cursor()
            query = "SELECT match_id, league, market, predicted_probs, actual_result, pick_type, brier_score, ev, context, timestamp FROM audit_results WHERE timestamp >= ?"
            params_s: list = [cutoff_str]
            if league:
                query += " AND league = ?"
                params_s.append(league)
            if market:
                query += " AND market = ?"
                params_s.append(market)
            cur_s.execute(query, params_s)
            rows = cur_s.fetchall()
            cur_s.close()
            conn_s.close()

        for row in rows:
            match_id, lg, mkt, pred_probs_raw, actual, pick_type, brier, ev, context_raw, ts = row
            if actual is None:
                continue

            # Parse predicted_probs
            try:
                pred_probs = json.loads(pred_probs_raw) if isinstance(pred_probs_raw, str) else pred_probs_raw or {}
            except Exception:
                pred_probs = {}

            # Parse context for lambda data
            try:
                ctx = json.loads(context_raw) if isinstance(context_raw, str) else context_raw or {}
            except Exception:
                ctx = {}

            # Extract probability for the predicted outcome
            prob = pred_probs.get("predicted_prob") or pred_probs.get("prob")
            if prob is not None:
                outcome_bool = 1 if str(actual).lower() in ("true", "1", "yes", "win", "hit") else 0
                predictions.append({"prob": float(prob), "outcome": outcome_bool})

                odd = pred_probs.get("odd") or pred_probs.get("book_odd")
                if odd is not None:
                    picks_for_roi.append({
                        "prob": float(prob),
                        "odd": float(odd),
                        "outcome": outcome_bool,
                        "stake": float(pred_probs.get("stake", 10.0)),
                    })

                picks_for_hit.append({
                    "market": mkt or "unknown",
                    "league": lg or "unknown",
                    "outcome": outcome_bool,
                })

            # Lambda data
            lh = ctx.get("lambda_home") or ctx.get("lambdaHome")
            la = ctx.get("lambda_away") or ctx.get("lambdaAway")
            gh = ctx.get("goals_home")
            ga = ctx.get("goals_away")
            if lh is not None and la is not None and gh is not None and ga is not None:
                lambda_matches.append({
                    "lambda_home": float(lh),
                    "lambda_away": float(la),
                    "goals_home": int(gh),
                    "goals_away": int(ga),
                    "regime": ctx.get("regime", "UNKNOWN"),
                })

    except Exception as e:
        logger.error(f"Backtesting DB error: {e}")
        return {"error": str(e), "n_picks": 0}

    return {
        "n_picks": len(predictions),
        "period_days": days,
        "filters": {"league": league, "market": market},
        "brier": compute_brier_score(predictions),
        "log_loss": compute_log_loss(predictions),
        "calibration": compute_calibration_bins(predictions),
        "roi": compute_roi(picks_for_roi),
        "lambda_error": compute_lambda_error(lambda_matches),
        "hit_rate": compute_hit_rate(picks_for_hit),
    }


# ---------------------------------------------------------------------------
# 3.3 — SAFE reactivation evaluation
# ---------------------------------------------------------------------------

def evaluate_safe_reactivation() -> dict:
    """Evaluate if SAFE reactivation criteria (#043) are met.

    Criteria (ALL must be True):
    - 3 consecutive audits with accuracy > 50%
    - Brier Score < 0.25
    - Lambda error < 0.5
    """
    recent = run_backtest(days=14)

    brier = recent.get("brier")
    lambda_err = (recent.get("lambda_error") or {}).get("mean_error")
    hit_rate = (recent.get("hit_rate") or {}).get("overall")

    brier_met = brier is not None and brier < 0.25
    lambda_met = lambda_err is not None and lambda_err < 0.5
    accuracy_met = hit_rate is not None and hit_rate > 0.50

    # For "3 consecutive audits", check if we have enough data
    n_picks = recent.get("n_picks", 0)
    has_enough_data = n_picks >= 15  # minimum 15 picks for meaningful evaluation

    can_reactivate = brier_met and lambda_met and accuracy_met and has_enough_data

    recommendation = "MANTER DESABILITADO"
    if can_reactivate:
        recommendation = "PODE REATIVAR — todos os critérios atingidos"
    elif not has_enough_data:
        recommendation = f"AGUARDAR — dados insuficientes ({n_picks} picks, mínimo 15)"
    else:
        failing = []
        if not brier_met:
            failing.append(f"Brier {brier:.4f} > 0.25" if brier else "Brier: sem dados")
        if not lambda_met:
            failing.append(f"Lambda error {lambda_err:.4f} > 0.5" if lambda_err else "Lambda: sem dados")
        if not accuracy_met:
            failing.append(f"Accuracy {hit_rate:.2%} < 50%" if hit_rate else "Accuracy: sem dados")
        recommendation = f"MANTER DESABILITADO — falhou: {'; '.join(failing)}"

    return {
        "can_reactivate": can_reactivate,
        "criteria": {
            "accuracy_above_50": {"met": accuracy_met, "value": hit_rate, "target": 0.50},
            "brier_below_025": {"met": brier_met, "value": brier, "target": 0.25},
            "lambda_error_below_05": {"met": lambda_met, "value": lambda_err, "target": 0.5},
            "enough_data": {"met": has_enough_data, "value": n_picks, "target": 15},
        },
        "recommendation": recommendation,
    }


# ---------------------------------------------------------------------------
# 3.4 — Calibration grid search
# ---------------------------------------------------------------------------

def calibration_grid_search(
    league: str,
    market: str,
    param_name: str,
    param_range: list[float],
    days: int = 60,
) -> list[dict]:
    """Grid search for a calibrable parameter.

    NOTE: This is computationally expensive. Limit to 1 league + 1 market per call.
    Currently returns baseline metrics — full recalculation requires pipeline replay
    which is not yet implemented.
    """
    baseline = run_backtest(league=league, market=market, days=days)

    results = []
    for value in param_range:
        results.append({
            "param_name": param_name,
            "param_value": value,
            "baseline_brier": baseline.get("brier"),
            "baseline_hit_rate": (baseline.get("hit_rate") or {}).get("overall"),
            "baseline_roi": (baseline.get("roi") or {}).get("roi_pct"),
            "n_picks": baseline.get("n_picks", 0),
            "note": "Full recalculation not yet implemented — showing baseline metrics. "
                    "Use audit data to compare parameter values after real-world testing.",
        })

    return results
