"use client";

import React from "react";

/* ── Quarter Kelly calculation (#148) ── */
export function calcQuarterKelly(
  prob: number,
  odd: number,
  bankroll: number,
  classification?: string,
): { stake: number; pct: number; ev: number } {
  if (prob <= 0 || odd <= 1 || bankroll <= 0) return { stake: 0, pct: 0, ev: 0 };
  const b = odd - 1;
  const kelly = (prob * b - (1 - prob)) / b;

  // Multiplicador e cap por classificação
  let multiplier = 0.25; // Quarter Kelly default (SAFE)
  let cap = 0.05;

  if (classification === "NEUTRO") {
    // VIÁVEL: prob < 50% não recebe stake
    if (prob < 0.5) return { stake: 0, pct: 0, ev: (prob * odd - 1) * 100 };
    multiplier = 0.25 * 0.3; // Quarter Kelly × 0.30
    cap = 0.02; // Cap 2%
  } else if (classification === "NEUTRO_QUALIFICADO") {
    multiplier = 0.25 * 0.6;
    cap = 0.05;
  } else if (classification === "NO_BET") {
    return { stake: 0, pct: 0, ev: (prob * odd - 1) * 100 };
  }

  let qk = kelly * multiplier;

  // Floor para VIÁVEL: se Kelly ≤ 0 mas prob ≥ 50%
  if (classification === "NEUTRO" && qk <= 0 && prob >= 0.5) {
    qk = 0.005; // floor 0.5%
  }

  const cappedPct = Math.min(Math.max(qk, 0), cap);
  return {
    stake: Math.max(Math.round(bankroll * cappedPct * 100) / 100, 0),
    pct: cappedPct,
    ev: (prob * odd - 1) * 100,
  };
}

/* ── Format BRL ── */
function fmtBRL(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/* ── Props ── */
interface BankrollCardProps {
  bankroll: number;
  onBankrollChange: (v: number) => void;
  totalStake: number;
  avgEV: number;
  pickCount: number;
}

const PRESETS = [50, 100, 250, 500, 1000];

export default function BankrollCard({
  bankroll,
  onBankrollChange,
  totalStake,
  avgEV,
  pickCount,
}: BankrollCardProps) {
  return (
    <div className="bkr-card">
      <div className="bkr-header">
        <div className="bkr-title-row">
          <div>
            <span className="bkr-title">Banca Disponível</span>
            <span className="bkr-subtitle">Quarter Kelly &bull; Cap 5%</span>
          </div>
          <span className="bkr-badge">EDITAVEL</span>
        </div>
      </div>

      <div className="bkr-input-row">
        <span className="bkr-currency">R$</span>
        <input
          type="number"
          className="bkr-input"
          value={bankroll}
          min={1}
          step={10}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (!isNaN(v) && v >= 0) onBankrollChange(v);
          }}
        />
      </div>

      <div className="bkr-presets">
        {PRESETS.map((p) => (
          <button
            key={p}
            className={`bkr-preset ${bankroll === p ? "bkr-preset--active" : ""}`}
            onClick={() => onBankrollChange(p)}
          >
            {p >= 1000 ? `${p / 1000}k` : p}
          </button>
        ))}
      </div>

      {pickCount > 0 && (
        <div className="bkr-summary">
          <div className="bkr-stat bkr-stat--green">
            <span className="bkr-stat-label">Stake Total</span>
            <span className="bkr-stat-value bkr-stat-value--green">{fmtBRL(totalStake)}</span>
            <span className="bkr-stat-sub">{bankroll > 0 ? ((totalStake / bankroll) * 100).toFixed(1) : "0.0"}% da banca</span>
          </div>
          <div className="bkr-stat bkr-stat--yellow">
            <span className="bkr-stat-label">EV Medio</span>
            <span className="bkr-stat-value bkr-stat-value--yellow">
              {avgEV >= 0 ? "+" : ""}{avgEV.toFixed(1)}%
            </span>
            <span className="bkr-stat-sub">{pickCount} picks</span>
          </div>
        </div>
      )}

      <div className="bkr-disclaimer">
        Gestao de risco: nunca aposte mais do que pode perder. O stake sugerido e matematico, nao garantia de lucro.
      </div>
    </div>
  );
}
