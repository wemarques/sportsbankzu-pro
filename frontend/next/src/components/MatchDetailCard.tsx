"use client";

import React, { useState } from "react";
import {
  Clock,
  MapPin,
  Users,
  Star,
  Sparkles,
  ChevronUp,
  ChevronDown,
  TrendingUp,
  Loader2,
  RefreshCw,
} from "lucide-react";
import "../styles/match-detail-card.css";

export type AIAnalysis = {
  summary: string;
  key_points: string[];
  recommendation: string;
  confidence: number;
  last_updated: string;
};

export type MatchDetailData = {
  id: string;
  homeTeam: string;
  awayTeam: string;
  leagueName?: string;
  datetime?: string;
  stadium?: string;
  status?: string;
  odds?: {
    home?: number;
    draw?: number;
    away?: number;
    over25?: number;
    under25?: number;
    bttsYes?: number;
    bttsNo?: number;
  };
  stats?: {
    homeWinProb?: number;
    drawProb?: number;
    awayWinProb?: number;
    avgGoals?: number;
    bttsProb?: number;
    over25Prob?: number;
    over15Prob?: number;
    over35Prob?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    lambdaTotal?: number;
    homePossession?: number;
    awayPossession?: number;
    leagueRegime?: string;
    leagueVolatility?: string;
    chaosDetected?: boolean;
    status?: string;
    mercado_principal?: string;
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
  ratings?: { home?: number; away?: number };
  xg?: { home?: number; away?: number };
  aiAnalysis?: AIAnalysis;
};

type Props = {
  match: MatchDetailData;
  aiLoading?: boolean;
  onRegenerate?: () => void;
};

function OddBadge({ label, value }: { label: string; value?: number }) {
  return (
    <div className="match-detail-card__odd">
      <span className="match-detail-card__odd-label">{label}</span>
      <span className="match-detail-card__odd-value">
        {value != null ? value.toFixed(2) : "-"}
      </span>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="match-detail-card__stat">
      <span className="match-detail-card__stat-label">{label}</span>
      <span className="match-detail-card__stat-value">{value}</span>
    </div>
  );
}

function FormBadges({ form, label }: { form?: string[]; label: string }) {
  if (!form || form.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[#888]">{label}:</span>
      <div className="flex gap-1">
        {form.map((f, i) => {
          const bg =
            f === "W"
              ? "bg-[#00cc66]"
              : f === "D"
                ? "bg-[#ffaa00]"
                : "bg-[#ff4444]";
          return (
            <span
              key={`${label}-${i}`}
              className={`${bg} text-black text-xs font-bold w-5 h-5 rounded flex items-center justify-center`}
            >
              {f}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default function MatchDetailCard({
  match,
  aiLoading,
  onRegenerate,
}: Props) {
  const [activeTab, setActiveTab] = useState("pre-jogo");
  const [aiOpen, setAiOpen] = useState(true);

  const { odds, stats, h2h, aiAnalysis } = match;

  const tabs = [
    { id: "pre-jogo", label: "Pre-Jogo" },
    { id: "cotacoes", label: "Cotacoes" },
    { id: "stats", label: "Stats" },
    { id: "h2h", label: "H2H" },
  ];

  return (
    <div className="match-detail-card">
      {/* Header: Teams + Time */}
      <div className="match-detail-card__header">
        <div className="match-detail-card__teams">
          <div className="match-detail-card__team">
            <div className="match-detail-card__team-name">
              {match.homeTeam}
            </div>
            <FormBadges form={match.homeForm} label="Forma" />
            {match.ratings?.home != null && (
              <span className="text-xs text-[#888]">
                Rating: {match.ratings.home.toFixed(1)}
              </span>
            )}
          </div>
          <div className="match-detail-card__vs">
            <div className="match-detail-card__time">
              {match.datetime ? (
                <>
                  <Clock size={14} className="inline mr-1 text-[#888]" />
                  {new Date(match.datetime).toLocaleTimeString("pt-BR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </>
              ) : (
                "VS"
              )}
            </div>
            {match.leagueName && (
              <div className="match-detail-card__league">
                {match.leagueName}
              </div>
            )}
            {match.stadium && (
              <div className="match-detail-card__league">
                <MapPin size={10} className="inline mr-0.5" />
                {match.stadium}
              </div>
            )}
          </div>
          <div className="match-detail-card__team match-detail-card__team--away">
            <div className="match-detail-card__team-name">
              {match.awayTeam}
            </div>
            <FormBadges form={match.awayForm} label="Forma" />
            {match.ratings?.away != null && (
              <span className="text-xs text-[#888]">
                Rating: {match.ratings.away.toFixed(1)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Odds bar */}
      <div className="match-detail-card__odds">
        <OddBadge label="1" value={odds?.home} />
        <OddBadge label="X" value={odds?.draw} />
        <OddBadge label="2" value={odds?.away} />
        <OddBadge label="O2.5" value={odds?.over25} />
        <OddBadge label="U2.5" value={odds?.under25} />
        <OddBadge label="BTTS S" value={odds?.bttsYes} />
        <OddBadge label="BTTS N" value={odds?.bttsNo} />
      </div>

      {/* Tabs */}
      <div className="match-detail-card__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`match-detail-card__tab ${activeTab === tab.id ? "match-detail-card__tab--active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="match-detail-card__content">
        {activeTab === "pre-jogo" && (
          <div className="match-detail-card__stats-grid">
            <StatRow
              label="Prob. Casa"
              value={stats?.homeWinProb != null ? `${stats.homeWinProb.toFixed(1)}%` : "-"}
            />
            <StatRow
              label="Prob. Empate"
              value={stats?.drawProb != null ? `${stats.drawProb.toFixed(1)}%` : "-"}
            />
            <StatRow
              label="Prob. Fora"
              value={stats?.awayWinProb != null ? `${stats.awayWinProb.toFixed(1)}%` : "-"}
            />
            <StatRow
              label="Media Gols"
              value={stats?.avgGoals != null ? stats.avgGoals.toFixed(2) : "-"}
            />
            <StatRow
              label="Over 2.5"
              value={stats?.over25Prob != null ? `${stats.over25Prob.toFixed(1)}%` : "-"}
            />
            <StatRow
              label="BTTS"
              value={stats?.bttsProb != null ? `${stats.bttsProb.toFixed(1)}%` : "-"}
            />
            {stats?.mercado_principal && (
              <StatRow label="Mercado" value={stats.mercado_principal} />
            )}
            {stats?.status && (
              <StatRow label="Status" value={stats.status} />
            )}
          </div>
        )}

        {activeTab === "cotacoes" && (
          <div className="match-detail-card__stats-grid">
            <StatRow label="1 (Casa)" value={odds?.home?.toFixed(2) ?? "-"} />
            <StatRow label="X (Empate)" value={odds?.draw?.toFixed(2) ?? "-"} />
            <StatRow label="2 (Fora)" value={odds?.away?.toFixed(2) ?? "-"} />
            <StatRow label="Over 2.5" value={odds?.over25?.toFixed(2) ?? "-"} />
            <StatRow label="Under 2.5" value={odds?.under25?.toFixed(2) ?? "-"} />
            <StatRow label="BTTS Sim" value={odds?.bttsYes?.toFixed(2) ?? "-"} />
            <StatRow label="BTTS Nao" value={odds?.bttsNo?.toFixed(2) ?? "-"} />
          </div>
        )}

        {activeTab === "stats" && (
          <div className="match-detail-card__stats-grid">
            <StatRow
              label="Lambda Casa"
              value={stats?.lambdaHome?.toFixed(2) ?? "-"}
            />
            <StatRow
              label="Lambda Fora"
              value={stats?.lambdaAway?.toFixed(2) ?? "-"}
            />
            <StatRow
              label="Lambda Total"
              value={stats?.lambdaTotal?.toFixed(2) ?? "-"}
            />
            <StatRow
              label="Posse Casa"
              value={stats?.homePossession != null ? `${stats.homePossession.toFixed(0)}%` : "-"}
            />
            <StatRow
              label="Posse Fora"
              value={stats?.awayPossession != null ? `${stats.awayPossession.toFixed(0)}%` : "-"}
            />
            <StatRow
              label="Regime"
              value={stats?.leagueRegime ?? "-"}
            />
            <StatRow
              label="Volatilidade"
              value={stats?.leagueVolatility ?? "-"}
            />
            <StatRow
              label="Caos"
              value={stats?.chaosDetected ? "Sim" : "Nao"}
            />
            {match.xg && (
              <>
                <StatRow
                  label="xG Casa"
                  value={match.xg.home?.toFixed(2) ?? "-"}
                />
                <StatRow
                  label="xG Fora"
                  value={match.xg.away?.toFixed(2) ?? "-"}
                />
              </>
            )}
          </div>
        )}

        {activeTab === "h2h" && (
          <div>
            <div className="match-detail-card__h2h-grid">
              <div className="match-detail-card__h2h-item">
                <div className="match-detail-card__h2h-value">
                  {h2h?.totalMatches ?? 0}
                </div>
                <div className="match-detail-card__h2h-label">Total Jogos</div>
              </div>
              <div className="match-detail-card__h2h-item">
                <div className="match-detail-card__h2h-value">
                  {h2h?.homeWins ?? 0}
                </div>
                <div className="match-detail-card__h2h-label">Vit. Casa</div>
              </div>
              <div className="match-detail-card__h2h-item">
                <div className="match-detail-card__h2h-value">
                  {h2h?.draws ?? 0}
                </div>
                <div className="match-detail-card__h2h-label">Empates</div>
              </div>
              <div className="match-detail-card__h2h-item">
                <div className="match-detail-card__h2h-value">
                  {h2h?.awayWins ?? 0}
                </div>
                <div className="match-detail-card__h2h-label">Vit. Fora</div>
              </div>
              <div className="match-detail-card__h2h-item">
                <div className="match-detail-card__h2h-value">
                  {h2h?.avgGoals?.toFixed(1) ?? "-"}
                </div>
                <div className="match-detail-card__h2h-label">Media Gols</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* AI Analysis Section */}
      <div className="match-detail-card__ai">
        <div
          className="match-detail-card__ai-header"
          onClick={() => setAiOpen(!aiOpen)}
        >
          <div className="match-detail-card__ai-title">
            <Sparkles size={18} className="match-detail-card__ai-sparkle" />
            Analise AI (MISTRAL)
          </div>
          <div
            className={`match-detail-card__ai-toggle ${aiOpen ? "match-detail-card__ai-toggle--open" : ""}`}
          >
            <ChevronDown size={18} />
          </div>
        </div>

        {aiOpen && (
          <div className="match-detail-card__ai-body">
            {aiLoading && (
              <div className="match-detail-card__loading">
                <Loader2 size={16} className="match-detail-card__loading-spinner" />
                Gerando analise AI...
              </div>
            )}

            {!aiLoading && aiAnalysis && (
              <>
                {/* Confidence Bar */}
                <div className="match-detail-card__confidence">
                  <div className="match-detail-card__confidence-header">
                    <span className="match-detail-card__confidence-label">
                      Confianca da Analise
                    </span>
                    <span className="match-detail-card__confidence-value">
                      {aiAnalysis.confidence}%
                    </span>
                  </div>
                  <div className="match-detail-card__confidence-bar">
                    <div
                      className="match-detail-card__confidence-fill"
                      style={{ width: `${aiAnalysis.confidence}%` }}
                    />
                  </div>
                </div>

                {/* Summary */}
                <div className="match-detail-card__ai-summary">
                  {aiAnalysis.summary}
                </div>

                {/* Key Points */}
                {aiAnalysis.key_points.length > 0 && (
                  <ul className="match-detail-card__key-points">
                    {aiAnalysis.key_points.map((point, i) => (
                      <li key={i} className="match-detail-card__key-point">
                        <Star
                          size={12}
                          className="match-detail-card__key-point-icon"
                        />
                        {point}
                      </li>
                    ))}
                  </ul>
                )}

                {/* Recommendation */}
                {aiAnalysis.recommendation && (
                  <div className="match-detail-card__recommendation">
                    <div className="match-detail-card__recommendation-label">
                      <TrendingUp size={12} className="inline mr-1" />
                      Recomendacao
                    </div>
                    <div className="match-detail-card__recommendation-text">
                      {aiAnalysis.recommendation}
                    </div>
                  </div>
                )}

                {/* Timestamp + Regenerate */}
                <div className="flex items-center justify-between">
                  {aiAnalysis.last_updated && (
                    <div className="match-detail-card__ai-timestamp">
                      <Clock size={10} className="inline mr-0.5" />
                      {new Date(aiAnalysis.last_updated).toLocaleString("pt-BR")}
                    </div>
                  )}
                  {onRegenerate && (
                    <button
                      onClick={onRegenerate}
                      className="flex items-center gap-1 text-xs text-[#00ff88] hover:text-[#00cc66] transition-colors"
                    >
                      <RefreshCw size={12} />
                      Regenerar
                    </button>
                  )}
                </div>
              </>
            )}

            {!aiLoading && !aiAnalysis && (
              <div className="text-center text-sm text-[#666] py-4">
                Analise AI nao disponivel para este jogo.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
