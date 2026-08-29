# backend/services/mistral_analysis.py
"""
Serviço de análise de jogos usando MISTRAL AI
Prompt v3.0 — SportsBankzu-Pro

Changelog v3.0 (vs v2):
- Output expandido: 24 mercados (era 6)
- Over/Under golos: linhas 0.5, 1.5, 2.5, 3.5, 4.5
- Double Chance: DC 1X, DC 12, DC X2
- BTTS: Sim + Não
- Escanteios: Over/Under 8.5, 9.5, 10.5, 11.5
- Lesões: filtrado apenas TITULARES ([FORA]/[DÚVIDA])
- Input: +40 campos do enriquecimento v3.7
- Cartões/jogo, faltas, clean sheet %, xG sofrido, médias da liga
"""
import hashlib
import os
import json
import time
from typing import Dict, List, Optional
from datetime import datetime
import httpx
from pydantic import BaseModel, Field


# =====================================================================
# MODELOS DE RESPOSTA — v3.0
# =====================================================================

class ProbabilidadesModel(BaseModel):
    """Probabilidades 1X2 — devem somar 1.0"""
    vitoria_casa: float = Field(ge=0, le=1)
    empate: float = Field(ge=0, le=1)
    vitoria_fora: float = Field(ge=0, le=1)


class DoubleChanceModel(BaseModel):
    """Dupla Chance — derivado do 1X2"""
    dc_1x: float = Field(ge=0, le=1, description="Casa ou Empate")
    dc_12: float = Field(ge=0, le=1, description="Casa ou Fora")
    dc_x2: float = Field(ge=0, le=1, description="Empate ou Fora")


class MercadoGolsModel(BaseModel):
    """Over/Under golos — linhas 0.5 a 4.5 + BTTS"""
    over_0_5: float = Field(ge=0, le=1)
    over_1_5: float = Field(ge=0, le=1)
    over_2_5: float = Field(ge=0, le=1)
    over_3_5: float = Field(ge=0, le=1)
    over_4_5: float = Field(ge=0, le=1)
    under_2_5: float = Field(ge=0, le=1)
    under_3_5: float = Field(ge=0, le=1)
    under_4_5: float = Field(ge=0, le=1)
    btts_sim: float = Field(ge=0, le=1)
    btts_nao: float = Field(ge=0, le=1)


class EscanteiosModel(BaseModel):
    """Escanteios Over/Under — linhas 8.5 a 11.5"""
    over_8_5: float = Field(ge=0, le=1)
    over_9_5: float = Field(ge=0, le=1)
    over_10_5: float = Field(ge=0, le=1)
    over_11_5: float = Field(ge=0, le=1)
    under_8_5: float = Field(ge=0, le=1)
    under_10_5: float = Field(ge=0, le=1)
    under_11_5: float = Field(ge=0, le=1)


class LesaoJogador(BaseModel):
    """Lesão/dúvida de jogador titular"""
    jogador: str
    status: str  # "FORA" | "DÚVIDA"
    posicao: str  # "GOL" | "DEF" | "MEI" | "ATA"
    impacto: str  # "Alto" | "Médio" | "Baixo"


class ImpactoLesoes(BaseModel):
    """Avaliação do impacto das lesões de titulares"""
    casa: List[LesaoJogador] = Field(default_factory=list)
    fora: List[LesaoJogador] = Field(default_factory=list)
    avaliacao: str = Field(
        default="Sem desfalques relevantes entre titulares",
        description="Resumo do impacto coletivo das lesões"
    )


class AIAnalysisResponse(BaseModel):
    """Modelo completo de resposta da análise AI — v3.0"""
    resumo_analitico: str
    probabilidades: ProbabilidadesModel
    double_chance: DoubleChanceModel
    mercado_gols: MercadoGolsModel
    escanteios: EscanteiosModel
    impacto_lesoes: ImpactoLesoes
    fator_decisivo: str
    nivel_confianca: str  # "Alto" | "Médio" | "Baixo"
    confidence: int = Field(ge=0, le=100)
    alertas: List[str]
    recomendacao_principal: str
    key_points: List[str]
    last_updated: str


# =====================================================================
# SERVIÇO MISTRAL — v3.0
# =====================================================================

class MistralAnalysisService:
    """Serviço para análise de jogos com MISTRAL AI — v3.0"""

    VERSION = "3.0"

    SYSTEM_PROMPT = (
        "Você é o motor de análise estatística do SportsBankzu-Pro v3.0. "
        "Sua função é atuar como um Analista Sênior de Prognósticos Esportivos, "
        "transformando dados brutos em inteligência preditiva estruturada "
        "cobrindo TODOS os mercados: 1X2, Double Chance, Over/Under golos "
        "(0.5-4.5), BTTS, e Escanteios Over/Under (8.5-11.5).\n\n"
        "Responda EXCLUSIVAMENTE em JSON válido, sem markdown, sem texto adicional."
    )

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('MISTRAL_API_KEY')
        self.base_url = 'https://api.mistral.ai/v1'
        self.model = 'mistral-large-latest'

        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY não configurada")

    async def analyze_match(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict] = None,
        pipeline_picks: Optional[list] = None,
        audit_meta: Optional[Dict] = None,
    ) -> AIAnalysisResponse:
        """Gera análise completa v3.0 cobrindo 24 mercados.

        audit_meta (#188, opcional): {"match_id", "league_id"} — usado APENAS
        pelo log de medição da camada de IA; não altera a análise.
        """
        prompt = self._build_prompt(
            home_team, away_team, league, match_stats, odds, context,
            pipeline_picks=pipeline_picks,
        )
        _t0 = time.time()
        self._last_parse_error = None  # #188 — resetado a cada análise

        try:
            analysis = await self._call_mistral_api(prompt)
            result = self._parse_analysis(analysis)
            # Camada 6 — anti-contradiction with pipeline (#096)
            result.recomendacao_principal = self._validate_recommendation_vs_pipeline(
                result.recomendacao_principal, pipeline_picks or []
            )
            # Camada 7 — enforcement do contrato (#181 era log-only): a
            # recomendação DEVE consumir o mesmo cálculo deflacionado da
            # tabela de mercados. Se citar mercado fora da lista aprovada
            # (ex.: DC 1X com EV negativo pós-deflação), é substituída por
            # uma recomendação determinística construída dos picks aprovados.
            result.recomendacao_principal = self._enforce_recommendation_contract(
                result.recomendacao_principal, pipeline_picks or [],
                match_label=f"{home_team} vs {away_team}",
            )
            # #181 — full-text contract validation (observability only, no retry)
            self._log_contract_violations(
                result, pipeline_picks or [],
                match_label=f"{home_team} vs {away_team}",
            )
            # #188 Fase 1 — instrumentação (log-only, nunca levanta).
            # _last_parse_error captura JSON inválido que _parse_analysis
            # engole devolvendo fallback — sem ele, contaria como sucesso.
            self._audit_log_safe(
                result=result, error=getattr(self, "_last_parse_error", None),
                latency_ms=int((time.time() - _t0) * 1000),
                prompt=prompt, audit_meta=audit_meta,
                home_team=home_team, away_team=away_team,
                match_stats=match_stats, odds=odds, context=context,
                pipeline_picks=pipeline_picks,
            )
            return result
        except Exception as e:
            print(f"[MistralV3] Erro ao chamar API: {e}")
            try:
                from backend.services.reliability_tracker import track_api_call, track_safety
                track_api_call("mistral", False)
                track_safety("fallbacks_ativados")
            except Exception:
                pass
            # #188 Fase 1 — registra a falha (JSON inválido / HTTP / timeout)
            self._audit_log_safe(
                result=None, error=f"{type(e).__name__}: {e}",
                latency_ms=int((time.time() - _t0) * 1000),
                prompt=prompt, audit_meta=audit_meta,
                home_team=home_team, away_team=away_team,
                match_stats=match_stats, odds=odds, context=context,
                pipeline_picks=pipeline_picks,
            )
            return self._get_fallback_analysis()

    def _audit_log_safe(
        self,
        *,
        result: Optional["AIAnalysisResponse"],
        error: Optional[str],
        latency_ms: int,
        prompt: str,
        audit_meta: Optional[Dict],
        home_team: str,
        away_team: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict],
        pipeline_picks: Optional[list],
    ) -> None:
        """#188 Fase 1 — grava o registro de medição. NUNCA levanta exceção.

        Não altera comportamento de produção: qualquer falha aqui é engolida
        (o log é observabilidade, não caminho crítico).
        """
        try:
            from backend.ai.audit_log import (
                STAGE_FALLBACK,
                STAGE_PRODUCTION,
                log_ai_audit,
                validate_ai_output,
            )

            meta = audit_meta or {}
            if result is not None:
                output = result.model_dump()
                valid, verrors = validate_ai_output(output)
                confidence = float(result.confidence)
                stage = STAGE_PRODUCTION
                if error:  # parse inválido → conteúdo servido é fallback (#188)
                    valid = False
                    verrors = [f"invalid model JSON: {error}"] + verrors
            else:
                output = None
                valid, verrors = False, [error or "unknown error"]
                confidence = None
                stage = STAGE_FALLBACK

            log_ai_audit(
                provider="mistral",
                model=self.model,
                stage=stage,
                match_id=meta.get("match_id"),
                league_id=meta.get("league_id"),
                home_team=home_team,
                away_team=away_team,
                prompt_version=self.VERSION,
                prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                prompt_chars=len(prompt),
                inputs={
                    "match_stats": match_stats,
                    "odds": odds,
                    "context": context,
                    "pipeline_picks": pipeline_picks or [],
                },
                output=output,
                confidence=confidence,
                valid_json=valid,
                validation_errors=verrors,
                latency_ms=latency_ms,
                error=error,
            )
        except Exception as log_err:
            # Log de medição jamais derruba a análise (#188)
            print(f"[MistralV3] audit log skipped: {log_err}")

    # -----------------------------------------------------------------
    # PROMPT BUILDER — v3.0
    # -----------------------------------------------------------------

    def _build_prompt(
        self,
        home_team: str,
        away_team: str,
        league: str,
        match_stats: Dict,
        odds: Dict,
        context: Optional[Dict] = None,
        pipeline_picks: Optional[list] = None,
    ) -> str:
        """Constrói o prompt v3.0 para a MISTRAL AI"""

        prompt = f"""# Contexto de Análise
Analise os dados fornecidos seguindo rigorosamente estas diretrizes:

1. **Ponderação Matemática:** Aplique 60% ao histórico de longo prazo (5 temporadas) e 40% à forma atual (últimos 5-10 jogos).
2. **Análise de Padrões:** Identifique comportamentos específicos (ex: "time que não sofre gols no 1º tempo fora de casa", "alta eficiência de conversão em casa", "média de escanteios acima da liga").
3. **Cruzamento H2H:** Analise se o histórico direto confirma ou contradiz a forma atual.
4. **Lógica Probabilística:**
   - 1X2: vitoria_casa + empate + vitoria_fora = 1.0
   - Over/Under: over_X + under_X = 1.0 para cada linha
   - BTTS: btts_sim + btts_nao = 1.0
   - Double Chance: derivado do 1X2 (dc_1x = vitoria_casa + empate)
   - Escanteios: Use Poisson com lambda de escanteios quando disponível
5. **Lesões — APENAS TITULARES:** Considere SOMENTE jogadores titulares com status [FORA] ou [DÚVIDA]. Reservas e jogadores do elenco secundário NÃO devem ser listados. Avalie o impacto na formação tática.

# Regras de Ouro (Invioláveis)
- **Restrição de Dados:** Use APENAS as informações presentes nos dados. Dado ausente = "Dado não disponível".
- **Sem Determinismo:** Proibido "certeza", "vai ganhar", "garantido". Use "probabilidade", "tendência", "cenário provável".
- **Justificativa Numérica:** Toda conclusão deve ter dado numérico (ex: "lambda_home de 1.45 indica média de 1.45 gols esperados").
- **Seja Específico:** Nos key_points, cite lambdas, probabilidades, odds, %. Nunca genérico.
- **Escanteios obrigatórios:** Se dados de escanteios existirem, DEVE haver pelo menos 1 key_point sobre corners.
- **Coerência Over/Under (Corredores):** Se recomendar Over X e Under Y do MESMO mercado (gols, cartoes ou escanteios), explicar como CORREDOR com a faixa esperada. Ex: "Corredor de gols: 3 gols (Over 2.5 + Under 3.5)", "Corredor de cartoes: 3-4 cartoes (Over 2.5 + Under 4.5)", "Corredor de escanteios: 9-12 (Over 8.5 + Under 12.5)".
- **REGRA #181 — Probabilidades narrativas:** Os números abaixo em "Estatísticas Poisson" são RAW (pré-deflação, usados internamente para classificação). Ao escrever resumo_analitico/key_points/recomendacao, **use APENAS as probabilidades dos PICKS DO PIPELINE** (mais abaixo, já deflated #105 — alinhadas ao display do operador). Citar o número raw em narrativa quebra o contrato da regra #082 e produz divergência operador-vs-Mistral.
- **REGRA #181 — Cálculo de EV:** Você NUNCA computa EV. EV vem pronto em cada pick do pipeline. Não escreva "EV +X%" para mercados fora da lista, nem recompute para os da lista. Se quiser justificar valor, use "EV positivo" / "EV negativo" qualitativo, sem número.

# Dados do Confronto

JOGO: {home_team} vs {away_team}
COMPETIÇÃO: {league}

ESTATÍSTICAS CALCULADAS (Poisson, RAW — uso interno, NÃO citar em narrativa #181):
- Lambda Casa: {match_stats.get('lambda_home', 'N/A')}
- Lambda Fora: {match_stats.get('lambda_away', 'N/A')}
- Prob Casa: {match_stats.get('prob_home', 'N/A')}% (raw)
- Prob Empate: {match_stats.get('prob_draw', 'N/A')}% (raw)
- Prob Fora: {match_stats.get('prob_away', 'N/A')}% (raw)
- Prob Over 0.5: {match_stats.get('prob_over_05', 'N/A')}% (raw)
- Prob Over 1.5: {match_stats.get('prob_over_15', 'N/A')}% (raw)
- Prob Over 2.5: {match_stats.get('prob_over_25', 'N/A')}% (raw)
- Prob Over 3.5: {match_stats.get('prob_over_35', 'N/A')}% (raw)
- Prob Over 4.5: {match_stats.get('prob_over_45', 'N/A')}% (raw)
- Prob BTTS: {match_stats.get('prob_btts', 'N/A')}% (raw)

ODDS DO MERCADO:
- Casa (1): {odds.get('home', 'N/A')}
- Empate (X): {odds.get('draw', 'N/A')}
- Fora (2): {odds.get('away', 'N/A')}
- Over 0.5: {odds.get('over_05', 'N/A')}
- Over 1.5: {odds.get('over_15', 'N/A')}
- Over 2.5: {odds.get('over_25', 'N/A')}
- Over 3.5: {odds.get('over_35', 'N/A')}
- Over 4.5: {odds.get('over_45', 'N/A')}
- Under 2.5: {odds.get('under_25', 'N/A')}
- Under 3.5: {odds.get('under_35', 'N/A')}
- Under 4.5: {odds.get('under_45', 'N/A')}
- BTTS Sim: {odds.get('btts_yes', 'N/A')}
- BTTS Não: {odds.get('btts_no', 'N/A')}
- DC 1X: {odds.get('dc_1x', 'N/A')}
- DC 12: {odds.get('dc_12', 'N/A')}
- DC X2: {odds.get('dc_x2', 'N/A')}

ESCANTEIOS (FootyStats + Poisson):
- Corners/jogo Casa: {match_stats.get('homeCornersPerMatch', 'N/A')}
- Corners/jogo Fora: {match_stats.get('awayCornersPerMatch', 'N/A')}
- Corners contra/jogo Casa: {match_stats.get('homeCornersAgainstPerMatch', 'N/A')}
- Corners contra/jogo Fora: {match_stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Potencial Over 8.5: {match_stats.get('cornerOver85Prob', 'N/A')}%
- Potencial Over 9.5: {match_stats.get('cornerOver95Prob', 'N/A')}%
- Potencial Over 10.5: {match_stats.get('cornerOver105Prob', 'N/A')}%
- Média escanteios da liga: {match_stats.get('leagueAvgCorners', 'N/A')}
"""

        # ---- Dados avançados do enriquecimento v3.7 ----
        prompt += f"""
DADOS AVANÇADOS:
- xG Casa: {match_stats.get('homeXg', 'N/A')}
- xG Fora: {match_stats.get('awayXg', 'N/A')}
- xG Sofrido Casa: {match_stats.get('homeXgAgainstAvg', 'N/A')}
- xG Sofrido Fora: {match_stats.get('awayXgAgainstAvg', 'N/A')}
- Clean Sheet % Casa: {match_stats.get('homeCleanSheetPct', 'N/A')}%
- Clean Sheet % Fora: {match_stats.get('awayCleanSheetPct', 'N/A')}%
- Failed To Score % Casa: {match_stats.get('homeFtsPercentage', 'N/A')}%
- Failed To Score % Fora: {match_stats.get('awayFtsPercentage', 'N/A')}%
- BTTS % Casa: {match_stats.get('homeBttsPercentage', 'N/A')}%
- BTTS % Fora: {match_stats.get('awayBttsPercentage', 'N/A')}%
- Over 2.5 % Casa: {match_stats.get('homeOver25Percentage', 'N/A')}%
- Over 2.5 % Fora: {match_stats.get('awayOver25Percentage', 'N/A')}%
- Vitória % Casa: {match_stats.get('homeWinPercentage', 'N/A')}%
- Vitória % Fora: {match_stats.get('awayWinPercentage', 'N/A')}%
- Cartões/jogo Casa: {match_stats.get('homeCardsPerMatch', 'N/A')}
- Cartões/jogo Fora: {match_stats.get('awayCardsPerMatch', 'N/A')}
- Faltas/jogo Casa: {match_stats.get('homeFoulsPerMatch', 'N/A')}
- Faltas/jogo Fora: {match_stats.get('awayFoulsPerMatch', 'N/A')}
- Média gols/jogo Casa: {match_stats.get('homeAvgTotalGoals', 'N/A')}
- Média gols/jogo Fora: {match_stats.get('awayAvgTotalGoals', 'N/A')}

MÉDIAS DA LIGA:
- Cartões/jogo liga: {match_stats.get('leagueAvgCards', 'N/A')}
- Faltas/jogo liga: {match_stats.get('leagueAvgFouls', 'N/A')}
- Clean Sheet % liga: {match_stats.get('leagueCleanSheetsPct', 'N/A')}%
- Over 2.5 % liga: {match_stats.get('leagueOver25Pct', 'N/A')}%
- Vantagem casa liga: {match_stats.get('leagueHomeAdvantage', 'N/A')}%
"""

        # ---- Contexto adicional (lesões filtradas p/ titulares) ----
        if context:
            prompt += f"""
CONTEXTO:
- Forma Casa (últimos 5): {context.get('home_form', 'N/A')}
- Forma Fora (últimos 5): {context.get('away_form', 'N/A')}
- H2H (confrontos diretos): {context.get('h2h', 'N/A')}
- Posição tabela Casa: {context.get('home_position', 'N/A')}
- Posição tabela Fora: {context.get('away_position', 'N/A')}

LESÕES/SUSPENSÕES DE TITULARES (apenas jogadores do 11 titular):
- Casa: {context.get('home_injuries_starters', context.get('absences', 'Dado não disponível'))}
- Fora: {context.get('away_injuries_starters', 'Dado não disponível')}
NOTA: Considere APENAS os jogadores listados acima. São titulares confirmados ou prováveis. Reservas e jogadores do elenco secundário foram filtrados e NÃO devem aparecer na análise.
"""

        # ---- Picks do pipeline (#096) — Mistral DEVE alinhar recomendação ----
        if pipeline_picks:
            picks_text = "\n".join(
                f"- {p['market']} | Prob: {p.get('prob_pct', '?')}% | "
                f"Odd: {p.get('odd', 'N/A')} | EV: +{p.get('ev_pct', '?')}% | "
                f"{p.get('classification', '')}"
                for p in pipeline_picks
            )
            prompt += f"""
PICKS SELECIONADOS PELO PIPELINE (Dixon-Coles):
{picks_text}

REGRA DE ALINHAMENTO (#096, endurecida):
- Sua recomendacao_principal DEVE ser EXATAMENTE UM DOS picks listados acima. NENHUM outro mercado e permitido — "mercado complementar" NAO existe.
- Mercados que NAO estao na lista acima foram REJEITADOS pelo pipeline (EV negativo apos deflacao ou sem odd). Recomenda-los contradiz a tabela exibida ao operador.
- Se o pipeline selecionou Under 2.5, voce NAO pode recomendar Over 2.5 (sao opostos).
- Se o pipeline selecionou Over 8.5 escanteios, voce NAO pode recomendar Under 8.5.
- NUNCA contradiga a direcao (Over/Under) de um pick do pipeline.
- Use APENAS as probabilidades listadas acima, NAO calcule probabilidades alternativas.
"""
        else:
            prompt += """
PICKS SELECIONADOS PELO PIPELINE (Dixon-Coles): NENHUM.

REGRA DE ALINHAMENTO (#096, endurecida):
- O pipeline NAO aprovou nenhum mercado (EV positivo apos deflacao) para este jogo.
- Sua recomendacao_principal DEVE ser exatamente: "Sem recomendação — nenhum mercado com EV positivo após deflação para este jogo."
- NAO recomende nenhum mercado, mesmo com probabilidade alta.
"""

        # ---- Schema de saída v3.0 ----
        prompt += """
# Formato de Saída (JSON Estrito — v3.0)

Responda exclusivamente no formato JSON abaixo. TODOS os campos são obrigatórios.

{
  "resumo_analitico": "Análise técnica de 2-3 frases com indicadores numéricos.",

  "probabilidades": {
    "vitoria_casa": 0.00,
    "empate": 0.00,
    "vitoria_fora": 0.00
  },

  "double_chance": {
    "dc_1x": 0.00,
    "dc_12": 0.00,
    "dc_x2": 0.00
  },

  "mercado_gols": {
    "over_0_5": 0.00,
    "over_1_5": 0.00,
    "over_2_5": 0.00,
    "over_3_5": 0.00,
    "over_4_5": 0.00,
    "under_2_5": 0.00,
    "under_3_5": 0.00,
    "under_4_5": 0.00,
    "btts_sim": 0.00,
    "btts_nao": 0.00
  },

  "escanteios": {
    "over_8_5": 0.00,
    "over_9_5": 0.00,
    "over_10_5": 0.00,
    "over_11_5": 0.00,
    "under_8_5": 0.00,
    "under_10_5": 0.00,
    "under_11_5": 0.00
  },

  "impacto_lesoes": {
    "casa": [
      {"jogador": "Nome", "status": "FORA|DÚVIDA", "posicao": "GOL|DEF|MEI|ATA", "impacto": "Alto|Médio|Baixo"}
    ],
    "fora": [],
    "avaliacao": "Resumo do impacto coletivo na formação titular"
  },

  "fator_decisivo": "O elemento isolado que mais influencia o confronto.",
  "nivel_confianca": "Alto|Médio|Baixo",
  "confidence": 75,

  "alertas": [
    "Alerta 1 relevante",
    "Alerta 2 relevante"
  ],

  "key_points": [
    "Ponto 1 — golos (com lambda/prob/odd)",
    "Ponto 2 — 1X2 ou DC (com prob/odd)",
    "Ponto 3 — BTTS (com % e odd)",
    "Ponto 4 — escanteios (com corners/jogo e potencial)",
    "Ponto 5 — contexto (forma, H2H, lesões de titulares)"
  ],

  "recomendacao_principal": "Mercado com maior EV+ incluindo odd específica e justificativa."
}

# REGRA DE RECOMENDAÇÃO (#093):
- A recomendacao_principal DEVE ser de um mercado que tenha odd REAL listada acima (NÃO "N/A").
- Se um mercado tem probabilidade alta mas odd = N/A, NÃO recomende esse mercado.
- Priorize mercados que tenham EV positivo (probabilidade > 1/odd).
- Se nenhum mercado tem odd disponível, escreva: "Sem recomendação — odds indisponíveis para os mercados analisados."
- NUNCA diga "odd não disponível mas probabilidade de X%" como recomendação.

# REGRA DE EV — CÁLCULO OBRIGATÓRIO (#146):
- EV = (probabilidade × odd) - 1. Se resultado < 0, o EV é NEGATIVO.
- NUNCA afirme "EV positivo" sem verificar: prob × odd > 1.0.
- Exemplo CORRETO: prob 72% (0.72) × odd 1.25 = 0.90 → EV = -10% (NEGATIVO).
- Exemplo INCORRETO: "72% > 80% (1/1.25) logo EV positivo" — ERRADO, 72% < 80%.
- Se prob < (1/odd), o mercado tem EV NEGATIVO. Diga claramente "EV negativo" na recomendacao.
- Mercados com EV negativo PODEM ter alta chance de acerto no jogo especifico (ex: DC X2 a 72%) mas NAO geram lucro no longo prazo. Separe as duas informacoes.

# REGRA DE CORREDORES (#146b):
- Quando recomendar Over X e Under Y do mesmo mercado (ex: Cards Over 2.5 + Under 4.5), explique como CORREDOR:
  "Corredor de Cartoes: entre 3 e 4 cartoes (Over 2.5 + Under 4.5)".
- NAO apresente Over e Under como picks independentes sem mencionar que formam um corredor.
- Indique a faixa esperada (ex: "3-4 cartoes", "9-12 escanteios") em vez de listar linhas separadas.

# VALIDAÇÕES OBRIGATÓRIAS:
- probabilidades: vitoria_casa + empate + vitoria_fora = 1.0
- double_chance: dc_1x = vitoria_casa + empate; dc_12 = vitoria_casa + vitoria_fora; dc_x2 = empate + vitoria_fora
- mercado_gols: over_X_5 + under_X_5 ≈ 1.0 (para linhas com ambos); btts_sim + btts_nao = 1.0
- escanteios: over_X_5 + under_X_5 ≈ 1.0 (para linhas com ambos)
- confidence: inteiro 0-100
- nivel_confianca: exatamente "Alto", "Médio" ou "Baixo"
- key_points: exatamente 5 itens, cobrindo os 5 temas indicados
- alertas: pelo menos 1 item
- impacto_lesoes.casa e .fora: listas vazias se sem desfalques de titulares. NUNCA incluir reservas.
- recomendacao_principal: deve incluir mercado + odd + justificativa numérica
- Se dados de escanteios = N/A, retorne 0.0 para todas as linhas e adicione alerta "Dados de escanteios indisponíveis"
"""
        return prompt

    # -----------------------------------------------------------------
    # API CALL
    # -----------------------------------------------------------------

    async def _call_mistral_api(self, prompt: str) -> str:
        """Chama a API da MISTRAL com system + user messages"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f'{self.base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': self.SYSTEM_PROMPT},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.15,
                    'max_tokens': 2500,
                    'response_format': {'type': 'json_object'}
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            try:
                from backend.services.reliability_tracker import track_api_call
                track_api_call("mistral", True)
            except Exception:
                pass
            return data['choices'][0]['message']['content']

    # -----------------------------------------------------------------
    # PARSER — v3.0
    # -----------------------------------------------------------------

    def _parse_analysis(self, raw_response: str) -> AIAnalysisResponse:
        """Parse da resposta da MISTRAL para o modelo v3.0"""
        try:
            cleaned = raw_response.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # --- Validar e normalizar 1X2 ---
            probs = data.get('probabilidades', {})
            soma_1x2 = sum(probs.get(k, 0) for k in
                           ['vitoria_casa', 'empate', 'vitoria_fora'])
            if abs(soma_1x2 - 1.0) > 0.05 and soma_1x2 > 0:
                for k in ['vitoria_casa', 'empate', 'vitoria_fora']:
                    probs[k] = round(probs.get(k, 0) / soma_1x2, 3)
                probs['vitoria_fora'] = round(
                    1.0 - probs['vitoria_casa'] - probs['empate'], 3
                )

            # --- Derivar Double Chance se ausente ---
            dc = data.get('double_chance', {})
            vc = probs.get('vitoria_casa', 0.33)
            em = probs.get('empate', 0.34)
            vf = probs.get('vitoria_fora', 0.33)
            if not dc or dc.get('dc_1x', 0) == 0:
                dc = {
                    'dc_1x': round(vc + em, 3),
                    'dc_12': round(vc + vf, 3),
                    'dc_x2': round(em + vf, 3)
                }

            # --- Validar complementaridade Over/Under ---
            mg = data.get('mercado_gols', {})
            if mg.get('under_2_5', 0) == 0 and mg.get('over_2_5', 0) > 0:
                mg['under_2_5'] = round(1.0 - mg['over_2_5'], 3)
            if mg.get('under_3_5', 0) == 0 and mg.get('over_3_5', 0) > 0:
                mg['under_3_5'] = round(1.0 - mg['over_3_5'], 3)
            if mg.get('under_4_5', 0) == 0 and mg.get('over_4_5', 0) > 0:
                mg['under_4_5'] = round(1.0 - mg['over_4_5'], 3)
            if mg.get('btts_nao', 0) == 0 and mg.get('btts_sim', 0) > 0:
                mg['btts_nao'] = round(1.0 - mg['btts_sim'], 3)

            # --- Validar escanteios complementares ---
            esc = data.get('escanteios', {})
            for line in ['8_5', '10_5', '11_5']:
                over_k = f'over_{line}'
                under_k = f'under_{line}'
                if esc.get(under_k, 0) == 0 and esc.get(over_k, 0) > 0:
                    esc[under_k] = round(1.0 - esc[over_k], 3)

            # --- Parse lesões (filtrar se Mistral incluiu reservas) ---
            lesoes_raw = data.get('impacto_lesoes', {})
            casa_lesoes = [
                LesaoJogador(**lj) for lj in lesoes_raw.get('casa', [])
                if isinstance(lj, dict) and lj.get('jogador')
            ]
            fora_lesoes = [
                LesaoJogador(**lj) for lj in lesoes_raw.get('fora', [])
                if isinstance(lj, dict) and lj.get('jogador')
            ]

            # --- Confidence ---
            nivel = data.get('nivel_confianca', 'Médio')
            confidence_raw = data.get('confidence')
            if confidence_raw is None:
                confidence_raw = {'Alto': 80, 'Médio': 55, 'Baixo': 30}.get(
                    nivel, 50
                )

            return AIAnalysisResponse(
                resumo_analitico=data.get('resumo_analitico', ''),
                probabilidades=ProbabilidadesModel(
                    vitoria_casa=probs.get('vitoria_casa', 0.33),
                    empate=probs.get('empate', 0.34),
                    vitoria_fora=probs.get('vitoria_fora', 0.33)
                ),
                double_chance=DoubleChanceModel(
                    dc_1x=dc.get('dc_1x', round(vc + em, 3)),
                    dc_12=dc.get('dc_12', round(vc + vf, 3)),
                    dc_x2=dc.get('dc_x2', round(em + vf, 3))
                ),
                mercado_gols=MercadoGolsModel(
                    over_0_5=mg.get('over_0_5', 0.0),
                    over_1_5=mg.get('over_1_5', 0.0),
                    over_2_5=mg.get('over_2_5', 0.0),
                    over_3_5=mg.get('over_3_5', 0.0),
                    over_4_5=mg.get('over_4_5', 0.0),
                    under_2_5=mg.get('under_2_5', 0.0),
                    under_3_5=mg.get('under_3_5', 0.0),
                    under_4_5=mg.get('under_4_5', 0.0),
                    btts_sim=mg.get('btts_sim', 0.0),
                    btts_nao=mg.get('btts_nao', 0.0)
                ),
                escanteios=EscanteiosModel(
                    over_8_5=esc.get('over_8_5', 0.0),
                    over_9_5=esc.get('over_9_5', 0.0),
                    over_10_5=esc.get('over_10_5', 0.0),
                    over_11_5=esc.get('over_11_5', 0.0),
                    under_8_5=esc.get('under_8_5', 0.0),
                    under_10_5=esc.get('under_10_5', 0.0),
                    under_11_5=esc.get('under_11_5', 0.0)
                ),
                impacto_lesoes=ImpactoLesoes(
                    casa=casa_lesoes,
                    fora=fora_lesoes,
                    avaliacao=lesoes_raw.get(
                        'avaliacao',
                        'Sem desfalques relevantes entre titulares'
                    )
                ),
                fator_decisivo=data.get(
                    'fator_decisivo', 'Dado não disponível'
                ),
                nivel_confianca=nivel,
                confidence=min(max(int(confidence_raw), 0), 100),
                alertas=data.get('alertas', []),
                recomendacao_principal=self._validate_recommendation(
                    data.get('recomendacao_principal', '')
                ),
                key_points=data.get('key_points', [])[:5],
                last_updated=datetime.now().strftime('%d/%m/%Y às %H:%M')
            )

        except Exception as e:
            print(f"[MistralV3] Erro parse: {e}")
            print(f"[MistralV3] Resposta bruta: {raw_response[:500]}")
            # #188 — marca o parse inválido para o log de medição (a resposta
            # servida continua sendo o fallback, comportamento inalterado)
            self._last_parse_error = f"{type(e).__name__}: {e}"
            return self._get_fallback_analysis()

    # -----------------------------------------------------------------
    # VALIDATION (#093)
    # -----------------------------------------------------------------

    @staticmethod
    def _validate_recommendation(recommendation: str) -> str:
        """Reject recommendations mentioning markets without real odds (#093)."""
        if not recommendation:
            return recommendation
        invalid_patterns = [
            "odd não disponível", "odds não disponíveis", "odd indisponível",
            "sem odd", "odd n/a", "odds indisponíveis", "não disponível, mas",
        ]
        rec_lower = recommendation.lower()
        for pattern in invalid_patterns:
            if pattern in rec_lower:
                return (
                    "Sem recomendação adicional — o mercado sugerido não possui "
                    "odd disponível. Consulte os picks do pipeline (VALOR DETECTADO) "
                    "que já possuem EV calculado."
                )
        return recommendation

    @staticmethod
    def _validate_recommendation_vs_pipeline(recommendation: str, picks: list) -> str:
        """Reject recommendations that contradict pipeline picks (#096).

        E.g. pipeline says Under 2.5, Mistral recommends Over 2.5 → blocked.

        Limitação conhecida (#181, 2026-05-04): inspeciona apenas
        recomendacao_principal e detecta apenas contradição de DIREÇÃO
        (Over X ↔ Under X). Não lê resumo_analitico/key_points e não
        valida coerência numérica (probs/odds/EV). Caso Sporting × Vitória
        (Mistral citou prob 70% para Under 3.5 quando display mostrava
        57%) passou despercebido por essa função porque a direção
        estava correta. Validação full-text + numérica vive em
        backend/ai/mistral_contract.py::validate_output.
        """
        if not recommendation or not picks:
            return recommendation

        import re
        rec_lower = recommendation.lower()

        opposites = [
            ("under", "over"),
            ("over", "under"),
        ]

        for pick in picks:
            market = (pick.get("market") or "").lower()
            for direction, opposite in opposites:
                if direction not in market:
                    continue
                # Extract the line number (e.g. "2.5" from "under 2.5 gols")
                line_match = re.search(r"(\d+\.?\d*)", market)
                if not line_match:
                    continue
                line = line_match.group(1)
                # Check if recommendation contains the OPPOSITE direction with the same line
                if opposite in rec_lower and line in rec_lower:
                    best = pick
                    return (
                        f"Recomendação alinhada ao pipeline: {best['market']} "
                        f"(odd {best.get('odd', 'N/A')}, EV +{best.get('ev_pct', '?')}%) — "
                        f"pick com maior EV+ confirmado pelo modelo Dixon-Coles."
                    )

        return recommendation

    @staticmethod
    def _enforce_recommendation_contract(
        recommendation: str,
        picks: list,
        match_label: str = "?",
    ) -> str:
        """Enforcement da recomendação vs. tabela de EV deflacionado.

        Caso real (KRC Genk × Waasland-Beveren, 2026-08-28): a Sugestão
        exibia "Double Chance 1X ... EV positivo, 87%" enquanto a tabela
        do mesmo jogo listava DC 1X com EV -29.8% (não recomendado após
        deflação). O prompt (#096) permitia "um mercado complementar" e a
        Camada 6 só checava direção Over/Under — a brecha exata.

        Regra: se a recomendacao_principal menciona um mercado que NÃO está
        na lista aprovada (picks EV+ pós-deflação), ou computa EV numérico
        no texto, ela é descartada e substituída pela recomendação
        determinística de mistral_contract.aligned_recommendation() —
        construída dos mesmos valores exibidos na tabela. Nunca recomenda
        o que a tabela rejeita.
        """
        if not recommendation:
            return recommendation
        try:
            from backend.ai.mistral_contract import (
                ApprovedPick, aligned_recommendation, log_violations,
                validate_output,
            )
        except Exception:
            return recommendation  # fail open — não derruba a análise

        approved: list = []
        for p in picks or []:
            try:
                approved.append(ApprovedPick(
                    market=str(p.get("market", "")),
                    classification=str(p.get("classification", "")),
                    prob_deflated_pct=float(p.get("prob_pct") or 0),
                    odd=float(p.get("odd") or 0),
                    ev_pct=float(p.get("ev_pct") or 0),
                ))
            except Exception:
                continue

        v = validate_output(recommendation, approved)
        if v["ok"]:
            return recommendation

        log_violations(
            [f"recomendacao_principal substituída (enforcement): {viol}"
             for viol in v["violations"]],
            match_label=match_label,
        )
        return aligned_recommendation(approved)

    @staticmethod
    def _log_contract_violations(
        result: 'AIAnalysisResponse',
        pipeline_picks: list,
        match_label: str = "?",
    ) -> None:
        """#181 — full-text contract validation against pipeline picks.

        Inspects resumo_analitico + key_points + recomendacao_principal
        (Camada 6 only inspected recomendacao_principal). Detects markets
        outside the approved list and EV computations in the narrative.

        Logs violations through sportsbankzu.mistral.contract logger; does
        NOT mutate the result, retry, or fallback. Pure observability.
        Once a few weeks of CloudWatch data show violation frequency, a
        follow-up fix wires retry/fallback.
        """
        try:
            from backend.ai.mistral_contract import (
                ApprovedPick, validate_output, log_violations,
            )
        except Exception:
            return  # contract module missing — fail open, don't crash analyze_match

        approved: list = []
        for p in pipeline_picks or []:
            try:
                approved.append(ApprovedPick(
                    market=str(p.get("market", "")),
                    classification=str(p.get("classification", "")),
                    prob_deflated_pct=float(p.get("prob_pct") or 0),
                    odd=float(p.get("odd") or 0),
                    ev_pct=float(p.get("ev_pct") or 0),
                ))
            except Exception:
                continue  # skip malformed picks; keep validating the rest

        # Concatenate full narrative — anything visible to the operator.
        text_parts = [
            getattr(result, "resumo_analitico", "") or "",
            getattr(result, "recomendacao_principal", "") or "",
            *(getattr(result, "key_points", []) or []),
        ]
        full_text = " ".join(text_parts)
        v = validate_output(full_text, approved)
        if not v["ok"]:
            log_violations(v["violations"], match_label=match_label)

    # -----------------------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------------------

    def _get_fallback_analysis(self) -> AIAnalysisResponse:
        """Retorna análise padrão em caso de erro"""
        return AIAnalysisResponse(
            resumo_analitico=(
                "Análise temporariamente indisponível. "
                "Tente novamente em alguns instantes."
            ),
            probabilidades=ProbabilidadesModel(
                vitoria_casa=0.33, empate=0.34, vitoria_fora=0.33
            ),
            double_chance=DoubleChanceModel(
                dc_1x=0.67, dc_12=0.66, dc_x2=0.67
            ),
            mercado_gols=MercadoGolsModel(
                over_0_5=0.0, over_1_5=0.0, over_2_5=0.0,
                over_3_5=0.0, over_4_5=0.0,
                under_2_5=0.0, under_3_5=0.0, under_4_5=0.0,
                btts_sim=0.0, btts_nao=0.0
            ),
            escanteios=EscanteiosModel(
                over_8_5=0.0, over_9_5=0.0, over_10_5=0.0,
                over_11_5=0.0, under_8_5=0.0, under_10_5=0.0,
                under_11_5=0.0
            ),
            impacto_lesoes=ImpactoLesoes(
                casa=[], fora=[],
                avaliacao="Serviço indisponível"
            ),
            fator_decisivo="Serviço indisponível",
            nivel_confianca="Baixo",
            confidence=0,
            alertas=["Serviço de análise AI temporariamente indisponível"],
            recomendacao_principal="Aguarde restabelecimento do serviço.",
            key_points=[
                "Serviço de análise AI temporariamente indisponível",
                "Recomendamos analisar as estatísticas manualmente",
                "Verifique as probabilidades e odds apresentadas",
                "Consulte o histórico de confrontos diretos",
                "Considere a forma recente das equipes"
            ],
            last_updated=datetime.now().strftime('%d/%m/%Y às %H:%M')
        )

    @staticmethod
    def _get_fallback_static() -> AIAnalysisResponse:
        """Fallback estático sem precisar instanciar o service (usado quando API key ausente)."""
        return MistralAnalysisService._build_fallback()

    @staticmethod
    def _build_fallback() -> AIAnalysisResponse:
        """Constrói resposta fallback padrão."""
        return AIAnalysisResponse(
            resumo_analitico=(
                "Análise indisponível. "
                "Tente novamente em alguns instantes."
            ),
            probabilidades=ProbabilidadesModel(
                vitoria_casa=0.33, empate=0.34, vitoria_fora=0.33
            ),
            double_chance=DoubleChanceModel(
                dc_1x=0.67, dc_12=0.66, dc_x2=0.67
            ),
            mercado_gols=MercadoGolsModel(
                over_0_5=0.0, over_1_5=0.0, over_2_5=0.0,
                over_3_5=0.0, over_4_5=0.0,
                under_2_5=0.0, under_3_5=0.0, under_4_5=0.0,
                btts_sim=0.0, btts_nao=0.0
            ),
            escanteios=EscanteiosModel(
                over_8_5=0.0, over_9_5=0.0, over_10_5=0.0,
                over_11_5=0.0, under_8_5=0.0, under_10_5=0.0,
                under_11_5=0.0
            ),
            impacto_lesoes=ImpactoLesoes(
                casa=[], fora=[],
                avaliacao="Serviço indisponível"
            ),
            fator_decisivo="Serviço indisponível",
            nivel_confianca="Baixo",
            confidence=0,
            alertas=["Serviço de análise AI temporariamente indisponível"],
            recomendacao_principal="Aguarde restabelecimento do serviço.",
            key_points=[
                "Serviço de análise AI temporariamente indisponível",
                "Recomendamos analisar as estatísticas manualmente",
                "Verifique as probabilidades e odds apresentadas",
                "Consulte o histórico de confrontos diretos",
                "Considere a forma recente das equipes"
            ],
            last_updated=datetime.now().strftime('%d/%m/%Y às %H:%M')
        )

    # -----------------------------------------------------------------
    # COMPATIBILIDADE LEGADO → MatchDetailCard.tsx
    # -----------------------------------------------------------------

    @staticmethod
    def to_legacy_format(analysis: AIAnalysisResponse) -> dict:
        """Converte v3.0 para formato legado do MatchDetailCard.tsx"""
        return {
            'summary': analysis.resumo_analitico,
            'key_points': analysis.key_points,
            'recommendation': analysis.recomendacao_principal,
            'confidence': analysis.confidence,
            'last_updated': analysis.last_updated,
        }

    @staticmethod
    def to_full_dict(analysis: AIAnalysisResponse) -> dict:
        """Retorna dict completo v3.0 para frontend atualizado"""
        return analysis.model_dump()
