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

/**
 * #189-g: estado visual proprio para picks INFORMATIVOS (gate #189-e).
 * Um pick de familia sem stake (cartoes; escanteios de linha media) nao pode
 * vestir o badge azul "VIAVEL" — o badge e o que o olho le; o motivo em
 * texto e complemento. Cinza, sem cor de acao.
 */
export const INFO_DISPLAY: ClassificationDisplay = {
  label: "INFO",
  color: "#9aa3ad",
  bgColor: "rgba(154,163,173,0.12)",
  description: "Pick informativo — família sem edge comprovado vs mercado; sem stake sugerido",
  tooltip:
    "O modelo analisa este mercado e mostra a leitura do jogo, mas a família não tem edge comprovado contra as odds (auditoria #189-e). Nenhum stake é sugerido.",
};

import { familyStakePolicy } from "@/components/BankrollCard";

/** Display do pick considerando o gate por família (#189-e/g). */
export function getPickDisplay(marketLabel: string, internal: string): ClassificationDisplay {
  if (familyStakePolicy(marketLabel || "") === "none") return INFO_DISPLAY;
  return getClassificationDisplay(internal);
}

/** #189-g: acentuação display-only dos rótulos de mercado (backend mantém ASCII como chave). */
export function fmtMercado(label: string): string {
  return (label || "")
    .replace(/\bCartoes\b/g, "Cartões")
    .replace(/\bCartao\b/g, "Cartão");
}
