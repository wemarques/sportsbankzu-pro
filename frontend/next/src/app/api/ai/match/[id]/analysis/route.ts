import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

function fallbackResponse(message: string) {
  return Response.json({
    summary: message,
    key_points: [],
    recommendation: "",
    confidence: 0,
    last_updated: "",
  });
}

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  const result = await fetchBackend(
    `/api/ai/match/${encodeURIComponent(matchId)}/analysis`,
    { timeoutMs: 25_000 },
  );

  if (result.ok) {
    return Response.json(result.data);
  }

  console.error(
    `[ai/analysis] GET ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
  );
  return fallbackResponse("Servico de analise AI indisponivel.");
}

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  const result = await fetchBackend(
    `/api/ai/match/${encodeURIComponent(matchId)}/analysis/regenerate`,
    { method: "POST", timeoutMs: 25_000 },
  );

  if (result.ok) {
    return Response.json(result.data);
  }

  console.error(
    `[ai/analysis] POST ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
  );
  return fallbackResponse("Falha ao regenerar analise.");
}
