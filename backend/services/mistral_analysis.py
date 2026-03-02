# backend/services/mistral_analysis.py
"""
Servico de analise de jogos usando MISTRAL AI
"""
import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

try:
    import httpx
except Exception:
    httpx = None  # type: ignore

from pydantic import BaseModel, Field

from backend.ai.mistral_client import MistralClient
from backend.ai.cache_manager import CacheManager

logger = logging.getLogger("sportsbankzu.ai.analysis")


class AIAnalysisResponse(BaseModel):
    """Modelo de resposta da analise AI"""

    summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    recommendation: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    last_updated: str = ""


class MistralAnalysisService:
    """Servico para analise de jogos com MISTRAL AI.

    Supports two modes:
    - Direct httpx call to Mistral REST API (when MISTRAL_API_KEY is set)
    - Fallback via existing MistralClient wrapper
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.base_url = "https://api.mistral.ai/v1"
        self.model = "mistral-small-latest"
        self.client = MistralClient()
        self.cache = CacheManager(ttl_hours=6)

    async def analyze_match(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict] = None,
    ) -> AIAnalysisResponse:
        """
        Gera analise completa de um jogo usando MISTRAL AI.

        Args:
            home_team: Nome do time da casa
            away_team: Nome do time visitante
            league: Nome da liga/competicao
            match_stats: Estatisticas do jogo (lambda, probabilidades, etc)
            odds: Odds do mercado
            context: Contexto adicional (forma recente, lesoes, etc)

        Returns:
            AIAnalysisResponse com a analise completa
        """
        # Check cache
        cached = self.cache.get("analysis", home_team, away_team)
        if cached:
            logger.info(f"Cache hit for analysis: {home_team} vs {away_team}")
            return AIAnalysisResponse(**cached)

        prompt = self._build_prompt(
            home_team, away_team, league, match_stats, odds, context
        )

        try:
            analysis = await self._call_mistral_api(prompt)
            result = self._parse_analysis(analysis)
            self.cache.set("analysis", home_team, away_team, result.model_dump())
            return result
        except Exception as e:
            logger.error(f"Mistral analysis error for {home_team} vs {away_team}: {e}")
            # Fallback: try sync client
            try:
                return self._analyze_sync(prompt, home_team, away_team)
            except Exception:
                return self._get_fallback_analysis()

    def _analyze_sync(
        self, prompt: str, home_team: str, away_team: str
    ) -> AIAnalysisResponse:
        """Fallback synchronous analysis via MistralClient wrapper."""
        response_text = self.client.simple_prompt(
            prompt,
            system_prompt="Voce e um analista esportivo profissional. Responda apenas em JSON valido.",
        )
        result = self._parse_analysis(response_text)
        self.cache.set("analysis", home_team, away_team, result.model_dump())
        return result

    def analyze_match_sync(self, match_data: Dict) -> AIAnalysisResponse:
        """Synchronous version for non-async contexts."""
        home = match_data.get("home_team") or match_data.get("homeTeam", "Home")
        away = match_data.get("away_team") or match_data.get("awayTeam", "Away")
        league = match_data.get("league") or match_data.get("leagueName", "")
        stats = match_data.get("stats", {})
        odds = match_data.get("odds", {})
        context = match_data.get("context")

        # Check cache
        cached = self.cache.get("analysis", home, away)
        if cached:
            logger.info(f"Cache hit for analysis: {home} vs {away}")
            return AIAnalysisResponse(**cached)

        prompt = self._build_prompt(home, away, league, stats, odds, context)
        try:
            return self._analyze_sync(prompt, home, away)
        except Exception as e:
            logger.error(f"Sync analysis error: {e}")
            return self._get_fallback_analysis()

    def _format_prob_for_prompt(self, value) -> str:
        """Normaliza e formata probabilidade para o prompt (0-1, 0-100 ou >100 -> X.X%)."""
        if value is None:
            return "N/A"
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if v < 0:
            return "N/A"
        if v <= 1:
            v *= 100
        elif v > 100:
            v /= 100
        return f"{v:.1f}"

    def _build_prompt(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict] = None,
    ) -> str:
        """Constroi o prompt para a MISTRAL AI"""
        prob_home = self._format_prob_for_prompt(
            match_stats.get("prob_home") or match_stats.get("homeWinProb")
        )
        prob_draw = self._format_prob_for_prompt(
            match_stats.get("prob_draw") or match_stats.get("drawProb")
        )
        prob_away = self._format_prob_for_prompt(
            match_stats.get("prob_away") or match_stats.get("awayWinProb")
        )
        prob_over25 = self._format_prob_for_prompt(
            match_stats.get("prob_over_25") or match_stats.get("over25Prob")
        )
        prob_btts = self._format_prob_for_prompt(
            match_stats.get("prob_btts") or match_stats.get("bttsProb")
        )

        # Team comparison stats
        def _stat(key: str) -> str:
            val = match_stats.get(key)
            if val is None:
                return "N/A"
            try:
                return f"{float(val):.1f}"
            except (TypeError, ValueError):
                return "N/A"

        prompt = f"""Voce e um analista profissional de apostas esportivas especializado em futebol.

JOGO: {home_team} vs {away_team}
COMPETICAO: {league}

PROGNOSTICOS (valores JA em porcentagem 0-100 — use EXATAMENTE como mostrado, ex: 85.5%):
- Probabilidade Vitoria Casa: {prob_home}%
- Probabilidade Empate: {prob_draw}%
- Probabilidade Vitoria Fora: {prob_away}%
- Probabilidade Over 2.5: {prob_over25}%
- Probabilidade BTTS: {prob_btts}%

LAMBDAS (taxa media de gols esperados — NAO sao probabilidades, sao contagens):
- Lambda Casa: {match_stats.get('lambda_home') or match_stats.get('lambdaHome', 'N/A')} gols
- Lambda Fora: {match_stats.get('lambda_away') or match_stats.get('lambdaAway', 'N/A')} gols

COMPARATIVO TIMES (medias por jogo na temporada):
- Posse de bola: {home_team} {_stat('homePossession')}% vs {away_team} {_stat('awayPossession')}%
- Escanteios/jogo: {home_team} {_stat('homeCornersPerMatch')} vs {away_team} {_stat('awayCornersPerMatch')}
- Escanteios sofridos/jogo: {home_team} {_stat('homeCornersAgainstPerMatch')} vs {away_team} {_stat('awayCornersAgainstPerMatch')}
- Cartoes/jogo: {home_team} {_stat('homeCardsPerMatch')} vs {away_team} {_stat('awayCardsPerMatch')}
- Finalizacoes/jogo: {home_team} {_stat('homeShotsPerMatch')} vs {away_team} {_stat('awayShotsPerMatch')}
- Chutes ao gol/jogo: {home_team} {_stat('homeShotsOnTarget')} vs {away_team} {_stat('awayShotsOnTarget')}
- Faltas/jogo: {home_team} {_stat('homeFoulsPerMatch')} vs {away_team} {_stat('awayFoulsPerMatch')}

PERFIL DE GOLS (medias na temporada):
- xG medio/jogo: {home_team} {_stat('homeXgForAvg')} vs {away_team} {_stat('awayXgForAvg')}
- xG sofrido/jogo: {home_team} {_stat('homeXgAgainstAvg')} vs {away_team} {_stat('awayXgAgainstAvg')}
- Media gols total/jogo: {home_team} {_stat('homeAvgTotalGoals')} vs {away_team} {_stat('awayAvgTotalGoals')}
- Over 2.5 %: {home_team} {_stat('homeOver25Percentage')}% vs {away_team} {_stat('awayOver25Percentage')}%
- BTTS %: {home_team} {_stat('homeBttsPercentage')}% vs {away_team} {_stat('awayBttsPercentage')}%
- Clean Sheet %: {home_team} {_stat('homeCleanSheetPct')}% vs {away_team} {_stat('awayCleanSheetPct')}%
- Faltou Marcar (FTS) %: {home_team} {_stat('homeFtsPercentage')}% vs {away_team} {_stat('awayFtsPercentage')}%

CLASSIFICACAO E DESEMPENHO:
- Posicao na liga: {home_team} {_stat('homeLeaguePosition')}o vs {away_team} {_stat('awayLeaguePosition')}o
- % Vitoria na temporada: {home_team} {_stat('homeWinPercentage')}% vs {away_team} {_stat('awayWinPercentage')}%

ODDS DO MERCADO:
- Casa (1): {odds.get('home', 'N/A')}
- Empate (X): {odds.get('draw', 'N/A')}
- Fora (2): {odds.get('away', 'N/A')}
- Over 2.5: {odds.get('over_25') or odds.get('over25', 'N/A')}
- BTTS Sim: {odds.get('btts_yes') or odds.get('bttsYes', 'N/A')}
"""

        if context:
            prompt += f"""
CONTEXTO ADICIONAL:
- Forma Casa (ultimos 5): {context.get('home_form', 'N/A')}
- Forma Fora (ultimos 5): {context.get('away_form', 'N/A')}
- Confrontos diretos: {context.get('h2h', 'N/A')}
- Lesoes/Suspensoes: {context.get('absences', 'Nenhuma informacao')}
"""
            if context.get("footystats_analysis"):
                prompt += f"""
ANALISE FOOTYSTATS (dados reais de forma recente, BTTS, clean sheets, streaks, H2H):
{context['footystats_analysis']}

IMPORTANTE: Use os dados da analise FootyStats acima como fonte primaria para forma recente,
tendencias de BTTS, clean sheets e confrontos diretos. NAO invente dados de forma.
"""

        prompt += """
Com base nesses dados, forneca uma analise OBJETIVA e ESTRUTURADA no seguinte formato JSON:

{
  "summary": "Um resumo de 2-3 frases sobre o jogo, destacando os principais pontos",
  "key_points": [
    "Ponto-chave 1 com dados especificos",
    "Ponto-chave 2 com dados especificos",
    "Ponto-chave 3 com dados especificos",
    "Ponto-chave 4 com dados especificos",
    "Ponto-chave 5 com dados especificos"
  ],
  "recommendation": "Recomendacao clara de aposta com mercado, odd e justificativa",
  "confidence": 75
}

IMPORTANTE:
- Seja especifico e use os numeros fornecidos EXATAMENTE como mostrados (ex: 85.5% significa 85.5%, NAO multiplique por 100)
- Use SEMPRE probabilidades em porcentagem (%) nos prognosticos, NAO use valores lambda como prognostico
- Lambdas sao taxas de gols esperados (ex: 1.5 gols), NAO probabilidades de resultado
- Exemplo correto: "probabilidade de vitoria de 85.5%". Exemplo INCORRETO: "8547.4%" ou "Casa (1.177) vs Fora (0.996)"
- Use os dados do COMPARATIVO TIMES e PERFIL DE GOLS para fundamentar sua analise:
  * xG alto + clean sheet baixo = time ofensivo mas vulneravel defensivamente
  * BTTS% alto de ambos = forte indicador de ambas marcam
  * FTS% alto = time nao marca com frequencia, considerar BTTS Nao
  * Over 2.5% dos dois times alto = tendencia a jogos com muitos gols
  * Escanteios contra/jogo alto do adversario = time pressiona muito, gera mais corners
  * Posicao na liga indica forca relativa dos times
- A confianca (confidence) deve ser um numero de 0-100
- Forneca 5 pontos-chave
- A recomendacao deve incluir o mercado e a odd especifica
- Retorne APENAS o JSON, sem texto adicional
"""
        return prompt

    async def _call_mistral_api(self, prompt: str) -> str:
        """Chama a API da MISTRAL via httpx"""
        if not httpx or not self.api_key:
            raise RuntimeError("httpx not available or API key missing")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1000,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _parse_analysis(self, raw_response: str) -> AIAnalysisResponse:
        """Parse da resposta da MISTRAL para o modelo estruturado"""
        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Handle potential fenced JSON
            if "```" in cleaned:
                import re

                match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL
                )
                if match:
                    cleaned = match.group(1).strip()

            data = json.loads(cleaned)

            return AIAnalysisResponse(
                summary=data.get("summary", ""),
                key_points=data.get("key_points", [])[:5],
                recommendation=data.get("recommendation", ""),
                confidence=min(max(int(data.get("confidence", 50)), 0), 100),
                last_updated=datetime.now().strftime("%d/%m/%Y as %H:%M"),
            )
        except Exception as e:
            logger.error(f"Error parsing Mistral response: {e}")
            return self._get_fallback_analysis()

    def _get_fallback_analysis(self) -> AIAnalysisResponse:
        """Retorna analise padrao em caso de erro"""
        return AIAnalysisResponse(
            summary="Analise temporariamente indisponivel. Por favor, tente novamente em alguns instantes.",
            key_points=[
                "Servico de analise AI temporariamente indisponivel",
                "Recomendamos analisar as estatisticas manualmente",
                "Verifique as probabilidades e odds apresentadas",
                "Consulte o historico de confrontos diretos",
                "Considere a forma recente das equipes",
            ],
            recommendation="Aguarde restabelecimento do servico de analise AI ou consulte as estatisticas disponiveis para tomar sua decisao.",
            confidence=0,
            last_updated=datetime.now().strftime("%d/%m/%Y as %H:%M"),
        )
