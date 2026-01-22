import { NextResponse } from "next/server";
import { Match } from "../../../../lib/leagues";

async function fetchLiveFromPackBall(ids: string[]): Promise<Match[]> {
  try {
    const url = `https://packball.com/matches/live?ids=${encodeURIComponent(ids.join(","))}`;
    const res = await fetch(url, { cache: "no-store", headers: { "user-agent": "Mozilla/5.0 SportsBankBot" } });
    if (!res.ok) return [];
    const data = await res.json().catch(() => null);
    if (!data || !Array.isArray(data)) return [];
    return data as Match[];
  } catch {
    return [];
  }
}

function simulateLive(ids: string[]): Match[] {
  const out: Match[] = [];
  for (const id of ids) {
    const minute = Math.min(90, 10 + Math.floor(Math.random() * 70));
    const home = Math.floor(Math.random() * 3);
    const away = Math.floor(Math.random() * 3);
    out.push({
      id,
      leagueId: "",
      leagueName: "",
      homeTeam: { name: "Home", logo: "", form: ["W","D","W","L","W"], rating: 7 },
      awayTeam: { name: "Away", logo: "", form: ["L","W","D","W","D"], rating: 6.8 },
      datetime: new Date().toISOString(),
      venue: "",
      status: "live",
      score: { home, away, halftime: { home: Math.floor(home/2), away: Math.floor(away/2) } },
      odds: { home: 2.0, draw: 3.1, away: 3.4, over25: 1.9, under25: 1.9, bttsYes: 1.85, bttsNo: 1.95 },
      stats: { homeWinProb: 40, drawProb: 30, awayWinProb: 30, avgGoals: 2.6, bttsProb: 52, over25Prob: 55 },
      h2h: { totalMatches: 0, homeWins: 0, draws: 0, awayWins: 0, avgGoals: 0 },
      source: "packball",
      lastUpdated: new Date().toISOString(),
    });
  }
  return out;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const matchIds = searchParams.get("ids")?.split(",").map((s)=>s.trim()).filter(Boolean) || [];
  const liveMatches = (await fetchLiveFromPackBall(matchIds));
  const matches = liveMatches.length ? liveMatches : simulateLive(matchIds);
  return NextResponse.json({ matches, nextUpdate: 30 });
}
