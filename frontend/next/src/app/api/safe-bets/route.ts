import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

/**
 * POST /api/safe-bets
 *
 * Proxies safe bet evaluation requests to the FastAPI backend.
 * Accepts an array of match inputs and returns SafeBetsResponse.
 */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body || !Array.isArray(body)) {
    return NextResponse.json(
      { success: false, error: "Request body must be a JSON array of match inputs" },
      { status: 400 },
    );
  }

  const result = await fetchBackend("/safe-bets/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 30_000,
  });

  if (!result.ok) {
    return NextResponse.json(
      {
        success: false,
        error: result.error?.message ?? "Backend unavailable",
        kind: result.error?.kind,
      },
      { status: 502 },
    );
  }

  return NextResponse.json(result.data);
}

/**
 * GET /api/safe-bets?type=league-dna&league_id=...
 * GET /api/safe-bets?type=leagues
 *
 * Proxies league DNA and league list requests to the FastAPI backend.
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const type = searchParams.get("type") ?? "leagues";

  let path: string;
  if (type === "league-dna") {
    const leagueId = searchParams.get("league_id");
    path = leagueId
      ? `/safe-bets/league-dna?league_id=${encodeURIComponent(leagueId)}`
      : "/safe-bets/league-dna";
  } else {
    path = "/safe-bets/leagues";
  }

  const result = await fetchBackend(path, { timeoutMs: 15_000 });

  if (!result.ok) {
    return NextResponse.json(
      {
        success: false,
        error: result.error?.message ?? "Backend unavailable",
        kind: result.error?.kind,
      },
      { status: 502 },
    );
  }

  return NextResponse.json(result.data);
}
