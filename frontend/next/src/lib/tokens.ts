/**
 * #254 — tokens da reformulacao (spec §2). Fonte unica: o CSS em globals.css
 * copia estes hex; o teste de contraste le daqui. Um significado por cor.
 */
export const TOKENS = {
  tinta: "#15161A",
  painel: "#22242B",
  linha: "#2C2E36",
  hover: "#262830",
  texto: "#E6E4DD",
  "texto-apagado": "#93959C",
  talao: "#E3D9AE",
  "tinta-do-talao": "#1B1710",
  "tinta-apoiada": "#4A4436",
  confianca: "#4FB3BF",
  "contra-texto": "#E8665A",
  contra: "#E0533F",
} as const;

export type NomeToken = keyof typeof TOKENS;

/**
 * Pares (texto, fundo, minimo WCAG) que a UI de fato produz — hover incluido.
 * Todo componente novo que combine texto e superficie de outro jeito adiciona
 * o par aqui; o teste e a fonte de verdade, a tabela da spec documenta.
 */
export const PARES_PERMITIDOS: ReadonlyArray<readonly [NomeToken, NomeToken, number]> = [
  ["texto", "tinta", 4.5],
  ["texto", "painel", 4.5],
  ["texto", "hover", 4.5],
  ["texto-apagado", "tinta", 4.5],
  ["texto-apagado", "painel", 4.5],
  ["texto-apagado", "hover", 4.5],
  ["confianca", "tinta", 4.5],
  ["confianca", "painel", 4.5],
  ["confianca", "hover", 4.5],
  ["contra-texto", "tinta", 4.5],
  ["contra-texto", "painel", 4.5],
  ["contra-texto", "hover", 4.5],
  ["tinta-do-talao", "talao", 4.5],
  ["tinta-apoiada", "talao", 4.5],
];

function luminancia(hex: string): number {
  const canal = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

/** Razao de contraste WCAG 2.1 (>= 1). */
export function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}
