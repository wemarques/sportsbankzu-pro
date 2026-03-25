class PromptTemplates:
    """Templates de prompts para geração de relatórios profissionais.

    #082: Stripped to narrative-only. All audit/calculation prompts removed —
    Mistral is narrative-only; Dixon-Coles + per-league calibration handle calculations.
    """

    @staticmethod
    def report_generation_prompt(home_team, away_team, stats, market, classification, probability):
        """Prompt para geração de relatórios profissionais."""
        return f"""
        Gere um relatório profissional de aposta para o jogo {home_team} vs {away_team}.
        Mercado: {market}
        Classificação: {classification}
        Probabilidade: {probability}%
        Estatísticas: {stats}

        O relatório deve ser conciso, dividido em:
        1. Análise Estatística
        2. Justificativa Técnica
        3. Conclusão e Recomendação
        """
