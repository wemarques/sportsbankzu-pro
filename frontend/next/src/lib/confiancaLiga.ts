import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
/** #254-b — os quatro estados do #250 viram uma frase de operador (spec §4.1). */
const PISO_SEM_DADO = 0.58; // #256: usado so enquanto /ledger/agregado nao respondeu
const FAIXA = 0.04;

export function fraseConfianca(c: LeagueConfidence | null, ligaNome: string, mediaDasLigas: number | null = null) {
  const media = mediaDasLigas ?? PISO_SEM_DADO;
  if (!c || c.level === "UNVERIFIED") return { texto: `${ligaNome}: confiança não verificada`, numero: null, semBase: true };
  if (c.level === "POISSON") return { texto: `${ligaNome}: modelo geral, sem histórico próprio`, numero: null, semBase: true };
  const n = c.nSamples ?? 0;
  if (c.level === "ML_SUPPRESSED" || c.accuracy == null || n < 20) {
    return { texto: `${ligaNome}: ${n} jogos medidos, ainda sem base`, numero: n, semBase: true };
  }
  const rel = c.accuracy - media;
  const onde = rel > FAIXA ? "acima da média" : rel < -FAIXA ? "abaixo da média" : "na média das ligas";
  return { texto: `${ligaNome}: ${n} jogos medidos, acerto ${onde}`, numero: n, semBase: false };
}
