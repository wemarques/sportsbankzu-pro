import { fetchBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  const result = await fetchBackend("/metrics/brier", { timeoutMs: 15_000 });
  if (result.ok) return Response.json(result.data);
  return Response.json({ error: "Backend indisponivel", total_picks: 0 }, { status: 503 });
}
