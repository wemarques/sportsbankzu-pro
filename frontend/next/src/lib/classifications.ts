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
    label: "INFORMATIVO",
    color: "#9ca3af",
    bgColor: "rgba(156,163,175,0.15)",
    description: "Mercado identificado mas sem valor suficiente ou sem odds disponiveis",
    tooltip:
      "Mercado mapeado pelo modelo, porem sem valor matematico suficiente para recomendacao. Pode ser usado como referencia informativa.",
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
