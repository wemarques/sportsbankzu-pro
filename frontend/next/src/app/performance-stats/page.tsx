"use client";
/**
 * #189-i — Painel de Confiabilidade do Modelo.
 * Substitui o esqueleto de template (F1) que ocupava esta rota.
 * Fonte: /api/metrics/brier (o mesmo endpoint do ReliabilityCard).
 * Gráficos em SVG puro seguindo src/lib/chartTokens.ts — sem lib de gráfico.
 */
import { useEffect, useState } from "react";
import { SERIES, STATUS, CHART, marketFamily, FAMILY_LABEL, MarketFamily } from "@/lib/chartTokens";

/* ── tipos do snapshot (backend/services/brier_service.py) ── */
interface Segment {
  n: number;
  accuracy: number;
  brier_model: number | null;
  brier_implied: number | null;
  delta: number | null;
}
interface Band {
  n: number;
  avg_prob: number;
  avg_outcome: number;
  gap: number;
}
interface Snapshot {
  total_picks: number;
  accuracy: number;
  brier_model: number | null;
  brier_implied: number | null;
  model_beats_house_ci?: {
    beats_bool: boolean;
    delta: number | null;
    p_value: number | null;
    n: number;
    significant_at_5pct: boolean;
    below_min_n: boolean;
  } | null;
  by_band?: Record<string, Band>;
  by_market?: Record<string, Segment>;
  by_league?: Record<string, Segment>;
}

const T = { t1: "#e8e8e8", t2: "#9aa4ad", t3: "#8b95a0", border: "#1e1e1e", card: "#111" };
const BAND_ORDER = ["<50%", "50-60%", "60-70%", "70-80%", "80%+"];
const mono: React.CSSProperties = { fontVariantNumeric: "tabular-nums" };

/* ── átomos ── */
function Tile({ label, value, sub, color }: { label: string; value: React.ReactNode; sub?: string; color?: string }) {
  return (
    <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "14px 16px", flex: "1 1 140px" }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: T.t3 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 800, color: color ?? T.t1, marginTop: 4, ...mono }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: T.t3, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Legend({ items }: { items: { swatch: React.CSSProperties; label: string }[] }) {
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11, color: T.t2, margin: "0 0 10px" }}>
      {items.map((it) => (
        <span key={it.label} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ display: "inline-block", width: 11, height: 11, borderRadius: "50%", ...it.swatch }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

function ChartCard({ title, sub, legend, children, reading }: {
  title: string; sub: string; legend?: { swatch: React.CSSProperties; label: string }[];
  children: React.ReactNode; reading?: string;
}) {
  return (
    <section style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 12, padding: "18px 20px 12px", marginBottom: 14 }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, color: T.t1, margin: 0 }}>{title}</h2>
      <p style={{ fontSize: 12, color: T.t2, margin: "2px 0 10px" }}>{sub}</p>
      {legend && <Legend items={legend} />}
      {children}
      {reading && <p style={{ fontSize: 12, color: T.t2, margin: "10px 0 4px" }}>{reading}</p>}
    </section>
  );
}

/* ── gráfico 1: calibração por banda (dumbbell previsto → ocorrido) ── */
function CalibrationChart({ bands }: { bands: Record<string, Band> }) {
  const rows = BAND_ORDER.filter((b) => bands[b]).map((b) => ({ label: b, ...bands[b] }));
  if (!rows.length) return null;
  const LX = 150, RX = 600, x = (v: number) => LX + ((v * 100 - 40) / 50) * (RX - LX);
  const rowH = 46, top = 34, H = top + rows.length * rowH + 16;
  return (
    <svg viewBox={`0 0 640 ${H}`} role="img" aria-label="Calibração: probabilidade prevista contra taxa real de acerto por banda" style={{ width: "100%", height: "auto", display: "block" }}>
      {[50, 60, 70, 80, 90].map((v) => (
        <g key={v}>
          <line x1={x(v / 100)} y1={20} x2={x(v / 100)} y2={H - 30} stroke={CHART.grid} />
          <text x={x(v / 100)} y={H - 12} fontSize={10} fill={CHART.axis} textAnchor="middle" style={mono}>{v}%</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = top + i * rowH;
        const xp = x(r.avg_prob), xo = x(r.avg_outcome);
        const d = (r.avg_outcome - r.avg_prob) * 100;
        return (
          <g key={r.label}>
            <title>{`${r.label}: previsto ${(r.avg_prob * 100).toFixed(1)}% · ocorrido ${(r.avg_outcome * 100).toFixed(1)}% · n=${r.n}`}</title>
            <text x={0} y={y + 4} fontSize={12} fontWeight={600} fill={T.t1}>{r.label}</text>
            <text x={0} y={y + 18} fontSize={10} fill={T.t3} style={mono}>n={r.n.toLocaleString("pt-BR")}</text>
            <line x1={xp} y1={y} x2={xo} y2={y} stroke={CHART.connector} strokeWidth={2} />
            <circle cx={xp} cy={y} r={5} fill={T.card} stroke={CHART.axis} strokeWidth={2} />
            <circle cx={xo} cy={y} r={5.5} fill={SERIES.s1} stroke={T.card} strokeWidth={2} />
            <text x={Math.max(xp, xo) + 14} y={y + 4} fontSize={11.5} fontWeight={600} fill={T.t1} style={mono}>
              {`${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(1)}pp`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ── gráfico 2: Brier modelo × casa por mercado, agrupado por família ── */
function BrierChart({ markets }: { markets: Record<string, Segment> }) {
  const fams: MarketFamily[] = ["gols", "cartoes", "escanteios", "1x2"];
  const grouped = fams
    .map((f) => ({
      fam: f,
      items: Object.entries(markets)
        .filter(([k, v]) => marketFamily(k) === f && v.n >= 50 && v.brier_model != null && v.brier_implied != null)
        .sort((a, b) => b[1].n - a[1].n)
        .slice(0, 3),
    }))
    .filter((g) => g.items.length > 0);
  const all = grouped.flatMap((g) => g.items.flatMap(([, v]) => [v.brier_model as number, v.brier_implied as number]));
  if (!all.length) return null;
  const lo = Math.min(...all) - 0.01, hi = Math.max(...all) + 0.01;
  const LX = 150, x = (v: number) => LX + ((v - lo) / (hi - lo)) * (600 - LX);
  let y = 30;
  const nodes: React.ReactNode[] = [];
  grouped.forEach((g) => {
    nodes.push(
      <text key={`f-${g.fam}`} x={0} y={y + 4} fontSize={10.5} fontWeight={600} fill={T.t3} letterSpacing="0.08em" style={{ textTransform: "uppercase" }}>
        {FAMILY_LABEL[g.fam]}
      </text>,
    );
    y += 24;
    g.items.forEach(([name, v]) => {
      const bm = v.brier_model as number, bi = v.brier_implied as number;
      const xm = x(bm), xh = x(bi);
      const better = bm < bi;
      const span = Math.abs(xh - xm);
      const txt = `${better ? "modelo" : "casa"} ${Math.abs(bi - bm).toFixed(4)}`;
      const yRow = y;
      nodes.push(
        <g key={`${g.fam}-${name}`}>
          <title>{`${name}: Brier modelo ${bm.toFixed(4)} vs casa ${bi.toFixed(4)} · n=${v.n}`}</title>
          <text x={0} y={yRow + 4} fontSize={12} fontWeight={600} fill={T.t1}>{name.length > 20 ? name.slice(0, 19) + "…" : name}</text>
          <text x={0} y={yRow + 18} fontSize={10} fill={T.t3} style={mono}>n={v.n.toLocaleString("pt-BR")}</text>
          <line x1={xm} y1={yRow} x2={xh} y2={yRow} stroke={CHART.connector} strokeWidth={2} />
          <circle cx={xh} cy={yRow} r={5} fill={T.card} stroke={SERIES.s2} strokeWidth={2.5} />
          <circle cx={xm} cy={yRow} r={5.5} fill={SERIES.s1} stroke={T.card} strokeWidth={2} />
          {span > 110 ? (
            <text x={(xm + xh) / 2} y={yRow - 10} fontSize={10.5} fontWeight={600} textAnchor="middle" fill={better ? STATUS.good : STATUS.bad} style={mono}>{txt}</text>
          ) : (
            <text x={Math.max(xm, xh) + 13} y={yRow + 4} fontSize={10.5} fontWeight={600} fill={better ? STATUS.good : STATUS.bad} style={mono}>{txt}</text>
          )}
        </g>,
      );
      y += 42;
    });
    y += 8;
  });
  const H = y + 18;
  const ticks = 4;
  return (
    <svg viewBox={`0 0 640 ${H}`} role="img" aria-label="Brier do modelo contra a casa por mercado — menor é melhor" style={{ width: "100%", height: "auto", display: "block" }}>
      {Array.from({ length: ticks + 1 }, (_, i) => lo + ((hi - lo) * i) / ticks).map((v) => (
        <g key={v}>
          <line x1={x(v)} y1={16} x2={x(v)} y2={H - 30} stroke={CHART.grid} />
          <text x={x(v)} y={H - 12} fontSize={10} fill={CHART.axis} textAnchor="middle" style={mono}>{v.toFixed(2)}</text>
        </g>
      ))}
      {nodes}
    </svg>
  );
}

/* ── gráfico 3: acurácia por liga ── */
function LeagueChart({ leagues, overall }: { leagues: Record<string, Segment>; overall: number }) {
  const rows = Object.entries(leagues)
    .filter(([, v]) => v.n >= 100)
    .sort((a, b) => b[1].accuracy - a[1].accuracy)
    .slice(0, 10);
  if (!rows.length) return null;
  const LX = 150, x = (v: number) => LX + (v / 85) * (600 - LX);
  const isCorrecao = (name: string) => /brasileir.{0,2}o\s*serie\s*a/i.test(name);
  let y = 30;
  const nodes: React.ReactNode[] = [];
  rows.forEach(([name, v]) => {
    const corr = isCorrecao(name);
    const xw = x(Math.min(v.accuracy, 85));
    const yRow = y;
    nodes.push(
      <g key={name}>
        <title>{`${name}: ${v.accuracy.toFixed(1)}% de acerto · n=${v.n}`}</title>
        <text x={0} y={yRow + 4} fontSize={12} fontWeight={600} fill={T.t1}>{name.length > 18 ? name.slice(0, 17) + "…" : name}</text>
        <text x={0} y={yRow + 18} fontSize={10} fill={T.t3} style={mono}>n={v.n.toLocaleString("pt-BR")}</text>
        <rect x={LX} y={yRow - 7} width={Math.max(xw - LX, 2)} height={14} rx={4} fill={corr ? STATUS.warn : SERIES.s1} />
        <text x={xw + 10} y={yRow + 4} fontSize={11.5} fontWeight={600} fill={T.t1} style={mono}>{v.accuracy.toFixed(1)}%</text>
        {corr && (
          <text x={LX} y={yRow + 26} fontSize={9.5} fontWeight={700} fill={STATUS.warn} letterSpacing="0.04em" style={mono}>
            MODO CORREÇÃO — plano #189 em execução
          </text>
        )}
      </g>,
    );
    y += corr ? 62 : 44;
  });
  const H = y + 16;
  const ref = x(overall);
  return (
    <svg viewBox={`0 0 640 ${H}`} role="img" aria-label="Acurácia por liga, com referência da média geral" style={{ width: "100%", height: "auto", display: "block" }}>
      <line x1={ref} y1={14} x2={ref} y2={H - 26} stroke={CHART.ref} strokeWidth={1.5} strokeDasharray="5 4" />
      <text x={ref} y={H - 10} fontSize={10} fill={CHART.axis} textAnchor="middle" style={mono}>{`média ${overall.toFixed(1)}%`}</text>
      {nodes}
    </svg>
  );
}

/* ── página ── */
export default function PerformanceStats() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    fetch("/api/metrics/brier", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => { if (!aborted) setSnap(j); })
      .catch((e) => { if (!aborted) setErr(String(e?.message ?? e)); });
    return () => { aborted = true; };
  }, []);

  const ci = snap?.model_beats_house_ci;
  return (
    <main style={{ background: "#0a0a0a", minHeight: "100vh", padding: "28px 16px", fontFamily: "'Inter',-apple-system,sans-serif" }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: T.t1, margin: "0 0 4px" }}>Confiabilidade do Modelo</h1>
        <p style={{ fontSize: 12.5, color: T.t2, margin: "0 0 18px" }}>
          Desempenho real dos prognósticos publicados, medido contra o resultado dos jogos e contra a odd implícita da casa.
        </p>

        {err && (
          <div role="status" style={{ color: STATUS.bad, fontSize: 13, padding: 20, background: T.card, border: `1px solid ${T.border}`, borderRadius: 10 }}>
            Métricas indisponíveis no momento ({err}). Tente novamente em instantes.
          </div>
        )}
        {!snap && !err && (
          <div role="status" aria-live="polite" style={{ color: T.t2, fontSize: 13, padding: 20 }}>Carregando métricas…</div>
        )}

        {snap && (
          <>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
              <Tile label="Picks auditados" value={snap.total_picks.toLocaleString("pt-BR")} />
              <Tile label="Acurácia" value={`${snap.accuracy?.toFixed(1)}%`} />
              <Tile label="Brier modelo" value={snap.brier_model?.toFixed(4) ?? "—"} sub="menor é melhor" />
              <Tile label="Brier casa" value={snap.brier_implied?.toFixed(4) ?? "—"} sub="odd implícita" />
              <Tile
                label="Modelo vence a casa?"
                value={ci ? (ci.below_min_n ? "n/d" : ci.beats_bool ? "Sim" : "Não") : "—"}
                sub={ci && !ci.below_min_n ? `p=${ci.p_value?.toFixed(4)} · N=${ci.n}` : undefined}
                color={ci?.significant_at_5pct ? STATUS.good : undefined}
              />
            </div>

            {snap.by_band && (
              <ChartCard
                title="Calibração por banda de confiança"
                sub="Probabilidade média prevista vs taxa real de acerto."
                legend={[
                  { swatch: { background: T.card, border: `2px solid ${CHART.axis}` }, label: "Previsto" },
                  { swatch: { background: SERIES.s1 }, label: "Ocorrido" },
                ]}
                reading="Bandas com o ponto azul à direita do vazado acertam MAIS do que prometem — o prognóstico publicado é conservador."
              >
                <CalibrationChart bands={snap.by_band} />
              </ChartCard>
            )}

            {snap.by_market && (
              <ChartCard
                title="Brier modelo × casa por mercado"
                sub="Menor é melhor. Cada linha compara o modelo com a odd implícita no mesmo jogo."
                legend={[
                  { swatch: { background: SERIES.s1 }, label: "Modelo" },
                  { swatch: { background: T.card, border: `2.5px solid ${SERIES.s2}` }, label: "Casa" },
                ]}
                reading="É o retrato da política de stake por família: onde o rótulo é verde, o modelo tem edge real."
              >
                <BrierChart markets={snap.by_market} />
              </ChartCard>
            )}

            {snap.by_league && (
              <ChartCard
                title="Acurácia por liga"
                sub="Ligas com pelo menos 100 picks auditados; tracejado = média geral."
              >
                <LeagueChart leagues={snap.by_league} overall={snap.accuracy} />
              </ChartCard>
            )}
          </>
        )}
      </div>
    </main>
  );
}
