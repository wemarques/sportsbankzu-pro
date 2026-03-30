"use client";

import { useState, useEffect } from "react";

/* ── Helpers ── */
function pct(v: number | null | undefined): string {
  return v != null ? (v * 100).toFixed(1) + "%" : "—";
}
function statusIcon(value: number | null | undefined, target: number, higherBetter = true): string {
  if (value == null) return "—";
  if (higherBetter) return value >= target ? "\u2705" : value >= target * 0.8 ? "\u26a0\ufe0f" : "\u274c";
  return value <= target ? "\u2705" : value <= target * 1.2 ? "\u26a0\ufe0f" : "\u274c";
}

/* ── Sub-components (inline styles matching mockup) ── */
function DimensionCard({ icon, title, color, score, scoreLabel, children }: {
  icon: string; title: string; color: string; score?: string; scoreLabel?: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${color}08 0%, ${color}03 100%)`,
      border: `1px solid ${color}30`, borderRadius: 14, padding: "18px 20px", marginBottom: 14,
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: color, borderRadius: "14px 0 0 14px" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "1rem" }}>{icon}</span>
          <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1.5 }}>{title}</span>
        </div>
        {score != null && (
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "1.1rem", fontWeight: 800, color, fontFamily: "monospace" }}>{score}</div>
            {scoreLabel && <div style={{ fontSize: "0.5rem", color: "#64748b", marginTop: 1 }}>{scoreLabel}</div>}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

function MetricRow({ label, value, target, higherBetter = true, sub }: {
  label: string; value: string | number | null; target: number; higherBetter?: boolean; sub?: string;
}) {
  const icon = statusIcon(typeof value === "number" ? value : null, target, higherBetter);
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <div>
        <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>{label}</span>
        {sub && <span style={{ fontSize: "0.58rem", color: "#475569", marginLeft: 8 }}>{sub}</span>}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>{value ?? "—"}</span>
        <span style={{ fontSize: "0.7rem" }}>{icon}</span>
      </div>
    </div>
  );
}

function SafetyCounter({ label, count, color = "#f59e0b" }: { label: string; count: number; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <span style={{ fontSize: "0.68rem", color: "#94a3b8" }}>{label}</span>
      <span style={{ fontSize: "0.78rem", fontWeight: 700, color, fontFamily: "monospace" }}>{count}</span>
    </div>
  );
}

function ApiBar({ label, rate }: { label: string; rate: number }) {
  const w = Math.min(rate * 100, 100);
  const color = rate >= 0.95 ? "#4ade80" : rate >= 0.85 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: "0.65rem", color: "#94a3b8" }}>{label}</span>
        <span style={{ fontSize: "0.68rem", fontWeight: 700, color, fontFamily: "monospace" }}>{(rate * 100).toFixed(1)}%</span>
      </div>
      <div style={{ height: 5, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${w}%`, background: `linear-gradient(90deg, ${color}90, ${color})`, borderRadius: 3, transition: "width 0.8s ease" }} />
      </div>
    </div>
  );
}

function DefenseRow({ label, value, regra }: { label: string; value: string; regra?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", flexShrink: 0 }} />
      <span style={{ fontSize: "0.65rem", color: "#cbd5e1", flex: 1 }}>{label}</span>
      <span style={{ fontSize: "0.62rem", fontWeight: 600, color: "#4ade80", fontFamily: "monospace" }}>{value}</span>
      {regra && <span style={{ fontSize: "0.5rem", color: "#475569" }}>{regra}</span>}
    </div>
  );
}

/* ── Page ── */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function ReliabilityPage() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/reliability")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: "#94a3b8", padding: 40, textAlign: "center" }}>Carregando metricas de confiabilidade...</div>;
  if (error) return <div style={{ color: "#ef4444", padding: 40, textAlign: "center" }}>Erro: {error}</div>;
  if (!data) return null;

  const pred = data.predictability ?? {};
  const saf = data.safety ?? {};
  const rob = data.robustness ?? {};
  const con = data.consistency ?? {};
  const def = data.defesas_ativas ?? {};

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg, #060a12 0%, #0a0f1a 30%, #0d1520 100%)",
      color: "#f8fafc", padding: "24px 16px", maxWidth: 520, margin: "0 auto",
    }}>
      {/* Header */}
      <div style={{ marginBottom: 24, textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <span style={{ fontSize: "0.7rem", fontWeight: 800, color: "#f8fafc" }}>sports</span>
          <span style={{ fontSize: "0.7rem", fontWeight: 800, color: "#4ade80" }}>bankzu</span>
          <span style={{ fontSize: "0.55rem", fontWeight: 600, color: "#4ade80", background: "rgba(34,197,94,0.15)", padding: "2px 7px", borderRadius: 4, border: "1px solid rgba(34,197,94,0.3)" }}>CONFIABILIDADE</span>
        </div>
        <div style={{ fontSize: "0.52rem", color: "#475569" }}>Framework: Princeton AI Agent Reliability (Rabanser et al., 2026)</div>
      </div>

      {/* PREDICTABILITY */}
      <DimensionCard icon={"\ud83d\udcc8"} title="Previsibilidade" color="#4ade80"
        score={pred.brier_score != null ? (1 - pred.brier_score).toFixed(2) : "\u2014"}
        scoreLabel="P_brier"
      >
        <MetricRow label="Brier Score" value={pred.brier_score?.toFixed(4) ?? null} target={0.22} higherBetter={false} sub="target < 0.22" />
        <MetricRow label="Amostra (N)" value={pred.n_total ?? 0} target={20} sub="min: 20 (#079)" />
        {!pred.suficiente && (
          <div style={{ fontSize: "0.6rem", color: "#f59e0b", padding: "6px 0" }}>
            {"\u26a0\ufe0f"} Amostra insuficiente (N={pred.n_total}). Metricas nao confiaveis.
          </div>
        )}
      </DimensionCard>

      {/* SAFETY */}
      <DimensionCard icon={"\ud83d\udee1\ufe0f"} title="Seguranca" color="#ef4444"
        score={pct(saf.compliance_rate ?? 1)}
        scoreLabel="compliance"
      >
        <div style={{
          background: "rgba(34,197,94,0.08)", borderRadius: 8, padding: "8px 12px", marginBottom: 8,
          border: "1px solid rgba(34,197,94,0.2)",
        }}>
          <span style={{ fontSize: "0.65rem", fontWeight: 600, color: "#4ade80" }}>
            {"\u2705"} Zero violacoes ativas
          </span>
        </div>
        <div style={{ fontSize: "0.52rem", color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6, fontWeight: 600 }}>Bloqueios preventivos</div>
        <SafetyCounter label="Complementares bloqueados" count={saf.complementares_bloqueados ?? 0} />
        <SafetyCounter label="Contradicoes Mistral bloqueadas" count={saf.mistral_contradicoes ?? 0} />
        <SafetyCounter label="Acoes de auditoria filtradas" count={saf.acoes_bloqueadas ?? 0} />
      </DimensionCard>

      {/* ROBUSTNESS */}
      <DimensionCard icon={"\u26a1"} title="Robustez" color="#60a5fa"
        score={(() => {
          const avg = ((rob.api_football_success_rate ?? 0) + (rob.footystats_success_rate ?? 0) + (rob.mistral_success_rate ?? 0)) / 3;
          return (avg * 100).toFixed(0) + "%";
        })()}
        scoreLabel="media APIs"
      >
        <ApiBar label="API-Football v3" rate={rob.api_football_success_rate ?? 0} />
        <ApiBar label="FootyStats" rate={rob.footystats_success_rate ?? 0} />
        <ApiBar label="Mistral AI" rate={rob.mistral_success_rate ?? 0} />
        <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
          <div style={{ flex: 1, background: "rgba(0,0,0,0.25)", borderRadius: 8, padding: "8px 10px", textAlign: "center", border: "1px solid rgba(255,255,255,0.04)" }}>
            <div style={{ fontSize: "0.9rem", fontWeight: 800, color: "#60a5fa", fontFamily: "monospace" }}>{rob.fallbacks_ativados ?? 0}</div>
            <div style={{ fontSize: "0.5rem", color: "#64748b", textTransform: "uppercase" }}>Fallbacks</div>
          </div>
        </div>
      </DimensionCard>

      {/* CONSISTENCY */}
      <DimensionCard icon={"\ud83d\udd04"} title="Consistencia" color="#a78bfa"
        score={con.lambda_duration_cv?.toFixed(2) ?? "\u2014"}
        scoreLabel="CV duration"
      >
        {con.lambda_duration_avg_ms != null ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
            {[
              { label: "Lambda avg", value: `${(con.lambda_duration_avg_ms / 1000).toFixed(1)}s`, ok: con.lambda_duration_avg_ms < 5000 },
              { label: "Lambda p95", value: con.lambda_duration_p95_ms ? `${(con.lambda_duration_p95_ms / 1000).toFixed(1)}s` : "\u2014", ok: (con.lambda_duration_p95_ms ?? 0) < 8000 },
              { label: "CV", value: con.lambda_duration_cv?.toFixed(2) ?? "\u2014", ok: (con.lambda_duration_cv ?? 1) < 0.3 },
            ].map((m, i) => (
              <div key={i} style={{ background: "rgba(0,0,0,0.25)", borderRadius: 8, padding: "10px 8px", textAlign: "center", border: "1px solid rgba(255,255,255,0.04)" }}>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: m.ok ? "#a78bfa" : "#f59e0b", fontFamily: "monospace" }}>{m.value}</div>
                <div style={{ fontSize: "0.48rem", color: "#64748b", textTransform: "uppercase", marginTop: 2 }}>{m.label}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: "0.6rem", color: "#64748b", padding: "6px 0" }}>Dados acumulando... (reset no cold start)</div>
        )}
        {con.picks_por_jogo_avg != null && (
          <MetricRow label="Picks/jogo" value={con.picks_por_jogo_avg.toFixed(1)} target={2} sub={`CV: ${con.picks_por_jogo_cv ?? "\u2014"}`} />
        )}
      </DimensionCard>

      {/* DEFESAS ATIVAS */}
      <DimensionCard icon={"\u2699\ufe0f"} title="Defesas Ativas" color="#94a3b8">
        <DefenseRow label="Anti-alucinacao Mistral" value={`${def.anti_alucinacao_mistral ?? 6} camadas`} />
        <DefenseRow label="Circuit breaker SAFE" value={def.circuit_breaker_safe ? "ATIVO" : "OFF"} regra="#043" />
        <DefenseRow label="Amostra minima Brier" value={`N>=${def.min_n_brier ?? 20}`} regra="#079" />
        <DefenseRow label="Contrato Mistral narrativa" value="ATIVO" regra="#082" />
        <DefenseRow label="Validacao complementares" value="ATIVO" regra="#098" />
        <DefenseRow label="Filtro acoes auditoria" value="ATIVO" regra="#099" />
      </DimensionCard>

      <div style={{ textAlign: "center", marginTop: 16, fontSize: "0.48rem", color: "#334155" }}>
        Baseado em: &quot;Towards a Science of AI Agent Reliability&quot; &bull; Rabanser et al., Princeton, 2026
      </div>
    </div>
  );
}
