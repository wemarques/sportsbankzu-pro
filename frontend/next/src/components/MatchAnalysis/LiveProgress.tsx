import { C } from "./constants";
import type { MatchContext, PickData } from "./types";

export const LiveProgress = ({
  pick,
  match,
}: {
  pick: PickData;
  match: MatchContext;
}) => {
  if (!match.isLive || !pick.liveTarget) return null;
  const minLeft = Math.max(0, 90 - match.minute);

  if (pick.liveDir === "corridor") {
    const min = pick.liveTarget.min ?? 0;
    const max = pick.liveTarget.max ?? 0;
    const current = pick.liveTarget.current;
    const inZone = current > min && current < max;
    const safe = current < max;
    const color = inZone ? C.green : safe ? C.gold : C.red;
    const label = inZone ? "DENTRO" : safe ? "EM ANDAMENTO" : "ESTOUROU";
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 8px",
          borderRadius: 4,
          background: `${color}11`,
          border: `1px solid ${color}33`,
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color,
            letterSpacing: "0.03em",
          }}
        >
          AO VIVO
        </span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {current}
        </span>
        <span style={{ fontSize: 10, color: C.t2 }}>
          de {min}-{max}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color,
            marginLeft: "auto",
          }}
        >
          {label}
        </span>
      </div>
    );
  }

  const line = pick.liveTarget.line ?? 0;
  const current = pick.liveTarget.current;
  const isOver = pick.liveDir === "over";
  const hit = isOver ? current > line : current < line;
  const pct = line > 0 ? Math.min((current / line) * 100, 115) : 0;
  const color = hit ? C.green : pct >= 80 ? C.gold : C.t2;
  const status = hit
    ? isOver
      ? "BATEU ✓"
      : "SEGURO ✓"
    : `${minLeft}' restantes`;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 8px",
        borderRadius: 4,
        background: "rgba(255,255,255,0.02)",
        border: `1px solid ${C.border}`,
      }}
    >
      <span
        style={{
          fontSize: 9,
          fontWeight: 700,
          color: C.blue,
          letterSpacing: "0.03em",
        }}
      >
        AO VIVO
      </span>
      <div
        style={{
          flex: 1,
          height: 4,
          borderRadius: 2,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(pct, 100)}%`,
            height: "100%",
            borderRadius: 2,
            background: color,
          }}
        />
      </div>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {current}
      </span>
      <span style={{ fontSize: 10, color: C.t3 }}>/ {line}</span>
      <span style={{ fontSize: 9, color }}>{status}</span>
    </div>
  );
};
