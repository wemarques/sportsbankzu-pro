import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #257 — proxy de `GET /ledger/picks` (Lambda). Mesmo padrao de
 * `api/ledger/agregado/route.ts`.
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function statusDoErro(kind?: string, message?: string): number {
  if (kind === "HTTP_ERROR") {
    const m = /^HTTP (\d+):/.exec(message ?? "");
    if (m) return Number(m[1]);
  }
  return 503;
}

export async function GET(request: Request) {
  if (!getBackendUrl()) {
    return Response.json(
      { ok: false, error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL não configurado" } },
      { status: 503 },
    );
  }

  const { searchParams } = new URL(request.url);
  const periodo = searchParams.get("periodo") ?? "30d";
  const params = new URLSearchParams({ periodo });
  const familia = searchParams.get("familia");
  const liga = searchParams.get("liga");
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);

  const result = await fetchBackend(`/ledger/picks?${params.toString()}`, { timeoutMs: 25_000 });
  if (!result.ok) {
    const status = statusDoErro(result.error?.kind, result.error?.message);
    console.error(`[ledger/picks] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`);
    return Response.json(
      {
        ok: false,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível carregar os picks do período.",
        },
      },
      { status },
    );
  }
  return Response.json({ ok: true, ...(result.data as Record<string, unknown>) });
}
