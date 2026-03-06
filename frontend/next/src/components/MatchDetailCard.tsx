// frontend/next/components/MatchDetailCard.tsx
"use client";

import React, { useState, useEffect, Component, type ErrorInfo, type ReactNode } from "react";
import {
  Clock,
  MapPin,
  Users,
  Star,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Loader2,
  RefreshCw,
  ArrowLeft,
  ShieldCheck,
} from "lucide-react";
import "../styles/match-detail-card.css";

/* ── ERROR BOUNDARY (reusable) ── */
export class SafeErrorBoundary extends Component<
  { children: ReactNode; fallbackMessage?: string; section?: string },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: ReactNode; fallbackMessage?: string; section?: string }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[SafeErrorBoundary:${this.props.section ?? "unknown"}]`, error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 16, background: "rgba(255,68,68,0.1)", borderRadius: 8, margin: "8px 0" }}>
          <p style={{ color: "#ff4444", fontSize: "0.8rem", margin: 0 }}>
            {this.props.fallbackMessage ?? "Erro ao exibir este conteudo. Tente recarregar a pagina."}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export interface AIAnalysis {
  summary: string;
  key_points: string[];
  recommendation: string;
  confidence: number;
  last_updated: string;
}

export interface AuditPickEvaluation {
  mercado: string;
  status_pick: string;
  resultado: string;
  nota: string;
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
  validation: {
    probabilities: { status: string; notes: string; brier_score?: number };
    lambdas: { status: string; notes: string; predicted_total?: number; actual_total?: number };
    ev: { status: string; notes: string };
  };
  ai_analysis_accuracy?: string;
  accuracy_summary?: string;
  corrections?: AuditCorrection[];
  biases_detected?: string[];
  suggestions?: string[];
  audit_confidence: number;
  audit_type?: string;
  timestamp?: string;
  match?: string;
}

// Alias for backward compatibility with V0 dashboard
export type MatchDetail = MatchDetailData;

export interface MatchDetailData {
  id: string;
  league: string;
  leagueId?: string;
  season?: string;
  homeTeam: string;
  awayTeam: string;
  homeTeamLogo?: string;
  awayTeamLogo?: string;
  startTime?: string;
  status?: "scheduled" | "live" | "finished";
  score?: { home: number; away: number; halftime?: { home: number; away: number } };
  period?: "1T" | "HT" | "2T" | null;
  minute?: number | null;
  venue?: {
    name: string;
    capacity?: number;
    image?: string;
  };
  odds?: {
    home?: number;
    draw?: number;
    away?: number;
    homeVariation?: "up" | "down";
    drawVariation?: "up" | "down";
    awayVariation?: "up" | "down";
  };
  doubleChance?: {
    homeOrDraw?: number;
    homeOrAway?: number;
    drawOrAway?: number;
  };
  btts?: {
    yes?: number;
    no?: number;
  };
  matchStats?: {
    homeWinProb?: number;
    drawProb?: number;
    awayWinProb?: number;
    avgGoals?: number;
    bttsProb?: number;
    over15Prob?: number;
    over25Prob?: number;
    over35Prob?: number;
    over45Prob?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    homePossession?: number;
    awayPossession?: number;
    homeXG?: number;
    awayXG?: number;
    leagueRegime?: string;
    leagueVolatility?: string;
    homeCornersPerMatch?: number;
    awayCornersPerMatch?: number;
    homeCardsPerMatch?: number;
    awayCardsPerMatch?: number;
    homeShotsOnTarget?: number;
    awayShotsOnTarget?: number;
    homeShotsPerMatch?: number;
    awayShotsPerMatch?: number;
    homeFoulsPerMatch?: number;
    awayFoulsPerMatch?: number;
    leagueAvgCorners?: number;
    leagueAvgCards?: number;
    leagueAvgFouls?: number;
    leagueAvgShots?: number;
    // League extended
    leagueHomeAdvantage?: number;
    leagueCleanSheetsPct?: number;
    leagueOver25Pct?: number;
    leagueXgAvg?: number;
    // Team advanced stats
    homeBttsPercentage?: number;
    awayBttsPercentage?: number;
    homeCleanSheetPct?: number;
    awayCleanSheetPct?: number;
    homeFtsPercentage?: number;
    awayFtsPercentage?: number;
    homeOver25Percentage?: number;
    awayOver25Percentage?: number;
    homeWinPercentage?: number;
    awayWinPercentage?: number;
    homeXgForAvg?: number;
    awayXgForAvg?: number;
    homeXgAgainstAvg?: number;
    awayXgAgainstAvg?: number;
    homeCornersAgainstPerMatch?: number;
    awayCornersAgainstPerMatch?: number;
    homeLeaguePosition?: number;
    awayLeaguePosition?: number;
    homeAvgTotalGoals?: number;
    awayAvgTotalGoals?: number;
    cornersPotential?: number;
    cornerOver85Prob?: number;
    cornerOver95Prob?: number;
    cornerOver105Prob?: number;
  };
  h2h?: {
    totalMatches?: number;
    homeWins?: number;
    draws?: number;
    awayWins?: number;
    avgGoals?: number;
  };
  homeForm?: string[];
  awayForm?: string[];
  round?: string;
  aiAnalysis?: AIAnalysis;
}

/** Normaliza probabilidade para exibição (0-1 ou 0-100 -> X.X%) */
function formatProbValue(value?: number | null): string {
  if (value == null || value < 0) return "-";
  let pct = value;
  if (pct > 0 && pct <= 1) pct *= 100;
  return `${pct.toFixed(1)}%`;
}

/** Corrige percentuais mal formatados na análise AI (ex: 4849.8% -> 48.5%, 2646.6% -> 26.5%) */
function fixAiPercentages(text: string): string {
  if (!text || typeof text !== "string") return text;
  return text.replace(/(\d[\d.,]*)\s*%/g, (match) => {
    const raw = match.replace(/\s/g, "").slice(0, -1);
    const numStr = raw.includes(",") && raw.lastIndexOf(",") > (raw.lastIndexOf(".") || -1)
      ? raw.replace(/\./g, "").replace(",", ".") // europeu: 2.646,6
      : raw.replace(/,/g, "");
    const n = parseFloat(numStr);
    if (Number.isNaN(n)) return match;
    if (n > 100) return `${(n / 100).toFixed(1)}%`;
    return match;
  });
}

type Props = {
  match: MatchDetailData;
  aiLoading?: boolean;
  onRegenerate?: () => void;
  onAudit?: () => void;
  onApplyCorrection?: (correction: AuditCorrection) => void;
  auditResult?: AuditResult | null;
  auditLoading?: boolean;
  auditResultRef?: React.RefObject<HTMLDivElement | null>;
  version?: string;
  onBack?: () => void;
  showBackButton?: boolean;
  isFavorite?: boolean;
  onFavorite?: () => void;
};

export default function MatchDetailCard(props: Props) {
  return (
    <SafeErrorBoundary section="MatchDetailCard" fallbackMessage="Erro ao exibir detalhes do jogo. Tente recarregar a pagina.">
      <MatchDetailCardInner {...props} />
    </SafeErrorBoundary>
  );
}

function MatchDetailCardInner({ match, aiLoading, onRegenerate, onAudit, onApplyCorrection, auditResult, auditLoading, auditResultRef, version = "pro V3.6", onBack, showBackButton = false, isFavorite = false, onFavorite }: Props) {
  const [activeTab, setActiveTab] = useState<"pre-game" | "odds" | "stats" | "h2h">("pre-game");
  const [activeSubTab, setActiveSubTab] = useState<"resumo" | "stats" | "h2h" | "ultimos">("resumo");
  const [isAIExpanded, setIsAIExpanded] = useState(true);
  const [isComparativeExpanded, setIsComparativeExpanded] = useState(true);
  const [comparativeTab, setComparativeTab] = useState<string>("gols");
  const [timeRemaining, setTimeRemaining] = useState<{ hours: number; minutes: number; seconds: number } | null>(null);
  const [showStandings, setShowStandings] = useState(false);
  const [standingsData, setStandingsData] = useState<any[]>([]);
  const [standingsLoading, setStandingsLoading] = useState(false);

  // Countdown timer
  useEffect(() => {
    if (!match.startTime) return;

    const update = () => {
      const now = new Date();
      const start = new Date(match.startTime!);
      const diff = start.getTime() - now.getTime();
      if (diff <= 0) {
        setTimeRemaining(null);
        return;
      }
      setTimeRemaining({
        hours: Math.floor(diff / (1000 * 60 * 60)),
        minutes: Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)),
        seconds: Math.floor((diff % (1000 * 60)) / 1000),
      });
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [match.startTime]);

  const getOddVariation = (variation?: "up" | "down") => {
    if (!variation) return null;
    return (
      <span className={`mdc-odd-variation mdc-odd-variation--${variation}`}>
        {variation === "up" ? "\u2191" : "\u2193"}
      </span>
    );
  };

  const getStatusBadge = () => {
    switch (match.status) {
      case "scheduled":
        return <span className="mdc-badge-upcoming">AGENDADO</span>;
      case "live":
        return <span className="mdc-badge-live">AO VIVO</span>;
      case "finished":
        return <span className="mdc-badge-finished">FINALIZADO</span>;
      default:
        return null;
    }
  };

  return (
    <div className="match-detail-card">
      {/* HEADER */}
      <div className="match-detail-card__header">
        {showBackButton && onBack && (
          <button className="mdc-back-btn" onClick={onBack} aria-label="Voltar">
            <ArrowLeft size={20} />
            <span>Voltar</span>
          </button>
        )}
        <div className="match-detail-card__league">
          {match.league}{match.season ? ` \u2022 ${match.season}` : ""}
        </div>
        <div className="match-detail-card__actions">
          {getStatusBadge()}
          <button
            className="mdc-icon-btn"
            aria-label={isFavorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}
            onClick={onFavorite}
            style={{ color: isFavorite ? "#ffbb33" : undefined }}
          >
            <Star size={18} fill={isFavorite ? "currentColor" : "none"} />
          </button>
          <button className="mdc-icon-btn" aria-label="Link externo">
            <ExternalLink size={18} />
          </button>
        </div>
      </div>

      {/* TEAMS + TIMER */}
      <div className="match-detail-card__teams">
        <div className="mdc-team-logo">
          {match.homeTeamLogo ? (
            <img src={match.homeTeamLogo} alt={match.homeTeam} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          ) : (
            <span>{"\ud83c\udfe0"}</span>
          )}
        </div>

        <div className="match-detail-card__center">
          <h3 className="mdc-team-name">{match.homeTeam}</h3>

          {match.status === "live" ? (
            <div className="mdc-live-score">
              <div className="mdc-live-score__indicator">
                <span className="mdc-live-score__dot" />
                <span className="mdc-live-score__label">AO VIVO</span>
                {match.period && (
                  <span className="mdc-live-score__period">{match.period}</span>
                )}
                {match.minute != null && match.period !== "HT" && (
                  <span className="mdc-live-score__minute">{match.minute}&apos;</span>
                )}
              </div>
              <div className="mdc-live-score__value">
                {typeof match.score?.home === "number" ? match.score.home : 0} - {typeof match.score?.away === "number" ? match.score.away : 0}
              </div>
              {match.score?.halftime && typeof match.score.halftime.home === "number" && (
                <div className="mdc-live-score__ht">
                  HT: {match.score.halftime.home} - {match.score.halftime.away}
                </div>
              )}
            </div>
          ) : match.status === "finished" && match.score ? (
            <div className="mdc-final-score">
              <div className="mdc-final-score__value">
                {typeof match.score.home === "number" ? match.score.home : 0} - {typeof match.score.away === "number" ? match.score.away : 0}
              </div>
              {match.score.halftime && typeof match.score.halftime.home === "number" && (
                <div className="mdc-final-score__ht">
                  HT: {match.score.halftime.home} - {match.score.halftime.away}
                </div>
              )}
            </div>
          ) : timeRemaining ? (
            <div className="mdc-countdown">
              <div className="mdc-countdown__label">Inicia em</div>
              <div className="mdc-countdown__time">
                <span className="mdc-countdown__number">{String(timeRemaining.hours).padStart(2, "0")}</span>
                <span className="mdc-countdown__separator">:</span>
                <span className="mdc-countdown__number">{String(timeRemaining.minutes).padStart(2, "0")}</span>
                <span className="mdc-countdown__separator">:</span>
                <span className="mdc-countdown__number">{String(timeRemaining.seconds).padStart(2, "0")}</span>
              </div>
            </div>
          ) : null}

          {match.leagueId && (
            <span
              className="mdc-link-small"
              style={{ cursor: "pointer", textDecoration: "underline", marginTop: 4, display: "inline-block" }}
              onClick={(e) => {
                e.stopPropagation();
                if (showStandings) {
                  setShowStandings(false);
                  return;
                }
                setStandingsLoading(true);
                setShowStandings(true);
                fetch(`/api/standings?league=${encodeURIComponent(match.leagueId!)}`)
                  .then((r) => r.json())
                  .then((data) => {
                    const rows = data.standings ?? [];
                    if (rows.length === 0) setShowStandings(false);
                    else setStandingsData(rows);
                  })
                  .catch(() => setShowStandings(false))
                  .finally(() => setStandingsLoading(false));
              }}
            >{showStandings ? "Fechar classificacao" : "Ver classificacao"}</span>
          )}

          {showStandings && (
            <div className="mdc-standings" style={{ width: "100%", marginTop: 8, marginBottom: 8, maxHeight: 300, overflowY: "auto", fontSize: "0.75rem" }}>
              {standingsLoading ? (
                <div style={{ textAlign: "center", padding: 12 }}><Loader2 size={16} className="animate-spin" style={{ display: "inline-block" }} /> Carregando...</div>
              ) : standingsData.length > 0 ? (
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "center" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                      <th style={{ padding: "4px 6px", textAlign: "left" }}>#</th>
                      <th style={{ padding: "4px 6px", textAlign: "left" }}>Time</th>
                      <th style={{ padding: "4px 6px" }}>J</th>
                      <th style={{ padding: "4px 6px" }}>V</th>
                      <th style={{ padding: "4px 6px" }}>E</th>
                      <th style={{ padding: "4px 6px" }}>D</th>
                      <th style={{ padding: "4px 6px" }}>Pts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {standingsData.map((team: any, idx: number) => {
                      const name = team.cleanName || team.name || team.team_name || `Time ${idx + 1}`;
                      const isHighlighted = name === match.homeTeam || name === match.awayTeam;
                      return (
                        <tr key={idx} style={{
                          borderBottom: "1px solid rgba(255,255,255,0.05)",
                          background: isHighlighted ? "rgba(255,165,0,0.15)" : "transparent",
                          fontWeight: isHighlighted ? 600 : 400,
                        }}>
                          <td style={{ padding: "3px 6px", textAlign: "left" }}>{team.position ?? idx + 1}</td>
                          <td style={{ padding: "3px 6px", textAlign: "left", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 120 }}>{name}</td>
                          <td style={{ padding: "3px 6px" }}>{team.played ?? team.matchesPlayed ?? "-"}</td>
                          <td style={{ padding: "3px 6px" }}>{team.won ?? team.wins ?? "-"}</td>
                          <td style={{ padding: "3px 6px" }}>{team.drawn ?? team.draws ?? "-"}</td>
                          <td style={{ padding: "3px 6px" }}>{team.lost ?? team.losses ?? "-"}</td>
                          <td style={{ padding: "3px 6px", fontWeight: 700 }}>{team.points ?? team.pts ?? "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: "center", padding: 12, opacity: 0.6 }}>Classificacao indisponivel</div>
              )}
            </div>
          )}

          <h3 className="mdc-team-name">{match.awayTeam}</h3>
        </div>

        <div className="mdc-team-logo">
          {match.awayTeamLogo ? (
            <img src={match.awayTeamLogo} alt={match.awayTeam} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          ) : (
            <span>{"\u2708\ufe0f"}</span>
          )}
        </div>
      </div>

      {/* TABS — logo após os times para ficarem sempre visíveis */}
      <div className="match-detail-card__tabs">
        <button className={`mdc-tab-btn ${activeTab === "pre-game" ? "mdc-tab-btn--active" : ""}`} onClick={() => setActiveTab("pre-game")}>
          Pre-Jogo
        </button>
        <button className={`mdc-tab-btn ${activeTab === "odds" ? "mdc-tab-btn--active" : ""}`} onClick={() => setActiveTab("odds")}>
          Cotacoes
        </button>
        <button className="mdc-tab-btn">
          <span className="mdc-badge-pro">{version}</span>
        </button>
      </div>

      {/* ODDS SECTION — só quando aba Cotacoes ativa */}
      {activeTab === "odds" && (
        <div className="match-detail-card__odds-section">
          <div className="mdc-odds-title">RESULTADO DA PARTIDA</div>
          <div className="mdc-odds-main-grid">
            <div className="mdc-odd-main">
              <span className="mdc-odd-main__label">1</span>
              <span className="mdc-odd-main__value">
                {match.odds?.home?.toFixed(2) ?? "-"}
                {getOddVariation(match.odds?.homeVariation)}
              </span>
            </div>
            <div className="mdc-odd-main">
              <span className="mdc-odd-main__label">X</span>
              <span className="mdc-odd-main__value">
                {match.odds?.draw?.toFixed(2) ?? "-"}
                {getOddVariation(match.odds?.drawVariation)}
              </span>
            </div>
            <div className="mdc-odd-main">
              <span className="mdc-odd-main__label">2</span>
              <span className="mdc-odd-main__value">
                {match.odds?.away?.toFixed(2) ?? "-"}
                {getOddVariation(match.odds?.awayVariation)}
              </span>
            </div>
          </div>

          {/* DUPLA CHANCE */}
          {match.doubleChance && (
            <>
              <div className="mdc-odds-title mt-md">DUPLA CHANCE</div>
              <div className="mdc-odds-secondary-grid">
                <div className="mdc-odd-secondary">
                  <span className="mdc-odd-secondary__label">1X</span>
                  <span className="mdc-odd-secondary__value">{match.doubleChance.homeOrDraw?.toFixed(2) ?? "-"}</span>
                </div>
                <div className="mdc-odd-secondary">
                  <span className="mdc-odd-secondary__label">12</span>
                  <span className="mdc-odd-secondary__value">{match.doubleChance.homeOrAway?.toFixed(2) ?? "-"}</span>
                </div>
                <div className="mdc-odd-secondary">
                  <span className="mdc-odd-secondary__label">X2</span>
                  <span className="mdc-odd-secondary__value">{match.doubleChance.drawOrAway?.toFixed(2) ?? "-"}</span>
                </div>
              </div>
            </>
          )}

          {/* AMBAS MARCAM */}
          {match.btts && (
            <>
              <div className="mdc-odds-title mt-md">AMBAS MARCAM</div>
              <div className="mdc-odds-secondary-grid">
                <div className="mdc-odd-secondary">
                  <span className="mdc-odd-secondary__label">Sim</span>
                  <span className="mdc-odd-secondary__value">{match.btts.yes?.toFixed(2) ?? "-"}</span>
                </div>
                <div className="mdc-odd-secondary">
                  <span className="mdc-odd-secondary__label">Nao</span>
                  <span className="mdc-odd-secondary__value">{match.btts.no?.toFixed(2) ?? "-"}</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* SUB-TABS */}
      {activeTab === "pre-game" && (
        <>
          <div className="match-detail-card__sub-tabs">
            <button className={`mdc-sub-tab-btn ${activeSubTab === "resumo" ? "mdc-sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("resumo")}>
              Resumo
            </button>
            <button className={`mdc-sub-tab-btn ${activeSubTab === "stats" ? "mdc-sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("stats")}>
              Stats
            </button>
            <button className={`mdc-sub-tab-btn ${activeSubTab === "h2h" ? "mdc-sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("h2h")}>
              H2H
            </button>
            <button className={`mdc-sub-tab-btn ${activeSubTab === "ultimos" ? "mdc-sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("ultimos")}>
              Ultimos Jogos
            </button>
          </div>

          {/* RESUMO CONTENT */}
          {activeSubTab === "resumo" && (
            <div className="match-detail-card__content">
              {/* AI ANALYSIS SECTION */}
              <div className="mdc-ai-section">
                <button className="mdc-collapsible-header" onClick={() => setIsAIExpanded(!isAIExpanded)}>
                  <div className="mdc-collapsible-header__left">
                    <Sparkles className="mdc-ai-icon" size={20} />
                    <span className="mdc-collapsible-title">Analise AI (MISTRAL)</span>
                    <span className="mdc-badge-pro" style={{ marginLeft: 8 }}>{version}</span>
                  </div>
                  {isAIExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {isAIExpanded && (
                  <div className="mdc-ai-content">
                    {aiLoading && (
                      <div className="mdc-loading">
                        <Loader2 size={16} className="mdc-loading-spinner" />
                        Gerando analise AI...
                      </div>
                    )}

                    {!aiLoading && match.aiAnalysis && (
                      <>
                        {/* Confidence Bar */}
                        <div className="mdc-confidence">
                          <div className="mdc-confidence__header">
                            <span>Confianca da Analise</span>
                            <span className="mdc-confidence__value">{match.aiAnalysis.confidence}%</span>
                          </div>
                          <div className="mdc-confidence__bar">
                            <div className="mdc-confidence__fill" style={{ width: `${match.aiAnalysis.confidence}%` }} />
                          </div>
                        </div>

                        {/* Summary */}
                        <div className="mdc-ai-summary">
                          <h4 className="mdc-ai-section-title">Resumo</h4>
                          <p className="mdc-ai-text">{fixAiPercentages(match.aiAnalysis.summary ?? "")}</p>
                        </div>

                        {/* Key Points */}
                        {Array.isArray(match.aiAnalysis.key_points) && match.aiAnalysis.key_points.length > 0 && (
                          <div className="mdc-ai-key-points">
                            <h4 className="mdc-ai-section-title">Pontos-Chave</h4>
                            <ul className="mdc-ai-list">
                              {match.aiAnalysis.key_points.map((point, index) => (
                                <li key={index} className="mdc-ai-list-item">
                                  <span className="mdc-ai-bullet">{"\u2022"}</span>
                                  {fixAiPercentages(typeof point === "string" ? point : String(point ?? ""))}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Recommendation */}
                        {match.aiAnalysis.recommendation && (
                          <div className="mdc-ai-recommendation">
                            <h4 className="mdc-ai-section-title">Recomendacao</h4>
                            <div className="mdc-ai-recommendation-box">
                              <Sparkles size={16} className="mdc-ai-recommendation-icon" />
                              <p className="mdc-ai-recommendation-text">{fixAiPercentages(match.aiAnalysis.recommendation ?? "")}</p>
                            </div>
                          </div>
                        )}

                        {/* Timestamp + Regenerate + Audit */}
                        <div className="mdc-ai-timestamp" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            <Clock size={14} />
                            <span>Ultima atualizacao: {match.aiAnalysis.last_updated}</span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                            {onAudit && (
                              <button
                                onClick={onAudit}
                                disabled={auditLoading}
                                style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.7rem", color: "#ffbb33", background: "transparent", border: "none", cursor: auditLoading ? "wait" : "pointer", opacity: auditLoading ? 0.6 : 1 }}
                              >
                                {auditLoading ? <Loader2 size={12} className="mdc-loading-spinner" /> : <ShieldCheck size={12} />}
                                Auditar
                              </button>
                            )}
                            {onRegenerate && (
                              <button
                                onClick={onRegenerate}
                                style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.7rem", color: "#00ff88", background: "transparent", border: "none", cursor: "pointer" }}
                              >
                                <RefreshCw size={12} />
                                Regenerar
                              </button>
                            )}
                          </div>
                        </div>
                      </>
                    )}

                    {!aiLoading && !match.aiAnalysis && (
                      <div style={{ textAlign: "center", fontSize: "0.8rem", color: "#666", padding: 16 }}>
                        <div style={{ marginBottom: 12 }}>Nenhuma análise AI gerada para este jogo.</div>
                        {onRegenerate && (
                          <button
                            onClick={onRegenerate}
                            style={{ padding: "8px 16px", borderRadius: 8, background: "rgba(0,255,136,0.15)", color: "#00ff88", border: "1px solid rgba(0,255,136,0.3)", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600 }}
                          >
                            <Sparkles size={14} />
                            Gerar Análise AI
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* AUDIT RESULTS */}
              {auditResult && (
                <div ref={auditResultRef}>
                  <SafeErrorBoundary section="audit" fallbackMessage="Erro ao exibir resultado da auditoria. Tente novamente.">
                    <AuditResultsSection auditResult={auditResult} onApplyCorrection={onApplyCorrection} />
                  </SafeErrorBoundary>
                </div>
              )}

              {/* VENUE IMAGE */}
              {match.venue?.image && (
                <div className="mdc-venue-image-container">
                  <img src={match.venue.image} alt={match.venue.name} className="mdc-venue-image" />
                </div>
              )}

              {/* MATCH INFO */}
              <div className="mdc-info-grid">
                {match.startTime && (
                  <div className="mdc-info-item">
                    <span className="mdc-info-label">
                      <Clock size={14} /> Data
                    </span>
                    <span className="mdc-info-value">
                      {new Date(match.startTime).toLocaleDateString("pt-BR", {
                        weekday: "long",
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                        timeZone: "America/Sao_Paulo",
                      })}
                      {" às "}
                      {new Date(match.startTime).toLocaleTimeString("pt-BR", {
                        hour: "2-digit",
                        minute: "2-digit",
                        timeZone: "America/Sao_Paulo",
                      })}
                    </span>
                  </div>
                )}
                <div className="mdc-info-item">
                  <span className="mdc-info-label">Competicao</span>
                  <span className="mdc-info-value">{match.league}</span>
                </div>
                {match.season && (
                  <div className="mdc-info-item">
                    <span className="mdc-info-label">Temporada</span>
                    <span className="mdc-info-value">{match.season}</span>
                  </div>
                )}
                {match.round && (
                  <div className="mdc-info-item">
                    <span className="mdc-info-label">Rodada</span>
                    <span className="mdc-info-value">{match.round}</span>
                  </div>
                )}
                {match.venue && (
                  <>
                    <div className="mdc-info-item">
                      <span className="mdc-info-label">
                        <MapPin size={14} /> Estadio
                      </span>
                      <span className="mdc-info-value">{match.venue.name}</span>
                    </div>
                    {match.venue.capacity && (
                      <div className="mdc-info-item">
                        <span className="mdc-info-label">
                          <Users size={14} /> Capacidade
                        </span>
                        <span className="mdc-info-value">{match.venue.capacity.toLocaleString("pt-BR")}</span>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* COMPARATIVE SECTION */}
              <div className="mdc-comparative">
                <button className="mdc-collapsible-header" onClick={() => setIsComparativeExpanded(!isComparativeExpanded)}>
                  <span className="mdc-collapsible-title">Comparativo dos Times</span>
                  {isComparativeExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                {isComparativeExpanded && (
                  <div className="mdc-comparative__content">
                    <div className="mdc-comparative__tabs">
                      {["gols", "perfil", "btts", "escanteios", "chutes", "finalizacoes", "faltas", "cartoes"].map((tab) => (
                        <button
                          key={tab}
                          className={`mdc-comparative__tab ${comparativeTab === tab ? "mdc-comparative__tab--active" : ""}`}
                          onClick={() => setComparativeTab(tab)}
                        >
                          {tab === "gols" ? "Gols" : tab === "perfil" ? "Perfil" : tab === "btts" ? "BTTS" : tab === "escanteios" ? "Escanteios" : tab === "chutes" ? "Chutes ao Gol" : tab === "finalizacoes" ? "Finalizacoes" : tab === "faltas" ? "Faltas" : "Cartoes"}
                        </button>
                      ))}
                    </div>
                    <div style={{ padding: "12px 0" }}>
                      {comparativeTab === "gols" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          <ComparativeBar label="Lambda (Gols Esperados)" homeVal={match.matchStats.lambdaHome ?? 0} awayVal={match.matchStats.lambdaAway ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                          <ComparativeBar label="xG (Gols Esperados)" homeVal={match.matchStats.homeXG ?? 0} awayVal={match.matchStats.awayXG ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                          <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: "0.75rem", color: "#ccc" }}>
                            <span>Media de Gols: {match.matchStats.avgGoals?.toFixed(2) ?? "-"}</span>
                            <span>Over 2.5: {formatProbValue(match.matchStats.over25Prob)}</span>
                          </div>
                        </div>
                      )}
                      {comparativeTab === "perfil" && (() => {
                        const ms = match.matchStats;
                        if (!ms) {
                          return (
                            <div className="mdc-comparative-data" style={{ textAlign: "center", padding: 16 }}>
                              <div style={{ color: "#888", fontSize: "0.75rem" }}>Carregando dados do jogo...</div>
                            </div>
                          );
                        }
                        const hasTeamData = ms.homeXgForAvg != null || ms.homeWinPercentage != null || ms.homeLeaguePosition != null;
                        const hasModelData = (ms.lambdaHome != null && ms.lambdaHome > 0) || (ms.homeWinProb != null && ms.homeWinProb > 0);
                        return (
                        <div className="mdc-comparative-data">
                          {/* Team-level data (from league-teams API) */}
                          {hasTeamData && (
                            <>
                              {(ms.homeXgForAvg != null || ms.awayXgForAvg != null) && (
                                <ComparativeBar label="xG Medio por Jogo" homeVal={ms.homeXgForAvg ?? 0} awayVal={ms.awayXgForAvg ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              )}
                              {(ms.homeXgAgainstAvg != null || ms.awayXgAgainstAvg != null) && (
                                <ComparativeBar label="xG Sofrido por Jogo" homeVal={ms.homeXgAgainstAvg ?? 0} awayVal={ms.awayXgAgainstAvg ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              )}
                              {(ms.homeAvgTotalGoals != null || ms.awayAvgTotalGoals != null) && (
                                <ComparativeBar label="Media Gols Total/Jogo" homeVal={ms.homeAvgTotalGoals ?? 0} awayVal={ms.awayAvgTotalGoals ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              )}
                              <div style={{ display: "flex", justifyContent: "space-around", padding: "10px 0", fontSize: "0.75rem", flexWrap: "wrap", gap: 8 }}>
                                {ms.homeWinPercentage != null && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Vitorias %</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeWinPercentage?.toFixed(0)}%</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayWinPercentage?.toFixed(0) ?? "-"}%</span>
                                  </div>
                                )}
                                {ms.homeOver25Percentage != null && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Over 2.5 %</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeOver25Percentage?.toFixed(0)}%</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayOver25Percentage?.toFixed(0) ?? "-"}%</span>
                                  </div>
                                )}
                                {ms.homeCleanSheetPct != null && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Clean Sheet %</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeCleanSheetPct?.toFixed(0)}%</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayCleanSheetPct?.toFixed(0) ?? "-"}%</span>
                                  </div>
                                )}
                                {ms.homeBttsPercentage != null && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>BTTS %</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeBttsPercentage?.toFixed(0)}%</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayBttsPercentage?.toFixed(0) ?? "-"}%</span>
                                  </div>
                                )}
                                {ms.homeLeaguePosition != null && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Posicao Liga</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeLeaguePosition?.toFixed(0)}o</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayLeaguePosition?.toFixed(0) ?? "-"}o</span>
                                  </div>
                                )}
                              </div>
                            </>
                          )}
                          {/* Model-data fallback: show Poisson model stats when team data unavailable */}
                          {!hasTeamData && hasModelData && (
                            <>
                              <div style={{ fontSize: "0.65rem", color: "#666", textAlign: "center", marginBottom: 8 }}>Analise estatistica (modelo Poisson)</div>
                              <ComparativeBar label="Lambda (Gols Esperados)" homeVal={ms.lambdaHome ?? 0} awayVal={ms.lambdaAway ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              <div style={{ display: "flex", justifyContent: "space-around", padding: "10px 0", fontSize: "0.75rem", flexWrap: "wrap", gap: 8 }}>
                                {ms.homeWinProb != null && ms.homeWinProb > 0 && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Prob. Vitoria</div>
                                    <span style={{ color: "#4fc3f7" }}>{ms.homeWinProb?.toFixed(1)}%</span>
                                    <span style={{ color: "#666" }}> vs </span>
                                    <span style={{ color: "#ff8a65" }}>{ms.awayWinProb?.toFixed(1) ?? "-"}%</span>
                                  </div>
                                )}
                                {ms.drawProb != null && ms.drawProb > 0 && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Empate</div>
                                    <span style={{ color: "#ccc" }}>{ms.drawProb?.toFixed(1)}%</span>
                                  </div>
                                )}
                                {ms.over25Prob != null && ms.over25Prob > 0 && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Over 2.5</div>
                                    <span style={{ color: "#ccc" }}>{ms.over25Prob?.toFixed(1)}%</span>
                                  </div>
                                )}
                                {ms.bttsProb != null && ms.bttsProb > 0 && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>BTTS</div>
                                    <span style={{ color: "#ccc" }}>{ms.bttsProb?.toFixed(1)}%</span>
                                  </div>
                                )}
                                {ms.avgGoals != null && ms.avgGoals > 0 && (
                                  <div style={{ textAlign: "center" }}>
                                    <div style={{ color: "#888", marginBottom: 2 }}>Media Gols</div>
                                    <span style={{ color: "#ccc" }}>{ms.avgGoals?.toFixed(2)}</span>
                                  </div>
                                )}
                              </div>
                            </>
                          )}
                          {/* No data at all */}
                          {!hasTeamData && !hasModelData && (
                            <div style={{ textAlign: "center", padding: 16, color: "#666", fontSize: "0.75rem" }}>
                              Dados de perfil serao exibidos apos o carregamento completo dos jogos.
                            </div>
                          )}
                        </div>
                        );
                      })()}
                      {comparativeTab === "btts" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          <div style={{ textAlign: "center", padding: "8px 0" }}>
                            <span style={{ fontSize: "1.5rem", fontWeight: "bold", color: (match.matchStats.bttsProb ?? 0) >= 55 ? "#00ff88" : (match.matchStats.bttsProb ?? 0) >= 40 ? "#ffbb33" : "#ff4444" }}>
                              {formatProbValue(match.matchStats.bttsProb)}
                            </span>
                            <div style={{ fontSize: "0.7rem", color: "#888", marginTop: 4 }}>Probabilidade BTTS</div>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-around", padding: "8px 0", fontSize: "0.75rem" }}>
                            <div style={{ textAlign: "center" }}><span style={{ color: "#888" }}>Sim</span><br /><span style={{ color: "#00ff88" }}>{match.btts?.yes?.toFixed(2) ?? "-"}</span></div>
                            <div style={{ textAlign: "center" }}><span style={{ color: "#888" }}>Nao</span><br /><span style={{ color: "#ff4444" }}>{match.btts?.no?.toFixed(2) ?? "-"}</span></div>
                          </div>
                        </div>
                      )}
                      {comparativeTab === "escanteios" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          <ComparativeBar label="Escanteios por Jogo" homeVal={match.matchStats.homeCornersPerMatch ?? 0} awayVal={match.matchStats.awayCornersPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                          <div style={{ display: "flex", justifyContent: "center", padding: "8px 0", fontSize: "0.75rem" }}>
                            <span style={{ color: "#888" }}>Media da Liga: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.matchStats.leagueAvgCorners?.toFixed(1) ?? "-"}</span></span>
                          </div>
                          {/* Corner predictions from FootyStats */}
                          {(match.matchStats.cornerOver85Prob != null || match.matchStats.cornerOver95Prob != null || match.matchStats.cornerOver105Prob != null) && (
                            <div style={{ marginTop: 12 }}>
                              <div style={{ fontSize: "0.7rem", color: "#888", marginBottom: 8, textAlign: "center" }}>Prognosticos de Escanteios</div>
                              <div style={{ display: "flex", justifyContent: "space-around", textAlign: "center" }}>
                                {match.matchStats.cornerOver85Prob != null && (
                                  <div>
                                    <div style={{ fontSize: "1rem", fontWeight: "bold", color: (match.matchStats.cornerOver85Prob ?? 0) >= 70 ? "#00ff88" : (match.matchStats.cornerOver85Prob ?? 0) >= 50 ? "#ffbb33" : "#ff4444" }}>
                                      {formatProbValue(match.matchStats.cornerOver85Prob)}
                                    </div>
                                    <div style={{ fontSize: "0.6rem", color: "#888", marginTop: 2 }}>Over 8.5</div>
                                  </div>
                                )}
                                {match.matchStats.cornerOver95Prob != null && (
                                  <div>
                                    <div style={{ fontSize: "1rem", fontWeight: "bold", color: (match.matchStats.cornerOver95Prob ?? 0) >= 65 ? "#00ff88" : (match.matchStats.cornerOver95Prob ?? 0) >= 45 ? "#ffbb33" : "#ff4444" }}>
                                      {formatProbValue(match.matchStats.cornerOver95Prob)}
                                    </div>
                                    <div style={{ fontSize: "0.6rem", color: "#888", marginTop: 2 }}>Over 9.5</div>
                                  </div>
                                )}
                                {match.matchStats.cornerOver105Prob != null && (
                                  <div>
                                    <div style={{ fontSize: "1rem", fontWeight: "bold", color: (match.matchStats.cornerOver105Prob ?? 0) >= 55 ? "#00ff88" : (match.matchStats.cornerOver105Prob ?? 0) >= 35 ? "#ffbb33" : "#ff4444" }}>
                                      {formatProbValue(match.matchStats.cornerOver105Prob)}
                                    </div>
                                    <div style={{ fontSize: "0.6rem", color: "#888", marginTop: 2 }}>Over 10.5</div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                          {(!match.matchStats.homeCornersPerMatch && !match.matchStats.awayCornersPerMatch && !match.matchStats.cornerOver85Prob) && (
                            <div style={{ textAlign: "center", padding: "8px 0", fontSize: "0.7rem", color: "#666" }}>Dados de escanteios nao disponiveis para este jogo.</div>
                          )}
                        </div>
                      )}
                      {comparativeTab === "cartoes" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          <ComparativeBar label="Cartoes por Jogo" homeVal={match.matchStats.homeCardsPerMatch ?? 0} awayVal={match.matchStats.awayCardsPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                          <div style={{ display: "flex", justifyContent: "center", padding: "8px 0", fontSize: "0.75rem" }}>
                            <span style={{ color: "#888" }}>Media da Liga: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.matchStats.leagueAvgCards?.toFixed(1) ?? "-"}</span></span>
                          </div>
                          {(!match.matchStats.homeCardsPerMatch && !match.matchStats.awayCardsPerMatch) && (
                            <div style={{ textAlign: "center", padding: "8px 0", fontSize: "0.7rem", color: "#666" }}>Dados de cartoes nao disponiveis para este jogo.</div>
                          )}
                        </div>
                      )}
                      {comparativeTab === "chutes" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          {(match.matchStats.homeShotsOnTarget != null || match.matchStats.awayShotsOnTarget != null) ? (
                            <ComparativeBar label="Chutes ao Gol por Jogo" homeVal={match.matchStats.homeShotsOnTarget ?? 0} awayVal={match.matchStats.awayShotsOnTarget ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                          ) : (
                            <div style={{ textAlign: "center", padding: "8px 0", fontSize: "0.7rem", color: "#666" }}>Dados de chutes ao gol nao disponiveis para este jogo.</div>
                          )}
                        </div>
                      )}
                      {comparativeTab === "finalizacoes" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          {(match.matchStats.homeShotsPerMatch != null || match.matchStats.awayShotsPerMatch != null) ? (
                            <>
                              <ComparativeBar label="Finalizacoes por Jogo" homeVal={match.matchStats.homeShotsPerMatch ?? 0} awayVal={match.matchStats.awayShotsPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              <div style={{ display: "flex", justifyContent: "center", padding: "8px 0", fontSize: "0.75rem" }}>
                                <span style={{ color: "#888" }}>Media da Liga: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.matchStats.leagueAvgShots?.toFixed(1) ?? "-"}</span></span>
                              </div>
                            </>
                          ) : (
                            <div style={{ textAlign: "center", padding: "8px 0", fontSize: "0.7rem", color: "#666" }}>Dados de finalizacoes nao disponiveis para este jogo.</div>
                          )}
                        </div>
                      )}
                      {comparativeTab === "faltas" && match.matchStats && (
                        <div className="mdc-comparative-data">
                          {(match.matchStats.homeFoulsPerMatch != null || match.matchStats.awayFoulsPerMatch != null) ? (
                            <>
                              <ComparativeBar label="Faltas por Jogo" homeVal={match.matchStats.homeFoulsPerMatch ?? 0} awayVal={match.matchStats.awayFoulsPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                              <div style={{ display: "flex", justifyContent: "center", padding: "8px 0", fontSize: "0.75rem" }}>
                                <span style={{ color: "#888" }}>Media da Liga: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.matchStats.leagueAvgFouls?.toFixed(1) ?? "-"}</span></span>
                              </div>
                            </>
                          ) : (
                            <div style={{ textAlign: "center", padding: "8px 0", fontSize: "0.7rem", color: "#666" }}>Dados de faltas nao disponiveis para este jogo.</div>
                          )}
                        </div>
                      )}
                      {comparativeTab === "gols" && !match.matchStats && (
                        <div style={{ textAlign: "center", padding: "16px 0", fontSize: "0.75rem", color: "#666" }}>
                          Dados estatisticos nao disponiveis para este jogo.
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STATS TAB CONTENT */}
          {activeSubTab === "stats" && (
            <div className="match-detail-card__content">
              {match.matchStats ? (
                <div className="mdc-stats-content">
                  <h4 className="mdc-section-title">Probabilidades</h4>
                  <div className="mdc-stats-grid">
                    <StatRow label="Vitoria Casa" value={formatProbValue(match.matchStats.homeWinProb)} />
                    <StatRow label="Empate" value={formatProbValue(match.matchStats.drawProb)} />
                    <StatRow label="Vitoria Fora" value={formatProbValue(match.matchStats.awayWinProb)} />
                  </div>

                  <h4 className="mdc-section-title" style={{ marginTop: 16 }}>Gols</h4>
                  <div className="mdc-stats-grid">
                    <StatRow label="Media de Gols" value={match.matchStats.avgGoals?.toFixed(2) ?? "-"} />
                    <StatRow label="Lambda Casa" value={match.matchStats.lambdaHome?.toFixed(2) ?? "-"} />
                    <StatRow label="Lambda Fora" value={match.matchStats.lambdaAway?.toFixed(2) ?? "-"} />
                  </div>

                  <h4 className="mdc-section-title" style={{ marginTop: 16 }}>Over/Under</h4>
                  <div className="mdc-stats-grid">
                    {match.matchStats.over15Prob != null && <StatRow label="Over 1.5" value={formatProbValue(match.matchStats.over15Prob)} />}
                    <StatRow label="Over 2.5" value={formatProbValue(match.matchStats.over25Prob)} />
                    {match.matchStats.over35Prob != null && <StatRow label="Over 3.5" value={formatProbValue(match.matchStats.over35Prob)} />}
                    {match.matchStats.over45Prob != null && <StatRow label="Over 4.5" value={formatProbValue(match.matchStats.over45Prob)} />}
                    <StatRow label="BTTS" value={formatProbValue(match.matchStats.bttsProb)} />
                  </div>

                  {(match.matchStats.homePossession != null || match.matchStats.homeXG != null) && (
                    <>
                      <h4 className="mdc-section-title" style={{ marginTop: 16 }}>Desempenho</h4>
                      <ComparativeBar label="Posse de Bola" homeVal={match.matchStats.homePossession ?? 50} awayVal={match.matchStats.awayPossession ?? 50} homeTeam={match.homeTeam} awayTeam={match.awayTeam} suffix="%" />
                      <ComparativeBar label="xG" homeVal={match.matchStats.homeXG ?? 0} awayVal={match.matchStats.awayXG ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                    </>
                  )}

                  {(match.matchStats.homeCornersPerMatch != null || match.matchStats.homeCardsPerMatch != null || match.matchStats.cornerOver85Prob != null) && (
                    <>
                      <h4 className="mdc-section-title" style={{ marginTop: 16 }}>Escanteios & Cartoes</h4>
                      {match.matchStats.homeCornersPerMatch != null && (
                        <ComparativeBar label="Escanteios/Jogo" homeVal={match.matchStats.homeCornersPerMatch} awayVal={match.matchStats.awayCornersPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                      )}
                      {(match.matchStats.cornerOver85Prob != null || match.matchStats.cornerOver95Prob != null || match.matchStats.cornerOver105Prob != null) && (
                        <div className="mdc-stats-grid" style={{ marginTop: 8 }}>
                          {match.matchStats.cornerOver85Prob != null && <StatRow label="Escanteios Over 8.5" value={formatProbValue(match.matchStats.cornerOver85Prob)} />}
                          {match.matchStats.cornerOver95Prob != null && <StatRow label="Escanteios Over 9.5" value={formatProbValue(match.matchStats.cornerOver95Prob)} />}
                          {match.matchStats.cornerOver105Prob != null && <StatRow label="Escanteios Over 10.5" value={formatProbValue(match.matchStats.cornerOver105Prob)} />}
                        </div>
                      )}
                      {match.matchStats.homeCardsPerMatch != null && (
                        <ComparativeBar label="Cartoes/Jogo" homeVal={match.matchStats.homeCardsPerMatch} awayVal={match.matchStats.awayCardsPerMatch ?? 0} homeTeam={match.homeTeam} awayTeam={match.awayTeam} />
                      )}
                    </>
                  )}

                  {match.matchStats.leagueRegime && (
                    <div style={{ marginTop: 16, padding: "8px 12px", background: "rgba(0,255,136,0.05)", borderRadius: 6, fontSize: "0.75rem" }}>
                      <span style={{ color: "#888" }}>Regime da Liga: </span>
                      <span style={{ color: match.matchStats.leagueRegime === "HIPER-OFENSIVA" ? "#00ff88" : "#ffbb33", fontWeight: 600 }}>
                        {match.matchStats.leagueRegime}
                      </span>
                      {match.matchStats.leagueVolatility && (
                        <span style={{ marginLeft: 12, color: "#888" }}>
                          Volatilidade: <span style={{ color: "#ccc" }}>{match.matchStats.leagueVolatility}</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "24px 0", fontSize: "0.8rem", color: "#666" }}>
                  Dados estatisticos nao disponiveis para este jogo.
                </div>
              )}
            </div>
          )}

          {/* H2H TAB CONTENT */}
          {activeSubTab === "h2h" && (
            <div className="match-detail-card__content">
              {match.h2h && match.h2h.totalMatches && match.h2h.totalMatches > 0 ? (
                <div className="mdc-h2h-content">
                  <h4 className="mdc-section-title">Confrontos Diretos</h4>
                  {match.season && (
                    <div style={{ fontSize: "0.7rem", color: "#888", marginBottom: 8 }}>
                      Temporada: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.season}</span>
                    </div>
                  )}
                  <div style={{ textAlign: "center", padding: "12px 0" }}>
                    <span style={{ fontSize: "2rem", fontWeight: "bold", color: "#00ff88" }}>{match.h2h.totalMatches}</span>
                    <div style={{ fontSize: "0.7rem", color: "#888", marginTop: 4 }}>Total de Jogos</div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-around", padding: "16px 0", textAlign: "center" }}>
                    <div>
                      <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#00ff88" }}>{match.h2h.homeWins ?? 0}</div>
                      <div style={{ fontSize: "0.65rem", color: "#888", marginTop: 2 }}>{match.homeTeam}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#ffbb33" }}>{match.h2h.draws ?? 0}</div>
                      <div style={{ fontSize: "0.65rem", color: "#888", marginTop: 2 }}>Empates</div>
                    </div>
                    <div>
                      <div style={{ fontSize: "1.2rem", fontWeight: "bold", color: "#ff4444" }}>{match.h2h.awayWins ?? 0}</div>
                      <div style={{ fontSize: "0.65rem", color: "#888", marginTop: 2 }}>{match.awayTeam}</div>
                    </div>
                  </div>

                  {/* H2H Bar */}
                  {match.h2h.totalMatches > 0 && (
                    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginTop: 8 }}>
                      <div style={{ width: `${((match.h2h.homeWins ?? 0) / match.h2h.totalMatches) * 100}%`, background: "#00ff88" }} />
                      <div style={{ width: `${((match.h2h.draws ?? 0) / match.h2h.totalMatches) * 100}%`, background: "#ffbb33" }} />
                      <div style={{ width: `${((match.h2h.awayWins ?? 0) / match.h2h.totalMatches) * 100}%`, background: "#ff4444" }} />
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 16, fontSize: "0.75rem" }}>
                    <span style={{ color: "#888" }}>Media de Gols: <span style={{ color: "#ccc", fontWeight: 600 }}>{match.h2h.avgGoals?.toFixed(2) ?? "-"}</span></span>
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "24px 0", fontSize: "0.8rem", color: "#666" }}>
                  Dados de confronto direto nao disponiveis.
                </div>
              )}
            </div>
          )}

          {/* ULTIMOS JOGOS TAB CONTENT */}
          {activeSubTab === "ultimos" && (
            <div className="match-detail-card__content">
              <h4 className="mdc-section-title">Forma Recente</h4>
              <div style={{ padding: "8px 0" }}>
                <FormDisplay label={match.homeTeam} form={match.homeForm} />
                <FormDisplay label={match.awayTeam} form={match.awayForm} />
              </div>
              {(!match.homeForm || match.homeForm.length === 0) && (!match.awayForm || match.awayForm.length === 0) && (
                <div style={{ textAlign: "center", padding: "16px 0", fontSize: "0.8rem", color: "#666" }}>
                  Dados de forma recente nao disponiveis.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── SUB-COMPONENTS ── */

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.75rem" }}>
      <span style={{ color: "#888" }}>{label}</span>
      <span style={{ color: "#e0e0e0", fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function ComparativeBar({ label, homeVal, awayVal, homeTeam, awayTeam, suffix = "" }: { label: string; homeVal: number; awayVal: number; homeTeam: string; awayTeam: string; suffix?: string }) {
  const total = homeVal + awayVal || 1;
  const homePct = (homeVal / total) * 100;
  return (
    <div style={{ padding: "8px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#888", marginBottom: 4 }}>
        <span>{homeTeam}: {homeVal.toFixed(2)}{suffix}</span>
        <span style={{ fontSize: "0.6rem" }}>{label}</span>
        <span>{awayTeam}: {awayVal.toFixed(2)}{suffix}</span>
      </div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: "rgba(255,255,255,0.05)" }}>
        <div style={{ width: `${homePct}%`, background: "#00ff88", transition: "width 0.3s" }} />
        <div style={{ width: `${100 - homePct}%`, background: "#ff4444", transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

function FormDisplay({ label, form }: { label: string; form?: string[] }) {
  if (!form || form.length === 0) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
      <span style={{ fontSize: "0.7rem", color: "#888", minWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      <div style={{ display: "flex", gap: 4 }}>
        {form.map((result, i) => {
          const r = result.toUpperCase();
          const color = r === "W" ? "#00ff88" : r === "D" ? "#ffbb33" : "#ff4444";
          const lbl = r === "W" ? "V" : r === "D" ? "E" : "D";
          return (
            <div
              key={i}
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                background: color,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.6rem",
                fontWeight: "bold",
                color: "#000",
              }}
            >
              {lbl}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── AUDIT RESULTS SECTION ── */

/** Safely coerce ANY value from Mistral LLM to a renderable string.
 *  Mistral may return objects/arrays where strings are expected. */
function safeStr(v: unknown, fallback = ""): string {
  if (v == null) return fallback;
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try { return JSON.stringify(v); } catch { return fallback; }
}

/** Safely extract a number, or return undefined */
function safeNum(v: unknown): number | undefined {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string") { const n = parseFloat(v); if (!Number.isNaN(n)) return n; }
  return undefined;
}

function AuditStatusBadge({ status }: { status: unknown }) {
  const s = safeStr(status, "UNKNOWN").toUpperCase();
  const color = s === "OK" ? "#00ff88" : s === "WARNING" ? "#ffbb33" : "#ff4444";
  return (
    <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: "0.65rem", fontWeight: 700, color: "#000", background: color }}>
      {s}
    </span>
  );
}

function AuditResultsSection({ auditResult, onApplyCorrection }: { auditResult: AuditResult; onApplyCorrection?: (c: AuditCorrection) => void }) {
  // Defensive: ensure auditResult is an object
  if (!auditResult || typeof auditResult !== "object") return null;

  const picks = Array.isArray(auditResult.picks_evaluation) ? auditResult.picks_evaluation : [];
  const validation = auditResult.validation && typeof auditResult.validation === "object" ? auditResult.validation : null;
  const probs = validation?.probabilities && typeof validation.probabilities === "object" ? validation.probabilities : null;
  const lambdas = validation?.lambdas && typeof validation.lambdas === "object" ? validation.lambdas : null;
  const ev = validation?.ev && typeof validation.ev === "object" ? validation.ev : null;
  const biases = Array.isArray(auditResult.biases_detected) ? auditResult.biases_detected : [];
  const suggestions = Array.isArray(auditResult.suggestions) ? auditResult.suggestions : [];
  const corrections = Array.isArray(auditResult.corrections) ? auditResult.corrections : [];
  const brierScore = safeNum(probs?.brier_score);
  const predictedTotal = safeNum(lambdas?.predicted_total);
  const actualTotal = safeNum(lambdas?.actual_total);
  const confidenceNum = safeNum(auditResult.audit_confidence) ?? 0;

  return (
    <div className="mdc-audit-section">
      {/* Header */}
      <div className="mdc-audit-header">
        <ShieldCheck size={18} style={{ color: "#ffbb33" }} />
        <span className="mdc-audit-title">Resultado da Auditoria</span>
        <span className="mdc-audit-confidence">
          Confianca: <strong>{confidenceNum}%</strong>
        </span>
      </div>

      {/* Picks Evaluation */}
      {picks.length > 0 && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Avaliacao dos Prognosticos</h4>
          <div className="mdc-audit-picks-table">
            <div className="mdc-audit-picks-row mdc-audit-picks-row--header">
              <span>Mercado</span>
              <span>Status</span>
              <span>Resultado</span>
            </div>
            {picks.map((pick, i) => {
              const resultado = safeStr(pick?.resultado);
              const isHit = resultado.toUpperCase().includes("ACERT");
              return (
                <div key={i} className="mdc-audit-picks-row">
                  <span className="mdc-audit-pick-market">{safeStr(pick?.mercado)}</span>
                  <span className="mdc-audit-pick-status">{safeStr(pick?.status_pick)}</span>
                  <span style={{ color: isHit ? "#00ff88" : "#ff4444", fontWeight: 600, fontSize: "0.75rem" }}>
                    {resultado}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Validation Grid */}
      {validation && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Validacao</h4>
          <div className="mdc-audit-validation-grid">
            {/* Probabilities */}
            {probs && (
              <div className="mdc-audit-validation-card">
                <div className="mdc-audit-validation-card-header">
                  <span>Probabilidades</span>
                  <AuditStatusBadge status={probs.status} />
                </div>
                <p className="mdc-audit-validation-notes">{safeStr(probs.notes)}</p>
                {brierScore != null && (
                  <div className="mdc-audit-validation-metric">
                    Brier Score: <strong>{brierScore.toFixed(3)}</strong>
                  </div>
                )}
              </div>
            )}
            {/* Lambdas */}
            {lambdas && (
              <div className="mdc-audit-validation-card">
                <div className="mdc-audit-validation-card-header">
                  <span>Lambdas</span>
                  <AuditStatusBadge status={lambdas.status} />
                </div>
                <p className="mdc-audit-validation-notes">{safeStr(lambdas.notes)}</p>
                {predictedTotal != null && (
                  <div className="mdc-audit-validation-metric">
                    Previsto: <strong>{predictedTotal.toFixed(1)}</strong>
                    {actualTotal != null && (
                      <> | Real: <strong>{actualTotal}</strong></>
                    )}
                  </div>
                )}
              </div>
            )}
            {/* EV */}
            {ev && (
              <div className="mdc-audit-validation-card">
                <div className="mdc-audit-validation-card-header">
                  <span>Expected Value</span>
                  <AuditStatusBadge status={ev.status} />
                </div>
                <p className="mdc-audit-validation-notes">{safeStr(ev.notes)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Analysis Accuracy */}
      {auditResult.ai_analysis_accuracy && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Precisao da Analise Mistral</h4>
          <p className="mdc-audit-text">{safeStr(auditResult.ai_analysis_accuracy)}</p>
        </div>
      )}

      {/* Accuracy Summary */}
      {auditResult.accuracy_summary && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Resumo de Precisao</h4>
          <p className="mdc-audit-text">{safeStr(auditResult.accuracy_summary)}</p>
        </div>
      )}

      {/* Biases Detected */}
      {biases.length > 0 && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title" style={{ color: "#ff4444" }}>Vieses Detectados</h4>
          <ul className="mdc-audit-biases-list">
            {biases.map((bias, i) => (
              <li key={i} className="mdc-audit-bias-item">{safeStr(bias)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Sugestoes</h4>
          <ul className="mdc-audit-biases-list" style={{ borderLeftColor: "#ffbb33" }}>
            {suggestions.map((sug, i) => (
              <li key={i} className="mdc-audit-bias-item">{safeStr(sug)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Corrections */}
      {corrections.length > 0 && (
        <div className="mdc-audit-block">
          <h4 className="mdc-audit-block-title">Correcoes Sugeridas</h4>
          <div className="mdc-audit-corrections">
            {corrections.map((corr, i) => {
              if (!corr || typeof corr !== "object") return null;
              const impact = safeStr(corr.impact, "LOW").toUpperCase();
              const impactColor = impact === "HIGH" ? "#ff4444" : impact === "MEDIUM" ? "#ffbb33" : "#00ff88";
              const currentVal = safeNum(corr.current_value);
              const suggestedVal = safeNum(corr.suggested_value);
              const corrConfidence = safeNum(corr.confidence) ?? 0;
              return (
                <div key={i} className="mdc-audit-correction-card">
                  <div className="mdc-audit-correction-header">
                    <span className="mdc-audit-correction-param">{safeStr(corr.parameter)}</span>
                    <span className="mdc-audit-correction-impact" style={{ color: impactColor }}>{impact}</span>
                  </div>
                  <div className="mdc-audit-correction-values">
                    <span className="mdc-audit-correction-old">{currentVal != null ? (Number.isInteger(currentVal) ? String(currentVal) : currentVal.toFixed(2)) : safeStr(corr.current_value, "-")}</span>
                    <span className="mdc-audit-correction-arrow">{"\u2192"}</span>
                    <span className="mdc-audit-correction-new">{suggestedVal != null ? (Number.isInteger(suggestedVal) ? String(suggestedVal) : suggestedVal.toFixed(2)) : safeStr(corr.suggested_value, "-")}</span>
                  </div>
                  <p className="mdc-audit-correction-reason">{safeStr(corr.reason)}</p>
                  <div className="mdc-audit-correction-footer">
                    <span style={{ fontSize: "0.65rem", color: "#888" }}>Confianca: {corrConfidence}%</span>
                    {onApplyCorrection && (
                      <button
                        className="mdc-audit-apply-btn"
                        onClick={() => onApplyCorrection(corr)}
                      >
                        Aplicar Correcao
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Timestamp */}
      {auditResult.timestamp && (
        <div className="mdc-audit-footer">
          <Clock size={12} />
          <span>Auditoria: {safeStr(auditResult.timestamp)}</span>
          {auditResult.audit_type && <span> | Tipo: {safeStr(auditResult.audit_type)}</span>}
        </div>
      )}
    </div>
  );
}
