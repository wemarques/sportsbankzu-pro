export const API_BASE = 'http://127.0.0.1:8001';

async function get(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { ...init, cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getRaces(season?: string) { return get(`/races${season ? `?season=${season}` : ''}`); }
export async function getResults(raceId?: string) { return get(`/results${raceId ? `?raceId=${raceId}` : ''}`); }
export async function getDrivers() { return get(`/drivers`); }
export async function getTeams() { return get(`/teams`); }
export async function getStandings(season?: string) { return get(`/standings${season ? `?season=${season}` : ''}`); }
export async function getLapTimes(raceId: string) { return get(`/laps?raceId=${raceId}`); }
export async function getPitStops(raceId: string) { return get(`/pits?raceId=${raceId}`); }
export async function getDRSZones(raceId: string) { return get(`/drs?raceId=${raceId}`); }
export async function getMarketPrices(season?: string) { return get(`/market/prices${season ? `?season=${season}` : ''}`); }
export async function getPerformanceStats(driverId: string) { return get(`/performance?driverId=${driverId}`); }
export async function getTrendData(metric: string) { return get(`/trends?metric=${metric}`); }
export async function getGridPositions(raceId: string) { return get(`/grid?raceId=${raceId}`); }
export async function getSystemStatus() { return get(`/api/status`); }
export async function refreshSource(source: string) { return get(`/api/refresh?source=${encodeURIComponent(source)}`); }
export async function getMatchesByLeague(league: string, date?: string) {
  try {
    const params = new URLSearchParams({ league });
    if (date) params.append('date', date);
    const res = await fetch(`${API_BASE}/api/matches?${params.toString()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Erro ao buscar jogos');
    return await res.json();
  } catch (error) {
    console.error('Erro na API getMatchesByLeague:', error);
    return { matches: [] } as any;
  }
}

export async function getValueBetsByLeague(league: string) {
  try {
    const res = await fetch(`${API_BASE}/api/value-bets?league=${encodeURIComponent(league)}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Erro ao buscar value bets');
    return await res.json();
  } catch (error) {
    console.error('Erro na API getValueBetsByLeague:', error);
    return { value_bets: [] } as any;
  }
}
