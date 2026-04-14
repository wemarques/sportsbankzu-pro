"use client";
import { useState } from "react";
import { C } from "./constants";
import { LiveTracker } from "./LiveTracker";
import { GLOSSARY } from "@/lib/glossary";
import type { AIAnalysisData, MatchContext, PickData } from "./types";

type Tab = "resumo" | "pontos" | "glossario";

export const AICard = ({
  analysis,
  match,
  picks,
}: {
  analysis: AIAnalysisData;
  match: MatchContext;
  picks: PickData[];
}) => {
  const [tab, setTab] = useState<Tab>("resumo");

  const noBetWithProb = picks.find(
    (p) =>
      p.classification === "NO_BET" &&
      p.ev != null &&
      p.ev < 0 &&
      p.rawProb >= 0.55 &&
      p.bookOdd != null
  );

  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>
            Análise AI
          </span>
          <span
            style={{
              fontSize: 9,
              padding: "2px 6px",
              borderRadius: 3,
              background: "rgba(167,139,250,0.10)",
              color: C.purple,
              fontWeight: 600,
            }}
          >
            Mistral v3.0
          </span>
          <span
            style={{
              fontSize: 9,
              padding: "2px 6px",
              borderRadius: 3,
              background: "rgba(255,255,255,0.04)",
              color: C.t3,
              fontWeight: 600,
            }}
          >
            NARRATIVA
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              width: 40,
              height: 3,
              borderRadius: 2,
              background: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${analysis.confidence}%`,
                height: "100%",
                borderRadius: 2,
                background: analysis.confidence >= 70 ? C.green : C.gold,
              }}
            />
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: analysis.confidence >= 70 ? C.green : C.gold,
            }}
          >
            {analysis.confidence}%
          </span>
        </div>
      </div>

      {match.isLive && (
        <div style={{ padding: "8px 14px", borderBottom: `1px solid ${C.border}` }}>
          <LiveTracker match={match} />
        </div>
      )}

      <div style={{ display: "flex", borderBottom: `1px solid ${C.border}` }}>
        {([
          { id: "resumo" as const, l: "Resumo" },
          { id: "pontos" as const, l: "Pontos-Chave" },
          { id: "glossario" as const, l: "Glossário" },
        ]).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1,
              padding: "8px 0",
              fontSize: 11,
              fontWeight: 600,
              cursor: "pointer",
              color: tab === t.id ? C.green : C.t3,
              background: "transparent",
              border: "none",
              borderBottom:
                tab === t.id ? `2px solid ${C.green}` : "2px solid transparent",
            }}
          >
            {t.l}
          </button>
        ))}
      </div>

      <div style={{ padding: 14 }}>
        {tab === "resumo" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p style={{ fontSize: 12, lineHeight: 1.6, color: C.t2, margin: 0 }}>
              {analysis.summary}
            </p>
            <div
              style={{
                background: C.gS,
                border: `1px solid ${C.gB}`,
                borderRadius: 6,
                padding: "10px 12px",
                display: "flex",
                gap: 8,
              }}
            >
              <span style={{ fontSize: 14 }}>✦</span>
              <div>
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 700,
                    color: C.green,
                    marginBottom: 3,
                    letterSpacing: "0.04em",
                  }}
                >
                  RECOMENDAÇÃO
                </div>
                <p style={{ fontSize: 11, lineHeight: 1.5, color: C.t1, margin: 0 }}>
                  {analysis.recommendation}
                </p>
              </div>
            </div>
            {noBetWithProb && noBetWithProb.bookOdd != null && (
              <div
                style={{
                  background: C.rS,
                  border: `1px solid ${C.rB}`,
                  borderRadius: 6,
                  padding: "10px 12px",
                  fontSize: 11,
                  lineHeight: 1.6,
                  color: C.t2,
                }}
              >
                <span style={{ color: C.red, fontWeight: 700 }}>
                  ⚠ {noBetWithProb.label} — EV negativo:
                </span>{" "}
                Prob {Math.round(noBetWithProb.rawProb * 100)}% parece alta, mas a odd{" "}
                {noBetWithProb.bookOdd.toFixed(2)} exige{" "}
                {Math.round((1 / noBetWithProb.bookOdd) * 100)}% para ser lucrativa. Apostar
                sistematicamente nisso perde capital no longo prazo. Pode acertar neste jogo,
                mas não é aposta de valor.
              </div>
            )}
          </div>
        )}
        {tab === "pontos" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {analysis.keyPoints.map((p, i) => {
              const [title, ...rest] = p.split(" — ");
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 8,
                    padding: "6px 8px",
                    borderRadius: 5,
                    background:
                      i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent",
                  }}
                >
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: 3,
                      background: "rgba(255,255,255,0.05)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 9,
                      fontWeight: 700,
                      color: C.t3,
                      flexShrink: 0,
                    }}
                  >
                    {i + 1}
                  </span>
                  <div style={{ fontSize: 11, lineHeight: 1.5 }}>
                    <span style={{ fontWeight: 700, color: C.t1 }}>{title}</span>
                    {rest.length > 0 && (
                      <span style={{ color: C.t2 }}> — {rest.join(" — ")}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {tab === "glossario" && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              maxHeight: 280,
              overflowY: "auto",
            }}
          >
            {GLOSSARY.map((g, i) => (
              <div
                key={`${g.term}-${i}`}
                style={{
                  padding: "8px 10px",
                  borderRadius: 5,
                  background:
                    i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 3,
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 700, color: C.t1 }}>
                    {g.term}
                  </span>
                  <span
                    style={{
                      fontSize: 8,
                      padding: "1px 5px",
                      borderRadius: 3,
                      background: "rgba(255,255,255,0.05)",
                      color: C.t3,
                      fontWeight: 600,
                      letterSpacing: "0.03em",
                    }}
                  >
                    {g.category.toUpperCase()}
                  </span>
                </div>
                <p style={{ fontSize: 10, lineHeight: 1.5, color: C.t2, margin: 0 }}>
                  {g.definition}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
