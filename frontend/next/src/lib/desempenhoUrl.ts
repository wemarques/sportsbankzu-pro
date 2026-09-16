export type Periodo = "7d" | "30d" | "temporada";
export interface DesempenhoUrl { periodo: Periodo; familia: string | null; liga: string | null }
const PERIODOS: Periodo[] = ["7d", "30d", "temporada"];

export function lerDesempenhoUrl(params: URLSearchParams): DesempenhoUrl {
  const periodo = params.get("periodo");
  return {
    periodo: PERIODOS.includes(periodo as Periodo) ? (periodo as Periodo) : "30d",
    familia: params.get("familia") || null,
    liga: params.get("liga") || null,
  };
}

export function escreverDesempenhoUrl(e: DesempenhoUrl): string {
  const p = new URLSearchParams();
  if (e.periodo !== "30d") p.set("periodo", e.periodo);
  if (e.familia) p.set("familia", e.familia);
  if (e.liga) p.set("liga", e.liga);
  const q = p.toString();
  return q ? `/desempenho?${q}` : "/desempenho";
}

const _2DIG = (n: number) => String(n).padStart(2, "0");

/** Texto por extenso do periodo ativo (spec §5): "03/09–hoje" em vez de
 * confiar no rotulo do segmento. `hoje` e injetado — nunca le o relogio. */
export function periodoPorExtenso(periodo: Periodo, hoje: Date): string {
  if (periodo === "temporada") return "03/09–hoje";
  const dias = periodo === "7d" ? 7 : 30;
  const inicio = new Date(hoje.getTime() - dias * 86_400_000);
  return `${_2DIG(inicio.getUTCDate())}/${_2DIG(inicio.getUTCMonth() + 1)}–hoje`;
}
