import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .mistral_client import MistralClient
from .prompt_templates import PromptTemplates
from .cache_manager import CacheManager

logger = logging.getLogger("sportsbank.ai.auditor")

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
        home = match_data.get("homeTeam")
        away = match_data.get("awayTeam")
        
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
            
            def _strip_fences(s: str) -> str:
                s = s.strip()
                if "```" in s:
                    import re
                    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
                    if match:
                        return match.group(1).strip()
                    s2 = s.strip("`")
                    if s2.lower().startswith("json"):
                        s2 = s2[4:]
                    return s2.strip()
                return s

            clean_text = _strip_fences(response_text)
            audit_result = json.loads(clean_text)
            
            # Adicionar metadados
            audit_result["timestamp"] = datetime.now().isoformat()
            audit_result["match"] = f"{home} vs {away}"
            
            # 4. Salvar no Cache
            self.cache.set("audit", home, away, audit_result)
            
            return audit_result
        except Exception as e:
            logger.error(f"Erro na auditoria Mistral para {home} vs {away}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "validation": {"probabilities": {"status": "UNKNOWN"}, "lambdas": {"status": "UNKNOWN"}, "ev": {"status": "UNKNOWN"}},
                "audit_confidence": 0
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
        home = match_data.get("homeTeam", "")
        away = match_data.get("awayTeam", "")

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

            def _strip_fences(s: str) -> str:
                s = s.strip()
                if "```" in s:
                    import re
                    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
                    if match:
                        return match.group(1).strip()
                    s2 = s.strip("`")
                    if s2.lower().startswith("json"):
                        s2 = s2[4:]
                    return s2.strip()
                return s

            clean_text = _strip_fences(response_text)
            audit_result = json.loads(clean_text)

            # Add metadata
            audit_result["timestamp"] = datetime.now().isoformat()
            audit_result["match"] = f"{home} vs {away}"
            audit_result["audit_type"] = "post_match"

            # Cache result
            self.cache.set("audit_post", home, away, audit_result)

            return audit_result
        except Exception as e:
            logger.error(f"Erro na auditoria pos-jogo para {home} vs {away}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "audit_type": "post_match",
                "picks_evaluation": [],
                "validation": {
                    "probabilities": {"status": "UNKNOWN"},
                    "lambdas": {"status": "UNKNOWN"},
                    "ev": {"status": "UNKNOWN"},
                },
                "corrections": [],
                "biases_detected": [],
                "audit_confidence": 0,
            }
