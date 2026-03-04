import { NextRequest } from "next/server";
import { AVAILABLE_LEAGUES } from "@/lib/leagues";
import { generateMockMatches } from "@/lib/mockMatches";

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

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const leagueIds: string[] = Array.isArray(body?.leagueIds) ? body.leagueIds : [];
  const validIds = new Set(AVAILABLE_LEAGUES.map((l) => l.id));
  const ids = leagueIds.filter((id) => validIds.has(id));
  if (ids.length === 0) {
    return new Response(JSON.stringify({ matches: [] }), { status: 200 });
  }

  const results: any[] = [];

  for (const id of ids) {
    const league = AVAILABLE_LEAGUES.find((l) => l.id === id)!;
    const sources = [
      { base: "https://footystats.org", path: league.apiEndpoints.footystats },
    ];
    const fetched: any[] = [];
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
            score: m.score && typeof m.score.home === "number" && typeof m.score.away === "number"
              ? m.score
              : m.score && (m.score.home != null || m.score.away != null)
                ? { home: Number(m.score.home) || 0, away: Number(m.score.away) || 0, halftime: m.score.halftime }
                : undefined,
          });
        }
      }
    }
    if (fetched.length === 0) {
      // Use shared mock data from mockMatches.ts instead of inline stub
      results.push(...generateMockMatches([id]));
    } else {
      results.push(...fetched);
    }
  }

  return new Response(JSON.stringify({ matches: results }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
