import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

/** Mistral-only evaluation — lightweight, no fixture fetching. ~3-5s. */
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const result = await fetchBackend("/api/ai/batch-audit/evaluate", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 25_000,
    });

    if (result.ok) {
      return Response.json(result.data);
    }

    console.error(
      `[ai/batch-audit/evaluate] ${result.error?.kind} | ${result.error?.message}`,
    );
    return Response.json(
      { status: "error", message: "Avaliacao Mistral indisponivel.", model_evaluation: null },
      { status: 502 },
    );
  } catch (err) {
    console.error("[ai/batch-audit/evaluate] error:", err instanceof Error ? err.message : err);
    return Response.json(
      { status: "error", message: "Erro interno.", model_evaluation: null },
      { status: 500 },
    );
  }
}
