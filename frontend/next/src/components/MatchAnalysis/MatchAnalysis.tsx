"use client";
import { useState } from "react";
import { C } from "./constants";
import { AICard } from "./AICard";
import { PickCard } from "./PickCard";
import { EVHelp } from "./EVHelp";
import type { StakeMode } from "@/components/BankrollCard";
import type { AIAnalysisData, MatchContext, PickData } from "./types";

type FilterId = "all" | "viable" | "value";

interface MatchAnalysisProps {
  match: MatchContext;
  picks: PickData[];
  analysis: AIAnalysisData;
  bankroll?: number;
  stakeMode?: StakeMode;
}

export default function MatchAnalysis({
  match,
  picks,
  analysis,
  bankroll = 100,
  stakeMode = "kelly",
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
          maxWidth: 500,
          margin: "0 auto",
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
                  {match.period} {match.minute}'
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
            <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>Mercados</span>
            <div style={{ display: "flex", gap: 3 }}>
              {filters.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setFilter(f.id)}
                  style={{
                    padding: "3px 9px",
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
      </div>
    </div>
  );
}
