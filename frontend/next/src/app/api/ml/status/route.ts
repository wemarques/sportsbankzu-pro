import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #250 — proxy de `/ml/status/all` (Lambda Function URL) para o selo de
 * confianca das ligas.
 *
 * Por que proxy e nao fetch direto do browser: o navegador nao conhece
 * PY_BACKEND_URL e `fetchBackend` concentra a guarda #114/#203 (nunca
 * execute-api). Por que cache em memoria: a rota e leitura de METADADO de
 * modelo, que so muda em retrain, e o custo real medido nao esta na rota e sim
 * no cold start da Lambda.
 *
 * Latencia medida em 2026-09-10 contra producao (3 chamadas seguidas):
 *   cold start 20.35s | warm 0.56s | warm 0.58s   (payload 2 056 bytes)
 * Ou seja: nao e recomputacao, e leitura de metadado — o teto de 30s do API
 * Gateway do #114/#203 nao esta em jogo aqui, e a Function URL (60s) cobre o
 * cold start com folga. Mesmo assim o selo NUNCA bloqueia a tela: os jogos vem
 * de `/api/matches/fetch`, e este hook so decide o que o selo mostra.
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

/** TTL do cache em memoria (segue a convencao do LAMBDA_CORRECTIONS_TTL_S). */
const TTL_MS = Number(process.env.ML_STATUS_TTL_S ?? 300) * 1000;

interface MlLeagueStatus {
  available: boolean;
  trained_at: string | null;
  validation_brier: number | null;
  n_samples: number | null;
}

let cache: { at: number; leagues: Record<string, MlLeagueStatus> } | null = null;

export async function GET() {
  if (!getBackendUrl()) {
    // #250 requisito 2 — sem backend NAO afirmamos nivel nenhum.
    return Response.json(
      {
        ok: false,
        leagues: null,
        error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL não configurado" },
      },
      { status: 503 },
    );
  }

  if (cache && Date.now() - cache.at < TTL_MS) {
    return Response.json({ ok: true, leagues: cache.leagues, _cached: true });
  }

  // Uma repeticao cobre o cold start (~20s medidos); a segunda chamada e ~0.6s.
  let result = await fetchBackend("/ml/status/all", { timeoutMs: 25_000 });
  if (!result.ok && (result.error?.kind === "TIMEOUT" || result.error?.kind === "CONNECTION_ERROR")) {
    result = await fetchBackend("/ml/status/all", { timeoutMs: 25_000 });
  }

  if (!result.ok) {
    console.error(
      `[ml/status] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`,
    );
    return Response.json(
      {
        ok: false,
        leagues: null,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível verificar os modelos em produção.",
        },
        _latencyMs: result.durationMs,
      },
      { status: 503 },
    );
  }

  const data = result.data as { leagues?: Record<string, MlLeagueStatus>; error?: string };
  if (!data?.leagues || typeof data.leagues !== "object") {
    // O backend responde 200 com {"error": ...} quando o handler falha —
    // 200 aqui NAO significa resposta utilizavel.
    console.error(`[ml/status] resposta sem 'leagues' | ${JSON.stringify(data).slice(0, 200)}`);
    return Response.json(
      {
        ok: false,
        leagues: null,
        error: { kind: "PARSE_ERROR", message: "Resposta do backend sem 'leagues'." },
      },
      { status: 503 },
    );
  }

  cache = { at: Date.now(), leagues: data.leagues };
  console.log(
    `[ml/status] OK | ${Object.keys(data.leagues).length} ligas | ` +
      `${Object.values(data.leagues).filter((l) => l.available).length} com modelo ativo | ` +
      `${result.durationMs}ms`,
  );
  return Response.json({ ok: true, leagues: data.leagues, _latencyMs: result.durationMs });
}
