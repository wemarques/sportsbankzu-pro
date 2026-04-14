import { C } from "./constants";
import type { MatchContext } from "./types";

export const LiveTracker = ({ match }: { match: MatchContext }) => {
  if (!match.isLive) return null;
  const s = match.liveStats;
  const yellowSum = s.homeYellow + s.awayYellow;
  const redSum = s.homeRed + s.awayRed;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 8,
        background: "rgba(255,255,255,0.02)",
        borderRadius: 6,
        padding: 10,
        border: `1px solid ${C.border}`,
      }}
    >
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              fontSize: 10,
              color: C.t3,
              fontWeight: 600,
              letterSpacing: "0.04em",
            }}
          >
            ESCANTEIOS
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: C.green,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {s.totalCorners}
          </span>
        </div>
        <div style={{ display: "flex", gap: 4, fontSize: 10, color: C.t2 }}>
          <span>
            {match.home.slice(0, 3).toUpperCase()} {s.homeCorners}
          </span>
          <span style={{ color: C.t3 }}>•</span>
          <span>
            {match.away.slice(0, 3).toUpperCase()} {s.awayCorners}
          </span>
        </div>
      </div>
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              fontSize: 10,
              color: C.t3,
              fontWeight: 600,
              letterSpacing: "0.04em",
            }}
          >
            CARTÕES
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: C.gold,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {s.totalCards}
          </span>
        </div>
        <div style={{ display: "flex", gap: 4, fontSize: 10, color: C.t2 }}>
          <span style={{ color: "#facc15" }}>{yellowSum}A</span>
          {redSum > 0 && <span style={{ color: C.red }}>{redSum}V</span>}
        </div>
      </div>
    </div>
  );
};
