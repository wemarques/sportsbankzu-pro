import type { JogoView } from "@/lib/jogoView";
/** #262 — soma um lote ao feed: dedup por id (novo substitui), em jogo primeiro, depois kickoff. */
export function mesclarLote(atual: JogoView[], novas: JogoView[]): JogoView[] {
  const porId = new Map(atual.map((j) => [j.id, j]));
  for (const j of novas) porId.set(j.id, j);
  return Array.from(porId.values())
    .sort((a, b) => Number(b.estado === "em_jogo") - Number(a.estado === "em_jogo") || a.kickoffIso.localeCompare(b.kickoffIso));
}
/** #262 — cards-esqueleto na tela = min(3, lotes pendentes). */
export function quantosEsqueletos(pendentes: number): number {
  return Math.max(0, Math.min(3, pendentes));
}
