"use client";
import { useState } from "react";
import { C } from "./constants";
import { AICard } from "./AICard";
import { PickCard } from "./PickCard";
import { EVHelp } from "./EVHelp";
import type { StakeMode } from "@/components/BankrollCard";
import type { AIAnalysisData, MatchContext, PickData } from "./types";
import type { RejectedInsightUI } from "@/lib/matchDataMapper";
import { fmtMercado } from "@/lib/classifications";

/** #189-g: motivo compacto para o chip; texto completo fica no title. */
function shortReason(reason: string): string {
  const r = (reason || "").toLowerCase();
  if (r.includes("ev negativo")) return "EV\u2212";
  if (r.includes("sem odd")) return "sem odd";
  if (r.includes("prob insuficiente") || r.includes("prob <")) return "prob abaixo do corte";
  if (r.includes("deflac")) return "EV\u2212 p\u00f3s-defla\u00e7\u00e3o";
  return reason.length > 28 ? reason.slice(0, 26) + "\u2026" : reason;
}

type FilterId = "all" | "viable" | "value";

interface MatchAnalysisProps {
  match: MatchContext;
  picks: PickData[];
  analysis: AIAnalysisData;
  bankroll?: number;
  stakeMode?: StakeMode;
  rejectedInsights?: RejectedInsightUI[];
}

export default function MatchAnalysis({
  match,
  picks,
  analysis,
  bankroll = 100,
  stakeMode = "kelly",
  rejectedInsights = [],
}: MatchAnalysisProps) {
  const [filter, setFilter] = useState<FilterId>("all");
  const filters: { id: FilterId; l: string }[] = [
    { id: "all", l: "Todos" },
    { id: "viable", l: "⚡ Viáveis" },
    { id: "value", l: "EV+" },
  ];

  const filtered = picks.filter((p) => {
    if (filter === "viable") return p.rawProb >= 0.5;
    if (filter === "value") return p.ev != null && p.ev > 0;
    return true;
  });

  return (
    <div
      style={{
        background: C.bg,
        padding: 16,
        fontFamily: "'Inter',-apple-system,sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <div
          style={{
            background: C.card,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
            padding: 14,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
          }}
        >
          <div style={{ fontSize: 10, color: C.t3, letterSpacing: "0.06em" }}>
            {match.league}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, width: "100%" }}>
            <div style={{ flex: 1, textAlign: "right" }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.t1 }}>
                {match.home}
              </div>
              {match.homePos > 0 && (
                <div style={{ fontSize: 10, color: C.t3 }}>{match.homePos}º</div>
              )}
            </div>
            {match.isLive ? (
              <div
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  background: C.rS,
                  border: `1px solid ${C.rB}`,
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 800,
                    color: C.t1,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {match.score.home} - {match.score.away}
                </div>
                <div style={{ fontSize: 10, fontWeight: 700, color: C.red }}>
                  {match.period === "HT"
                    ? "INTERVALO"
                    : `${match.period} ${match.clockLabel ?? `${match.minute}'`}`}
                </div>
              </div>
            ) : (
              <div
                style={{
                  padding: "4px 12px",
                  borderRadius: 6,
                  background: "rgba(255,255,255,0.03)",
                  border: `1px solid ${C.border}`,
                  fontSize: 13,
                  fontWeight: 700,
                  color: C.t2,
                }}
              >
                vs
              </div>
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.t1 }}>
                {match.away}
              </div>
              {match.awayPos > 0 && (
                <div style={{ fontSize: 10, color: C.t3 }}>{match.awayPos}º</div>
              )}
            </div>
          </div>
        </div>

        <AICard analysis={analysis} match={match} picks={picks} />

        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 10,
            }}
          >
            <h2 style={{ fontSize: 13, fontWeight: 700, color: C.t1, margin: 0 }}>Mercados</h2>
            <div style={{ display: "flex", gap: 3 }}>
              {filters.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setFilter(f.id)}
                  style={{
                    /* #189-h: alvo de toque maior (WCAG 2.5.5) */
                    padding: "8px 11px",
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 600,
                    border: "none",
                    cursor: "pointer",
                    background:
                      filter === f.id ? "rgba(255,255,255,0.08)" : "transparent",
                    color: filter === f.id ? C.t1 : C.t3,
                  }}
                >
                  {f.l}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filtered.map((p) => (
              <PickCard key={p.id} pick={p} match={match} bankroll={bankroll} stakeMode={stakeMode} />
            ))}
            {filtered.length === 0 && (
              <div style={{ textAlign: "center", padding: 20, color: C.t3, fontSize: 11 }}>
                Nenhum mercado com este filtro.
              </div>
            )}
          </div>
          <EVHelp />
        </div>

        {/* Rejected insights (#152) — transparency for notable NO_BET markets */}
        {rejectedInsights.length > 0 && (
          <div
            style={{
              background: "rgba(255,107,53,0.06)",
              border: `1px solid rgba(255,107,53,0.15)`,
              borderRadius: 8,
              padding: "10px 12px",
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 700, color: "#ff6b35", letterSpacing: "0.04em", marginBottom: 6 }}>
              MERCADOS ANALISADOS — NÃO RECOMENDADOS
            </div>
            {/* #189-g: o bloco mais honesto do produto merece ser legivel —
                nome do mercado em t1, numeros em t2 (>=4.5:1 sobre o fundo),
                e o motivo vira CHIP em vez de texto vermelho sobre vinho. */}
            {rejectedInsights.map((r, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                  flexWrap: "wrap",
                  padding: "5px 0",
                  borderTop: i > 0 ? "1px solid rgba(255,255,255,0.06)" : undefined,
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 600, color: C.t1 }}>{fmtMercado(r.market)}</span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 10, color: C.t2, fontVariantNumeric: "tabular-nums" }}>
                  {r.rawProb.toFixed(0)}% raw → {r.deflatedProb.toFixed(0)}% cal
                  {r.ev != null && (
                    <span style={{ color: r.ev < 0 ? "#ff8a80" : C.green, fontWeight: 700 }}>
                      EV {r.ev > 0 ? "+" : ""}{r.ev.toFixed(1)}%
                    </span>
                  )}
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      letterSpacing: "0.03em",
                      padding: "1px 7px",
                      borderRadius: 999,
                      background: "rgba(255,107,53,0.12)",
                      border: "1px solid rgba(255,107,53,0.3)",
                      color: "#ffb08a",
                      whiteSpace: "nowrap",
                    }}
                    title={r.reason}
                  >
                    {shortReason(r.reason)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
