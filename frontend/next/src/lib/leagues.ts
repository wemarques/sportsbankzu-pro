export type League = {
  id: string;
  name: string;
  country: string;
  countryFlag: string;
  logo: string;
  season: string;
  totalMatches: number;
  matchesToday: number;
  apiEndpoints: {
    footystats: string;
  };
  /** #189-e: ligas inativas ficam listadas mas fora do fetch/portfolio.
   *  Base: analise de 5.505 picks (Wilson + Δ Brier vs mercado, 29/08/2026).
   *  Brasileirao A permanece ATIVO em modo correcao (decisao 30/08). */
  active?: boolean;
};

export type Match = {
  id: string;
  footystatsId?: number;
  leagueId: string;
  leagueName: string;
  homeTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  awayTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  datetime: string;
  venue: string;
  status: "scheduled" | "live" | "finished" | "postponed";
  score?: {
    home: number;
    away: number;
    halftime?: { home: number; away: number };
  };
  period?: "1T" | "HT" | "2T" | null;
  minute?: number | null;
  currentCorners?: number | null;
  currentCards?: number | null;
  odds: {
    home: number;
    draw: number;
    away: number;
    over15?: number;
    over25: number;
    over35?: number;
    over45?: number;
    under25: number;
    bttsYes: number;
    bttsNo: number;
    cornersOver85?: number;
    cornersOver95?: number;
    cornersOver105?: number;
    cornersOver115?: number;
  };
  stats: {
    homeWinProb: number;
    drawProb: number;
    awayWinProb: number;
    avgGoals: number;
    bttsProb: number;
    over15Prob?: number;
    over25Prob: number;
    over35Prob?: number;
    over45Prob?: number;
    over05Prob?: number;
    homePossession?: number;
    awayPossession?: number;
    homeXG?: number;
    awayXG?: number;
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
    homeCornersCount?: number;
    awayCornersCount?: number;
    homeYellowCards?: number;
    awayYellowCards?: number;
    homeRedCards?: number;
    awayRedCards?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    lambdaTotal?: number;
    regime?: string;
    leagueRegime?: string;
    leagueVolatility?: string;
    homeForm?: string[];
    awayForm?: string[];
  };
  h2h: {
    totalMatches: number;
    homeWins: number;
    draws: number;
    awayWins: number;
    avgGoals: number;
  };
  cornerPredictions?: CornerPredictions;
  cardsPredictions?: CardsPredictions;
  predictions?: MatchPrediction[];
  rejectedInsights?: RejectedInsight[];
  source: "footystats";
  lastUpdated: string;
  /** #192: set by the pick ledger when the rendered prognosis is a frozen snapshot
   *  ("kickoff" = match started; "degraded" = fresh recompute lost its odds). */
  picksFrozen?: "kickoff" | "degraded";
  picksFrozenAt?: string;
};

export type RejectedInsight = {
  market: string;
  raw_prob: number;
  deflated_prob: number;
  ev: number | null;
  reason: string;
  reason_codes?: string[];
};

export type CornerPredictions = {
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

export type CardsPredictions = {
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

export type MarketClassification = "SAFE" | "NEUTRO_QUALIFICADO" | "NEUTRO" | "NO_BET";

export type ReasonCode =
  | "LOW_DATA_QUALITY"
  | "NO_ODDS_AVAILABLE"
  | "NEGATIVE_EV"
  | "INSUFFICIENT_EDGE"
  | "EARLY_SEASON_FALLBACK"
  | "HIGH_MARKET_CORRELATION"
  | "LINEUP_UNCERTAINTY"
  | "HIGH_PREDICTION_RISK"
  | "REGIME_BLOCKED"
  | "POSITIVE_EV"
  | "STRONG_EDGE"
  | "HIGH_CALIBRATED_PROB"
  | "ODDS_TOO_LOW"
  | "STABLE_MARKET"
  | "VOLATILE_MARKET"
  | "COVERAGE_INSUFFICIENT"
  | "SUSPICIOUS_EV"
  | "SAFE_CIRCUIT_BREAKER"
  | "BORDERLINE_LINE_MARGIN"
  | "DIRECTION_AGAINST_PROJFT"
  | "DIRECTION_NATURAL_MATCH"
  | "DIRECTION_NATURAL_NO_EV";

export type MatchPrediction = {
  mercado: string;
  status: string;
  prob_min: number;
  prob_max: number;
  odd_minima: number | null;
  alerta?: string;
  // New unified contract fields
  classification?: MarketClassification;
  reason_codes?: ReasonCode[];
  data_quality_score?: number;
  odds_available?: boolean;
  ev?: number | null;
  edge?: number | null;
  fair_odd?: number | null;
  book_odd?: number | null;
  calibrated_probability?: number | null;
  raw_probability?: number | null;
  stake?: number | null;
  // Corner governance (populated for marketFamily=corners)
  corner_governance?: {
    marketFamily: string;
    cornerModelStatus: string;
    championModel: string;
    fallbackModel: string;
    modelUsed: string;
    beatsPoisson: boolean;
    beatsNegativeBinomial: boolean;
    beatsMLRegression: boolean;
    cornerCalibrationStatus: string;
    cornerSampleAdequacy: string;
    cornerValidationVersion: string;
  };
  // Market reference signal fields
  finalClassification?: string;
  wasCappedByMarketSignal?: boolean;
  marketReferenceSignal?: "SAFE" | "NEUTRO" | "RESTRITO";
};

/** #189-e: ligas com fetch/stake habilitados (13 = nucleo 8 + observacao 4
 *  + Brasileirao A em modo correcao). As demais ficam visiveis em
 *  Campeonatos mas fora do dashboard diario. */
export const ACTIVE_LEAGUES = (): League[] =>
  AVAILABLE_LEAGUES.filter((l) => l.active !== false);

export const AVAILABLE_LEAGUES: League[] = [
  {
    id: "premier-league",
    name: "Premier League",
    country: "Inglaterra",
    countryFlag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    logo: "/logos/premier-league.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/england/premier-league",
    },
  },
  {
    id: "championship",
    name: "Championship",
    country: "Inglaterra",
    countryFlag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    logo: "/logos/championship.png",
    season: "2025/26",
    totalMatches: 552,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/england/championship",
    },
  },
  {
    id: "england-league-one",
    name: "League One",
    country: "Inglaterra",
    countryFlag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    logo: "/logos/league-one.png",
    season: "2025/26",
    totalMatches: 552,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/england/league-one",
    },
  },
  {
    id: "primera-division",
    name: "Primera Division",
    country: "Argentina",
    countryFlag: "🇦🇷",
    logo: "/logos/primera-division.png",
    season: "2026",
    totalMatches: 378,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/argentina/primera-division",
    },
  },
  {
    id: "a-league",
    active: false,
    name: "A-League",
    country: "Austrália",
    countryFlag: "🇦🇺",
    logo: "/logos/a-league.png",
    season: "2025/26",
    totalMatches: 162,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/australia/a-league",
    },
  },
  {
    id: "pro-league",
    active: false,
    name: "Pro League",
    country: "Bélgica",
    countryFlag: "🇧🇪",
    logo: "/logos/pro-league.png",
    season: "2025/26",
    totalMatches: 240,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/belgium/pro-league",
    },
  },
  {
    id: "brazil-serie-a",
    name: "Brasileirão Série A",
    country: "Brasil",
    countryFlag: "🇧🇷",
    logo: "/logos/brasileirao.png",
    season: "2026",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/brazil/campeonato-brasileiro-serie-a",
    },
  },
  {
    id: "brazil-serie-b",
    name: "Brasileirão Série B",
    country: "Brasil",
    countryFlag: "🇧🇷",
    logo: "/logos/brasileirao-b.png",
    season: "2026",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/brazil/campeonato-brasileiro-serie-b",
    },
  },
  {
    id: "denmark-superliga",
    active: false,
    name: "Superliga",
    country: "Dinamarca",
    countryFlag: "🇩🇰",
    logo: "/logos/superliga.png",
    season: "2025/26",
    totalMatches: 132,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/denmark/superliga",
    },
  },
  {
    id: "france-ligue-1",
    active: false,
    name: "Ligue 1",
    country: "França",
    countryFlag: "🇫🇷",
    logo: "/logos/ligue-1.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/france/ligue-1",
    },
  },
  {
    id: "germany-bundesliga",
    active: false,
    name: "Bundesliga",
    country: "Alemanha",
    countryFlag: "🇩🇪",
    logo: "/logos/bundesliga.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/germany/bundesliga",
    },
  },
  {
    id: "germany-2-bundesliga",
    name: "2. Bundesliga",
    country: "Alemanha",
    countryFlag: "🇩🇪",
    logo: "/logos/2-bundesliga.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/germany/2-bundesliga",
    },
  },
  {
    id: "italy-serie-a",
    name: "Serie A",
    country: "Itália",
    countryFlag: "🇮🇹",
    logo: "/logos/serie-a.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/italy/serie-a",
    },
  },
  {
    id: "italy-serie-b",
    active: false,
    name: "Serie B",
    country: "Itália",
    countryFlag: "🇮🇹",
    logo: "/logos/serie-b.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/italy/serie-b",
    },
  },
  {
    id: "netherlands-eredivisie",
    name: "Eredivisie",
    country: "Holanda",
    countryFlag: "🇳🇱",
    logo: "/logos/eredivisie.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/netherlands/eredivisie",
    },
  },
  {
    id: "portugal-liga-nos",
    name: "Liga NOS",
    country: "Portugal",
    countryFlag: "🇵🇹",
    logo: "/logos/liga-nos.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/portugal/liga-nos",
    },
  },
  {
    id: "scotland-premiership",
    active: false,
    name: "Premiership",
    country: "Escócia",
    countryFlag: "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    logo: "/logos/premiership.png",
    season: "2025/26",
    totalMatches: 228,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/scotland/premiership",
    },
  },
  {
    id: "spain-la-liga",
    name: "La Liga",
    country: "Espanha",
    countryFlag: "🇪🇸",
    logo: "/logos/laliga.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/spain/la-liga",
    },
  },
  {
    id: "turkey-super-lig",
    active: false,
    name: "Süper Lig",
    country: "Turquia",
    countryFlag: "🇹🇷",
    logo: "/logos/super-lig.png",
    season: "2025/26",
    totalMatches: 342,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/turkey/super-lig",
    },
  },
  {
    id: "usa-mls",
    name: "MLS",
    country: "Estados Unidos",
    countryFlag: "🇺🇸",
    logo: "/logos/mls.png",
    season: "2026",
    totalMatches: 510,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/usa/mls",
    },
  },
  {
    id: "colombia-primera-a",
    active: false,
    name: "Campeonato Colombiano",
    country: "Colômbia",
    countryFlag: "🇨🇴",
    logo: "/logos/colombian-primera-a.png",
    season: "2026",
    totalMatches: 200,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/colombia/colombian-primera-a",
    },
  },
  {
    id: "mexico-liga-mx",
    name: "Liga MX",
    country: "México",
    countryFlag: "🇲🇽",
    logo: "/logos/liga-mx.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/mexico/liga-mx",
    },
  },
];

// =============================================================================
// Safe Bets Types
// =============================================================================

export type SafeBetTag =
  | "UNDER_35"
  | "BTTS_NO"
  | "SAFE_CORNERS"
  | "SAFE_CORNERS_HT"
  | "TIMING_2H"
  | "NO_BET";

export type RiskLevel = "SAFE" | "MODERATE" | "NO_BET";

export type StrategyResult = {
  strategy: string;
  tag: SafeBetTag;
  passed: boolean;
  confidence: number | null;
  reason: string;
  market_label: string;
  details?: Record<string, unknown>;
};

export type SafeBetsResult = {
  match_id: string;
  league_id: string;
  home_team: string;
  away_team: string;
  tags: SafeBetTag[];
  risk_level: RiskLevel;
  layer1_dna: Record<string, unknown>;
  layer2_risk: Record<string, unknown>;
  layer3_strategies: StrategyResult[];
  blocked: boolean;
  block_reason: string;
};

export type SafeBetsResponse = {
  success: boolean;
  total_matches: number;
  safe_count: number;
  blocked_count: number;
  results: SafeBetsResult[];
};

export const SAFE_BET_TAG_CONFIG: Record<
  SafeBetTag,
  { label: string; color: string; description: string }
> = {
  UNDER_35: {
    label: "Under 3.5",
    color: "bg-blue-600 text-white",
    description: "Under 3.5 Gols — Liga defensiva com baixa média de gols sofridos",
  },
  BTTS_NO: {
    label: "BTTS Não",
    color: "bg-indigo-600 text-white",
    description: "Ambos Marcam: Não — Mandante com CS alto + visitante sem marcar",
  },
  SAFE_CORNERS: {
    label: "Escanteios 9.5+",
    color: "bg-amber-600 text-white",
    description: "Over 9.5 Escanteios — Liga e times com alta média de escanteios",
  },
  SAFE_CORNERS_HT: {
    label: "Escanteios HT 4.5+",
    color: "bg-amber-500 text-white",
    description: "Over 4.5 Escanteios 1T — Alta média de escanteios no 1º tempo",
  },
  TIMING_2H: {
    label: "Gols 2T",
    color: "bg-emerald-600 text-white",
    description: "Over 0.5 Gols 2T — Alta probabilidade de gols no 2º tempo",
  },
  NO_BET: {
    label: "Sem Aposta",
    color: "bg-red-600 text-white",
    description: "Risco elevado — Partida bloqueada pelo motor de segurança",
  },
};
