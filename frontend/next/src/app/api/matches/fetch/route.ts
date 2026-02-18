import { NextRequest } from "next/server";
import { generateMockMatches } from "@/lib/mockMatches";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const leaguesParam = url.searchParams.get("leagues") || "";
  const leagueIds = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);

  if (leagueIds.length === 0) {
    return new Response(JSON.stringify({ matches: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }

  // 1. Try Python backend if configured
  try {
    const backend = process.env.PY_BACKEND_URL;
    if (backend) {
      const date = url.searchParams.get("date") || "today";
      const qs = new URLSearchParams({ leagues: leagueIds.join(","), date });
      const base = backend.endsWith("/") ? backend.slice(0, -1) : backend;

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15_000);

      const res = await fetch(`${base}/fixtures?${qs.toString()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      clearTimeout(timeout);

      const data = await res.json();
      if (data.matches && data.matches.length > 0) {
        console.log(
          `[fetch/route] Backend OK | ${data.matches.length} matches | source: ${data.matches[0]?.source ?? "unknown"}`
        );
        return new Response(
          JSON.stringify({ ...data, _dataSource: "backend" }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      }
      console.log("[fetch/route] Backend returned 0 matches — falling back to mock");
    }
  } catch (err) {
    console.error("[fetch/route] Backend error:", err instanceof Error ? err.message : err);
  }

  // 2. No backend or backend returned empty — use mock data directly
  const mockData = generateMockMatches(leagueIds);
  console.log(`[fetch/route] Using mock fallback | ${mockData.length} matches`);
  return new Response(
    JSON.stringify({ matches: mockData, _dataSource: "mock-fallback" }),
    { status: 200, headers: { "content-type": "application/json" } }
  );
}
