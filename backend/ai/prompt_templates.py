def _build_feedback_block(league: str) -> str:
    """Build feedback loop block for prompts when historical accuracy data is available.

    Reference: REGRAS #050 — Mistral feedback loop.
    """
    try:
        from backend.audit import get_mistral_accuracy
        accuracy = get_mistral_accuracy(league, days=30)
        if not accuracy or accuracy.get("total_predictions", 0) < 10:
            return ""
        lines = [
            f"\nHISTORICO DE ACERTOS DESTE SISTEMA (ultimos 30 dias, {league}):",
            f"- Total de analises: {accuracy['total_predictions']}",
            f"- Accuracy geral: {accuracy['overall_accuracy']:.0%}",
        ]
        for mkt, stats in accuracy.get("by_market", {}).items():
            if stats.get("total", 0) >= 5:
                lines.append(f"- {mkt}: {stats['accuracy']:.0%} ({stats['correct']}/{stats['total']})")
        lines.append(
            "Considere este historico ao calibrar sua confianca. "
            "Se a accuracy esta baixa para um mercado especifico, seja mais conservador nesse mercado.\n"
        )
        return "\n".join(lines)
    except Exception:
        return ""  # Silent fallback — don't break analysis if DB unavailable


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

        REGRAS CRITICAS SOBRE AUSENCIAS E STATUS AO VIVO:
        - Utilize SOMENTE os dados de ausencias (lesoes/suspensoes) que foram fornecidos no contexto acima.
        - NUNCA invente, suponha ou fabrique nomes de jogadores lesionados ou suspensos.
        - Se nao houver dados de ausencias, informe apenas que nao ha informacao disponivel.
        - Considere o status da partida (live_status). Se o jogo estiver ao vivo, comente sobre o placar atual e ajuste sua analise.

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

        REGRAS CRITICAS PARA SUGESTAO DE CORRECOES:
        1. PRIORIDADE MAXIMA: Correcoes de lambda (lambda_home, lambda_away, lambda_total).
           Lambda e a base de TODOS os calculos downstream (probabilidades, EV, thresholds).
           Se lambda esta errado, TODAS as probabilidades estao erradas.
           SEMPRE sugira correcao de lambda ANTES de correcoes de threshold.

        2. PRIORIDADE MEDIA: Correcoes de peso/multiplicador (btts_weight_defense, corner_multiplier).
           Estes afetam mercados especificos sem afetar a base de calculo.

        3. PRIORIDADE BAIXA: Correcoes de threshold (over_25_threshold, etc).
           SOMENTE sugira threshold se o lambda ja estiver correto e o threshold ainda gerar erro.
           Na maioria dos casos, corrigir lambda torna desnecessario ajustar threshold.
           NUNCA sugira threshold_adjustment se lambda_multiplier tambem esta sendo sugerido
           — a correcao de lambda ja resolve o problema de threshold downstream.

        4. Para mercados de ESCANTEIOS, sempre compare:
           - Escanteios reais (home_corners + away_corners do resultado) vs projecao do modelo
           - Potenciais da FootyStats vs escanteios reais
           - Se a liga tem dados suficientes de escanteios (corners_recorded_matches_num)
           Se os dados de escanteios reais estiverem disponiveis no resultado, AVALIE a precisao
           do motor de corners e sugira corner_multiplier se necessario.

        5. Para CARTOES, compare:
           - Cartoes reais (total_cards do resultado) vs media esperada
           - Se houve cartao vermelho, avalie impacto no jogo (vantagem numerica)

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
                    "type": "lambda_multiplier|threshold_adjustment|weight_adjustment|corner_multiplier",
                    "parameter": "nome especifico do parametro a ajustar",
                    "current_value": 0.0,
                    "suggested_value": 0.0,
                    "reason": "Justificativa baseada nos dados",
                    "confidence": 75,
                    "impact": "LOW|MEDIUM|HIGH",
                    "priority": "LAMBDA_ROOT_CAUSE|WEIGHT_ADJUSTMENT|THRESHOLD_SYMPTOM"
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

        ACURACIA POR LIGA (Brier, lambda erro e SAFE calculados POR LIGA):
        {batch_data.get("league_accuracy_text", "Sem dados")}

        DETALHES DOS JOGOS (resumo):
        {batch_data.get("matches_summary_text", "Sem dados")}

        SINAL ESTRUTURAL DE MERCADO (market_reference_signal):
        {_format_market_reference_stats(batch_data.get("market_reference_stats"))}
        NOTA: market_reference_signal e uma camada estrutural de governanca por liga+mercado (SAFE/NEUTRO/RESTRITO).
        Use como contexto adicional, mas NAO o trate como verdade matematica nem como substituto da validacao probabilistica.
        Warnings sobre lambdas, probabilidades e thresholds devem continuar normalmente independente do sinal estrutural.
        NAO sugira correcoes do tipo MARKET_REFERENCE_SIGNAL — este parametro nao e ajustavel por correcao automatica.

        TAREFA:
        Avalie se os modelos estatisticos (Poisson, lambdas, thresholds) e a propria analise AI precisam de ajustes.
        Considere:
        1. Os lambdas estao sobre-estimando ou sub-estimando gols?
        2. Os thresholds SAFE e NEUTRO estao adequados?
        3. Ha vieses sistematicos por mercado (ex: BTTS sempre errando)?
        4. A AI (voce mesmo) — seus fatores de analise estao alinhados com os resultados?
           Quais fatores deve enfatizar mais? Quais deve reduzir?
        5. Correcoes especificas com tipo, parametro, valor atual, valor sugerido
        6. O modelo precisa ser atualizado/re-treinado? Avalie com base em:
           - Brier Score medio (>0.25 preocupante, >0.35 critico)
           - Erro lambda medio (>1.5 preocupante, >2.0 critico)
           - Acuracia geral (<50% preocupante, <40% critico)
           - Acuracia SAFE (<60% preocupante, <50% critico)
           - Mercados especificos com performance muito baixa

        REGRAS CRITICAS PARA CORRECOES:
        - PRIORIDADE 1: Lambda (causa raiz). Se lambdas estao sobre/sub-estimando, corrigir PRIMEIRO.
        - PRIORIDADE 2: Pesos/multiplicadores (btts_weight, corner_multiplier). Afetam mercados especificos.
        - PRIORIDADE 3: Thresholds. SOMENTE se lambda e pesos ja estiverem corretos.
        - NUNCA sugira threshold_adjustment junto com lambda_multiplier para o mesmo problema.
        - Para ESCANTEIOS: inclua dados reais de corners quando disponiveis e sugira corner_multiplier.
        - Para CARTOES: compare cards reais vs media esperada.

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
                    "type": "THRESHOLD|LAMBDA_WEIGHT|MARKET_FILTER|AI_PROMPT|BTTS_THRESHOLD|BTTS_MULTIPLIER|CORNER_THRESHOLD|CORNER_MULTIPLIER",
                    "parameter": "nome especifico do parametro (ex: btts_multiplier, corner_multiplier, lambda_home_multiplier)",
                    "current_value": 0.0,
                    "suggested_value": 0.0,
                    "reason": "Justificativa baseada nos dados da rodada",
                    "confidence": 75,
                    "impact": "LOW|MEDIUM|HIGH"
                }}
            ],
            "model_update_recommendation": {{
                "needs_update": true,
                "urgency": "BAIXA|MEDIA|ALTA|CRITICA",
                "reasons": ["razao 1 baseada nos dados", "razao 2"],
                "recommended_actions": ["acao especifica 1", "acao especifica 2"],
                "next_retrain_suggestion": "Descricao de quando re-treinar (ex: Imediato, Proximas 24h, Proxima segunda-feira)"
            }},
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


    @staticmethod
    def build_1x2_prompt(home_team: str, away_team: str, stats: dict, odds: dict) -> str:
        """Prompt focado em 1X2: forma recente, H2H, qualidade do elenco, mando, odds value."""
        return f"""Voce e um analista profissional de apostas esportivas. Analise EXCLUSIVAMENTE o mercado 1X2.

JOGO: {home_team} vs {away_team}

DADOS RELEVANTES:
- Probabilidade Vitoria Casa: {stats.get('homeWinProb', 'N/A')}%
- Probabilidade Empate: {stats.get('drawProb', 'N/A')}%
- Probabilidade Vitoria Fora: {stats.get('awayWinProb', 'N/A')}%
- Posicao na liga: {home_team} {stats.get('homeLeaguePosition', '?')}o vs {away_team} {stats.get('awayLeaguePosition', '?')}o
- % Vitoria temporada: {home_team} {stats.get('homeWinPercentage', 'N/A')}% vs {away_team} {stats.get('awayWinPercentage', 'N/A')}%
- Chaos Score: {stats.get('chaosScore', 'N/A')}

ODDS:
- Casa: {odds.get('homeWin', 'N/A')} | Empate: {odds.get('draw', 'N/A')} | Fora: {odds.get('awayWin', 'N/A')}

FOCO DA ANALISE:
1. Forma recente e momentum de ambos os times
2. Historico de confrontos diretos (H2H)
3. Fator mandante (desempenho casa vs fora)
4. Value nas odds oferecidas vs probabilidade calculada

Responda EXCLUSIVAMENTE em JSON:
{{
    "recommendation": "CASA|EMPATE|FORA|NO_BET",
    "confidence": 0-100,
    "key_points": ["ponto 1", "ponto 2", "ponto 3"],
    "value_assessment": "Odds com value? Sim/Nao e por que"
}}"""

    @staticmethod
    def build_over_under_prompt(home_team: str, away_team: str, stats: dict, odds: dict) -> str:
        """Prompt focado em Over/Under: lambda, xG, ritmo de jogo, gols por tempo."""
        return f"""Voce e um analista profissional de apostas esportivas. Analise EXCLUSIVAMENTE o mercado Over/Under gols.

JOGO: {home_team} vs {away_team}

DADOS RELEVANTES:
- Lambda Casa: {stats.get('lambdaHome', 'N/A')} gols | Lambda Fora: {stats.get('lambdaAway', 'N/A')} gols
- xG medio/jogo: {home_team} {stats.get('homeXgForAvg', 'N/A')} vs {away_team} {stats.get('awayXgForAvg', 'N/A')}
- Media gols total/jogo: {home_team} {stats.get('homeAvgTotalGoals', 'N/A')} vs {away_team} {stats.get('awayAvgTotalGoals', 'N/A')}
- Over 2.5 %: {home_team} {stats.get('homeOver25Percentage', 'N/A')}% vs {away_team} {stats.get('awayOver25Percentage', 'N/A')}%
- Liga avg gols: {stats.get('leagueAvgGoals', 'N/A')}
- Chaos Score: {stats.get('chaosScore', 'N/A')}

ODDS:
- Over 2.5: {odds.get('over25', 'N/A')} | Under 2.5: {odds.get('under25', 'N/A')}
- Over 3.5: {odds.get('over35', 'N/A')} | Under 3.5: {odds.get('under35', 'N/A')}

FOCO DA ANALISE:
1. Os lambdas sao coerentes com xG e historico de gols?
2. Ritmo de jogo (finalizacoes, posse ofensiva)
3. Distribuicao temporal de gols (1o vs 2o tempo)
4. Value nas odds oferecidas

Responda EXCLUSIVAMENTE em JSON:
{{
    "recommendation": "OVER_25|UNDER_25|OVER_35|UNDER_35|NO_BET",
    "confidence": 0-100,
    "key_points": ["ponto 1", "ponto 2", "ponto 3"],
    "lambda_assessment": "Os lambdas estao adequados? Justifique"
}}"""

    @staticmethod
    def build_btts_prompt(home_team: str, away_team: str, stats: dict, odds: dict) -> str:
        """Prompt focado em BTTS: clean sheets, failed to score, equilibrio ofensivo/defensivo."""
        return f"""Voce e um analista profissional de apostas esportivas. Analise EXCLUSIVAMENTE o mercado BTTS (Ambos Marcam).

JOGO: {home_team} vs {away_team}

DADOS RELEVANTES:
- BTTS %: {home_team} {stats.get('homeBttsPercentage', 'N/A')}% vs {away_team} {stats.get('awayBttsPercentage', 'N/A')}%
- Clean Sheet %: {home_team} {stats.get('homeCleanSheetPct', 'N/A')}% vs {away_team} {stats.get('awayCleanSheetPct', 'N/A')}%
- Faltou Marcar (FTS) %: {home_team} {stats.get('homeFtsPercentage', 'N/A')}% vs {away_team} {stats.get('awayFtsPercentage', 'N/A')}%
- Gols marcados/jogo: {home_team} {stats.get('homeScoredAvg', 'N/A')} vs {away_team} {stats.get('awayScoredAvg', 'N/A')}
- Gols sofridos/jogo: {home_team} {stats.get('homeConcededAvg', 'N/A')} vs {away_team} {stats.get('awayConcededAvg', 'N/A')}
- Chaos Score: {stats.get('chaosScore', 'N/A')}

ODDS:
- BTTS Sim: {odds.get('bttsYes', 'N/A')} | BTTS Nao: {odds.get('bttsNo', 'N/A')}

FOCO DA ANALISE:
1. Equilibrio ofensivo/defensivo de ambos os times
2. Historico de clean sheets vs capacidade de marcar
3. Times que falham em marcar — qual frequencia?
4. Value nas odds oferecidas

Responda EXCLUSIVAMENTE em JSON:
{{
    "recommendation": "BTTS_SIM|BTTS_NAO|NO_BET",
    "confidence": 0-100,
    "key_points": ["ponto 1", "ponto 2", "ponto 3"],
    "defensive_assessment": "Analise do equilibrio defesa/ataque"
}}"""

    @staticmethod
    def build_corners_prompt(home_team: str, away_team: str, stats: dict, odds: dict) -> str:
        """Prompt focado em Corners: corners for/against, shots, possession, estilo tatico."""
        return f"""Voce e um analista profissional de apostas esportivas. Analise EXCLUSIVAMENTE o mercado de Escanteios (Corners).

JOGO: {home_team} vs {away_team}

DADOS RELEVANTES:
- Escanteios/jogo: {home_team} {stats.get('homeCornersPerMatch', 'N/A')} vs {away_team} {stats.get('awayCornersPerMatch', 'N/A')}
- Escanteios sofridos/jogo: {home_team} {stats.get('homeCornersAgainstPerMatch', 'N/A')} vs {away_team} {stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Posse de bola: {home_team} {stats.get('homePossession', 'N/A')}% vs {away_team} {stats.get('awayPossession', 'N/A')}%
- Finalizacoes/jogo: {home_team} {stats.get('homeShotsPerMatch', 'N/A')} vs {away_team} {stats.get('awayShotsPerMatch', 'N/A')}
- Corners projetados FT: {stats.get('projectedTotalCornersFT', 'N/A')}
- Corners projetados 1H: {stats.get('projectedTotalCorners1H', 'N/A')}
- Liga avg corners: {stats.get('leagueAvgCorners', 'N/A')}
- Chaos Score: {stats.get('chaosScore', 'N/A')}

FOCO DA ANALISE:
1. Estilo tatico: times que pressionam alto geram mais escanteios?
2. Posse + finalizacoes indicam pressao ofensiva?
3. Escanteios sofridos — indica defesa reativa (bloqueia com corners)?
4. Linha projetada vs odds oferecidas

Responda EXCLUSIVAMENTE em JSON:
{{
    "recommendation": "OVER|UNDER|NO_BET",
    "line": 9.5,
    "confidence": 0-100,
    "key_points": ["ponto 1", "ponto 2", "ponto 3"],
    "tactical_assessment": "Analise do estilo tatico e impacto nos escanteios"
}}"""


def _format_market_reference_stats(stats: dict | None) -> str:
    """Format market_reference_stats for inclusion in Mistral prompt."""
    if not stats:
        return "Nenhum dado de sinal estrutural disponivel nesta rodada."
    capped = stats.get("capped_by_market_reference_count", 0)
    s2n = stats.get("safe_to_neutro_by_signal_count", 0)
    blocked = stats.get("safe_blocked_by_restrito_count", 0)
    if capped == 0:
        return "Nenhum pick foi limitado pelo sinal estrutural nesta rodada."
    return (
        f"- Picks limitados pelo sinal estrutural: {capped}\n"
        f"        - SAFE rebaixado para NEUTRO (sinal NEUTRO): {s2n}\n"
        f"        - SAFE bloqueado por RESTRITO: {blocked}"
    )
