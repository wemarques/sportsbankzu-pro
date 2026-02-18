/**
 * Mock matches fallback — garante que o dashboard nunca fique vazio.
 * Usado quando PY_BACKEND_URL nao responde E o proxy /api/matches tambem falha.
 *
 * IDs usam os mesmos valores de AVAILABLE_LEAGUES em leagues.ts.
 * Campos seguem o tipo Match de leagues.ts (homeTeam/awayTeam como objetos).
 *
 * Dados baseados na imagem de referencia do dashboard (fonte da verdade).
 */

import type { Match } from "./leagues";

function today(hoursOffset: number): string {
  const d = new Date();
  d.setHours(d.getHours() + hoursOffset, 0, 0, 0);
  return d.toISOString();
}

const MOCK_DATA: Match[] = [
  // ═══════════════════════════════════════════════
  // Premier League — 10 matches (reference image)
  // ═══════════════════════════════════════════════
  {
    id: "mock-pl-01",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Manchester City", logo: "", form: ["W", "W", "D", "W", "W"], rating: 8.9 },
    awayTeam: { name: "Wolverhampton Wanderers", logo: "", form: ["L", "D", "W", "L", "D"], rating: 6.5 },
    datetime: today(2),
    venue: "Etihad Stadium",
    status: "scheduled",
    odds: { home: 1.25, draw: 5.8, away: 11.0, over25: 1.42, under25: 2.75, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.72, drawProb: 0.16, awayWinProb: 0.12, avgGoals: 3.2, bttsProb: 0.52, over25Prob: 0.78, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 20, homeWins: 14, draws: 3, awayWins: 3, avgGoals: 3.1 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-02",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Arsenal", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.5 },
    awayTeam: { name: "Manchester United", logo: "", form: ["D", "W", "L", "W", "D"], rating: 7.4 },
    datetime: today(5),
    venue: "Emirates Stadium",
    status: "scheduled",
    odds: { home: 1.65, draw: 3.9, away: 5.2, over25: 1.68, under25: 2.15, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.55, drawProb: 0.24, awayWinProb: 0.21, avgGoals: 2.9, bttsProb: 0.56, over25Prob: 0.65, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 16, draws: 10, awayWins: 14, avgGoals: 2.7 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-03",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Liverpool", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.7 },
    awayTeam: { name: "Chelsea", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.8 },
    datetime: today(8),
    venue: "Anfield",
    status: "scheduled",
    odds: { home: 1.80, draw: 3.6, away: 4.5, over25: 1.62, under25: 2.25, bttsYes: 1.68, bttsNo: 2.12 },
    stats: { homeWinProb: 0.50, drawProb: 0.26, awayWinProb: 0.24, avgGoals: 3.0, bttsProb: 0.58, over25Prob: 0.67, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 35, homeWins: 14, draws: 9, awayWins: 12, avgGoals: 2.8 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-04",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Tottenham Hotspur", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.6 },
    awayTeam: { name: "Newcastle United", logo: "", form: ["W", "W", "D", "W", "L"], rating: 7.9 },
    datetime: today(2),
    venue: "Tottenham Hotspur Stadium",
    status: "scheduled",
    odds: { home: 2.30, draw: 3.4, away: 3.1, over25: 1.70, under25: 2.10, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.38, drawProb: 0.28, awayWinProb: 0.34, avgGoals: 2.8, bttsProb: 0.55, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 25, homeWins: 10, draws: 7, awayWins: 8, avgGoals: 2.6 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-05",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Brighton & Hove Albion", logo: "", form: ["D", "W", "W", "D", "W"], rating: 7.3 },
    awayTeam: { name: "Fulham", logo: "", form: ["L", "D", "W", "W", "D"], rating: 6.9 },
    datetime: today(5),
    venue: "Amex Stadium",
    status: "scheduled",
    odds: { home: 1.95, draw: 3.5, away: 4.0, over25: 1.78, under25: 2.02, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.45, drawProb: 0.27, awayWinProb: 0.28, avgGoals: 2.6, bttsProb: 0.52, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 15, homeWins: 7, draws: 4, awayWins: 4, avgGoals: 2.4 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-06",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "West Ham United", logo: "", form: ["L", "D", "W", "L", "W"], rating: 6.8 },
    awayTeam: { name: "Sunderland", logo: "", form: ["D", "L", "D", "W", "L"], rating: 6.2 },
    datetime: today(8),
    venue: "London Stadium",
    status: "scheduled",
    odds: { home: 1.75, draw: 3.7, away: 4.8, over25: 1.82, under25: 1.98, bttsYes: 1.85, bttsNo: 1.95 },
    stats: { homeWinProb: 0.50, drawProb: 0.25, awayWinProb: 0.25, avgGoals: 2.5, bttsProb: 0.50, over25Prob: 0.55, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 9, draws: 5, awayWins: 4, avgGoals: 2.3 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-07",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Burnley", logo: "", form: ["L", "L", "D", "W", "L"], rating: 5.8 },
    awayTeam: { name: "AFC Bournemouth", logo: "", form: ["W", "D", "W", "D", "W"], rating: 7.0 },
    datetime: today(2),
    venue: "Turf Moor",
    status: "scheduled",
    odds: { home: 2.80, draw: 3.3, away: 2.5, over25: 1.85, under25: 1.95, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.32, drawProb: 0.28, awayWinProb: 0.40, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 5, draws: 3, awayWins: 4, avgGoals: 2.5 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-08",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Brentford", logo: "", form: ["W", "D", "W", "L", "D"], rating: 7.1 },
    awayTeam: { name: "Nottingham Forest", logo: "", form: ["D", "W", "L", "W", "W"], rating: 7.0 },
    datetime: today(5),
    venue: "Gtech Community Stadium",
    status: "scheduled",
    odds: { home: 2.10, draw: 3.4, away: 3.5, over25: 1.75, under25: 2.05, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.42, drawProb: 0.28, awayWinProb: 0.30, avgGoals: 2.7, bttsProb: 0.53, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.6 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-09",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Crystal Palace", logo: "", form: ["D", "W", "L", "D", "W"], rating: 6.9 },
    awayTeam: { name: "Aston Villa", logo: "", form: ["W", "W", "W", "D", "W"], rating: 7.8 },
    datetime: today(8),
    venue: "Selhurst Park",
    status: "scheduled",
    odds: { home: 2.90, draw: 3.3, away: 2.4, over25: 1.80, under25: 2.00, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.30, drawProb: 0.28, awayWinProb: 0.42, avgGoals: 2.6, bttsProb: 0.54, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 8, draws: 6, awayWins: 8, avgGoals: 2.4 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-10",
    leagueId: "premier-league",
    leagueName: "Premier League",
    homeTeam: { name: "Everton", logo: "", form: ["L", "D", "L", "W", "D"], rating: 6.2 },
    awayTeam: { name: "Leicester City", logo: "", form: ["D", "L", "W", "L", "W"], rating: 6.5 },
    datetime: today(5),
    venue: "Goodison Park",
    status: "scheduled",
    odds: { home: 2.40, draw: 3.3, away: 3.0, over25: 1.90, under25: 1.90, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.36, drawProb: 0.29, awayWinProb: 0.35, avgGoals: 2.4, bttsProb: 0.50, over25Prob: 0.53, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 12, draws: 8, awayWins: 10, avgGoals: 2.5 },
    source: "footystats",
    lastUpdated: new Date().toISOString(),
  },
  // ═══════════════════════════════════════════════
  // La Liga — ID: "spain-la-liga"
  // ═══════════════════════════════════════════════
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
  // ═══════════════════════════════════════════════
  // Serie A (Italy) — ID: "italy-serie-a"
  // ═══════════════════════════════════════════════
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
  // ═══════════════════════════════════════════════
  // Bundesliga (Germany) — ID: "germany-bundesliga"
  // ═══════════════════════════════════════════════
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
  // ═══════════════════════════════════════════════
  // Ligue 1 (France) — ID: "france-ligue-1"
  // ═══════════════════════════════════════════════
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
  // ═══════════════════════════════════════════════
  // Brasileirao — ID: "brazil-serie-a"
  // ═══════════════════════════════════════════════
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
