/**
 * Kelly Criterion & Bankroll Distribution Engine
 *
 * Implements fractional Kelly for optimal bet sizing across
 * simple bets, intra-game doubles, and inter-game doubles.
 */

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
}

export interface BankrollDistribution {
  simples: BetAllocation[];
  dupla_intra: BetAllocation[];
  dupla_inter: BetAllocation[];
  totalStaked: number;
  expectedReturn: number;
  expectedProfit: number;
  unutilized: number;
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
 */
export function expectedValue(prob: number, odd: number): number {
  return (prob / 100) * odd - 1;
}

/**
 * Edge: how much the true probability exceeds the implied probability
 */
export function edge(prob: number, odd: number): number {
  const impliedProb = 1 / odd;
  return prob / 100 - impliedProb;
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

  const result: BankrollDistribution = {
    simples: [],
    dupla_intra: [],
    dupla_inter: [],
    totalStaked: 0,
    expectedReturn: 0,
    expectedProfit: 0,
    unutilized: 0,
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
      return { bet, kf, ev, edge: e };
    });

    // Filter positive EV only
    const posEV = betCalcs.filter((b) => b.ev > 0 && b.kf > 0);

    if (posEV.length === 0) continue;

    // Apply fractional Kelly and normalize to fit budget
    const totalKelly = posEV.reduce((sum, b) => sum + b.kf * kellyMultiplier, 0);
    const scaleFactor = totalKelly > 0 ? catBudget / (bankroll * totalKelly) : 0;

    for (const calc of posEV) {
      const rawStake = bankroll * calc.kf * kellyMultiplier * scaleFactor;
      const stake = Math.round(rawStake * 100) / 100;
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
      });
    }

    // Sort by EV descending
    result[cat].sort((a, b) => b.ev - a.ev);
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
