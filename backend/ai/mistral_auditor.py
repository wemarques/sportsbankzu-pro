import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .mistral_client import MistralClient
from .prompt_templates import PromptTemplates
from .cache_manager import CacheManager

logger = logging.getLogger("sportsbankzu.ai.auditor")


def _strip_fences(s: str) -> str:
    """Remove markdown code fences from Mistral JSON responses."""
    s = s.strip()
    if "```" in s:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
        if match:
            return match.group(1).strip()
        s2 = s.strip("`")
        if s2.lower().startswith("json"):
            s2 = s2[4:]
        return s2.strip()
    return s


def _safe_json_loads(text: str) -> dict:
    """Parse JSON from Mistral responses, handling common issues.

    Fixes:
    - Control characters inside strings (tabs, newlines)
    - Unterminated strings (truncated responses)
    - BOM markers
    """
    clean = _strip_fences(text)

    # Remove BOM if present
    clean = clean.lstrip("\ufeff")

    # Try direct parse first
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Remove control characters inside JSON strings (except escaped ones)
    sanitized = re.sub(r'[\x00-\x1f\x7f]', ' ', clean)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # Try to fix unterminated strings by finding the last complete brace
    # Walk backwards to find the last balanced closing brace
    depth = 0
    last_valid = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(sanitized):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_valid = i
                break

    if last_valid > 0:
        truncated = sanitized[:last_valid + 1]
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    # Last resort: raise with sanitized text for better error message
    return json.loads(sanitized)

def _friendly_error(exc: Exception) -> str:
    """Convert raw Mistral/HTTP exceptions into user-friendly messages."""
    msg = str(exc)
    if "503" in msg or "Service Unavailable" in msg:
        return "Servico Mistral AI temporariamente indisponivel. Tente novamente em alguns minutos."
    if "429" in msg or "rate" in msg.lower():
        return "Limite de requisicoes da Mistral AI atingido. Tente novamente em alguns minutos."
    if "401" in msg or "unauthorized" in msg.lower() or "api_key" in msg.lower():
        return "Chave da Mistral API invalida ou ausente. Verifique MISTRAL_API_KEY."
    if "timeout" in msg.lower():
        return "Tempo esgotado na chamada ao Mistral AI. Tente novamente."
    if "500" in msg or "502" in msg or "504" in msg:
        return "Erro interno no servico Mistral AI. Tente novamente em alguns minutos."
    return f"Erro na auditoria: {msg[:120]}"


class MistralAuditor:
    """Audita os cálculos estatísticos do sistema usando Mistral AI."""
    
    def __init__(self):
        self.client = MistralClient()
        self.cache = CacheManager(ttl_hours=12) # Cache de auditoria por 12h

    def audit_match_calculation(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Realiza a auditoria de um conjunto de cálculos para uma partida.
        
        Args:
            match_data: Dicionário contendo as probabilidades, lambdas e EV calculados.
        """
        match_id = match_data.get("id")
        home = match_data.get("homeTeam") or match_data.get("home_team") or ""
        away = match_data.get("awayTeam") or match_data.get("away_team") or ""
        
        # 1. Verificar Cache
        cached_result = self.cache.get("audit", home, away)
        if cached_result:
            logger.info(f"Cache hit para auditoria: {home} vs {away}")
            return cached_result

        # 2. Preparar Prompt
        prompt = PromptTemplates.audit_calculation_prompt(match_data)
        
        # 3. Chamar Mistral
        try:
            response_text = self.client.simple_prompt(prompt)
            audit_result = _safe_json_loads(response_text)
            
            # Adicionar metadados
            audit_result["timestamp"] = datetime.now().isoformat()
            audit_result["match"] = f"{home} vs {away}"
            
            # 4. Salvar no Cache
            self.cache.set("audit", home, away, audit_result)
            
            return audit_result
        except Exception as e:
            logger.error(f"Erro na auditoria Mistral para {home} vs {away}: {e}")
            friendly_msg = _friendly_error(e)
            return {
                "status": "error",
                "message": friendly_msg,
                "validation": {
                    "probabilities": {"status": "UNKNOWN", "notes": friendly_msg},
                    "lambdas": {"status": "UNKNOWN", "notes": friendly_msg},
                    "ev": {"status": "UNKNOWN", "notes": friendly_msg},
                },
                "audit_confidence": 0,
            }

    def audit_match_vs_result(
        self,
        match_data: Dict[str, Any],
        predictions: list,
        ai_analysis: Dict[str, Any],
        actual_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Post-match audit: compares system predictions + Mistral analysis vs actual results.

        Args:
            match_data: Original match stats, lambdas, odds
            predictions: System picks (SAFE/NEUTRO) with mercado, prob, odd
            ai_analysis: Mistral AI analysis (summary, key_points, recommendation)
            actual_result: {home_goals, away_goals, total_goals, btts, result_1x2}
        """
        home = match_data.get("homeTeam") or match_data.get("home_team") or ""
        away = match_data.get("awayTeam") or match_data.get("away_team") or ""

        # Check cache
        cached = self.cache.get("audit_post", home, away)
        if cached:
            logger.info(f"Cache hit para auditoria pos-jogo: {home} vs {away}")
            return cached

        # Build prediction data for prompt
        predictions_data = {
            "match": f"{home} vs {away}",
            "picks": predictions,
            "stats": {
                k: match_data.get(k)
                for k in ("lambdaHome", "lambdaAway", "lambdaTotal",
                          "homeWinProb", "drawProb", "awayWinProb",
                          "over25Prob", "under35Prob", "bttsProb", "avgGoals")
                if match_data.get(k) is not None
            },
        }

        ai_summary = {
            "summary": ai_analysis.get("summary", ""),
            "key_points": ai_analysis.get("key_points", []),
            "recommendation": ai_analysis.get("recommendation", ""),
            "confidence": ai_analysis.get("confidence", 0),
        }

        prompt = PromptTemplates.audit_post_match_prompt(predictions_data, ai_summary, actual_result)

        try:
            response_text = self.client.simple_prompt(prompt)
            audit_result = _safe_json_loads(response_text)

            # Add metadata
            audit_result["timestamp"] = datetime.now().isoformat()
            audit_result["match"] = f"{home} vs {away}"
            audit_result["audit_type"] = "post_match"

            # Cache result
            self.cache.set("audit_post", home, away, audit_result)

            return audit_result
        except Exception as e:
            logger.error(f"Erro na auditoria pos-jogo para {home} vs {away}: {e}")
            friendly_msg = _friendly_error(e)
            return {
                "status": "error",
                "message": friendly_msg,
                "audit_type": "post_match",
                "picks_evaluation": [],
                "validation": {
                    "probabilities": {"status": "UNKNOWN", "notes": friendly_msg},
                    "lambdas": {"status": "UNKNOWN", "notes": friendly_msg},
                    "ev": {"status": "UNKNOWN", "notes": friendly_msg},
                },
                "corrections": [],
                "biases_detected": [],
                "audit_confidence": 0,
            }

    def evaluate_model_from_batch(self, batch_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate system models + AI with aggregated round data.
        Makes ONE Mistral call with all batch statistics.

        Args:
            batch_summary: Aggregated stats (accuracy by market, lambda errors, brier scores)
        Returns:
            Model evaluation with recommended corrections.
        """
        prompt = PromptTemplates.batch_audit_model_evaluation_prompt(batch_summary)

        try:
            response_text = self.client.simple_prompt(prompt)
            evaluation = _safe_json_loads(response_text)

            evaluation["timestamp"] = datetime.now().isoformat()
            evaluation["audit_type"] = "batch_model_evaluation"
            evaluation["total_matches_evaluated"] = batch_summary.get("total_audited", 0)

            return evaluation
        except Exception as e:
            logger.error(f"Erro na avaliacao de modelos em lote: {e}")
            return {
                "status": "error",
                "message": _friendly_error(e),
                "audit_type": "batch_model_evaluation",
                "overall_assessment": "UNKNOWN",
                "lambda_evaluation": {"status": "UNKNOWN", "notes": "Erro na avaliacao"},
                "threshold_evaluation": {"safe_status": "UNKNOWN", "neutro_status": "UNKNOWN", "notes": "Erro"},
                "market_biases": [],
                "ai_self_evaluation": {"alignment_with_results": "UNKNOWN", "factors_to_emphasize": [], "factors_to_reduce": [], "notes": "Erro"},
                "recommended_corrections": [],
                "audit_confidence": 0,
            }
