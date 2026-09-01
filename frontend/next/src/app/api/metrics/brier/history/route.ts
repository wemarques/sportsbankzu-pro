import { fetchBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * #199: historico de snapshots de Brier.
 *
 * Existia no backend desde sempre e nunca teve passagem pelo front — sem ela
 * nao havia como verificar se o cron voltou a gravar snapshot depois do #197,
 * nem inspecionar a serie de um jeito que nao fosse recalcular tudo.
 */
export async function GET(req: Request) {
  const limit = new URL(req.url).searchParams.get("limit") || "30";
  const result = await fetchBackend(`/metrics/brier/history?limit=${encodeURIComponent(limit)}`, {
    timeoutMs: 15_000,
  });
  if (result.ok) return Response.json(result.data);

  console.error(`[metrics/brier/history] ${result.error?.kind}: ${result.error?.message}`);
  return Response.json(
    { history: [], count: 0, _error: { kind: result.error?.kind }, _latencyMs: result.durationMs },
    { status: 503 },
  );
}
