import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from backend.ai.mistral_client import MistralClient
from backend.ai.cache_manager import CacheManager

logger = logging.getLogger("sportsbank.ai.analysis")


class AIAnalysisResponse(BaseModel):
    """Structured response from Mistral AI match analysis."""

    summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    recommendation: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    last_updated: str = ""


class MistralAnalysisService:
    """Generates structured AI match analyses using the Mistral API."""

    def __init__(self):
        self.client = MistralClient()
        self.cache = CacheManager(ttl_hours=6)

    def _build_prompt(self, match_data: Dict[str, Any]) -> str:
        home = match_data.get("home_team") or match_data.get("homeTeam", "Home")
        away = match_data.get("away_team") or match_data.get("awayTeam", "Away")
        league = match_data.get("league") or match_data.get("leagueName", "")
        stats = match_data.get("stats", {})
        odds = match_data.get("odds", {})
        h2h = match_data.get("h2h", {})

        return f"""Voce e um analista de dados esportivos especializado em futebol.
Analise os dados abaixo e gere um prognostico estruturado.

JOGO: {home} vs {away}
LIGA: {league}

ESTATISTICAS:
- Lambda Home: {stats.get('lambdaHome') or stats.get('lambda_home', 'N/A')}
- Lambda Away: {stats.get('lambdaAway') or stats.get('lambda_away', 'N/A')}
- Prob Home Win: {stats.get('homeWinProb') or stats.get('prob_home', 'N/A')}%
- Prob Draw: {stats.get('drawProb') or stats.get('prob_draw', 'N/A')}%
- Prob Away Win: {stats.get('awayWinProb') or stats.get('prob_away', 'N/A')}%
- Prob Over 2.5: {stats.get('over25Prob') or stats.get('prob_over_25', 'N/A')}%
- Prob BTTS: {stats.get('bttsProb') or stats.get('prob_btts', 'N/A')}%

ODDS:
- Home: {odds.get('home', 'N/A')}
- Draw: {odds.get('draw', 'N/A')}
- Away: {odds.get('away', 'N/A')}
- Over 2.5: {odds.get('over25') or odds.get('over_25', 'N/A')}
- BTTS Yes: {odds.get('bttsYes') or odds.get('btts_yes', 'N/A')}

H2H:
- Total jogos: {h2h.get('totalMatches', 'N/A')}
- Vitorias casa: {h2h.get('homeWins', 'N/A')}
- Empates: {h2h.get('draws', 'N/A')}
- Vitorias fora: {h2h.get('awayWins', 'N/A')}
- Media gols: {h2h.get('avgGoals', 'N/A')}

Responda EXCLUSIVAMENTE em JSON valido com a seguinte estrutura:
{{
    "summary": "Resumo geral da analise em 2-3 frases",
    "key_points": [
        "Ponto-chave 1",
        "Ponto-chave 2",
        "Ponto-chave 3",
        "Ponto-chave 4",
        "Ponto-chave 5"
    ],
    "recommendation": "Recomendacao clara de aposta com justificativa",
    "confidence": 75
}}

REGRAS:
- confidence deve ser um inteiro de 0 a 100
- key_points deve ter exatamente 5 itens
- Nao use markdown, apenas JSON puro
- Baseie-se nos dados fornecidos, nao invente estatisticas"""

    def _strip_json_fences(self, text: str) -> str:
        text = text.strip()
        if "```" in text:
            import re

            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            return text.strip()
        return text

    def analyze_match(self, match_data: Dict[str, Any]) -> AIAnalysisResponse:
        """Analyze a match and return a structured AI response.

        Uses cache when available. Falls back to a generic response on error.
        """
        home = match_data.get("home_team") or match_data.get("homeTeam", "Home")
        away = match_data.get("away_team") or match_data.get("awayTeam", "Away")

        # Check cache
        cached = self.cache.get("analysis", home, away)
        if cached:
            logger.info(f"Cache hit for analysis: {home} vs {away}")
            return AIAnalysisResponse(**cached)

        prompt = self._build_prompt(match_data)

        try:
            response_text = self.client.simple_prompt(
                prompt,
                system_prompt="Voce e um analista esportivo profissional. Responda apenas em JSON valido.",
            )
            clean = self._strip_json_fences(response_text)
            parsed = json.loads(clean)

            result = AIAnalysisResponse(
                summary=parsed.get("summary", ""),
                key_points=parsed.get("key_points", [])[:5],
                recommendation=parsed.get("recommendation", ""),
                confidence=max(0, min(100, int(parsed.get("confidence", 50)))),
                last_updated=datetime.now().isoformat(),
            )

            # Save to cache
            self.cache.set("analysis", home, away, result.model_dump())
            return result

        except Exception as e:
            logger.error(f"Mistral analysis error for {home} vs {away}: {e}")
            return AIAnalysisResponse(
                summary=f"Analise automatica indisponivel para {home} vs {away}. Tente novamente mais tarde.",
                key_points=[
                    "Servico de AI temporariamente indisponivel",
                    "Verifique as estatisticas manuais disponíveis",
                    "Consulte o historico H2H para referencia",
                    "Odds de mercado podem indicar tendencias",
                    "Aguarde nova tentativa de analise",
                ],
                recommendation="Analise manual recomendada enquanto o servico AI esta indisponivel.",
                confidence=0,
                last_updated=datetime.now().isoformat(),
            )
