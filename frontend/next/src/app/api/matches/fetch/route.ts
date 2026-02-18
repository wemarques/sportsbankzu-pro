import { NextRequest } from "next/server";
import { generateMockMatches } from "@/lib/mockMatches";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const leaguesParam = url.searchParams.get("leagues") || "";
  const date = url.searchParams.get("date") || "today";
  const leagueIds = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);

  if (leagueIds.length === 0) {
    return new Response(JSON.stringify({ matches: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }

  try {
    const backend = process.env.PY_BACKEND_URL;
    if (backend) {
      // Proxy to Python backend
      const qs = new URLSearchParams({ leagues: leagueIds.join(","), date });
      const base = backend.endsWith("/") ? backend.slice(0, -1) : backend;
      const res = await fetch(`${base}/fixtures?${qs.toString()}`, { cache: "no-store" });
      const data = await res.json();
      // If backend returned matches, use them; otherwise fall through to mock
      if (data.matches && data.matches.length > 0) {
        return new Response(JSON.stringify(data), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
    }

    // No PY_BACKEND_URL or backend returned empty — try POST /api/matches
    const origin = `${url.protocol}//${url.host}`;
    const res = await fetch(`${origin}/api/matches`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ leagueIds, date }),
      cache: "no-store",
    });
    const data = await res.json();
    if (data.matches && data.matches.length > 0) {
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
  } catch {
    // Fall through to mock fallback below
  }

  // Final fallback: use shared mock data directly
  const mockData = generateMockMatches(leagueIds);
  return new Response(JSON.stringify({ matches: mockData }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
