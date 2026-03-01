import { NextResponse } from "next/server";
import { fetchBackend, getBackendUrl } from "@/lib/backend";

export const maxDuration = 15;

export async function GET() {
  const backendBase = getBackendUrl();

  if (!backendBase) {
    return NextResponse.json({ matches: [], nextUpdate: 60 });
  }

  const result = await fetchBackend("/live-scores", { timeoutMs: 10_000 });

  if (result.ok) {
    const data = result.data as { matches?: unknown[]; nextUpdate?: number };
    return NextResponse.json({
      matches: data.matches ?? [],
      nextUpdate: data.nextUpdate ?? 60,
    });
  }

  console.error(`[live-scores] ${result.error?.kind}: ${result.error?.message}`);
  return NextResponse.json({ matches: [], nextUpdate: 60 });
}
