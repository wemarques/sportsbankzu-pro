import { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  try {
    const backend = process.env.PY_BACKEND_URL;
    if (backend) {
      const res = await fetch(`${backend.replace(/\\/$/, "")}/decision/pre`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    } else {
      return new Response(JSON.stringify({ picks: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
  } catch {
    return new Response(JSON.stringify({ picks: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
}

