import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

export async function POST(req: NextRequest) {
  const parameterName = req.nextUrl.searchParams.get("parameter_name");
  const originalValue = req.nextUrl.searchParams.get("original_value");

  if (!parameterName || !originalValue) {
    return Response.json(
      { status: "error", message: "parameter_name and original_value are required" },
      { status: 400 },
    );
  }

  try {
    const result = await fetchBackend(
      `/api/ai/correction/revert?parameter_name=${encodeURIComponent(parameterName)}&original_value=${encodeURIComponent(originalValue)}`,
      { method: "POST", timeoutMs: 15_000 },
    );

    if (result.ok) {
      return Response.json(result.data);
    }

    console.error(
      `[ai/correction/revert] POST ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
    );
    return Response.json(
      { status: "error", message: "Falha ao reverter correcao." },
      { status: 502 },
    );
  } catch (err) {
    console.error("[ai/correction/revert] POST error:", err instanceof Error ? err.message : err);
    return Response.json(
      { status: "error", message: "Erro interno ao reverter correcao." },
      { status: 500 },
    );
  }
}
