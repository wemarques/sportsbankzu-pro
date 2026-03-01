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

  const COMBINADAS_TIMEOUT_MS = 55_000;
  let result = await fetchBackend(`/combinadas?${qs.toString()}`, { timeoutMs: COMBINADAS_TIMEOUT_MS });

  // Auto-retry once on transient errors (Lambda cold start)
  if (
    !result.ok &&
    result.error &&
    (result.error.kind === "TIMEOUT" ||
      result.error.kind === "CONNECTION_ERROR" ||
      (result.error.kind === "HTTP_ERROR" && /HTTP (502|503|504)/.test(result.error.message)))
  ) {
    console.log(
      `[combinadas] ${result.error.kind} on first attempt (${result.durationMs}ms), retrying...`,
    );
    result = await fetchBackend(`/combinadas?${qs.toString()}`, { timeoutMs: COMBINADAS_TIMEOUT_MS });
  }

  if (result.ok) {
    return Response.json({ ...(result.data as object), _latencyMs: result.durationMs });
  }

  console.error(
    `[combinadas] ${result.error?.kind ?? "UNKNOWN"} | ${result.error?.message ?? ""} | ${result.durationMs}ms`,
  );
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
