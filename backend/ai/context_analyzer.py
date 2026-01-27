import json
from backend.ai.mistral_client import MistralClient

class ContextAnalyzer:
    def __init__(self, model: str = "mistral-medium-latest", client: MistralClient | None = None):
        self.client = client or MistralClient(model=model)

    def analyze_match_context(self, home_team: str, away_team: str, news_summary: str | None = None) -> dict:
        prompt = f"""
        Analise o contexto do jogo {home_team} vs {away_team}:
        Notícias recentes:
        {news_summary or "Nenhuma notícia disponível"}
        Responda em JSON com a seguinte estrutura:
        {{
            "injuries_key_players": {{"home": "str", "away": "str"}},
            "pressure_level": {{"home": "ALTA|MEDIA|BAIXA", "away": "ALTA|MEDIA|BAIXA"}},
            "confidence_adjustment": {{
                "recommendation": "AUMENTAR|MANTER|REDUZIR",
                "reason": "str"
            }}
        }}
        """
        resp = self.client.simple_prompt(prompt)
        try:
            return json.loads(resp)
        except Exception:
            return {"error": "invalid_json", "raw": resp}
