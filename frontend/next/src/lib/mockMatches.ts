/**
 * Mock matches — DEVELOPMENT ONLY.
 *
 * Em producao, o proxy route.ts nunca importa este arquivo.
 * Mock data so e usado quando NODE_ENV === "development" para
 * permitir desenvolvimento local sem backend.
 *
 * Em producao, o dashboard mostra um EmptyState com mensagem
 * clara quando o backend esta indisponivel.
 *
 * IDs usam os mesmos valores de AVAILABLE_LEAGUES em leagues.ts.
 * Campos seguem o tipo Match de leagues.ts (homeTeam/awayTeam como objetos).
 *
 * 22 ligas — temporada 2025/26 — com predictions (prognosticos).
 */

import type { Match } from "./leagues";

function today(hoursOffset: number): string {
  const d = new Date();
  d.setHours(d.getHours() + hoursOffset, 0, 0, 0);
  return d.toISOString();
}

const MOCK_DATA: Match[] = [
  // ═══════════════════════════════════════════════
  // Premier League — 10 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-pl-01", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Manchester City", logo: "", form: ["W", "W", "D", "W", "W"], rating: 8.9 },
    awayTeam: { name: "Wolverhampton Wanderers", logo: "", form: ["L", "D", "W", "L", "D"], rating: 6.5 },
    datetime: today(2), venue: "Etihad Stadium", status: "scheduled",
    odds: { home: 1.25, draw: 5.8, away: 11.0, over25: 1.42, under25: 2.75, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.72, drawProb: 0.16, awayWinProb: 0.12, avgGoals: 3.2, bttsProb: 0.52, over25Prob: 0.78, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 20, homeWins: 14, draws: 3, awayWins: 3, avgGoals: 3.1 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE*", prob_min: 63, prob_max: 65, odd_minima: 1.54, alerta: "Odd muito baixa" },
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-02", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Arsenal", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.5 },
    awayTeam: { name: "Manchester United", logo: "", form: ["D", "W", "L", "W", "D"], rating: 7.4 },
    datetime: today(5), venue: "Emirates Stadium", status: "scheduled",
    odds: { home: 1.65, draw: 3.9, away: 5.2, over25: 1.68, under25: 2.15, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.55, drawProb: 0.24, awayWinProb: 0.21, avgGoals: 2.9, bttsProb: 0.56, over25Prob: 0.65, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 16, draws: 10, awayWins: 14, avgGoals: 2.7 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.49 },
      { mercado: "BTTS — SIM", status: "NEUTRO", prob_min: 54, prob_max: 56, odd_minima: 1.72 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-03", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Liverpool", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.7 },
    awayTeam: { name: "Chelsea", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.8 },
    datetime: today(8), venue: "Anfield", status: "scheduled",
    odds: { home: 1.80, draw: 3.6, away: 4.5, over25: 1.62, under25: 2.25, bttsYes: 1.68, bttsNo: 2.12 },
    stats: { homeWinProb: 0.50, drawProb: 0.26, awayWinProb: 0.24, avgGoals: 3.0, bttsProb: 0.58, over25Prob: 0.67, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 35, homeWins: 14, draws: 9, awayWins: 12, avgGoals: 2.8 },
    predictions: [
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 72, prob_max: 74, odd_minima: 1.35 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-04", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Tottenham Hotspur", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.6 },
    awayTeam: { name: "Newcastle United", logo: "", form: ["W", "W", "D", "W", "L"], rating: 7.9 },
    datetime: today(2), venue: "Tottenham Hotspur Stadium", status: "scheduled",
    odds: { home: 2.30, draw: 3.4, away: 3.1, over25: 1.70, under25: 2.10, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.38, drawProb: 0.28, awayWinProb: 0.34, avgGoals: 2.8, bttsProb: 0.55, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 25, homeWins: 10, draws: 7, awayWins: 8, avgGoals: 2.6 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 62, prob_max: 65, odd_minima: 1.54 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-05", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Brighton & Hove Albion", logo: "", form: ["D", "W", "W", "D", "W"], rating: 7.3 },
    awayTeam: { name: "Fulham", logo: "", form: ["L", "D", "W", "W", "D"], rating: 6.9 },
    datetime: today(5), venue: "Amex Stadium", status: "scheduled",
    odds: { home: 1.95, draw: 3.5, away: 4.0, over25: 1.78, under25: 2.02, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.45, drawProb: 0.27, awayWinProb: 0.28, avgGoals: 2.6, bttsProb: 0.52, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 15, homeWins: 7, draws: 4, awayWins: 4, avgGoals: 2.4 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 68, odd_minima: 1.47 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-06", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "West Ham United", logo: "", form: ["L", "D", "W", "L", "W"], rating: 6.8 },
    awayTeam: { name: "Sunderland", logo: "", form: ["D", "L", "D", "W", "L"], rating: 6.2 },
    datetime: today(8), venue: "London Stadium", status: "scheduled",
    odds: { home: 1.75, draw: 3.7, away: 4.8, over25: 1.82, under25: 1.98, bttsYes: 1.85, bttsNo: 1.95 },
    stats: { homeWinProb: 0.50, drawProb: 0.25, awayWinProb: 0.25, avgGoals: 2.5, bttsProb: 0.50, over25Prob: 0.55, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 9, draws: 5, awayWins: 4, avgGoals: 2.3 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 67, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-07", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Burnley", logo: "", form: ["L", "L", "D", "W", "L"], rating: 5.8 },
    awayTeam: { name: "AFC Bournemouth", logo: "", form: ["W", "D", "W", "D", "W"], rating: 7.0 },
    datetime: today(2), venue: "Turf Moor", status: "scheduled",
    odds: { home: 2.80, draw: 3.3, away: 2.5, over25: 1.85, under25: 1.95, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.32, drawProb: 0.28, awayWinProb: 0.40, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 5, draws: 3, awayWins: 4, avgGoals: 2.5 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 64, prob_max: 66, odd_minima: 1.52 },
      { mercado: "BTTS — SIM", status: "NEUTRO", prob_min: 52, prob_max: 54, odd_minima: 1.78 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-08", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Brentford", logo: "", form: ["W", "D", "W", "L", "D"], rating: 7.1 },
    awayTeam: { name: "Nottingham Forest", logo: "", form: ["D", "W", "L", "W", "W"], rating: 7.0 },
    datetime: today(5), venue: "Gtech Community Stadium", status: "scheduled",
    odds: { home: 2.10, draw: 3.4, away: 3.5, over25: 1.75, under25: 2.05, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.42, drawProb: 0.28, awayWinProb: 0.30, avgGoals: 2.7, bttsProb: 0.53, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.6 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 63, prob_max: 66, odd_minima: 1.52 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-09", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Crystal Palace", logo: "", form: ["D", "W", "L", "D", "W"], rating: 6.9 },
    awayTeam: { name: "Aston Villa", logo: "", form: ["W", "W", "W", "D", "W"], rating: 7.8 },
    datetime: today(8), venue: "Selhurst Park", status: "scheduled",
    odds: { home: 2.90, draw: 3.3, away: 2.4, over25: 1.80, under25: 2.00, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.30, drawProb: 0.28, awayWinProb: 0.42, avgGoals: 2.6, bttsProb: 0.54, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 8, draws: 6, awayWins: 8, avgGoals: 2.4 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pl-10", leagueId: "premier-league", leagueName: "Premier League",
    homeTeam: { name: "Everton", logo: "", form: ["L", "D", "L", "W", "D"], rating: 6.2 },
    awayTeam: { name: "Leeds United", logo: "", form: ["D", "L", "W", "L", "W"], rating: 6.5 },
    datetime: today(5), venue: "Goodison Park", status: "scheduled",
    odds: { home: 2.40, draw: 3.3, away: 3.0, over25: 1.90, under25: 1.90, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.36, drawProb: 0.29, awayWinProb: 0.35, avgGoals: 2.4, bttsProb: 0.50, over25Prob: 0.53, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 12, draws: 8, awayWins: 10, avgGoals: 2.5 },
    predictions: [
      { mercado: "Under 3.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Championship — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ch-01", leagueId: "championship", leagueName: "Championship",
    homeTeam: { name: "Leeds United", logo: "", form: ["W", "W", "D", "W", "L"], rating: 7.6 },
    awayTeam: { name: "Leicester City", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.4 },
    datetime: today(3), venue: "Elland Road", status: "scheduled",
    odds: { home: 2.10, draw: 3.3, away: 3.5, over25: 1.78, under25: 2.02, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.42, drawProb: 0.28, awayWinProb: 0.30, avgGoals: 2.6, bttsProb: 0.54, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 7, draws: 5, awayWins: 6, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ch-02", leagueId: "championship", leagueName: "Championship",
    homeTeam: { name: "Burnley", logo: "", form: ["W", "D", "W", "W", "W"], rating: 7.2 },
    awayTeam: { name: "Sunderland", logo: "", form: ["D", "L", "W", "D", "W"], rating: 6.8 },
    datetime: today(5), venue: "Turf Moor", status: "scheduled",
    odds: { home: 1.70, draw: 3.6, away: 5.0, over25: 1.82, under25: 1.98, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.52, drawProb: 0.25, awayWinProb: 0.23, avgGoals: 2.5, bttsProb: 0.51, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 14, homeWins: 6, draws: 4, awayWins: 4, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 67, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ch-03", leagueId: "championship", leagueName: "Championship",
    homeTeam: { name: "Sheffield United", logo: "", form: ["L", "W", "D", "L", "W"], rating: 6.5 },
    awayTeam: { name: "West Bromwich Albion", logo: "", form: ["W", "D", "L", "W", "D"], rating: 6.7 },
    datetime: today(7), venue: "Bramall Lane", status: "scheduled",
    odds: { home: 2.35, draw: 3.2, away: 3.1, over25: 1.85, under25: 1.95, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.37, drawProb: 0.29, awayWinProb: 0.34, avgGoals: 2.4, bttsProb: 0.52, over25Prob: 0.54, regime: "NORMAL" },
    h2h: { totalMatches: 16, homeWins: 6, draws: 5, awayWins: 5, avgGoals: 2.2 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 69, prob_max: 72, odd_minima: 1.39 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // La Liga — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ll-01", leagueId: "spain-la-liga", leagueName: "La Liga",
    homeTeam: { name: "Real Madrid", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.9 },
    awayTeam: { name: "Barcelona", logo: "", form: ["W", "D", "W", "W", "W"], rating: 8.8 },
    datetime: today(3), venue: "Santiago Bernabeu", status: "scheduled",
    odds: { home: 2.1, draw: 3.4, away: 3.3, over25: 1.75, under25: 2.05, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.42, drawProb: 0.27, awayWinProb: 0.31, avgGoals: 2.9, bttsProb: 0.57, over25Prob: 0.64, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 50, homeWins: 20, draws: 12, awayWins: 18, avgGoals: 3.0 },
    predictions: [
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 72, prob_max: 74, odd_minima: 1.35 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ll-02", leagueId: "spain-la-liga", leagueName: "La Liga",
    homeTeam: { name: "Atletico Madrid", logo: "", form: ["W", "D", "W", "D", "W"], rating: 7.8 },
    awayTeam: { name: "Sevilla", logo: "", form: ["D", "L", "W", "W", "D"], rating: 7.0 },
    datetime: today(5), venue: "Civitas Metropolitano", status: "scheduled",
    odds: { home: 1.7, draw: 3.5, away: 5.0, over25: 1.9, under25: 1.85, bttsYes: 1.95, bttsNo: 1.82 },
    stats: { homeWinProb: 0.52, drawProb: 0.26, awayWinProb: 0.22, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 24, homeWins: 12, draws: 7, awayWins: 5, avgGoals: 2.2 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 70, prob_max: 73, odd_minima: 1.37 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ll-03", leagueId: "spain-la-liga", leagueName: "La Liga",
    homeTeam: { name: "Real Sociedad", logo: "", form: ["W", "D", "D", "W", "L"], rating: 7.2 },
    awayTeam: { name: "Villarreal", logo: "", form: ["W", "W", "D", "L", "W"], rating: 7.3 },
    datetime: today(7), venue: "Reale Arena", status: "scheduled",
    odds: { home: 2.25, draw: 3.3, away: 3.2, over25: 1.82, under25: 1.98, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.39, drawProb: 0.28, awayWinProb: 0.33, avgGoals: 2.5, bttsProb: 0.53, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 20, homeWins: 8, draws: 6, awayWins: 6, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Serie A (Italy) — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-sa-01", leagueId: "italy-serie-a", leagueName: "Serie A",
    homeTeam: { name: "AC Milan", logo: "", form: ["D", "W", "L", "W", "W"], rating: 7.6 },
    awayTeam: { name: "Inter Milan", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.3 },
    datetime: today(1), venue: "San Siro", status: "scheduled",
    odds: { home: 2.6, draw: 3.2, away: 2.7, over25: 1.8, under25: 2.0, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.35, drawProb: 0.30, awayWinProb: 0.35, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 15, draws: 12, awayWins: 13, avgGoals: 2.5 },
    predictions: [{ mercado: "BTTS — SIM", status: "NEUTRO", prob_min: 52, prob_max: 54, odd_minima: 1.78 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-sa-02", leagueId: "italy-serie-a", leagueName: "Serie A",
    homeTeam: { name: "Juventus", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.8 },
    awayTeam: { name: "Napoli", logo: "", form: ["W", "W", "D", "W", "W"], rating: 8.1 },
    datetime: today(4), venue: "Allianz Stadium", status: "scheduled",
    odds: { home: 2.20, draw: 3.3, away: 3.2, over25: 1.85, under25: 1.95, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.40, drawProb: 0.28, awayWinProb: 0.32, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 12, draws: 9, awayWins: 9, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 67, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-sa-03", leagueId: "italy-serie-a", leagueName: "Serie A",
    homeTeam: { name: "Roma", logo: "", form: ["D", "L", "W", "D", "W"], rating: 7.2 },
    awayTeam: { name: "Lazio", logo: "", form: ["W", "D", "W", "L", "D"], rating: 7.1 },
    datetime: today(6), venue: "Stadio Olimpico", status: "scheduled",
    odds: { home: 2.30, draw: 3.2, away: 3.1, over25: 1.82, under25: 1.98, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.38, drawProb: 0.29, awayWinProb: 0.33, avgGoals: 2.6, bttsProb: 0.53, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 28, homeWins: 11, draws: 8, awayWins: 9, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Bundesliga (Germany) — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-bl-01", leagueId: "germany-bundesliga", leagueName: "Bundesliga",
    homeTeam: { name: "Bayern Munich", logo: "", form: ["W", "W", "W", "W", "W"], rating: 9.0 },
    awayTeam: { name: "Borussia Dortmund", logo: "", form: ["W", "D", "W", "L", "W"], rating: 8.0 },
    datetime: today(6), venue: "Allianz Arena", status: "scheduled",
    odds: { home: 1.55, draw: 4.2, away: 5.5, over25: 1.45, under25: 2.6, bttsYes: 1.6, bttsNo: 2.3 },
    stats: { homeWinProb: 0.58, drawProb: 0.22, awayWinProb: 0.20, avgGoals: 3.4, bttsProb: 0.62, over25Prob: 0.75, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 35, homeWins: 18, draws: 8, awayWins: 9, avgGoals: 3.2 },
    predictions: [
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 73, prob_max: 75, odd_minima: 1.33 },
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-bl-02", leagueId: "germany-bundesliga", leagueName: "Bundesliga",
    homeTeam: { name: "RB Leipzig", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.8 },
    awayTeam: { name: "Bayer Leverkusen", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.2 },
    datetime: today(4), venue: "Red Bull Arena", status: "scheduled",
    odds: { home: 2.40, draw: 3.4, away: 2.9, over25: 1.65, under25: 2.20, bttsYes: 1.70, bttsNo: 2.10 },
    stats: { homeWinProb: 0.36, drawProb: 0.27, awayWinProb: 0.37, avgGoals: 3.0, bttsProb: 0.58, over25Prob: 0.68, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 15, homeWins: 6, draws: 4, awayWins: 5, avgGoals: 3.1 },
    predictions: [
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 },
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-bl-03", leagueId: "germany-bundesliga", leagueName: "Bundesliga",
    homeTeam: { name: "Eintracht Frankfurt", logo: "", form: ["D", "W", "W", "L", "W"], rating: 7.3 },
    awayTeam: { name: "VfB Stuttgart", logo: "", form: ["W", "D", "L", "W", "D"], rating: 7.1 },
    datetime: today(8), venue: "Deutsche Bank Park", status: "scheduled",
    odds: { home: 2.05, draw: 3.4, away: 3.6, over25: 1.72, under25: 2.08, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.43, drawProb: 0.27, awayWinProb: 0.30, avgGoals: 2.8, bttsProb: 0.55, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 5, draws: 3, awayWins: 4, avgGoals: 2.7 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 63, prob_max: 65, odd_minima: 1.54 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Ligue 1 (France) — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-l1-01", leagueId: "france-ligue-1", leagueName: "Ligue 1",
    homeTeam: { name: "PSG", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.8 },
    awayTeam: { name: "Marseille", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.4 },
    datetime: today(7), venue: "Parc des Princes", status: "scheduled",
    odds: { home: 1.4, draw: 4.8, away: 7.0, over25: 1.5, under25: 2.5, bttsYes: 1.7, bttsNo: 2.1 },
    stats: { homeWinProb: 0.65, drawProb: 0.20, awayWinProb: 0.15, avgGoals: 3.2, bttsProb: 0.55, over25Prob: 0.72, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 32, homeWins: 20, draws: 6, awayWins: 6, avgGoals: 2.8 },
    predictions: [
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-l1-02", leagueId: "france-ligue-1", leagueName: "Ligue 1",
    homeTeam: { name: "Lyon", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.3 },
    awayTeam: { name: "Monaco", logo: "", form: ["W", "W", "D", "W", "D"], rating: 7.5 },
    datetime: today(4), venue: "Groupama Stadium", status: "scheduled",
    odds: { home: 2.20, draw: 3.4, away: 3.2, over25: 1.75, under25: 2.05, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.40, drawProb: 0.27, awayWinProb: 0.33, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 9, draws: 6, awayWins: 7, avgGoals: 2.6 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 64, prob_max: 66, odd_minima: 1.52 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Brasileirao Serie A — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-br-01", leagueId: "brazil-serie-a", leagueName: "Serie A",
    homeTeam: { name: "Flamengo", logo: "", form: ["W", "D", "W", "W", "L"], rating: 7.9 },
    awayTeam: { name: "Palmeiras", logo: "", form: ["W", "W", "D", "W", "W"], rating: 8.1 },
    datetime: today(8), venue: "Maracana", status: "scheduled",
    odds: { home: 2.3, draw: 3.1, away: 3.2, over25: 1.85, under25: 1.95, bttsYes: 1.8, bttsNo: 2.0 },
    stats: { homeWinProb: 0.39, drawProb: 0.29, awayWinProb: 0.32, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 9, draws: 7, awayWins: 6, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-br-02", leagueId: "brazil-serie-a", leagueName: "Serie A",
    homeTeam: { name: "Corinthians", logo: "", form: ["D", "W", "L", "W", "D"], rating: 7.0 },
    awayTeam: { name: "Sao Paulo", logo: "", form: ["W", "D", "W", "D", "L"], rating: 7.2 },
    datetime: today(5), venue: "Neo Quimica Arena", status: "scheduled",
    odds: { home: 2.40, draw: 3.2, away: 3.0, over25: 1.88, under25: 1.92, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.37, drawProb: 0.28, awayWinProb: 0.35, avgGoals: 2.4, bttsProb: 0.50, over25Prob: 0.53, regime: "NORMAL" },
    h2h: { totalMatches: 25, homeWins: 10, draws: 8, awayWins: 7, avgGoals: 2.2 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 69, prob_max: 72, odd_minima: 1.39 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-br-03", leagueId: "brazil-serie-a", leagueName: "Serie A",
    homeTeam: { name: "Internacional", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.4 },
    awayTeam: { name: "Atletico Mineiro", logo: "", form: ["D", "L", "W", "D", "W"], rating: 7.1 },
    datetime: today(3), venue: "Beira-Rio", status: "scheduled",
    odds: { home: 1.90, draw: 3.4, away: 4.2, over25: 1.80, under25: 2.00, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.46, drawProb: 0.27, awayWinProb: 0.27, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 20, homeWins: 8, draws: 6, awayWins: 6, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Primera Division (Argentina) — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ar-01", leagueId: "primera-division", leagueName: "Primera Division",
    homeTeam: { name: "Boca Juniors", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.5 },
    awayTeam: { name: "River Plate", logo: "", form: ["W", "W", "D", "W", "D"], rating: 7.8 },
    datetime: today(6), venue: "La Bombonera", status: "scheduled",
    odds: { home: 2.30, draw: 3.1, away: 3.2, over25: 1.85, under25: 1.95, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.38, drawProb: 0.29, awayWinProb: 0.33, avgGoals: 2.4, bttsProb: 0.52, over25Prob: 0.54, regime: "NORMAL" },
    h2h: { totalMatches: 50, homeWins: 20, draws: 15, awayWins: 15, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ar-02", leagueId: "primera-division", leagueName: "Primera Division",
    homeTeam: { name: "Racing Club", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.0 },
    awayTeam: { name: "Independiente", logo: "", form: ["D", "L", "W", "D", "L"], rating: 6.6 },
    datetime: today(4), venue: "El Cilindro", status: "scheduled",
    odds: { home: 1.85, draw: 3.4, away: 4.5, over25: 1.90, under25: 1.90, bttsYes: 1.85, bttsNo: 1.95 },
    stats: { homeWinProb: 0.48, drawProb: 0.26, awayWinProb: 0.26, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 12, draws: 10, awayWins: 8, avgGoals: 2.1 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 70, prob_max: 73, odd_minima: 1.37 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // A-League (Australia) — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-al-01", leagueId: "a-league", leagueName: "A-League",
    homeTeam: { name: "Melbourne Victory", logo: "", form: ["W", "D", "W", "W", "L"], rating: 7.0 },
    awayTeam: { name: "Sydney FC", logo: "", form: ["W", "W", "D", "L", "W"], rating: 7.2 },
    datetime: today(2), venue: "AAMI Park", status: "scheduled",
    odds: { home: 2.20, draw: 3.3, away: 3.3, over25: 1.78, under25: 2.02, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.40, drawProb: 0.28, awayWinProb: 0.32, avgGoals: 2.7, bttsProb: 0.55, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 7, draws: 5, awayWins: 6, avgGoals: 2.6 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 63, prob_max: 65, odd_minima: 1.54 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-al-02", leagueId: "a-league", leagueName: "A-League",
    homeTeam: { name: "Western Sydney Wanderers", logo: "", form: ["L", "D", "W", "L", "D"], rating: 6.2 },
    awayTeam: { name: "Melbourne City", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.1 },
    datetime: today(5), venue: "CommBank Stadium", status: "scheduled",
    odds: { home: 2.80, draw: 3.3, away: 2.5, over25: 1.82, under25: 1.98, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.31, drawProb: 0.28, awayWinProb: 0.41, avgGoals: 2.6, bttsProb: 0.53, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 14, homeWins: 5, draws: 4, awayWins: 5, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Austria Bundesliga — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ab-01", leagueId: "austria-bundesliga", leagueName: "Bundesliga",
    homeTeam: { name: "Red Bull Salzburg", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.0 },
    awayTeam: { name: "Rapid Wien", logo: "", form: ["D", "W", "L", "W", "D"], rating: 6.8 },
    datetime: today(3), venue: "Red Bull Arena", status: "scheduled",
    odds: { home: 1.50, draw: 4.0, away: 6.5, over25: 1.55, under25: 2.40, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.60, drawProb: 0.22, awayWinProb: 0.18, avgGoals: 3.0, bttsProb: 0.56, over25Prob: 0.68, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 20, homeWins: 12, draws: 4, awayWins: 4, avgGoals: 2.9 },
    predictions: [{ mercado: "Over 2.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ab-02", leagueId: "austria-bundesliga", leagueName: "Bundesliga",
    homeTeam: { name: "Sturm Graz", logo: "", form: ["W", "D", "W", "W", "L"], rating: 7.2 },
    awayTeam: { name: "LASK", logo: "", form: ["D", "L", "W", "D", "W"], rating: 6.5 },
    datetime: today(6), venue: "Merkur Arena", status: "scheduled",
    odds: { home: 1.85, draw: 3.5, away: 4.2, over25: 1.80, under25: 2.00, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.47, drawProb: 0.26, awayWinProb: 0.27, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 5, draws: 3, awayWins: 4, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Pro League (Belgium) — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-be-01", leagueId: "pro-league", leagueName: "Pro League",
    homeTeam: { name: "Club Brugge", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.8 },
    awayTeam: { name: "Anderlecht", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.3 },
    datetime: today(3), venue: "Jan Breydel Stadium", status: "scheduled",
    odds: { home: 1.75, draw: 3.6, away: 4.8, over25: 1.72, under25: 2.08, bttsYes: 1.70, bttsNo: 2.10 },
    stats: { homeWinProb: 0.50, drawProb: 0.26, awayWinProb: 0.24, avgGoals: 2.8, bttsProb: 0.57, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 20, homeWins: 9, draws: 5, awayWins: 6, avgGoals: 2.7 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 63, prob_max: 65, odd_minima: 1.54 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-be-02", leagueId: "pro-league", leagueName: "Pro League",
    homeTeam: { name: "Gent", logo: "", form: ["D", "W", "L", "W", "D"], rating: 7.0 },
    awayTeam: { name: "Standard Liege", logo: "", form: ["L", "D", "W", "L", "W"], rating: 6.5 },
    datetime: today(6), venue: "Ghelamco Arena", status: "scheduled",
    odds: { home: 1.90, draw: 3.4, away: 4.2, over25: 1.78, under25: 2.02, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.46, drawProb: 0.27, awayWinProb: 0.27, avgGoals: 2.6, bttsProb: 0.54, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 15, homeWins: 6, draws: 5, awayWins: 4, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Brazil Serie B — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-brb-01", leagueId: "brazil-serie-b", leagueName: "Serie B",
    homeTeam: { name: "Santos", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.5 },
    awayTeam: { name: "Sport Recife", logo: "", form: ["D", "L", "W", "D", "L"], rating: 6.4 },
    datetime: today(4), venue: "Vila Belmiro", status: "scheduled",
    odds: { home: 1.65, draw: 3.5, away: 5.5, over25: 1.85, under25: 1.95, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.54, drawProb: 0.25, awayWinProb: 0.21, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 6, draws: 3, awayWins: 3, avgGoals: 2.1 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 71, prob_max: 73, odd_minima: 1.37 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-brb-02", leagueId: "brazil-serie-b", leagueName: "Serie B",
    homeTeam: { name: "Ceara", logo: "", form: ["W", "D", "L", "W", "D"], rating: 6.6 },
    awayTeam: { name: "Goias", logo: "", form: ["L", "W", "D", "L", "W"], rating: 6.3 },
    datetime: today(7), venue: "Arena Castelao", status: "scheduled",
    odds: { home: 2.10, draw: 3.2, away: 3.5, over25: 1.92, under25: 1.88, bttsYes: 1.85, bttsNo: 1.95 },
    stats: { homeWinProb: 0.42, drawProb: 0.28, awayWinProb: 0.30, avgGoals: 2.2, bttsProb: 0.46, over25Prob: 0.48, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.0 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 73, prob_max: 75, odd_minima: 1.33 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Denmark Superliga — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-dk-01", leagueId: "denmark-superliga", leagueName: "Superliga",
    homeTeam: { name: "FC Copenhagen", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.8 },
    awayTeam: { name: "FC Midtjylland", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.3 },
    datetime: today(3), venue: "Parken", status: "scheduled",
    odds: { home: 1.80, draw: 3.5, away: 4.5, over25: 1.75, under25: 2.05, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.49, drawProb: 0.26, awayWinProb: 0.25, avgGoals: 2.7, bttsProb: 0.55, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 16, homeWins: 7, draws: 4, awayWins: 5, avgGoals: 2.6 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 64, prob_max: 66, odd_minima: 1.52 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-dk-02", leagueId: "denmark-superliga", leagueName: "Superliga",
    homeTeam: { name: "Brondby IF", logo: "", form: ["D", "W", "L", "W", "D"], rating: 6.8 },
    awayTeam: { name: "Aarhus GF", logo: "", form: ["W", "D", "D", "L", "W"], rating: 6.5 },
    datetime: today(5), venue: "Brondby Stadion", status: "scheduled",
    odds: { home: 2.00, draw: 3.3, away: 3.8, over25: 1.82, under25: 1.98, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.44, drawProb: 0.28, awayWinProb: 0.28, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 12, homeWins: 5, draws: 3, awayWins: 4, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // France Ligue 2 — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-l2-01", leagueId: "france-ligue-2", leagueName: "Ligue 2",
    homeTeam: { name: "Lorient", logo: "", form: ["W", "D", "W", "W", "L"], rating: 6.8 },
    awayTeam: { name: "Caen", logo: "", form: ["D", "L", "W", "D", "D"], rating: 6.2 },
    datetime: today(4), venue: "Stade du Moustoir", status: "scheduled",
    odds: { home: 1.90, draw: 3.3, away: 4.2, over25: 1.92, under25: 1.88, bttsYes: 1.88, bttsNo: 1.92 },
    stats: { homeWinProb: 0.46, drawProb: 0.28, awayWinProb: 0.26, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.1 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-l2-02", leagueId: "france-ligue-2", leagueName: "Ligue 2",
    homeTeam: { name: "Bordeaux", logo: "", form: ["L", "D", "W", "L", "W"], rating: 6.0 },
    awayTeam: { name: "Metz", logo: "", form: ["W", "W", "D", "W", "D"], rating: 6.7 },
    datetime: today(7), venue: "Matmut Atlantique", status: "scheduled",
    odds: { home: 2.60, draw: 3.2, away: 2.8, over25: 1.88, under25: 1.92, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.34, drawProb: 0.29, awayWinProb: 0.37, avgGoals: 2.2, bttsProb: 0.47, over25Prob: 0.49, regime: "NORMAL" },
    h2h: { totalMatches: 8, homeWins: 3, draws: 2, awayWins: 3, avgGoals: 2.0 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 72, prob_max: 74, odd_minima: 1.35 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Germany 2. Bundesliga — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-2bl-01", leagueId: "germany-2-bundesliga", leagueName: "2. Bundesliga",
    homeTeam: { name: "Hamburger SV", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.2 },
    awayTeam: { name: "1. FC Koln", logo: "", form: ["W", "W", "D", "L", "W"], rating: 7.0 },
    datetime: today(3), venue: "Volksparkstadion", status: "scheduled",
    odds: { home: 2.10, draw: 3.3, away: 3.5, over25: 1.80, under25: 2.00, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.42, drawProb: 0.28, awayWinProb: 0.30, avgGoals: 2.6, bttsProb: 0.53, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 16, homeWins: 6, draws: 5, awayWins: 5, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-2bl-02", leagueId: "germany-2-bundesliga", leagueName: "2. Bundesliga",
    homeTeam: { name: "Hertha BSC", logo: "", form: ["D", "L", "W", "D", "W"], rating: 6.5 },
    awayTeam: { name: "FC Schalke 04", logo: "", form: ["L", "D", "W", "L", "D"], rating: 6.3 },
    datetime: today(6), venue: "Olympiastadion", status: "scheduled",
    odds: { home: 2.20, draw: 3.2, away: 3.3, over25: 1.85, under25: 1.95, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.40, drawProb: 0.29, awayWinProb: 0.31, avgGoals: 2.4, bttsProb: 0.50, over25Prob: 0.54, regime: "NORMAL" },
    h2h: { totalMatches: 14, homeWins: 5, draws: 4, awayWins: 5, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Italy Serie B — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-isb-01", leagueId: "italy-serie-b", leagueName: "Serie B",
    homeTeam: { name: "Sampdoria", logo: "", form: ["D", "W", "L", "W", "D"], rating: 6.6 },
    awayTeam: { name: "Palermo", logo: "", form: ["W", "D", "D", "L", "W"], rating: 6.5 },
    datetime: today(4), venue: "Stadio Luigi Ferraris", status: "scheduled",
    odds: { home: 2.15, draw: 3.2, away: 3.4, over25: 1.88, under25: 1.92, bttsYes: 1.82, bttsNo: 1.98 },
    stats: { homeWinProb: 0.41, drawProb: 0.29, awayWinProb: 0.30, avgGoals: 2.3, bttsProb: 0.49, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.1 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-isb-02", leagueId: "italy-serie-b", leagueName: "Serie B",
    homeTeam: { name: "Bari", logo: "", form: ["W", "L", "D", "W", "L"], rating: 6.3 },
    awayTeam: { name: "Cremonese", logo: "", form: ["D", "W", "W", "D", "L"], rating: 6.4 },
    datetime: today(7), venue: "Stadio San Nicola", status: "scheduled",
    odds: { home: 2.30, draw: 3.1, away: 3.2, over25: 1.90, under25: 1.90, bttsYes: 1.85, bttsNo: 1.95 },
    stats: { homeWinProb: 0.38, drawProb: 0.29, awayWinProb: 0.33, avgGoals: 2.2, bttsProb: 0.47, over25Prob: 0.50, regime: "NORMAL" },
    h2h: { totalMatches: 8, homeWins: 3, draws: 2, awayWins: 3, avgGoals: 2.0 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 72, prob_max: 74, odd_minima: 1.35 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Eredivisie (Netherlands) — 3 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ed-01", leagueId: "netherlands-eredivisie", leagueName: "Eredivisie",
    homeTeam: { name: "Ajax", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.8 },
    awayTeam: { name: "PSV", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.2 },
    datetime: today(3), venue: "Johan Cruyff Arena", status: "scheduled",
    odds: { home: 2.30, draw: 3.4, away: 3.0, over25: 1.55, under25: 2.40, bttsYes: 1.60, bttsNo: 2.30 },
    stats: { homeWinProb: 0.38, drawProb: 0.27, awayWinProb: 0.35, avgGoals: 3.2, bttsProb: 0.62, over25Prob: 0.72, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 30, homeWins: 12, draws: 7, awayWins: 11, avgGoals: 3.1 },
    predictions: [
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 },
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 70, prob_max: 72, odd_minima: 1.39 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ed-02", leagueId: "netherlands-eredivisie", leagueName: "Eredivisie",
    homeTeam: { name: "Feyenoord", logo: "", form: ["W", "D", "W", "W", "L"], rating: 7.6 },
    awayTeam: { name: "AZ Alkmaar", logo: "", form: ["W", "W", "D", "L", "W"], rating: 7.3 },
    datetime: today(5), venue: "De Kuip", status: "scheduled",
    odds: { home: 1.85, draw: 3.5, away: 4.2, over25: 1.65, under25: 2.20, bttsYes: 1.68, bttsNo: 2.12 },
    stats: { homeWinProb: 0.47, drawProb: 0.26, awayWinProb: 0.27, avgGoals: 2.9, bttsProb: 0.58, over25Prob: 0.65, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 18, homeWins: 8, draws: 4, awayWins: 6, avgGoals: 2.8 },
    predictions: [
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Liga NOS (Portugal) — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-pt-01", leagueId: "portugal-liga-nos", leagueName: "Liga NOS",
    homeTeam: { name: "FC Porto", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.0 },
    awayTeam: { name: "Benfica", logo: "", form: ["W", "D", "W", "W", "W"], rating: 8.2 },
    datetime: today(4), venue: "Estadio do Dragao", status: "scheduled",
    odds: { home: 2.20, draw: 3.3, away: 3.2, over25: 1.70, under25: 2.10, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.40, drawProb: 0.28, awayWinProb: 0.32, avgGoals: 2.8, bttsProb: 0.56, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 16, draws: 10, awayWins: 14, avgGoals: 2.6 },
    predictions: [{ mercado: "BTTS — SIM", status: "NEUTRO", prob_min: 54, prob_max: 56, odd_minima: 1.72 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-pt-02", leagueId: "portugal-liga-nos", leagueName: "Liga NOS",
    homeTeam: { name: "Sporting CP", logo: "", form: ["W", "W", "D", "W", "D"], rating: 7.8 },
    awayTeam: { name: "SC Braga", logo: "", form: ["D", "W", "L", "W", "W"], rating: 7.2 },
    datetime: today(7), venue: "Estadio Jose Alvalade", status: "scheduled",
    odds: { home: 1.75, draw: 3.5, away: 4.8, over25: 1.72, under25: 2.08, bttsYes: 1.70, bttsNo: 2.10 },
    stats: { homeWinProb: 0.50, drawProb: 0.26, awayWinProb: 0.24, avgGoals: 2.7, bttsProb: 0.55, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 8, draws: 5, awayWins: 5, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 64, prob_max: 66, odd_minima: 1.52 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Saudi Professional League — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-sa-pro-01", leagueId: "saudi-professional-league", leagueName: "Professional League",
    homeTeam: { name: "Al Hilal", logo: "", form: ["W", "W", "W", "W", "D"], rating: 8.5 },
    awayTeam: { name: "Al Nassr", logo: "", form: ["W", "D", "W", "W", "W"], rating: 8.2 },
    datetime: today(3), venue: "Kingdom Arena", status: "scheduled",
    odds: { home: 1.80, draw: 3.5, away: 4.5, over25: 1.65, under25: 2.20, bttsYes: 1.68, bttsNo: 2.12 },
    stats: { homeWinProb: 0.49, drawProb: 0.26, awayWinProb: 0.25, avgGoals: 2.9, bttsProb: 0.57, over25Prob: 0.64, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 20, homeWins: 9, draws: 5, awayWins: 6, avgGoals: 2.8 },
    predictions: [{ mercado: "Over 2.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-sa-pro-02", leagueId: "saudi-professional-league", leagueName: "Professional League",
    homeTeam: { name: "Al Ahli", logo: "", form: ["W", "D", "W", "L", "W"], rating: 7.5 },
    awayTeam: { name: "Al Ittihad", logo: "", form: ["D", "W", "W", "D", "W"], rating: 7.8 },
    datetime: today(6), venue: "King Abdullah Sports City", status: "scheduled",
    odds: { home: 2.40, draw: 3.3, away: 2.9, over25: 1.72, under25: 2.08, bttsYes: 1.70, bttsNo: 2.10 },
    stats: { homeWinProb: 0.36, drawProb: 0.28, awayWinProb: 0.36, avgGoals: 2.7, bttsProb: 0.56, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 15, homeWins: 6, draws: 4, awayWins: 5, avgGoals: 2.6 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 63, prob_max: 65, odd_minima: 1.54 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Scotland Premiership — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-sc-01", leagueId: "scotland-premiership", leagueName: "Premiership",
    homeTeam: { name: "Celtic", logo: "", form: ["W", "W", "W", "W", "W"], rating: 8.3 },
    awayTeam: { name: "Rangers", logo: "", form: ["W", "D", "W", "W", "D"], rating: 7.8 },
    datetime: today(3), venue: "Celtic Park", status: "scheduled",
    odds: { home: 1.70, draw: 3.6, away: 5.0, over25: 1.65, under25: 2.20, bttsYes: 1.68, bttsNo: 2.12 },
    stats: { homeWinProb: 0.52, drawProb: 0.25, awayWinProb: 0.23, avgGoals: 2.9, bttsProb: 0.57, over25Prob: 0.64, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 40, homeWins: 18, draws: 10, awayWins: 12, avgGoals: 2.7 },
    predictions: [{ mercado: "Over 2.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-sc-02", leagueId: "scotland-premiership", leagueName: "Premiership",
    homeTeam: { name: "Aberdeen", logo: "", form: ["D", "W", "L", "W", "D"], rating: 6.8 },
    awayTeam: { name: "Hearts", logo: "", form: ["W", "D", "D", "L", "W"], rating: 6.5 },
    datetime: today(6), venue: "Pittodrie", status: "scheduled",
    odds: { home: 2.00, draw: 3.3, away: 3.8, over25: 1.82, under25: 1.98, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.44, drawProb: 0.28, awayWinProb: 0.28, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 16, homeWins: 6, draws: 5, awayWins: 5, avgGoals: 2.4 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 66, prob_max: 68, odd_minima: 1.47 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Switzerland Super League — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-ch-sl-01", leagueId: "switzerland-super-league", leagueName: "Super League",
    homeTeam: { name: "Young Boys", logo: "", form: ["W", "W", "D", "W", "L"], rating: 7.5 },
    awayTeam: { name: "FC Basel", logo: "", form: ["D", "W", "W", "D", "W"], rating: 7.2 },
    datetime: today(4), venue: "Stade de Suisse", status: "scheduled",
    odds: { home: 2.00, draw: 3.3, away: 3.8, over25: 1.78, under25: 2.02, bttsYes: 1.75, bttsNo: 2.05 },
    stats: { homeWinProb: 0.44, drawProb: 0.28, awayWinProb: 0.28, avgGoals: 2.6, bttsProb: 0.54, over25Prob: 0.58, regime: "NORMAL" },
    h2h: { totalMatches: 18, homeWins: 8, draws: 4, awayWins: 6, avgGoals: 2.5 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 65, prob_max: 67, odd_minima: 1.49 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-ch-sl-02", leagueId: "switzerland-super-league", leagueName: "Super League",
    homeTeam: { name: "FC Zurich", logo: "", form: ["L", "D", "W", "W", "D"], rating: 6.8 },
    awayTeam: { name: "Servette", logo: "", form: ["W", "L", "D", "W", "L"], rating: 6.5 },
    datetime: today(7), venue: "Letzigrund", status: "scheduled",
    odds: { home: 2.10, draw: 3.2, away: 3.5, over25: 1.85, under25: 1.95, bttsYes: 1.80, bttsNo: 2.00 },
    stats: { homeWinProb: 0.42, drawProb: 0.29, awayWinProb: 0.29, avgGoals: 2.4, bttsProb: 0.50, over25Prob: 0.54, regime: "NORMAL" },
    h2h: { totalMatches: 10, homeWins: 4, draws: 3, awayWins: 3, avgGoals: 2.3 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },

  // ═══════════════════════════════════════════════
  // Turkey Super Lig — 2 matches
  // ═══════════════════════════════════════════════
  {
    id: "mock-tr-01", leagueId: "turkey-super-lig", leagueName: "Super Lig",
    homeTeam: { name: "Galatasaray", logo: "", form: ["W", "W", "W", "D", "W"], rating: 8.0 },
    awayTeam: { name: "Fenerbahce", logo: "", form: ["W", "W", "D", "W", "W"], rating: 7.8 },
    datetime: today(4), venue: "NEF Stadium", status: "scheduled",
    odds: { home: 1.85, draw: 3.4, away: 4.2, over25: 1.68, under25: 2.12, bttsYes: 1.65, bttsNo: 2.15 },
    stats: { homeWinProb: 0.47, drawProb: 0.27, awayWinProb: 0.26, avgGoals: 2.9, bttsProb: 0.60, over25Prob: 0.65, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 40, homeWins: 16, draws: 12, awayWins: 12, avgGoals: 2.8 },
    predictions: [
      { mercado: "BTTS — SIM", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
      { mercado: "Over 2.5 gols", status: "SAFE", prob_min: 68, prob_max: 70, odd_minima: 1.43 },
    ],
    source: "footystats", lastUpdated: new Date().toISOString(),
  },
  {
    id: "mock-tr-02", leagueId: "turkey-super-lig", leagueName: "Super Lig",
    homeTeam: { name: "Besiktas", logo: "", form: ["W", "D", "L", "W", "W"], rating: 7.4 },
    awayTeam: { name: "Trabzonspor", logo: "", form: ["D", "W", "W", "L", "D"], rating: 7.0 },
    datetime: today(7), venue: "Tupras Stadium", status: "scheduled",
    odds: { home: 1.90, draw: 3.4, away: 4.0, over25: 1.75, under25: 2.05, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.46, drawProb: 0.27, awayWinProb: 0.27, avgGoals: 2.7, bttsProb: 0.56, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 9, draws: 6, awayWins: 7, avgGoals: 2.6 },
    predictions: [{ mercado: "Under 3.5 gols", status: "SAFE", prob_min: 64, prob_max: 66, odd_minima: 1.52 }],
    source: "footystats", lastUpdated: new Date().toISOString(),
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
