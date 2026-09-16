export type Dia = "ontem" | "hoje" | "amanha";
export interface FeedUrl { dia: Dia; liga: string; jogo: string | null }
const DIAS: Dia[] = ["ontem", "hoje", "amanha"];

export function lerFeedUrl(params: URLSearchParams): FeedUrl {
  const dia = params.get("dia");
  return {
    dia: DIAS.includes(dia as Dia) ? (dia as Dia) : "hoje",
    liga: params.get("liga") || "todas",
    jogo: params.get("jogo") || null,
  };
}
export function escreverFeedUrl(e: FeedUrl): string {
  const p = new URLSearchParams();
  if (e.dia !== "hoje") p.set("dia", e.dia);
  if (e.liga !== "todas") p.set("liga", e.liga);
  if (e.jogo) p.set("jogo", e.jogo);
  const q = p.toString();
  return q ? `/jogos?${q}` : "/jogos";
}
/** `ontem` vem de /ledger/dia (plano 3); ate la o feed mostra o vazio "sem fonte". */
export function diaParaApi(dia: Dia): "today" | "tomorrow" | null {
  return dia === "hoje" ? "today" : dia === "amanha" ? "tomorrow" : null;
}
