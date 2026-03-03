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
} from "lucide-react";
import type {
  BatchAuditResult,
  BatchAuditCorrection,
  BatchAuditMatchResult,
  ModelUpdateRecommendation,
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

function UrgencyBadge({ urgency }: { urgency: string }) {
  const cls =
    urgency === "CRITICA"
      ? "mdc-batch-audit__urgency--critica"
      : urgency === "ALTA"
        ? "mdc-batch-audit__urgency--alta"
        : urgency === "MEDIA"
          ? "mdc-batch-audit__urgency--media"
          : "mdc-batch-audit__urgency--baixa";
  return <span className={`mdc-batch-audit__urgency ${cls}`}>{urgency}</span>;
}

function ModelUpdateSection({ rec }: { rec: ModelUpdateRecommendation }) {
  return (
    <div className={`mdc-batch-audit__model-update ${rec.needs_update ? "mdc-batch-audit__model-update--needs" : "mdc-batch-audit__model-update--ok"}`}>
      <div className="mdc-batch-audit__model-update-header">
        <div className="mdc-batch-audit__model-update-title">
          {rec.needs_update ? (
            <AlertTriangle size={18} className="mdc-batch-audit__model-update-icon--warning" />
          ) : (
            <CheckCircle2 size={18} className="mdc-batch-audit__model-update-icon--ok" />
          )}
          <span>{rec.needs_update ? "Modelo Precisa de Atualização" : "Modelo Dentro dos Parâmetros"}</span>
        </div>
        <UrgencyBadge urgency={rec.urgency} />
      </div>

      <div className="mdc-batch-audit__model-update-reasons">
        <h4>Diagnóstico</h4>
        <ul>
          {rec.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>

      <div className="mdc-batch-audit__model-update-actions">
        <h4>Ações Recomendadas</h4>
        <ul>
          {rec.recommended_actions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </div>

      <div className="mdc-batch-audit__model-update-retrain">
        <Wrench size={14} />
        <span>Próximo re-treino: <strong>{rec.next_retrain_suggestion}</strong></span>
      </div>
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
          {/* Empty / error state */}
          {(!result.audited_matches || result.status === "error") && (
            <div className="mdc-batch-audit__empty">
              <AlertTriangle size={32} />
              <p>{result.message || "Nenhum jogo finalizado encontrado para auditar."}</p>
            </div>
          )}

          {result.audited_matches > 0 && (
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
                    <AccuracyColor pct={result.safe_accuracy} />
                    <span className="mdc-batch-audit__summary-sub">{result.safe_correct}/{result.safe_total}</span>
                  </div>
                </div>
                <div className="mdc-batch-audit__summary-card">
                  <Brain size={16} />
                  <div className="mdc-batch-audit__summary-label">NEUTRO</div>
                  <div className="mdc-batch-audit__summary-value">
                    <AccuracyColor pct={result.neutro_accuracy} />
                    <span className="mdc-batch-audit__summary-sub">{result.neutro_correct}/{result.neutro_total}</span>
                  </div>
                </div>
              </div>

              {/* Brier + Lambda */}
              <div className="mdc-batch-audit__metrics-row">
                <div className="mdc-batch-audit__metric">
                  <span className="mdc-batch-audit__metric-label">Brier Score Médio</span>
                  <span className="mdc-batch-audit__metric-value">{result.avg_brier_score.toFixed(4)}</span>
                </div>
                <div className="mdc-batch-audit__metric">
                  <span className="mdc-batch-audit__metric-label">Erro Lambda Médio</span>
                  <span className="mdc-batch-audit__metric-value">{result.avg_lambda_error.toFixed(2)} gols</span>
                </div>
              </div>

              {/* Model Update Recommendation */}
              {result.model_update_recommendation && (
                <ModelUpdateSection rec={result.model_update_recommendation} />
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

              {/* Match results (collapsible) */}
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
                      {result.match_results.map((mr) => (
                        <MatchItem key={mr.match_id} match={mr} />
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
