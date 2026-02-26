import { NextRequest } from "next/server";
import { fetchBackend, getBackendUrl } from "@/lib/backend";

export const maxDuration = 60;

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const backendBase = getBackendUrl();

  if (!backendBase) {
    return Response.json(
      { intra: [], inter: [], total_intra: 0, total_inter: 0, _error: { kind: "NOT_CONFIGURED" } },
      { status: 503 },
    );
  }

  const qs = new URLSearchParams({
    leagues: url.searchParams.get("leagues") ?? "",
    date: url.searchParams.get("date") ?? "today",
    tipos: url.searchParams.get("tipos") ?? "intra,inter",
    min_status: url.searchParams.get("min_status") ?? "NEUTRO",
    limite_intra: url.searchParams.get("limite_intra") ?? "8",
    limite_inter: url.searchParams.get("limite_inter") ?? "8",
  });

  const result = await fetchBackend(`/combinadas?${qs.toString()}`, { timeoutMs: 55_000 });

  if (result.ok) {
    return Response.json({ ...(result.data as object), _latencyMs: result.durationMs });
  }

  return Response.json(
    {
      intra: [],
      inter: [],
      total_intra: 0,
      total_inter: 0,
      _error: result.error ?? { kind: "BACKEND_ERROR" },
      _latencyMs: result.durationMs,
    },
    { status: 503 },
  );
}
