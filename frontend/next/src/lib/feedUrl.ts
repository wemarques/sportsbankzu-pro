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
 * #256 — data ISO (YYYY-MM-DD) em BRT fixo (UTC-3, sem horário de verão desde
 * 2019 — mesma convenção informal do resto do app, que já usa BRT fixo para
 * "today"/"tomorrow" em `backend/routes/fixtures.py`). Pura: recebe `agora`,
 * nunca lê o relógio — testável sem mock de tempo. `diasAtras=0` é hoje,
 * `1` é ontem.
 */
function diaISOEmBrt(agora: Date, diasAtras: number): string {
  const brt = new Date(agora.getTime() - 3 * 3600_000 - diasAtras * 24 * 3600_000);
  return brt.toISOString().slice(0, 10);
}

export function diaISOOntem(agora: Date): string {
  return diaISOEmBrt(agora, 1);
}

/** #261 — mesma regra de `diaISOOntem`, um dia a mais: o dia do operador em
 * BRT para o enriquecimento de "hoje" com `/ledger/dia`. */
export function diaISOHoje(agora: Date): string {
  return diaISOEmBrt(agora, 0);
}

/** #262 fix wave — chave de `diasLidos` (Feed.tsx) pela data ISO do dia do
 * operador em BRT, nao pelo rotulo da aba: evita colisao entre "hoje" de uma
 * carga e "hoje" do dia seguinte sem refresh de pagina. */
export function chaveDoDia(dia: Dia, agora: Date): string {
  if (dia === "ontem") return diaISOOntem(agora);
  if (dia === "hoje") return diaISOHoje(agora);
  return diaISOEmBrt(agora, -1);
}
