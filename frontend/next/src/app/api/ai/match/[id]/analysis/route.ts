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
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  if (matchId.startsWith("mock-") || matchId.includes("-mock-")) {
    return fallbackResponse(
      "Analise AI disponivel apenas para jogos com dados reais. Selecione um jogo da lista principal.",
    );
  }
  const url = new URL(req.url);
  const homeTeam = url.searchParams.get("home_team") || "";
  const awayTeam = url.searchParams.get("away_team") || "";
  const qs = new URLSearchParams();
  if (homeTeam) qs.set("home_team", homeTeam);
  if (awayTeam) qs.set("away_team", awayTeam);
  const qsStr = qs.toString() ? `?${qs.toString()}` : "";
  const result = await fetchBackend(
    `/api/ai/match/${encodeURIComponent(matchId)}/analysis${qsStr}`,
    { timeoutMs: 28_000 },
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
    { method: "POST", timeoutMs: 28_000 },
  );

  if (result.ok) {
    return Response.json(result.data);
  }

  console.error(
    `[ai/analysis] POST ${result.error?.kind} | ${result.error?.message} | ${result.error?.durationMs}ms`,
  );
  return fallbackResponse("Falha ao regenerar analise.");
}
