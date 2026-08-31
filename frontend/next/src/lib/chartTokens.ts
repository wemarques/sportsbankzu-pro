/**
 * #189-i — sistema único de cor para visualização de dados.
 *
 * Paleta categórica VALIDADA (validador CVD da análise de 31/08/2026):
 * banda de luminância, croma, separação deutan/protan/tritan (ΔE ≥ 8),
 * piso de visão normal (ΔE ≥ 15) e contraste ≥ 3:1 sobre superfície escura.
 *
 * REGRAS (não negociáveis):
 * 1. Slots em ORDEM FIXA por entidade — filtrar séries nunca repinta as que
 *    sobram; a 5ª série não existe (agrupar em "Outros" ou facetar).
 * 2. STATUS é reservado para estado (EV+, acerto/erro, SAFE/NO_BET,
 *    aguarde-odd) e NUNCA vira cor de série de gráfico.
 * 3. Texto e valores sempre em tokens de texto (C.t1/t2/t3) — a cor da série
 *    fica na marca (barra/ponto), não no número.
 * 4. Um eixo por gráfico. Rótulos diretos nas marcas + <title> nativo como
 *    tooltip; legenda sempre presente com ≥ 2 séries.
 */

/** Séries categóricas — superfície escura (#0a0a0a/#111). Ordem fixa. */
export const SERIES = {
  /** slot 1 — série principal (ex.: modelo) */
  s1: "#3987e5",
  /** slot 2 — comparação (ex.: casa/mercado) */
  s2: "#d95926",
  /** slot 3 */
  s3: "#199e70",
  /** slot 4 */
  s4: "#c98500",
} as const;

/** Cores de estado — reservadas; alinhadas às classificações do produto. */
export const STATUS = {
  /** confiança alta / EV+ / acerto — verde da marca */
  good: "#00df82",
  /** faixa intermediária / valor detectado / aguarde-odd */
  warn: "#f5c542",
  /** faixa baixa */
  low: "#ff9d4d",
  /** NO_BET / erro */
  bad: "#ef4444",
  /** pick informativo (gate #189-e) — AA sobre fundo escuro (#189-h) */
  muted: "#9ca3af",
} as const;

/** Anatomia de gráfico — grid recessivo, eixo e referências discretos. */
export const CHART = {
  grid: "rgba(255,255,255,0.08)",
  axis: "#8b95a0",
  ref: "#8b95a0",
  connector: "rgba(139,149,160,0.55)",
  surface: "#111",
} as const;

/**
 * Cor da faixa de probabilidade — fonte única para ProbBar, badges e
 * qualquer medidor de confiança. Cortes: ≥70 good · ≥50 warn · <50 low.
 */
export function probColor(prob: number, muted = false): string {
  if (muted) return STATUS.muted;
  const pct = prob * 100;
  return pct >= 70 ? STATUS.good : pct >= 50 ? STATUS.warn : STATUS.low;
}

export type MarketFamily = "gols" | "1x2" | "cartoes" | "escanteios" | "outros";

/** Família do mercado a partir do label (mesma heurística do gate #189-e). */
export function marketFamily(label: string): MarketFamily {
  const ml = (label || "").toLowerCase();
  if (ml.includes("escante") || ml.includes("corner")) return "escanteios";
  if (ml.includes("cart") || ml.includes("card") || ml.includes("booking")) return "cartoes";
  if (ml.includes("btts") || ml.includes("gol") || ml.includes("goal") || /\bover\b|\bunder\b/.test(ml)) return "gols";
  if (ml.includes("1x2") || ml.includes("dupla") || ml.includes("double") || ml.includes("chance") || /\b(home|away|casa|fora)\b/.test(ml)) return "1x2";
  return "outros";
}

export const FAMILY_LABEL: Record<MarketFamily, string> = {
  gols: "Gols / BTTS",
  "1x2": "1X2 / Dupla Chance",
  cartoes: "Cartões",
  escanteios: "Escanteios",
  outros: "Outros",
};
