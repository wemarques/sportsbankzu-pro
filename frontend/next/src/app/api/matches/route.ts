import { NextRequest } from "next/server";
import { AVAILABLE_LEAGUES } from "@/lib/leagues";

type Match = {
  id: string;
  leagueId: string;
  homeTeam: string;
  awayTeam: string;
  datetime: string;
  stadium?: string;
  status: "scheduled" | "live" | "finished";
  odds?: { home?: number; draw?: number; away?: number };
  stats?: { possession?: string; shots?: string; passes?: string };
  ratings?: { home?: number; away?: number };
  score?: { home: number; away: number };
};

const ua =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36";

async function safeJson(url: string) {
  try {
    const r = await fetch(url, { headers: { "user-agent": ua } });
    if (!r.ok) return null;
    const ct = r.headers.get("content-type") || "";
    if (!ct.includes("application/json")) return null;
    return await r.json();
  } catch {
    return null;
  }
}

function mockMatches(leagueIds: string[]): Match[] {
  const now = new Date();
  const date = now.toISOString();
  const base: Match[] = [
    {
      id: "m1",
      leagueId: leagueIds[0] ?? "premier-league",
      homeTeam: "Team A",
      awayTeam: "Team B",
      datetime: date,
      stadium: "Stadium Alpha",
      status: "scheduled",
      odds: { home: 1.9, draw: 3.4, away: 2.2 },
      stats: { possession: "52%-48%", shots: "12-9", passes: "410-380" },
      ratings: { home: 6.7, away: 6.5 },
      score: { home: 0, away: 0 },
    },
    {
      id: "m2",
      leagueId: leagueIds[1] ?? "la-liga",
      homeTeam: "Team C",
      awayTeam: "Team D",
      datetime: date,
      stadium: "Stadium Beta",
      status: "live",
      odds: { home: 2.1, draw: 3.1, away: 2.8 },
      stats: { possession: "48%-52%", shots: "7-10", passes: "360-420" },
      ratings: { home: 6.4, away: 6.8 },
      score: { home: 1, away: 2 },
    },
  ];
  return base;
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const leagueIds: string[] = Array.isArray(body?.leagueIds) ? body.leagueIds : [];
  const validIds = new Set(AVAILABLE_LEAGUES.map((l) => l.id));
  const ids = leagueIds.filter((id) => validIds.has(id));
  if (ids.length === 0) {
    return new Response(JSON.stringify({ matches: [] }), { status: 200 });
  }

  const results: Match[] = [];

  for (const id of ids) {
    const league = AVAILABLE_LEAGUES.find((l) => l.id === id)!;
    const sources = [
      { base: "https://www.whoscored.com", path: league.apiEndpoints.whoscored },
      { base: "https://footystats.org", path: league.apiEndpoints.footystats },
      { base: "https://packball.com", path: league.apiEndpoints.packball },
    ];
    const fetched: Match[] = [];
    for (const s of sources) {
      const url = `${s.base}${s.path}`;
      const data = await safeJson(url);
      if (data && Array.isArray(data?.matches)) {
        for (const m of data.matches) {
          fetched.push({
            id: String(m.id ?? `${id}-${Math.random()}`),
            leagueId: id,
            homeTeam: String(m.homeTeam ?? m.home ?? "Home"),
            awayTeam: String(m.awayTeam ?? m.away ?? "Away"),
            datetime: String(m.datetime ?? m.date ?? new Date().toISOString()),
            stadium: m.stadium ?? undefined,
            status: (m.status as any) ?? "scheduled",
            odds: m.odds ?? undefined,
            stats: m.stats ?? undefined,
            ratings: m.ratings ?? undefined,
            score: m.score ?? undefined,
          });
        }
      }
    }
    if (fetched.length === 0) {
      results.push(...mockMatches([id]));
    } else {
      results.push(...fetched);
    }
  }

  return new Response(JSON.stringify({ matches: results }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

