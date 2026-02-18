import { NextRequest } from "next/server";

const PY_BACKEND = process.env.PY_BACKEND_URL || "http://127.0.0.1:5001";
const TIMEOUT_MS = 25_000; // AI analysis may take longer than fixture fetches

function backendUrl(path: string): string {
  return `${PY_BACKEND.replace(/\/$/, "")}${path}`;
}

function fallbackResponse(message: string) {
  return new Response(
    JSON.stringify({
      summary: message,
      key_points: [],
      recommendation: "",
      confidence: 0,
      last_updated: "",
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(
      backendUrl(`/api/ai/match/${encodeURIComponent(matchId)}/analysis`),
      { cache: "no-store", signal: controller.signal },
    );
    clearTimeout(timeout);

    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    console.error("[ai/analysis] GET error:", err instanceof Error ? err.message : err);
    return fallbackResponse("Servico de analise AI indisponivel.");
  }
}

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(
      backendUrl(`/api/ai/match/${encodeURIComponent(matchId)}/analysis/regenerate`),
      { method: "POST", cache: "no-store", signal: controller.signal },
    );
    clearTimeout(timeout);

    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    console.error("[ai/analysis] POST error:", err instanceof Error ? err.message : err);
    return fallbackResponse("Falha ao regenerar analise.");
  }
}
