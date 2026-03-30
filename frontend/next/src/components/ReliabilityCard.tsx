"use client";

import React, { useState } from "react";

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
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "1.2rem", padding: 4 }}>{"\u2715"}</button>
      </div>

      {/* Banner explicativo quando sem dados */}
      {!hasAnyData && (
        <div style={{
          background: "rgba(96,165,250,0.08)", border: "1px solid rgba(96,165,250,0.2)",
          borderRadius: 10, padding: "12px 16px", marginBottom: 16,
          fontSize: "0.75rem", color: "#93c5fd", lineHeight: 1.6,
        }}>
          As metricas sao coletadas durante o uso do sistema.
          Robustez e Consistencia resetam no cold start da Lambda.
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
          {!pred.suficiente && (
            <div style={{ fontSize: "0.72rem", color: "#f59e0b", padding: "6px 0" }}>
              {"\u26a0\ufe0f"} Amostra insuficiente — execute &quot;Auditar Rodada&quot; apos jogos finalizados
            </div>
          )}
        </DimCard>

        {/* Safety */}
        <DimCard icon={"\ud83d\udee1\ufe0f"} title="Seguranca" color="#ef4444"
          score={displayRate(saf.compliance_rate ?? 1)} sub="compliance">
          <Row label="Complementares bloqueados" value={saf.complementares_bloqueados ?? 0} />
          <Row label="Contradicoes Mistral" value={saf.mistral_contradicoes ?? 0} />
          <Row label="Acoes auditoria filtradas" value={saf.acoes_bloqueadas ?? 0} />
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
          <Row label="Fallbacks ativados" value={rob.fallbacks_ativados ?? 0} />
        </DimCard>

        {/* Consistency */}
        <DimCard icon={"\ud83d\udd04"} title="Consistencia" color="#a78bfa"
          score={con.lambda_duration_cv != null ? con.lambda_duration_cv.toFixed(2) : <EmptyVal />} sub="CV duration">
          <Row label="Lambda avg" value={con.lambda_duration_avg_ms != null ? `${(con.lambda_duration_avg_ms / 1000).toFixed(1)}s` : null} />
          <Row label="Lambda p95" value={con.lambda_duration_p95_ms != null ? `${(con.lambda_duration_p95_ms / 1000).toFixed(1)}s` : null} />
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

      {/* Glossario */}
      <details style={{ marginTop: 14 }} open={glossaryOpen} onToggle={(e) => setGlossaryOpen((e.target as HTMLDetailsElement).open)}>
        <summary style={{ fontSize: "0.75rem", color: "#94a3b8", cursor: "pointer", padding: "6px 0", fontWeight: 600 }}>
          {glossaryOpen ? "\u25bc" : "\u25b6"} Glossario de termos
        </summary>
        <div style={{ fontSize: "0.68rem", color: "#94a3b8", lineHeight: 1.7, marginTop: 6 }}>
          <p><strong style={{ color: "#cbd5e1" }}>Brier Score:</strong> Erro quadratico medio das probabilidades (0 = perfeito, 1 = pessimo). Target: &lt; 0.22.</p>
          <p><strong style={{ color: "#cbd5e1" }}>ECE:</strong> Expected Calibration Error — mede se &quot;70% previsto = 70% real&quot;.</p>
          <p><strong style={{ color: "#cbd5e1" }}>Compliance:</strong> Taxa de conformidade com regras operacionais (100% = zero violacoes).</p>
          <p><strong style={{ color: "#cbd5e1" }}>CV (Coef. Variacao):</strong> Desvio padrao / media. CV &lt; 0.3 indica consistencia aceitavel.</p>
          <p><strong style={{ color: "#cbd5e1" }}>Fallback:</strong> Ativacao de caminho alternativo quando fonte primaria falha.</p>
        </div>
      </details>
    </div>
  );
}
