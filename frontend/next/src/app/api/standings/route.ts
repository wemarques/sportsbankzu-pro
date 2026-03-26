import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const league = url.searchParams.get("league") || "";

  if (!league) {
    return Response.json({ standings: [], error: "Parâmetro 'league' é obrigatório" });
  }

  const qs = new URLSearchParams({ league });

  // Primary: API-Football via /live/standings (reliable, has all leagues)
  const result = await fetchBackend(`/live/standings?${qs.toString()}`, {
    timeoutMs: 10_000,
  });

  if (result.ok) {
    const data = result.data as Record<string, unknown>;
    const raw = (data.standings ?? []) as Record<string, unknown>[];
    // Normalize field names to match MatchDetailCard expectations
    const standings = raw.map((t: Record<string, unknown>) => ({
      ...t,
      position: t.rank ?? t.position,
      name: t.teamName ?? t.name ?? t.cleanName ?? "",
    }));
    return Response.json({ standings, leagueId: league });
  }

  // Fallback: FootyStats via /standings
  const fallback = await fetchBackend(`/standings?${qs.toString()}`, {
    timeoutMs: 10_000,
  });

  if (fallback.ok) {
    return Response.json(fallback.data);
  }

  console.error(`[standings/route] Error fetching standings: ${result.error?.message}`);
  return Response.json(
    { standings: [], error: result.error?.message ?? "Erro ao buscar classificação" },
    { status: 502 },
  );
}
