import { C, CLS } from "./constants";
import { Badge, Ev, Odd, ProbBar, ResultBadge, StakeRow } from "./atoms";
import { LiveProgress } from "./LiveProgress";
import { calcQuarterKelly, calcStakeOportunidade } from "@/components/BankrollCard";
import { familyStakePolicy } from "@/components/BankrollCard";
import { fmtMercado, INFO_DISPLAY } from "@/lib/classifications";
import type { StakeMode } from "@/components/BankrollCard";
import type { MatchContext, PickData } from "./types";

const CorridorCard = ({
  pick,
  match,
  bankroll,
  stakeMode = "kelly",
}: {
  pick: PickData;
  match: MatchContext;
  bankroll: number;
  stakeMode?: StakeMode;
}) => {
  const legs = pick.corridorLegs ?? [];
  const min = pick.liveTarget?.min ?? 0;
  const max = pick.liveTarget?.max ?? 0;
  const scale = Math.max(6, Math.ceil(max + 2));
  const liveValue = match.isLive ? pick.liveTarget?.current ?? null : null;

  const corridorLabel =
    pick.type.toLowerCase().includes("corner") || pick.type.toLowerCase().includes("escante")
      ? "CORREDOR DE ESCANTEIOS"
      : pick.type.toLowerCase().includes("goal") || pick.type.toLowerCase().includes("gol")
      ? "CORREDOR DE GOLS"
      : "CORREDOR DE CARTÕES";

  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${C.dB}`,
        borderRadius: 8,
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Badge cls={pick.classification} />
        <ResultBadge result={pick.result} />
        <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{pick.label}</span>
      </div>
      <LiveProgress pick={pick} match={match} />
      <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 6, padding: 10 }}>
        <div
          style={{
            fontSize: 10,
            color: C.t3,
            fontWeight: 600,
            letterSpacing: "0.04em",
            marginBottom: 8,
          }}
        >
          {corridorLabel}
        </div>
        <div style={{ position: "relative", height: 28 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              position: "absolute",
              width: "100%",
              top: 20,
              fontSize: 9,
              color: C.t3,
            }}
          >
            {Array.from({ length: scale + 1 }, (_, n) => (
              <span key={n}>{n}</span>
            ))}
          </div>
          <div
            style={{
              position: "absolute",
              top: 6,
              left: 0,
              right: 0,
              height: 5,
              borderRadius: 3,
              background: "rgba(255,255,255,0.05)",
            }}
          />
          <div
            style={{
              position: "absolute",
              top: 4,
              left: `${(min / scale) * 100}%`,
              width: `${((max - min) / scale) * 100}%`,
              height: 9,
              borderRadius: 5,
              background: `linear-gradient(90deg,${C.gold},${C.green})`,
              opacity: 0.75,
            }}
          />
          {liveValue != null && (
            <div
              style={{
                position: "absolute",
                top: 0,
                left: `${(liveValue / scale) * 100}%`,
                width: 2,
                height: 14,
                borderRadius: 1,
                background: "#fff",
                transform: "translateX(-1px)",
                boxShadow: "0 0 6px rgba(255,255,255,0.5)",
              }}
            />
          )}
        </div>
        {legs.length > 0 && (
          <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
            {legs.map((leg, i) => {
              const kellyLeg = calcQuarterKelly(leg.prob, leg.odd, bankroll, pick.classification);
              const oportLeg = stakeMode === "oportunidade"
                ? calcStakeOportunidade(leg.prob, leg.odd, bankroll, pick.classification)
                : null;
              const legStake = stakeMode === "oportunidade" && oportLeg && !oportLeg.bloqueado
                ? { stake: oportLeg.stake, pct: oportLeg.pct }
                : kellyLeg;
              return (
                <div
                  key={`${leg.selection}-${i}`}
                  style={{
                    flex: 1,
                    background: "rgba(255,255,255,0.02)",
                    borderRadius: 5,
                    padding: "6px 8px",
                  }}
                >
                  <div style={{ fontSize: 11, color: C.t2, marginBottom: 4 }}>
                    {leg.selection}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Odd odd={leg.odd} />
                    <Ev ev={leg.ev} />
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <ProbBar prob={leg.prob} size="sm" />
                  </div>
                  {legStake.stake > 0 && (
                    <div
                      style={{
                        marginTop: 4,
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 10,
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      <span style={{ color: C.gold }}>
                        {(legStake.pct * 100).toFixed(1)}%
                      </span>
                      <span style={{ color: C.green, fontWeight: 700 }}>
                        R${legStake.stake.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {stakeMode === "oportunidade" && oportLeg && oportLeg.bloqueado && (
                    <div style={{ marginTop: 4, fontSize: 9, color: C.red }}>{oportLeg.motivo}</div>
                  )}
                  {stakeMode === "oportunidade" && oportLeg && !oportLeg.bloqueado && oportLeg.ev < 0 && (
                    <div style={{ marginTop: 2, fontSize: 9, color: C.orange }}>
                      Custo R${oportLeg.custoPor100.toFixed(0)}/R$100
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export const PickCard = ({
  pick,
  match,
  bankroll,
  stakeMode = "kelly",
}: {
  pick: PickData;
  match: MatchContext;
  bankroll: number;
  stakeMode?: StakeMode;
}) => {
  if (pick.isCorridorBet)
    return <CorridorCard pick={pick} match={match} bankroll={bankroll} stakeMode={stakeMode} />;
  const noBet = pick.classification === "NO_BET";
  // #189-g: pick de familia sem stake (gate #189-e) veste INFO cinza — o
  // badge azul "VIAVEL" + barra dourada contradiziam o "sem stake" do gate.
  const infoGated = familyStakePolicy(pick.label) === "none";
  const st = CLS[pick.classification] ?? CLS.NEUTRO;
  return (
    <div
      style={{
        background: C.card,
        border: `1px solid ${st.b}`,
        borderRadius: 8,
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        opacity: noBet ? 0.65 : 1,
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}
      >
        {infoGated ? (
          <span
            title={INFO_DISPLAY.tooltip}
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.04em",
              background: INFO_DISPLAY.bgColor,
              border: "1px solid rgba(154,163,173,0.28)",
              color: INFO_DISPLAY.color,
            }}
          >
            {INFO_DISPLAY.label}
          </span>
        ) : (
          <Badge cls={pick.classification} />
        )}
        <ResultBadge result={pick.result} />
        <span style={{ fontSize: 13, fontWeight: 700, color: C.t1 }}>{fmtMercado(pick.label)}</span>
      </div>
      <LiveProgress pick={pick} match={match} />
      <ProbBar prob={pick.rawProb} muted={infoGated} />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 10, color: C.t3 }}>Odd</span>
          <Odd odd={pick.bookOdd} fair={pick.fairOdd} />
        </div>
        {pick.fairOdd != null && (
          <span style={{ fontSize: 11, color: C.t3 }}>
            Fair {pick.fairOdd.toFixed(2)}
          </span>
        )}
        <Ev ev={pick.ev} />
      </div>
      <StakeRow pick={pick} bankroll={bankroll} stakeMode={stakeMode} />
      {noBet && pick.ev != null && pick.ev < 0 && pick.bookOdd != null && (
        <div
          style={{
            background: C.rS,
            border: `1px solid ${C.rB}`,
            borderRadius: 5,
            padding: "6px 10px",
            fontSize: 11,
            lineHeight: 1.5,
            color: C.t2,
          }}
        >
          <span style={{ color: C.red, fontWeight: 600 }}>Sem valor: </span>
          Prob {Math.round(pick.rawProb * 100)}% alta, mas odd {pick.bookOdd.toFixed(2)}{" "}
          exige {Math.round((1 / pick.bookOdd) * 100)}% para lucro.
        </div>
      )}
    </div>
  );
};
