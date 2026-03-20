import type { LeagueClassificationType } from "@/hooks/useLeagueClassifications";

interface LeagueConfidenceBadgeProps {
  classification: LeagueClassificationType;
  accuracy?: number | null;
  brier?: number | null;
  nSamples?: number;
  lastUpdated?: string;
}

const CONFIG: Record<
  LeagueClassificationType,
  { level: number; label: string; cssClass: string }
> = {
  ML_ACTIVE: { level: 3, label: "AI", cssClass: "confidence-badge--ai" },
  POISSON: { level: 2, label: "ST", cssClass: "confidence-badge--st" },
  DEACTIVATED: { level: 1, label: "BS", cssClass: "confidence-badge--bs" },
};

function buildTooltip(props: LeagueConfidenceBadgeProps): string {
  const { classification, accuracy, brier, nSamples, lastUpdated } = props;
  const date = lastUpdated || "20/03/2026";

  if (classification === "ML_ACTIVE") {
    const acc = accuracy != null ? `${(accuracy * 100).toFixed(1)}%` : "—";
    const br = brier != null ? brier.toFixed(3) : "—";
    const samples = nSamples ?? "—";
    return `Modelo AI treinado com ${samples} jogos\nPrecisão: ${acc} | Calibração (Brier): ${br}\nAtualizado em: ${date}`;
  }
  if (classification === "POISSON") {
    const acc = accuracy != null ? `${(accuracy * 100).toFixed(1)}%` : "—";
    const br = brier != null ? brier.toFixed(3) : "—";
    return `Modelo estatístico (Poisson)\nPrecisão: ${acc} | Calibração (Brier): ${br}\nAtualizado em: ${date}`;
  }
  return `Dados limitados — análise básica\nML desativado: calibração insuficiente\nAtualizado em: ${date}`;
}

export default function LeagueConfidenceBadge(
  props: LeagueConfidenceBadgeProps
) {
  const { classification } = props;
  const cfg = CONFIG[classification];
  const tooltip = buildTooltip(props);

  return (
    <div
      className={`league-confidence-badge ${cfg.cssClass}`}
      aria-label={tooltip}
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
        <span style={{ color: "#00ff88" }}>AI</span> = modelo treinado
      </span>
      <span className="legend-item">
        <span className="legend-bars legend-bars--st">
          <span className="bar active" />
          <span className="bar active" />
          <span className="bar" />
        </span>
        <span style={{ color: "#ffa726" }}>ST</span> = estatístico
      </span>
      <span className="legend-item">
        <span className="legend-bars legend-bars--bs">
          <span className="bar active" />
          <span className="bar" />
          <span className="bar" />
        </span>
        <span style={{ color: "#666" }}>BS</span> = básico
      </span>
    </div>
  );
}
