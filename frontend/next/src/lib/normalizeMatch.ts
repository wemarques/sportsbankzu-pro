/**
 * #254-a — mapeador do payload de /fixtures para `Match`, EXTRAIDO de
 * app/dashboard/page.tsx sem alteracao de comportamento. Fase 2 da spec de
 * reformulacao: primeiro testavel, depois redesenhado.
 */
import { AVAILABLE_LEAGUES, type Match } from "@/lib/leagues";

export function safeOdd(value?: number, fallback = 0) {
  if (!value || value <= 0) return fallback;
  return value;
}

/** Alias map: common nicknames/abbreviations → canonical name (lowercase). */
const TEAM_ALIASES: Record<string, string> = {
  wolves: "wolverhampton wanderers",
  "man united": "manchester united", "man utd": "manchester united",
  "man city": "manchester city",
  spurs: "tottenham hotspur",
  brighton: "brighton and hove albion",
  "west ham": "west ham united",
  newcastle: "newcastle united",
  leicester: "leicester city",
  "nottm forest": "nottingham forest", "nott'm forest": "nottingham forest",
  "sheffield utd": "sheffield united",
  luton: "luton town",
  inter: "inter milan", internazionale: "inter milan",
  psg: "paris saint germain", "paris sg": "paris saint germain",
  bayern: "bayern munich", "bayern munchen": "bayern munich",
  dortmund: "borussia dortmund",
  leverkusen: "bayer leverkusen",
};

/** Normalize team name for matching: remove accents, periods, extra spaces, common prefixes. */
export function normalizeTeamName(name: string): string {
  let s = name
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")  // Remove diacritics (é→e, ñ→n)
    .replace(/\./g, "")               // Remove periods (Dep. → Dep)
    .replace(/\s+/g, " ")
    .trim();
  // Remove common prefixes (SC Internacional → Internacional, FC Barcelona → Barcelona, Atlético Mineiro → Mineiro)
  s = s.replace(/\b(sc|ec|fc|cr|se|aa|ce|gr|ac|cf|as|rc|cd|ca|ss|afc|atletico)\b\s*/gi, "").trim();
  return s;
}

/** Resolve team name to canonical form via alias map. */
export function resolveTeamAlias(name: string): string {
  const norm = normalizeTeamName(name);
  return TEAM_ALIASES[norm] ?? norm;
}

/** Deduplicate matches by canonical team names. Keeps the richer record (more odds/stats/predictions). */
export function deduplicateMatches(matches: Match[]): Match[] {
  if (matches.length <= 1) return matches;
  const seen = new Map<string, { idx: number; richness: number }>();
  const result: Match[] = [];

  for (const m of matches) {
    // #135: Include date in key to avoid collision when same teams play on different dates
    const dateStr = m.datetime ? m.datetime.slice(0, 10) : "";
    const key = `${resolveTeamAlias(m.homeTeam.name)}||${resolveTeamAlias(m.awayTeam.name)}||${dateStr}`;
    const rich = matchRichness(m);
    const prev = seen.get(key);

    if (prev != null) {
      const prevMatch = result[prev.idx];
      if (rich > prev.richness) {
        // Current match is richer — replace, but merge live data from previous
        const merged = mergeMatchData(m, prevMatch);
        result[prev.idx] = merged;
        seen.set(key, { idx: prev.idx, richness: rich });
      } else {
        // Previous is richer — merge live data from current into it
        result[prev.idx] = mergeMatchData(prevMatch, m);
      }
      console.warn(`[dedup] Removed duplicate: ${m.homeTeam.name} vs ${m.awayTeam.name}`);
    } else {
      seen.set(key, { idx: result.length, richness: rich });
      result.push(m);
    }
  }
  return result;
}

function matchRichness(m: Match): number {
  let score = 0;
  if (m.predictions && m.predictions.length > 0) score += 100;
  if ((m as any).recommendations?.length > 0) score += 100;
  const odds = m.odds;
  if (odds) {
    for (const v of Object.values(odds)) {
      if (typeof v === "number" && v > 0) score++;
    }
  }
  const stats = m.stats;
  if (stats) {
    for (const v of Object.values(stats)) {
      if (typeof v === "number" && v > 0) score++;
    }
  }
  if (m.score && ((m.score.home ?? 0) + (m.score.away ?? 0)) > 0) score += 50;
  if (m.status === "live") score += 20;
  return score;
}

function mergeMatchData(primary: Match, secondary: Match): Match {
  const merged = { ...primary };
  // Merge live score if primary lacks it
  const pTotal = (primary.score?.home ?? 0) + (primary.score?.away ?? 0);
  const sTotal = (secondary.score?.home ?? 0) + (secondary.score?.away ?? 0);
  if (sTotal > 0 && pTotal === 0) {
    merged.score = secondary.score;
  }
  if (secondary.score?.halftime && !primary.score?.halftime) {
    merged.score = { ...(merged.score ?? { home: 0, away: 0 }), halftime: secondary.score.halftime };
  }
  // Merge live status
  if (secondary.status === "live" && primary.status !== "live") {
    merged.status = secondary.status;
    merged.period = secondary.period ?? merged.period;
    merged.minute = secondary.minute ?? merged.minute;
  }
  return merged;
}

/** Known Danish Superliga teams — correct leagueId when backend returns wrong/missing leagueId */
const KNOWN_DANISH_TEAMS = new Set([
  "esbjerg", "hillerød", "hillerod", "hvidovre", "kolding if", "kolding", "fc midtjylland", "midtjylland",
  "fc copenhagen", "copenhagen", "brøndby", "brondby", "aalborg", "aab", "nordsjælland",
  "nordsjaelland", "silkeborg", "viborg", "ob", "odense", "randers", "lyngby", "vejle",
]);
function inferLeagueFromTeams(home: string, away: string): string | null {
  const h = normalizeTeamName(home);
  const a = normalizeTeamName(away);
  if (KNOWN_DANISH_TEAMS.has(h) || KNOWN_DANISH_TEAMS.has(a)) return "denmark-superliga";
  return null;
}

export function normalizeMatch(item: any, leagueId: string, idx: number): Match {
  const home = item.home_team
    ?? (typeof item.homeTeam === "string" ? item.homeTeam : item.homeTeam?.name)
    ?? item.home ?? "Home";
  const away = item.away_team
    ?? (typeof item.awayTeam === "string" ? item.awayTeam : item.awayTeam?.name)
    ?? item.away ?? "Away";
  // Heuristic: correct leagueId when backend returns wrong/missing (e.g. Danish teams in EPL group)
  const inferred = inferLeagueFromTeams(home, away);
  // Backend config uses short IDs, frontend uses prefixed IDs
  const LEAGUE_ID_ALIASES: Record<string, string> = {
    "superliga": "denmark-superliga",
    "league-one": "england-league-one",
    "ligue-1": "france-ligue-1",
    "bundesliga": "germany-bundesliga",
    "2-bundesliga": "germany-2-bundesliga",
    "serie-a": "italy-serie-a",
    "serie-b": "italy-serie-b",
    "la-liga": "spain-la-liga",
    "eredivisie": "netherlands-eredivisie",
    "liga-nos": "portugal-liga-nos",
    "primeira-liga": "portugal-liga-nos",
    "super-lig": "turkey-super-lig",
    "mls": "usa-mls",
    "liga-mx": "mexico-liga-mx",
    "primera-division": "primera-division",
    "primera-a": "colombia-primera-a",
    "colombian-primera-a": "colombia-primera-a",
    "a-league": "a-league",
    "pro-league": "pro-league",
  };
  const normalizedLid = LEAGUE_ID_ALIASES[leagueId] ?? leagueId;
  const resolvedLeagueId = inferred ?? normalizedLid;
  const dt = item.match_date ?? item.datetime ?? new Date().toISOString();
  const league = AVAILABLE_LEAGUES.find((l) => l.id === resolvedLeagueId);
  return {
    id: item.id ?? `${resolvedLeagueId}-${resolveTeamAlias(home)}-${resolveTeamAlias(away)}`,
    footystatsId: item.footystatsId ?? undefined,
    apiFootballId: item.apiFootballFixtureId ?? item.apiFootballId ?? undefined,
    leagueId: resolvedLeagueId,
    leagueName: league?.name ?? resolvedLeagueId,
    homeTeam: { name: home, logo: item.homeTeam?.logo ?? "", form: item.homeTeam?.form ?? item.homeForm ?? [], rating: item.homeTeam?.rating || item.ratings?.home || 0 },
    awayTeam: { name: away, logo: item.awayTeam?.logo ?? "", form: item.awayTeam?.form ?? item.awayForm ?? [], rating: item.awayTeam?.rating || item.ratings?.away || 0 },
    datetime: dt,
    venue: item.venue ?? item.stadium ?? "",
    status: item.status ?? "scheduled",
    score: (() => {
      const raw = item.score;
      if (raw && typeof raw.home === "number" && typeof raw.away === "number") {
        return raw;
      }
      // Coerce any non-null fields to numbers — use nullish coalescing
      // to avoid treating 0 as falsy (Number(0) || 0 works by coincidence
      // but Number(val) ?? 0 is semantically correct).
      if (raw && raw.home != null && raw.away != null) {
        return { home: Number(raw.home) ?? 0, away: Number(raw.away) ?? 0, halftime: raw.halftime };
      }
      // For finished or live matches without score, default to 0-0.
      // A live match that just kicked off is at 0-0 until proven otherwise;
      // the /live-scores overlay will update with the real score when available.
      if (item.status === "finished" || item.status === "live") {
        return { home: 0, away: 0 };
      }
      // Discard invalid score objects (e.g. {home: null, away: null})
      return undefined;
    })(),
    period: item.period ?? undefined,
    minute: item.minute ?? undefined,
    minuteUpdatedAt: item.minute != null ? Date.now() : undefined,
    odds: {
      home: item.odds?.home ?? 0,
      draw: item.odds?.draw ?? 0,
      away: item.odds?.away ?? 0,
      over15: item.odds?.over15 ?? 0,
      over25: item.odds?.over25 ?? 0,
      over35: item.odds?.over35 ?? 0,
      over45: item.odds?.over45 ?? 0,
      under25: item.odds?.under25 ?? 0,
      bttsYes: item.odds?.bttsYes ?? 0,
      bttsNo: item.odds?.bttsNo ?? 0,
    },
    stats: {
      homeWinProb: item.stats?.homeWinProb ?? 0,
      drawProb: item.stats?.drawProb ?? 0,
      awayWinProb: item.stats?.awayWinProb ?? 0,
      avgGoals: item.stats?.avgGoals ?? 0,
      bttsProb: item.stats?.bttsProb ?? 0,
      over15Prob: item.stats?.over15Prob ?? 0,
      over25Prob: item.stats?.over25Prob ?? 0,
      over35Prob: item.stats?.over35Prob ?? 0,
      over45Prob: item.stats?.over45Prob ?? 0,
      lambdaHome: item.stats?.lambdaHome ?? 0,
      lambdaAway: item.stats?.lambdaAway ?? 0,
      homePossession: item.stats?.homePossession ?? 0,
      awayPossession: item.stats?.awayPossession ?? 0,
      homeXG: item.stats?.homeXG ?? 0,
      awayXG: item.stats?.awayXG ?? 0,
      homeForm: item.stats?.homeForm ?? item.homeForm ?? item.homeTeam?.form ?? [],
      awayForm: item.stats?.awayForm ?? item.awayForm ?? item.awayTeam?.form ?? [],
      leagueRegime: item.stats?.leagueRegime ?? "",
      leagueVolatility: item.stats?.leagueVolatility ?? "",
      regime: item.stats?.regime ?? "",
      homeCornersPerMatch: item.stats?.homeCornersPerMatch ?? 0,
      awayCornersPerMatch: item.stats?.awayCornersPerMatch ?? 0,
      homeCardsPerMatch: item.stats?.homeCardsPerMatch ?? 0,
      awayCardsPerMatch: item.stats?.awayCardsPerMatch ?? 0,
      homeShotsOnTarget: item.stats?.homeShotsOnTarget ?? undefined,
      awayShotsOnTarget: item.stats?.awayShotsOnTarget ?? undefined,
      homeShotsPerMatch: item.stats?.homeShotsPerMatch ?? undefined,
      awayShotsPerMatch: item.stats?.awayShotsPerMatch ?? undefined,
      homeFoulsPerMatch: item.stats?.homeFoulsPerMatch ?? undefined,
      awayFoulsPerMatch: item.stats?.awayFoulsPerMatch ?? undefined,
      leagueAvgCorners: item.stats?.leagueAvgCorners ?? 0,
      leagueAvgCards: item.stats?.leagueAvgCards ?? 0,
      leagueAvgFouls: item.stats?.leagueAvgFouls ?? undefined,
      leagueAvgShots: item.stats?.leagueAvgShots ?? undefined,
      // League extended
      leagueHomeAdvantage: item.stats?.leagueHomeAdvantage ?? undefined,
      leagueCleanSheetsPct: item.stats?.leagueCleanSheetsPct ?? undefined,
      leagueOver25Pct: item.stats?.leagueOver25Pct ?? undefined,
      leagueXgAvg: item.stats?.leagueXgAvg ?? undefined,
      // Team advanced stats
      homeBttsPercentage: item.stats?.homeBttsPercentage ?? undefined,
      awayBttsPercentage: item.stats?.awayBttsPercentage ?? undefined,
      homeCleanSheetPct: item.stats?.homeCleanSheetPct ?? undefined,
      awayCleanSheetPct: item.stats?.awayCleanSheetPct ?? undefined,
      homeFtsPercentage: item.stats?.homeFtsPercentage ?? undefined,
      awayFtsPercentage: item.stats?.awayFtsPercentage ?? undefined,
      homeOver25Percentage: item.stats?.homeOver25Percentage ?? undefined,
      awayOver25Percentage: item.stats?.awayOver25Percentage ?? undefined,
      homeWinPercentage: item.stats?.homeWinPercentage ?? undefined,
      awayWinPercentage: item.stats?.awayWinPercentage ?? undefined,
      homeXgForAvg: item.stats?.homeXgForAvg ?? undefined,
      awayXgForAvg: item.stats?.awayXgForAvg ?? undefined,
      homeXgAgainstAvg: item.stats?.homeXgAgainstAvg ?? undefined,
      awayXgAgainstAvg: item.stats?.awayXgAgainstAvg ?? undefined,
      homeCornersAgainstPerMatch: item.stats?.homeCornersAgainstPerMatch ?? undefined,
      awayCornersAgainstPerMatch: item.stats?.awayCornersAgainstPerMatch ?? undefined,
      homeCornersCount: item.stats?.homeCornersCount ?? item.home_team_corner_count ?? undefined,
      awayCornersCount: item.stats?.awayCornersCount ?? item.away_team_corner_count ?? undefined,
      homeYellowCards: item.stats?.homeYellowCards ?? item.home_team_yellow_cards ?? undefined,
      awayYellowCards: item.stats?.awayYellowCards ?? item.away_team_yellow_cards ?? undefined,
      homeRedCards: item.stats?.homeRedCards ?? item.home_team_red_cards ?? undefined,
      awayRedCards: item.stats?.awayRedCards ?? item.away_team_red_cards ?? undefined,
      homeLeaguePosition: item.stats?.homeLeaguePosition ?? undefined,
      awayLeaguePosition: item.stats?.awayLeaguePosition ?? undefined,
      homeAvgTotalGoals: item.stats?.homeAvgTotalGoals ?? undefined,
      awayAvgTotalGoals: item.stats?.awayAvgTotalGoals ?? undefined,
    },
    h2h: {
      totalMatches: item.h2h?.totalMatches ?? 0,
      homeWins: item.h2h?.homeWins ?? 0,
      draws: item.h2h?.draws ?? 0,
      awayWins: item.h2h?.awayWins ?? 0,
      avgGoals: item.h2h?.avgGoals ?? 0,
    },
    predictions: item.mercados ?? item.predictions ?? [],
    rejectedInsights: item.stats?.rejected_insights ?? [],
    source: item.source ?? "footystats",
    lastUpdated: item.lastUpdated ?? new Date().toISOString(),
  };
}
