"use client";

import React, { useState } from "react";
import { Clock, MapPin, Users, Star, ExternalLink, ChevronDown, ChevronUp, Sparkles } from "lucide-react";

export type MatchDetail = {
  id: string;
  league: string;
  season: string;
  homeTeam: string;
  awayTeam: string;
  homeTeamLogo?: string;
  awayTeamLogo?: string;
  startTime: string;
  status: "scheduled" | "live" | "finished";
  venue: {
    name: string;
    capacity: number;
    image?: string;
  };
  odds: {
    home: number;
    draw: number;
    away: number;
    homeVariation?: "up" | "down";
    drawVariation?: "up" | "down";
    awayVariation?: "up" | "down";
  };
  doubleChance: {
    homeOrDraw: number;
    homeOrAway: number;
    drawOrAway: number;
  };
  btts: {
    yes: number;
    no: number;
  };
  round?: string;
  aiAnalysis?: {
    summary: string;
    keyPoints: string[];
    recommendation: string;
    confidence: number;
    lastUpdated: string;
  };
};

interface MatchDetailCardProps {
  match: MatchDetail;
}

export default function MatchDetailCard({ match }: MatchDetailCardProps) {
  const [activeTab, setActiveTab] = useState<"pre-game" | "odds" | "stats" | "h2h">("pre-game");
  const [activeSubTab, setActiveSubTab] = useState<"resumo" | "stats" | "h2h" | "ultimos">("resumo");
  const [isComparativeExpanded, setIsComparativeExpanded] = useState(false);
  const [isAIAnalysisExpanded, setIsAIAnalysisExpanded] = useState(true);
  const aiFallback = {
    summary: "Análise Mistral indisponível no momento.",
    keyPoints: ["Sem dados suficientes para gerar insights detalhados."],
    recommendation: "Nenhuma recomendação disponível.",
    confidence: 0,
    lastUpdated: "—",
  };
  const ai = match.aiAnalysis ?? aiFallback;

  const getTimeRemaining = () => {
    const now = new Date();
    const start = new Date(match.startTime);
    const diff = start.getTime() - now.getTime();
    if (diff <= 0) return null;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    return { hours, minutes, seconds };
  };

  const timeRemaining = getTimeRemaining();

  const getOddVariationIcon = (variation?: "up" | "down") => {
    if (!variation) return null;
    return variation === "up" ? "↑" : "↓";
  };

  const getStatusBadge = () => {
    switch (match.status) {
      case "scheduled":
        return <span className="badge badge-upcoming">AGENDADO</span>;
      case "live":
        return <span className="badge badge-live">● AO VIVO</span>;
      case "finished":
        return <span className="badge badge-finished">ENCERRADO</span>;
      default:
        return null;
    }
  };

  return (
    <div className="match-detail-card">
      <div className="match-detail-card__header">
        <div className="match-detail-card__league">
          {match.league} • {match.season}
        </div>
        <div className="match-detail-card__actions">
          {getStatusBadge()}
          <button className="icon-btn" aria-label="Favoritar">
            <Star size={18} />
          </button>
          <button className="icon-btn" aria-label="Link externo">
            <ExternalLink size={18} />
          </button>
        </div>
      </div>

      <div className="match-detail-card__teams">
        <div className="team-logo">
          {match.homeTeamLogo ? <img src={match.homeTeamLogo} alt={match.homeTeam} /> : <div className="team-logo-placeholder">🏠</div>}
        </div>

        <div className="match-detail-card__center">
          <h3 className="team-name">{match.homeTeam}</h3>

          {timeRemaining && (
            <div className="countdown-timer">
              <div className="countdown-label">Inicia em</div>
              <div className="countdown-time">
                <span className="countdown-number">{String(timeRemaining.hours).padStart(2, "0")}</span>
                <span className="countdown-separator">:</span>
                <span className="countdown-number">{String(timeRemaining.minutes).padStart(2, "0")}</span>
                <span className="countdown-separator">:</span>
                <span className="countdown-number">{String(timeRemaining.seconds).padStart(2, "0")}</span>
              </div>
              <a href="#" className="link-small">Ver classificação</a>
            </div>
          )}

          <h3 className="team-name">{match.awayTeam}</h3>
        </div>

        <div className="team-logo">
          {match.awayTeamLogo ? <img src={match.awayTeamLogo} alt={match.awayTeam} /> : <div className="team-logo-placeholder">✈️</div>}
        </div>
      </div>

      <div className="match-detail-card__odds-section">
        <div className="odds-section-title">RESULTADO DA PARTIDA</div>
        <div className="odds-main-grid">
          <div className="odd-main-item">
            <span className="odd-main-label">1</span>
            <span className="odd-main-value">
              {match.odds.home.toFixed(2)}
              <span className={`odd-variation odd-variation--${match.odds.homeVariation}`}>
                {getOddVariationIcon(match.odds.homeVariation)}
              </span>
            </span>
          </div>
          <div className="odd-main-item">
            <span className="odd-main-label">X</span>
            <span className="odd-main-value">
              {match.odds.draw.toFixed(2)}
              <span className={`odd-variation odd-variation--${match.odds.drawVariation}`}>
                {getOddVariationIcon(match.odds.drawVariation)}
              </span>
            </span>
          </div>
          <div className="odd-main-item">
            <span className="odd-main-label">2</span>
            <span className="odd-main-value">
              {match.odds.away.toFixed(2)}
              <span className={`odd-variation odd-variation--${match.odds.awayVariation}`}>
                {getOddVariationIcon(match.odds.awayVariation)}
              </span>
            </span>
          </div>
        </div>

        <div className="odds-section-title mt-md">DUPLA CHANCE</div>
        <div className="odds-secondary-grid">
          <div className="odd-secondary-item">
            <span className="odd-secondary-label">1X</span>
            <span className="odd-secondary-value">{match.doubleChance.homeOrDraw.toFixed(2)}</span>
          </div>
          <div className="odd-secondary-item">
            <span className="odd-secondary-label">12</span>
            <span className="odd-secondary-value">{match.doubleChance.homeOrAway.toFixed(2)}</span>
          </div>
          <div className="odd-secondary-item">
            <span className="odd-secondary-label">X2</span>
            <span className="odd-secondary-value">{match.doubleChance.drawOrAway.toFixed(2)}</span>
          </div>
        </div>

        <div className="odds-section-title mt-md">AMBAS MARCAM</div>
        <div className="odds-secondary-grid">
          <div className="odd-secondary-item">
            <span className="odd-secondary-label">Sim</span>
            <span className="odd-secondary-value">{match.btts.yes.toFixed(2)}</span>
          </div>
          <div className="odd-secondary-item">
            <span className="odd-secondary-label">Não</span>
            <span className="odd-secondary-value">{match.btts.no.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div className="match-detail-card__tabs">
        <button className={`tab-btn ${activeTab === "pre-game" ? "tab-btn--active" : ""}`} onClick={() => setActiveTab("pre-game")}>
          Pré-Jogo
        </button>
        <button className={`tab-btn ${activeTab === "odds" ? "tab-btn--active" : ""}`} onClick={() => setActiveTab("odds")}>
          Cotações
        </button>
        <button className="tab-btn">
          <span className="badge-pro">PRO</span>
        </button>
      </div>

      {activeTab === "pre-game" && (
        <>
          <div className="match-detail-card__sub-tabs">
            <button className={`sub-tab-btn ${activeSubTab === "resumo" ? "sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("resumo")}>
              Resumo
            </button>
            <button className={`sub-tab-btn ${activeSubTab === "stats" ? "sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("stats")}>
              Stats
            </button>
            <button className={`sub-tab-btn ${activeSubTab === "h2h" ? "sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("h2h")}>
              H2H
            </button>
            <button className={`sub-tab-btn ${activeSubTab === "ultimos" ? "sub-tab-btn--active" : ""}`} onClick={() => setActiveSubTab("ultimos")}>
              Últimos Jogos
            </button>
          </div>

          {activeSubTab === "resumo" && (
            <div className="match-detail-card__content">
              <div className={`ai-analysis-section ${match.aiAnalysis ? "" : "ai-analysis-section--fallback"}`}>
                <button className="collapsible-header" onClick={() => setIsAIAnalysisExpanded(!isAIAnalysisExpanded)}>
                  <div className="collapsible-header__left">
                    <Sparkles className="ai-icon" size={20} />
                    <span className="collapsible-title">Análise AI (MISTRAL)</span>
                    <span className="badge-pro ml-sm">PRO</span>
                    {!match.aiAnalysis && <span className="ai-fallback-badge">Indisponível</span>}
                  </div>
                  {isAIAnalysisExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {isAIAnalysisExpanded && (
                  <div className="ai-analysis-content">
                    <div className="confidence-bar-container">
                      <div className="confidence-bar-label">
                        <span>Confiança da Análise</span>
                        <span className="confidence-value">{ai.confidence}%</span>
                      </div>
                      <div className="confidence-bar">
                        <div className="confidence-bar-fill" style={{ width: `${ai.confidence}%` }} />
                      </div>
                    </div>

                    <div className="ai-summary">
                      <h4 className="ai-section-title">Resumo</h4>
                      <p className="ai-text">{ai.summary}</p>
                    </div>

                    <div className="ai-key-points">
                      <h4 className="ai-section-title">Pontos-Chave</h4>
                      <ul className="ai-list">
                        {ai.keyPoints.map((point, index) => (
                          <li key={index} className="ai-list-item">
                            <span className="ai-bullet">•</span>
                            {point}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="ai-recommendation">
                      <h4 className="ai-section-title">Recomendação</h4>
                      <div className="ai-recommendation-box">
                        <Sparkles size={16} className="ai-recommendation-icon" />
                        <p className="ai-recommendation-text">{ai.recommendation}</p>
                      </div>
                    </div>

                    <div className="ai-timestamp">
                      <Clock size={14} />
                      <span>Última atualização: {ai.lastUpdated}</span>
                    </div>
                  </div>
                )}
              </div>

              {match.venue.image && (
                <div className="venue-image-container">
                  <img src={match.venue.image} alt={match.venue.name} className="venue-image" />
                </div>
              )}

              <div className="match-info-grid">
                <div className="match-info-item">
                  <span className="match-info-label">Competição</span>
                  <span className="match-info-value">{match.league}</span>
                </div>
                <div className="match-info-item">
                  <span className="match-info-label">Temporada</span>
                  <span className="match-info-value">{match.season}</span>
                </div>
                <div className="match-info-item">
                  <span className="match-info-label">Rodada</span>
                  <span className="match-info-value">{match.round || "-"}</span>
                </div>
                <div className="match-info-item">
                  <span className="match-info-label">
                    <MapPin size={14} className="inline-icon" />
                    Estádio
                  </span>
                  <span className="match-info-value">{match.venue.name}</span>
                </div>
                <div className="match-info-item">
                  <span className="match-info-label">
                    <Users size={14} className="inline-icon" />
                    Capacidade
                  </span>
                  <span className="match-info-value">
                    {match.venue.capacity ? match.venue.capacity.toLocaleString("pt-BR") : "-"}
                  </span>
                </div>
              </div>

              <div className="comparative-section">
                <button className="collapsible-header" onClick={() => setIsComparativeExpanded(!isComparativeExpanded)}>
                  <span className="collapsible-title">Comparativo dos Times</span>
                  {isComparativeExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {isComparativeExpanded && (
                  <div className="comparative-content">
                    <div className="comparative-tabs">
                      <button className="comparative-tab comparative-tab--active">Gols</button>
                      <button className="comparative-tab">BTTS</button>
                      <button className="comparative-tab">Escanteios</button>
                      <button className="comparative-tab">Chutes ao Gol</button>
                      <button className="comparative-tab">Finalizações</button>
                      <button className="comparative-tab">Faltas</button>
                      <button className="comparative-tab">Cartões</button>
                    </div>
                    <div className="muted">Gráficos comparativos em breve.</div>
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
