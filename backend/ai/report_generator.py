from backend.ai.mistral_client import MistralClient

class ReportGenerator:
    def __init__(self, model: str = "mistral-medium-latest", client: MistralClient | None = None):
        self.client = client or MistralClient(model=model)

    def generate_match_report(self, home_team: str, away_team: str, stats: dict, market: str, classification: str, probability: float) -> str:
        prompt = f"""
        Gere um relatório para o jogo {home_team} vs {away_team}:
        Dados:
        - Lambda casa: {stats.get("lambda_home")}
        - Lambda fora: {stats.get("lambda_away")}
        - Mercado: {market} ({classification}, {probability}%)
        Formato:
        1. Análise estatística (1 parágrafo).
        2. Justificativa da classificação (1 parágrafo).
        """
        return self.client.simple_prompt(prompt)
