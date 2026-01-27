import json
from backend.ai.mistral_client import MistralClient


class ContextAnalyzer:
    def __init__(self, model: str = "mistral-medium-latest", client: MistralClient | None = None):
        self.client = client or MistralClient(model=model)

    def analyze_match_context(self, home_team: str, away_team: str, news_summary: str | None = None) -> dict:
        prompt = f"""
        Analise o contexto do jogo {home_team} vs {away_team}:
        Noticias recentes:
        {news_summary or "Nenhuma noticia disponivel"}
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
        system = "Voce e um gerador estrito de JSON. Responda somente JSON valido, sem texto adicional."
        resp = self.client.simple_prompt(prompt, system_prompt=system)

        def _strip_fences(s: str) -> str:
            if s.strip().startswith("```"):
                s2 = s.strip().strip("`")
                if s2.lower().startswith("json"):
                    s2 = s2[4:]
                return s2.strip()
            return s

        raw = resp
        text = _strip_fences(raw)
        try:
            return json.loads(text)
        except Exception:
            return {"error": "invalid_json", "raw": raw}
