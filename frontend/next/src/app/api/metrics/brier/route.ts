import { fetchBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

/**
 * #198: ao falhar, esta rota devolvia apenas {error, total_picks: 0} — sem
 * duracao e sem tipo de erro. Um 503 aqui podia ser timeout do snapshot,
 * backend fora do ar ou erro de query, e nao havia como distinguir sem
 * adivinhar. Passa a logar e a expor _error.kind e _latencyMs.
 *
 * O timeout SEGUE em 15s de proposito. O vercel.json declara maxDuration 30
 * para "app/api/**\/*.ts", mas a Vercel constroi este projeto a partir de
 * frontend/next (o build log mostra sportsbank-pro@4.0.0 / Next 15.5.15) e as
 * rotas vivem em src/app/api/** — o glob nao tem o prefixo src/. Enquanto isso
 * nao estiver confirmado, subir o timeout arriscaria trocar este 503 com corpo
 * por um 504 de plataforma sem corpo nenhum, que e justamente o diagnostico
 * que se quer preservar.
 */
export async function GET() {
  const result = await fetchBackend("/metrics/brier", { timeoutMs: 15_000 });
  if (result.ok) return Response.json(result.data);

  console.error(
    `[metrics/brier] ${result.error?.kind}: ${result.error?.message} (${result.durationMs}ms)`,
  );
  return Response.json(
    {
      error: "Servidor de dados indisponível",
      total_picks: 0,
      _error: { kind: result.error?.kind, message: result.error?.message },
      _latencyMs: result.durationMs,
    },
    { status: 503 },
  );
}
