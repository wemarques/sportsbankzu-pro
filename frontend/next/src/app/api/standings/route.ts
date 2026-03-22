import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const league = url.searchParams.get("league") || "";

  if (!league) {
    return Response.json({ standings: [], error: "Parâmetro 'league' é obrigatório" });
  }

  const qs = new URLSearchParams({ league });
  const result = await fetchBackend(`/standings?${qs.toString()}`, {
    timeoutMs: 10_000,
  });

  if (result.ok) {
    return Response.json(result.data);
  }

  console.error(`[standings/route] Error fetching standings: ${result.error?.message}`);
  return Response.json(
    { standings: [], error: result.error?.message ?? "Erro ao buscar classificação" },
    { status: 502 },
  );
}
