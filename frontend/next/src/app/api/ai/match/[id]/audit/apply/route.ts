import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const body = await req.json().catch(() => ({}));
    const result = await fetchBackend(
      `/api/ai/match/${encodeURIComponent(matchId)}/audit/apply`,
      { method: "POST", body: JSON.stringify(body), timeoutMs: 15_000 },
    );

    if (result.ok) {
      return Response.json(result.data);
    }

    console.error(
      `[ai/audit/apply] POST ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
    );
    return Response.json(
      { status: "error", message: "Falha ao aplicar correcao." },
      { status: 502 },
    );
  } catch (err) {
    console.error("[ai/audit/apply] POST error:", err instanceof Error ? err.message : err);
    return Response.json(
      { status: "error", message: "Erro interno ao aplicar correcao." },
      { status: 500 },
    );
  }
}
