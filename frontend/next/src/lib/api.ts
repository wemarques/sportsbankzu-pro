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

export async function getAiMatchAnalysis(matchId: string) {
  try {
    // Corrige para usar endpoints reais de AI se existirem, ou retorna mock por enquanto
    // O backend atual tem /ai/analyze-context mas espera home/away, não ID direto
    // Precisaremos adaptar ou criar um endpoint no backend para busca por ID
    // Por enquanto, vamos manter o mock/erro tratado
    return null; 
  } catch (error) {
    console.error('Erro na API getAiMatchAnalysis:', error);
    return null;
  }
}

// Funções legadas ou não utilizadas removidas para clareza, ou mantidas como stub
export async function getRaces(season?: string) { return {}; }
export async function getResults(raceId?: string) { return {}; }
