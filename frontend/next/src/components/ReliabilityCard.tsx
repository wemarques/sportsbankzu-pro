"use client";

import React, { useState } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */

function pct(v: number | null | undefined): string {
  return v != null ? (v * 100).toFixed(1) + "%" : "\u2014";
}

function DimCard({ icon, title, color, score, sub, children }: {
  icon: string; title: string; color: string; score?: string; sub?: string; children: React.ReactNode;
}) {
  return (
    <div className="reliability-dimension-card" style={{
      background: `linear-gradient(135deg, ${color}08 0%, ${color}03 100%)`,
      border: `1px solid ${color}30`, borderRadius: 12, padding: "14px 16px",
      position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 3, height: "100%", background: color }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span>{icon}</span>
          <span className="reliability-dimension-title" style={{ fontSize: "0.62rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1.2 }}>{title}</span>
        </div>
        {score != null && (
          <div style={{ textAlign: "right" }}>
            <div className="reliability-metric-value" style={{ fontSize: "0.95rem", fontWeight: 800, color, fontFamily: "monospace" }}>{score}</div>
            {sub && <div style={{ fontSize: "0.45rem", color: "#64748b" }}>{sub}</div>}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, sub }: { label: string; value: string | number | null; sub?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <div>
        <span style={{ fontSize: "0.65rem", color: "#cbd5e1" }}>{label}</span>
        {sub && <span style={{ fontSize: "0.5rem", color: "#475569", marginLeft: 6 }}>{sub}</span>}
      </div>
      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>{value ?? "\u2014"}</span>
    </div>
  );
}

function ApiBar({ label, rate }: { label: string; rate: number }) {
  const color = rate >= 0.95 ? "#4ade80" : rate >= 0.85 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: "0.58rem", color: "#94a3b8" }}>{label}</span>
        <span style={{ fontSize: "0.6rem", fontWeight: 700, color, fontFamily: "monospace" }}>{(rate * 100).toFixed(1)}%</span>
      </div>
      <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(rate * 100, 100)}%`, background: color, borderRadius: 2, transition: "width 0.6s" }} />
      </div>
    </div>
  );
}

export default function ReliabilityCard({ data, onClose }: { data: any; onClose: () => void }) {
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const pred = data?.predictability ?? {};
  const saf = data?.safety ?? {};
  const rob = data?.robustness ?? {};
  const con = data?.consistency ?? {};
  const def = data?.defesas_ativas ?? {};

  return (
    <div className="reliability-card" style={{
      background: "linear-gradient(135deg, rgba(10,15,26,0.97), rgba(13,21,32,0.97))",
      border: "1px solid rgba(96,165,250,0.15)", borderRadius: 12, padding: 16,
      maxHeight: "75vh", overflowY: "auto",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#f8fafc" }}>Confiabilidade do Sistema</span>
          <span style={{ fontSize: "0.5rem", color: "#475569", display: "block", marginTop: 1 }}>Princeton AI Agent Reliability Framework</span>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: "1rem" }}>{"\u2715"}</button>
      </div>

      {/* 4 dimensions */}
      <div className="reliability-dimensions" style={{ display: "grid", gap: 10 }}>
        {/* Predictability */}
        <DimCard icon={"\ud83d\udcc8"} title="Previsibilidade" color="#4ade80"
          score={pred.brier_score != null ? (1 - pred.brier_score).toFixed(2) : "\u2014"} sub="P_brier">
          <Row label="Brier Score" value={pred.brier_score?.toFixed(4) ?? null} sub="target < 0.22" />
          <Row label="Amostra (N)" value={pred.n_total ?? 0} sub="min: 20" />
          {!pred.suficiente && <div style={{ fontSize: "0.55rem", color: "#f59e0b", padding: "4px 0" }}>{"\u26a0\ufe0f"} N insuficiente</div>}
        </DimCard>

        {/* Safety */}
        <DimCard icon={"\ud83d\udee1\ufe0f"} title="Seguranca" color="#ef4444"
          score={pct(saf.compliance_rate ?? 1)} sub="compliance">
          <Row label="Complementares bloqueados" value={saf.complementares_bloqueados ?? 0} />
          <Row label="Contradicoes Mistral" value={saf.mistral_contradicoes ?? 0} />
          <Row label="Acoes auditoria filtradas" value={saf.acoes_bloqueadas ?? 0} />
        </DimCard>

        {/* Robustness */}
        <DimCard icon={"\u26a1"} title="Robustez" color="#60a5fa"
          score={(() => { const a = ((rob.api_football_success_rate ?? 0) + (rob.footystats_success_rate ?? 0) + (rob.mistral_success_rate ?? 0)) / 3; return (a * 100).toFixed(0) + "%"; })()}
          sub="media APIs">
          <ApiBar label="API-Football" rate={rob.api_football_success_rate ?? 0} />
          <ApiBar label="FootyStats" rate={rob.footystats_success_rate ?? 0} />
          <ApiBar label="Mistral AI" rate={rob.mistral_success_rate ?? 0} />
          <Row label="Fallbacks ativados" value={rob.fallbacks_ativados ?? 0} />
        </DimCard>

        {/* Consistency */}
        <DimCard icon={"\ud83d\udd04"} title="Consistencia" color="#a78bfa"
          score={con.lambda_duration_cv?.toFixed(2) ?? "\u2014"} sub="CV duration">
          <Row label="Lambda avg" value={con.lambda_duration_avg_ms != null ? `${(con.lambda_duration_avg_ms / 1000).toFixed(1)}s` : null} />
          <Row label="Lambda p95" value={con.lambda_duration_p95_ms != null ? `${(con.lambda_duration_p95_ms / 1000).toFixed(1)}s` : null} />
          <Row label="Picks/jogo" value={con.picks_por_jogo_avg?.toFixed(1) ?? null} />
        </DimCard>
      </div>

      {/* Defesas Ativas */}
      <div style={{ marginTop: 10, background: "rgba(0,0,0,0.2)", borderRadius: 8, padding: "10px 12px", border: "1px solid rgba(255,255,255,0.04)" }}>
        <div style={{ fontSize: "0.55rem", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{"\u2699\ufe0f"} Defesas Ativas</div>
        {[
          { label: "Anti-alucinacao Mistral", value: `${def.anti_alucinacao_mistral ?? 6} camadas` },
          { label: "Circuit breaker SAFE", value: def.circuit_breaker_safe ? "ATIVO" : "OFF" },
          { label: "Contrato Mistral narrativa", value: "ATIVO" },
          { label: "Validacao complementares", value: "ATIVO" },
          { label: "Filtro acoes auditoria", value: "ATIVO" },
        ].map((d, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 0", borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#4ade80", flexShrink: 0 }} />
            <span style={{ fontSize: "0.58rem", color: "#cbd5e1", flex: 1 }}>{d.label}</span>
            <span style={{ fontSize: "0.55rem", fontWeight: 600, color: "#4ade80", fontFamily: "monospace" }}>{d.value}</span>
          </div>
        ))}
      </div>

      {/* Glossario colapsavel */}
      <details style={{ marginTop: 10 }} open={glossaryOpen} onToggle={(e) => setGlossaryOpen((e.target as HTMLDetailsElement).open)}>
        <summary style={{ fontSize: "0.58rem", color: "#64748b", cursor: "pointer", padding: "4px 0" }}>
          {glossaryOpen ? "\u25bc" : "\u25b6"} Glossario de termos
        </summary>
        <div style={{ fontSize: "0.52rem", color: "#475569", lineHeight: 1.6, marginTop: 4 }}>
          <p><strong>Brier Score:</strong> Erro quadratico medio das probabilidades (0 = perfeito, 1 = pessimo). Target: &lt; 0.22.</p>
          <p><strong>ECE:</strong> Expected Calibration Error — mede se &quot;70% previsto = 70% real&quot;.</p>
          <p><strong>Compliance:</strong> Taxa de conformidade com regras operacionais (100% = zero violacoes).</p>
          <p><strong>CV (Coef. Variacao):</strong> Desvio padrao / media. CV &lt; 0.3 indica consistencia aceitavel.</p>
          <p><strong>Fallback:</strong> Ativacao de caminho alternativo quando fonte primaria falha.</p>
        </div>
      </details>
    </div>
  );
}
