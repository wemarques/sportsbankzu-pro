class PromptTemplates:
    """Templates de prompts otimizados para análise de futebol e auditoria de cálculos."""
    
    @staticmethod
    def context_analysis_prompt(home_team: str, away_team: str, news_summary: str, stats: dict) -> str:
        """Prompt para análise de contexto profundo."""
        return f"""
        Você é um analista de dados esportivos especializado em futebol. Sua função é analisar estatísticas detalhadas de duas equipes e prever o resultado mais provável para o mercado de 'Total de Gols (Acima/Abaixo)'. Suas previsões devem ser lógicas, baseadas exclusivamente nos dados fornecidos e expressas em valores positivos, pois representam contagens de gols.

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
                "impact_percentage": 0 a 20  // Valor de ajuste de confiança (sempre positivo)
            }},
            "independent_prediction": {{
                "total_goals_estimate": 0.0, // Estimativa de gols totais (ex: 2.75)
                "reasoning": "Breve justificativa para a estimativa de gols baseada nos dados."
            }}
        }}
        """

    @staticmethod
    def audit_calculation_prompt(calc_data: dict) -> str:
        """Prompt para a Mistral atuar como auditora de cálculos."""
        return f"""
        Você é um analista de dados esportivos especializado em futebol. Sua função é analisar estatísticas detalhadas de duas equipes e prever o resultado mais provável para o mercado de 'Total de Gols (Acima/Abaixo)'. Suas previsões devem ser lógicas, baseadas exclusivamente nos dados fornecidos e expressas em valores positivos, pois representam contagens de gols.
        Você também atua como um auditor sênior de modelos estatísticos (Poisson, xG, ML).
        
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
            "independent_prediction": {{
                "total_goals_estimate": 0.0, // Sua estimativa independente de gols totais (sempre positiva)
                "reasoning": "Justificativa para sua estimativa."
            }},
            "suggestions": ["Sugestão 1", "Sugestão 2"],
            "audit_confidence": 0-100
        }}
        """

    @staticmethod
    def audit_post_match_prompt(predictions_data: dict, ai_analysis: dict, actual_result: dict) -> str:
        """Prompt para auditoria pos-jogo: compara prognosticos do sistema + analise Mistral vs resultado real."""
        return f"""
        Voce e um auditor senior de modelos estatisticos esportivos (Poisson, xG, ML).
        Sua tarefa e avaliar a precisao dos prognosticos do sistema e da analise AI comparando com o resultado real.

        PROGNOSTICOS DO SISTEMA (picks gerados antes do jogo):
        {predictions_data}

        ANALISE AI MISTRAL (gerada antes do jogo):
        {ai_analysis}

        RESULTADO REAL DO JOGO:
        {actual_result}

        TAREFA:
        1. Para cada pick do sistema (SAFE/NEUTRO), avalie se ACERTOU ou ERROU com base no resultado real
           - Exemplo: pick "Under 3.5 gols" e resultado com 2 gols totais = ACERTOU
           - Exemplo: pick "BTTS SIM" e resultado 2x0 (sem gols fora) = ERROU
        2. Calcule o Brier Score das probabilidades previstas
        3. Avalie se os lambdas previram corretamente o total de gols
        4. Verifique se a analise Mistral estava alinhada com o resultado real
        5. Identifique vieses sistematicos (ex: lambda consistentemente alto)
        6. Sugira correcoes ESPECIFICAS com parametros e valores numericos

        Responda EXCLUSIVAMENTE em JSON valido (sem markdown, sem ```, apenas JSON puro):
        {{
            "picks_evaluation": [
                {{
                    "mercado": "nome do mercado",
                    "status_pick": "SAFE|NEUTRO",
                    "resultado": "ACERTOU|ERROU",
                    "nota": "explicacao breve"
                }}
            ],
            "validation": {{
                "probabilities": {{"status": "OK|WARNING|CRITICAL", "notes": "analise detalhada", "brier_score": 0.0}},
                "lambdas": {{"status": "OK|WARNING|CRITICAL", "notes": "analise detalhada", "predicted_total": 0.0, "actual_total": 0}},
                "ev": {{"status": "OK|WARNING|CRITICAL", "notes": "analise do valor esperado"}}
            }},
            "ai_analysis_accuracy": "Resumo de quao precisa foi a analise Mistral em relacao ao resultado",
            "accuracy_summary": "Resumo geral da precisao do sistema + AI",
            "corrections": [
                {{
                    "type": "lambda_multiplier|threshold_adjustment|weight_adjustment",
                    "parameter": "nome especifico do parametro a ajustar",
                    "current_value": 0.0,
                    "suggested_value": 0.0,
                    "reason": "Justificativa baseada nos dados",
                    "confidence": 75,
                    "impact": "LOW|MEDIUM|HIGH"
                }}
            ],
            "biases_detected": ["descricao do vies detectado"],
            "audit_confidence": 80
        }}
        """

    @staticmethod
    def batch_audit_model_evaluation_prompt(batch_data: dict) -> str:
        """Prompt agregado para Mistral avaliar modelos do sistema e da propria AI com dados da rodada."""
        return f"""
        Voce e um auditor senior de modelos estatisticos esportivos (Poisson, xG, ML).
        Sua tarefa e avaliar a precisao dos MODELOS do sistema e da AI com base nos resultados agregados de uma rodada completa.

        DADOS AGREGADOS DA RODADA:
        - Total de jogos finalizados auditados: {batch_data.get("total_audited", 0)}
        - Acerto total dos picks: {batch_data.get("overall_correct", 0)}/{batch_data.get("overall_total", 0)} ({batch_data.get("overall_accuracy_pct", 0):.1f}%)
        - Acerto picks SAFE: {batch_data.get("safe_correct", 0)}/{batch_data.get("safe_total", 0)} ({batch_data.get("safe_accuracy_pct", 0):.1f}%)
        - Acerto picks NEUTRO: {batch_data.get("neutro_correct", 0)}/{batch_data.get("neutro_total", 0)} ({batch_data.get("neutro_accuracy_pct", 0):.1f}%)
        - Media Brier Score: {batch_data.get("avg_brier_score", 0):.4f}
        - Media EV (Expected Value): {batch_data.get("avg_ev", 0):.4f}
        - Erro medio de lambda (previsto vs real): {batch_data.get("avg_lambda_error", 0):.2f} gols

        ACURACIA POR MERCADO:
        {batch_data.get("market_accuracy_text", "Sem dados")}

        DETALHES DOS JOGOS (resumo):
        {batch_data.get("matches_summary_text", "Sem dados")}

        TAREFA:
        Avalie se os modelos estatisticos (Poisson, lambdas, thresholds) e a propria analise AI precisam de ajustes.
        Considere:
        1. Os lambdas estao sobre-estimando ou sub-estimando gols?
        2. Os thresholds SAFE e NEUTRO estao adequados?
        3. Ha vieses sistematicos por mercado (ex: BTTS sempre errando)?
        4. A AI (voce mesmo) — seus fatores de analise estao alinhados com os resultados?
           Quais fatores deve enfatizar mais? Quais deve reduzir?
        5. Correcoes especificas com tipo, parametro, valor atual, valor sugerido

        Responda EXCLUSIVAMENTE em JSON valido (sem markdown, sem ```, apenas JSON puro):
        {{
            "overall_assessment": "SATISFATORIO|NECESSITA_AJUSTE|CRITICO",
            "overall_notes": "Resumo geral da avaliacao",
            "lambda_evaluation": {{
                "status": "OK|WARNING|CRITICAL",
                "direction": "OVER_ESTIMATING|UNDER_ESTIMATING|BALANCED",
                "avg_error": 0.0,
                "notes": "Analise detalhada dos lambdas"
            }},
            "threshold_evaluation": {{
                "safe_status": "OK|WARNING|CRITICAL",
                "neutro_status": "OK|WARNING|CRITICAL",
                "notes": "Analise dos thresholds SAFE e NEUTRO"
            }},
            "market_biases": [
                {{
                    "market": "nome do mercado",
                    "bias_type": "OVER_CONFIDENT|UNDER_CONFIDENT|SYSTEMATIC_ERROR",
                    "description": "descricao do vies",
                    "severity": "LOW|MEDIUM|HIGH"
                }}
            ],
            "ai_self_evaluation": {{
                "alignment_with_results": "BOM|MODERADO|FRACO",
                "factors_to_emphasize": ["fator 1", "fator 2"],
                "factors_to_reduce": ["fator 1", "fator 2"],
                "notes": "Auto-avaliacao da AI sobre seus proprios padroes de analise"
            }},
            "recommended_corrections": [
                {{
                    "type": "THRESHOLD|LAMBDA_WEIGHT|MARKET_FILTER|AI_PROMPT",
                    "parameter": "nome especifico do parametro",
                    "current_value": 0.0,
                    "suggested_value": 0.0,
                    "reason": "Justificativa baseada nos dados da rodada",
                    "confidence": 75,
                    "impact": "LOW|MEDIUM|HIGH"
                }}
            ],
            "audit_confidence": 80
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
