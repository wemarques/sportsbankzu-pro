import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #255 — proxy de `GET /ledger/dia` (Lambda). Mesmo padrao de
 * `api/ml/status/route.ts`: o navegador nao conhece PY_BACKEND_URL, e
 * fetchBackend concentra a guarda #114/#203 (nunca api Gateway).
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
  const data = searchParams.get("data");
  if (!data) {
    return Response.json(
      { ok: false, error: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório (YYYY-MM-DD)" } },
      { status: 400 },
    );
  }

  const result = await fetchBackend(`/ledger/dia?data=${encodeURIComponent(data)}`, { timeoutMs: 25_000 });
  if (!result.ok) {
    const status = statusDoErro(result.error?.kind, result.error?.message);
    console.error(`[ledger/dia] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`);
    return Response.json(
      {
        ok: false,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível carregar o ledger do dia.",
        },
      },
      { status },
    );
  }
  return Response.json({ ok: true, ...(result.data as Record<string, unknown>) });
}
