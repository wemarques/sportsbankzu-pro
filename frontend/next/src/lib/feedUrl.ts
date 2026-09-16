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
/** "ontem" nao usa este mapeamento — Feed.tsx chama getLedgerDia direto (#256). */
export function diaParaApi(dia: Dia): "today" | "tomorrow" | null {
  return dia === "hoje" ? "today" : dia === "amanha" ? "tomorrow" : null;
}

/**
 * #256 — data ISO (YYYY-MM-DD) do dia anterior, em BRT fixo (UTC-3, sem
 * horário de verão desde 2019 — mesma convenção informal do resto do app,
 * que já usa BRT fixo para "today"/"tomorrow" em `backend/routes/fixtures.py`).
 * Pura: recebe `agora`, nunca lê o relógio — testável sem mock de tempo.
 */
export function diaISOOntem(agora: Date): string {
  const brtOntem = new Date(agora.getTime() - 3 * 3600_000 - 24 * 3600_000);
  return brtOntem.toISOString().slice(0, 10);
}
