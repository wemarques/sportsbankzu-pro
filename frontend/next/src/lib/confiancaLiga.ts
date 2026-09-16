import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
/** #254-b — os quatro estados do #250 viram uma frase de operador (spec §4.1). */
const MEDIA_DAS_LIGAS = 0.58; // acerto medio medido no ledger em 2026-09-15 (spec §5); atualizar com /ledger/agregado no plano 3
const FAIXA = 0.04;

export function fraseConfianca(c: LeagueConfidence | null, ligaNome: string) {
  if (!c || c.level === "UNVERIFIED") return { texto: `${ligaNome}: confiança não verificada`, numero: null, semBase: true };
  if (c.level === "POISSON") return { texto: `${ligaNome}: modelo geral, sem histórico próprio`, numero: null, semBase: true };
  const n = c.nSamples ?? 0;
  if (c.level === "ML_SUPPRESSED" || c.accuracy == null || n < 20) {
    return { texto: `${ligaNome}: ${n} jogos medidos, ainda sem base`, numero: n, semBase: true };
  }
  const rel = c.accuracy - MEDIA_DAS_LIGAS;
  const onde = rel > FAIXA ? "acima da média" : rel < -FAIXA ? "abaixo da média" : "na média das ligas";
  return { texto: `${ligaNome}: ${n} jogos medidos, acerto ${onde}`, numero: n, semBase: false };
}
