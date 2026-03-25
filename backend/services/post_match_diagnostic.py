"""Post-Match Diagnostic Engine (#083).

3 components:
1. Error Decomposition — per-pick cause identification (Python)
2. Pattern Detection — aggregate pattern analysis (Python)
3. Narrative Generator — human-readable text (Mistral narrative, optional)

Follows #082 contract: Mistral is narrative-only, never calculates.
"""

import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("sportsbankzu.diagnostic")


# ── Error Decomposition ──

ERROR_CAUSES = [
    "LAMBDA_OVERESTIMATE",
    "LAMBDA_UNDERESTIMATE",
    "RHO_INSUFFICIENT",
    "ODDS_VALUE_TRAP",
    "EARLY_SEASON",
    "CALIBRATION_DRIFT",
    "MARKET_MISMATCH",
    "CORNER_MODEL_ERROR",
    "LOW_SAMPLE",
    "UNKNOWN",
]


def decompose_error(
    pick: dict,
    match_result: dict,
    league_stats: dict | None = None,
) -> dict:
    """Decompose a single pick error into its probable cause.

    Args:
        pick: evaluated pick with prob, ev, odd, mercado, status, acertou
        match_result: actual result with goals, corners, cards
        league_stats: league statistics (optional, for context)

    Returns:
        {
            "cause": "LAMBDA_OVERESTIMATE",
            "confidence": 0.85,
            "detail": "...",
            "suggested_action": "...",
        }
    """
    if pick.get("acertou", True):
        return {"cause": "CORRECT", "confidence": 1.0, "detail": "Pick acertou"}

    causes = []
    mercado = pick.get("mercado", "").lower()
    prob = pick.get("prob", 50)
    ev = pick.get("ev", 0)
    odd = pick.get("odd", 0)

    lambda_h = pick.get("lambda_home") or match_result.get("lambda_home")
    lambda_a = pick.get("lambda_away") or match_result.get("lambda_away")
    actual_home_goals = match_result.get("homeGoals", match_result.get("home_goals"))
    actual_away_goals = match_result.get("awayGoals", match_result.get("away_goals"))

    actual_total = None
    if actual_home_goals is not None and actual_away_goals is not None:
        actual_total = actual_home_goals + actual_away_goals

    predicted_total = None
    if lambda_h is not None and lambda_a is not None:
        try:
            predicted_total = float(lambda_h) + float(lambda_a)
        except (ValueError, TypeError):
            pass

    # 1. Lambda overestimate/underestimate
    if predicted_total is not None and actual_total is not None and predicted_total > 0:
        ratio = predicted_total / max(actual_total, 0.5)
        if ratio > 1.3:
            causes.append({
                "cause": "LAMBDA_OVERESTIMATE",
                "confidence": min(0.9, 0.5 + (ratio - 1.3) * 2),
                "detail": f"lambda total previsto {predicted_total:.2f} vs gols reais {actual_total} (razao {ratio:.2f}x)",
                "suggested_action": "Verificar deflacao O/U e decay temporal para esta liga",
            })
        elif ratio < 0.7:
            causes.append({
                "cause": "LAMBDA_UNDERESTIMATE",
                "confidence": min(0.9, 0.5 + (0.7 - ratio) * 2),
                "detail": f"lambda total previsto {predicted_total:.2f} vs gols reais {actual_total} (razao {ratio:.2f}x)",
                "suggested_action": "Verificar se decay esta descartando dados relevantes",
            })

    # 2. Rho insufficient (draws not predicted)
    if actual_home_goals is not None and actual_away_goals is not None:
        is_draw = actual_home_goals == actual_away_goals
        draw_prob = pick.get("draw_prob", match_result.get("drawProb", 0))
        if is_draw and draw_prob < 22:
            causes.append({
                "cause": "RHO_INSUFFICIENT",
                "confidence": 0.7,
                "detail": f"Empate {actual_home_goals}-{actual_away_goals} com P(draw)={draw_prob:.1f}%",
                "suggested_action": "Verificar rho calibrado para esta liga — pode precisar de valor mais negativo",
            })

    # 3. Odds value trap
    if ev > 15 and odd > 5.0:
        causes.append({
            "cause": "ODDS_VALUE_TRAP",
            "confidence": 0.65,
            "detail": f"EV={ev:.1f}% com odd={odd:.2f} — high EV em odd muito alta e frequentemente trap",
            "suggested_action": "Considerar cap de odds maximo para classificacao ALTA CONFIANCA",
        })

    # 4. Calibration drift (overconfidence)
    if prob > 70 and not pick.get("acertou", False):
        causes.append({
            "cause": "CALIBRATION_DRIFT",
            "confidence": min(0.8, 0.5 + (prob - 70) / 100),
            "detail": f"Probabilidade {prob:.1f}% mas errou — possivel overconfidence",
            "suggested_action": "Verificar reliability diagram (ECE) para este mercado",
        })

    # 5. Corner model error
    if "escant" in mercado or "corner" in mercado:
        actual_corners = match_result.get(
            "totalCorners",
            match_result.get("total_corners",
                             (match_result.get("home_corners", 0) or 0) +
                             (match_result.get("away_corners", 0) or 0)),
        )
        projected_corners = pick.get("projected_corners") or match_result.get("projectedTotalCornersFT")
        if actual_corners and projected_corners:
            try:
                corner_error = abs(float(actual_corners) - float(projected_corners))
                if corner_error > 3:
                    causes.append({
                        "cause": "CORNER_MODEL_ERROR",
                        "confidence": min(0.85, 0.5 + corner_error / 10),
                        "detail": f"Corners projetados {projected_corners:.1f} vs reais {actual_corners} (erro {corner_error:.1f})",
                        "suggested_action": "Verificar NB2 fit e data quality tier para esta liga",
                    })
            except (ValueError, TypeError):
                pass

    # 6. Low sample
    if league_stats:
        n_calibrated = league_stats.get("calibrated_matches", league_stats.get("n_matches", 100))
        if n_calibrated < 20:
            causes.append({
                "cause": "LOW_SAMPLE",
                "confidence": 0.75,
                "detail": f"Liga com apenas {n_calibrated} jogos calibrados (min. 20)",
                "suggested_action": "Aguardar mais dados ou usar defaults conservadores",
            })

    # Select highest-confidence cause
    if not causes:
        return {
            "cause": "UNKNOWN",
            "confidence": 0.3,
            "detail": "Nenhuma causa sistemica identificada — provavel aleatoriedade",
            "suggested_action": "Monitorar nas proximas rodadas",
        }

    causes.sort(key=lambda c: c["confidence"], reverse=True)
    return causes[0]


# ── Pattern Detection ──

def detect_patterns(
    diagnostics: list[dict],
    league_metrics: dict | None = None,
) -> dict:
    """Detect recurring patterns in diagnosed errors.

    Args:
        diagnostics: list of decompose_error() results
        league_metrics: per-league metrics from cron_handler

    Returns:
        {"patterns": [...], "summary": {...}}
    """
    if not diagnostics:
        return {"patterns": [], "summary": {"total_errors": 0}}

    errors = [d for d in diagnostics if d.get("cause") != "CORRECT"]
    total_errors = len(errors)

    if total_errors == 0:
        return {"patterns": [], "summary": {"total_errors": 0, "all_correct": True}}

    # Count by cause
    cause_counts: dict[str, int] = defaultdict(int)
    cause_by_league: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    cause_by_market: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for d in errors:
        cause = d["cause"]
        cause_counts[cause] += 1
        league = d.get("league", "unknown")
        market = d.get("market", "unknown")
        cause_by_league[cause][league] += 1
        cause_by_market[cause][market] += 1

    patterns = []

    # Pattern 1: Systematic lambda over
    lambda_over = cause_counts.get("LAMBDA_OVERESTIMATE", 0)
    if lambda_over >= 3 and lambda_over / total_errors >= 0.30:
        affected_leagues = [lg for lg, c in cause_by_league["LAMBDA_OVERESTIMATE"].items() if c >= 2]
        patterns.append({
            "type": "SYSTEMATIC_LAMBDA_OVER",
            "frequency": round(lambda_over / total_errors, 2),
            "count": lambda_over,
            "affected_leagues": affected_leagues,
            "severity": "HIGH" if lambda_over / total_errors >= 0.50 else "MEDIUM",
            "recommendation": f"Recalibrar deflacao O/U para {', '.join(affected_leagues) or 'todas as ligas'}. "
                             f"Lambda sobre-estima gols em {lambda_over}/{total_errors} erros ({lambda_over/total_errors:.0%}).",
        })

    # Pattern 2: Systematic lambda under
    lambda_under = cause_counts.get("LAMBDA_UNDERESTIMATE", 0)
    if lambda_under >= 3 and lambda_under / total_errors >= 0.30:
        affected_leagues = [lg for lg, c in cause_by_league["LAMBDA_UNDERESTIMATE"].items() if c >= 2]
        patterns.append({
            "type": "SYSTEMATIC_LAMBDA_UNDER",
            "frequency": round(lambda_under / total_errors, 2),
            "count": lambda_under,
            "affected_leagues": affected_leagues,
            "severity": "HIGH" if lambda_under / total_errors >= 0.50 else "MEDIUM",
            "recommendation": "Lambda sub-estima gols. Verificar decay temporal e dados recentes.",
        })

    # Pattern 3: Draws not predicted (rho insufficient)
    rho_count = cause_counts.get("RHO_INSUFFICIENT", 0)
    if rho_count >= 2 and rho_count / total_errors >= 0.15:
        affected_leagues = [lg for lg, c in cause_by_league["RHO_INSUFFICIENT"].items() if c >= 1]
        patterns.append({
            "type": "DRAW_UNDERESTIMATION",
            "frequency": round(rho_count / total_errors, 2),
            "count": rho_count,
            "affected_leagues": affected_leagues,
            "severity": "MEDIUM",
            "recommendation": f"Empates nao previstos em {', '.join(affected_leagues)}. "
                             f"Verificar rho calibrado — pode precisar de valor mais negativo.",
        })

    # Pattern 4: Overconfidence
    overconf_count = cause_counts.get("CALIBRATION_DRIFT", 0)
    if overconf_count >= 3 and overconf_count / total_errors >= 0.25:
        patterns.append({
            "type": "OVERCONFIDENCE",
            "frequency": round(overconf_count / total_errors, 2),
            "count": overconf_count,
            "severity": "HIGH",
            "recommendation": "Modelo overconfident — probabilidades altas demais para o acerto real. "
                             "Verificar ECE no reliability diagram e considerar recalibracao.",
        })

    # Pattern 5: Corners systematically wrong
    corner_count = cause_counts.get("CORNER_MODEL_ERROR", 0)
    if corner_count >= 2:
        patterns.append({
            "type": "CORNER_SYSTEMATIC_ERROR",
            "frequency": round(corner_count / total_errors, 2),
            "count": corner_count,
            "severity": "MEDIUM",
            "recommendation": "Motor de corners (NB2) com erro sistematico. "
                             "Verificar champion selector e data quality tier por liga.",
        })

    # Pattern 6: Value traps in high odds
    trap_count = cause_counts.get("ODDS_VALUE_TRAP", 0)
    if trap_count >= 2:
        patterns.append({
            "type": "HIGH_ODDS_VALUE_TRAP",
            "frequency": round(trap_count / total_errors, 2),
            "count": trap_count,
            "severity": "LOW",
            "recommendation": "Picks com EV alto em odds > 5.0 falhando sistematicamente. "
                             "Considerar cap de odds maximo para classificacao ALTA CONFIANCA.",
        })

    # Sort by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    patterns.sort(key=lambda p: severity_order.get(p["severity"], 3))

    top_cause = max(cause_counts, key=cause_counts.get) if cause_counts else "UNKNOWN"

    return {
        "patterns": patterns,
        "summary": {
            "total_errors": total_errors,
            "decomposed": total_errors - cause_counts.get("UNKNOWN", 0),
            "unknown": cause_counts.get("UNKNOWN", 0),
            "top_cause": top_cause,
            "top_cause_pct": round(cause_counts[top_cause] / total_errors, 2) if total_errors > 0 else 0,
            "cause_distribution": dict(cause_counts),
        },
    }


# ── Narrative Generator ──

def generate_diagnostic_narrative(
    pattern_report: dict,
    use_mistral: bool = False,
) -> str:
    """Generate human-readable diagnostic text.

    Default: deterministic text (Python).
    Optional: Mistral for more fluent narrative (#082 — narrative only).
    """
    summary = pattern_report.get("summary", {})
    patterns = pattern_report.get("patterns", [])

    if summary.get("total_errors", 0) == 0:
        return "Todos os picks da rodada acertaram. Sem diagnostico de erro necessario."

    if summary.get("all_correct"):
        return "Desempenho perfeito nesta rodada. Monitorar estabilidade nas proximas."

    # Deterministic text (default — always works)
    lines = []
    lines.append("DIAGNOSTICO POS-RODADA")
    lines.append(f"Erros analisados: {summary['total_errors']}")
    lines.append(f"Causa principal: {summary['top_cause']} ({summary['top_cause_pct']:.0%} dos erros)")
    lines.append(f"Erros sem causa identificada: {summary.get('unknown', 0)}")
    lines.append("")

    if patterns:
        lines.append("PADROES DETECTADOS:")
        for i, p in enumerate(patterns, 1):
            severity_label = {"HIGH": "[ALTO]", "MEDIUM": "[MEDIO]", "LOW": "[BAIXO]"}.get(p["severity"], "[?]")
            lines.append(f"{i}. {severity_label} {p['type']} ({p['severity']})")
            lines.append(f"   Frequencia: {p['frequency']:.0%} dos erros ({p['count']} ocorrencias)")
            if p.get("affected_leagues"):
                lines.append(f"   Ligas afetadas: {', '.join(p['affected_leagues'])}")
            lines.append(f"   Acao: {p['recommendation']}")
            lines.append("")
    else:
        lines.append("Nenhum padrao sistematico detectado — erros provavelmente aleatorios.")

    deterministic_text = "\n".join(lines)

    # Optional: enrich with Mistral (narrative only)
    if use_mistral:
        try:
            enriched = _mistral_narrative_enrichment(deterministic_text, pattern_report)
            if enriched:
                return enriched
        except Exception as e:
            logger.debug(f"Mistral narrative enrichment skipped: {e}")

    return deterministic_text


def _mistral_narrative_enrichment(
    deterministic_text: str,
    pattern_report: dict,
) -> str | None:
    """Use Mistral ONLY to make text more fluent and readable.

    Mistral does NOT calculate, does NOT generate new conclusions.
    It receives the ready diagnosis and rewrites in natural language.
    (#082: Mistral is narrative-only)
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        import httpx
        prompt = (
            "Reescreva o diagnostico abaixo em linguagem natural fluida, "
            "mantendo TODAS as informacoes, numeros e recomendacoes. "
            "NAO adicione analises novas. NAO invente dados. "
            "Apenas torne o texto mais legivel e profissional.\n\n"
            f"DIAGNOSTICO ORIGINAL:\n{deterministic_text}\n\n"
            "Responda APENAS com o texto reescrito, sem JSON, sem markdown."
        )

        with httpx.Client() as client:
            response = client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "mistral-large-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.15,
                    "max_tokens": 1500,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.debug(f"Mistral narrative enrichment failed: {e}")
        return None


# ── Orchestrator ──

def run_post_match_diagnostic(
    evaluated_picks: list[dict],
    match_results: list[dict],
    league_metrics: dict | None = None,
    use_mistral_narrative: bool = False,
) -> dict:
    """Orchestrate all 3 diagnostic components.

    Called after cron_handler evaluates picks.

    Args:
        evaluated_picks: picks with acertou, prob, ev, etc.
        match_results: actual match results
        league_metrics: per-league metrics from cron_handler
        use_mistral_narrative: if True, use Mistral to enrich text

    Returns:
        {
            "error_decomposition": [...],
            "pattern_report": {...},
            "narrative": "...",
            "timestamp": "...",
        }
    """
    # Index results by match_id
    results_by_match: dict[str, dict] = {}
    for r in match_results:
        mid = r.get("match_id", r.get("id", ""))
        if mid:
            results_by_match[mid] = r

    # Component 1: Error Decomposition
    decompositions = []
    for pick in evaluated_picks:
        match_id = pick.get("match_id", "")
        match_result = results_by_match.get(match_id, {})
        league = pick.get("league", "unknown")
        market = pick.get("mercado", pick.get("market", "unknown"))

        league_stats = None
        if league_metrics and league in league_metrics:
            league_stats = league_metrics[league]

        diag = decompose_error(pick, match_result, league_stats)
        diag["match_id"] = match_id
        diag["league"] = league
        diag["market"] = market
        decompositions.append(diag)

    # Component 2: Pattern Detection
    pattern_report = detect_patterns(decompositions, league_metrics)

    # Component 3: Narrative
    narrative = generate_diagnostic_narrative(pattern_report, use_mistral=use_mistral_narrative)

    return {
        "error_decomposition": decompositions,
        "pattern_report": pattern_report,
        "narrative": narrative,
        "timestamp": datetime.now().isoformat(),
        "engine_version": "1.0",
    }
