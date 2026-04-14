import { C, CLS } from "./constants";
import type { ClassificationKey } from "./types";

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
