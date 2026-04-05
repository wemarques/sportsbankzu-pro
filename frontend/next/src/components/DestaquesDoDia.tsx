"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  Info,
  ChevronRight,
  Zap,
  Wallet,
  Calculator,
  ArrowLeft,
} from "lucide-react";
import { calcQuarterKelly } from "@/components/BankrollCard";
import type { Match, MatchPrediction } from "@/lib/leagues";
import { AVAILABLE_LEAGUES } from "@/lib/leagues";

/* ── Helpers ── */

function formatTime(dt: string): string {
  try {
    const d = new Date(dt);
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function fmtBRL(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function leagueName(match: Match): string {
  const league = AVAILABLE_LEAGUES.find((l) => l.id === match.leagueId);
  return league?.name ?? match.leagueId;
}

/* ── Types ── */

type ValueBet = {
  match: Match;
  markets: {
    label: string;
    odd: number;
    evPct: number;
    kellyPct: number;
    prob: number;
  }[];
};

type AnalysisItem = {
  match: Match;
  bestMarket: string;
  odd: number;
  modelProb: number;
  impliedProb: number;
};

/* ── Classify matches ── */

function classifyMatches(
  matches: Match[],
): { valueBets: ValueBet[]; analysisOnly: AnalysisItem[] } {
  const valueBets: ValueBet[] = [];
  const analysisOnly: AnalysisItem[] = [];

  for (const m of matches) {
    if (m.status !== "scheduled") continue;
    const preds = m.predictions ?? [];

    // Value bets: picks with positive EV and eligible classification
    const valuePicks = preds.filter((p) => {
      const cls = p.classification || p.finalClassification || p.status || "";
      const isEligible =
        cls === "SAFE" || cls === "NEUTRO_QUALIFICADO" || cls === "VALOR_DETECTADO";
      return isEligible && p.ev != null && p.ev > 0 && p.book_odd != null && p.book_odd > 1;
    });

    if (valuePicks.length > 0) {
      valueBets.push({
        match: m,
        markets: valuePicks.map((p) => {
          const prob = p.calibrated_probability ?? p.raw_probability ?? (p.prob_max > 0 ? p.prob_max / 100 : 0);
          const odd = p.book_odd ?? p.odd_minima ?? 1;
          return {
            label: p.mercado,
            odd: typeof odd === "number" ? odd : 1,
            evPct: (p.ev ?? 0) * 100,
            kellyPct: 0, // computed with bankroll in render
            prob,
          };
        }),
      });
    } else {
      // Analysis only: pick the best market by model probability
      const bestPred = preds
        .filter((p) => p.prob_max > 0 || (p.calibrated_probability ?? 0) > 0)
        .sort((a, b) => {
          const probA = a.calibrated_probability ?? a.raw_probability ?? (a.prob_max > 0 ? a.prob_max / 100 : 0);
          const probB = b.calibrated_probability ?? b.raw_probability ?? (b.prob_max > 0 ? b.prob_max / 100 : 0);
          return probB - probA;
        })[0];

      if (bestPred) {
        const odd = bestPred.book_odd ?? bestPred.odd_minima ?? bestPred.fair_odd ?? 0;
        const modelProb = bestPred.calibrated_probability ?? bestPred.raw_probability ?? (bestPred.prob_max > 0 ? bestPred.prob_max / 100 : 0);
        const impliedProb = odd && odd > 1 ? 1 / odd : 0;
        analysisOnly.push({
          match: m,
          bestMarket: bestPred.mercado,
          odd: typeof odd === "number" ? odd : 0,
          modelProb,
          impliedProb,
        });
      }
    }
  }

  // Sort value bets by total EV descending
  valueBets.sort((a, b) => {
    const evA = a.markets.reduce((s, mk) => s + mk.evPct, 0);
    const evB = b.markets.reduce((s, mk) => s + mk.evPct, 0);
    return evB - evA;
  });

  // Sort analysis by model probability descending
  analysisOnly.sort((a, b) => b.modelProb - a.modelProb);

  return { valueBets, analysisOnly: analysisOnly.slice(0, 10) };
}

/* ── PRESETS ── */
const BANK_PRESETS = [50, 100, 250, 500, 1000];

/* ── Component ── */

interface DestaquesDoDiaProps {
  matches: Match[];
  bankroll: number;
  onBankrollChange: (v: number) => void;
  onBack: () => void;
  onSelectMatch: (id: string) => void;
}

export default function DestaquesDoDia({
  matches,
  bankroll,
  onBankrollChange,
  onBack,
  onSelectMatch,
}: DestaquesDoDiaProps) {
  const [showGuide, setShowGuide] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sb_show_guide");
      return saved !== null ? JSON.parse(saved) : true;
    }
    return true;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("sb_show_guide", JSON.stringify(showGuide));
    }
  }, [showGuide]);

  const { valueBets, analysisOnly } = useMemo(() => classifyMatches(matches), [matches]);

  return (
    <div className="st-view-panel">
      {/* Header */}
      <div className="st-view-header">
        <button className="st-view-back" onClick={onBack}>
          <ArrowLeft size={14} /> Voltar
        </button>
        <h2 className="st-view-title">
          <Zap size={16} /> Destaques do Dia
        </h2>
      </div>

      {/* Bankroll Editor */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          padding: "12px 0",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "#000",
            border: "1px solid #1f2937",
            borderRadius: 8,
            padding: "4px 12px",
            maxWidth: 220,
          }}
          className="destaques-bankroll-input"
        >
          <Wallet size={14} style={{ color: "#10b981", flexShrink: 0 }} />
          <span style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase" }}>
            R$
          </span>
          <input
            type="number"
            value={bankroll}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v) && v >= 0) onBankrollChange(v);
            }}
            style={{
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#fff",
              fontSize: 14,
              fontWeight: 900,
              width: "100%",
            }}
          />
        </div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {BANK_PRESETS.map((amt) => (
            <button
              key={amt}
              onClick={() => onBankrollChange(amt)}
              style={{
                background: "#111827",
                border: "1px solid #1f2937",
                color: "#d1d5db",
                fontSize: 9,
                fontWeight: 900,
                padding: "4px 10px",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              {amt}
            </button>
          ))}
        </div>
      </div>

      {/* ── SECTION: Valor Detectado ── */}
      {valueBets.length > 0 && (
        <section style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "#10b981",
                  boxShadow: "0 0 10px rgba(16,185,129,0.6)",
                  animation: "pulse 2s infinite",
                }}
              />
              <h2
                style={{
                  fontSize: 16,
                  fontWeight: 900,
                  textTransform: "uppercase",
                  letterSpacing: "-0.02em",
                  fontStyle: "italic",
                  color: "#ecfdf5",
                  margin: 0,
                }}
              >
                Aposte aqui — valor detectado
              </h2>
            </div>
            <p
              style={{
                color: "#6b7280",
                fontSize: 10,
                textTransform: "uppercase",
                fontWeight: 700,
                letterSpacing: "0.15em",
                paddingLeft: 18,
                margin: "2px 0 0",
              }}
            >
              Calculo de Stake:{" "}
              <span style={{ color: "#34d399" }}>Quarter Kelly Automatico</span>
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {valueBets.map((bet) => (
              <ValueBetCard
                key={bet.match.id}
                bet={bet}
                bankroll={bankroll}
                onSelect={() => onSelectMatch(bet.match.id)}
              />
            ))}
          </div>

          {/* Disclaimer */}
          <div
            style={{
              marginTop: 16,
              background: "rgba(34,197,94,0.06)",
              border: "1px solid rgba(34,197,94,0.15)",
              borderRadius: 8,
              padding: "12px 14px",
              fontSize: 10,
              fontWeight: 700,
              textTransform: "uppercase",
              color: "#f8fafc",
            }}
          >
            Gestao de risco: nunca aposte mais do que pode perder. O stake sugerido e matematico, nao garantia de lucro.
          </div>
        </section>
      )}

      {/* Separator */}
      {valueBets.length > 0 && analysisOnly.length > 0 && (
        <div
          style={{
            height: 1,
            margin: "24px 0",
            background: "linear-gradient(to right, transparent, rgba(31,41,55,0.5), transparent)",
          }}
        />
      )}

      {/* ── SECTION: Apenas Analise ── */}
      {analysisOnly.length > 0 && (
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#374151",
              }}
            />
            <h2
              style={{
                fontSize: 14,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "-0.02em",
                color: "#6b7280",
                margin: 0,
              }}
            >
              Destaques do dia — apenas analise
            </h2>
          </div>

          <div
            style={{
              background: "#121212",
              borderRadius: 12,
              border: "1px solid #1f2937",
              overflow: "hidden",
            }}
          >
            {analysisOnly.map((item, idx) => (
              <div
                key={item.match.id}
                onClick={() => onSelectMatch(item.match.id)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "14px 16px",
                  cursor: "pointer",
                  borderTop: idx > 0 ? "1px solid rgba(31,41,55,0.4)" : undefined,
                  transition: "background 0.2s",
                }}
                className="destaques-analysis-item"
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 700, color: "#9ca3af", fontSize: 14 }}>
                      {item.match.homeTeam.name} vs {item.match.awayTeam.name}
                    </span>
                    <span style={{ color: "#374151" }}>•</span>
                    <span style={{ fontSize: 10, color: "#6b7280", fontWeight: 700, textTransform: "uppercase" }}>
                      {item.bestMarket} • Odd {item.odd > 0 ? item.odd.toFixed(2) : "N/A"}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.12em",
                      margin: "4px 0 0",
                      display: "flex",
                      gap: 12,
                    }}
                  >
                    <span style={{ color: "#9ca3af" }}>
                      <span style={{ color: "#10b981" }}>Modelo:</span>{" "}
                      <span style={{ color: "#d9a834", fontWeight: 900 }}>
                        {(item.modelProb * 100).toFixed(0)}%
                      </span>
                    </span>
                    <span style={{ color: "#1f2937" }}>|</span>
                    <span style={{ color: "#9ca3af" }}>
                      Odd Mercado:{" "}
                      <span style={{ color: "#d9a834", fontWeight: 900 }}>
                        {item.impliedProb > 0 ? (item.impliedProb * 100).toFixed(0) : "?"}%
                      </span>
                    </span>
                  </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0, marginLeft: 12 }}>
                  <span
                    style={{
                      fontSize: 9,
                      color: "#6b7280",
                      background: "#030712",
                      border: "1px solid #1f2937",
                      padding: "5px 12px",
                      borderRadius: 9999,
                      fontWeight: 900,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      minWidth: 75,
                      textAlign: "center",
                    }}
                  >
                    Sem Edge
                  </span>
                  <ChevronRight size={16} style={{ color: "#1f2937" }} className="destaques-chevron" />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {valueBets.length === 0 && analysisOnly.length === 0 && (
        <div style={{ textAlign: "center", padding: "48px 16px", color: "#6b7280" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>&#9917;</div>
          {matches.length === 0
            ? "Carregando jogos para analise..."
            : "Nenhum destaque encontrado para hoje."}
        </div>
      )}

      {/* ── Guide ── */}
      {showGuide && (valueBets.length > 0 || analysisOnly.length > 0) && (
        <section style={{ marginTop: 32 }}>
          <div
            style={{
              background: "linear-gradient(135deg, #111, #0a0a0a)",
              borderRadius: 16,
              border: "1px solid rgba(31,41,55,0.6)",
              padding: "24px",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
              <h3
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  fontSize: 14,
                  fontWeight: 900,
                  color: "#9ca3af",
                  textTransform: "uppercase",
                  letterSpacing: "0.2em",
                  margin: 0,
                }}
              >
                <Info size={18} style={{ color: "#10b981" }} />
                Guia de Leitura Profissional
              </h3>
              <button
                onClick={() => setShowGuide(false)}
                style={{
                  fontSize: 10,
                  textTransform: "uppercase",
                  fontWeight: 900,
                  color: "#4b5563",
                  border: "1px solid #1f2937",
                  background: "transparent",
                  padding: "4px 12px",
                  borderRadius: 4,
                  cursor: "pointer",
                }}
              >
                Ocultar Guia
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 24 }} className="destaques-guide-grid">
              <div style={{ padding: 16, borderRadius: 12 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 900,
                    color: "#10b981",
                    textTransform: "uppercase",
                    letterSpacing: "0.3em",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981" }} />
                  Valor Detectado
                </span>
                <p style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.6, marginTop: 8 }}>
                  A odd <span style={{ color: "#d9a834", fontWeight: 700 }}>dourada</span> e o preco do
                  mercado. O valor <span style={{ color: "#34d399", fontWeight: 700 }}>verde</span> e a sua
                  margem de lucro (EV). A{" "}
                  <span style={{ color: "#fff", fontWeight: 700, textDecoration: "underline", textDecorationColor: "rgba(16,185,129,0.3)", textUnderlineOffset: 4 }}>
                    Stake
                  </span>{" "}
                  e calculada individualmente via Quarter Kelly para cada mercado.
                </p>
              </div>
              <div style={{ padding: 16, borderRadius: 12 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 900,
                    color: "#6b7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.3em",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#374151" }} />
                  Apenas Analise
                </span>
                <p style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.6, marginTop: 8 }}>
                  O modelo concorda com a casa. O badge{" "}
                  <span style={{ color: "#9ca3af", fontWeight: 700 }}>Sem Edge</span> indica que nao existe
                  vantagem matematica a longo prazo para apostar nestes eventos, servindo apenas para contexto.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {!showGuide && (valueBets.length > 0 || analysisOnly.length > 0) && (
        <button
          onClick={() => setShowGuide(true)}
          style={{
            width: "100%",
            marginTop: 24,
            padding: 16,
            border: "1px dashed #1f2937",
            borderRadius: 12,
            background: "transparent",
            color: "#4b5563",
            fontSize: 10,
            textTransform: "uppercase",
            fontWeight: 900,
            cursor: "pointer",
          }}
        >
          Mostrar Guia de Leitura
        </button>
      )}
    </div>
  );
}

/* ── Value Bet Card ── */

function ValueBetCard({
  bet,
  bankroll,
  onSelect,
}: {
  bet: ValueBet;
  bankroll: number;
  onSelect: () => void;
}) {
  const league = leagueName(bet.match);
  const time = formatTime(bet.match.datetime);

  return (
    <div
      style={{
        background: "#141414",
        border: "1px solid rgba(31,41,55,0.8)",
        borderRadius: 12,
        overflow: "hidden",
        cursor: "pointer",
        transition: "border-color 0.3s",
      }}
      className="destaques-value-card"
      onClick={onSelect}
    >
      <div style={{ padding: "16px 20px" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 12,
            paddingBottom: 12,
            borderBottom: "1px solid rgba(31,41,55,0.4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Zap size={12} style={{ color: "#10b981" }} />
            <span
              style={{
                fontSize: 10,
                color: "#6b7280",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
              }}
            >
              {league} • {time}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 9,
              color: "#34d399",
              fontWeight: 900,
              background: "rgba(52,211,153,0.05)",
              padding: "2px 8px",
              borderRadius: 4,
              border: "1px solid rgba(16,185,129,0.1)",
              textTransform: "uppercase",
              letterSpacing: "-0.02em",
            }}
          >
            <TrendingUp size={10} />
            VALOR DETECTADO
          </div>
        </div>

        {/* Teams */}
        <div style={{ marginBottom: 20 }}>
          <h3
            style={{
              fontSize: 20,
              fontWeight: 900,
              letterSpacing: "-0.02em",
              color: "#f3f4f6",
              margin: 0,
            }}
          >
            {bet.match.homeTeam.name}
            <span style={{ color: "#9ca3af", fontWeight: 700, margin: "0 8px", fontSize: 13, textTransform: "uppercase" }}>
              vs
            </span>
            {bet.match.awayTeam.name}
          </h3>
        </div>

        {/* Markets Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 10,
          }}
        >
          {bet.markets.map((mk, idx) => {
            const kelly = calcQuarterKelly(mk.prob, mk.odd, bankroll);
            return (
              <div
                key={idx}
                style={{
                  background: "#1c1c1c",
                  border: "1px solid rgba(31,41,55,0.5)",
                  padding: "10px 14px",
                  borderRadius: 8,
                }}
              >
                {/* Line 1: Label + Odd + EV */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 900,
                      color: "#9ca3af",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    {mk.label}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 15,
                        fontWeight: 900,
                        color: "#d9a834",
                        filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.4))",
                      }}
                    >
                      @{mk.odd.toFixed(2)}
                    </span>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 900,
                        color: "#34d399",
                        background: "rgba(16,185,129,0.1)",
                        padding: "2px 6px",
                        borderRadius: 4,
                        border: "1px solid rgba(16,185,129,0.2)",
                      }}
                    >
                      +{mk.evPct.toFixed(1)}%
                    </span>
                  </div>
                </div>
                {/* Line 2: Stake */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    alignItems: "center",
                    gap: 4,
                    marginTop: 6,
                    fontSize: 9,
                    fontWeight: 700,
                    color: "#6b7280",
                  }}
                >
                  <Calculator size={10} style={{ color: "rgba(16,185,129,0.3)" }} />
                  <span>
                    Stake:{" "}
                    <span style={{ color: "#d1d5db" }}>{(kelly.pct * 100).toFixed(1)}%</span>{" "}
                    ({fmtBRL(kelly.stake)})
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
