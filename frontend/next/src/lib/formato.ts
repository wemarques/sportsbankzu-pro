/** #254 — formatacao pt-BR, um ponto so (spec §4.4). Virgula decimal sempre. */
const FUSO = "America/Sao_Paulo";
const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });
const duasCasas = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function fmtReais(v: number): string {
  // Intl usa espaco nao separavel entre "R$" e o numero; normaliza para espaco comum.
  return reais.format(v).replace(/ /g, " ");
}
export function fmtOdd(v: number): string {
  return duasCasas.format(v);
}
export function fmtDelta(v: number): string {
  const abs = duasCasas.format(Math.abs(v));
  if (Math.abs(v) < 0.005) return abs;
  return (v > 0 ? "+" : "−") + abs;
}
export function fmtPct(p01: number): number {
  return Math.round(p01 * 100);
}
export function fmtHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: FUSO }).format(new Date(iso));
}
export function fmtDataCurta(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: FUSO }).format(new Date(iso));
}
export function fmtLigaHora(liga: string, iso: string): string {
  return `${liga}, ${fmtHora(iso)}`;
}
