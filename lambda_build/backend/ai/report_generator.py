from backend.ai.mistral_client import MistralClient
from backend.ai.prompt_templates import PromptTemplates

class ReportGenerator:
    def __init__(self, model: str = "mistral-medium-latest", client: MistralClient | None = None):
        self.client = client or MistralClient(model=model)

    def generate_match_report(self, home_team: str, away_team: str, stats: dict, market: str, classification: str, probability: float) -> str:
        prompt = PromptTemplates.report_generation_prompt(
            home_team, away_team, stats, market, classification, probability
        )
        return self.client.simple_prompt(prompt)
