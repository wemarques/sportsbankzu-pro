"use client";

import { useState, useCallback } from "react";
import type { BatchAuditResult, LeagueAuditStats } from "@/lib/api";

// ===== TYPES =====
interface AuditReportData {
  auditDate: string;
  totalMatches: number;
  totalLeagues: number;
  modelSeverity: "ALTA" | "MEDIA" | "BAIXA";
  mistralSeverity?: "ALTA" | "MEDIA" | "BAIXA";
  brierScore: number;
  safeAccuracy: number | null;  // #162: null when 0/0
  lambdaError: number;
  leagues: {
    name: string;
    flag: string;
    matches: number;
    safeHits: number;
    safeTotal: number;
    brierScore: number;
  }[];
  marketResults: {
    market: string;
    total: number;
    correct: number;
  }[];
  diagnostics: { text: string; severity: "critical" | "warning" | "info" }[];
  mistralDiagnostics: { text: string; severity: "critical" | "warning" | "info" }[];
  modelActions: string[];
  mistralActions: string[];
  retrainDeadline?: string;
}

interface Props {
  data?: BatchAuditResult;
}

// ===== LEAGUE FLAG MAP =====
const LEAGUE_FLAGS: Record<string, string> = {
  "premier league": "\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67\uDB40\uDC7F",
  "la liga": "\uD83C\uDDEA\uD83C\uDDF8",
  "serie a": "\uD83C\uDDEE\uD83C\uDDF9",
  "bundesliga": "\uD83C\uDDE9\uD83C\uDDEA",
  "ligue 1": "\uD83C\uDDEB\uD83C\uDDF7",
  "eredivisie": "\uD83C\uDDF3\uD83C\uDDF1",
  "primeira liga": "\uD83C\uDDF5\uD83C\uDDF9",
  "super lig": "\uD83C\uDDF9\uD83C\uDDF7",
  "brasileirao": "\uD83C\uDDE7\uD83C\uDDF7",
  "serie b": "\uD83C\uDDEE\uD83C\uDDF9",
  default: "\u26BD",
};

function getFlag(leagueName: string): string {
  const lower = leagueName.toLowerCase();
  for (const [key, flag] of Object.entries(LEAGUE_FLAGS)) {
    if (key !== "default" && lower.includes(key)) return flag;
  }
  return LEAGUE_FLAGS.default;
}

// ===== CONVERT BatchAuditResult TO AuditReportData =====
function fromBatchAudit(r: BatchAuditResult): AuditReportData {
  const now = new Date();
  const dateStr = now.toLocaleDateString("pt-BR");

  // Determine severities
  // #168/#174: r.safe_accuracy is number|null per #162 (null when 0/0).
  // Skip safe_accuracy contribution when null — never penalize severity for absence of SAFE picks.
  const safeBelow40 = r.safe_accuracy != null && r.safe_accuracy < 40;
  const safeBelow65 = r.safe_accuracy != null && r.safe_accuracy < 65;
  const modelSev: "ALTA" | "MEDIA" | "BAIXA" =
    r.avg_brier_score > 0.30 || safeBelow40 ? "ALTA" :
    r.avg_brier_score > 0.22 || safeBelow65 ? "MEDIA" : "BAIXA";

  const eval_ = r.model_evaluation;
  const mistralAssessment = eval_?.overall_assessment ?? "";
  const mistralSev: "ALTA" | "MEDIA" | "BAIXA" =
    mistralAssessment === "CRITICO" ? "ALTA" :
    mistralAssessment === "NECESSITA_AJUSTE" ? "MEDIA" : "BAIXA";

  // League breakdown (#077: use per-league Brier, rename SAFE→Acurácia)
  const leagues = (r.league_accuracy ?? []).map((lg: LeagueAuditStats) => ({
    name: lg.league,
    flag: getFlag(lg.league),
    matches: lg.matches_audited,
    safeHits: lg.picks_correct,
    safeTotal: lg.picks_total,
    brierScore: lg.brier_score ?? r.avg_brier_score,
  }));

  // Market results
  const marketResults = (r.market_accuracy ?? []).map((m) => ({
    market: m.market,
    total: m.total,
    correct: m.correct,
  }));

  // Diagnostics from model evaluation
  const diagnostics: AuditReportData["diagnostics"] = [];
  if (r.avg_brier_score > 0.22) {
    diagnostics.push({
      text: `Brier Score acima do ideal (${r.avg_brier_score.toFixed(4)}) — probabilidades precisam de ajuste`,
      severity: r.avg_brier_score > 0.30 ? "critical" : "warning",
    });
  }
  // #174: guard null per #162 — was crashing AuditReportCard with TypeError
  // "Cannot read properties of null (reading 'toFixed')" when SAFE = 0/0.
  if (r.safe_accuracy != null && r.safe_accuracy < 65) {
    diagnostics.push({
      text: `Picks SAFE com acurácia baixa (${r.safe_accuracy.toFixed(1)}%) — thresholds SAFE precisam recalibração`,
      severity: r.safe_accuracy < 40 ? "critical" : "warning",
    });
  }

  const mistralDiagnostics: AuditReportData["mistralDiagnostics"] = [];
  if (r.avg_lambda_error > 0.5) {
    mistralDiagnostics.push({
      text: `Erro médio de lambda (${r.avg_lambda_error.toFixed(2)} gols) acima do limite (>0.5)`,
      severity: "critical",
    });
  }
  const biases = eval_?.market_biases ?? [];
  for (const b of biases) {
    mistralDiagnostics.push({
      text: `${b.market}: ${b.description}`,
      severity: b.severity === "HIGH" ? "critical" : b.severity === "MEDIUM" ? "warning" : "info",
    });
  }

  // Actions
  const modelActions: string[] = [];
  // #174: guard null per #162 — only suggest threshold tuning when SAFE has data and is underperforming
  if (r.safe_accuracy != null && r.safe_accuracy < 65) modelActions.push("Ajustar thresholds de probabilidade");
  if (r.avg_brier_score > 0.22) modelActions.push("Recalibrar probabilidades do modelo");  // #178: target unificado em 0.22

  const mistralActions: string[] = [];
  const corrections = eval_?.recommended_corrections ?? [];
  for (const c of corrections) {
    mistralActions.push(`${c.parameter}: ${c.current_value} → ${c.suggested_value} (${c.reason})`);
  }

  const retrain = r.model_update_recommendation ?? r.mistral_recommendation;
  const retrainDeadline = retrain?.next_retrain_suggestion ?? undefined;

  return {
    auditDate: dateStr,
    totalMatches: r.audited_matches,
    totalLeagues: leagues.length,
    modelSeverity: modelSev,
    mistralSeverity: mistralSev,
    brierScore: r.avg_brier_score,
    safeAccuracy: r.safe_accuracy,
    lambdaError: r.avg_lambda_error,
    leagues,
    marketResults,
    diagnostics,
    mistralDiagnostics,
    modelActions,
    mistralActions,
    retrainDeadline,
  };
}

// ===== HELPERS =====
function sevColor(s: string) {
  if (s === "ALTA") return "#ff4d4d";
  if (s === "MEDIA") return "#ffa726";
  return "#00ff88";
}
function sevBg(s: string) {
  if (s === "ALTA") return "rgba(255,77,77,0.12)";
  if (s === "MEDIA") return "rgba(255,167,38,0.12)";
  return "rgba(0,255,136,0.12)";
}
function pctColor(pct: number) {
  if (pct >= 60) return "#00ff88";
  if (pct >= 40) return "#ffa726";
  return "#ff4d4d";
}
function brierColor(b: number) {
  if (b <= 0.22) return "#00ff88";
  if (b <= 0.30) return "#ffa726";
  return "#ff4d4d";
}

function formatReport(d: AuditReportData) {
  const div = "\u2500".repeat(56);
  const l: string[] = [];
  l.push("\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557");
  l.push("\u2551        AUDITORIA DA RODADA \u2014 SportsBank Pro           \u2551");
  l.push("\u2551  " + d.auditDate + " \u2022 " + d.totalMatches + " jogos \u2022 " + d.totalLeagues + " ligas analisadas");
  l.push("\u255A\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255D");
  l.push("");
  l.push("Modelo: " + d.modelSeverity);
  if (d.mistralSeverity) {
    l.push("Avaliacao Mistral AI: " + d.mistralSeverity);
    if (d.modelSeverity !== d.mistralSeverity)
      l.push("\u26A0 Divergência: Modelo=" + d.modelSeverity + ", Mistral=" + d.mistralSeverity);
  }
  l.push("");
  l.push(div);
  l.push("METRICAS GLOBAIS");
  l.push(div);
  l.push("Brier Score: " + d.brierScore.toFixed(4) + " (ideal < 0.22)");
  l.push("SAFE Acuracia: " + (d.safeAccuracy != null ? d.safeAccuracy.toFixed(1) + "%" : "N/A (circuit breaker)") + " (meta > 65%)");
  if (d.lambdaError != null) l.push("Lambda Erro Medio: " + d.lambdaError.toFixed(2) + " gols (limite < 0.5)");
  l.push("");
  l.push(div);
  l.push("LIGAS ANALISADAS");
  l.push(div);
  d.leagues.forEach((lg) => {
    const safePct = lg.safeTotal > 0 ? ((lg.safeHits / lg.safeTotal) * 100).toFixed(0) : "N/A";
    l.push("  " + lg.flag + " " + lg.name);
    l.push("    Jogos: " + lg.matches + " | Brier: " + lg.brierScore.toFixed(4) + " | Acuracia: " + safePct + "% (" + lg.safeHits + "/" + lg.safeTotal + ")");
  });
  l.push("");
  if (d.marketResults.length > 0) {
    l.push(div);
    l.push("RESULTADOS POR MERCADO (GLOBAL)");
    l.push(div);
    d.marketResults.forEach((m) => {
      const p = m.total > 0 ? ((m.correct / m.total) * 100).toFixed(1) : "0.0";
      l.push("  " + m.market + ": " + p + "% (" + m.correct + "/" + m.total + ")");
    });
    l.push("");
  }
  l.push(div);
  l.push("DIAGNOSTICO");
  l.push(div);
  d.diagnostics.forEach((x) => l.push("\u2022 " + x.text));
  if (d.mistralDiagnostics.length > 0) {
    l.push("");
    l.push("Diagnostico Mistral:");
    d.mistralDiagnostics.forEach((x) => l.push("\u2022 " + x.text));
  }
  l.push("");
  l.push(div);
  l.push("ACOES RECOMENDADAS");
  l.push(div);
  if (d.modelActions.length > 0) {
    l.push("Modelo:");
    d.modelActions.forEach((a) => l.push("  \u2192 " + a));
  }
  if (d.mistralActions.length > 0) {
    l.push("Mistral:");
    d.mistralActions.forEach((a) => l.push("  \u2192 " + a));
  }
  l.push("");
  if (d.retrainDeadline) l.push("Proximo re-treino: " + d.retrainDeadline);
  l.push(div);
  l.push("Gerado por SportsBank Pro \u2022 " + new Date().toLocaleString("pt-BR"));
  return l.join("\n");
}

// ===== SUB-COMPONENTS =====
function Section({
  title,
  open,
  onToggle,
  children,
  count,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  count?: number | null;
}) {
  return (
    <div style={{ margin: "0 20px 12px", background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 10, overflow: "hidden" }}>
      <button
        onClick={onToggle}
        style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "transparent", border: "none", color: "#e0e0e0", cursor: "pointer", fontSize: 14, fontWeight: 600, textAlign: "left" }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {title}
          {count != null && (
            <span style={{ fontSize: 11, color: "#888", background: "#2a2a2a", padding: "2px 8px", borderRadius: 10 }}>{count}</span>
          )}
        </span>
        <span style={{ fontSize: 10, color: "#666" }}>{open ? "\u25B2" : "\u25BC"}</span>
      </button>
      {open && <div style={{ padding: "0 16px 14px" }}>{children}</div>}
    </div>
  );
}

function Diag({ text, sev }: { text: string; sev: string }) {
  const c = sev === "critical" ? "#ff4d4d" : sev === "warning" ? "#ffa726" : "#00ff88";
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0", fontSize: 13, lineHeight: 1.5 }}>
      <span style={{ fontSize: 8, marginTop: 5, color: c }}>{"\u25CF"}</span>
      <span style={{ color: "#ccc" }}>{text}</span>
    </div>
  );
}

// ===== MAIN COMPONENT =====
export default function AuditReportCard({ data }: Props) {
  const d: AuditReportData | null = data ? fromBatchAudit(data) : null;

  const [copied, setCopied] = useState(false);
  const [sections, setSections] = useState({ leagues: true, markets: true, diag: true, actions: true });
  const [showPreview, setShowPreview] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!d) return;
    const text = formatReport(d);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }, [d]);

  const toggle = (k: keyof typeof sections) => {
    setSections((p) => ({ ...p, [k]: !p[k] }));
  };

  if (!d) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#666", fontSize: 14 }}>
        Nenhuma auditoria disponivel. Execute uma auditoria batch primeiro.
      </div>
    );
  }

  const bC = brierColor(d.brierScore);
  const bL = d.brierScore <= 0.22 ? "OK" : d.brierScore <= 0.30 ? "ATENCAO" : "CRITICO";
  const sC = d.safeAccuracy == null ? "#888" : d.safeAccuracy >= 65 ? "#00ff88" : d.safeAccuracy >= 40 ? "#ffa726" : "#ff4d4d";
  const sL = d.safeAccuracy == null ? "N/A" : d.safeAccuracy >= 65 ? "OK" : d.safeAccuracy >= 40 ? "ATENCAO" : "CRITICO";
  const lC = d.lambdaError > 0.5 ? "#ff4d4d" : d.lambdaError > 0.3 ? "#ffa726" : "#00ff88";
  const lL = d.lambdaError > 0.5 ? "ALTO" : d.lambdaError > 0.3 ? "ATENCAO" : "OK";

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <div style={{ background: "#141414", border: "1px solid #2a2a2a", borderRadius: 12, overflow: "hidden", color: "#e0e0e0" }}>
        {/* HEADER */}
        <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid #2a2a2a", background: "linear-gradient(180deg, #1e1e1e 0%, #141414 100%)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 4 }}>
                Auditoria da Rodada
              </div>
              <div style={{ fontSize: 13, color: "#888" }}>
                {d.auditDate} &bull; <span style={{ color: "#ccc" }}>{d.totalMatches} jogos</span> em{" "}
                <span style={{ color: "#ccc" }}>{d.totalLeagues} ligas</span>
              </div>
            </div>
            <button
              onClick={handleCopy}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "10px 16px",
                background: copied ? "rgba(0,255,136,0.2)" : "rgba(0,255,136,0.08)",
                border: "1px solid " + (copied ? "#00ff88" : "rgba(0,255,136,0.3)"),
                borderRadius: 8,
                color: "#00ff88",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s",
                boxShadow: copied ? "0 0 16px rgba(0,255,136,0.25)" : "none",
              }}
            >
              {copied ? (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>Copiado!</span>
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                  <span>Copiar Relatório</span>
                </>
              )}
            </button>
          </div>

          {/* LEAGUE PILLS */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {d.leagues.map((lg, i) => (
              <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, color: "#aaa", background: "#222", padding: "4px 10px", borderRadius: 20, border: "1px solid #333" }}>
                {lg.flag} {lg.name.split(" - ")[1] || lg.name}
                <span style={{ color: "#666", marginLeft: 2 }}>({lg.matches})</span>
              </span>
            ))}
          </div>
        </div>

        {/* SEVERITY BADGES */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, padding: "10px 20px", border: "1px solid " + sevColor(d.modelSeverity), background: sevBg(d.modelSeverity), borderRadius: 8, minWidth: 100 }}>
            <span style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: 0.5 }}>Modelo</span>
            <span style={{ fontSize: 18, fontWeight: 800, color: sevColor(d.modelSeverity) }}>{d.modelSeverity}</span>
          </div>
          {d.mistralSeverity && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, padding: "10px 20px", border: "1px solid " + sevColor(d.mistralSeverity), background: sevBg(d.mistralSeverity), borderRadius: 8, minWidth: 100 }}>
              <span style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: 0.5 }}>Mistral AI</span>
              <span style={{ fontSize: 18, fontWeight: 800, color: sevColor(d.mistralSeverity) }}>{d.mistralSeverity}</span>
            </div>
          )}
          {d.mistralSeverity && d.modelSeverity !== d.mistralSeverity && (
            <div style={{ fontSize: 12, color: "#ffa726", background: "rgba(255,167,38,0.1)", padding: "6px 12px", borderRadius: 6, border: "1px solid rgba(255,167,38,0.2)" }}>
              Divergencia detectada
            </div>
          )}
        </div>

        {/* GLOBAL METRICS */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, padding: "0 20px 16px" }}>
          {[
            { label: "Brier Score", val: d.brierScore.toFixed(4), color: bC, badge: bL, pct: Math.min((d.brierScore / 0.4) * 100, 100), target: "Ideal: < 0.22" },
            { label: "SAFE Acuracia", val: d.safeAccuracy != null ? d.safeAccuracy.toFixed(1) + "%" : "N/A", color: sC, badge: sL, pct: d.safeAccuracy ?? 0, target: "Meta: > 65%" },
            { label: "Lambda Erro", val: d.lambdaError.toFixed(2), color: lC, badge: lL, pct: Math.min((d.lambdaError / 1.5) * 100, 100), target: "Limite: < 0.5 gols" },
          ].map((m, i) => (
            <div key={i} style={{ background: "#1a1a1a", border: "1px solid #2a2a2a", borderRadius: 10, padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: "#888", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.3 }}>{m.label}</span>
                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, border: "1px solid " + m.color, color: m.color, textTransform: "uppercase" }}>{m.badge}</span>
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, fontFamily: "'Courier New',monospace", color: m.color, marginBottom: 8 }}>{m.val}</div>
              <div style={{ width: "100%", height: 4, background: "#2a2a2a", borderRadius: 2, overflow: "hidden", marginBottom: 6 }}>
                <div style={{ height: "100%", borderRadius: 2, width: m.pct + "%", background: m.color, boxShadow: "0 0 8px " + m.color + "40", transition: "width 0.6s" }} />
              </div>
              <div style={{ fontSize: 11, color: "#666" }}>{m.target}</div>
            </div>
          ))}
        </div>

        {/* LEAGUES BREAKDOWN */}
        <Section title="Ligas Analisadas" open={sections.leagues} onToggle={() => toggle("leagues")} count={d.totalLeagues}>
          {d.leagues.map((lg, i) => {
            const safePct = lg.safeTotal > 0 ? (lg.safeHits / lg.safeTotal) * 100 : 0;
            const lgBrierC = brierColor(lg.brierScore);
            const lgSafeC = pctColor(safePct);
            return (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 12,
                  padding: "12px 0",
                  borderBottom: i < d.leagues.length - 1 ? "1px solid #222" : "none",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#e0e0e0", marginBottom: 6 }}>
                    <span style={{ fontSize: 18 }}>{lg.flag}</span>
                    {lg.name}
                    <span style={{ fontSize: 11, color: "#666", fontWeight: 400 }}>({lg.matches} jogos)</span>
                  </div>
                  <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                    <div style={{ fontSize: 12, color: "#888" }}>
                      Brier: <span style={{ color: lgBrierC, fontWeight: 700, fontFamily: "'Courier New',monospace" }}>{lg.brierScore.toFixed(4)}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "#888" }}>
                      Acur\u00e1cia:{" "}
                      <span style={{ color: lg.safeTotal > 0 ? lgSafeC : "#555", fontWeight: 700 }}>
                        {lg.safeTotal > 0 ? safePct.toFixed(0) + "%" : "N/A"}
                      </span>
                      <span style={{ color: "#555", marginLeft: 4 }}>
                        ({lg.safeHits}/{lg.safeTotal})
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <div style={{ width: 60, height: 4, background: "#2a2a2a", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, width: Math.min((1 - lg.brierScore / 0.4) * 100, 100) + "%", background: lgBrierC }} />
                  </div>
                </div>
              </div>
            );
          })}
        </Section>

        {/* MARKET RESULTS */}
        <Section title="Resultados por Mercado" open={sections.markets} onToggle={() => toggle("markets")} count={d.marketResults.length}>
          {d.marketResults.map((m, i) => {
            const pct = m.total > 0 ? (m.correct / m.total) * 100 : 0;
            const c = pctColor(pct);
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: i < d.marketResults.length - 1 ? "1px solid #222" : "none" }}>
                <div style={{ flex: 1, fontSize: 13, color: "#ccc" }}>{m.market}</div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13, minWidth: 100, justifyContent: "flex-end" }}>
                  <span style={{ color: c, fontWeight: 700 }}>{pct.toFixed(1)}%</span>
                  <span style={{ fontSize: 11, color: "#666" }}>
                    ({m.correct}/{m.total})
                  </span>
                </div>
                <div style={{ width: 80, height: 4, background: "#2a2a2a", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 2, width: pct + "%", background: c }} />
                </div>
              </div>
            );
          })}
        </Section>

        {/* DIAGNOSTICS */}
        <Section title="Diagnostico" open={sections.diag} onToggle={() => toggle("diag")}>
          {d.diagnostics.map((x, i) => (
            <Diag key={i} text={x.text} sev={x.severity} />
          ))}
          {d.mistralDiagnostics.length > 0 && (
            <>
              <div style={{ margin: "12px 0 8px", paddingTop: 10, borderTop: "1px solid #2a2a2a" }}>
                <span style={{ fontSize: 12, color: "#bb86fc", fontWeight: 600 }}>Diagnostico Mistral</span>
              </div>
              {d.mistralDiagnostics.map((x, i) => (
                <Diag key={"m" + i} text={x.text} sev={x.severity} />
              ))}
            </>
          )}
        </Section>

        {/* ACTIONS */}
        <Section title="Ações Recomendadas" open={sections.actions} onToggle={() => toggle("actions")}>
          {d.modelActions.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: "#00ff88", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Modelo</div>
              {d.modelActions.map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, padding: "5px 0", fontSize: 13, color: "#ccc", lineHeight: 1.5 }}>
                  <span style={{ color: "#00ff88", fontWeight: 700 }}>{"\u2192"}</span>
                  <span>{a}</span>
                </div>
              ))}
            </div>
          )}
          {d.mistralActions.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: "#bb86fc", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Mistral AI</div>
              {d.mistralActions.map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, padding: "5px 0", fontSize: 13, color: "#ccc", lineHeight: 1.5 }}>
                  <span style={{ color: "#bb86fc", fontWeight: 700 }}>{"\u2192"}</span>
                  <span>{a}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* FOOTER */}
        <div style={{ padding: "14px 20px", borderTop: "1px solid #2a2a2a", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          {d.retrainDeadline && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#ffa726", background: "rgba(255,167,38,0.08)", padding: "6px 12px", borderRadius: 6, border: "1px solid rgba(255,167,38,0.15)" }}>
              {d.retrainDeadline}
            </div>
          )}
          <button
            onClick={() => setShowPreview(!showPreview)}
            style={{
              background: "transparent",
              border: "1px solid #333",
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 11,
              color: "#666",
              cursor: "pointer",
            }}
          >
            {showPreview ? "Ocultar preview" : "Preview texto"}
          </button>
          <div style={{ fontSize: 11, color: "#555" }}>SportsBank Pro</div>
        </div>

        {/* CLIPBOARD PREVIEW */}
        {showPreview && (
          <div style={{ padding: "0 20px 16px" }}>
            <div style={{ background: "#0d0d0d", border: "1px solid #2a2a2a", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 11, color: "#555", marginBottom: 6, fontWeight: 600 }}>Texto que sera copiado:</div>
              <pre style={{ fontSize: 11, color: "#555", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "'Courier New',monospace", margin: 0, maxHeight: 240, overflowY: "auto" }}>
                {formatReport(d)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
