import { NextRequest } from "next/server";
import { fetchBackend } from "@/lib/backend";

export const maxDuration = 30;

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));

  const result = await fetchBackend("/decision/pre", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 20_000,
  });

  if (result.ok) {
    return Response.json(result.data);
  }

  if (result.error) {
    console.error(
      `[decision/pre] ${result.error.kind} | ${result.error.message} | ${result.error.durationMs}ms`,
    );
  }

  return Response.json({ picks: [] });
}
