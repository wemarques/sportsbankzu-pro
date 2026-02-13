import { NextRequest } from "next/server";

const PY_BACKEND = process.env.PY_BACKEND_URL || "http://127.0.0.1:5001";

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const res = await fetch(
      `${PY_BACKEND.replace(/\/$/, "")}/api/ai/match/${encodeURIComponent(matchId)}/analysis`,
      { cache: "no-store" },
    );
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return new Response(
      JSON.stringify({
        summary: "Servico de analise AI indisponivel.",
        key_points: [],
        recommendation: "",
        confidence: 0,
        last_updated: "",
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
}

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const matchId = params.id;
  try {
    const res = await fetch(
      `${PY_BACKEND.replace(/\/$/, "")}/api/ai/match/${encodeURIComponent(matchId)}/analysis/regenerate`,
      { method: "POST", cache: "no-store" },
    );
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: res.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return new Response(
      JSON.stringify({
        summary: "Falha ao regenerar analise.",
        key_points: [],
        recommendation: "",
        confidence: 0,
        last_updated: "",
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
}
