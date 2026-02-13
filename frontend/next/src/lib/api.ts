export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "https://4eksz2n7h5.execute-api.us-east-1.amazonaws.com";

async function get(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { ...init, cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getMatchesByLeague(league: string, date?: string) {
  try {
    // Corrige para usar o endpoint /fixtures do backend FastAPI e não /api/matches
    const params = new URLSearchParams({ leagues: league });
    if (date) params.append('date', date);
    // IMPORTANTE: Backend espera 'leagues' (plural) como query param e rota é /fixtures
    const res = await fetch(`${API_BASE}/fixtures?${params.toString()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Erro ao buscar jogos');
    return await res.json();
  } catch (error) {
    console.error('Erro na API getMatchesByLeague:', error);
    return { matches: [] } as any;
  }
}

export type MatchForAnalysis = {
  homeTeam: { name: string; form?: string[] };
  awayTeam: { name: string; form?: string[] };
  leagueName: string;
  stats?: Record<string, unknown>;
  odds?: Record<string, number>;
  h2h?: Record<string, unknown>;
};

export async function getAiMatchAnalysis(match: MatchForAnalysis | null): Promise<{
  summary: string;
  key_points: string[];
  recommendation: string;
  confidence: number;
  last_updated: string;
} | null> {
  if (!match) return null;
  try {
    const body = {
      home_team: match.homeTeam?.name ?? "",
      away_team: match.awayTeam?.name ?? "",
      league: match.leagueName ?? "",
      stats: {
        lambdaHome: match.stats?.lambdaHome ?? match.stats?.lambda_home,
        lambdaAway: match.stats?.lambdaAway ?? match.stats?.lambda_away,
        homeWinProb: match.stats?.homeWinProb ?? match.stats?.prob_home,
        drawProb: match.stats?.drawProb ?? match.stats?.prob_draw,
        awayWinProb: match.stats?.awayWinProb ?? match.stats?.prob_away,
        over25Prob: match.stats?.over25Prob ?? match.stats?.prob_over_25,
        bttsProb: match.stats?.bttsProb ?? match.stats?.prob_btts,
        ...match.stats,
      },
      odds: {
        home: match.odds?.home,
        draw: match.odds?.draw,
        away: match.odds?.away,
        over25: match.odds?.over25,
        bttsYes: match.odds?.bttsYes,
        ...match.odds,
      },
      context: match.h2h
        ? {
            home_form: match.homeTeam?.form?.join("-") ?? "N/A",
            away_form: match.awayTeam?.form?.join("-") ?? "N/A",
            h2h: `${match.h2h?.homeWins ?? 0}V ${match.h2h?.draws ?? 0}E ${match.h2h?.awayWins ?? 0}D`,
          }
        : undefined,
    };
    const res = await fetch(`${API_BASE}/ai/match-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status !== "success") return null;
    return {
      summary: data.summary ?? "",
      key_points: data.key_points ?? [],
      recommendation: data.recommendation ?? "",
      confidence: data.confidence ?? 0,
      last_updated: data.last_updated ?? new Date().toLocaleString("pt-BR"),
    };
  } catch (error) {
    console.error("Erro na API getAiMatchAnalysis:", error);
    return null;
  }
}

// Funções legadas ou não utilizadas removidas para clareza, ou mantidas como stub
export async function getRaces(season?: string) { return {}; }
export async function getResults(raceId?: string) { return {}; }
