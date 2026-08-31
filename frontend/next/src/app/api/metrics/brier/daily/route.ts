import { fetchBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * #195: serie diaria de acuracia e Brier.
 *
 * O /api/metrics/brier existente e cumulativo — util para "o modelo bate a
 * casa no agregado?", inutil para "a queda comecou no deploy de terca?".
 * Esta rota expoe o dia a dia.
 */
export async function GET(req: Request) {
  const days = new URL(req.url).searchParams.get("days") || "30";
  const result = await fetchBackend(`/metrics/brier/daily?days=${encodeURIComponent(days)}`, {
    timeoutMs: 20_000,
  });
  if (result.ok) return Response.json(result.data);
  return Response.json({ series: [], count: 0, error: "Servidor de dados indisponível" }, { status: 503 });
}
