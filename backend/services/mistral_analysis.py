# backend/services/mistral_analysis.py
"""
Servico de analise de jogos usando MISTRAL AI
"""
import os
import json
import logging
import re
from typing import Dict, List, Optional
from datetime import datetime
from backend.services.util_service import team_name

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
    match_live_data: Optional[Dict] = Field(default=None, description="Live match data from API-Football (status, score, injuries)")


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
            result = self._parse_analysis(analysis, odds)
            self.cache.set("analysis", home_team, away_team, result.model_dump())
            return result
        except Exception as e:
            logger.error(f"Mistral analysis error for {home_team} vs {away_team}: {e}")
            # Fallback: try sync client
            try:
                return self._analyze_sync(prompt, home_team, away_team, odds)
            except Exception:
                return self._get_fallback_analysis()

    def _analyze_sync(
        self, prompt: str, home_team: str, away_team: str, odds: Optional[Dict] = None
    ) -> AIAnalysisResponse:
        """Fallback synchronous analysis via MistralClient wrapper."""
        response_text = self.client.simple_prompt(
            prompt,
            system_prompt="Voce e um analista esportivo profissional. Responda apenas em JSON valido.",
        )
        result = self._parse_analysis(response_text, odds)
        self.cache.set("analysis", home_team, away_team, result.model_dump())
        return result

    def analyze_match_sync(self, match_data: Dict) -> AIAnalysisResponse:
        """Synchronous version for non-async contexts."""
        home = team_name(match_data.get("home_team") or match_data.get("homeTeam", "Home"))
        away = team_name(match_data.get("away_team") or match_data.get("awayTeam", "Away"))
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
            return self._analyze_sync(prompt, home, away, odds)
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

    @staticmethod
    def _derive_under_odd(odds: Dict, over_key: str, under_key: str) -> str:
        """Derive Under odd from Over odd if not directly available.

        Uses the complementary market formula: under = 1 / (1 - 1/over)
        with a 5% margin adjustment similar to market_service.calcular_odd_under.
        """
        # Check if explicitly provided first
        val = odds.get(under_key)
        if val is not None:
            try:
                return str(round(float(val), 2))
            except (TypeError, ValueError):
                pass
        # Derive from over
        over_val = odds.get(over_key)
        if over_val is not None:
            try:
                over_f = float(over_val)
                if over_f > 1.0:
                    implied_under = 1.0 - (1.0 / over_f)
                    if implied_under > 0:
                        raw = 1.0 / implied_under
                        # Apply ~5% margin like real bookmakers
                        adjusted = round(raw * 0.95, 2)
                        return str(adjusted)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return "N/A"

    @staticmethod
    def _format_extended_live_context(
        stats: Dict,
        events: Dict,
        live_data: Dict,
        home_team: str,
        away_team: str,
    ) -> str:
        """Build a dense tactical context string from live statistics and events.

        This string gives Mistral a full X-ray of the match so it can make
        data-driven recommendations instead of defaulting to BTTS.

        Args:
            stats: Output of APIFootballClient.parse_fixture_statistics()
            events: Output of APIFootballClient.parse_fixture_events()
            live_data: Live data dict (status, minute, score, corners, possession)
            home_team: Home team display name
            away_team: Away team display name

        Returns:
            Dense tactical context string.
        """
        parts = []

        # -- Status line --
        status = live_data.get("status", "NS")
        minute = live_data.get("minute")
        extra = live_data.get("extra_time")
        period_map = {"1H": "1T", "HT": "INT", "2H": "2T", "ET": "PRO", "FT": "FIM", "AET": "FIM+PRO", "PEN": "PEN"}
        period = period_map.get(status, status)
        minute_str = ""
        if minute is not None:
            minute_str = str(minute)
            if extra:
                minute_str += f"+{extra}"

        score = live_data.get("score", "N/A")
        status_line = f"Status: {minute_str} min ({period}). Placar: {home_team} {score} {away_team}."
        parts.append(status_line)

        h = stats.get("home", {})
        a = stats.get("away", {})

        def _v(d: Dict, key: str, default: str = "?") -> str:
            val = d.get(key)
            return str(val) if val is not None else default

        # -- DOMÍNIO --
        if h.get("possession") is not None and a.get("possession") is not None:
            parts.append(f"DOMINIO: Posse ({_v(h, 'possession')}% x {_v(a, 'possession')}%).")

        # -- PRESSÃO OFENSIVA --
        pressure_items = []
        if h.get("shots_on_goal") is not None or a.get("shots_on_goal") is not None:
            pressure_items.append(f"Chutes no Alvo ({_v(h, 'shots_on_goal', '0')} x {_v(a, 'shots_on_goal', '0')})")
        if h.get("shots_inside_box") is not None or a.get("shots_inside_box") is not None:
            pressure_items.append(f"Chutes na Area ({_v(h, 'shots_inside_box', '0')} x {_v(a, 'shots_inside_box', '0')})")
        if h.get("total_shots") is not None or a.get("total_shots") is not None:
            pressure_items.append(f"Finalizacoes Totais ({_v(h, 'total_shots', '0')} x {_v(a, 'total_shots', '0')})")
        if h.get("shots_off_goal") is not None or a.get("shots_off_goal") is not None:
            pressure_items.append(f"Chutes Fora ({_v(h, 'shots_off_goal', '0')} x {_v(a, 'shots_off_goal', '0')})")
        if h.get("corner_kicks") is not None or a.get("corner_kicks") is not None:
            hc = _v(h, 'corner_kicks', '0')
            ac = _v(a, 'corner_kicks', '0')
            try:
                total_c = int(hc) + int(ac)
            except (ValueError, TypeError):
                total_c = "?"
            pressure_items.append(f"Escanteios ({hc} x {ac} = {total_c})")
        if pressure_items:
            parts.append(f"PRESSAO: {', '.join(pressure_items)}.")

        # -- DEFESA --
        defense_items = []
        if h.get("goalkeeper_saves") is not None or a.get("goalkeeper_saves") is not None:
            defense_items.append(f"Defesas do Goleiro ({_v(h, 'goalkeeper_saves', '0')} x {_v(a, 'goalkeeper_saves', '0')})")
        if h.get("shots_blocked") is not None or a.get("shots_blocked") is not None:
            defense_items.append(f"Chutes Bloqueados ({_v(h, 'shots_blocked', '0')} x {_v(a, 'shots_blocked', '0')})")
        if defense_items:
            parts.append(f"DEFESA: {', '.join(defense_items)}.")

        # -- DISCIPLINA --
        discipline_items = []
        if h.get("fouls") is not None or a.get("fouls") is not None:
            discipline_items.append(f"Faltas ({_v(h, 'fouls', '0')} x {_v(a, 'fouls', '0')})")
        if h.get("yellow_cards") is not None or a.get("yellow_cards") is not None:
            discipline_items.append(f"Amarelos ({_v(h, 'yellow_cards', '0')} x {_v(a, 'yellow_cards', '0')})")
        if h.get("red_cards") is not None or a.get("red_cards") is not None:
            discipline_items.append(f"Vermelhos ({_v(h, 'red_cards', '0')} x {_v(a, 'red_cards', '0')})")
        if discipline_items:
            parts.append(f"DISCIPLINA: {', '.join(discipline_items)}.")

        # -- PASSES --
        if h.get("passes_accurate") is not None or a.get("passes_accurate") is not None:
            parts.append(
                f"PASSES: Precisos ({_v(h, 'passes_accurate', '?')} x {_v(a, 'passes_accurate', '?')}), "
                f"Total ({_v(h, 'passes_total', '?')} x {_v(a, 'passes_total', '?')}), "
                f"Acerto ({_v(h, 'passes_pct', '?')}% x {_v(a, 'passes_pct', '?')}%)."
            )

        # -- xG (if available) --
        if h.get("expected_goals") is not None or a.get("expected_goals") is not None:
            parts.append(f"xG AO VIVO: {_v(h, 'expected_goals', '?')} x {_v(a, 'expected_goals', '?')}.")

        # -- EVENTOS CHAVE --
        event_items = []
        for rc in events.get("red_card_events", []):
            event_items.append(f"Cartao Vermelho para {rc.get('team', '?')} ({rc.get('player', '?')}) aos {rc.get('time', '?')} min")
        for g in events.get("goals", []):
            detail = g.get("detail", "")
            assist = f" (assist: {g['assist']})" if g.get("assist") else ""
            event_items.append(f"Gol de {g.get('team', '?')} ({g.get('player', '?')}{assist}) aos {g.get('time', '?')} min{' [P]' if 'Penalty' in detail else ''}")
        if event_items:
            parts.append(f"EVENTOS: {'; '.join(event_items)}.")

        return " ".join(parts)

    def _build_prompt(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict] = None,
        market_type: str = "general",
    ) -> str:
        """Constroi o prompt para a MISTRAL AI.

        When market_type is specified, uses a specialized template that sends
        only the data relevant to that market family.
        """
        # Use specialized prompt if market_type is not generic
        if market_type != "general":
            from backend.ai.prompt_templates import PromptTemplates
            if market_type == "1x2":
                return PromptTemplates.build_1x2_prompt(home_team, away_team, match_stats, odds)
            elif market_type in ("over_under", "under"):
                return PromptTemplates.build_over_under_prompt(home_team, away_team, match_stats, odds)
            elif market_type == "btts":
                return PromptTemplates.build_btts_prompt(home_team, away_team, match_stats, odds)
            elif market_type == "corners":
                return PromptTemplates.build_corners_prompt(home_team, away_team, match_stats, odds)
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

ODDS DO MERCADO (SOMENTE estas odds estao disponiveis — NAO invente odds que nao estejam listadas):
- Casa (1): {odds.get('home', 'N/A')}
- Empate (X): {odds.get('draw', 'N/A')}
- Fora (2): {odds.get('away', 'N/A')}
- Over 1.5: {odds.get('over15', 'N/A')}
- Over 2.5: {odds.get('over_25') or odds.get('over25', 'N/A')}
- Over 3.5: {odds.get('over35', 'N/A')}
- Over 4.5: {odds.get('over45', 'N/A')}
- Under 2.5: {odds.get('under25', 'N/A')}
- Under 3.5: {self._derive_under_odd(odds, 'over35', 'under35')}
- Under 4.5: {self._derive_under_odd(odds, 'over45', 'under45')}
- BTTS Sim: {odds.get('btts_yes') or odds.get('bttsYes', 'N/A')}
- BTTS Nao: {odds.get('btts_no') or odds.get('bttsNo', 'N/A')}
- Escanteios Over 8.5: {odds.get('cornersOver85', 'N/A')}
- Escanteios Over 9.5: {odds.get('cornersOver95', 'N/A')}
- Escanteios Over 10.5: {odds.get('cornersOver105', 'N/A')}
- Escanteios Over 11.5: {odds.get('cornersOver115', 'N/A')}

ATENCAO: Se um mercado acima mostra "N/A", ele NAO esta disponivel. NAO recomende mercados com odd N/A.
Nos key_points, NAO cite odds de mercados que nao estejam listados acima. Cite apenas porcentagens e dados estatisticos.
NAO existem mercados de Double Chance, Cartoes ou Draw No Bet neste sistema — NAO os recomende.
"""

        if context:
            prompt += f"""
CONTEXTO ADICIONAL:
- Forma Casa (ultimos 5): {context.get('home_form', 'N/A')}
- Forma Fora (ultimos 5): {context.get('away_form', 'N/A')}
- Confrontos diretos: {context.get('h2h', 'N/A')}
- Liga/Competicao (API-Football): {context.get('league_info', 'N/A')}
- Lesoes/Suspensoes (API-Football): {context.get('absences', 'Nenhuma informacao')}
  NOTA: [FORA] = desfalque confirmado, [DUVIDA] = presenca incerta — pese o impacto de forma diferente.
- Escalacoes provaveis: {context.get('lineups', 'Nenhuma informacao')}
- Status ao Vivo: {context.get('live_status', 'Sem dados ao vivo')}

RAIO-X TATICO AO VIVO (dados detalhados da partida em andamento):
{context.get('live_data_extended', 'Sem dados taticos ao vivo disponiveis.')}
  NOTA: Use o RAIO-X TATICO para fundamentar CADA recomendacao. Se um time tem 0 ou 1 chute no alvo, ele NAO esta criando perigo real — desconsidere BTTS.
  Compare escanteios totais com as linhas Over (8.5, 9.5, etc) e o tempo restante.
  Chutes na Area e xG ao vivo indicam quem realmente ameaca o gol.
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
- Considere o status da partida (Status ao Vivo). Se o jogo estiver ao vivo, comente sobre o placar atual e como ele impacta a analise.
- Utilize os dados de ausencias (Lesoes/Suspensoes) informados pela API-Football e NUNCA invente lesoes ou suspensoes que nao estejam listadas.
- Se nao houver dados de ausencias, diga apenas que nao ha informacao disponivel — NAO fabrique nomes de jogadores lesionados.
- Seja especifico e use os numeros fornecidos EXATAMENTE como mostrados (ex: 85.5% significa 85.5%, NAO multiplique por 100)
- Use SEMPRE probabilidades em porcentagem (%) nos prognosticos, NAO use valores lambda como prognostico
- Lambdas sao taxas de gols esperados (ex: 1.5 gols), NAO probabilidades de resultado
- Exemplo correto: "probabilidade de vitoria de 85.5%". Exemplo INCORRETO: "8547.4%" ou "Casa (1.177) vs Fora (0.996)"
- Use os dados do COMPARATIVO TIMES e PERFIL DE GOLS para fundamentar sua analise:
  * xG alto + clean sheet baixo = time ofensivo mas vulneravel defensivamente
  * FTS% alto = time nao marca com frequencia, considerar BTTS Nao
  * Over 2.5% dos dois times alto = tendencia a jogos com muitos gols
  * Escanteios contra/jogo alto do adversario = time pressiona muito, gera mais corners
  * Posicao na liga indica forca relativa dos times

REGRA ANTI-VIES BTTS (CRITICO — LEIA COM ATENCAO):
- NAO sugira BTTS (Ambas Marcam) como recomendacao padrao. BTTS so deve ser recomendado quando AMBOS os times demonstram volume ofensivo real.
- Se o RAIO-X TATICO ao vivo estiver disponivel, LEIA-O OBRIGATORIAMENTE antes de recomendar:
  * Se um time tem 0 ou 1 chute no alvo E 0-1 chutes na area: BTTS tem EV+ NEGATIVO. NAO recomende BTTS.
  * Se um time tem 0 finalizacoes totais: esse time NAO vai marcar. Recomende BTTS Nao ou ML do time dominante.
  * Se a posse e > 65% para um lado com muitos chutes no alvo: foque no ML (Money Line) do time dominante ou Over gols.
  * Se ha muitos escanteios (> 6 no total antes dos 60min): considere Escanteios Over como alternativa.
  * Se ha Cartao Vermelho: time com menos jogadores perde volume ofensivo — reconsidere BTTS.
- Foque a analise na ASSIMETRIA do jogo: quem domina posse, finaliza mais e gera mais escanteios e quem provavelmente marcara.
- Priorize estas alternativas ao BTTS quando a assimetria for clara:
  1. ML (Money Line) do time dominante — quando um time controla o jogo
  2. Over gols (1.5, 2.5, 3.5) — quando ha pressao ofensiva de pelo menos um lado
  3. Over Escanteios — quando o ritmo de corners indica tendencia
  4. BTTS Nao — quando um time e claramente inofensivo (0-1 chutes no alvo)
  5. BTTS Sim — SOMENTE quando ambos tem 3+ chutes no alvo e criam perigo real

- A confianca (confidence) deve ser um numero de 0-100
- Forneca 5 pontos-chave
- A recomendacao deve incluir o mercado e a odd especifica
- OBRIGATORIO: o campo "recommendation" DEVE conter uma aposta concreta (ex: "Over 2.5 @1.80" ou "Casa @1.45"). NUNCA diga "indisponivel", "consulte as estatisticas" ou "aguarde". Sempre recomende algo com base nos dados.
- CRITICO: A odd na recomendacao DEVE ser uma das odds listadas em "ODDS DO MERCADO" acima. NAO invente, estime ou arredonde odds. Se a odd de um mercado e "N/A", NAO recomende esse mercado. Escolha APENAS entre mercados com odd numerica disponivel.
- Retorne APENAS o JSON, sem texto adicional
"""
        return prompt

    async def _call_mistral_api(self, prompt: str) -> str:
        """Chama a API da MISTRAL via httpx with retry on transient errors."""
        if not httpx or not self.api_key:
            raise RuntimeError("httpx not available or API key missing")

        import asyncio

        max_retries = 2
        retry_delay = 3.0
        last_exc = None

        for attempt in range(max_retries + 1):
            try:
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
                            "max_tokens": 2048,
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_exc = e
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ("timeout", "timed out", "429", "500", "502", "503", "504", "connection"))
                if is_transient and attempt < max_retries:
                    logger.warning(f"[MistralAnalysis] Transient error (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _sanitize_key_points(key_points: List[str], odds: Dict) -> List[str]:
        """Remove hallucinated odds from key_points.

        Strips patterns like 'odd de 1.95' or 'com odd 1.95' when the value
        doesn't match any real available odd.
        """
        if not key_points or not odds:
            return key_points

        # Collect all real odd values (including derived under odds)
        real_values: set = set()
        for key, val in odds.items():
            if val is not None:
                try:
                    real_values.add(round(float(val), 2))
                except (TypeError, ValueError):
                    pass
        # Derive under odds
        for over_k in ("over35", "over45"):
            ov = odds.get(over_k)
            if ov is not None:
                try:
                    ov_f = float(ov)
                    if ov_f > 1.0:
                        impl = 1.0 - (1.0 / ov_f)
                        if impl > 0:
                            real_values.add(round((1.0 / impl) * 0.95, 2))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        sanitized = []
        for point in key_points:
            # Find all odds mentioned in the key point (e.g. "odd de 1.95", "com odd 1.95", "@1.95")
            for m in re.finditer(r"(?:odd\s+(?:de\s+)?|@\s*)([\d]+[.,][\d]+)", point, re.IGNORECASE):
                mentioned_odd = round(float(m.group(1).replace(",", ".")), 2)
                # Check if this odd is real (within tolerance)
                if not any(abs(mentioned_odd - rv) < 0.02 for rv in real_values):
                    # Strip the hallucinated odd reference
                    point = re.sub(
                        r",?\s*com\s+odd\s+(?:de\s+)?[\d]+[.,][\d]+", "", point, flags=re.IGNORECASE
                    )
                    point = re.sub(
                        r",?\s*odd\s+(?:de\s+)?[\d]+[.,][\d]+", "", point, flags=re.IGNORECASE
                    )
                    point = re.sub(r"\s*@\s*[\d]+[.,][\d]+", "", point)
                    logger.warning(f"Stripped hallucinated odd {mentioned_odd} from key_point")
                    break
            sanitized.append(point.strip())
        return sanitized

    @staticmethod
    def _validate_recommendation_odd(recommendation: str, odds: Dict) -> str:
        """Validate that the odd in the recommendation matches an actual available odd.

        If the recommended odd doesn't match any real odd, replace it with the
        closest real odd for a matching market, or strip the odd entirely.
        """
        if not recommendation or not odds:
            return recommendation

        # Extract odd from recommendation (e.g. "@1.95" or "@ 1.95")
        odd_match = re.search(r"@\s*([\d]+[.,][\d]+)", recommendation)
        if not odd_match:
            return recommendation

        rec_odd = float(odd_match.group(1).replace(",", "."))

        # Build map of available real odds (including derived under odds)
        enriched = dict(odds)
        # Derive under35/under45 from over odds if missing
        for over_k, under_k in [("over35", "under35"), ("over45", "under45")]:
            if under_k not in enriched or enriched[under_k] is None:
                over_v = enriched.get(over_k)
                if over_v is not None:
                    try:
                        ov = float(over_v)
                        if ov > 1.0:
                            impl = 1.0 - (1.0 / ov)
                            if impl > 0:
                                enriched[under_k] = round((1.0 / impl) * 0.95, 2)
                    except (TypeError, ValueError, ZeroDivisionError):
                        pass

        real_odds: Dict[str, float] = {}
        _MARKET_NAMES = {
            "home": "Casa", "draw": "Empate", "away": "Fora",
            "over15": "Over 1.5", "over25": "Over 2.5", "over35": "Over 3.5",
            "over45": "Over 4.5", "under25": "Under 2.5",
            "under35": "Under 3.5", "under45": "Under 4.5",
            "bttsYes": "BTTS Sim", "bttsNo": "BTTS Nao",
            "btts_yes": "BTTS Sim", "btts_no": "BTTS Nao",
            "over_25": "Over 2.5",
            "cornersOver85": "Escanteios Over 8.5",
            "cornersOver95": "Escanteios Over 9.5",
            "cornersOver105": "Escanteios Over 10.5",
            "cornersOver115": "Escanteios Over 11.5",
        }
        for key, val in enriched.items():
            if val is not None:
                try:
                    real_odds[_MARKET_NAMES.get(key, key)] = float(val)
                except (TypeError, ValueError):
                    pass

        # Check if recommended odd matches any real odd (within 0.01 tolerance)
        for _market, real_odd in real_odds.items():
            if abs(rec_odd - real_odd) < 0.02:
                return recommendation  # Odd is valid

        # Odd not found — try to find the correct odd for the recommended market
        rec_lower = recommendation.lower()
        best_market = None
        best_odd = None
        for market_name, real_odd in real_odds.items():
            if market_name.lower() in rec_lower:
                best_market = market_name
                best_odd = real_odd
                break

        if best_odd is not None:
            # Replace hallucinated odd with real one
            corrected = re.sub(r"@\s*[\d]+[.,][\d]+", f"@{best_odd:.2f}", recommendation)
            logger.warning(
                f"Corrected hallucinated odd: {rec_odd} -> {best_odd} for market {best_market}"
            )
            return corrected

        # Can't find a matching market — strip the odd to avoid confusion
        corrected = re.sub(r"\s*@\s*[\d]+[.,][\d]+", "", recommendation)
        logger.warning(f"Stripped hallucinated odd {rec_odd} from recommendation (no matching market)")
        return corrected

    def _parse_analysis(self, raw_response: str, odds: Optional[Dict] = None) -> AIAnalysisResponse:
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

            recommendation = data.get("recommendation", "")

            # Detect generic/unavailable recommendations that Mistral sometimes returns
            # instead of a real data-driven recommendation
            _GENERIC_PATTERNS = (
                "indisponivel",
                "indisponível",
                "aguarde",
                "tente novamente",
                "consulte as estatisticas",
                "consulte as estatísticas",
            )
            if recommendation and any(p in recommendation.lower() for p in _GENERIC_PATTERNS):
                logger.warning(f"Mistral returned generic recommendation, discarding: {recommendation[:80]}")
                recommendation = ""

            # Validate recommended odd against real available odds
            if recommendation and odds:
                recommendation = self._validate_recommendation_odd(recommendation, odds)

            # Sanitize key_points to remove hallucinated odds
            key_points = data.get("key_points", [])[:5]
            if odds:
                key_points = self._sanitize_key_points(key_points, odds)

            return AIAnalysisResponse(
                summary=data.get("summary", ""),
                key_points=key_points,
                recommendation=recommendation,
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
