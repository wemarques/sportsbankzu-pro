/**
 * API client — todas as chamadas passam pelas rotas proxy do Next.js (/api/*)
 * para usar PY_BACKEND_URL (server-side) e evitar CORS.
 */

export interface MatchesResponse {
  matches: unknown[];
  _dataSource?: string;
  _isMockData?: boolean;
  _error?: {
    kind: string;
    message: string;
  };
  _latencyMs?: number;
}

/**
 * Fetch matches for a single batch of leagues (internal helper).
 */
async function _fetchMatchesBatch(leagues: string, date?: string): Promise<MatchesResponse> {
  try {
    const params = new URLSearchParams({ leagues });
    if (date) params.append("date", date);
    const res = await fetch(`/api/matches/fetch?${params.toString()}`, { cache: "no-store" });
    const data = await res.json();

    return {
      matches: data.matches ?? [],
      _dataSource: data._dataSource,
      _isMockData: data._isMockData ?? false,
      _error: data._error,
      _latencyMs: data._latencyMs,
    };
  } catch (error) {
    console.error("Erro na API _fetchMatchesBatch:", error);
    return {
      matches: [],
      _dataSource: "client-error",
      _isMockData: false,
      _error: {
        kind: "NETWORK_ERROR",
        message: "Erro de conexao com o servidor. Verifique sua internet e tente novamente.",
      },
    };
  }
}

/**
 * Max leagues per batch — aligns with Lambda ThreadPoolExecutor (4 workers)
 * so each request can fill internal parallelism (#119c).
 * FootyStats ~12-19s/league; 3 leagues × 4 workers = single parallel round ≤ 20s
 * within API Gateway 30s limit.
 */
const LEAGUES_PER_BATCH = 3;

/**
 * Max concurrent batch requests — fewer simultaneous Lambda cold starts /
 * less SQLite contention in FootyStats client (#119c).
 */
const MAX_CONCURRENT = 2;

/**
 * Run async tasks with a concurrency limit (semaphore pattern).
 * Returns PromiseSettledResult[] in the same order as input.
 */
async function parallelWithLimit<T>(
  tasks: (() => Promise<T>)[],
  limit: number,
): Promise<PromiseSettledResult<T>[]> {
  const results: PromiseSettledResult<T>[] = new Array(tasks.length);
  let nextIdx = 0;

  async function worker() {
    while (nextIdx < tasks.length) {
      const i = nextIdx++;
      try {
        results[i] = { status: "fulfilled", value: await tasks[i]() };
      } catch (reason) {
        results[i] = { status: "rejected", reason };
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, tasks.length) }, () => worker()),
  );
  return results;
}

/**
 * Fan-out fetch: splits leagues into small parallel batches so each
 * Lambda invocation handles only a few leagues and responds within timeout.
 * Uses concurrency limiting to avoid overwhelming Lambda with cold starts.
 * Merges results client-side into a single MatchesResponse.
 *
 * @param onBatchReady — optional; invoked after each batch completes (#119a progressive loading).
 */
export async function getMatchesByLeague(
  leagues: string,
  date?: string,
  onBatchReady?: (batch: MatchesResponse) => void,
): Promise<MatchesResponse> {
  const leagueIds = leagues.split(",").map((s) => s.trim()).filter(Boolean);

  // Single or few leagues: direct call (no fan-out overhead)
  if (leagueIds.length <= LEAGUES_PER_BATCH) {
    const res = await _fetchMatchesBatch(leagues, date);
    onBatchReady?.(res);
    return res;
  }

  // Split into batches and fetch in parallel (concurrency-limited)
  const batches: string[][] = [];
  for (let i = 0; i < leagueIds.length; i += LEAGUES_PER_BATCH) {
    batches.push(leagueIds.slice(i, i + LEAGUES_PER_BATCH));
  }

  console.log(`[api] Fan-out: ${leagueIds.length} leagues → ${batches.length} batches of ≤${LEAGUES_PER_BATCH} (max ${MAX_CONCURRENT} concurrent)`);
  for (let b = 0; b < batches.length; b++) {
    console.log(`[api]   batch ${b + 1}: ${batches[b].join(", ")}`);
  }

  const results = await parallelWithLimit(
    batches.map((batch, idx) => async () => {
      const res = await _fetchMatchesBatch(batch.join(","), date);
      onBatchReady?.(res);
      const ok = res.matches.length > 0 || res._dataSource === "backend-empty";
      console.log(`[api]   batch ${idx + 1} ${ok ? "OK" : "FAIL"}: ${res.matches.length} matches, src=${res._dataSource}${res._error ? `, err=${res._error.kind}` : ""}`);
      return res;
    }),
    MAX_CONCURRENT,
  );

  // Identify failed batches for retry
  const RETRYABLE_ERRORS = new Set(["TIMEOUT", "HTTP_ERROR", "CONNECTION_ERROR", "NETWORK_ERROR"]);
  const failedBatchIndices: number[] = [];
  for (let i = 0; i < results.length; i++) {
    const r = results[i];
    if (r.status === "rejected") {
      failedBatchIndices.push(i);
    } else if (r.value._error && RETRYABLE_ERRORS.has(r.value._error.kind) && r.value.matches.length === 0) {
      failedBatchIndices.push(i);
    }
  }

  // Retry failed batches individually (1 league at a time for reliability)
  if (failedBatchIndices.length > 0) {
    console.log(`[api] Retrying ${failedBatchIndices.length} failed batch(es) individually...`);
    const retryTasks: (() => Promise<{ batchIdx: number; res: MatchesResponse }>)[] = [];
    for (const batchIdx of failedBatchIndices) {
      for (const leagueId of batches[batchIdx]) {
        retryTasks.push(async () => {
          const res = await _fetchMatchesBatch(leagueId, date);
          console.log(`[api]   retry ${leagueId}: ${res.matches.length} matches, src=${res._dataSource}${res._error ? `, err=${res._error.kind}` : ""}`);
          return { batchIdx, res };
        });
      }
    }
    const retryResults = await parallelWithLimit(retryTasks, MAX_CONCURRENT);

    // Replace failed batch results with individual league results
    for (const batchIdx of failedBatchIndices) {
      const batchRetries = retryResults
        .filter((r) => r.status === "fulfilled" && r.value.batchIdx === batchIdx)
        .map((r) => (r as PromiseSettledResult<{ batchIdx: number; res: MatchesResponse }> & { status: "fulfilled" }).value.res);
      if (batchRetries.length > 0) {
        const merged: MatchesResponse = {
          matches: batchRetries.flatMap((r) => r.matches),
          _dataSource: batchRetries.some((r) => r._dataSource === "backend") ? "backend" : "backend-empty",
          _isMockData: batchRetries.some((r) => r._isMockData),
          _error: batchRetries.find((r) => r._error)?._error,
          _latencyMs: Math.max(...batchRetries.map((r) => r._latencyMs ?? 0)),
        };
        results[batchIdx] = { status: "fulfilled", value: merged };
        onBatchReady?.(merged);
      }
    }
  }

  // Merge results
  const allMatches: unknown[] = [];
  let lastError: MatchesResponse["_error"] | undefined;
  let hasAnySuccess = false;
  let isMockData = false;
  let totalLatency = 0;
  let failedCount = 0;

  for (const r of results) {
    if (r.status === "rejected") {
      lastError = { kind: "NETWORK_ERROR", message: "Falha em uma das requisicoes paralelas." };
      failedCount++;
      continue;
    }
    const res = r.value;
    if (res.matches.length > 0) {
      allMatches.push(...res.matches);
      hasAnySuccess = true;
    }
    if (res._isMockData) isMockData = true;
    if (res._error) {
      lastError = res._error;
      failedCount++;
    }
    if (res._latencyMs) {
      totalLatency = Math.max(totalLatency, res._latencyMs);
    }
    if (res._dataSource === "backend" || res._dataSource === "backend-empty") {
      hasAnySuccess = true;
    }
  }

  console.log(`[api] Fan-out complete: ${allMatches.length} total matches, ${failedCount}/${batches.length} batches failed`);

  // Propagate retryable error kind even on partial success so dashboard
  // can decide to retry. Only suppress error if majority succeeded.
  const shouldSurfaceError = !hasAnySuccess || failedCount > batches.length / 2;

  return {
    matches: allMatches,
    _dataSource: hasAnySuccess ? "backend" : lastError ? "error" : "backend-empty",
    _isMockData: isMockData,
    _error: shouldSurfaceError ? lastError : undefined,
    _latencyMs: totalLatency,
  };
}

export async function getAiMatchAnalysis(matchId: string, homeTeam?: string, awayTeam?: string) {
  try {
    const params = new URLSearchParams();
    if (homeTeam) params.set("home_team", homeTeam);
    if (awayTeam) params.set("away_team", awayTeam);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/ai/match/${encodeURIComponent(matchId)}/analysis${qs}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.summary && data.confidence === 0) return null;
    return data;
  } catch {
    return null;
  }
}

// ===== AUDIT API =====

export interface AuditPickEvaluation {
  mercado: string;
  status_pick: string;
  resultado: string;
  nota: string;
}

export interface AuditValidation {
  probabilities: { status: string; notes: string; brier_score?: number };
  lambdas: { status: string; notes: string; predicted_total?: number; actual_total?: number };
  ev: { status: string; notes: string };
}

export interface AuditCorrection {
  type: string;
  parameter: string;
  current_value: number;
  suggested_value: number;
  reason: string;
  confidence: number;
  impact: string;
}

export interface AuditResult {
  picks_evaluation?: AuditPickEvaluation[];
  validation: AuditValidation;
  ai_analysis_accuracy?: string;
  accuracy_summary?: string;
  independent_prediction?: { total_goals_estimate: number; reasoning: string };
  corrections?: AuditCorrection[];
  biases_detected?: string[];
  suggestions?: string[];
  audit_confidence: number;
  audit_type?: string;
  timestamp?: string;
  match?: string;
}

export type AuditResponse =
  | { ok: true; audit: AuditResult }
  | { ok: false; message: string };

export async function postMatchAudit(
  matchId: string,
  predictions?: Array<{ mercado: string; status: string; prob_min: number; prob_max: number; odd_minima: number }>,
  aiSummary?: { summary: string; key_points: string[]; recommendation: string; confidence: number },
  homeTeam?: string,
  awayTeam?: string,
): Promise<AuditResponse> {
  try {
    const body: Record<string, unknown> = {};
    if (predictions) body.predictions = predictions;
    if (aiSummary) body.ai_summary = aiSummary;
    const params = new URLSearchParams();
    if (homeTeam) params.set("home_team", homeTeam);
    if (awayTeam) params.set("away_team", awayTeam);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/ai/match/${encodeURIComponent(matchId)}/audit${qs}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.audit) return { ok: true, audit: data.audit };
    return { ok: false, message: data.message || "Servico de auditoria indisponivel." };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : "Erro de conexao." };
  }
}

export async function applyAuditCorrection(
  matchId: string,
  correction: {
    correction_type: string;
    parameter_name: string;
    old_value: number;
    new_value: number;
    reason: string;
    audit_confidence: number;
  },
): Promise<{ status: string; message: string } | null> {
  try {
    const res = await fetch(`/api/ai/match/${encodeURIComponent(matchId)}/audit/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(correction),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ===== BATCH AUDIT API =====

export interface BatchAuditPickEval {
  mercado: string;
  status_pick: string;
  resultado: "ACERTOU" | "ERROU";
  marketReferenceSignal?: "SAFE" | "NEUTRO" | "RESTRITO";
  wasCappedByMarketSignal?: boolean;
}

export interface BatchAuditMatchResult {
  match_id: string;
  home_team: string;
  away_team: string;
  league: string;
  score: string;
  picks: BatchAuditPickEval[];
  picks_correct: number;
  picks_total: number;
  brier_score?: number;
}

export interface BatchAuditMarketAccuracy {
  market: string;
  correct: number;
  total: number;
  accuracy_pct: number;
}

export interface BatchAuditMarketBias {
  market: string;
  bias_type: string;
  description: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
}

export interface ModelUpdateRecommendation {
  needs_update: boolean;
  urgency: "BAIXA" | "MEDIA" | "ALTA" | "CRITICA";
  reasons: string[];
  recommended_actions: string[];
  next_retrain_suggestion: string;
}

export interface BatchAuditModelEvaluation {
  overall_assessment: "SATISFATORIO" | "NECESSITA_AJUSTE" | "CRITICO" | "UNKNOWN";
  overall_notes?: string;
  lambda_evaluation: {
    status: string;
    direction?: string;
    avg_error?: number;
    notes: string;
  };
  threshold_evaluation: {
    safe_status: string;
    neutro_status: string;
    notes: string;
  };
  market_biases?: BatchAuditMarketBias[];
  ai_self_evaluation?: {
    alignment_with_results: string;
    factors_to_emphasize: string[];
    factors_to_reduce: string[];
    notes: string;
  };
  recommended_corrections?: BatchAuditCorrection[];
  blocked_corrections?: Array<{ original: string; rule: string }>;  // #099b
  model_update_recommendation?: ModelUpdateRecommendation;
  audit_confidence: number;
  timestamp?: string;
}

export interface BatchAuditCorrection {
  type: string;
  parameter: string;
  current_value: number;
  suggested_value: number;
  reason: string;
  confidence: number;
  impact: "LOW" | "MEDIUM" | "HIGH";
}

export interface LeagueAuditStats {
  league: string;
  matches_audited: number;
  picks_correct: number;
  picks_total: number;
  accuracy_pct: number;
  brier_score?: number;
}

export interface MarketReferenceStats {
  capped_by_market_reference_count: number;
  safe_to_neutro_by_signal_count: number;
  safe_blocked_by_restrito_count: number;
}

export interface BatchAuditResult {
  status: string;
  total_matches: number;
  finished_matches: number;
  audited_matches: number;
  overall_accuracy: number;
  safe_accuracy: number | null;  // #162: null when 0/0
  neutro_accuracy: number | null;  // #162: null when 0/0
  safe_correct: number;
  safe_total: number;
  neutro_correct: number;
  neutro_total: number;
  avg_brier_score: number;
  avg_lambda_error: number;
  market_accuracy: BatchAuditMarketAccuracy[];
  match_results: BatchAuditMatchResult[];
  model_evaluation: BatchAuditModelEvaluation | null;
  league_accuracy?: LeagueAuditStats[];
  model_update_recommendation?: ModelUpdateRecommendation;
  mistral_recommendation?: ModelUpdateRecommendation;
  combinadas?: AuditCombinadas;
  market_reference_stats?: MarketReferenceStats;
  message?: string;
}

export interface AuditCombinadaLeg {
  jogo: string;
  homeTeam: string;
  awayTeam: string;
  leagueId: string;
  leagueName: string;
  datetime: string;
  mercado: string;
  status: string;
  prob_min: number;
  prob_max: number;
  odd_minima: number;
}

export interface AuditCombinada {
  tipo: "intra" | "inter";
  leg1: AuditCombinadaLeg;
  leg2: AuditCombinadaLeg;
  odd_combinada: number;
  prob_combinada_min: number;
  prob_combinada_max: number;
  status_combinada: "SAFE" | "MISTA" | "NEUTRO";
  resultado?: "ACERTOU" | "ERROU" | "PENDENTE";
}

export interface AuditCombinadas {
  intra: AuditCombinada[];
  inter: AuditCombinada[];
  total_intra: number;
  total_inter: number;
  total_jogos: number;
  dupla_intra_correct?: number;
  dupla_intra_total?: number;
  dupla_intra_accuracy?: number;
  dupla_inter_correct?: number;
  dupla_inter_total?: number;
  dupla_inter_accuracy?: number;
  dupla_overall_accuracy?: number;
}

/**
 * Fan-out batch audit: one request per league in parallel.
 * Each single-league request completes within the 29-second API Gateway limit.
 * Results are merged client-side into a unified BatchAuditResult.
 */
export async function postBatchAudit(date?: string, leagues?: string[]): Promise<BatchAuditResult | null> {
  // No leagues or single league: direct call
  if (!leagues || leagues.length <= 1) {
    return _postBatchAuditSingle(date, leagues);
  }

  // Fan out: one request per league in parallel
  const results = await Promise.allSettled(
    leagues.map((league) => _postBatchAuditSingle(date, [league]))
  );

  return _mergeBatchAuditResults(results);
}

async function _postBatchAuditSingle(date?: string, leagues?: string[]): Promise<BatchAuditResult | null> {
  try {
    const body: Record<string, unknown> = {};
    if (date) body.date = date;
    if (leagues && leagues.length > 0) body.leagues = leagues;
    const res = await fetch("/api/ai/batch-audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json();
    if (!res.ok) {
      return { ...data, status: "error" } as BatchAuditResult;
    }
    return data;
  } catch {
    return null;
  }
}

function _mergeBatchAuditResults(
  results: PromiseSettledResult<BatchAuditResult | null>[]
): BatchAuditResult | null {
  const successful = results
    .filter(
      (r): r is PromiseFulfilledResult<BatchAuditResult> =>
        r.status === "fulfilled" && r.value !== null && r.value.status !== "error"
    )
    .map((r) => r.value);

  if (successful.length === 0) {
    // All failed — return first error for display
    const firstError = results.find(
      (r): r is PromiseFulfilledResult<BatchAuditResult> =>
        r.status === "fulfilled" && r.value !== null
    );
    return firstError?.value ?? null;
  }

  // Aggregate numeric fields
  const safeCorrect = successful.reduce((s, r) => s + (r.safe_correct || 0), 0);
  const safeTotal = successful.reduce((s, r) => s + (r.safe_total || 0), 0);
  const neutroCorrect = successful.reduce((s, r) => s + (r.neutro_correct || 0), 0);
  const neutroTotal = successful.reduce((s, r) => s + (r.neutro_total || 0), 0);
  const totalAudited = successful.reduce((s, r) => s + (r.audited_matches || 0), 0);

  // Merge market accuracy
  const marketMap = new Map<string, { correct: number; total: number }>();
  for (const r of successful) {
    for (const ma of r.market_accuracy || []) {
      const existing = marketMap.get(ma.market) || { correct: 0, total: 0 };
      existing.correct += ma.correct;
      existing.total += ma.total;
      marketMap.set(ma.market, existing);
    }
  }

  // Pick model_evaluation from result with most audited matches
  const withEval = successful.filter((r) => r.model_evaluation && r.audited_matches > 0);
  const bestEval =
    withEval.length > 0
      ? withEval.reduce((best, r) => (r.audited_matches > best.audited_matches ? r : best))
          .model_evaluation
      : null;

  const merged: BatchAuditResult = {
    status: "success",
    total_matches: successful.reduce((s, r) => s + (r.total_matches || 0), 0),
    finished_matches: successful.reduce((s, r) => s + (r.finished_matches || 0), 0),
    audited_matches: totalAudited,
    safe_correct: safeCorrect,
    safe_total: safeTotal,
    neutro_correct: neutroCorrect,
    neutro_total: neutroTotal,
    overall_accuracy:
      safeTotal + neutroTotal > 0
        ? Math.round(((safeCorrect + neutroCorrect) / (safeTotal + neutroTotal)) * 1000) / 10
        : 0,
    safe_accuracy: safeTotal > 0 ? Math.round((safeCorrect / safeTotal) * 1000) / 10 : null,  // #162
    neutro_accuracy: neutroTotal > 0 ? Math.round((neutroCorrect / neutroTotal) * 1000) / 10 : null,  // #162
    avg_brier_score:
      totalAudited > 0
        ? successful.reduce((s, r) => s + (r.avg_brier_score || 0) * (r.audited_matches || 0), 0) /
          totalAudited
        : 0,
    avg_lambda_error:
      totalAudited > 0
        ? successful.reduce(
            (s, r) => s + (r.avg_lambda_error || 0) * (r.audited_matches || 0),
            0
          ) / totalAudited
        : 0,
    market_accuracy: Array.from(marketMap.entries()).map(([market, data]) => ({
      market,
      correct: data.correct,
      total: data.total,
      accuracy_pct: data.total > 0 ? Math.round((data.correct / data.total) * 1000) / 10 : 0,
    })),
    match_results: successful.flatMap((r) => r.match_results || []),
    model_evaluation: bestEval,
  };

  return merged;
}

export async function applyBatchCorrections(
  corrections: BatchAuditCorrection[],
): Promise<{ status: string; applied: number; errors: number } | null> {
  try {
    const res = await fetch("/api/ai/batch-audit/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrections }),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ===== AUDIT STATUS API =====

export interface AuditStatusCorrection {
  match_id: string;
  league: string;
  type: string;
  parameter: string;
  old_value: number;
  new_value: number;
  suggested_by: string;
  applied_by: string;
  confidence: number;
  reason: string;
  status: string;
  created_at: string;
}

export interface AuditStatusResult {
  match_id: string;
  league: string;
  data: Record<string, unknown>;
  timestamp: string;
  user: string;
  version: string;
}

export interface AuditStatusResponse {
  version: string;
  last_batch_audit: AuditStatusResult | null;
  recent_audits: AuditStatusResult[];
  recent_corrections: AuditStatusCorrection[];
  active_corrections: Record<string, { value: number; type: string; reason: string }>;
  summary: {
    total_audits: number;
    total_corrections_applied: number;
    has_recent_activity: boolean;
  };
}

export async function getAuditStatus(days: number = 3): Promise<AuditStatusResponse | null> {
  try {
    const res = await fetch(`/api/audit/status?days=${days}`, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
