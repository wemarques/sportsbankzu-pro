import { NextRequest, NextResponse } from "next/server";
import { fetchBackend, getBackendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET(req: NextRequest) {
  const backendBase = getBackendUrl();

  if (!backendBase) {
    console.warn("[live-scores] PY_BACKEND_URL not configured — returning empty");
    return NextResponse.json({ matches: [], nextUpdate: 60 });
  }

  // 1. Try the dedicated /live-scores endpoint first
  const result = await fetchBackend("/live-scores", { timeoutMs: 20_000 });

  if (result.ok) {
    const data = result.data as { matches?: unknown[]; nextUpdate?: number };
    const matches = data.matches ?? [];
    if (matches.length > 0) {
      console.log(`[live-scores] OK — ${matches.length} matches (${result.durationMs}ms)`);
      return NextResponse.json({ matches, nextUpdate: data.nextUpdate ?? 60 });
    }
  }

  // 2. Fallback: /live-scores returned empty (FootyStats todays-matches
  //    often returns [] for certain leagues).  Re-fetch via /fixtures for
  //    leagues the caller says have live matches, extracting only live/
  //    finished records as an overlay.
  const leagues = req.nextUrl.searchParams.get("leagues") ?? "";
  if (leagues) {
    try {
      const qs = new URLSearchParams({ leagues, date: "today" });
      const fbResult = await fetchBackend(`/fixtures?${qs}`, { timeoutMs: 20_000 });
      if (fbResult.ok) {
        const fbData = fbResult.data as { matches?: Array<Record<string, unknown>> };
        const fbMatches = (fbData.matches ?? [])
          .filter((m) => m.status === "live" || m.status === "finished")
          .map((m) => ({
            id: m.footystatsId ?? m.id,
            homeTeam: typeof m.homeTeam === "string" ? m.homeTeam : (m.homeTeam as Record<string, unknown>)?.name ?? "",
            awayTeam: typeof m.awayTeam === "string" ? m.awayTeam : (m.awayTeam as Record<string, unknown>)?.name ?? "",
            status: m.status,
            score: m.score,
            period: m.period,
            minute: m.minute,
            ...(m.currentCorners != null ? { currentCorners: m.currentCorners } : {}),
            ...(m.currentCards != null ? { currentCards: m.currentCards } : {}),
          }));
        if (fbMatches.length > 0) {
          console.log(`[live-scores] Fallback via /fixtures — ${fbMatches.length} live/finished matches (${fbResult.durationMs}ms)`);
          return NextResponse.json({ matches: fbMatches, nextUpdate: 60 });
        }
      }
    } catch {
      // Fallback failed — return empty
    }
  }

  if (!result.ok) {
    console.error(`[live-scores] ${result.error?.kind}: ${result.error?.message}`);
  }
  return NextResponse.json({ matches: [], nextUpdate: 60 });
}
