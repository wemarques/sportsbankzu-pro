/**
 * API client — todas as chamadas passam pelas rotas proxy do Next.js (/api/*)
 * para usar PY_BACKEND_URL (server-side) e evitar CORS.
 */

export async function getMatchesByLeague(leagues: string, date?: string) {
  try {
    const params = new URLSearchParams({ leagues });
    if (date) params.append("date", date);
    const res = await fetch(`/api/matches/fetch?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.matches && data.matches.length > 0) return data;
    // Server proxy retornou vazio — fallback client-side
    const { getMockMatches } = await import("./mockMatches");
    return { matches: getMockMatches(leagues) };
  } catch (error) {
    console.error("Erro na API getMatchesByLeague:", error);
    const { getMockMatches } = await import("./mockMatches");
    return { matches: getMockMatches(leagues) };
  }
}

export async function getAiMatchAnalysis(matchId: string, homeTeam?: string, awayTeam?: string) {
  try {
    const params = new URLSearchParams();
    if (homeTeam) params.set("home_team", homeTeam);
    if (awayTeam) params.set("away_team", awayTeam);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/ai/match/${encodeURIComponent(matchId)}/analysis${qs}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.summary && data.confidence === 0) return null;
    return data;
  } catch {
    return null;
  }
}
