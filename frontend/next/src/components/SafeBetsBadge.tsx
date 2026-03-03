import React from "react";
import { Badge } from "./ui/badge";
import type { SafeBetTag, SafeBetsResult, RiskLevel } from "@/lib/leagues";
import { SAFE_BET_TAG_CONFIG } from "@/lib/leagues";

type Props = {
  result: SafeBetsResult;
  compact?: boolean;
};

function RiskBadge({ level }: { level: RiskLevel }) {
  const config: Record<RiskLevel, { label: string; className: string }> = {
    SAFE: { label: "SAFE", className: "bg-emerald-700 text-white" },
    MODERATE: { label: "MODERADO", className: "bg-yellow-600 text-black" },
    NO_BET: { label: "NO BET", className: "bg-red-700 text-white" },
  };
  const c = config[level] ?? config.NO_BET;
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${c.className}`}
    >
      {c.label}
    </span>
  );
}

function TagBadge({ tag }: { tag: SafeBetTag }) {
  const cfg = SAFE_BET_TAG_CONFIG[tag];
  if (!cfg) return null;
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${cfg.color}`}
      title={cfg.description}
    >
      {cfg.label}
    </span>
  );
}

export default function SafeBetsBadge({ result, compact = false }: Props) {
  if (!result) return null;

  // Blocked match
  if (result.blocked) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <RiskBadge level="NO_BET" />
        {!compact && (
          <span className="text-xs text-red-400">{result.block_reason}</span>
        )}
      </div>
    );
  }

  // No tags found
  if (!result.tags || result.tags.length === 0 || (result.tags.length === 1 && result.tags[0] === "NO_BET")) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <RiskBadge level={result.risk_level} />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <RiskBadge level={result.risk_level} />
      {result.tags
        .filter((t) => t !== "NO_BET")
        .map((tag) => (
          <TagBadge key={tag} tag={tag} />
        ))}
    </div>
  );
}

export function SafeBetsDetail({ result }: { result: SafeBetsResult }) {
  if (!result) return null;

  const dna = result.layer1_dna ?? {};
  const risk = result.layer2_risk ?? {};

  return (
    <div className="space-y-3 rounded-lg border border-[var(--border)] p-3">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">Safe Bets Analysis</span>
        <SafeBetsBadge result={result} />
      </div>

      {/* Layer 1: League DNA */}
      <div className="text-xs space-y-1">
        <div className="font-medium text-[var(--text-secondary)]">
          DNA da Liga
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded bg-[var(--card)] px-2 py-0.5 border border-[var(--border)]">
            Categoria: {String(dna.category ?? "—")}
          </span>
          {dna.is_aggressive && (
            <span className="rounded bg-orange-900/40 px-2 py-0.5 text-orange-300 border border-orange-800">
              Agressiva (Cartões)
            </span>
          )}
          <span className="rounded bg-[var(--card)] px-2 py-0.5 border border-[var(--border)]">
            Avg Gols: {dna.season_avg_goals != null ? Number(dna.season_avg_goals).toFixed(2) : "—"}
          </span>
        </div>
      </div>

      {/* Layer 2: Risk */}
      <div className="text-xs space-y-1">
        <div className="font-medium text-[var(--text-secondary)]">
          Semáforo de Risco
        </div>
        <div
          className={`rounded px-2 py-1 ${
            result.blocked
              ? "bg-red-900/30 text-red-300 border border-red-800"
              : "bg-emerald-900/30 text-emerald-300 border border-emerald-800"
          }`}
        >
          {String(risk.reason ?? "—")}
        </div>
      </div>

      {/* Layer 3: Strategies */}
      {result.layer3_strategies && result.layer3_strategies.length > 0 && (
        <div className="text-xs space-y-1">
          <div className="font-medium text-[var(--text-secondary)]">
            Estratégias Avaliadas
          </div>
          <div className="space-y-1">
            {result.layer3_strategies.map((s, i) => (
              <div
                key={`${s.strategy}-${i}`}
                className={`flex items-center justify-between rounded px-2 py-1 ${
                  s.passed
                    ? "bg-emerald-900/20 border border-emerald-800"
                    : "bg-[var(--card)] border border-[var(--border)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      s.passed ? "bg-emerald-500" : "bg-gray-500"
                    }`}
                  />
                  <span className="font-medium">{s.market_label}</span>
                </div>
                <div className="flex items-center gap-2">
                  {s.confidence != null && (
                    <span className="text-[var(--text-secondary)]">
                      {s.confidence.toFixed(0)}%
                    </span>
                  )}
                  <span
                    className={
                      s.passed ? "text-emerald-400 font-bold" : "text-gray-500"
                    }
                  >
                    {s.passed ? "PASS" : "FAIL"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
