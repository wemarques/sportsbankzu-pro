/**
 * Kelly Criterion & Bankroll Distribution Engine
 *
 * Implements fractional Kelly for optimal bet sizing across
 * simple bets, intra-game doubles, and inter-game doubles.
 * Includes stake cap safety, system bet suggestions (Trixie / Lucky 15),
 * and implied probability utilities.
 */

/** Maximum fraction of bankroll allowed on a single bet (safety cap) */
export const MAX_STAKE_PCT = 0.05; // 5% hard cap per bet

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

export type SystemBetFormat = "trixie" | "lucky15" | "none";

export interface SystemBetCombination {
  legs: BetAllocation[];
  combinedOdd: number;
  stake: number;
  potentialReturn: number;
}

export interface SystemBetSuggestion {
  format: SystemBetFormat;
  label: string;
  description: string;
  selections: BetAllocation[];
  totalStake: number;
  combinations: SystemBetCombination[];
  totalCombinations: number;
  bestCaseReturn: number;
  worstCaseReturn: number;
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
 * Build a system bet suggestion from +EV simple bets.
 *
 * - 3 selections → Trixie (3 doubles + 1 treble = 4 bets)
 * - 4 selections → Lucky 15 (4 singles + 6 doubles + 4 trebles + 1 fourfold = 15 bets)
 * - Other counts → none
 */
export function suggestSystemBet(
  posEVBets: BetAllocation[],
  bankroll: number,
  kellyMultiplier: number,
): SystemBetSuggestion | null {
  // Only suggest for exactly 3 or 4 simple +EV selections
  const candidates = posEVBets
    .filter((a) => a.bet.category === "simples" && a.ev > 0)
    .sort((a, b) => b.ev - a.ev);

  if (candidates.length < 3) return null;

  // Take the top 3 or 4 by EV
  const isLucky15 = candidates.length >= 4;
  const selections = candidates.slice(0, isLucky15 ? 4 : 3);
  const n = selections.length;

  const format: SystemBetFormat = isLucky15 ? "lucky15" : "trixie";

  // Build all combination legs
  const combos: SystemBetCombination[] = [];

  // For lucky15, include singles (k=1); for trixie, start at k=2
  const minK = isLucky15 ? 1 : 2;

  for (let k = minK; k <= n; k++) {
    for (const combo of combinations(selections, k)) {
      const combinedOdd = combo.reduce((acc, a) => acc * a.bet.odd, 1);
      combos.push({ legs: combo, combinedOdd, stake: 0, potentialReturn: 0 });
    }
  }

  // Distribute a total system stake proportionally using avg Kelly of the selections
  const avgKelly =
    selections.reduce((s, a) => s + a.kellyFraction, 0) / selections.length;
  const systemFraction = Math.min(avgKelly * kellyMultiplier, MAX_STAKE_PCT);
  const totalSystemStake = Math.round(bankroll * systemFraction * 100) / 100;
  const perCombStake = Math.round((totalSystemStake / combos.length) * 100) / 100;

  for (const c of combos) {
    c.stake = perCombStake;
    c.potentialReturn = Math.round(perCombStake * c.combinedOdd * 100) / 100;
  }

  // Best case: all legs win → sum of all combo returns
  const bestCaseReturn = combos.reduce((s, c) => s + c.potentialReturn, 0);
  // Worst case: 0 legs win (trixie) or 1 leg wins (lucky15 has singles)
  const worstCaseReturn = isLucky15
    ? Math.min(...selections.map((sel) => perCombStake * sel.bet.odd))
    : 0;

  return {
    format,
    label: isLucky15 ? "Lucky 15" : "Trixie",
    description: isLucky15
      ? `4 simples + 6 duplas + 4 triplas + 1 quadrupla = 15 apostas`
      : `3 duplas + 1 tripla = 4 apostas`,
    selections,
    totalStake: Math.round(perCombStake * combos.length * 100) / 100,
    combinations: combos,
    totalCombinations: combos.length,
    bestCaseReturn: Math.round(bestCaseReturn * 100) / 100,
    worstCaseReturn: Math.round(worstCaseReturn * 100) / 100,
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
      return { bet, kf, ev, edge: e, impliedProb: ip };
    });

    // Filter positive EV only
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
      const stake = Math.round(cappedStake * 100) / 100;
      const potentialReturn = stake * calc.bet.odd;
      const potentialProfit = potentialReturn - stake;

      result[cat].push({
        bet: calc.bet,
        kellyFraction: calc.kf * kellyMultiplier,
        ev: calc.ev,
        stake,
        potentialReturn: Math.round(potentialReturn * 100) / 100,
        potentialProfit: Math.round(potentialProfit * 100) / 100,
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
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: BankrollSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export const KELLY_MULTIPLIERS: Record<BankrollSettings["kellyMode"], number> = {
  quarter: 0.25,
  half: 0.5,
  full: 1.0,
};
