import type { MatchDetailData } from "@/components/MatchDetailCard";

type MatchStats = NonNullable<MatchDetailData["matchStats"]>;

/**
 * Canonical list of matchStats keys. Both the Python backend and the
 * MatchDetailCard interface use these exact names, so a single pick
 * loop replaces the 55-line manual mapping that was duplicated across
 * dashboard/page.tsx and match/[id]/page.tsx.
 */
const MATCH_STATS_KEYS: (keyof MatchStats)[] = [
  "homeWinProb", "drawProb", "awayWinProb", "avgGoals", "bttsProb",
  "over15Prob", "over25Prob", "over35Prob", "over45Prob",
  "lambdaHome", "lambdaAway",
  "homePossession", "awayPossession", "homeXG", "awayXG",
  "leagueRegime", "leagueVolatility",
  "homeCornersPerMatch", "awayCornersPerMatch",
  "homeCardsPerMatch", "awayCardsPerMatch",
  "homeShotsOnTarget", "awayShotsOnTarget",
  "homeShotsPerMatch", "awayShotsPerMatch",
  "homeFoulsPerMatch", "awayFoulsPerMatch",
  "leagueAvgCorners", "leagueAvgCards", "leagueAvgFouls", "leagueAvgShots",
  "leagueHomeAdvantage", "leagueCleanSheetsPct", "leagueOver25Pct", "leagueXgAvg",
  "homeBttsPercentage", "awayBttsPercentage",
  "homeCleanSheetPct", "awayCleanSheetPct",
  "homeFtsPercentage", "awayFtsPercentage",
  "homeOver25Percentage", "awayOver25Percentage",
  "homeWinPercentage", "awayWinPercentage",
  "homeXgForAvg", "awayXgForAvg",
  "homeXgAgainstAvg", "awayXgAgainstAvg",
  "homeCornersAgainstPerMatch", "awayCornersAgainstPerMatch",
  "homeLeaguePosition", "awayLeaguePosition",
  "homeAvgTotalGoals", "awayAvgTotalGoals",
  "cornersPotential", "cornerOver85Prob", "cornerOver95Prob", "cornerOver105Prob",
];

/**
 * Pick matchStats fields from any stats-like source object.
 * Works with both typed `Match["stats"]` objects and raw
 * `Record<string, unknown>` API responses.
 */
export function mapMatchStats(
  source: Record<string, unknown> | null | undefined,
): MatchStats | undefined {
  if (!source) return undefined;
  const out: Record<string, unknown> = {};
  for (const key of MATCH_STATS_KEYS) {
    const val = source[key];
    if (val !== undefined && val !== null) {
      out[key] = val;
    }
  }
  return out as MatchStats;
}
