import { NextRequest } from "next/server";
import { fetchBackend, getBackendUrl } from "@/lib/backend";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const backendBase = getBackendUrl();

  if (!backendBase) {
    return Response.json(
      { intra: [], inter: [], total_intra: 0, total_inter: 0, _error: { kind: "NOT_CONFIGURED" } },
      { status: 503 },
    );
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return Response.json(
      { intra: [], inter: [], total_intra: 0, total_inter: 0, _error: { kind: "PARSE_ERROR", message: "Invalid JSON body" } },
      { status: 400 },
    );
  }

  // POST with match data → backend computes combinadas without re-fetching
  const COMBINADAS_TIMEOUT_MS = 25_000;
  let result = await fetchBackend("/combinadas", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: COMBINADAS_TIMEOUT_MS,
  });

  // Auto-retry once on transient errors (only if enough time remains)
  const isPostRetryable =
    !result.ok &&
    result.error &&
    result.durationMs < 30_000 &&
    (result.error.kind === "TIMEOUT" ||
      result.error.kind === "CONNECTION_ERROR" ||
      (result.error.kind === "HTTP_ERROR" && /HTTP (429|502|503|504)/.test(result.error.message)));
  if (isPostRetryable) {
    const is429 = /HTTP 429/.test(result.error!.message);
    const backoffMs = is429 ? 2000 : 500;
    console.log(
      `[combinadas] ${result.error!.kind} on first attempt (${result.durationMs}ms), retrying after ${backoffMs}ms...`,
    );
    await new Promise((r) => setTimeout(r, backoffMs));
    result = await fetchBackend("/combinadas", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: COMBINADAS_TIMEOUT_MS,
    });
  }

  if (result.ok) {
    return Response.json({ ...(result.data as object), _latencyMs: result.durationMs });
  }

  const errorKind = result.error?.kind ?? "BACKEND_ERROR";
  console.error(
    `[combinadas] ${errorKind} | ${result.error?.message ?? ""} | ${result.durationMs}ms`,
  );

  const friendlyMsg =
    errorKind === "TIMEOUT"
      ? "O servidor demorou para responder. O Lambda pode estar iniciando — tente novamente em 30s."
      : errorKind === "CONNECTION_ERROR"
        ? "Nao foi possivel conectar ao servidor. Verifique se o backend esta ativo."
        : errorKind === "HTTP_ERROR"
          ? "O servidor retornou um erro temporario. Tente novamente em instantes."
          : "Servidor de duplas temporariamente indisponivel. Tente novamente.";

  return Response.json(
    {
      intra: [],
      inter: [],
      total_intra: 0,
      total_inter: 0,
      _error: { kind: errorKind, message: friendlyMsg },
      _latencyMs: result.durationMs,
    },
    { status: 503 },
  );
}

// Legacy GET fallback (uses league IDs, slower)
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

  const COMBINADAS_TIMEOUT_MS = 25_000;
  let result = await fetchBackend(`/combinadas?${qs.toString()}`, { timeoutMs: COMBINADAS_TIMEOUT_MS });

  const isGetRetryable =
    !result.ok &&
    result.error &&
    result.durationMs < 30_000 &&
    (result.error.kind === "TIMEOUT" ||
      result.error.kind === "CONNECTION_ERROR" ||
      (result.error.kind === "HTTP_ERROR" && /HTTP (429|502|503|504)/.test(result.error.message)));
  if (isGetRetryable) {
    const is429 = /HTTP 429/.test(result.error!.message);
    const backoffMs = is429 ? 2000 : 500;
    console.log(
      `[combinadas] ${result.error!.kind} on first attempt (${result.durationMs}ms), retrying after ${backoffMs}ms...`,
    );
    await new Promise((r) => setTimeout(r, backoffMs));
    result = await fetchBackend(`/combinadas?${qs.toString()}`, { timeoutMs: COMBINADAS_TIMEOUT_MS });
  }

  if (result.ok) {
    return Response.json({ ...(result.data as object), _latencyMs: result.durationMs });
  }

  const errorKind = result.error?.kind ?? "BACKEND_ERROR";
  console.error(
    `[combinadas] ${errorKind} | ${result.error?.message ?? ""} | ${result.durationMs}ms`,
  );

  const friendlyMsg =
    errorKind === "TIMEOUT"
      ? "O servidor demorou para responder. O Lambda pode estar iniciando — tente novamente em 30s."
      : errorKind === "CONNECTION_ERROR"
        ? "Nao foi possivel conectar ao servidor. Verifique se o backend esta ativo."
        : errorKind === "HTTP_ERROR"
          ? "O servidor retornou um erro temporario. Tente novamente em instantes."
          : "Servidor de duplas temporariamente indisponivel. Tente novamente.";

  return Response.json(
    {
      intra: [],
      inter: [],
      total_intra: 0,
      total_inter: 0,
      _error: { kind: errorKind, message: friendlyMsg },
      _latencyMs: result.durationMs,
    },
    { status: 503 },
  );
}
