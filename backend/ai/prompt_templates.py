class PromptTemplates:
    """Templates de prompts otimizados para análise de futebol e auditoria de cálculos."""
    
    @staticmethod
    def context_analysis_prompt(home_team: str, away_team: str, news_summary: str, stats: dict) -> str:
        """Prompt para análise de contexto profundo."""
        return f"""
        Você é um analista de futebol especializado em prognósticos de apostas de elite.
        
        JOGO: {home_team} vs {away_team}
        
        CONTEXTO COLETADO:
        {news_summary}
        
        ESTATÍSTICAS DO SISTEMA:
        {stats}
        
        TAREFA:
        Analise o contexto do jogo e responda EXCLUSIVAMENTE em JSON com a seguinte estrutura:
        {{
            "injuries_key_players": {{
                "home": "Principais ausências do {home_team}",
                "away": "Principais ausências do {away_team}"
            }},
            "pressure_level": {{
                "home": "ALTA|MEDIA|BAIXA",
                "away": "ALTA|MEDIA|BAIXA"
            }},
            "tactical_insight": "Breve análise de como o contexto afeta o jogo",
            "confidence_adjustment": {{
                "recommendation": "AUMENTAR|MANTER|REDUZIR",
                "reason": "Justificativa baseada no contexto",
                "impact_percentage": -20 a +20
            }}
        }}
        """

    @staticmethod
    def audit_calculation_prompt(calc_data: dict) -> str:
        """Prompt para a Mistral atuar como auditora de cálculos."""
        return f"""
        Você é um auditor sênior de modelos estatísticos de futebol (Poisson, xG, ML).
        
        DADOS PARA AUDITORIA:
        {calc_data}
        
        TAREFA:
        Valide se os cálculos (Probabilidades, Lambdas, EV) são coerentes com o contexto e históricos.
        Responda EXCLUSIVAMENTE em JSON:
        {{
            "validation": {{
                "probabilities": {{"status": "OK|WARNING|CRITICAL", "notes": "..."}},
                "lambdas": {{"status": "OK|WARNING|CRITICAL", "notes": "..."}},
                "ev": {{"status": "OK|WARNING|CRITICAL", "notes": "..."}}
            }},
            "suggestions": ["Sugestão 1", "Sugestão 2"],
            "audit_confidence": 0-100
        }}
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
