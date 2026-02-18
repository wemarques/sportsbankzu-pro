// frontend/next/components/MatchDetailCard.tsx
"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import "../styles/match-detail-card.css";

export interface AIAnalysis {
  summary: string;
  key_points: string[];
  recommendation: string;
  confidence: number;
  last_updated: string;
}

// Alias for backward compatibility with V0 dashboard
export type MatchDetail = MatchDetailData;

export interface MatchDetailData {
  id: string;
  league: string;
  season?: string;
  homeTeam: string;
  awayTeam: string;
  homeTeamLogo?: string;
  awayTeamLogo?: string;
  startTime?: string;
  status?: "scheduled" | "live" | "finished";
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
  round?: string;
  aiAnalysis?: AIAnalysis;
}

type Props = {
  match: MatchDetailData;
  aiLoading?: boolean;
  onRegenerate?: () => void;
  version?: string;
};

export default function MatchDetailCard({ match, aiLoading, onRegenerate, version = "pro V2.2" }: Props) {
  const [activeTab, setActiveTab] = useState<"pre-game" | "odds" | "stats" | "h2h">("pre-game");
  const [activeSubTab, setActiveSubTab] = useState<"resumo" | "stats" | "h2h" | "ultimos">("resumo");
  const [isAIExpanded, setIsAIExpanded] = useState(true);
  const [isComparativeExpanded, setIsComparativeExpanded] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<{ hours: number; minutes: number; seconds: number } | null>(null);

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
        <div className="match-detail-card__league">
          {match.league}{match.season ? ` \u2022 ${match.season}` : ""}
        </div>
        <div className="match-detail-card__actions">
          {getStatusBadge()}
          <button className="mdc-icon-btn" aria-label="Favoritar">
            <Star size={18} />
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

          {timeRemaining && (
            <div className="mdc-countdown">
              <div className="mdc-countdown__label">Inicia em</div>
              <div className="mdc-countdown__time">
                <span className="mdc-countdown__number">{String(timeRemaining.hours).padStart(2, "0")}</span>
                <span className="mdc-countdown__separator">:</span>
                <span className="mdc-countdown__number">{String(timeRemaining.minutes).padStart(2, "0")}</span>
                <span className="mdc-countdown__separator">:</span>
                <span className="mdc-countdown__number">{String(timeRemaining.seconds).padStart(2, "0")}</span>
              </div>
              <span className="mdc-link-small">Ver classificacao</span>
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

      {/* ODDS SECTION */}
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

      {/* TABS */}
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
                          <p className="mdc-ai-text">{match.aiAnalysis.summary}</p>
                        </div>

                        {/* Key Points */}
                        <div className="mdc-ai-key-points">
                          <h4 className="mdc-ai-section-title">Pontos-Chave</h4>
                          <ul className="mdc-ai-list">
                            {match.aiAnalysis.key_points.map((point, index) => (
                              <li key={index} className="mdc-ai-list-item">
                                <span className="mdc-ai-bullet">{"\u2022"}</span>
                                {point}
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Recommendation */}
                        {match.aiAnalysis.recommendation && (
                          <div className="mdc-ai-recommendation">
                            <h4 className="mdc-ai-section-title">Recomendacao</h4>
                            <div className="mdc-ai-recommendation-box">
                              <Sparkles size={16} className="mdc-ai-recommendation-icon" />
                              <p className="mdc-ai-recommendation-text">{match.aiAnalysis.recommendation}</p>
                            </div>
                          </div>
                        )}

                        {/* Timestamp + Regenerate */}
                        <div className="mdc-ai-timestamp" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            <Clock size={14} />
                            <span>Ultima atualizacao: {match.aiAnalysis.last_updated}</span>
                          </div>
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
                      </>
                    )}

                    {!aiLoading && !match.aiAnalysis && (
                      <div style={{ textAlign: "center", fontSize: "0.8rem", color: "#666", padding: 16 }}>
                        Analise AI nao disponivel para este jogo.
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* VENUE IMAGE */}
              {match.venue?.image && (
                <div className="mdc-venue-image-container">
                  <img src={match.venue.image} alt={match.venue.name} className="mdc-venue-image" />
                </div>
              )}

              {/* MATCH INFO */}
              <div className="mdc-info-grid">
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
                      <button className="mdc-comparative__tab mdc-comparative__tab--active">Gols</button>
                      <button className="mdc-comparative__tab">BTTS</button>
                      <button className="mdc-comparative__tab">Escanteios</button>
                      <button className="mdc-comparative__tab">Chutes ao Gol</button>
                      <button className="mdc-comparative__tab">Finalizacoes</button>
                      <button className="mdc-comparative__tab">Faltas</button>
                      <button className="mdc-comparative__tab">Cartoes</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
