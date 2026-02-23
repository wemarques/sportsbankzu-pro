/**
 * API client — todas as chamadas passam pelas rotas proxy do Next.js (/api/*)
 * para usar PY_BACKEND_URL (server-side) e evitar CORS.
 */

export async function getMatchesByLeague(leagues: string, date?: string) {
  try {
    const params = new URLSearchParams({ leagues });
    if (date) params.append("date", date);
    const res = await fetch(`/api/matches/fetch?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.matches && data.matches.length > 0) return data;
    // Server proxy retornou vazio — fallback client-side
    const { getMockMatches } = await import("./mockMatches");
    return { matches: getMockMatches(leagues) };
  } catch (error) {
    console.error("Erro na API getMatchesByLeague:", error);
    const { getMockMatches } = await import("./mockMatches");
    return { matches: getMockMatches(leagues) };
  }
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

export interface BatchAuditResult {
  status: string;
  total_matches: number;
  finished_matches: number;
  audited_matches: number;
  overall_accuracy: number;
  safe_accuracy: number;
  neutro_accuracy: number;
  safe_correct: number;
  safe_total: number;
  neutro_correct: number;
  neutro_total: number;
  avg_brier_score: number;
  avg_lambda_error: number;
  market_accuracy: BatchAuditMarketAccuracy[];
  match_results: BatchAuditMatchResult[];
  model_evaluation: BatchAuditModelEvaluation | null;
  message?: string;
}

export async function postBatchAudit(date?: string): Promise<BatchAuditResult | null> {
  try {
    const body: Record<string, string> = {};
    if (date) body.date = date;
    const res = await fetch("/api/ai/batch-audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
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
