import type { ClassificationKey } from "./types";

export const C = {
  bg: "#0a0a0a",
  card: "#111",
  border: "#1e1e1e",
  bHi: "#2a2a2a",
  t1: "#e8e8e8",
  t2: "#888",
  t3: "#555",
  green: "#00df82",
  gS: "rgba(0,223,130,0.10)",
  gB: "rgba(0,223,130,0.22)",
  gold: "#f5c542",
  dS: "rgba(245,197,66,0.08)",
  dB: "rgba(245,197,66,0.22)",
  blue: "#60a5fa",
  bS: "rgba(96,165,250,0.10)",
  bB: "rgba(96,165,250,0.22)",
  red: "#ef4444",
  rS: "rgba(239,68,68,0.08)",
  rB: "rgba(239,68,68,0.22)",
  orange: "#ff9d4d",
  purple: "#a78bfa",
} as const;

export interface ClassificationStyle {
  bg: string;
  b: string;
  c: string;
  l: string;
}

export const CLS: Record<ClassificationKey, ClassificationStyle> = {
  SAFE: { bg: C.gS, b: C.gB, c: C.green, l: "ALTA CONFIANÇA" },
  NEUTRO_QUALIFICADO: { bg: C.dS, b: C.dB, c: C.gold, l: "VALOR DETECTADO" },
  NEUTRO: { bg: C.bS, b: C.bB, c: C.blue, l: "VIÁVEL" },
  NO_BET: { bg: C.rS, b: C.rB, c: C.red, l: "SEM VALOR" },
};
