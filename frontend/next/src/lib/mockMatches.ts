/**
 * Mock matches fallback — garante que o dashboard nunca fique vazio.
 * Usado quando PY_BACKEND_URL nao responde E o proxy /api/matches tambem falha.
 *
 * IDs usam os mesmos valores de AVAILABLE_LEAGUES em leagues.ts.
 * Campos seguem o tipo Match de leagues.ts (homeTeam/awayTeam como objetos).
 */

import type { Match } from "./leagues";

function today(hoursOffset: number): string {
  const d = new Date();
  d.setHours(d.getHours() + hoursOffset, 0, 0, 0);
  return d.toISOString();
}

const MOCK_DATA: Match[] = [
  // Premier League
  {
    id: "mock-pl-1",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Arsenal", logo: "", form: ["W", "W", "D", "W", "L"], rating: 8.2 },
    awayTeam: { name: "Chelsea", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.5 },
    datetime: today(2),
    venue: "Emirates Stadium",
    status: "scheduled",
    odds: { home: 1.85, draw: 3.6, away: 4.2, over25: 1.72, under25: 2.1, bttsYes: 1.75, bttsNo: 2.0 },
    stats: { homeWinProb: 0.48, drawProb: 0.26, awayWinProb: 0.26, avgGoals: 2.8, bttsProb: 0.55, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 14, draws: 8, awayWins: 8, avgGoals: 2.6 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-2",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Liverpool", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.5 },
    awayTeam: { name: "Manchester City", logo: "", form: ["W", "D", "W", "W", "D"], rating: 8.7 },
    datetime: today(4),
    venue: "Anfield",
    status: "scheduled",
    odds: { home: 2.25, draw: 3.3, away: 3.1, over25: 1.65, under25: 2.2, bttsYes: 1.68, bttsNo: 2.15 },
    stats: { homeWinProb: 0.40, drawProb: 0.28, awayWinProb: 0.32, avgGoals: 3.1, bttsProb: 0.60, over25Prob: 0.68, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 28, homeWins: 10, draws: 6, awayWins: 12, avgGoals: 2.9 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // La Liga (Spain) — ID corrigido: "spain-la-liga"
  {
    id: "mock-ll-1",
    leagueId: "spain-la-liga",
    leagueName: "La Liga",
    homeTeam: { name: "Real Madrid", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.9 },
    awayTeam: { name: "Barcelona", logo: "", form: ["W", "D", "W", "W", "W"], rating: 8.8 },
    datetime: today(3),
    venue: "Santiago Bernabeu",
    status: "scheduled",
    odds: { home: 2.1, draw: 3.4, away: 3.3, over25: 1.75, under25: 2.05, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.42, drawProb: 0.27, awayWinProb: 0.31, avgGoals: 2.9, bttsProb: 0.57, over25Prob: 0.64, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 50, homeWins: 20, draws: 12, awayWins: 18, avgGoals: 3.0 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ll-2",
    leagueId: "spain-la-liga",
    leagueName: "La Liga",
    homeTeam: { name: "Atletico Madrid", logo: "", form: ["W", "D", "W", "D", "W"], rating: 7.8 },
    awayTeam: { name: "Sevilla", logo: "", form: ["D", "L", "W", "W", "D"], rating: 7.0 },
    datetime: today(5),
    venue: "Wanda Metropolitano",
    status: "scheduled",
    odds: { home: 1.7, draw: 3.5, away: 5.0, over25: 1.9, under25: 1.85, bttsYes: 1.95, bttsNo: 1.82 },
    stats: { homeWinProb: 0.52, drawProb: 0.26, awayWinProb: 0.22, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 24, homeWins: 12, draws: 7, awayWins: 5, avgGoals: 2.2 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // Serie A (Italy) — ID corrigido: "italy-serie-a"
  {
    id: "mock-sa-1",
    leagueId: "italy-serie-a",
    leagueName: "Serie A",
    homeTeam: { name: "AC Milan", logo: "", form: ["D", "W", "L", "W", "W"], rating: 7.6 },
    awayTeam: { name: "Inter Milan", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.3 },
    datetime: today(1),
    venue: "San Siro",
    status: "scheduled",
    odds: { home: 2.6, draw: 3.2, away: 2.7, over25: 1.8, under25: 2.0, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.35, drawProb: 0.30, awayWinProb: 0.35, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 15, draws: 12, awayWins: 13, avgGoals: 2.5 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // Bundesliga (Germany) — ID corrigido: "germany-bundesliga"
  {
    id: "mock-bl-1",
    leagueId: "germany-bundesliga",
    leagueName: "Bundesliga",
    homeTeam: { name: "Bayern Munich", logo: "", form: ["W", "W", "W", "W", "W"], rating: 9.0 },
    awayTeam: { name: "Borussia Dortmund", logo: "", form: ["W", "D", "W", "L", "W"], rating: 8.0 },
    datetime: today(6),
    venue: "Allianz Arena",
    status: "scheduled",
    odds: { home: 1.55, draw: 4.2, away: 5.5, over25: 1.45, under25: 2.6, bttsYes: 1.6, bttsNo: 2.3 },
    stats: { homeWinProb: 0.58, drawProb: 0.22, awayWinProb: 0.20, avgGoals: 3.4, bttsProb: 0.62, over25Prob: 0.75, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 35, homeWins: 18, draws: 8, awayWins: 9, avgGoals: 3.2 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // Ligue 1 (France) — ID corrigido: "france-ligue-1"
  {
    id: "mock-l1-1",
    leagueId: "france-ligue-1",
    leagueName: "Ligue 1",
    homeTeam: { name: "PSG", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.8 },
    awayTeam: { name: "Marseille", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.4 },
    datetime: today(7),
    venue: "Parc des Princes",
    status: "scheduled",
    odds: { home: 1.4, draw: 4.8, away: 7.0, over25: 1.5, under25: 2.5, bttsYes: 1.7, bttsNo: 2.1 },
    stats: { homeWinProb: 0.65, drawProb: 0.20, awayWinProb: 0.15, avgGoals: 3.2, bttsProb: 0.55, over25Prob: 0.72, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 32, homeWins: 20, draws: 6, awayWins: 6, avgGoals: 2.8 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // Brasileirao — ID corrigido: "brazil-serie-a"
  {
    id: "mock-br-1",
    leagueId: "brazil-serie-a",
    leagueName: "Serie A",
    homeTeam: { name: "Flamengo", logo: "", form: ["W", "D", "W", "W", "L"], rating: 7.9 },
    awayTeam: { name: "Palmeiras", logo: "", form: ["W", "W", "D", "W", "W"], rating: 8.1 },
    datetime: today(8),
    venue: "Maracana",
    status: "scheduled",
    odds: { home: 2.3, draw: 3.1, away: 3.2, over25: 1.85, under25: 1.95, bttsYes: 1.8, bttsNo: 2.0 },
    stats: { homeWinProb: 0.39, drawProb: 0.29, awayWinProb: 0.32, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 9, draws: 7, awayWins: 6, avgGoals: 2.3 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
];

export function getMockMatches(leaguesParam: string): Match[] {
  const ids = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);
  if (ids.length === 0) return MOCK_DATA;
  return MOCK_DATA.filter((m) => ids.includes(m.leagueId));
}

/** Alias for backward compatibility with route.ts */
export function generateMockMatches(leagueIds: string[]): Match[] {
  if (leagueIds.length === 0) return MOCK_DATA;
  return MOCK_DATA.filter((m) => leagueIds.includes(m.leagueId));
}
