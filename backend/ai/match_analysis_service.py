"""
Serviço de análise de jogos para o card de detalhe (formato MatchDetailCard).
Usa MistralClient existente para gerar summary, key_points, recommendation, confidence.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.ai.mistral_client import MistralClient

logger = logging.getLogger("sportsbankzu.ai.match_analysis")


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        return text.strip()
    return text


def analyze_match(
    home_team: str,
    away_team: str,
    league: str,
    stats: Optional[Dict[str, Any]] = None,
    odds: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    client: Optional[MistralClient] = None,
) -> Dict[str, Any]:
    """
    Gera análise no formato esperado pelo MatchDetailCard.
    Retorna: { summary, key_points, recommendation, confidence, last_updated }
    """
    stats = stats or {}
    odds = odds or {}
    client = client or MistralClient(model="mistral-small-latest")

    prompt = f"""Você é um analista profissional de apostas esportivas especializado em futebol.

JOGO: {home_team} vs {away_team}
COMPETIÇÃO: {league}

ESTATÍSTICAS DO JOGO:
- Lambda Casa: {stats.get('lambdaHome', stats.get('lambda_home', 'N/A'))}
- Lambda Fora: {stats.get('lambdaAway', stats.get('lambda_away', 'N/A'))}
- Probabilidade Casa: {stats.get('homeWinProb', stats.get('prob_home', 'N/A'))}%
- Probabilidade Empate: {stats.get('drawProb', stats.get('prob_draw', 'N/A'))}%
- Probabilidade Fora: {stats.get('awayWinProb', stats.get('prob_away', 'N/A'))}%
- Probabilidade Over 2.5: {stats.get('over25Prob', stats.get('prob_over_25', 'N/A'))}%
- Probabilidade BTTS: {stats.get('bttsProb', stats.get('prob_btts', 'N/A'))}%

ODDS DO MERCADO (SOMENTE estas odds estao disponiveis — NAO invente odds):
- Casa (1): {odds.get('home', 'N/A')}
- Empate (X): {odds.get('draw', 'N/A')}
- Fora (2): {odds.get('away', 'N/A')}
- Over 1.5: {odds.get('over15', 'N/A')}
- Over 2.5: {odds.get('over25', 'N/A')}
- Over 3.5: {odds.get('over35', 'N/A')}
- Over 4.5: {odds.get('over45', 'N/A')}
- Under 2.5: {odds.get('under25', 'N/A')}
- BTTS Sim: {odds.get('bttsYes', 'N/A')}
- BTTS Nao: {odds.get('bttsNo', 'N/A')}
"""

    if context:
        prompt += f"""
CONTEXTO ADICIONAL:
- Forma Casa: {context.get('home_form', 'N/A')}
- Forma Fora: {context.get('away_form', 'N/A')}
- Confrontos diretos: {context.get('h2h', 'N/A')}
"""

    prompt += """
Com base nesses dados, forneça uma análise OBJETIVA no seguinte formato JSON:

{
  "summary": "Resumo de 2-3 frases sobre o jogo",
  "key_points": [
    "Ponto-chave 1",
    "Ponto-chave 2",
    "Ponto-chave 3",
    "Ponto-chave 4",
    "Ponto-chave 5"
  ],
  "recommendation": "Recomendacao de aposta com mercado e odd REAL das ODDS DO MERCADO acima. NUNCA invente odds. Ex: Over 2.5 @2.07",
  "confidence": 75
}

Retorne APENAS o JSON, sem texto adicional.
"""

    system = "Você é um gerador estrito de JSON. Responda somente JSON válido, sem markdown."

    try:
        raw = client.simple_prompt(prompt, system_prompt=system)
        cleaned = _strip_json_fences(raw)
        data = json.loads(cleaned)

        return {
            "summary": data.get("summary", "Análise gerada."),
            "key_points": data.get("key_points", [])[:5],
            "recommendation": data.get("recommendation", "Consulte as estatísticas."),
            "confidence": min(max(int(data.get("confidence", 50)), 0), 100),
            "last_updated": datetime.now().strftime("%d/%m/%Y às %H:%M"),
        }
    except Exception as e:
        logger.error(f"Erro na análise Mistral para {home_team} vs {away_team}: {e}")
        return _fallback_analysis()


def _fallback_analysis() -> Dict[str, Any]:
    return {
        "summary": "Análise temporariamente indisponível. Verifique MISTRAL_API_KEY na Lambda.",
        "key_points": [
            "Serviço de análise AI indisponível no momento",
            "Consulte as estatísticas e odds apresentadas",
            "Analise o histórico de confrontos diretos",
            "Considere a forma recente das equipes",
            "Tome decisões com base nos dados disponíveis",
        ],
        "recommendation": "Aguarde o restabelecimento do serviço ou analise os dados manualmente.",
        "confidence": 0,
        "last_updated": datetime.now().strftime("%d/%m/%Y às %H:%M"),
    }
