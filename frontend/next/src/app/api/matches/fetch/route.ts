import { NextRequest } from "next/server";
import { generateMockMatches } from "@/lib/mockMatches";
import { fetchBackend, getBackendUrl, maskUrl } from "@/lib/backend";

/** Allow up to 25 s on Vercel Pro (our fetch timeout is 20 s). */
export const maxDuration = 25;

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const leaguesParam = url.searchParams.get("leagues") || "";
  const leagueIds = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);
  const debug = url.searchParams.get("debug") === "true";

  if (leagueIds.length === 0) {
    return Response.json({ matches: [] });
  }

  // 1. Try Python backend if configured
  const backendBase = getBackendUrl();

  if (backendBase) {
    const date = url.searchParams.get("date") || "today";
    const qs = new URLSearchParams({ leagues: leagueIds.join(","), date });
    const result = await fetchBackend(`/fixtures?${qs.toString()}`, {
      timeoutMs: 20_000,
    });

    if (result.ok) {
      const matches = (result.data as Record<string, unknown>)?.matches;
      if (Array.isArray(matches) && matches.length > 0) {
        console.log(
          `[fetch/route] Backend OK | ${matches.length} matches | ${result.durationMs}ms`,
        );
        return Response.json({
          ...(result.data as object),
          _dataSource: "backend",
          _latencyMs: result.durationMs,
        });
      }
      console.log(
        `[fetch/route] Backend returned 0 matches — falling back to mock | ${result.durationMs}ms`,
      );
    }

    if (result.error) {
      console.error(
        `[fetch/route] ${result.error.kind} | ${result.error.message} | url: ${result.error.url} | ${result.error.durationMs}ms`,
      );
    }

    // In debug mode, return the error instead of falling back to mock
    if (debug) {
      return Response.json(
        {
          _dataSource: "error",
          _debug: {
            error: result.error ?? { kind: "EMPTY_RESPONSE", message: "Backend returned 0 matches" },
            backendConfigured: true,
            backendUrl: maskUrl(backendBase),
            durationMs: result.durationMs,
          },
          matches: [],
        },
        { status: 502 },
      );
    }
  } else {
    console.warn("[fetch/route] PY_BACKEND_URL not configured — using mock data");

    if (debug) {
      return Response.json(
        {
          _dataSource: "error",
          _debug: {
            error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL is not set" },
            backendConfigured: false,
          },
          matches: [],
        },
        { status: 503 },
      );
    }
  }

  // 2. Fallback to mock data
  const mockData = generateMockMatches(leagueIds);
  console.log(`[fetch/route] Using mock fallback | ${mockData.length} matches`);
  return Response.json({ matches: mockData, _dataSource: "mock-fallback" });
}
