// frontend/next/src/lib/matchDetailTypes.ts
// Tipos movidos de components/MatchDetailCard.tsx (#258, ruling 3) — o componente foi apagado
// no corte do legado; matchDataMapper.ts continua vivo via MatchAnalysis e precisa destes tipos.
import type { EvReferencia, AncoraReferencia } from "@/lib/fonteProbabilidade";

export interface AIAnalysis {
  summary: string;
  key_points: string[];
  recommendation: string;
  confidence: number;
  last_updated: string;
}

export interface AuditPickEvaluation {
  mercado: string;
  status_pick: string;
  resultado: string;
  nota: string;
}

export interface AuditCorrection {
  type: string;
  parameter: string;
  current_value: number;
  suggested_value: number;
  reason: string;
  confidence: number;
  impact: string;
}

export interface AuditResult {
  picks_evaluation?: AuditPickEvaluation[];
  validation: {
    probabilities: { status: string; notes: string; brier_score?: number };
    lambdas: { status: string; notes: string; predicted_total?: number; actual_total?: number };
    ev: { status: string; notes: string };
  };
  ai_analysis_accuracy?: string;
  accuracy_summary?: string;
  corrections?: AuditCorrection[];
  biases_detected?: string[];
  suggestions?: string[];
  audit_confidence: number;
  audit_type?: string;
  timestamp?: string;
  match?: string;
}

// Alias for backward compatibility with V0 dashboard
export type MatchDetail = MatchDetailData;

export interface MatchDetailData {
  /** #189-g: true enquanto a análise Mistral carrega (sem % falsa) */
  aiLoading?: boolean;
  id: string;
  league: string;
  leagueId?: string;
  season?: string;
  homeTeam: string;
  awayTeam: string;
  homeTeamLogo?: string;
  awayTeamLogo?: string;
  startTime?: string;
  status?: "scheduled" | "live" | "finished";
  score?: { home: number; away: number; halftime?: { home: number; away: number } };
  period?: "1T" | "HT" | "2T" | null;
  /** #190: texto pronto do relogio ("58'", "45+2'", "INT") */
  clockLabel?: string;
  /** #190: minutos regulamentares restantes */
  minutesLeft?: number;
  /** #190: true quando o feed travou e o tempo esta congelado */
  clockStale?: boolean;
  minute?: number | null;
  venue?: {
    name: string;
    capacity?: number;
    image?: string;
  };
  odds?: {
    home?: number;
    draw?: number;
    away?: number;
    homeVariation?: "up" | "down";
    drawVariation?: "up" | "down";
    awayVariation?: "up" | "down";
  };
  doubleChance?: {
    homeOrDraw?: number;
    homeOrAway?: number;
    drawOrAway?: number;
  };
  btts?: {
    yes?: number;
    no?: number;
  };
  matchStats?: {
    homeWinProb?: number;
    drawProb?: number;
    awayWinProb?: number;
    /** #187: "odds_implied" (prob. de mercado, #028/#064) | "ml_ensemble" (modelo) */
    predictionSource?: string;
    avgGoals?: number;
    bttsProb?: number;
    over15Prob?: number;
    over25Prob?: number;
    over35Prob?: number;
    over45Prob?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    homePossession?: number;
    awayPossession?: number;
    homeXG?: number;
    awayXG?: number;
    leagueRegime?: string;
    leagueVolatility?: string;
    homeCornersPerMatch?: number;
    awayCornersPerMatch?: number;
    homeCardsPerMatch?: number;
    awayCardsPerMatch?: number;
    homeShotsOnTarget?: number;
    awayShotsOnTarget?: number;
    homeShotsPerMatch?: number;
    awayShotsPerMatch?: number;
    homeFoulsPerMatch?: number;
    awayFoulsPerMatch?: number;
    leagueAvgCorners?: number;
    leagueAvgCards?: number;
    leagueAvgFouls?: number;
    leagueAvgShots?: number;
    // League extended
    leagueHomeAdvantage?: number;
    leagueCleanSheetsPct?: number;
    leagueOver25Pct?: number;
    leagueXgAvg?: number;
    // Team advanced stats
    homeBttsPercentage?: number;
    awayBttsPercentage?: number;
    homeCleanSheetPct?: number;
    awayCleanSheetPct?: number;
    homeFtsPercentage?: number;
    awayFtsPercentage?: number;
    homeOver25Percentage?: number;
    awayOver25Percentage?: number;
    homeWinPercentage?: number;
    awayWinPercentage?: number;
    homeXgForAvg?: number;
    awayXgForAvg?: number;
    homeXgAgainstAvg?: number;
    awayXgAgainstAvg?: number;
    homeCornersAgainstPerMatch?: number;
    awayCornersAgainstPerMatch?: number;
    homeLeaguePosition?: number;
    awayLeaguePosition?: number;
    homeAvgTotalGoals?: number;
    awayAvgTotalGoals?: number;
    cornersPotential?: number;
    cornerOver85Prob?: number;
    cornerOver95Prob?: number;
    cornerOver105Prob?: number;
    // Actual match card/corner counts (for result badges)
    homeCornersCount?: number;
    awayCornersCount?: number;
    homeYellowCards?: number;
    awayYellowCards?: number;
    homeRedCards?: number;
    awayRedCards?: number;
  };
  h2h?: {
    totalMatches?: number;
    homeWins?: number;
    draws?: number;
    awayWins?: number;
    avgGoals?: number;
  };
  homeForm?: string[];
  awayForm?: string[];
  round?: string;
  aiAnalysis?: AIAnalysis;
  currentCorners?: number | null;
  currentCards?: number | null;
  rejectedInsights?: {
    market: string;
    raw_prob: number;
    deflated_prob: number;
    ev: number | null;
    reason: string;
    reason_codes?: string[];
  }[];
  cornerPredictions?: {
    projectedTotalFT?: number | null;
    projectedTotal1H?: number | null;
    projectedTotal2H?: number | null;
    modelSource?: string;
    dataQualityTier?: string;
    governanceState?: string;
    recommendedLine?: number | null;
    recommendedSide?: string | null;
    recommendedEdge?: number | null;
    noBet?: boolean;
    engineVersion?: string;
  };
  cardsPredictions?: {
    projectedTotalCards?: number | null;
    cardsLambda?: number | null;
    cardsLambdaHome?: number | null;
    cardsLambdaAway?: number | null;
    cardsMultiplier?: number | null;
    overdispersion?: number | null;
    modelSource?: string;
    adjustments?: {
      foul_adjustment?: number;
      referee_factor?: number;
      league_discipline_factor?: number;
    };
    lines?: Record<string, { prob: number }>;
  };
  predictions?: {
    mercado: string;
    status: string;
    prob_min: number;
    prob_max: number;
    odd_minima: number | null;
    alerta?: string;
    // New unified contract fields
    classification?: string;
    reason_codes?: string[];
    data_quality_score?: number;
    odds_available?: boolean;
    ev?: number | null;
    edge?: number | null;
    fair_odd?: number | null;
    book_odd?: number | null;
    calibrated_probability?: number | null;
    stake?: number | null;
    // #231–#234: presentes só com PROB_SOURCE=mercado no backend
    prob_source?: "mercado" | "taxa_base" | "modelo_sem_referencia";
    model_probability?: number | null;
    ev_referencia?: EvReferencia | null;
    ancora_referencia?: AncoraReferencia | null;
    // Market reference signal fields
    marketReferenceSignal?: "SAFE" | "NEUTRO" | "RESTRITO";
    marketReferenceReason?: string;
    rawClassification?: string;
    finalClassification?: string;
    wasCappedByMarketSignal?: boolean;
  }[];
}
