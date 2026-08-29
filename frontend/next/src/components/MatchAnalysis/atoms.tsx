import { useState } from "react";
import { C, CLS } from "./constants";
import { calcQuarterKelly, calcStakeOportunidade } from "@/components/BankrollCard";
import type { StakeMode } from "@/components/BankrollCard";
import type { ClassificationKey, PickData, PickResult } from "./types";

export const Badge = ({ cls }: { cls: ClassificationKey }) => {
  const s = CLS[cls] ?? CLS.NEUTRO;
  return (
    <span
      style={{
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.04em",
        background: s.bg,
        border: `1px solid ${s.b}`,
        color: s.c,
      }}
    >
      {s.l}
    </span>
  );
};

export const Ev = ({ ev }: { ev: number | null }) => {
  if (ev == null) return null;
  const color = ev >= 0.05 ? C.green : ev >= 0 ? C.orange : C.red;
  return (
    <span
      style={{
        color,
        fontSize: 12,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      EV {ev >= 0 ? "+" : ""}
      {(ev * 100).toFixed(1)}%
    </span>
  );
};

export const Odd = ({
  odd,
  fair,
}: {
  odd: number | null;
  fair?: number | null;
}) => {
  if (!odd) return <span style={{ color: C.t3, fontSize: 11 }}>sem odd</span>;
  const good = !!fair && odd > fair;
  return (
    <span
      style={{
        padding: "2px 7px",
        borderRadius: 4,
        fontSize: 12,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums",
        background: good ? C.gS : "rgba(255,255,255,0.04)",
        border: `1px solid ${good ? C.gB : "rgba(255,255,255,0.08)"}`,
        color: good ? C.green : C.t1,
      }}
    >
      {odd.toFixed(2)}
    </span>
  );
};

export const ResultBadge = ({ result }: { result?: PickResult }) => {
  if (!result) return null;
  const isHit = result === "hit";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 22,
        height: 22,
        borderRadius: 4,
        fontSize: 13,
        fontWeight: 800,
        background: isHit ? "rgba(0,223,130,0.15)" : "rgba(239,68,68,0.85)",
        color: isHit ? C.green : "#ffffff",
        border: `1px solid ${isHit ? "rgba(0,223,130,0.3)" : "rgba(239,68,68,1)"}`,
        flexShrink: 0,
      }}
      aria-label={isHit ? "Acertou" : "Errou"}
    >
      {isHit ? "✓" : "✗"}
    </span>
  );
};

export const StakeRow = ({
  pick,
  bankroll,
  stakeMode = "kelly",
}: {
  pick: PickData;
  bankroll: number;
  stakeMode?: StakeMode;
}) => {
  // Kelly calculation
  const kellyResult = (pick.bookOdd && pick.classification !== "NO_BET" && bankroll > 0)
    ? calcQuarterKelly(pick.rawProb, pick.bookOdd, bankroll, pick.classification)
    : null;

  // Oportunidade calculation
  const oportResult = (bankroll > 0 && pick.classification !== "NO_BET")
    ? calcStakeOportunidade(pick.rawProb, pick.bookOdd ?? 0, bankroll, pick.classification)
    : null;

  const suggestedPct = stakeMode === "oportunidade"
    ? (oportResult && !oportResult.bloqueado ? oportResult.pct * 100 : null)
    : (kellyResult && kellyResult.stake > 0 ? kellyResult.pct * 100 : null);

  const [customPct, setCustomPct] = useState<string>("");
  const isCustom = customPct !== "";
  const activePct = isCustom ? parseFloat(customPct) || 0 : (suggestedPct ?? 0);
  const stakeValue = Math.max(Math.round(bankroll * (activePct / 100) * 100) / 100, 0);

  if (bankroll <= 0 || pick.classification === "NO_BET") return null;

  // Sem odd real não há EV nem stake — ocultar a linha inteira em vez de
  // sugerir valor (o card já mostra "Odd sem odd" logo acima).
  if (pick.bookOdd == null || pick.bookOdd <= 1) return null;

  // #189-d: EV negativo na odd atual → o pick vira ordem-limite. Em vez de
  // stake, mostrar a odd mínima (fair) a aguardar. Vale para os dois modos.
  const evNow = pick.ev ?? (pick.rawProb > 0 ? pick.rawProb * pick.bookOdd - 1 : null);
  if (evNow != null && evNow < 0 && !isCustom) {
    const fairOdd = pick.fairOdd ?? (pick.rawProb > 0 ? 1 / pick.rawProb : null);
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          borderRadius: 5,
          background: "rgba(245,181,74,0.05)",
          border: "1px solid rgba(245,181,74,0.2)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 10, color: C.gold, fontWeight: 700 }}>
          Aguarde odd ≥ {fairOdd != null ? fairOdd.toFixed(2) : "—"}
        </span>
        <span style={{ fontSize: 10, color: C.t3 }}>
          EV {(evNow * 100).toFixed(1)}% na odd atual {pick.bookOdd.toFixed(2)} — sem stake
        </span>
      </div>
    );
  }

  // If oportunidade mode and blocked, show reason
  if (stakeMode === "oportunidade" && oportResult && oportResult.bloqueado && !isCustom) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          borderRadius: 5,
          background: "rgba(239,68,68,0.04)",
          border: `1px solid rgba(239,68,68,0.15)`,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 10, color: C.red, fontWeight: 600 }}>
          {oportResult.motivo}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 10px",
        borderRadius: 5,
        background: "rgba(255,255,255,0.02)",
        border: `1px solid ${C.border}`,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 10, color: C.t3 }}>Banca</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: C.t2, fontVariantNumeric: "tabular-nums" }}>
          R${bankroll.toLocaleString("pt-BR")}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
        <input
          type="number"
          inputMode="decimal"
          placeholder={suggestedPct != null ? suggestedPct.toFixed(1) : "0"}
          value={customPct}
          onChange={(e) => setCustomPct(e.target.value)}
          style={{
            width: 48,
            padding: "2px 4px",
            borderRadius: 4,
            border: `1px solid ${isCustom ? C.gold : C.border}`,
            background: isCustom ? "rgba(255,195,0,0.08)" : "rgba(255,255,255,0.04)",
            color: isCustom ? C.gold : C.t2,
            fontSize: 11,
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            textAlign: "right",
            outline: "none",
          }}
          min={0}
          max={100}
          step={0.1}
        />
        <span style={{ fontSize: 10, color: C.t3 }}>%</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 10, color: C.t3 }}>Stake</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: stakeValue > 0 ? C.green : C.t3, fontVariantNumeric: "tabular-nums" }}>
          R${stakeValue.toFixed(2)}
        </span>
      </div>
      {stakeMode === "oportunidade" && oportResult && oportResult.ev < 0 && !oportResult.bloqueado && !isCustom && (
        <span style={{ fontSize: 9, color: C.orange }}>
          Custo R${oportResult.custoPor100.toFixed(0)}/R$100
        </span>
      )}
      {isCustom && (
        <button
          onClick={() => setCustomPct("")}
          style={{
            padding: "1px 6px",
            borderRadius: 3,
            border: `1px solid ${C.border}`,
            background: "transparent",
            color: C.t3,
            fontSize: 9,
            cursor: "pointer",
          }}
          title={stakeMode === "oportunidade" ? "Voltar ao Oportunidade sugerido" : "Voltar ao Kelly sugerido"}
        >
          Auto
        </button>
      )}
    </div>
  );
};

export const ProbBar = ({
  prob,
  size = "md",
}: {
  prob: number;
  size?: "sm" | "md";
}) => {
  const pct = Math.round(prob * 100);
  const h = size === "sm" ? 4 : 5;
  const color = pct >= 70 ? C.green : pct >= 50 ? C.gold : C.orange;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          flex: 1,
          height: h,
          borderRadius: h,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            borderRadius: h,
            background: color,
            transition: "width 0.4s",
          }}
        />
      </div>
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color,
          fontVariantNumeric: "tabular-nums",
          minWidth: 36,
        }}
      >
        {pct}%
      </span>
    </div>
  );
};
