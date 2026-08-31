/**
 * Kelly Criterion & Bankroll Distribution Engine
 *
 * Implements fractional Kelly for optimal bet sizing across
 * simple bets, intra-game doubles, and inter-game doubles.
 * Includes stake cap safety, advanced system bet suggestions
 * (2de3, Trixie, 3de5), banker selection, break-even filter,
 * and scenario-based return calculations.
 */

import { getBankroll, setBankroll } from "./bankrollStore";

/** Maximum fraction of bankroll allowed on a single bet (safety cap) */
export const MAX_STAKE_PCT = 0.05; // 5% hard cap per bet

/** Caps */
export const MAX_STAKE_PER_GAME_PCT = 0.08; // 8% max per game
export const MAX_STAKE_PER_DAY_PCT = 0.30; // 30% max per day

/** Stake multipliers by classification */
export const CLASSIFICATION_STAKE_MULTIPLIER: Record<string, number> = {
  SAFE: 1.0,
  NEUTRO_QUALIFICADO: 0.60,
  NEUTRO: 0.0,
  NO_BET: 0.0,
};

export interface BetInput {
  id: string;
  label: string;
  homeTeam: string;
  awayTeam: string;
  market: string;
  odd: number;
  probMin: number;
  probMax: number;
  status: string;
  datetime: string;
  leagueName: string;
  category: "simples" | "dupla_intra" | "dupla_inter";
  // New fields from unified contract
  classification?: string;
  dataQualityScore?: number;
  reasonCodes?: string[];
  oddsAvailable?: boolean;
  // For duplas
  leg2Label?: string;
  leg2Market?: string;
  leg2Odd?: number;
  leg2Status?: string;
}

export interface BetAllocation {
  bet: BetInput;
  kellyFraction: number;
  ev: number;
  stake: number;
  potentialReturn: number;
  potentialProfit: number;
  edge: number;
  impliedProb: number;
  /** true when the stake was capped by MAX_STAKE_PCT */
  capped: boolean;
}

export interface BankrollDistribution {
  simples: BetAllocation[];
  dupla_intra: BetAllocation[];
  dupla_inter: BetAllocation[];
  totalStaked: number;
  expectedReturn: number;
  expectedProfit: number;
  unutilized: number;
  systemBet: SystemBetSuggestion | null;
}

/* ── System Bet types ── */

export type SystemBetFormat = "2de3" | "trixie" | "3de5" | "none";

export interface SystemBetCombination {
  legs: BetAllocation[];
  combinedOdd: number;
  stake: number;
  potentialReturn: number;
}

/** Scenario: what happens when the user hits exactly N of M selections */
export interface SystemBetScenario {
  /** How many legs win */
  hitsRequired: number;
  /** Total number of combinations that would pay out */
  winningCombos: number;
  /** Estimated gross return */
  estimatedReturn: number;
  /** Net profit (return - totalStake) */
  netProfit: number;
  /** Whether the user breaks even or profits */
  coversInvestment: boolean;
}

/** Banker: the algorithmically-selected anchor bet */
export interface BankerSelection {
  allocation: BetAllocation;
  /** Composite score used to pick the banker (EV * prob * edge) */
  score: number;
  /** Why this bet was picked */
  reason: string;
}

export interface SystemBetSuggestion {
  format: SystemBetFormat;
  label: string;
  description: string;
  /** Explanatory headline for the UI hero card */
  headline: string;
  selections: BetAllocation[];
  totalStake: number;
  stakePerLine: number;
  combinations: SystemBetCombination[];
  totalCombinations: number;
  bestCaseReturn: number;
  worstCaseReturn: number;
  /** Scenario breakdown: returns for each possible hit count */
  scenarios: SystemBetScenario[];
  /** Banker (anchor) bet — highest probability + EV selection */
  banker: BankerSelection | null;
  /** Whether the system passes the break-even profitability filter */
  passesBreakEven: boolean;
  /** Reason if break-even filter rejects the system */
  breakEvenReason: string;
  /** Whether this system is recommended (passes all filters) */
  recommended: boolean;
}

/**
 * Implied probability from decimal odd: P = 1 / Odd
 */
export function impliedProbability(odd: number): number {
  if (odd <= 0) return 0;
  return 1 / odd;
}

/**
 * Full Kelly fraction: f* = (p * b - q) / b
 * where p = win probability, b = odd - 1, q = 1 - p
 */
export function kellyFraction(prob: number, odd: number): number {
  const p = prob / 100;
  const q = 1 - p;
  const b = odd - 1;
  if (b <= 0) return 0;
  const f = (p * b - q) / b;
  return Math.max(0, f);
}

/**
 * Expected Value: EV = (prob * odd) - 1
 * Positive EV means the real probability exceeds the implied probability.
 */
export function expectedValue(prob: number, odd: number): number {
  return (prob / 100) * odd - 1;
}

/**
 * Edge: how much the true probability exceeds the implied probability
 */
export function edge(prob: number, odd: number): number {
  return prob / 100 - impliedProbability(odd);
}

/**
 * Generate all k-combinations of an array.
 */
function combinations<T>(arr: T[], k: number): T[][] {
  if (k === 0) return [[]];
  if (arr.length < k) return [];
  const [first, ...rest] = arr;
  const withFirst = combinations(rest, k - 1).map((c) => [first, ...c]);
  const withoutFirst = combinations(rest, k);
  return [...withFirst, ...withoutFirst];
}

/**
 * Round to 2 decimal places.
 */
function r2(n: number): number {
  return Math.round(n * 100) / 100;
}

/* ── System format definitions ── */

interface SystemFormatDef {
  format: SystemBetFormat;
  label: string;
  /** How many selections the system needs */
  selectionCount: number;
  /** Minimum combination size (k). 2de3 and 3de5 only use doubles. Trixie uses 2+3 */
  minK: number;
  /** Maximum combination size */
  maxK: number;
  /** Description template */
  description: (totalCombos: number) => string;
}

const SYSTEM_FORMATS: SystemFormatDef[] = [
  {
    format: "2de3",
    label: "Sistema 2/3",
    selectionCount: 3,
    minK: 2,
    maxK: 2,
    description: () => "3 combinacoes duplas — lucra com 2 de 3 acertos",
  },
  {
    format: "trixie",
    label: "Trixie",
    selectionCount: 3,
    minK: 2,
    maxK: 3,
    description: () => "3 duplas + 1 tripla = 4 linhas de aposta",
  },
  {
    format: "3de5",
    label: "Sistema 3/5",
    selectionCount: 5,
    minK: 2,
    maxK: 2,
    description: (n) => `${n} combinacoes duplas — lucra com 3 de 5 acertos`,
  },
];

/**
 * Determine the best system format based on the number of +EV games.
 *
 * Rule 3 — Dynamic Level Recommendation:
 * - 3 games  → prefer "2de3" (3 lines) for bankroll protection, upgrade to Trixie (4 lines) for higher upside
 * - 5+ games → suggest "3de5" (10 lines) for high-volume days
 */
function pickSystemFormat(candidateCount: number): SystemFormatDef | null {
  if (candidateCount >= 5) return SYSTEM_FORMATS[2]; // 3de5
  if (candidateCount >= 3) return SYSTEM_FORMATS[1]; // trixie (default for 3-4 games)
  return null;
}

/**
 * Rule 4 — Banker (Anchor) Selection
 * Identifies the game with highest combined score of probability, EV, and edge.
 * The banker is present in ALL combinations, reducing cost while boosting potential return.
 */
function selectBanker(selections: BetAllocation[]): BankerSelection | null {
  if (selections.length < 3) return null;

  let best: BankerSelection | null = null;

  for (const alloc of selections) {
    const midProb = (alloc.bet.probMin + alloc.bet.probMax) / 2;
    // Composite: emphasizes high probability AND positive EV
    const score = r2((midProb / 100) * (1 + alloc.ev) * (1 + alloc.edge));

    if (!best || score > best.score) {
      best = {
        allocation: alloc,
        score,
        reason: `Maior probabilidade (${midProb.toFixed(0)}%) combinada com EV +${(alloc.ev * 100).toFixed(1)}%`,
      };
    }
  }

  return best;
}

/**
 * Build scenario breakdown: for each possible number of hits (0..N),
 * calculate how many combos pay out and the estimated return.
 */
function buildScenarios(
  selections: BetAllocation[],
  combos: SystemBetCombination[],
  totalStake: number,
): SystemBetScenario[] {
  const n = selections.length;
  const scenarios: SystemBetScenario[] = [];

  for (let hits = 0; hits <= n; hits++) {
    // For each hit count, simulate: pick the top `hits` selections by odd as winners
    // and count how many combos have ALL legs within those winners
    const winners = new Set(
      selections
        .slice()
        .sort((a, b) => b.bet.odd - a.bet.odd)
        .slice(0, hits)
        .map((a) => a.bet.id),
    );

    let estimatedReturn = 0;
    let winningCombos = 0;

    for (const combo of combos) {
      const allWin = combo.legs.every((leg) => winners.has(leg.bet.id));
      if (allWin) {
        estimatedReturn += combo.potentialReturn;
        winningCombos++;
      }
    }

    estimatedReturn = r2(estimatedReturn);
    const netProfit = r2(estimatedReturn - totalStake);

    scenarios.push({
      hitsRequired: hits,
      winningCombos,
      estimatedReturn,
      netProfit,
      coversInvestment: estimatedReturn >= totalStake,
    });
  }

  return scenarios;
}

/**
 * Rule 5 — Break-even Profitability Filter
 * Checks if the minimum winning scenario (N-1 hits for an N-selection system)
 * covers the total stake. If odds are too low, system bets are not recommended.
 */
function checkBreakEven(
  scenarios: SystemBetScenario[],
  selections: BetAllocation[],
  totalStake: number,
): { passes: boolean; reason: string } {
  const n = selections.length;
  // Minimum hits to break even: for Trixie/2de3 (3 selections) check 2 hits;
  // for 3de5 (5 selections) check 3 hits
  const minHits = n <= 3 ? 2 : 3;

  const minScenario = scenarios.find((s) => s.hitsRequired === minHits);
  if (!minScenario) {
    return { passes: false, reason: "Cenário mínimo não encontrado" };
  }

  // Calculate average odds of selections
  const avgOdd = r2(selections.reduce((s, a) => s + a.bet.odd, 0) / selections.length);

  if (!minScenario.coversInvestment) {
    return {
      passes: false,
      reason: `Odds médias baixas (${avgOdd.toFixed(2)}). Com ${minHits} de ${n} acertos, o retorno estimado (R$ ${minScenario.estimatedReturn.toFixed(2)}) nao cobre o investimento total (R$ ${totalStake.toFixed(2)}). Recomendamos apostas simples individuais.`,
    };
  }

  return { passes: true, reason: "" };
}

/**
 * Build a system bet suggestion from +EV simple bets.
 *
 * Implements all 5 business rules:
 * 1. System Bet Calculator — combinations + scenario returns
 * 2. Automatic Stake Distribution — Kelly total divided equally across lines
 * 3. Dynamic Level Recommendation — format based on game count
 * 4. Banker (Algorithmic Anchor) — highest-score selection
 * 5. Break-even Filter — rejects low-odd systems
 */
export function suggestSystemBet(
  posEVBets: BetAllocation[],
  bankroll: number,
  kellyMultiplier: number,
): SystemBetSuggestion | null {
  // Filter for eligible +EV bets: SAFE or NEUTRO_QUALIFICADO with real odds
  const candidates = posEVBets
    .filter((a) => {
      if (a.ev <= 0) return false;
      if (a.bet.category !== "simples") return false;
      const cls = a.bet.classification || a.bet.status;
      // Block NO_BET and plain NEUTRO from system bets
      if (cls === "NO_BET") return false;
      // Must have real odds
      if (a.bet.oddsAvailable === false) return false;
      return true;
    })
    .sort((a, b) => b.ev - a.ev);

  if (candidates.length < 3) return null;

  // Rule 3: Pick the right system format
  const formatDef = pickSystemFormat(candidates.length);
  if (!formatDef) return null;

  // Select top N bets by EV for the chosen format
  const selections = candidates.slice(0, formatDef.selectionCount);

  // Build all combination legs
  const combos: SystemBetCombination[] = [];
  for (let k = formatDef.minK; k <= formatDef.maxK; k++) {
    for (const combo of combinations(selections, k)) {
      const combinedOdd = combo.reduce((acc, a) => acc * a.bet.odd, 1);
      combos.push({ legs: combo, combinedOdd, stake: 0, potentialReturn: 0 });
    }
  }

  // Rule 2: Distribute Kelly total equally across all lines
  const avgKelly =
    selections.reduce((s, a) => s + a.kellyFraction, 0) / selections.length;
  const systemFraction = Math.min(avgKelly * kellyMultiplier, MAX_STAKE_PCT);
  const totalSystemStake = r2(bankroll * systemFraction);
  const stakePerLine = r2(totalSystemStake / combos.length);

  for (const c of combos) {
    c.stake = stakePerLine;
    c.potentialReturn = r2(stakePerLine * c.combinedOdd);
  }

  const actualTotalStake = r2(stakePerLine * combos.length);

  // Best case: all legs win → sum of all combo returns
  const bestCaseReturn = r2(combos.reduce((s, c) => s + c.potentialReturn, 0));
  // Worst case: 0 or 1 legs win
  const worstCaseReturn = 0;

  // Rule 1: Scenario breakdown
  const scenarios = buildScenarios(selections, combos, actualTotalStake);

  // Rule 4: Banker selection
  const banker = selectBanker(selections);

  // Rule 5: Break-even filter
  const { passes: passesBreakEven, reason: breakEvenReason } = checkBreakEven(
    scenarios,
    selections,
    actualTotalStake,
  );

  const n = selections.length;
  const recommended = passesBreakEven;

  // Build headline
  const headline = recommended
    ? `Encontramos ${n} jogos de grande valor hoje. Para proteger sua banca contra ${n <= 3 ? "1 erro" : "até 2 erros"}, sugerimos um ${formatDef.label} (${combos.length} linhas). Invista R$ ${stakePerLine.toFixed(2)} em cada combinação.`
    : `${n} jogos +EV encontrados, mas as odds médias são baixas para sistema. Recomendamos apostas simples individuais.`;

  return {
    format: formatDef.format,
    label: formatDef.label,
    description: formatDef.description(combos.length),
    headline,
    selections,
    totalStake: actualTotalStake,
    stakePerLine,
    combinations: combos,
    totalCombinations: combos.length,
    bestCaseReturn,
    worstCaseReturn,
    scenarios,
    banker,
    passesBreakEven,
    breakEvenReason,
    recommended,
  };
}

/**
 * Distributes bankroll across bets using fractional Kelly.
 *
 * @param bets - Array of bet inputs
 * @param bankroll - Total bankroll value
 * @param allocations - Percentage allocation per category { simples, dupla_intra, dupla_inter }
 * @param kellyMultiplier - Kelly fraction (0.25 = quarter Kelly, 0.5 = half, 1 = full)
 */
export function distributeBankroll(
  bets: BetInput[],
  bankroll: number,
  allocations: { simples: number; dupla_intra: number; dupla_inter: number },
  kellyMultiplier: number = 0.25,
): BankrollDistribution {
  const categories = ["simples", "dupla_intra", "dupla_inter"] as const;
  const maxStakeAbs = bankroll * MAX_STAKE_PCT;

  const result: BankrollDistribution = {
    simples: [],
    dupla_intra: [],
    dupla_inter: [],
    totalStaked: 0,
    expectedReturn: 0,
    expectedProfit: 0,
    unutilized: 0,
    systemBet: null,
  };

  for (const cat of categories) {
    const catBets = bets.filter((b) => b.category === cat);
    const catBudget = bankroll * (allocations[cat] / 100);

    if (catBets.length === 0 || catBudget <= 0) continue;

    // Calculate Kelly for each bet using midpoint probability
    const betCalcs = catBets.map((bet) => {
      const midProb = (bet.probMin + bet.probMax) / 2;
      const kf = kellyFraction(midProb, bet.odd);
      const ev = expectedValue(midProb, bet.odd);
      const e = edge(midProb, bet.odd);
      const ip = impliedProbability(bet.odd);

      // Apply classification-based stake multiplier (Layer 4)
      const clsMultiplier = CLASSIFICATION_STAKE_MULTIPLIER[bet.classification || "NEUTRO"] ?? 0;

      // Apply haircut for low data quality
      let haircut = 1.0;
      if ((bet.dataQualityScore ?? 1.0) < 0.4) haircut *= 0.85;
      if (bet.reasonCodes?.includes("EARLY_SEASON_FALLBACK")) haircut *= 0.80;
      if (bet.reasonCodes?.includes("LINEUP_UNCERTAINTY")) haircut *= 0.90;
      if (bet.reasonCodes?.includes("HIGH_MARKET_CORRELATION")) haircut *= 0.85;

      const adjustedKf = kf * clsMultiplier * haircut;

      return { bet, kf: adjustedKf, ev, edge: e, impliedProb: ip };
    });

    // Filter positive EV and non-zero Kelly (respects NO_BET/NEUTRO exclusion)
    const posEV = betCalcs.filter((b) => b.ev > 0 && b.kf > 0);

    if (posEV.length === 0) continue;

    // Apply fractional Kelly and normalize to fit budget
    const totalKelly = posEV.reduce((sum, b) => sum + b.kf * kellyMultiplier, 0);
    const scaleFactor = totalKelly > 0 ? catBudget / (bankroll * totalKelly) : 0;

    for (const calc of posEV) {
      const rawStake = bankroll * calc.kf * kellyMultiplier * scaleFactor;
      // Apply hard cap: no single bet exceeds MAX_STAKE_PCT of bankroll
      const cappedStake = Math.min(rawStake, maxStakeAbs);
      const capped = rawStake > maxStakeAbs;
      const stake = r2(cappedStake);
      const potentialReturn = stake * calc.bet.odd;
      const potentialProfit = potentialReturn - stake;

      result[cat].push({
        bet: calc.bet,
        kellyFraction: calc.kf * kellyMultiplier,
        ev: calc.ev,
        stake,
        potentialReturn: r2(potentialReturn),
        potentialProfit: r2(potentialProfit),
        edge: calc.edge,
        impliedProb: Math.round(calc.impliedProb * 10000) / 100,
        capped,
      });
    }

    // Sort by EV descending
    result[cat].sort((a, b) => b.ev - a.ev);
  }

  // Generate system bet suggestion from simple +EV allocations
  if (result.simples.length >= 3) {
    result.systemBet = suggestSystemBet(result.simples, bankroll, kellyMultiplier);
  }

  // Calculate totals
  const allAllocations = [...result.simples, ...result.dupla_intra, ...result.dupla_inter];
  result.totalStaked = allAllocations.reduce((s, a) => s + a.stake, 0);
  result.expectedReturn = allAllocations.reduce((s, a) => s + a.stake * (1 + a.ev), 0);
  result.expectedProfit = result.expectedReturn - result.totalStaked;
  result.unutilized = bankroll - result.totalStaked;

  return result;
}

/**
 * Storage key for bankroll settings persistence
 */
const STORAGE_KEY = "sportsbankzu_bankroll_settings";

export interface BankrollSettings {
  bankroll: number;
  pctSimples: number;
  pctIntra: number;
  pctInter: number;
  kellyMode: "quarter" | "half" | "full";
}

export const DEFAULT_SETTINGS: BankrollSettings = {
  bankroll: 1000,
  pctSimples: 40,
  pctIntra: 35,
  pctInter: 25,
  kellyMode: "quarter",
};

export function loadSettings(): BankrollSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  let settings = DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    settings = DEFAULT_SETTINGS;
  }
  // #190: the bankroll amount is owned by the shared store (single source of truth
  // with the dashboard); this JSON keeps only allocation percentages and Kelly mode.
  return { ...settings, bankroll: getBankroll() };
}

export function saveSettings(settings: BankrollSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  // #190: propagate to the canonical store so the dashboard sees the change live.
  setBankroll(settings.bankroll);
}

export const KELLY_MULTIPLIERS: Record<BankrollSettings["kellyMode"], number> = {
  quarter: 0.25,
  half: 0.5,
  full: 1.0,
};
