"use client";

import React, { useEffect, useState } from "react";

/* #178 — model_beats_house with CI shape (inline; matches backend brier_service._with_ci) */
type ModelBeatsHouseCI = {
  beats_bool: boolean;
  delta: number | null;
  p_value: number | null;
  n: number;
  significant_at_5pct: boolean;
  below_min_n: boolean;
};

/* eslint-disable @typescript-eslint/no-explicit-any */

/* ── Empty state helper ── */
function EmptyVal({ text = "Aguardando dados" }: { text?: string }) {
  return <span style={{ fontStyle: "italic", color: "#64748b", fontSize: "0.78rem" }}>{text}</span>;
}

function displayRate(rate: number | null | undefined): React.ReactNode {
  if (rate == null) return <EmptyVal text="Sem registros" />;
  if (rate === 0) return <EmptyVal text="Sem chamadas" />;
  return `${(rate * 100).toFixed(1)}%`;
}

/* ���─ Sub-components ── */
function DimCard({ icon, title, color, score, sub, children }: {
  icon: string; title: string; color: string; score?: React.ReactNode; sub?: string; children: React.ReactNode;
}) {
  return (
    <div className="reliability-dimension-card" style={{
      background: `linear-gradient(135deg, ${color}08 0%, ${color}03 100%)`,
      border: `1px solid ${color}30`, borderRadius: 12, padding: "18px 22px",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: color }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ fontSize: "1.1rem" }}>{icon}</span>
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#e2e8f0", textTransform: "uppercase", letterSpacing: 1.2 }}>{title}</span>
        </div>
        {score != null && (
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "1.3rem", fontWeight: 800, color, fontFamily: "monospace" }}>{score}</div>
            {sub && <div style={{ fontSize: "0.6rem", color: "#64748b" }}>{sub}</div>}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <div>
        <span style={{ fontSize: "0.78rem", color: "#cbd5e1" }}>{label}</span>
        {sub && <span style={{ fontSize: "0.62rem", color: "#64748b", marginLeft: 8 }}>{sub}</span>}
      </div>
      <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>
        {value ?? <EmptyVal />}
      </span>
    </div>
  );
}

/* #178 — model_beats_house with Wilcoxon p-value badge.
   Self-contained: fetches /api/metrics/brier on mount.
   Three states: below_min_n (gray), significant (green), not significant (yellow). */
function ModelBeatsHouseRow() {
  const [ci, setCi] = useState<ModelBeatsHouseCI | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    fetch("/api/metrics/brier", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => {
        if (aborted) return;
        const next = j?.model_beats_house_ci ?? null;
        setCi(next);
      })
      .catch((e) => {
        if (!aborted) setErr(String(e?.message ?? e));
      });
    return () => {
      aborted = true;
    };
  }, []);

  let value: React.ReactNode = <EmptyVal text="Carregando..." />;
  if (err) {
    value = <EmptyVal text="Indisponível" />;
  } else if (ci) {
    if (ci.below_min_n) {
      value = (
        <span style={{ color: "#94a3b8", fontWeight: 600, fontFamily: "monospace" }}>
          Indeterminado (N={ci.n}&lt;20)
        </span>
      );
    } else if (ci.significant_at_5pct) {
      value = (
        <span style={{ color: "#4ade80", fontWeight: 700, fontFamily: "monospace" }}>
          Sim (delta {ci.delta?.toFixed(4)}, p={ci.p_value?.toFixed(3)}, N={ci.n})
        </span>
      );
    } else {
      value = (
        <span style={{ color: "#f59e0b", fontWeight: 600, fontFamily: "monospace" }}>
          Sem significância (delta {ci.delta?.toFixed(4) ?? "?"}, p={ci.p_value?.toFixed(3) ?? "?"}, N={ci.n})
        </span>
      );
    }
  }

  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <div>
        <span style={{ fontSize: "0.78rem", color: "#cbd5e1" }}>Bate o mercado?</span>
        <span style={{ fontSize: "0.62rem", color: "#64748b", marginLeft: 8 }}>Wilcoxon paired</span>
      </div>
      <span style={{ fontSize: "0.78rem" }}>{value}</span>
    </div>
  );
}

function ApiBar({ label, rate }: { label: string; rate: number }) {
  const hasData = rate > 0;
  const color = !hasData ? "#475569" : rate >= 0.95 ? "#4ade80" : rate >= 0.85 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: "0.72rem", color: "#cbd5e1" }}>{label}</span>
        <span style={{ fontSize: "0.78rem", fontWeight: 700, color, fontFamily: "monospace" }}>
          {hasData ? `${(rate * 100).toFixed(1)}%` : <EmptyVal text="Sem chamadas" />}
        </span>
      </div>
      <div style={{ height: 5, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${hasData ? Math.min(rate * 100, 100) : 0}%`, background: hasData ? color : "transparent", borderRadius: 3, transition: "width 0.6s" }} />
      </div>
    </div>
  );
}

/* ── Main ── */
export default function ReliabilityCard({ data, onClose }: { data: any; onClose: () => void }) {
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const pred = data?.predictability ?? {};
  const saf = data?.safety ?? {};
  const rob = data?.robustness ?? {};
  const con = data?.consistency ?? {};
  const def = data?.defesas_ativas ?? {};

  const hasAnyData = pred.n_total > 0 || (rob.api_football_success_rate ?? 0) > 0 || con.lambda_duration_avg_ms != null;
  const [copied, setCopied] = useState(false);

  const handleCopyReport = () => {
    const p = (v: number | null | undefined) => v != null ? (v * 100).toFixed(1) + "%" : "N/A";
    const lines = [
      "\u2550\u2550\u2550\u2550\u2550 CONFIABILIDADE \u2014 SportsBankZu Pro \u2550\u2550\u2550\u2550\u2550",
      "",
      "\ud83d\udcc8 PREVISIBILIDADE",
      `  Brier Score: ${pred.brier_score?.toFixed(4) ?? "N/A"} (target < 0.22)`,
      `  Amostra (N): ${pred.n_total ?? 0} (min: 20)`,
      "",
      "\ud83d\udee1\ufe0f SEGURANCA",
      `  Conformidade: ${p(saf.compliance_rate ?? 1)}`,
      `  Complementares bloqueados: ${saf.complementares_bloqueados ?? 0}`,
      `  Contradições da IA corrigidas: ${saf.mistral_contradicoes ?? 0}`,
      `  Ações bloqueadas pela auditoria: ${saf.acoes_bloqueadas ?? 0}`,
      "",
      "\u26a1 ROBUSTEZ",
      `  API-Football: ${p(rob.api_football_success_rate)}`,
      `  FootyStats: ${p(rob.footystats_success_rate)}`,
      `  Mistral AI: ${p(rob.mistral_success_rate)}`,
      `  Fallbacks: ${rob.fallbacks_ativados ?? 0}`,
      "",
      "\ud83d\udd04 CONSISTENCIA",
      `  Tempo de análise (média): ${con.lambda_duration_avg_ms != null ? (con.lambda_duration_avg_ms / 1000).toFixed(1) + "s" : "N/A"}`,
      `  Tempo de análise (p95): ${con.lambda_duration_p95_ms != null ? (con.lambda_duration_p95_ms / 1000).toFixed(1) + "s" : "N/A"}`,
      `  CV: ${con.lambda_duration_cv?.toFixed(2) ?? "N/A"}`,
      "",
      `Gerado: ${new Date().toLocaleDateString("pt-BR")}, ${new Date().toLocaleTimeString("pt-BR")}`,
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="reliability-card" style={{
      background: "linear-gradient(135deg, rgba(10,15,26,0.97), rgba(13,21,32,0.97))",
      border: "1px solid rgba(96,165,250,0.15)", borderRadius: 12, padding: "20px 22px",
      maxHeight: "78vh", overflowY: "auto",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc" }}>Confiabilidade do Sistema</span>
          <span style={{ fontSize: "0.62rem", color: "#64748b", display: "block", marginTop: 2 }}>Princeton AI Agent Reliability Framework</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={handleCopyReport} style={{
            fontSize: "0.65rem", fontWeight: 600, padding: "5px 12px", borderRadius: 6,
            border: copied ? "1px solid rgba(34,197,94,0.5)" : "1px solid rgba(96,165,250,0.3)",
            background: copied ? "rgba(34,197,94,0.15)" : "rgba(96,165,250,0.1)",
            color: copied ? "#4ade80" : "#60a5fa", cursor: "pointer", transition: "all 0.2s",
          }}>{copied ? "\u2705 Copiado!" : "\ud83d\udccb Copiar"}</button>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "1.2rem", padding: 4 }}>{"\u2715"}</button>
        </div>
      </div>

      {/* Banner explicativo quando sem dados */}
      {!hasAnyData && (
        <div style={{
          background: "rgba(96,165,250,0.08)", border: "1px solid rgba(96,165,250,0.2)",
          borderRadius: 10, padding: "12px 16px", marginBottom: 16,
          fontSize: "0.75rem", color: "#93c5fd", lineHeight: 1.6,
        }}>
          As métricas sao coletadas durante o uso do sistema.
          Robustez e Consistência resetam no cold start da Lambda.
          Previsibilidade vem do relatorio de auditoria de rodada.
        </div>
      )}

      {/* 4 dimensions */}
      <div className="reliability-dimensions" style={{ display: "grid", gap: 14 }}>
        {/* Predictability */}
        <DimCard icon={"\ud83d\udcc8"} title="Previsibilidade" color="#4ade80"
          score={pred.brier_score != null ? (1 - pred.brier_score).toFixed(2) : <EmptyVal />} sub="P_brier">
          <Row label="Brier Score" value={pred.brier_score?.toFixed(4) ?? null} sub="target < 0.22" />
          <Row label="Amostra (N)" value={pred.n_total ?? 0} sub="min: 20" />
          <ModelBeatsHouseRow />
          {!pred.suficiente && (
            <div style={{ fontSize: "0.72rem", color: "#f59e0b", padding: "6px 0" }}>
              {"\u26a0\ufe0f"} Amostra insuficiente — execute &quot;Auditar Rodada&quot; apos jogos finalizados
            </div>
          )}
        </DimCard>

        {/* Safety */}
        <DimCard icon={"\ud83d\udee1\ufe0f"} title="Segurança" color="#ef4444"
          score={displayRate(saf.compliance_rate ?? 1)} sub="compliance">
          <Row label="Complementares bloqueados" value={saf.complementares_bloqueados ?? 0} />
          <Row label="Contradições da IA corrigidas" value={saf.mistral_contradicoes ?? 0} />
          <Row label="Ações bloqueadas pela auditoria" value={saf.acoes_bloqueadas ?? 0} />
        </DimCard>

        {/* Robustness */}
        <DimCard icon={"\u26a1"} title="Robustez" color="#60a5fa"
          score={(() => {
            const af = rob.api_football_success_rate ?? 0;
            const fs = rob.footystats_success_rate ?? 0;
            const mi = rob.mistral_success_rate ?? 0;
            if (af === 0 && fs === 0 && mi === 0) return <EmptyVal />;
            return ((af + fs + mi) / 3 * 100).toFixed(0) + "%";
          })()}
          sub="media APIs">
          <ApiBar label="API-Football" rate={rob.api_football_success_rate ?? 0} />
          <ApiBar label="FootyStats" rate={rob.footystats_success_rate ?? 0} />
          <ApiBar label="Mistral AI" rate={rob.mistral_success_rate ?? 0} />
          <Row label="Fontes alternativas acionadas" value={rob.fallbacks_ativados ?? 0} />
        </DimCard>

        {/* Consistency */}
        <DimCard icon={"\ud83d\udd04"} title="Consistência" color="#a78bfa"
          score={con.lambda_duration_cv != null ? con.lambda_duration_cv.toFixed(2) : <EmptyVal />} sub="consistência do tempo de análise (CV)">
          <Row label="Tempo de análise (média)" value={con.lambda_duration_avg_ms != null ? `${(con.lambda_duration_avg_ms / 1000).toFixed(1)}s` : null} />
          <Row label="Tempo de análise (p95)" value={con.lambda_duration_p95_ms != null ? `${(con.lambda_duration_p95_ms / 1000).toFixed(1)}s` : null} />
          <Row label="Picks/jogo" value={con.picks_por_jogo_avg != null ? con.picks_por_jogo_avg.toFixed(1) : null} />
          {con.lambda_duration_avg_ms == null && (
            <div style={{ fontSize: "0.72rem", color: "#64748b", fontStyle: "italic", padding: "6px 0" }}>Dados acumulam durante o uso (reset no cold start)</div>
          )}
        </DimCard>
      </div>

      {/* Defesas Ativas */}
      <div style={{ marginTop: 14, background: "rgba(0,0,0,0.2)", borderRadius: 10, padding: "14px 16px", border: "1px solid rgba(255,255,255,0.04)" }}>
        <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#e2e8f0", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>{"\u2699\ufe0f"} Defesas Ativas</div>
        {[
          { label: "Anti-alucinacao Mistral", value: `${def.anti_alucinacao_mistral ?? 6} camadas` },
          { label: "Circuit breaker SAFE", value: def.circuit_breaker_safe ? "ATIVO" : "OFF" },
          { label: "Contrato Mistral narrativa", value: "ATIVO" },
          { label: "Validacao complementares", value: "ATIVO" },
          { label: "Filtro acoes auditoria", value: "ATIVO" },
        ].map((d, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", flexShrink: 0 }} />
            <span style={{ fontSize: "0.72rem", color: "#cbd5e1", flex: 1 }}>{d.label}</span>
            <span style={{ fontSize: "0.68rem", fontWeight: 600, color: "#4ade80", fontFamily: "monospace" }}>{d.value}</span>
          </div>
        ))}
      </div>

      {/* Glossário */}
      <details style={{ marginTop: 14 }} open={glossaryOpen} onToggle={(e) => setGlossaryOpen((e.target as HTMLDetailsElement).open)}>
        <summary style={{ fontSize: "0.75rem", color: "#94a3b8", cursor: "pointer", padding: "6px 0", fontWeight: 600 }}>
          {glossaryOpen ? "\u25bc" : "\u25b6"} Glossário de termos
        </summary>
        <div style={{ fontSize: "0.68rem", color: "#94a3b8", lineHeight: 1.7, marginTop: 6 }}>
          <p><strong style={{ color: "#cbd5e1" }}>Brier Score:</strong> Erro quadratico medio das probabilidades (0 = perfeito, 1 = pessimo). Target: &lt; 0.22.</p>
          <p><strong style={{ color: "#cbd5e1" }}>ECE:</strong> Expected Calibration Error — mede se &quot;70% previsto = 70% real&quot;.</p>
          <p><strong style={{ color: "#cbd5e1" }}>Conformidade:</strong> Taxa de cumprimento das regras operacionais (100% = nenhuma violação).</p>
          <p><strong style={{ color: "#cbd5e1" }}>CV (Coef. Variação):</strong> Desvio padrão / media. CV &lt; 0.3 indica consistencia aceitavel.</p>
          <p><strong style={{ color: "#cbd5e1" }}>Fallback:</strong> Ativacao de caminho alternativo quando fonte primaria falha.</p>
        </div>
      </details>
      <a
        href="/performance-stats"
        style={{ display: "block", textAlign: "center", marginTop: 14, fontSize: "0.72rem", fontWeight: 600, color: "#4ade80", textDecoration: "none" }}
      >
        Ver painel completo com gráficos → /performance-stats
      </a>
    </div>
  );
}
