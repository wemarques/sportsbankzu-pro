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
  - Input: {"source": "eventbridge", "action": "batch_audit", "date": "today"}
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("sportsbank.cron")
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
    date_filter = event.get("date", "today")

    try:
        if action == "batch_audit":
            return _run_batch_audit(date_filter)
        elif action == "adjust_thresholds":
            return _run_threshold_adjustment()
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    except Exception as e:
        logger.error(f"Cron handler error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        os.environ.pop("EVENTBRIDGE_TRIGGERED", None)


def _run_batch_audit(date_filter: str) -> dict:
    """Execute batch audit for all finished matches."""
    from backend.routes.ai_analysis import (
        _get_all_finished_matches,
        _evaluate_pick_deterministic,
    )
    from backend.ai.mistral_auditor import MistralAuditor
    from backend import audit as audit_db

    logger.info(f"Starting automated batch audit for date={date_filter}")

    finished_matches = _get_all_finished_matches(date_filter)

    if not finished_matches:
        logger.info("No finished matches found. Skipping audit.")
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

        actual_result = {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "total_goals": total_goals,
            "btts": btts,
            "result_1x2": result_1x2,
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

    # Aggregate
    overall_accuracy_pct = (overall_correct / overall_total * 100.0) if overall_total > 0 else 0.0
    safe_accuracy_pct = (safe_correct / safe_total * 100.0) if safe_total > 0 else 0.0
    neutro_accuracy_pct = (neutro_correct / neutro_total * 100.0) if neutro_total > 0 else 0.0
    avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0.0
    avg_lambda_error = sum(lambda_errors) / len(lambda_errors) if lambda_errors else 0.0

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
        "market_accuracy_text": "\n".join(market_accuracy_list) or "Sem dados",
        "matches_summary_text": "\n".join(matches_summary_lines) or "Sem detalhes",
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
                "model_evaluation_summary": model_evaluation.get("overall_assessment", "") if model_evaluation else "",
            },
            match_status="cron_batch_audit",
            user="cron",
        )
    except Exception as e:
        logger.warning(f"Could not store cron batch audit result: {e}")

    # Auto-apply high-confidence corrections from model evaluation
    auto_applied = []
    if model_evaluation and model_evaluation.get("recommended_corrections"):
        for corr in model_evaluation["recommended_corrections"]:
            confidence = corr.get("confidence", 0)
            # Only auto-apply if confidence >= 80%
            if confidence >= 80:
                try:
                    audit_db.log_correction(
                        match_id=f"cron_auto_{datetime.now().strftime('%Y%m%d')}",
                        league="ALL",
                        correction_type=corr.get("type", ""),
                        parameter_name=corr.get("parameter", ""),
                        old_value=float(corr.get("current_value", 0)),
                        new_value=float(corr.get("suggested_value", 0)),
                        suggested_by="mistral_cron_audit",
                        applied_by="cron_auto",
                        audit_confidence=confidence,
                        reason=corr.get("reason", ""),
                    )
                    auto_applied.append(corr.get("parameter", ""))
                    logger.info(f"Auto-applied correction: {corr.get('parameter', '')} "
                                f"({corr.get('current_value', 0)} -> {corr.get('suggested_value', 0)})")
                except Exception as e:
                    logger.warning(f"Failed to auto-apply correction: {e}")

    result = {
        "status": "success",
        "triggered_by": "eventbridge_cron",
        "timestamp": datetime.now().isoformat(),
        "audited_matches": len(match_results),
        "overall_accuracy": round(overall_accuracy_pct, 1),
        "safe_accuracy": round(safe_accuracy_pct, 1),
        "neutro_accuracy": round(neutro_accuracy_pct, 1),
        "avg_brier_score": round(avg_brier, 4),
        "model_assessment": model_evaluation.get("overall_assessment", "") if model_evaluation else "N/A",
        "auto_corrections_applied": len(auto_applied),
        "auto_corrections": auto_applied,
    }

    logger.info(f"Cron batch audit completed: {json.dumps(result)}")
    return result


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
