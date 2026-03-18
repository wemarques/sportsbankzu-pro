"""
Corners Engine v2 — Layer E: Mistral AI Contextual Review

Mistral serves as a contextual reviewer and explainer, NOT the primary
probability engine. It can:
- reduce confidence
- flag tactical/style conflicts
- force NO_BET for contextual risk
- enrich explanation

Mistral CANNOT:
- invent probabilities
- substitute projected_total_corners
- promote a weak market to ACTIVE unilaterally
- transform a statistical NO_BET into a pick
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("sportsbankzu.corners.mistral_review")


def build_corners_review_prompt(engine_output: Dict[str, Any]) -> str:
    """Build a structured prompt for Mistral to review corner predictions."""
    proj = engine_output.get("projection", {})
    ladder = engine_output.get("pricing", {})
    selected = ladder.get("selected", {})
    quality = engine_output.get("data_quality", {})

    return f"""Você é um analista sênior de escanteios (corners) de futebol.
O motor estatístico do SportsBankZU Pro gerou a seguinte projeção de escanteios para um jogo.
Sua tarefa é revisar contextualmente a escolha do motor, NÃO substituí-la.

PROJEÇÃO DO MOTOR:
- Total esperado FT: {proj.get('expected_total_corners_ft', 'N/A')}
- Total esperado 1H: {proj.get('expected_total_corners_1h', 'N/A')}
- Total esperado 2H: {proj.get('expected_total_corners_2h', 'N/A')}
- Intervalo de previsão: [{ladder.get('prediction_interval_low', '?')}, {ladder.get('prediction_interval_high', '?')}]
- Modelo campeão: {engine_output.get('champion_model', 'N/A')}
- Desvio padrão: {ladder.get('std_dev', 'N/A')}

MELHOR CANDIDATO:
- Mercado: {selected.get('market_label', 'NO BET')}
- Probabilidade modelada: {selected.get('modeled_probability', 'N/A')}
- Edge ajustado: {selected.get('edge', 'N/A')}
- Fair odds: {selected.get('fair_odds', 'N/A')}

QUALIDADE DOS DADOS:
- Tier: {quality.get('data_quality_tier', 'UNKNOWN')}
- Cobertura: {quality.get('coverage_score', 'N/A')}
- Timing FH/2H disponível: {quality.get('corner_timing_available', False)}

FEATURES USADAS:
- Pressão (shots/posse/xG): {quality.get('details', {}).get('has_shots', False)} / {quality.get('details', {}).get('has_possession', False)} / {quality.get('details', {}).get('has_xg', False)}
- Corners contra disponível: {quality.get('details', {}).get('has_corners_against', False)}

TAREFA:
Avalie se a escolha do motor é razoável no contexto tático do jogo.
Responda EXCLUSIVAMENTE em JSON:
{{
    "recommendation_adjustment": "maintain" | "lower_confidence" | "force_no_bet",
    "tactical_context_flags": ["flag1", "flag2"],
    "risk_flags": ["flag1"],
    "style_conflict_flags": [],
    "reason_codes": ["code1"],
    "explanation_text": "Explicação breve em português",
    "confidence_modifier": 0  // -20 a 0 (nunca positivo)
}}

REGRAS:
- Você NÃO pode inventar probabilidades ou substituir o total esperado
- Você NÃO pode promover um mercado fraco para premium
- Você pode reduzir confiança ou forçar NO BET por contexto tático
- Se o motor disse NO BET por razão estatística, mantenha NO BET
"""


def parse_mistral_response(raw: str) -> Dict[str, Any]:
    """Parse Mistral's JSON response with fallback for malformed output."""
    default = {
        "recommendation_adjustment": "maintain",
        "tactical_context_flags": [],
        "risk_flags": [],
        "style_conflict_flags": [],
        "reason_codes": [],
        "explanation_text": "",
        "confidence_modifier": 0,
    }

    if not raw or not raw.strip():
        return default

    try:
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        parsed = json.loads(text)

        # Validate and clamp
        adj = parsed.get("recommendation_adjustment", "maintain")
        if adj not in ("maintain", "lower_confidence", "force_no_bet"):
            adj = "maintain"
        parsed["recommendation_adjustment"] = adj

        modifier = parsed.get("confidence_modifier", 0)
        parsed["confidence_modifier"] = max(-20, min(0, int(modifier)))

        return {**default, **parsed}

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Failed to parse Mistral corner review: {e}")
        return default


def review_corners_with_mistral(
    engine_output: Dict[str, Any],
    mistral_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Call Mistral AI to review corner engine output.

    Args:
        engine_output: Full engine output dict.
        mistral_client: MistralClient instance (optional, graceful degradation).

    Returns:
        Parsed review dict.
    """
    if mistral_client is None:
        try:
            from backend.ai.mistral_client import MistralClient
            mistral_client = MistralClient()
        except Exception:
            logger.info("Mistral client unavailable, skipping corner review")
            return parse_mistral_response("")

    prompt = build_corners_review_prompt(engine_output)

    try:
        response = mistral_client.simple_prompt(
            prompt,
            system_prompt="Você é um auditor de modelos estatísticos esportivos. Responda APENAS em JSON válido.",
            max_tokens=1500,
        )
        return parse_mistral_response(response)
    except Exception as e:
        logger.error(f"Mistral corner review failed: {e}")
        return parse_mistral_response("")


def apply_mistral_adjustment(
    engine_decision: Dict[str, Any],
    mistral_review: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply Mistral's review adjustment to the engine decision.

    Precedence:
    1. Hard blockers from engine (cannot be overridden)
    2. Governance gates
    3. Mistral adjustment
    4. Final output

    Mistral can:
    - lower_confidence: reduce effective edge/probability
    - force_no_bet: turn pick into NO_BET
    - maintain: no change

    Mistral CANNOT:
    - Promote a NO_BET to a pick
    - Increase probability/edge
    """
    decision = {**engine_decision}
    adj = mistral_review.get("recommendation_adjustment", "maintain")

    # If engine already says NO_BET, Mistral can't override
    if decision.get("no_bet"):
        decision["mistral_review"] = mistral_review
        return decision

    if adj == "force_no_bet":
        decision["no_bet"] = True
        decision["no_bet_reason"] = "mistral_context_block"
        decision["mistral_forced_no_bet"] = True
        reason_codes = decision.get("reason_codes", [])
        reason_codes.append("MISTRAL_CONTEXT_BLOCK")
        decision["reason_codes"] = reason_codes

    elif adj == "lower_confidence":
        modifier = mistral_review.get("confidence_modifier", -5)
        modifier = max(-20, min(0, modifier))  # always negative or zero

        if decision.get("modeled_probability") is not None:
            # Reduce probability by modifier percentage points
            prob = decision["modeled_probability"]
            adjustment = abs(modifier) / 100.0
            decision["modeled_probability"] = round(max(0.01, prob - adjustment), 5)
            decision["probability_before_mistral"] = prob

        if decision.get("edge") is not None:
            edge = decision["edge"]
            decision["edge"] = round(edge + modifier / 100.0, 5)  # modifier is negative
            decision["edge_before_mistral"] = edge

        reason_codes = decision.get("reason_codes", [])
        reason_codes.append("MISTRAL_CONFIDENCE_REDUCED")
        decision["reason_codes"] = reason_codes

    decision["mistral_review"] = mistral_review
    return decision
