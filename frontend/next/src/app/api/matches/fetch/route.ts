import { NextRequest } from "next/server";
import { fetchBackend, getBackendUrl, maskUrl } from "@/lib/backend";

/** Allow up to 60 s on Vercel for Lambda cold starts + multi-league fetches. */
export const maxDuration = 60;

const isDev = process.env.NODE_ENV === "development";

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const leaguesParam = url.searchParams.get("leagues") || "";
  const leagueIds = leaguesParam.split(",").map((s) => s.trim()).filter(Boolean);
  const debug = url.searchParams.get("debug") === "true";

  if (leagueIds.length === 0) {
    return Response.json({ matches: [], _dataSource: "empty-request" });
  }

  // 1. Try Python backend if configured
  const backendBase = getBackendUrl();

  if (backendBase) {
    const date = url.searchParams.get("date") || "today";
    const qs = new URLSearchParams({ leagues: leagueIds.join(","), date });
    // With fan-out each batch has ≤3 leagues.
    // Cold start (~10-20s) + 3 leagues (~10-15s) = ~20-35s.
    // Timeout 28s + 1 retry = 56s, within 60s maxDuration.
    const BATCH_TIMEOUT_MS = 28_000;

    let result = await fetchBackend(`/fixtures?${qs.toString()}`, {
      timeoutMs: BATCH_TIMEOUT_MS,
    });

    // Auto-retry once on transient errors (Lambda cold start takes ~10-20s, second call is fast)
    if (
      !result.ok &&
      result.error &&
      (result.error.kind === "TIMEOUT" ||
        result.error.kind === "CONNECTION_ERROR" ||
        (result.error.kind === "HTTP_ERROR" && /HTTP (502|503|504)/.test(result.error.message)))
    ) {
      console.log(
        `[fetch/route] ${result.error.kind} on first attempt (${result.durationMs}ms), retrying (Lambda cold start)...`,
      );
      result = await fetchBackend(`/fixtures?${qs.toString()}`, {
        timeoutMs: BATCH_TIMEOUT_MS,
      });
    }

    if (result.ok) {
      const matches = (result.data as Record<string, unknown>)?.matches;
      if (Array.isArray(matches) && matches.length > 0) {
        // Quality gate: detect mock data from backend
        // 1. Generic team names: "Team A", "Team B", etc.
        // 2. Mock IDs: IDs containing "-mock-" (backend generate_mock_fixtures pattern)
        // 3. Uniform odds: all matches have identical odds (sign of mock generator)
        const hasGenericNames = matches.every((m: Record<string, unknown>) => {
          const home = typeof m.homeTeam === "string" ? m.homeTeam : (m.homeTeam as Record<string, string>)?.name;
          return home && /^Team [A-Z]$/i.test(home);
        });

        const hasMockIds = matches.some((m: Record<string, unknown>) => {
          const id = String(m.id ?? "");
          return id.includes("-mock-");
        });

        const hasUniformOdds = matches.length >= 3 && (() => {
          const oddsSet = new Set<string>();
          for (const m of matches.slice(0, 10) as Record<string, unknown>[]) {
            const odds = m.odds as Record<string, number> | undefined;
            if (odds?.home) oddsSet.add(`${odds.home}-${odds.draw}-${odds.away}`);
          }
          return oddsSet.size === 1; // All matches have identical odds
        })();

        const isMockData = hasGenericNames || hasMockIds || hasUniformOdds;

        if (!isMockData) {
          console.log(
            `[fetch/route] Backend OK | ${matches.length} matches | ${result.durationMs}ms`,
          );
          return Response.json({
            ...(result.data as object),
            _dataSource: "backend",
            _latencyMs: result.durationMs,
          });
        }

        // Backend returned mock data (detected by: names/IDs/uniform odds)
        const mockReason = hasGenericNames ? "generic names" : hasMockIds ? "mock IDs" : "uniform odds";
        console.warn(
          `[fetch/route] Backend returned mock data (${mockReason}) | ${matches.length} matches | ${result.durationMs}ms`,
        );

        // In development: allow mock data with flag
        if (isDev) {
          const { generateMockMatches } = await import("@/lib/mockMatches");
          const devMock = generateMockMatches(leagueIds);
          console.log(`[fetch/route] DEV MODE: using frontend mock | ${devMock.length} matches`);
          return Response.json({
            matches: devMock,
            _dataSource: "mock-dev",
            _isMockData: true,
            _latencyMs: result.durationMs,
          });
        }

        // In production: return empty with error info (never show mock silently)
        return Response.json(
          {
            matches: [],
            _dataSource: "backend-low-quality",
            _error: {
              kind: "LOW_QUALITY_DATA",
              message: "O backend retornou dados de baixa qualidade (nomes genericos). Tente novamente em alguns minutos.",
            },
            _latencyMs: result.durationMs,
          },
          { status: 503 },
        );
      }

      // Backend returned 0 matches — this is legitimate (no games for this date)
      console.log(
        `[fetch/route] Backend returned 0 matches for date=${url.searchParams.get("date") || "today"} | ${result.durationMs}ms`,
      );
      return Response.json({
        matches: [],
        _dataSource: "backend-empty",
        _latencyMs: result.durationMs,
      });
    }

    // Backend error (timeout, connection refused, 500, etc.)
    if (result.error) {
      console.error(
        `[fetch/route] ${result.error.kind} | ${result.error.message} | url: ${result.error.url} | ${result.error.durationMs}ms`,
      );
    }

    // In development: fallback to mock data with flag
    if (isDev) {
      const { generateMockMatches } = await import("@/lib/mockMatches");
      const devMock = generateMockMatches(leagueIds);
      console.log(`[fetch/route] DEV MODE: backend error, using mock | ${devMock.length} matches`);
      return Response.json({
        matches: devMock,
        _dataSource: "mock-dev",
        _isMockData: true,
        _error: result.error ?? { kind: "BACKEND_ERROR", message: "Backend indisponivel (dev mode)" },
        _latencyMs: result.durationMs,
      });
    }

    // In production: return error, never mock
    const errorKind = result.error?.kind ?? "BACKEND_ERROR";
    const friendlyMsg = _friendlyErrorMessage(errorKind, result.durationMs);
    return Response.json(
      {
        matches: [],
        _dataSource: "error",
        _error: {
          kind: errorKind,
          message: friendlyMsg,
          code: errorKind,
          durationMs: result.durationMs,
        },
        _debug: debug ? {
          error: result.error,
          backendConfigured: true,
          backendUrl: maskUrl(backendBase),
          durationMs: result.durationMs,
        } : undefined,
        _latencyMs: result.durationMs,
      },
      { status: 503 },
    );
  }

  // Backend URL not configured
  console.warn("[fetch/route] PY_BACKEND_URL not configured");

  // In development: fallback to mock data
  if (isDev) {
    const { generateMockMatches } = await import("@/lib/mockMatches");
    const devMock = generateMockMatches(leagueIds);
    console.log(`[fetch/route] DEV MODE: no backend URL, using mock | ${devMock.length} matches`);
    return Response.json({
      matches: devMock,
      _dataSource: "mock-dev",
      _isMockData: true,
    });
  }

  // In production: return error
  return Response.json(
    {
      matches: [],
      _dataSource: "error",
      _error: {
        kind: "NOT_CONFIGURED",
        message: "O servidor de dados nao esta configurado. Contate o administrador.",
      },
      _debug: debug ? {
        error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL is not set" },
        backendConfigured: false,
      } : undefined,
    },
    { status: 503 },
  );
}

/** Maps error kind to a user-facing message with diagnostic hint. */
function _friendlyErrorMessage(kind: string, durationMs?: number): string {
  const dur = durationMs ? ` (${Math.round(durationMs / 1000)}s)` : "";
  switch (kind) {
    case "TIMEOUT":
      return `O servidor demorou demais para responder${dur}. Lambda pode estar em cold start — tente novamente.`;
    case "CONNECTION_ERROR":
      return "Nao foi possivel conectar ao servidor de dados. Verifique se o backend esta ativo.";
    case "HTTP_ERROR":
      return `O servidor retornou um erro${dur}. Pode ser throttling ou reinicializacao do Lambda.`;
    default:
      return "O servidor de dados esta temporariamente indisponivel. Tente novamente em alguns minutos.";
  }
}
