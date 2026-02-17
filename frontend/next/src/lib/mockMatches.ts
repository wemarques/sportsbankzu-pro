/**
 * Mock matches fallback — garante que o dashboard nunca fique vazio.
 * Usado quando PY_BACKEND_URL nao responde E o proxy /api/matches tambem falha.
 *
 * Campos usam snake_case (home_team, away_team) porque normalizeMatch()
 * checa item.home_team primeiro.
 */

function today(hoursOffset: number): string {
  const d = new Date();
  d.setHours(d.getHours() + hoursOffset, 0, 0, 0);
  return d.toISOString();
}

const MOCK_DATA = [
  // Premier League
  {
    id: "mock-pl-1",
    leagueId: "premier-league",
    leagueName: "Premier League",
    home_team: "Arsenal",
    away_team: "Chelsea",
    datetime: today(2),
    stadium: "Emirates Stadium",
    status: "scheduled" as const,
    odds: { home: 1.85, draw: 3.6, away: 4.2, over25: 1.72, under25: 2.1, bttsYes: 1.75, bttsNo: 2.0 },
    stats: { homeWinProb: 0.48, drawProb: 0.26, awayWinProb: 0.26, avgGoals: 2.8, bttsProb: 0.55, over25Prob: 0.62, regime: "NORMAL" },
    h2h: { totalMatches: 30, homeWins: 14, draws: 8, awayWins: 8, avgGoals: 2.6 },
  },
  {
    id: "mock-pl-2",
    leagueId: "premier-league",
    leagueName: "Premier League",
    home_team: "Liverpool",
    away_team: "Manchester City",
    datetime: today(4),
    stadium: "Anfield",
    status: "scheduled" as const,
    odds: { home: 2.25, draw: 3.3, away: 3.1, over25: 1.65, under25: 2.2, bttsYes: 1.68, bttsNo: 2.15 },
    stats: { homeWinProb: 0.40, drawProb: 0.28, awayWinProb: 0.32, avgGoals: 3.1, bttsProb: 0.60, over25Prob: 0.68, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 28, homeWins: 10, draws: 6, awayWins: 12, avgGoals: 2.9 },
  },
  // La Liga
  {
    id: "mock-ll-1",
    leagueId: "la-liga",
    leagueName: "La Liga",
    home_team: "Real Madrid",
    away_team: "Barcelona",
    datetime: today(3),
    stadium: "Santiago Bernabeu",
    status: "scheduled" as const,
    odds: { home: 2.1, draw: 3.4, away: 3.3, over25: 1.75, under25: 2.05, bttsYes: 1.72, bttsNo: 2.08 },
    stats: { homeWinProb: 0.42, drawProb: 0.27, awayWinProb: 0.31, avgGoals: 2.9, bttsProb: 0.57, over25Prob: 0.64, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 50, homeWins: 20, draws: 12, awayWins: 18, avgGoals: 3.0 },
  },
  {
    id: "mock-ll-2",
    leagueId: "la-liga",
    leagueName: "La Liga",
    home_team: "Atletico Madrid",
    away_team: "Sevilla",
    datetime: today(5),
    stadium: "Wanda Metropolitano",
    status: "scheduled" as const,
    odds: { home: 1.7, draw: 3.5, away: 5.0, over25: 1.9, under25: 1.85, bttsYes: 1.95, bttsNo: 1.82 },
    stats: { homeWinProb: 0.52, drawProb: 0.26, awayWinProb: 0.22, avgGoals: 2.3, bttsProb: 0.48, over25Prob: 0.52, regime: "NORMAL" },
    h2h: { totalMatches: 24, homeWins: 12, draws: 7, awayWins: 5, avgGoals: 2.2 },
  },
  // Serie A
  {
    id: "mock-sa-1",
    leagueId: "serie-a",
    leagueName: "Serie A",
    home_team: "AC Milan",
    away_team: "Inter Milan",
    datetime: today(1),
    stadium: "San Siro",
    status: "scheduled" as const,
    odds: { home: 2.6, draw: 3.2, away: 2.7, over25: 1.8, under25: 2.0, bttsYes: 1.78, bttsNo: 2.02 },
    stats: { homeWinProb: 0.35, drawProb: 0.30, awayWinProb: 0.35, avgGoals: 2.7, bttsProb: 0.54, over25Prob: 0.60, regime: "NORMAL" },
    h2h: { totalMatches: 40, homeWins: 15, draws: 12, awayWins: 13, avgGoals: 2.5 },
  },
  // Bundesliga
  {
    id: "mock-bl-1",
    leagueId: "bundesliga",
    leagueName: "Bundesliga",
    home_team: "Bayern Munich",
    away_team: "Borussia Dortmund",
    datetime: today(6),
    stadium: "Allianz Arena",
    status: "scheduled" as const,
    odds: { home: 1.55, draw: 4.2, away: 5.5, over25: 1.45, under25: 2.6, bttsYes: 1.6, bttsNo: 2.3 },
    stats: { homeWinProb: 0.58, drawProb: 0.22, awayWinProb: 0.20, avgGoals: 3.4, bttsProb: 0.62, over25Prob: 0.75, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 35, homeWins: 18, draws: 8, awayWins: 9, avgGoals: 3.2 },
  },
  // Ligue 1
  {
    id: "mock-l1-1",
    leagueId: "ligue-1",
    leagueName: "Ligue 1",
    home_team: "PSG",
    away_team: "Marseille",
    datetime: today(7),
    stadium: "Parc des Princes",
    status: "scheduled" as const,
    odds: { home: 1.4, draw: 4.8, away: 7.0, over25: 1.5, under25: 2.5, bttsYes: 1.7, bttsNo: 2.1 },
    stats: { homeWinProb: 0.65, drawProb: 0.20, awayWinProb: 0.15, avgGoals: 3.2, bttsProb: 0.55, over25Prob: 0.72, regime: "HIPER-OFENSIVA" },
    h2h: { totalMatches: 32, homeWins: 20, draws: 6, awayWins: 6, avgGoals: 2.8 },
  },
  // Brasileirao
  {
    id: "mock-br-1",
    leagueId: "brasileirao-serie-a",
    leagueName: "Brasileirao Serie A",
    home_team: "Flamengo",
    away_team: "Palmeiras",
    datetime: today(8),
    stadium: "Maracana",
    status: "scheduled" as const,
    odds: { home: 2.3, draw: 3.1, away: 3.2, over25: 1.85, under25: 1.95, bttsYes: 1.8, bttsNo: 2.0 },
    stats: { homeWinProb: 0.39, drawProb: 0.29, awayWinProb: 0.32, avgGoals: 2.5, bttsProb: 0.52, over25Prob: 0.56, regime: "NORMAL" },
    h2h: { totalMatches: 22, homeWins: 9, draws: 7, awayWins: 6, avgGoals: 2.3 },
  },
];

export function getMockMatches(leaguesParam: string) {
  const ids = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);
  if (ids.length === 0) return MOCK_DATA;
  return MOCK_DATA.filter((m) => ids.includes(m.leagueId));
}
