import { NextRequest } from "next/server";
import { fetchBackend, getBackendUrl, maskUrl } from "@/lib/backend";

export const maxDuration = 15;

export async function GET(req: NextRequest) {
  const debug = new URL(req.url).searchParams.get("debug") === "true";
  const backendBase = getBackendUrl();

  if (!backendBase) {
    return Response.json(
      {
        status: "error",
        reason: "PY_BACKEND_URL not configured",
        timestamp: new Date().toISOString(),
      },
      { status: 503 },
    );
  }

  const result = await fetchBackend("/health", { timeoutMs: 10_000 });

  if (result.ok) {
    return Response.json({
      status: "ok",
      backend: result.data,
      latencyMs: result.durationMs,
      timestamp: new Date().toISOString(),
      ...(debug ? { backendUrl: maskUrl(backendBase) } : {}),
    });
  }

  return Response.json(
    {
      status: "error",
      errorKind: result.error?.kind,
      errorMessage: result.error?.message,
      latencyMs: result.durationMs,
      timestamp: new Date().toISOString(),
      ...(debug ? { backendUrl: maskUrl(backendBase) } : {}),
    },
    { status: 502 },
  );
}
