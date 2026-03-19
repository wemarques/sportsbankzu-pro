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

DADOS AVANCADOS DO SISTEMA:
- xG Casa: {stats.get('homeXgForAvg', stats.get('xg_home', 'N/A'))}
- xG Fora: {stats.get('awayXgForAvg', stats.get('xg_away', 'N/A'))}
- Chutes/Jogo Casa: {stats.get('homeShotsPerMatch', 'N/A')}
- Chutes/Jogo Fora: {stats.get('awayShotsPerMatch', 'N/A')}
- Posse Casa: {stats.get('homePossession', 'N/A')}%
- Posse Fora: {stats.get('awayPossession', 'N/A')}%
- Escanteios/Jogo Casa: {stats.get('homeCornersPerMatch', 'N/A')}
- Escanteios/Jogo Fora: {stats.get('awayCornersPerMatch', 'N/A')}
- Escanteios Contra Casa: {stats.get('homeCornersAgainstPerMatch', 'N/A')}
- Escanteios Contra Fora: {stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Chaos Detectado: {stats.get('chaosDetected', False)}
- Regime da Liga: {stats.get('leagueRegime', 'N/A')}
- Volatilidade: {stats.get('leagueVolatility', 'N/A')}
"""

    # Corner odds from bookmakers
    corner_odds = []
    for line in ["85", "95", "105", "115"]:
        odd = odds.get(f"cornersOver{line}")
        if odd:
            corner_odds.append(f"Over {line[0]}.{line[1]} = {odd}")
    if corner_odds:
        prompt += "\nODDS DE ESCANTEIOS:\n"
        prompt += "\n".join(f"- {o}" for o in corner_odds)
        prompt += "\n"

    if context:
        prompt += f"""
CONTEXTO ADICIONAL:
- Forma Casa: {context.get('home_form', 'N/A')}
- Forma Fora: {context.get('away_form', 'N/A')}
- Confrontos diretos: {context.get('h2h', 'N/A')}
"""
        # Injuries from API-Football
        injuries = context.get('injuries', {})
        if injuries:
            home_inj = injuries.get('home', [])
            away_inj = injuries.get('away', [])
            if home_inj:
                names = [f"{i.get('player', {}).get('name', '?')} ({i.get('player', {}).get('type', '?')})" for i in home_inj[:5]]
                prompt += f"- Lesoes/Suspensoes Casa: {', '.join(names)}\n"
            if away_inj:
                names = [f"{i.get('player', {}).get('name', '?')} ({i.get('player', {}).get('type', '?')})" for i in away_inj[:5]]
                prompt += f"- Lesoes/Suspensoes Fora: {', '.join(names)}\n"
            else:
                prompt += "- Lesoes/Suspensoes: Sem informacoes disponiveis\n"

        # Lineups
        lineups = context.get('lineups')
        if lineups:
            prompt += "- Escalacoes confirmadas: Sim\n"
        else:
            prompt += "- Escalacoes: Nao confirmadas\n"

    # Pipeline v2 predictions (reason codes + EV)
    predictions = context.get('predictions', []) if context else []
    if predictions:
        prompt += "\nMERCADOS SELECIONADOS PELO SISTEMA:\n"
        for p in predictions[:5]:
            line = f"- {p.get('mercado', '?')}: {p.get('status', '?')} ({p.get('prob_min', '?')}-{p.get('prob_max', '?')}%)"
            if p.get('ev') is not None:
                line += f" EV={p['ev']:.1%}"
            if p.get('reason_codes'):
                line += f" [{', '.join(str(r) for r in p['reason_codes'][:3])}]"
            prompt += line + "\n"

    prompt += """
Com base nesses dados, forneca uma analise OBJETIVA no seguinte formato JSON:

{
  "summary": "Resumo de 2-3 frases sobre o jogo, incluindo projecao de escanteios se relevante",
  "key_points": [
    "Ponto sobre gols/resultado",
    "Ponto sobre BTTS/Under/Over",
    "Ponto sobre escanteios se os dados forem relevantes",
    "Ponto sobre contexto tatico/lesoes",
    "Ponto sobre valor nas odds"
  ],
  "recommendation": "Recomendacao com mercado e odd REAL. Pode recomendar mercado de gols OU escanteios. NUNCA invente odds. Use as odds fornecidas.",
  "confidence": 75
}

REGRAS:
- Use APENAS odds fornecidas nos dados acima. NUNCA invente odds.
- Se houver dados de escanteios relevantes, inclua na analise.
- Se o sistema detectou chaos, mencione isso como fator de risco.
- Se houver lesoes de jogadores-chave, avalie o impacto.
- Retorne APENAS o JSON, sem texto adicional.
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
