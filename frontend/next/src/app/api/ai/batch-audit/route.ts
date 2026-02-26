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

    console.error(
      `[ai/batch-audit] POST ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
    );
    return Response.json(
      { status: "error", message: "Servico de auditoria em lote indisponivel." },
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
