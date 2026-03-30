import { fetchBackend } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  const result = await fetchBackend("/health/reliability", { timeoutMs: 10_000 });
  if (result.ok) return Response.json(result.data);
  return Response.json(
    { error: "Backend indisponivel", detail: result.error?.message },
    { status: 503 },
  );
}
