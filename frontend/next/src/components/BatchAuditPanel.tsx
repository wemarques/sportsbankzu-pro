"use client";

import { useState } from "react";
import {
  X,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  TrendingUp,
  BarChart3,
  Brain,
  Wrench,
  AlertTriangle,
  Layers,
  Link2,
  FileText,
} from "lucide-react";
import AuditReportCard from "./AuditReportCard";
import type {
  BatchAuditResult,
  BatchAuditCorrection,
  BatchAuditMatchResult,
  ModelUpdateRecommendation,
  LeagueAuditStats,
  AuditCombinada,
  AuditCombinadaLeg,
  AuditCombinadas,
} from "@/lib/api";

interface BatchAuditPanelProps {
  result: BatchAuditResult;
  onClose: () => void;
  onApplyCorrections: (corrections: BatchAuditCorrection[]) => Promise<void>;
}

function AccuracyColor({ pct }: { pct: number }) {
  if (pct >= 70) return <span className="mdc-batch-audit__pct mdc-batch-audit__pct--green">{pct.toFixed(1)}%</span>;
  if (pct >= 50) return <span className="mdc-batch-audit__pct mdc-batch-audit__pct--yellow">{pct.toFixed(1)}%</span>;
  return <span className="mdc-batch-audit__pct mdc-batch-audit__pct--red">{pct.toFixed(1)}%</span>;
}

function AssessmentBadge({ assessment }: { assessment: string }) {
  const cls =
    assessment === "SATISFATORIO"
      ? "mdc-batch-audit__badge--green"
      : assessment === "NECESSITA_AJUSTE"
        ? "mdc-batch-audit__badge--yellow"
        : assessment === "CRITICO"
          ? "mdc-batch-audit__badge--red"
          : "mdc-batch-audit__badge--gray";
  const label =
    assessment === "SATISFATORIO"
      ? "Satisfatório"
      : assessment === "NECESSITA_AJUSTE"
        ? "Necessita Ajuste"
        : assessment === "CRITICO"
          ? "Crítico"
          : assessment;
  return <span className={`mdc-batch-audit__badge ${cls}`}>{label}</span>;
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "OK"
      ? "mdc-batch-audit__status--ok"
      : status === "WARNING"
        ? "mdc-batch-audit__status--warning"
        : status === "CRITICAL"
          ? "mdc-batch-audit__status--critical"
          : "mdc-batch-audit__status--unknown";
  return <span className={`mdc-batch-audit__status ${cls}`}>{status}</span>;
}

function normalizeUrgency(u: string): string {
  return u.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();
}

function UrgencyBadge({ urgency }: { urgency: string }) {
  const norm = normalizeUrgency(urgency);
  const cls =
    norm === "CRITICA"
      ? "mdc-batch-audit__urgency--critica"
      : norm === "ALTA"
        ? "mdc-batch-audit__urgency--alta"
        : norm === "MEDIA"
          ? "mdc-batch-audit__urgency--media"
          : "mdc-batch-audit__urgency--baixa";
  return <span className={`mdc-batch-audit__urgency ${cls}`}>{urgency}</span>;
}

function ModelUpdateSection({ rec, mistralRec }: { rec: ModelUpdateRecommendation; mistralRec?: ModelUpdateRecommendation }) {
  const hasMistral = !!mistralRec;
  const diverges = hasMistral && normalizeUrgency(mistralRec.urgency) !== normalizeUrgency(rec.urgency);

  return (
    <div className={`mdc-batch-audit__model-update ${rec.needs_update ? "mdc-batch-audit__model-update--needs" : "mdc-batch-audit__model-update--ok"}`}>
      {/* Local (deterministic) assessment */}
      <div className="mdc-batch-audit__model-update-header">
        <div className="mdc-batch-audit__model-update-title">
          {rec.needs_update ? (
            <AlertTriangle size={18} className="mdc-batch-audit__model-update-icon--warning" />
          ) : (
            <CheckCircle2 size={18} className="mdc-batch-audit__model-update-icon--ok" />
          )}
          <span>{rec.needs_update ? "Modelo Precisa de Atualização" : "Modelo Dentro dos Parâmetros"}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: "0.65rem", color: "#64748b", textTransform: "uppercase" }}>Modelo</span>
          <UrgencyBadge urgency={rec.urgency} />
        </div>
      </div>

      {/* Mistral AI assessment (side-by-side) */}
      {hasMistral && (
        <div className="mdc-batch-audit__model-update-header" style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid rgba(148,163,184,0.15)" }}>
          <div className="mdc-batch-audit__model-update-title">
            <Brain size={18} style={{ color: "#a78bfa" }} />
            <span>Avaliação Mistral AI</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "0.65rem", color: "#a78bfa", textTransform: "uppercase" }}>Mistral</span>
            <UrgencyBadge urgency={mistralRec.urgency} />
          </div>
        </div>
      )}

      {/* Divergence alert — signal for fine-tuning */}
      {diverges && (
        <div style={{
          marginTop: 8, padding: "6px 10px", borderRadius: 6,
          background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)",
          display: "flex", alignItems: "center", gap: 6,
          fontSize: "0.75rem", color: "#f59e0b"
        }}>
          <AlertTriangle size={14} />
          <span>
            Divergência detectada: Modelo avalia <strong>{rec.urgency}</strong>, Mistral avalia <strong>{mistralRec.urgency}</strong> — considerar ajuste fino nos thresholds
          </span>
        </div>
      )}

      <div className="mdc-batch-audit__model-update-reasons">
        <h4>Diagnóstico</h4>
        <ul>
          {rec.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
        {hasMistral && mistralRec.reasons?.length > 0 && (
          <>
            <h4 style={{ marginTop: 8, color: "#a78bfa" }}>Diagnóstico Mistral</h4>
            <ul>
              {mistralRec.reasons.map((r, i) => (
                <li key={`m-${i}`} style={{ color: "#c4b5fd" }}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="mdc-batch-audit__model-update-actions">
        <h4>Ações Recomendadas</h4>
        <ul>
          {rec.recommended_actions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
        {hasMistral && mistralRec.recommended_actions?.length > 0 && (
          <>
            <h4 style={{ marginTop: 8, color: "#a78bfa" }}>Ações Mistral</h4>
            <ul>
              {mistralRec.recommended_actions.map((a, i) => (
                <li key={`m-${i}`} style={{ color: "#c4b5fd" }}>{a}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      <div className="mdc-batch-audit__model-update-retrain">
        <Wrench size={14} />
        <span>Próximo re-treino: <strong>{rec.next_retrain_suggestion}</strong></span>
      </div>
    </div>
  );
}

function CombinadaCard({ c }: { c: AuditCombinada }) {
  const isIntra = c.tipo === "intra";
  const stColor = c.status_combinada === "SAFE" ? "#00df82" : c.status_combinada === "MISTA" ? "#c4a0ff" : "#ffaa44";
  const stBg = c.status_combinada === "SAFE" ? "rgba(0,223,130,0.08)" : c.status_combinada === "MISTA" ? "rgba(157,80,255,0.08)" : "rgba(255,136,0,0.06)";
  const stBorder = c.status_combinada === "SAFE" ? "rgba(0,223,130,0.25)" : c.status_combinada === "MISTA" ? "rgba(157,80,255,0.25)" : "rgba(255,136,0,0.2)";
  const timeStr = (dt: string) => {
    try { const d = new Date(dt); return isNaN(d.getTime()) ? "--:--" : d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" }); }
    catch { return "--:--"; }
  };

  const legStatusBg = (s: string) => s.toUpperCase().startsWith("SAFE") ? "rgba(0,223,130,0.12)" : "rgba(255,136,0,0.12)";
  const legStatusColor = (s: string) => s.toUpperCase().startsWith("SAFE") ? "#00df82" : "#ffaa44";

  const resultadoColor = c.resultado === "ACERTOU" ? "#00df82" : c.resultado === "ERROU" ? "#ef4444" : "#666";
  const resultadoBg = c.resultado === "ACERTOU" ? "rgba(0,223,130,0.15)" : c.resultado === "ERROU" ? "rgba(239,68,68,0.15)" : "rgba(100,100,100,0.1)";

  return (
    <div style={{ borderRadius: 10, border: `1px solid ${stBorder}`, background: stBg, padding: "10px 12px", marginBottom: 6 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          {isIntra ? <Layers size={11} style={{ color: "#c4a0ff" }} /> : <Link2 size={11} style={{ color: "#00df82" }} />}
          <span style={{ fontSize: "0.6rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "#888" }}>
            {isIntra ? "Intra-jogo" : "Inter-jogo"}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ fontSize: "0.6rem", color: "#666" }}>{c.prob_combinada_min}–{c.prob_combinada_max}%</span>
          <span style={{ fontSize: "0.6rem", fontWeight: 700, borderRadius: 4, padding: "1px 5px", background: `${stColor}22`, color: stColor }}>{c.status_combinada}</span>
          {c.resultado && (
            <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: "0.6rem", fontWeight: 700, borderRadius: 4, padding: "1px 6px", background: resultadoBg, color: resultadoColor }}>
              {c.resultado === "ACERTOU" ? <CheckCircle2 size={10} /> : c.resultado === "ERROU" ? <XCircle size={10} /> : null}
              {c.resultado}
            </span>
          )}
        </div>
      </div>
      {([c.leg1, c.leg2] as AuditCombinadaLeg[]).map((leg, i) => (
        <div key={i} style={{ display: "flex", gap: 6, marginBottom: 4 }}>
          <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#1a1a1a", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.55rem", color: "#888", flexShrink: 0, marginTop: 2 }}>{i + 1}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "0.68rem", fontWeight: 600, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {leg.homeTeam} <span style={{ color: "#666" }}>x</span> {leg.awayTeam} <span style={{ color: "#555", fontWeight: 400 }}>{timeStr(leg.datetime)}</span>
            </div>
            <div style={{ display: "flex", gap: 5, alignItems: "center", marginTop: 1, flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.65rem", color: "#00df82", fontWeight: 500 }}>{leg.mercado}</span>
              <span style={{ fontSize: "0.6rem", borderRadius: 4, padding: "1px 4px", fontWeight: 700, background: legStatusBg(leg.status), color: legStatusColor(leg.status) }}>
                {leg.status} {leg.prob_min}–{leg.prob_max}%
              </span>
              <span style={{ fontSize: "0.6rem", color: "#555" }}>@{leg.odd_minima.toFixed(2)}</span>
            </div>
          </div>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 6, borderTop: "1px solid rgba(255,255,255,0.05)", marginTop: 2 }}>
        <span style={{ fontSize: "0.6rem", color: "#555", textTransform: "uppercase", letterSpacing: "0.05em" }}>Odd Combinada</span>
        <span style={{ fontSize: "1rem", fontWeight: 900, color: "#fff" }}>{c.odd_combinada.toFixed(2)}</span>
      </div>
    </div>
  );
}

function CombinadasSection({ data }: { data: AuditCombinadas }) {
  const [tab, setTab] = useState<"intra" | "inter">("intra");
  const list = tab === "intra" ? data.intra : data.inter;
  const total = tab === "intra" ? data.total_intra : data.total_inter;

  if (data.total_intra === 0 && data.total_inter === 0) return null;

  const hasAccuracy = (data.dupla_intra_total ?? 0) > 0 || (data.dupla_inter_total ?? 0) > 0;

  return (
    <div className="mdc-batch-audit__block">
      <h3 className="mdc-batch-audit__block-title">
        <Layers size={16} /> Duplas Recomendadas ({data.total_jogos} jogos)
      </h3>

      {/* Dupla accuracy summary */}
      {hasAccuracy && (
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
          {(data.dupla_intra_total ?? 0) > 0 && (
            <div style={{
              flex: 1, minWidth: 120, padding: "8px 10px", borderRadius: 8,
              background: "rgba(157,80,255,0.06)", border: "1px solid rgba(157,80,255,0.15)",
            }}>
              <div style={{ fontSize: "0.55rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Intra-jogo</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <AccuracyColor pct={data.dupla_intra_accuracy ?? 0} />
                <span style={{ fontSize: "0.65rem", color: "#666" }}>{data.dupla_intra_correct}/{data.dupla_intra_total}</span>
              </div>
            </div>
          )}
          {(data.dupla_inter_total ?? 0) > 0 && (
            <div style={{
              flex: 1, minWidth: 120, padding: "8px 10px", borderRadius: 8,
              background: "rgba(0,223,130,0.06)", border: "1px solid rgba(0,223,130,0.15)",
            }}>
              <div style={{ fontSize: "0.55rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Inter-jogo</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <AccuracyColor pct={data.dupla_inter_accuracy ?? 0} />
                <span style={{ fontSize: "0.65rem", color: "#666" }}>{data.dupla_inter_correct}/{data.dupla_inter_total}</span>
              </div>
            </div>
          )}
          {(data.dupla_overall_accuracy != null) && ((data.dupla_intra_total ?? 0) + (data.dupla_inter_total ?? 0) > 0) && (
            <div style={{
              flex: 1, minWidth: 120, padding: "8px 10px", borderRadius: 8,
              background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)",
            }}>
              <div style={{ fontSize: "0.55rem", color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>Geral Duplas</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                <AccuracyColor pct={data.dupla_overall_accuracy} />
                <span style={{ fontSize: "0.65rem", color: "#666" }}>
                  {(data.dupla_intra_correct ?? 0) + (data.dupla_inter_correct ?? 0)}/{(data.dupla_intra_total ?? 0) + (data.dupla_inter_total ?? 0)}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {(["intra", "inter"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "4px 12px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.08)",
              background: tab === t ? "rgba(157,80,255,0.18)" : "rgba(255,255,255,0.03)",
              color: tab === t ? "#c4a0ff" : "#777", fontSize: "0.7rem", fontWeight: 600, cursor: "pointer",
            }}
          >
            {t === "intra" ? "Intra-jogo" : "Inter-jogo"} ({t === "intra" ? data.total_intra : data.total_inter})
          </button>
        ))}
      </div>
      {list.length === 0 ? (
        <div style={{ color: "#555", fontSize: "0.75rem", textAlign: "center", padding: "16px 0" }}>
          Nenhuma dupla {tab === "intra" ? "intra-jogo" : "inter-jogo"} encontrada.
        </div>
      ) : (
        <div>
          {list.map((c, i) => (
            <CombinadaCard key={i} c={c} />
          ))}
          {total > list.length && (
            <div style={{ fontSize: "0.65rem", color: "#555", textAlign: "center", marginTop: 4 }}>
              Mostrando {list.length} de {total} duplas
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MatchItem({ match }: { match: BatchAuditMatchResult }) {
  const [open, setOpen] = useState(false);
  const accuracy = match.picks_total > 0 ? (match.picks_correct / match.picks_total) * 100 : 0;

  return (
    <div className="mdc-batch-audit__match-item">
      <button className="mdc-batch-audit__match-header" onClick={() => setOpen(!open)}>
        <div className="mdc-batch-audit__match-info">
          <span className="mdc-batch-audit__match-teams">
            {match.home_team} <strong>{match.score}</strong> {match.away_team}
          </span>
          <span className="mdc-batch-audit__match-league">{match.league}</span>
        </div>
        <div className="mdc-batch-audit__match-meta">
          <AccuracyColor pct={accuracy} />
          <span className="mdc-batch-audit__match-count">
            {match.picks_correct}/{match.picks_total}
          </span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>
      {open && match.picks.length > 0 && (
        <div className="mdc-batch-audit__match-picks">
          {match.picks.map((p, i) => (
            <div key={i} className="mdc-batch-audit__pick-row">
              <span className={`mdc-batch-audit__pick-status-badge mdc-batch-audit__pick-status-badge--${p.status_pick?.toLowerCase() || "neutro"}`}>
                {p.status_pick}
              </span>
              <span className="mdc-batch-audit__pick-market">{p.mercado}</span>
              {p.resultado === "ACERTOU" ? (
                <CheckCircle2 size={14} className="mdc-batch-audit__pick-icon--correct" />
              ) : (
                <XCircle size={14} className="mdc-batch-audit__pick-icon--wrong" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function BatchAuditPanel({ result, onClose, onApplyCorrections }: BatchAuditPanelProps) {
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [matchesExpanded, setMatchesExpanded] = useState(false);
  const [view, setView] = useState<"detail" | "report">("detail");

  const ev = result.model_evaluation;
  const corrections = ev?.recommended_corrections ?? [];

  async function handleApply() {
    if (corrections.length === 0) return;
    setApplying(true);
    try {
      await onApplyCorrections(corrections);
      setApplied(true);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="mdc-batch-audit__overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="mdc-batch-audit__panel">
        {/* Header */}
        <div className="mdc-batch-audit__header">
          <div className="mdc-batch-audit__header-left">
            <ShieldCheck size={20} />
            <h2>Auditoria da Rodada</h2>
            {result.audited_matches > 0 && (
              <span className="mdc-batch-audit__header-count">{result.audited_matches} jogos</span>
            )}
          </div>
          <button className="mdc-batch-audit__close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="mdc-batch-audit__body">
          {/* View toggle */}
          {result.audited_matches > 0 && (
            <div style={{ display: "flex", gap: 4, padding: "12px 16px 4px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <button
                onClick={() => setView("detail")}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
                  background: view === "detail" ? "rgba(0,255,136,0.12)" : "transparent",
                  border: view === "detail" ? "1px solid rgba(0,255,136,0.3)" : "1px solid transparent",
                  borderRadius: 6, color: view === "detail" ? "#00ff88" : "#888",
                  fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all 0.2s",
                }}
              >
                <BarChart3 size={14} /> Detalhado
              </button>
              <button
                onClick={() => setView("report")}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 14px",
                  background: view === "report" ? "rgba(0,255,136,0.12)" : "transparent",
                  border: view === "report" ? "1px solid rgba(0,255,136,0.3)" : "1px solid transparent",
                  borderRadius: 6, color: view === "report" ? "#00ff88" : "#888",
                  fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all 0.2s",
                }}
              >
                <FileText size={14} /> Report Card
              </button>
            </div>
          )}

          {/* Report Card view */}
          {view === "report" && result.audited_matches > 0 && (
            <div style={{ padding: "16px 0" }}>
              <AuditReportCard data={result} />
            </div>
          )}

          {/* Empty / error state */}
          {(!result.audited_matches || result.status === "error") && (
            <div className="mdc-batch-audit__empty">
              <AlertTriangle size={32} />
              <p>{result.message || "Nenhum jogo finalizado encontrado para auditar."}</p>
            </div>
          )}

          {result.audited_matches > 0 && view === "detail" && (
            <>
              {/* Summary cards */}
              <div className="mdc-batch-audit__summary-cards">
                <div className="mdc-batch-audit__summary-card">
                  <BarChart3 size={16} />
                  <div className="mdc-batch-audit__summary-label">Jogos Auditados</div>
                  <div className="mdc-batch-audit__summary-value">{result.audited_matches}</div>
                </div>
                <div className="mdc-batch-audit__summary-card">
                  <TrendingUp size={16} />
                  <div className="mdc-batch-audit__summary-label">Acerto Geral</div>
                  <div className="mdc-batch-audit__summary-value">
                    <AccuracyColor pct={result.overall_accuracy} />
                  </div>
                </div>
                <div className="mdc-batch-audit__summary-card mdc-batch-audit__summary-card--safe">
                  <ShieldCheck size={16} />
                  <div className="mdc-batch-audit__summary-label">SAFE</div>
                  <div className="mdc-batch-audit__summary-value">
                    {/* #168: guard null from #162 — safe_accuracy is number|null when safe_total=0 */}
                    {result.safe_accuracy != null ? <AccuracyColor pct={result.safe_accuracy} /> : <span style={{color:"#666"}}>N/A</span>}
                    <span className="mdc-batch-audit__summary-sub">{result.safe_correct}/{result.safe_total}</span>
                  </div>
                </div>
                <div className="mdc-batch-audit__summary-card">
                  <Brain size={16} />
                  <div className="mdc-batch-audit__summary-label">NEUTRO</div>
                  <div className="mdc-batch-audit__summary-value">
                    {/* #168: guard null from #162 — neutro_accuracy is number|null when neutro_total=0 */}
                    {result.neutro_accuracy != null ? <AccuracyColor pct={result.neutro_accuracy} /> : <span style={{color:"#666"}}>N/A</span>}
                    <span className="mdc-batch-audit__summary-sub">{result.neutro_correct}/{result.neutro_total}</span>
                  </div>
                </div>
              </div>

              {/* Brier + Lambda */}
              <div className="mdc-batch-audit__metrics-row">
                {/* #195: o tile antigo dizia "Brier Score Médio" mas media so
                    Over 2.5 gols — aparecia 0.11 ao lado de 36.8% de acerto,
                    dois numeros que nao podem coexistir. Agora o destaque e o
                    Brier dos picks auditados; o de Over 2.5 fica ao lado, com
                    o nome certo. */}
                <div className="mdc-batch-audit__metric">
                  <span className="mdc-batch-audit__metric-label">Brier dos picks</span>
                  <span className="mdc-batch-audit__metric-value">
                    {result.brier_picks != null
                      ? `${result.brier_picks.toFixed(4)}${result.brier_picks_n ? ` (${result.brier_picks_n})` : ""}`
                      : "N/A"}
                  </span>
                </div>
                <div className="mdc-batch-audit__metric">
                  <span className="mdc-batch-audit__metric-label">Brier Over 2.5</span>
                  <span className="mdc-batch-audit__metric-value">{result.avg_brier_score.toFixed(4)}</span>
                </div>
                <div className="mdc-batch-audit__metric">
                  <span className="mdc-batch-audit__metric-label">Erro Lambda Médio</span>
                  <span className="mdc-batch-audit__metric-value">{result.avg_lambda_error.toFixed(2)} gols</span>
                </div>
              </div>

              {/* Market Reference Signal stats */}
              {result.market_reference_stats && result.market_reference_stats.capped_by_market_reference_count > 0 && (
                <div className="mdc-batch-audit__metrics-row" style={{ marginTop: 8 }}>
                  <div className="mdc-batch-audit__metric">
                    <span className="mdc-batch-audit__metric-label">Picks limitados por sinal estrutural</span>
                    <span className="mdc-batch-audit__metric-value">
                      {result.market_reference_stats.capped_by_market_reference_count}
                    </span>
                  </div>
                  {result.market_reference_stats.safe_to_neutro_by_signal_count > 0 && (
                    <div className="mdc-batch-audit__metric">
                      <span className="mdc-batch-audit__metric-label" style={{ color: "#ffaa44" }}>
                        SAFE → NEUTRO (sinal)
                      </span>
                      <span className="mdc-batch-audit__metric-value">
                        {result.market_reference_stats.safe_to_neutro_by_signal_count}
                      </span>
                    </div>
                  )}
                  {result.market_reference_stats.safe_blocked_by_restrito_count > 0 && (
                    <div className="mdc-batch-audit__metric">
                      <span className="mdc-batch-audit__metric-label" style={{ color: "#ff5555" }}>
                        SAFE bloqueado (RESTRITO)
                      </span>
                      <span className="mdc-batch-audit__metric-value">
                        {result.market_reference_stats.safe_blocked_by_restrito_count}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Model Update Recommendation — local vs Mistral comparison */}
              {result.model_update_recommendation && (
                <ModelUpdateSection rec={result.model_update_recommendation} mistralRec={result.mistral_recommendation} />
              )}

              {/* Market accuracy table */}
              {result.market_accuracy.length > 0 && (
                <div className="mdc-batch-audit__block">
                  <h3 className="mdc-batch-audit__block-title">Acurácia por Mercado</h3>
                  <div className="mdc-batch-audit__market-table-wrap">
                    <table className="mdc-batch-audit__market-table">
                      <thead>
                        <tr>
                          <th>Mercado</th>
                          <th>Acertos</th>
                          <th>Total</th>
                          <th>%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.market_accuracy.map((ma) => (
                          <tr key={ma.market}>
                            <td>{ma.market}</td>
                            <td>{ma.correct}</td>
                            <td>{ma.total}</td>
                            <td>
                              <AccuracyColor pct={ma.accuracy_pct} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* League accuracy table */}
              {result.league_accuracy && result.league_accuracy.length > 0 && (
                <div className="mdc-batch-audit__block">
                  <h3 className="mdc-batch-audit__block-title">Acurácia por Liga</h3>
                  <div className="mdc-batch-audit__market-table-wrap">
                    <table className="mdc-batch-audit__market-table">
                      <thead>
                        <tr>
                          <th>Liga</th>
                          <th>Jogos</th>
                          <th>Acertos</th>
                          <th>Total</th>
                          <th>%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.league_accuracy.map((la) => (
                          <tr key={la.league}>
                            <td>{la.league}</td>
                            <td>{la.matches_audited}</td>
                            <td>{la.picks_correct}</td>
                            <td>{la.picks_total}</td>
                            <td>
                              <AccuracyColor pct={la.accuracy_pct} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Combinadas (duplas) section */}
              {result.combinadas && (
                <CombinadasSection data={result.combinadas} />
              )}

              {/* Match results grouped by league (collapsible) */}
              {result.match_results.length > 0 && (
                <div className="mdc-batch-audit__block">
                  <button
                    className="mdc-batch-audit__block-toggle"
                    onClick={() => setMatchesExpanded(!matchesExpanded)}
                  >
                    <h3 className="mdc-batch-audit__block-title">
                      Detalhes por Jogo ({result.match_results.length})
                    </h3>
                    {matchesExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                  {matchesExpanded && (
                    <div className="mdc-batch-audit__matches-list">
                      {Object.entries(
                        result.match_results.reduce<Record<string, BatchAuditMatchResult[]>>((acc, mr) => {
                          const key = mr.league || "Outros";
                          if (!acc[key]) acc[key] = [];
                          acc[key].push(mr);
                          return acc;
                        }, {})
                      ).map(([league, matches]) => (
                        <div key={league} className="mdc-batch-audit__league-group">
                          <div className="mdc-batch-audit__league-group-header">
                            <span className="mdc-batch-audit__league-group-title">{league}</span>
                            <span className="mdc-batch-audit__league-group-count">
                              {matches.reduce((s, m) => s + m.picks_correct, 0)}/{matches.reduce((s, m) => s + m.picks_total, 0)} picks
                            </span>
                          </div>
                          {matches.map((mr) => (
                            <MatchItem key={mr.match_id} match={mr} />
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Model Evaluation */}
              {ev && (
                <div className="mdc-batch-audit__block mdc-batch-audit__block--eval">
                  <h3 className="mdc-batch-audit__block-title">
                    <Brain size={16} /> Avaliação dos Modelos (Mistral AI)
                  </h3>

                  <div className="mdc-batch-audit__eval-header">
                    <AssessmentBadge assessment={ev.overall_assessment} />
                    {ev.overall_notes && (
                      <p className="mdc-batch-audit__eval-notes">{ev.overall_notes}</p>
                    )}
                  </div>

                  <div className="mdc-batch-audit__eval-grid">
                    {/* Lambda evaluation */}
                    <div className="mdc-batch-audit__eval-card">
                      <div className="mdc-batch-audit__eval-card-header">
                        <span>Lambdas (Poisson)</span>
                        <StatusBadge status={ev.lambda_evaluation?.status || "UNKNOWN"} />
                      </div>
                      {ev.lambda_evaluation?.direction && (
                        <div className="mdc-batch-audit__eval-direction">
                          Tendência: <strong>{ev.lambda_evaluation.direction.replace(/_/g, " ")}</strong>
                        </div>
                      )}
                      <p className="mdc-batch-audit__eval-card-notes">{ev.lambda_evaluation?.notes}</p>
                    </div>

                    {/* Threshold evaluation */}
                    <div className="mdc-batch-audit__eval-card">
                      <div className="mdc-batch-audit__eval-card-header">
                        <span>Thresholds</span>
                        <div style={{ display: "flex", gap: 4 }}>
                          <StatusBadge status={ev.threshold_evaluation?.safe_status || "UNKNOWN"} />
                          <StatusBadge status={ev.threshold_evaluation?.neutro_status || "UNKNOWN"} />
                        </div>
                      </div>
                      <p className="mdc-batch-audit__eval-card-notes">{ev.threshold_evaluation?.notes}</p>
                    </div>
                  </div>

                  {/* Market biases */}
                  {ev.market_biases && ev.market_biases.length > 0 && (
                    <div className="mdc-batch-audit__biases">
                      <h4>Vieses Detectados</h4>
                      {ev.market_biases.map((b, i) => (
                        <div key={i} className={`mdc-batch-audit__bias mdc-batch-audit__bias--${b.severity?.toLowerCase()}`}>
                          <strong>{b.market}</strong>: {b.description}
                          <span className="mdc-batch-audit__bias-type">{b.bias_type?.replace(/_/g, " ")}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* AI self-evaluation */}
                  {ev.ai_self_evaluation && (
                    <div className="mdc-batch-audit__ai-self">
                      <h4>
                        <Wrench size={14} /> Auto-Avaliação da AI
                      </h4>
                      <div className="mdc-batch-audit__ai-self-alignment">
                        Alinhamento: <strong>{ev.ai_self_evaluation.alignment_with_results}</strong>
                      </div>
                      {ev.ai_self_evaluation.factors_to_emphasize?.length > 0 && (
                        <div className="mdc-batch-audit__ai-factors">
                          <span className="mdc-batch-audit__ai-factors-label mdc-batch-audit__ai-factors-label--up">
                            ▲ Enfatizar mais:
                          </span>
                          {ev.ai_self_evaluation.factors_to_emphasize.map((f, i) => (
                            <span key={i} className="mdc-batch-audit__ai-factor-tag">{f}</span>
                          ))}
                        </div>
                      )}
                      {ev.ai_self_evaluation.factors_to_reduce?.length > 0 && (
                        <div className="mdc-batch-audit__ai-factors">
                          <span className="mdc-batch-audit__ai-factors-label mdc-batch-audit__ai-factors-label--down">
                            ▼ Reduzir ênfase:
                          </span>
                          {ev.ai_self_evaluation.factors_to_reduce.map((f, i) => (
                            <span key={i} className="mdc-batch-audit__ai-factor-tag mdc-batch-audit__ai-factor-tag--reduce">{f}</span>
                          ))}
                        </div>
                      )}
                      {ev.ai_self_evaluation.notes && (
                        <p className="mdc-batch-audit__ai-self-notes">{ev.ai_self_evaluation.notes}</p>
                      )}
                    </div>
                  )}

                  {/* Confidence */}
                  <div className="mdc-batch-audit__confidence">
                    Confiança da auditoria: <strong>{ev.audit_confidence}%</strong>
                  </div>
                </div>
              )}

              {/* Corrections */}
              {corrections.length > 0 && (
                <div className="mdc-batch-audit__block mdc-batch-audit__block--corrections">
                  <h3 className="mdc-batch-audit__block-title">
                    <Wrench size={16} /> Correções Recomendadas ({corrections.length})
                  </h3>
                  <div className="mdc-batch-audit__corrections-list">
                    {corrections.map((c, i) => (
                      <div key={i} className="mdc-batch-audit__correction-card">
                        <div className="mdc-batch-audit__correction-header">
                          <span className={`mdc-batch-audit__correction-type mdc-batch-audit__correction-type--${c.impact?.toLowerCase()}`}>
                            {c.type?.replace(/_/g, " ")}
                          </span>
                          <span className="mdc-batch-audit__correction-impact">{c.impact}</span>
                        </div>
                        <div className="mdc-batch-audit__correction-param">{c.parameter}</div>
                        <div className="mdc-batch-audit__correction-values">
                          <span className="mdc-batch-audit__correction-old">{typeof c.current_value === "number" ? (Number.isInteger(c.current_value) ? String(c.current_value) : parseFloat(c.current_value.toFixed(2))) : c.current_value}</span>
                          <span className="mdc-batch-audit__correction-arrow">→</span>
                          <span className="mdc-batch-audit__correction-new">{typeof c.suggested_value === "number" ? (Number.isInteger(c.suggested_value) ? String(c.suggested_value) : parseFloat(c.suggested_value.toFixed(2))) : c.suggested_value}</span>
                        </div>
                        <p className="mdc-batch-audit__correction-reason">{c.reason}</p>
                        <div className="mdc-batch-audit__correction-confidence">
                          Confiança: {c.confidence}%
                        </div>
                      </div>
                    ))}
                  </div>
                  <button
                    className="mdc-batch-audit__apply-btn"
                    onClick={handleApply}
                    disabled={applying || applied}
                  >
                    {applying
                      ? "Aplicando..."
                      : applied
                        ? "✓ Correções Aplicadas"
                        : `Aplicar Todas as Correções (${corrections.length})`}
                  </button>
                </div>
              )}
              {/* Blocked corrections (#099b) */}
              {ev?.blocked_corrections && ev.blocked_corrections.length > 0 && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{ fontSize: "0.65rem", color: "#64748b", cursor: "pointer" }}>
                    {ev.blocked_corrections.length} ação(ões) bloqueada(s) por regras operacionais
                  </summary>
                  <div style={{ fontSize: "0.6rem", color: "#475569", marginTop: 4, padding: "4px 8px" }}>
                    {ev.blocked_corrections.map((b: { original: string; rule: string }, i: number) => (
                      <div key={i} style={{ marginBottom: 4, borderBottom: "1px solid rgba(255,255,255,0.03)", paddingBottom: 4 }}>
                        <span style={{ textDecoration: "line-through", color: "#64748b" }}>{b.original}</span>
                        <br />
                        <span style={{ color: "#ef4444", fontSize: "0.55rem" }}>Bloqueada ({b.rule})</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
