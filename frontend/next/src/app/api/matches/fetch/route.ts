import { NextRequest } from "next/server";

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
      const qs = new URLSearchParams({ leagues: leagueIds.join(","), date });
      const res = await fetch(`${backend.replace(/\\/$/, "")}/fixtures?${qs.toString()}`, { cache: "no-store" });
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    } else {
      const origin = `${url.protocol}//${url.host}`;
      const res = await fetch(`${origin}/api/matches`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leagueIds, date }),
        cache: "no-store",
      });
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
  } catch {
    return new Response(JSON.stringify({ matches: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
}
