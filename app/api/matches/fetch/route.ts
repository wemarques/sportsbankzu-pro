import { NextResponse } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  "https://4eksz2n7h5.execute-api.us-east-1.amazonaws.com";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const leagues = searchParams.get("leagues") ?? "";
  const date = searchParams.get("date") ?? new Date().toISOString().split("T")[0];

  try {
    const params = new URLSearchParams({ leagues, date });
    const res = await fetch(`${API_BASE}/fixtures?${params.toString()}`, {
      cache: "no-store",
    });

    if (!res.ok) {
      return NextResponse.json(
        { matches: [], error: `Backend returned ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching matches from backend:", error);
    return NextResponse.json({ matches: [], error: "Failed to fetch matches" }, { status: 500 });
  }
}
