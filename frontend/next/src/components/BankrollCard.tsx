"use client";

import React from "react";

/* ── Quarter Kelly calculation ── */
export function calcQuarterKelly(
  prob: number,
  odd: number,
  bankroll: number,
): { stake: number; pct: number; ev: number } {
  if (prob <= 0 || odd <= 1 || bankroll <= 0) return { stake: 0, pct: 0, ev: 0 };
  const b = odd - 1;
  const kelly = (prob * b - (1 - prob)) / b;
  const qk = kelly * 0.25;
  const cappedPct = Math.min(Math.max(qk, 0), 0.05); // cap 0-5%
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
          <span className="bkr-title">Bankroll Disponivel</span>
          <span className="bkr-badge">EDITAVEL</span>
        </div>
        <span className="bkr-subtitle">Quarter Kelly &bull; Cap 5% por pick</span>
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
            {p}
          </button>
        ))}
      </div>

      {pickCount > 0 && (
        <div className="bkr-summary">
          <div className="bkr-stat">
            <span className="bkr-stat-label">Stake total</span>
            <span className="bkr-stat-value">{fmtBRL(totalStake)}</span>
          </div>
          <div className="bkr-stat">
            <span className="bkr-stat-label">EV medio</span>
            <span className="bkr-stat-value" style={{ color: avgEV >= 0 ? "#4ade80" : "#f87171" }}>
              {avgEV >= 0 ? "+" : ""}{avgEV.toFixed(1)}%
            </span>
          </div>
          <div className="bkr-stat">
            <span className="bkr-stat-label">% comprometido</span>
            <span className="bkr-stat-value">
              {bankroll > 0 ? ((totalStake / bankroll) * 100).toFixed(1) : "0.0"}%
            </span>
          </div>
        </div>
      )}

      <div className="bkr-disclaimer">
        Gestao de risco: nunca aposte mais do que pode perder. O stake sugerido e matematico, nao garantia de lucro.
      </div>
    </div>
  );
}
