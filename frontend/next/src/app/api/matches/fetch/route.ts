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
      const res = await fetch(`${base}/fixtures?${qs.toString()}`, { cache: "no-store" });
      const data = await res.json();
      if (data.matches && data.matches.length > 0) {
        return new Response(JSON.stringify(data), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
    }
  } catch {
    // Python backend unavailable — fall through to mock
  }

  // 2. No backend or backend returned empty — use mock data directly
  //    (Previously this tried a self-referencing POST to /api/matches which
  //     caused stale data issues on Vercel serverless.)
  const mockData = generateMockMatches(leagueIds);
  console.log("[fetch/route] V2.3 | Using generateMockMatches | count:", mockData.length, "| first id:", mockData[0]?.id);
  return new Response(JSON.stringify({ matches: mockData, _version: "V2.3", _source: "generateMockMatches" }), {
    status: 200,
    headers: { "content-type": "application/json", "x-data-version": "V2.3" },
  });
}
