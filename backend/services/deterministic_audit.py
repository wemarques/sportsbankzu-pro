"""Deterministic audit report generator (#079).

Replaces MistralAuditor.evaluate_model_from_batch() with 100% rule-based logic.
Output matches frontend BatchAuditModelEvaluation interface exactly.

References: REGRAS #079, #069 (per-league Brier), #043 (SAFE circuit breaker).
"""
import logging
import math
from datetime import datetime
from typing import Any

from backend.services.backtesting import (
    compute_log_loss,
    compute_calibration_bins,
    MIN_N_BRIER,
    MIN_N_LOG_LOSS,
    MIN_N_RELIABILITY,
)

logger = logging.getLogger("sportsbankzu.deterministic_audit")

# Display names for frontend-facing text strings (#080).
# Structural fields (safe_status, threshold params) keep internal names.
DISPLAY_NAMES: dict[str, str] = {
    "SAFE": "ALTA CONFIANCA",
    "NEUTRO_QUALIFICADO": "VALOR DETECTADO",
    "NEUTRO": "VIÁVEL",
    "NO_BET": "BLOQUEADO",
}


def _display_name(internal: str) -> str:
    return DISPLAY_NAMES.get(internal, internal)


def generate_deterministic_audit_report(
    batch_summary: dict[str, Any],
    league_metrics: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Generate a deterministic batch audit report.

    Args:
        batch_summary: Dict built in cron_handler (keys: overall_accuracy_pct,
            safe_accuracy_pct, neutro_accuracy_pct, avg_brier_score,
            avg_lambda_error, avg_ev, market_accuracy_text, etc.)
        league_metrics: Per-league dict from cron_handler (keys per league:
            correct, total, safe_correct, safe_total, brier_scores, lambda_errors)

    Returns:
        Dict matching BatchAuditModelEvaluation frontend interface.
    """
    league_metrics = league_metrics or {}

    avg_brier = batch_summary.get("avg_brier_score", 0.0)
    avg_lambda_err = batch_summary.get("avg_lambda_error", 0.0)
    safe_acc = batch_summary.get("safe_accuracy_pct", 0.0)
    neutro_acc = batch_summary.get("neutro_accuracy_pct", 0.0)
    overall_acc = batch_summary.get("overall_accuracy_pct", 0.0)
    total_audited = batch_summary.get("total_audited", 0)

    # ── overall_assessment ──────────────────────────────────────────
    assessment = _compute_assessment(avg_brier, safe_acc, avg_lambda_err, overall_acc)

    # ── lambda_evaluation ───────────────────────────────────────────
    lambda_eval = _compute_lambda_evaluation(avg_lambda_err, league_metrics)

    # ── threshold_evaluation ────────────────────────────────────────
    threshold_eval = _compute_threshold_evaluation(safe_acc, neutro_acc)

    # ── market_biases ───────────────────────────────────────────────
    market_biases = _detect_market_biases(batch_summary)

    # ── recommended_corrections ─────────────────────────────────────
    corrections = _compute_corrections(
        avg_brier, avg_lambda_err, safe_acc, batch_summary, league_metrics
    )

    # ── Safety: filter corrections against operational rules (#099) ──
    try:
        from backend.services.safety_validation import filtrar_corrections_por_regras
        _filter_result = filtrar_corrections_por_regras(corrections, n_jogos=total_audited)
        corrections = _filter_result["acoes_validas"]
        _blocked_corrections = _filter_result["acoes_bloqueadas"]
    except Exception:
        _blocked_corrections = []

    # ── model_update_recommendation ─────────────────────────────────
    model_rec = _compute_model_recommendation(assessment, corrections)

    # Filter recommended_actions against rules (#099)
    try:
        from backend.services.safety_validation import filtrar_acoes_por_regras
        _act_filter = filtrar_acoes_por_regras(
            model_rec.get("recommended_actions", []), n_jogos=total_audited
        )
        model_rec["recommended_actions"] = _act_filter["acoes_validas"]
        _blocked_corrections.extend(_act_filter["acoes_bloqueadas"])
    except Exception:
        pass

    # ── overall_notes with per-league summary ───────────────────────
    notes_parts = [
        f"Auditados: {total_audited} jogos",
        f"Accuracy: {overall_acc:.1f}%",
        f"Brier O/U: {avg_brier:.4f}",
        f"Lambda Err: {avg_lambda_err:.2f}",
    ]

    # Per-league log-loss and calibration from league_metrics
    league_lines = []
    for lg_name in sorted(league_metrics):
        lm = league_metrics[lg_name]
        brier_scores = lm.get("brier_scores", [])
        lg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else None

        # Compute log-loss from ou_predictions if available
        ou_preds = lm.get("ou_predictions", [])
        lg_log_loss = compute_log_loss(ou_preds) if len(ou_preds) >= MIN_N_LOG_LOSS else None

        parts = [f"{lg_name}: {lm.get('correct', 0)}/{lm.get('total', 0)}"]
        if lg_brier is not None:
            parts.append(f"Brier={lg_brier:.4f}")
        if lg_log_loss is not None:
            parts.append(f"LogLoss={lg_log_loss:.4f}")
        league_lines.append(", ".join(parts))

    if league_lines:
        notes_parts.append("Per-league: " + " | ".join(league_lines[:5]))
        if len(league_lines) > 5:
            notes_parts.append(f"... +{len(league_lines) - 5} ligas")

    # #084: Additional metrics from batch_summary
    sharpe_data = batch_summary.get("sharpe_ratio", {})
    if sharpe_data.get("sharpe") is not None:
        notes_parts.append(f"Sharpe Ratio: {sharpe_data['sharpe']:.3f} ({sharpe_data.get('n_bets', 0)} apostas)")

    roi_data = batch_summary.get("roi", {})
    if roi_data.get("roi_pct") is not None:
        notes_parts.append(f"ROI: {roi_data['roi_pct']:.1f}%")

    cal_data = batch_summary.get("calibration", {})
    if cal_data.get("ece") is not None:
        notes_parts.append(f"ECE: {cal_data['ece']:.4f} ({'bem calibrado' if cal_data['ece'] < 0.05 else 'recalibrar'})")

    baseline = batch_summary.get("odds_baseline", {})
    if baseline.get("model_vs_house") is not None:
        direction = "MELHOR" if baseline["model_beats_house"] else "PIOR"
        notes_parts.append(
            f"Modelo vs Casa: {direction} (Brier modelo={baseline['brier_model']:.4f}, "
            f"casa={baseline['brier_implied']:.4f}, diff={baseline['model_vs_house']:.4f})"
        )

    ev_data = batch_summary.get("hit_rate_by_ev", [])
    if ev_data:
        ev_summary = ", ".join(f"{b['band']}={b['accuracy']:.0%}" for b in ev_data if b.get("total", 0) >= 5)
        if ev_summary:
            notes_parts.append(f"Hit Rate por EV: {ev_summary}")

    # ── confidence ──────────────────────────────────────────────────
    confidence = _compute_confidence(total_audited)

    return {
        "overall_assessment": assessment,
        "overall_notes": ". ".join(notes_parts),
        "lambda_evaluation": lambda_eval,
        "threshold_evaluation": threshold_eval,
        "market_biases": market_biases,
        "ai_self_evaluation": {
            "alignment_with_results": "N/A (deterministic)",
            "factors_to_emphasize": [],
            "factors_to_reduce": [],
            "notes": "Audit 100% deterministico — sem LLM (#079)",
        },
        "recommended_corrections": corrections,
        "blocked_corrections": _blocked_corrections,  # #099
        "model_update_recommendation": model_rec,
        "audit_confidence": confidence,
        "timestamp": datetime.now().isoformat(),
        "audit_type": "batch_model_evaluation",
        "total_matches_evaluated": total_audited,
    }


# ── Private helpers ─────────────────────────────────────────────────────


def _compute_assessment(
    avg_brier: float, safe_acc: float, avg_lambda_err: float, overall_acc: float
) -> str:
    if avg_brier > 0.28 or safe_acc < 40 or avg_lambda_err > 1.5:
        return "CRITICO"
    if avg_brier > 0.24 or safe_acc < 50 or avg_lambda_err > 1.0 or overall_acc < 45:
        return "NECESSITA_AJUSTE"
    return "SATISFATORIO"


def _compute_lambda_evaluation(
    avg_lambda_err: float, league_metrics: dict
) -> dict[str, Any]:
    if avg_lambda_err < 0.8:
        status = "OK"
    elif avg_lambda_err < 1.2:
        status = "ALTO"
    else:
        status = "CRITICO"

    # Determine direction from league_metrics lambda data
    direction = "UNKNOWN"
    total_diff = 0.0
    count = 0
    for lm in league_metrics.values():
        for le in lm.get("lambda_errors_detail", []):
            if le.get("predicted") is not None and le.get("actual") is not None:
                total_diff += le["predicted"] - le["actual"]
                count += 1
    if count > 0:
        direction = "OVER" if total_diff > 0 else "UNDER"

    notes = f"Erro medio: {avg_lambda_err:.2f}."
    if status == "CRITICO":
        notes += " Lambdas precisam de recalibracao urgente."
    elif status == "ALTO":
        notes += " Considerar ajuste no proximo ciclo."

    return {
        "status": status,
        "direction": direction,
        "avg_error": round(avg_lambda_err, 4),
        "notes": notes,
    }


def _compute_threshold_evaluation(safe_acc: float, neutro_acc: float) -> dict[str, Any]:
    safe_status = "OK" if safe_acc >= 55 else "BAIXO"
    neutro_status = "OK" if neutro_acc >= 45 else "BAIXO"

    notes_parts = []
    if safe_status == "BAIXO":
        notes_parts.append(f"{_display_name('SAFE')} accuracy {safe_acc:.1f}% abaixo do alvo 55%")
    if neutro_status == "BAIXO":
        notes_parts.append(f"{_display_name('NEUTRO')} accuracy {neutro_acc:.1f}% abaixo do alvo 45%")
    if not notes_parts:
        notes_parts.append("Thresholds dentro dos parametros aceitaveis")

    return {
        "safe_status": safe_status,
        "neutro_status": neutro_status,
        "notes": ". ".join(notes_parts),
    }


def _detect_market_biases(batch_summary: dict) -> list[dict]:
    """Parse market_accuracy_text to detect markets with <40% accuracy (N>=5)."""
    biases = []
    text = batch_summary.get("market_accuracy_text", "")
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue
        # Format: "- OVER_2.5: 5/12 (41.7%)"
        try:
            parts = line[2:].split(":")
            market = parts[0].strip()
            stats_part = parts[1].strip()
            fraction, pct_part = stats_part.split("(")
            correct, total = fraction.strip().split("/")
            correct_n = int(correct)
            total_n = int(total)
            pct = float(pct_part.replace("%)", "").strip())
            if total_n >= 5 and pct < 40.0:
                biases.append({
                    "market": market,
                    "actual_accuracy": round(pct, 1),
                    "expected_accuracy": 50.0,
                    "bias_direction": "UNDER" if "OVER" in market.upper() else "OVER",
                    "sample_size": total_n,
                })
        except (ValueError, IndexError):
            continue
    return biases


def _compute_corrections(
    avg_brier: float,
    avg_lambda_err: float,
    safe_acc: float,
    batch_summary: dict,
    league_metrics: dict,
) -> list[dict]:
    """Generate deterministic correction suggestions."""
    corrections = []
    total = batch_summary.get("overall_total", 0)

    # Confidence based on sample size
    base_confidence = 60
    if total >= 50:
        base_confidence = 80
    elif total >= 30:
        base_confidence = 70

    # Rule 1: O/U Brier too high → lambda deflation
    if avg_brier > 0.25:
        delta = avg_brier - 0.22  # target Brier = 0.22
        suggested_deflation = max(0.80, 1.0 - delta * 2)
        corrections.append({
            "type": "lambda_deflation",
            "parameter": "lambda_ou",
            "current_value": 1.0,
            "suggested_value": round(suggested_deflation, 2),
            "reason": f"Brier O/U {avg_brier:.4f} > 0.25. Reducao de deflation sugerida.",
            "confidence": base_confidence,
            "impact": "HIGH" if avg_brier > 0.28 else "MEDIUM",
        })

    # Rule 2: Lambda error too high
    if avg_lambda_err > 1.0:
        corrections.append({
            "type": "lambda_calibration",
            "parameter": "lambda_weights",
            "current_value": 0.6,
            "suggested_value": 0.5,
            "reason": f"Lambda error {avg_lambda_err:.2f} > 1.0. Ajuste de pesos sugerido.",
            "confidence": min(base_confidence, 70),
            "impact": "MEDIUM",
        })

    # Rule 3: SAFE accuracy low → increase thresholds
    if safe_acc < 50 and batch_summary.get("safe_total", 0) >= 5:
        corrections.append({
            "type": "threshold",
            "parameter": "safe_prob_ou",
            "current_value": 0.65,
            "suggested_value": 0.70,
            "reason": f"{_display_name('SAFE')} accuracy {safe_acc:.1f}% < 50%. Aumentar threshold.",
            "confidence": base_confidence,
            "impact": "HIGH",
        })

    # Rule 4: Per-league corrections for worst performers
    for lg_name, lm in league_metrics.items():
        lg_total = lm.get("total", 0)
        lg_correct = lm.get("correct", 0)
        if lg_total < 5:
            continue
        lg_acc = lg_correct / lg_total * 100
        if lg_acc < 35:
            corrections.append({
                "type": "league_calibration",
                "parameter": f"recalibrate_{lg_name}",
                "current_value": lg_acc,
                "suggested_value": 50.0,
                "reason": f"{lg_name}: accuracy {lg_acc:.1f}% muito baixa. Recalibracao recomendada.",
                "confidence": min(base_confidence, 65),
                "impact": "MEDIUM",
            })

    return corrections


def _compute_model_recommendation(
    assessment: str, corrections: list[dict]
) -> dict[str, Any]:
    """Generate model update recommendation based on assessment and corrections."""
    high_impact = sum(1 for c in corrections if c.get("impact") == "HIGH")
    medium_impact = sum(1 for c in corrections if c.get("impact") == "MEDIUM")

    if assessment == "CRITICO":
        urgency = "ALTA"
        needs_update = True
    elif assessment == "NECESSITA_AJUSTE" or high_impact > 0:
        urgency = "MEDIA"
        needs_update = True
    elif medium_impact > 2:
        urgency = "MEDIA"
        needs_update = True
    else:
        urgency = "BAIXA"
        needs_update = False

    reasons = []
    if assessment == "CRITICO":
        reasons.append("Modelo em estado critico — multiplos indicadores abaixo do aceitavel")
    for c in corrections[:3]:
        reasons.append(c["reason"])

    actions = []
    if high_impact > 0:
        actions.append("Aplicar correcoes de alto impacto")
    if any(c["type"] == "league_calibration" for c in corrections):
        actions.append("Recalibrar ligas com baixa performance")
    if not actions:
        actions.append("Monitorar proxima rodada")

    return {
        "needs_update": needs_update,
        "urgency": urgency,
        "reasons": reasons if reasons else ["Modelo dentro dos parametros aceitaveis"],
        "recommended_actions": actions,
        "next_retrain_suggestion": (
            "Imediato" if urgency == "ALTA"
            else "Proxima rodada" if urgency == "MEDIA"
            else "Monitorar 3 rodadas"
        ),
    }


def _compute_confidence(total_audited: int) -> int:
    """Confidence score 0-100 based on sample size."""
    if total_audited >= 50:
        return 85
    if total_audited >= 30:
        return 75
    if total_audited >= 15:
        return 60
    if total_audited >= 5:
        return 40
    return 20
