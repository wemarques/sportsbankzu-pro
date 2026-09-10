import type {
  LeagueConfidence,
  LeagueConfidenceLevel,
} from "@/hooks/useLeagueClassifications";

interface LeagueConfidenceBadgeProps {
  confidence: LeagueConfidence;
}

/**
 * #250 — o selo descreve o que a producao SERVE, verificado no backend.
 *
 * `UNVERIFIED` nao e "nivel baixo": e ausencia de verificacao. Por isso nao
 * acende barra nenhuma e nao herda o estilo de AI/ST/BS.
 */
const CONFIG: Record<
  LeagueConfidenceLevel,
  { level: number; label: string; cssClass: string }
> = {
  ML_ACTIVE: { level: 3, label: "AI", cssClass: "confidence-badge--ai" },
  POISSON: { level: 2, label: "ST", cssClass: "confidence-badge--st" },
  ML_SUPPRESSED: { level: 1, label: "BS", cssClass: "confidence-badge--bs" },
  UNVERIFIED: { level: 0, label: "?", cssClass: "confidence-badge--unknown" },
};

/** Formata ISO -> dd/mm/aaaa. Sem data verificada nao inventa uma. */
export function formatTrainedAt(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getUTCFullYear()}`;
}

/**
 * #250 — o tooltip so pode afirmar o que foi verificado.
 *
 * Regra dura: a frase "Modelo AI treinado com N jogos" existe UNICAMENTE no
 * ramo ML_ACTIVE, isto e, quando `/ml/status/all` respondeu `available: true`
 * para a liga (o que ja implica os 3 gates de `is_ml_available`). Nos demais
 * ramos o texto diz o que a liga usa de fato, sem prometer nivel de confianca.
 */
export function buildTooltip(c: LeagueConfidence): string {
  const date = formatTrainedAt(c.trainedAt);
  const acc = c.accuracy != null ? `${(c.accuracy * 100).toFixed(1)}%` : null;
  const br = c.brier != null ? c.brier.toFixed(3) : null;

  if (c.level === "ML_ACTIVE") {
    const linhas = [
      c.nSamples != null
        ? `Modelo AI treinado com ${c.nSamples} jogos`
        : "Modelo AI ativo (amostra de treino não reportada)",
    ];
    const metricas = [
      acc ? `Precisão: ${acc}` : null,
      br ? `Calibração (Brier): ${br}` : null,
    ].filter(Boolean);
    if (metricas.length) linhas.push(metricas.join(" | "));
    linhas.push(date ? `Treinado em: ${date}` : "Data de treino não reportada");
    linhas.push("Verificado agora no backend.");
    return linhas.join("\n");
  }

  if (c.level === "ML_SUPPRESSED") {
    return [
      "Modelo treinado, porém desativado",
      "Reprovou um dos gates de calibração (Brier / OddsVal / ECE)",
      "Em uso: 1X2 por espelho de mercado de-vigado; gols e BTTS por Poisson",
      date ? `Treinado em: ${date}` : "Data de treino não reportada",
    ].join("\n");
  }

  if (c.level === "POISSON") {
    return [
      "Sem modelo treinado em produção",
      "1X2: espelho de mercado de-vigado (odds implícitas)",
      "Gols e BTTS: modelo estatístico Poisson",
      "Verificado agora no backend.",
    ].join("\n");
  }

  // UNVERIFIED
  return [
    "Não foi possível verificar o modelo em produção",
    "O backend não respondeu — nenhum nível de confiança é afirmado",
    "Tente novamente em instantes",
  ].join("\n");
}

export default function LeagueConfidenceBadge({
  confidence,
}: LeagueConfidenceBadgeProps) {
  const cfg = CONFIG[confidence.level];
  const tooltip = buildTooltip(confidence);

  return (
    <div
      className={`league-confidence-badge ${cfg.cssClass}`}
      aria-label={tooltip}
      data-confidence-level={confidence.level}
    >
      <div className="confidence-bars">
        <div className={`bar ${cfg.level >= 1 ? "active" : ""}`} />
        <div className={`bar ${cfg.level >= 2 ? "active" : ""}`} />
        <div className={`bar ${cfg.level >= 3 ? "active" : ""}`} />
      </div>
      <span className="confidence-label">{cfg.label}</span>
      <div className="confidence-tooltip">
        {tooltip.split("\n").map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </div>
    </div>
  );
}

export function ConfidenceLegend() {
  return (
    <div className="confidence-legend">
      <span className="legend-item">
        <span className="legend-bars legend-bars--ai">
          <span className="bar active" />
          <span className="bar active" />
          <span className="bar active" />
        </span>
        <span style={{ color: "#00ff88" }}>AI</span> = modelo treinado ativo
      </span>
      <span className="legend-item">
        <span className="legend-bars legend-bars--st">
          <span className="bar active" />
          <span className="bar active" />
          <span className="bar" />
        </span>
        <span style={{ color: "#ffa726" }}>ST</span> = Poisson + espelho de mercado
      </span>
      <span className="legend-item">
        <span className="legend-bars legend-bars--bs">
          <span className="bar active" />
          <span className="bar" />
          <span className="bar" />
        </span>
        <span style={{ color: "#666" }}>BS</span> = modelo desativado por calibração
      </span>
      <span className="legend-item">
        <span className="legend-bars legend-bars--unknown">
          <span className="bar" />
          <span className="bar" />
          <span className="bar" />
        </span>
        <span style={{ color: "#666" }}>?</span> = não verificado
      </span>
    </div>
  );
}
