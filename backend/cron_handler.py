"""
Handler para AWS EventBridge (CloudWatch Events).
Executa auditoria batch automatizada diariamente.

A Lambda principal (backend.main:handler) roda o FastAPI via Mangum.
Este handler eh invocado separadamente pelo EventBridge rule
e chama diretamente a logica de batch audit, sem precisar de HTTP.

Configuracao EventBridge:
  - Rule name: sportsbank-daily-audit
  - Schedule: cron(0 23 * * ? *)  -> 23:00 UTC = 20:00 BRT
  - Target: Lambda sportsbank-pro-backend
  - Input: {"source": "eventbridge", "action": "batch_audit", "date": "yesterday"}
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("sportsbankzu.cron")
logger.setLevel(logging.INFO)


def cron_handler(event, context):
    """
    Entry point for EventBridge-triggered events.
    Delegates to the appropriate action based on event payload.
    """
    logger.info(f"EventBridge triggered: {json.dumps(event)}")

    # Set env flag so audit logs know this is a cron execution
    os.environ["EVENTBRIDGE_TRIGGERED"] = "1"

    action = event.get("action", "batch_audit")
    date_filter = event.get("date", "yesterday")

    try:
        if action == "batch_audit":
            return _run_batch_audit(date_filter)
        elif action == "today_audit":
            # New rule: cron(45 2 * * ? *) → 02:45 UTC = 23:45 BRT
            return _run_batch_audit("today", before_time_brt="23:45")
        elif action == "retrain_calibrators":
            return _run_retrain_calibrators()
        elif action == "adjust_thresholds":
            return _run_threshold_adjustment()
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    except Exception as e:
        logger.error(f"Cron handler error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        os.environ.pop("EVENTBRIDGE_TRIGGERED", None)


def _run_batch_audit(date_filter: str, before_time_brt: str | None = None) -> dict:
    """Execute batch audit for all finished matches.

    Args:
        date_filter: 'today' | 'yesterday' | 'week'
        before_time_brt: Optional cutoff time in BRT (e.g. '23:45') — only include
            matches that finished before this time. Used by the today_audit action so
            that late European matches already completed are audited same-day.
    """
    from backend.routes.ai_analysis import (
        _get_all_finished_matches,
        _evaluate_pick_deterministic,
    )
    from backend.ai.mistral_auditor import MistralAuditor
    from backend import audit as audit_db

    label = f"date={date_filter}" + (f" before_brt={before_time_brt}" if before_time_brt else "")
    logger.info(f"Starting automated batch audit for {label}")

    finished_matches = _get_all_finished_matches(date_filter, before_time_brt=before_time_brt)

    if not finished_matches:
        from backend.audit import audit_logger
        msg = f"[CRON] {date_filter} — Nenhum jogo finalizado encontrado. Auditoria pulada."
        logger.info(msg)
        audit_logger.info(msg)
        return {
            "status": "success",
            "message": "Nenhum jogo finalizado encontrado.",
            "audited_matches": 0,
        }

    # Evaluate each match deterministically (same logic as the API endpoint)
    overall_correct = 0
    overall_total = 0
    safe_correct = 0
    safe_total = 0
    neutro_correct = 0
    neutro_total = 0
    market_stats = {}
    lambda_errors = []
    brier_scores = []
    ev_values = []
    match_results = []

    for m in finished_matches:
        home = m.get("homeTeam", "")
        away = m.get("awayTeam", "")
        league = m.get("leagueName", m.get("leagueId", ""))
        score = m.get("score") or {}
        stats = m.get("stats", {})
        mercados = m.get("mercados", [])

        home_goals = score.get("home", 0) if score else 0
        away_goals = score.get("away", 0) if score else 0

        if not score:
            home_goals = m.get("home_team_goal_count") or m.get("homeGoals") or 0
            away_goals = m.get("away_team_goal_count") or m.get("awayGoals") or 0
            try:
                home_goals = int(home_goals)
                away_goals = int(away_goals)
            except (ValueError, TypeError):
                home_goals, away_goals = 0, 0

        total_goals = home_goals + away_goals
        btts = home_goals > 0 and away_goals > 0
        if home_goals > away_goals:
            result_1x2 = "1"
        elif home_goals == away_goals:
            result_1x2 = "X"
        else:
            result_1x2 = "2"

        # Extract total corners for corner market evaluation
        home_corners = stats.get("homeCornersCount") or m.get("home_team_corner_count") or 0
        away_corners = stats.get("awayCornersCount") or m.get("away_team_corner_count") or 0
        try:
            home_corners = int(home_corners) if home_corners and int(home_corners) >= 0 else 0
            away_corners = int(away_corners) if away_corners and int(away_corners) >= 0 else 0
            total_corners = home_corners + away_corners
        except (ValueError, TypeError):
            total_corners = 0
        if any("ESCANTEIO" in (mc.get("mercado", mc.get("market", "")).upper()) for mc in mercados):
            logger.info(f"[audit] {home} vs {away}: corners home={home_corners} away={away_corners} total={total_corners}")

        actual_result = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "total_goals": total_goals,
            "btts": btts,
            "result_1x2": result_1x2,
            "total_corners": total_corners,
        }

        picks_eval = []
        match_correct = 0
        match_total = 0

        for merc in mercados:
            merc_name = merc.get("mercado", merc.get("market", ""))
            merc_status = merc.get("status", merc.get("pick_type", "NEUTRO"))

            pick_dict = {"mercado": merc_name}
            is_correct = _evaluate_pick_deterministic(pick_dict, actual_result)

            picks_eval.append({
                "mercado": merc_name,
                "status_pick": merc_status,
                "resultado": "ACERTOU" if is_correct else "ERROU",
            })

            match_total += 1
            overall_total += 1
            if is_correct:
                match_correct += 1
                overall_correct += 1

            if merc_status == "SAFE":
                safe_total += 1
                if is_correct:
                    safe_correct += 1
            elif merc_status == "NEUTRO":
                neutro_total += 1
                if is_correct:
                    neutro_correct += 1

            market_key = merc_name.upper().strip()
            if market_key not in market_stats:
                market_stats[market_key] = {"correct": 0, "total": 0}
            market_stats[market_key]["total"] += 1
            if is_correct:
                market_stats[market_key]["correct"] += 1

            # Calculate EV for each pick
            odd_pick = merc.get("odd_minima", 0) or 0
            prob_pick = merc.get("prob_max", 0) / 100.0 if merc.get("prob_max") else 0
            ev_pick = None
            if odd_pick > 0 and prob_pick > 0:
                ev_pick = (prob_pick * (odd_pick - 1)) - (1 - prob_pick)
                ev_values.append(ev_pick)

            # Log individual pick to audit_results for calibrator training (Gap 3)
            try:
                _norm_market = merc_name.strip()
                actual_outcome = "hit" if is_correct else "miss"
                audit_db.log_pick(
                    match_id=m.get("id", f"{home}-{away}"),
                    league=league,
                    market=_norm_market,
                    predicted_probs={"prob": prob_pick, "market": _norm_market},
                    pick_type=merc_status,
                    ev=ev_pick,
                    context={"regime": stats.get("leagueRegime", ""), "source": "cron_batch"},
                    actual_result=actual_outcome,
                )
            except Exception as _log_err:
                logger.debug(f"[Gap3] Could not log pick {merc_name}: {_log_err}")

        lambda_total = stats.get("lambdaTotal") or (
            (stats.get("lambdaHome") or 0) + (stats.get("lambdaAway") or 0)
        )
        if lambda_total and lambda_total > 0:
            lambda_errors.append(abs(lambda_total - total_goals))

        over25_prob = stats.get("over25Prob")
        if over25_prob is not None:
            actual_over25 = 1 if total_goals > 2.5 else 0
            brier = (over25_prob / 100.0 - actual_over25) ** 2
            brier_scores.append(brier)

        match_results.append({
            "match_id": m.get("id", ""),
            "home_team": home,
            "away_team": away,
            "league": league,
            "score": f"{home_goals}x{away_goals}",
            "picks_correct": match_correct,
            "picks_total": match_total,
        })

    # ── Dupla (combinada) accuracy: INTRA and INTER ──
    # Build actual_result lookup by match ID for leg evaluation
    _actual_by_id: dict[str, dict] = {}
    for m in finished_matches:
        mid = m.get("id", "")
        score = m.get("score") or {}
        hg = score.get("home", 0) if score else 0
        ag = score.get("away", 0) if score else 0
        if not score:
            hg = int(m.get("home_team_goal_count") or m.get("homeGoals") or 0)
            ag = int(m.get("away_team_goal_count") or m.get("awayGoals") or 0)
        tg = hg + ag
        _btts = hg > 0 and ag > 0
        _1x2 = "1" if hg > ag else ("X" if hg == ag else "2")
        _actual_by_id[mid] = {"total_goals": tg, "btts": _btts, "result_1x2": _1x2}
        # Also index by homeTeam+awayTeam for leg matching
        hname = (m.get("homeTeam") or "").strip().lower()
        aname = (m.get("awayTeam") or "").strip().lower()
        if hname and aname:
            _actual_by_id[f"{hname}|{aname}"] = _actual_by_id[mid]

    def _find_actual_for_leg(leg: dict) -> dict | None:
        """Find actual result for a dupla leg by team names."""
        h = (leg.get("homeTeam") or "").strip().lower()
        a = (leg.get("awayTeam") or "").strip().lower()
        if h and a:
            key = f"{h}|{a}"
            if key in _actual_by_id:
                return _actual_by_id[key]
        return None

    dupla_stats = {"intra": {"correct": 0, "total": 0}, "inter": {"correct": 0, "total": 0}}
    try:
        from backend.services.combinadas_service import gerar_combinadas
        combinadas = gerar_combinadas(finished_matches, tipos=["intra", "inter"])
        for tipo in ("intra", "inter"):
            for dupla in combinadas.get(tipo, []):
                leg1 = dupla.get("leg1", {})
                leg2 = dupla.get("leg2", {})
                actual1 = _find_actual_for_leg(leg1)
                actual2 = _find_actual_for_leg(leg2)
                if actual1 is None or actual2 is None:
                    continue
                hit1 = _evaluate_pick_deterministic({"mercado": leg1.get("mercado", "")}, actual1)
                hit2 = _evaluate_pick_deterministic({"mercado": leg2.get("mercado", "")}, actual2)
                dupla_stats[tipo]["total"] += 1
                if hit1 and hit2:
                    dupla_stats[tipo]["correct"] += 1
    except Exception as e:
        logger.warning(f"[audit] Dupla accuracy calculation failed: {e}")

    intra_acc = (dupla_stats["intra"]["correct"] / dupla_stats["intra"]["total"] * 100.0) if dupla_stats["intra"]["total"] > 0 else 0.0
    inter_acc = (dupla_stats["inter"]["correct"] / dupla_stats["inter"]["total"] * 100.0) if dupla_stats["inter"]["total"] > 0 else 0.0
    logger.info(
        f"[audit] Duplas: INTRA {dupla_stats['intra']['correct']}/{dupla_stats['intra']['total']} ({intra_acc:.1f}%) | "
        f"INTER {dupla_stats['inter']['correct']}/{dupla_stats['inter']['total']} ({inter_acc:.1f}%)"
    )

    # Aggregate
    overall_accuracy_pct = (overall_correct / overall_total * 100.0) if overall_total > 0 else 0.0
    safe_accuracy_pct = (safe_correct / safe_total * 100.0) if safe_total > 0 else 0.0
    neutro_accuracy_pct = (neutro_correct / neutro_total * 100.0) if neutro_total > 0 else 0.0
    avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
    avg_lambda_error = sum(lambda_errors) / len(lambda_errors) if lambda_errors else 0.0
    avg_ev = sum(ev_values) / len(ev_values) if ev_values else 0.0

    # Build prompt data
    market_accuracy_list = []
    for mkt, data in sorted(market_stats.items()):
        acc = (data["correct"] / data["total"] * 100.0) if data["total"] > 0 else 0.0
        market_accuracy_list.append(f"- {mkt}: {data['correct']}/{data['total']} ({acc:.1f}%)")

    matches_summary_lines = []
    for mr in match_results[:20]:
        matches_summary_lines.append(
            f"- {mr['home_team']} {mr['score']} {mr['away_team']} ({mr['league']}) | "
            f"{mr['picks_correct']}/{mr['picks_total']} acertos"
        )

    batch_summary = {
        "total_audited": len(match_results),
        "overall_correct": overall_correct,
        "overall_total": overall_total,
        "overall_accuracy_pct": overall_accuracy_pct,
        "safe_correct": safe_correct,
        "safe_total": safe_total,
        "safe_accuracy_pct": safe_accuracy_pct,
        "neutro_correct": neutro_correct,
        "neutro_total": neutro_total,
        "neutro_accuracy_pct": neutro_accuracy_pct,
        "avg_brier_score": avg_brier,
        "avg_lambda_error": avg_lambda_error,
        "avg_ev": avg_ev,
        "market_accuracy_text": "\n".join(market_accuracy_list) or "Sem dados",
        "matches_summary_text": "\n".join(matches_summary_lines) or "Sem detalhes",
        "dupla_intra_correct": dupla_stats["intra"]["correct"],
        "dupla_intra_total": dupla_stats["intra"]["total"],
        "dupla_intra_accuracy_pct": intra_acc,
        "dupla_inter_correct": dupla_stats["inter"]["correct"],
        "dupla_inter_total": dupla_stats["inter"]["total"],
        "dupla_inter_accuracy_pct": inter_acc,
    }

    # ONE Mistral call for model evaluation
    model_evaluation = None
    try:
        auditor = MistralAuditor()
        model_evaluation = auditor.evaluate_model_from_batch(batch_summary)
        logger.info(f"Model evaluation: {model_evaluation.get('overall_assessment', 'UNKNOWN')}")
    except Exception as e:
        logger.error(f"Mistral batch evaluation failed in cron: {e}")

    # Store result
    try:
        audit_db.log_audit_result(
            match_id=f"cron_batch:{date_filter}:{datetime.now().strftime('%Y%m%d')}",
            league="ALL",
            audit_data={
                "overall_accuracy": overall_accuracy_pct,
                "safe_accuracy": safe_accuracy_pct,
                "neutro_accuracy": neutro_accuracy_pct,
                "total_matches": len(match_results),
                "avg_brier_score": avg_brier,
                "avg_lambda_error": avg_lambda_error,
                "avg_ev": avg_ev,
                "model_evaluation_summary": model_evaluation.get("overall_assessment", "") if model_evaluation else "",
            },
            match_status="cron_batch_audit",
            user="cron",
        )
    except Exception as e:
        logger.warning(f"Could not store cron batch audit result: {e}")

    # Auto-apply high-confidence corrections from model evaluation (with validation)
    auto_applied = []
    rejected = []
    if model_evaluation and model_evaluation.get("recommended_corrections"):
        from backend.audit import validate_adjustment, audit_logger
        for corr in model_evaluation["recommended_corrections"]:
            confidence = corr.get("confidence", 0)
            # Only auto-apply if confidence >= 80%
            if confidence >= 80:
                try:
                    old_val = float(corr.get("current_value", 0))
                    new_val = float(corr.get("suggested_value", 0))
                    param = corr.get("parameter", "")
                    corr_type = corr.get("type", "")

                    # Validate adjustment is within safety limits
                    is_valid, reason = validate_adjustment(corr_type, param, old_val, new_val)
                    if not is_valid:
                        rejected.append(param)
                        logger.warning(f"Correction rejected: {param} — {reason}")
                        audit_logger.info(
                            f"[CRON] Correcao rejeitada: parameter={param}, "
                            f"old={old_val}, new={new_val}, reason={reason}"
                        )
                        continue

                    audit_db.log_correction(
                        match_id=f"cron_auto_{datetime.now().strftime('%Y%m%d')}",
                        league="ALL",
                        correction_type=corr_type,
                        parameter_name=param,
                        old_value=old_val,
                        new_value=new_val,
                        suggested_by="mistral_cron_audit",
                        applied_by="cron_auto",
                        audit_confidence=confidence,
                        reason=corr.get("reason", ""),
                    )
                    auto_applied.append(param)
                    logger.info(f"Auto-applied correction: {param} ({old_val} -> {new_val})")
                except Exception as e:
                    logger.warning(f"Failed to auto-apply correction: {e}")

    # Increment app version if corrections were applied
    if auto_applied:
        try:
            from backend.audit import increment_version, audit_logger as _al
            new_ver = increment_version()
            _al.info(f"[CRON] Versao atualizada: {new_ver} apos {len(auto_applied)} correcoes")
            logger.info(f"Version incremented to {new_ver}")
        except Exception as e:
            logger.warning(f"Failed to increment version: {e}")

    result = {
        "status": "success",
        "triggered_by": "eventbridge_cron",
        "timestamp": datetime.now().isoformat(),
        "audited_matches": len(match_results),
        "overall_accuracy": round(overall_accuracy_pct, 1),
        "safe_accuracy": round(safe_accuracy_pct, 1),
        "neutro_accuracy": round(neutro_accuracy_pct, 1),
        "avg_brier_score": round(avg_brier, 4),
        "avg_ev": round(avg_ev, 4),
        "model_assessment": model_evaluation.get("overall_assessment", "") if model_evaluation else "N/A",
        "dupla_intra_accuracy": round(intra_acc, 1),
        "dupla_intra_total": dupla_stats["intra"]["total"],
        "dupla_inter_accuracy": round(inter_acc, 1),
        "dupla_inter_total": dupla_stats["inter"]["total"],
        "auto_corrections_applied": len(auto_applied),
        "auto_corrections": auto_applied,
        "rejected_corrections": len(rejected),
    }

    logger.info(f"Cron batch audit completed: {json.dumps(result)}")
    return result


def _run_retrain_calibrators() -> dict:
    """Retrain Isotonic Regression calibrators for all active leagues (Gap 5).

    Scheduled weekly: cron(0 4 ? * MON *) → 04:00 UTC Monday.
    Uses season_start boundary per league (not a fixed 90-day window).
    """
    try:
        from backend.modeling.calibrator import retrain_all_calibrators
        results = retrain_all_calibrators()
        logger.info(f"Calibrator retraining completed: {results}")
        return {"status": "success", "calibrators": results}
    except Exception as e:
        logger.error(f"Calibrator retraining failed: {e}")
        return {"status": "error", "message": str(e)}


def _run_threshold_adjustment() -> dict:
    """Auto-adjust thresholds based on accumulated Brier scores."""
    from backend import audit as audit_db

    logger.info("Starting automated threshold adjustment")

    defaults = {
        "1X2": {"SAFE": 0.60, "NEUTRO": 0.50},
        "Over/Under": {"SAFE": 0.60, "NEUTRO": 0.50},
        "BTTS": {"SAFE": 0.60, "NEUTRO": 0.50},
        "Double Chance": {"SAFE": 0.60, "NEUTRO": 0.50},
    }

    try:
        audit_db.adjust_thresholds(defaults)
        logger.info("Threshold adjustment completed successfully")
        return {"status": "success", "message": "Thresholds ajustados com sucesso"}
    except Exception as e:
        logger.error(f"Threshold adjustment failed: {e}")
        return {"status": "error", "message": str(e)}
