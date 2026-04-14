/**
 * Classification display mapping — frontend-only rename (#080).
 * Backend enum values (SAFE, NEUTRO_QUALIFICADO, NEUTRO, NO_BET) stay unchanged.
 */

export interface ClassificationDisplay {
  label: string;
  color: string;
  bgColor: string;
  description: string;
  tooltip: string;
}

export const CLASSIFICATION_DISPLAY: Record<string, ClassificationDisplay> = {
  SAFE: {
    label: "ALTA CONFIANCA",
    color: "#00ff88",
    bgColor: "rgba(0,255,136,0.15)",
    description: "Probabilidade alta, EV positivo, dados confiaveis, edge suficiente",
    tooltip:
      "Classificacao maxima do modelo. Todos os criterios atingidos: probabilidade acima do threshold, valor esperado positivo, qualidade de dados alta e margem de vantagem significativa.",
  },
  NEUTRO_QUALIFICADO: {
    label: "VALOR DETECTADO",
    color: "#ffd700",
    bgColor: "rgba(255,215,0,0.15)",
    description: "EV positivo mas nao atinge todos os criterios SAFE — elegivel para combinadas",
    tooltip:
      "O modelo detectou valor matematico (EV+), mas nem todos os criterios de alta confianca foram atingidos. Elegivel para duplas e combinadas.",
  },
  NEUTRO: {
    label: "VIÁVEL",
    color: "#60a5fa",
    bgColor: "rgba(96,165,250,0.12)",
    description: "Mercado com chance real de acerto neste jogo, mas sem valor matematico de longo prazo",
    tooltip:
      "O modelo identifica probabilidade razoavel para este jogo especifico. Nao atinge criterios de EV+ para recomendacao de aposta sistematica, mas e viavel como pick pontual.",
  },
  NO_BET: {
    label: "BLOQUEADO",
    color: "#ef4444",
    bgColor: "rgba(239,68,68,0.15)",
    description: "Bloqueado por risco alto, dados insuficientes ou regime restritivo",
    tooltip:
      "Mercado bloqueado pelo sistema. Razoes possiveis: risco muito alto, dados insuficientes, EV negativo ou regime restritivo da liga.",
  },
};

/**
 * Get display config for a classification. Falls back to NEUTRO for unknown values.
 */
export function getClassificationDisplay(internal: string): ClassificationDisplay {
  return CLASSIFICATION_DISPLAY[internal] ?? CLASSIFICATION_DISPLAY.NEUTRO;
}
