import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const result = await fetchBackend("/api/ai/batch-audit", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 55_000,
    });

    if (result.ok) {
      return Response.json(result.data);
    }

    const kind = result.error?.kind ?? "UNKNOWN";
    const msg = result.error?.message ?? "";
    let userMessage = "Servico de auditoria em lote indisponivel.";
    if (kind === "CONNECTION_ERROR" && msg.includes("PY_BACKEND_URL")) {
      userMessage = "Backend nao configurado. Defina PY_BACKEND_URL no Vercel (ou .env.local) com a URL do FastAPI.";
    } else if (kind === "TIMEOUT") {
      userMessage = "Tempo esgotado. A auditoria em lote demorou para responder. Tente novamente.";
    } else if (kind === "CONNECTION_ERROR") {
      userMessage = "Nao foi possivel conectar ao backend. Verifique se o FastAPI esta rodando e PY_BACKEND_URL esta correto.";
    } else if (kind === "HTTP_ERROR" && /50[234]/.test(msg)) {
      userMessage = "Backend temporariamente indisponivel. O servidor pode estar reiniciando (cold start). Tente novamente em 10-15 segundos.";
    } else if (kind === "HTTP_ERROR" && msg) {
      userMessage = msg.length > 120 ? msg.slice(0, 120) + "..." : msg;
    }

    console.error(
      `[ai/batch-audit] POST ${kind} | ${msg} | ${result.error?.durationMs ?? 0}ms`,
    );
    return Response.json(
      { status: "error", message: userMessage, errorKind: kind },
      { status: 502 },
    );
  } catch (err) {
    console.error(
      "[ai/batch-audit] POST error:",
      err instanceof Error ? err.message : err,
    );
    return Response.json(
      { status: "error", message: "Erro interno no proxy de auditoria em lote." },
      { status: 500 },
    );
  }
}
