/**
 * Shared backend connectivity module.
 *
 * Centralises URL handling, timeouts, error classification, and
 * structured logging for every Next.js API route that talks to the
 * Python FastAPI backend (AWS Lambda).
 */

/* ------------------------------------------------------------------ */
/*  URL helpers                                                       */
/* ------------------------------------------------------------------ */

const PY_BACKEND = process.env.PY_BACKEND_URL ?? null;

/** Normalised backend base URL (no trailing slash), or null. */
export function getBackendUrl(): string | null {
  return PY_BACKEND ? PY_BACKEND.replace(/\/+$/, "") : null;
}

/** Masks a URL for safe inclusion in logs (hides path & query). */
export function maskUrl(raw: string): string {
  try {
    const u = new URL(raw);
    return `${u.protocol}//${u.host}/***`;
  } catch {
    return "(invalid URL)";
  }
}

/* ------------------------------------------------------------------ */
/*  Error classification                                              */
/* ------------------------------------------------------------------ */

export type BackendErrorKind =
  | "TIMEOUT"
  | "CONNECTION_ERROR"
  | "HTTP_ERROR"
  | "PARSE_ERROR"
  | "UNKNOWN";

export interface BackendError {
  kind: BackendErrorKind;
  message: string;
  url: string;          // always masked
  durationMs: number;
}

export function classifyError(
  err: unknown,
  fullUrl: string,
  startMs: number,
): BackendError {
  const durationMs = Date.now() - startMs;
  const masked = maskUrl(fullUrl);

  // AbortController timeout
  if (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.message === "This operation was aborted")
  ) {
    return { kind: "TIMEOUT", message: `Aborted after ${durationMs}ms`, url: masked, durationMs };
  }

  // Network-level failures
  if (err instanceof TypeError) {
    const msg = err.message;
    if (/fetch failed|ECONNREFUSED|ENOTFOUND|EHOSTUNREACH|ENETUNREACH/.test(msg)) {
      return { kind: "CONNECTION_ERROR", message: msg, url: masked, durationMs };
    }
  }

  if (err instanceof SyntaxError) {
    return { kind: "PARSE_ERROR", message: err.message, url: masked, durationMs };
  }

  if (err instanceof Error) {
    return { kind: "UNKNOWN", message: err.message, url: masked, durationMs };
  }

  return { kind: "UNKNOWN", message: String(err), url: masked, durationMs };
}

/* ------------------------------------------------------------------ */
/*  fetchBackend — single entrypoint for all backend calls            */
/* ------------------------------------------------------------------ */

export interface FetchBackendOpts {
  timeoutMs?: number;       // default 20 000
  method?: string;          // default GET
  body?: string;            // JSON string for POST
}

export interface FetchResult {
  ok: boolean;
  data?: unknown;
  error?: BackendError;
  durationMs: number;
}

export async function fetchBackend(
  path: string,
  opts: FetchBackendOpts = {},
): Promise<FetchResult> {
  const base = getBackendUrl();
  if (!base) {
    return {
      ok: false,
      durationMs: 0,
      error: {
        kind: "CONNECTION_ERROR",
        message: "PY_BACKEND_URL not configured",
        url: "(none)",
        durationMs: 0,
      },
    };
  }

  const url = `${base}${path}`;
  const timeoutMs = opts.timeoutMs ?? 20_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const startMs = Date.now();

  try {
    const res = await fetch(url, {
      method: opts.method ?? "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: opts.body ? { "content-type": "application/json" } : undefined,
      body: opts.body,
    });
    clearTimeout(timer);
    const durationMs = Date.now() - startMs;

    if (!res.ok) {
      const errBody = await res.text().catch(() => "(unreadable)");
      return {
        ok: false,
        durationMs,
        error: {
          kind: "HTTP_ERROR",
          message: `HTTP ${res.status}: ${errBody.slice(0, 200)}`,
          url: maskUrl(url),
          durationMs,
        },
      };
    }

    const data = await res.json();
    return { ok: true, data, durationMs: Date.now() - startMs };
  } catch (err) {
    clearTimeout(timer);
    const classified = classifyError(err, url, startMs);
    return { ok: false, durationMs: classified.durationMs, error: classified };
  }
}
