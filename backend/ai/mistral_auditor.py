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
            audit_result = json.loads(response_text)
            
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
