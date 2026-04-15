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

/* ── Oportunidade stake calculation (#149) ── */
export interface OportunidadeResult {
  stake: number;
  pct: number;
  ev: number;
  descontoEv: number;
  custoPor100: number;
  bloqueado: boolean;
  motivo?: string;
}

const OPORT_TIERS: Record<string, { base: number; cap: number; evBloqueio: number }> = {
  SAFE:                 { base: 0.03, cap: 0.05, evBloqueio: -0.05 },
  NEUTRO_QUALIFICADO:   { base: 0.02, cap: 0.04, evBloqueio: -0.10 },
  NEUTRO:               { base: 0.01, cap: 0.02, evBloqueio: -0.15 },
  NO_BET:               { base: 0.00, cap: 0.00, evBloqueio: 999 },
};

export function calcStakeOportunidade(
  prob: number,
  odd: number,
  bankroll: number,
  classification: string,
  marketThreshold: number = 0.50,
): OportunidadeResult {
  const tier = OPORT_TIERS[classification] ?? OPORT_TIERS.NO_BET;
  const evDecimal = odd > 1 ? prob * odd - 1 : 0;
  const evPct = evDecimal * 100;

  // Piso 50%
  if (prob < 0.50 || bankroll <= 0) {
    return { stake: 0, pct: 0, ev: evPct, descontoEv: 1, custoPor100: 0, bloqueado: true, motivo: "Prob < 50%" };
  }

  // Bloqueio EV
  if (evDecimal < tier.evBloqueio) {
    return { stake: 0, pct: 0, ev: evPct, descontoEv: 0, custoPor100: 0, bloqueado: true,
             motivo: `EV ${(evDecimal * 100).toFixed(1)}% abaixo do limite` };
  }

  // Stake base
  let stakePct = tier.base;

  // Bônus confiança (saturado em +2%)
  const excesso = Math.max(0, prob - marketThreshold);
  const bonus = Math.min(excesso * 0.3, 0.02);
  stakePct += bonus;

  // Desconto EV negativo
  let desconto = 1.0;
  if (evDecimal < 0) {
    desconto = Math.max(0.50, 1.0 + evDecimal);
    stakePct *= desconto;
  }

  // Cap
  stakePct = Math.min(stakePct, tier.cap);

  const stakeValor = Math.max(Math.round(bankroll * stakePct * 100) / 100, 0);
  const custoPor100 = evDecimal < 0 ? Math.round(-evDecimal * 10000) / 100 : 0;

  return {
    stake: stakeValor,
    pct: stakePct,
    ev: evPct,
    descontoEv: desconto,
    custoPor100,
    bloqueado: false,
  };
}

/* ── Format BRL ── */
function fmtBRL(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/* ── Props ── */
export type StakeMode = "kelly" | "oportunidade";

interface BankrollCardProps {
  bankroll: number;
  onBankrollChange: (v: number) => void;
  totalStake: number;
  avgEV: number;
  pickCount: number;
  stakeMode?: StakeMode;
  onStakeModeChange?: (m: StakeMode) => void;
  exposurePct?: number;
}

const PRESETS = [50, 100, 250, 500, 1000];

export default function BankrollCard({
  bankroll,
  onBankrollChange,
  totalStake,
  avgEV,
  pickCount,
  stakeMode = "kelly",
  onStakeModeChange,
  exposurePct,
}: BankrollCardProps) {
  return (
    <div className="bkr-card">
      <div className="bkr-header">
        <div className="bkr-title-row">
          <div>
            <span className="bkr-title">Banca Disponível</span>
            <span className="bkr-subtitle">
              {stakeMode === "kelly" ? "Quarter Kelly \u00B7 Cap 5%" : "Stake por Confian\u00E7a \u00B7 Cap vari\u00E1vel"}
            </span>
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

      {onStakeModeChange && (
        <div className="bkr-mode-toggle">
          <button
            className={`bkr-mode-btn ${stakeMode === "kelly" ? "bkr-mode-btn--active" : ""}`}
            onClick={() => onStakeModeChange("kelly")}
          >
            Kelly
          </button>
          <button
            className={`bkr-mode-btn ${stakeMode === "oportunidade" ? "bkr-mode-btn--active" : ""}`}
            onClick={() => onStakeModeChange("oportunidade")}
          >
            Oportunidade
          </button>
        </div>
      )}

      {exposurePct != null && exposurePct > 0 && (
        <div className="bkr-exposure">
          <div className="bkr-exposure-label">
            Exposição: {(exposurePct * 100).toFixed(1)}% / 15%
          </div>
          <div className="bkr-exposure-track">
            <div
              className={`bkr-exposure-bar ${exposurePct > 0.15 ? "bkr-exposure-bar--danger" : ""}`}
              style={{ width: `${Math.min(exposurePct / 0.15 * 100, 100)}%` }}
            />
          </div>
          {exposurePct > 0.15 && (
            <div className="bkr-exposure-alert">Acima do limite recomendado de 15%</div>
          )}
        </div>
      )}

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
