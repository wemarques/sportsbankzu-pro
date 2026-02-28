import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 60;

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const body = await req.json().catch(() => ({}));
    const url = new URL(req.url);
    const qs = url.search ? url.search : "";
    const result = await fetchBackend(
      `/api/ai/match/${encodeURIComponent(matchId)}/audit${qs}`,
      { method: "POST", body: JSON.stringify(body), timeoutMs: 55_000 },
    );

    if (result.ok) {
      return Response.json(result.data);
    }

    const kind = result.error?.kind ?? "UNKNOWN";
    const msg = result.error?.message ?? "";
    let userMessage = "Auditoria individual indisponivel. Use 'Auditar Rodada' para resultado instantaneo.";
    if (kind === "CONNECTION_ERROR" && msg.includes("PY_BACKEND_URL")) {
      userMessage = "Backend nao configurado. Use 'Auditar Rodada' para auditoria local instantanea.";
    } else if (kind === "TIMEOUT") {
      userMessage = "Tempo esgotado — o backend demorou para responder. Use 'Auditar Rodada' para resultado instantaneo.";
    } else if (kind === "CONNECTION_ERROR") {
      userMessage = "Backend indisponivel. Use 'Auditar Rodada' para auditoria local instantanea.";
    } else if (kind === "HTTP_ERROR" && /50[234]/.test(msg)) {
      userMessage = "Backend reiniciando (cold start). Tente novamente em 10-15s, ou use 'Auditar Rodada'.";
    } else if (kind === "HTTP_ERROR" && msg) {
      userMessage = msg.length > 120 ? msg.slice(0, 120) + "..." : msg;
    }

    console.error(`[ai/audit] POST ${kind} | ${msg} | ${result.error?.durationMs ?? 0}ms`);
    return Response.json(
      { status: "error", message: userMessage, errorKind: kind },
      { status: 502 },
    );
  } catch (err) {
    console.error("[ai/audit] POST error:", err instanceof Error ? err.message : err);
    return Response.json(
      { status: "error", message: "Erro interno no proxy de auditoria." },
      { status: 500 },
    );
  }
}
