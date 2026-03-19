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

OFENSIVOS:
- xG Casa: {stats.get('homeXgForAvg', stats.get('xg_home', 'N/A'))}
- xG Fora: {stats.get('awayXgForAvg', stats.get('xg_away', 'N/A'))}
- xG Sofrido Casa: {stats.get('homeXgAgainstAvg', 'N/A')}
- xG Sofrido Fora: {stats.get('awayXgAgainstAvg', 'N/A')}
- Chutes/Jogo Casa: {stats.get('homeShotsPerMatch', 'N/A')}
- Chutes/Jogo Fora: {stats.get('awayShotsPerMatch', 'N/A')}
- Chutes no Alvo Casa: {stats.get('homeShotsOnTarget', 'N/A')}
- Chutes no Alvo Fora: {stats.get('awayShotsOnTarget', 'N/A')}
- Media Total Gols/Jogo Casa: {stats.get('homeAvgTotalGoals', 'N/A')}
- Media Total Gols/Jogo Fora: {stats.get('awayAvgTotalGoals', 'N/A')}

DEFENSIVOS:
- Clean Sheet Casa: {stats.get('homeCleanSheetPct', 'N/A')}%
- Clean Sheet Fora: {stats.get('awayCleanSheetPct', 'N/A')}%
- Failed To Score Casa: {stats.get('homeFtsPercentage', 'N/A')}%
- Failed To Score Fora: {stats.get('awayFtsPercentage', 'N/A')}%

PERCENTUAIS POR TIME:
- Vitoria Casa: {stats.get('homeWinPercentage', 'N/A')}%
- Vitoria Fora: {stats.get('awayWinPercentage', 'N/A')}%
- Over 2.5 Casa: {stats.get('homeOver25Percentage', 'N/A')}%
- Over 2.5 Fora: {stats.get('awayOver25Percentage', 'N/A')}%
- BTTS Casa: {stats.get('homeBttsPercentage', 'N/A')}%
- BTTS Fora: {stats.get('awayBttsPercentage', 'N/A')}%

ESCANTEIOS:
- Escanteios/Jogo Casa: {stats.get('homeCornersPerMatch', 'N/A')}
- Escanteios/Jogo Fora: {stats.get('awayCornersPerMatch', 'N/A')}
- Escanteios Contra Casa: {stats.get('homeCornersAgainstPerMatch', 'N/A')}
- Escanteios Contra Fora: {stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Potencial Over 8.5 Corners: {stats.get('cornerOver85Prob', 'N/A')}%
- Potencial Over 9.5 Corners: {stats.get('cornerOver95Prob', 'N/A')}%
- Potencial Over 10.5 Corners: {stats.get('cornerOver105Prob', 'N/A')}%

CARTOES E FALTAS:
- Cartoes/Jogo Casa: {stats.get('homeCardsPerMatch', 'N/A')}
- Cartoes/Jogo Fora: {stats.get('awayCardsPerMatch', 'N/A')}
- Faltas/Jogo Casa: {stats.get('homeFoulsPerMatch', 'N/A')}
- Faltas/Jogo Fora: {stats.get('awayFoulsPerMatch', 'N/A')}

POSSE E CONTROLE:
- Posse Casa: {stats.get('homePossession', 'N/A')}%
- Posse Fora: {stats.get('awayPossession', 'N/A')}%

MEDIAS DA LIGA:
- Media Gols Liga: {stats.get('leagueAvgGoals', 'N/A')}
- Media Escanteios Liga: {stats.get('leagueAvgCorners', 'N/A')}
- Media Cartoes Liga: {stats.get('leagueAvgCards', 'N/A')}
- Media Faltas Liga: {stats.get('leagueAvgFouls', 'N/A')}
- Clean Sheets Liga: {stats.get('leagueCleanSheetsPct', 'N/A')}%
- Over 2.5 Liga: {stats.get('leagueOver25Pct', 'N/A')}%
- xG Medio Liga: {stats.get('leagueXgAvg', 'N/A')}
- Vantagem Casa Liga: {stats.get('leagueHomeAdvantage', 'N/A')}%

POSICAO NA LIGA:
- Posicao Casa: {stats.get('homeLeaguePosition', 'N/A')}
- Posicao Fora: {stats.get('awayLeaguePosition', 'N/A')}

INDICADORES DO SISTEMA:
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
  "summary": "Resumo de 2-3 frases cobrindo: resultado provavel, tendencia de gols, e destaque de escanteios ou cartoes se relevante",
  "key_points": [
    "Ponto sobre resultado 1X2 (usar win%, posicao na liga, forma)",
    "Ponto sobre gols Over/Under (usar lambda, Over 2.5%, media total gols)",
    "Ponto sobre BTTS (usar BTTS%, clean sheet%, FTS%)",
    "Ponto sobre escanteios (usar corners/jogo, corners contra, potenciais, media liga)",
    "Ponto sobre cartoes e disciplina (usar cards/jogo, fouls/jogo, media liga) OU valor nas odds"
  ],
  "recommendation": "Recomendacao com mercado e odd REAL. Pode ser gols, BTTS, escanteios ou cartoes. NUNCA invente odds. Use APENAS as odds fornecidas nos dados.",
  "confidence": 75
}

REGRAS:
- Use APENAS odds fornecidas nos dados acima. NUNCA invente odds.
- Se dados de escanteios estiverem disponiveis (nao N/A), INCLUA analise de corners nos pontos-chave.
- Se dados de cartoes estiverem disponiveis (nao N/A), INCLUA analise de disciplina.
- Compare os dados do time com as medias da liga para contextualizar.
- Se o sistema detectou chaos, mencione como fator de risco.
- Se houver lesoes de jogadores-chave, avalie o impacto.
- Se Clean Sheet% for alto para algum time, destaque no contexto de BTTS.
- Se Failed To Score% for alto, destaque no contexto de Under.
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
