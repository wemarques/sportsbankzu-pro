import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 30;

export async function GET(req: NextRequest) {
  const backend = process.env.PY_BACKEND_URL;
  if (!backend) {
    return NextResponse.json(
      {
        version: "unknown",
        last_batch_audit: null,
        recent_audits: [],
        recent_corrections: [],
        active_corrections: {},
        summary: {
          total_audits: 0,
          total_corrections_applied: 0,
          has_recent_activity: false,
        },
      },
      { status: 200 },
    );
  }

  const base = backend.replace(/\/+$/, "");
  const { searchParams } = new URL(req.url);
  const days = searchParams.get("days") || "3";

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    const res = await fetch(`${base}/api/audit/status?days=${days}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      console.error(`[audit/status] Backend returned ${res.status}`);
      return NextResponse.json(
        { recent_corrections: [], summary: { has_recent_activity: false } },
        { status: 200 },
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: 200 });
  } catch (err) {
    console.error(
      "[audit/status] Backend error:",
      err instanceof Error ? err.message : err,
    );
    return NextResponse.json(
      {
        version: "unknown",
        last_batch_audit: null,
        recent_audits: [],
        recent_corrections: [],
        active_corrections: {},
        summary: {
          total_audits: 0,
          total_corrections_applied: 0,
          has_recent_activity: false,
        },
      },
      { status: 200 },
    );
  }
}
