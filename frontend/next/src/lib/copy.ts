/** #254 — toda frase da UI nasce aqui (spec §4.4). Numero antes de nome. */
import { fmtDelta, fmtOdd, fmtPct, fmtReais } from "@/lib/formato";

export type Trecho = { texto: string } | { termo: string; texto: string };

/** `{term:edge|edge}` → trecho com termo; o componente vira link /glossario#edge. */
export function comTermos(template: string): Trecho[] {
  const out: Trecho[] = [];
  const re = /\{term:([a-z0-9-]+)\|([^}]+)\}/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(template)) !== null) {
    if (m.index > ultimo) out.push({ texto: template.slice(ultimo, m.index) });
    out.push({ termo: m[1], texto: m[2] });
    ultimo = m.index + m[0].length;
  }
  if (ultimo < template.length) out.push({ texto: template.slice(ultimo) });
  return out;
}

export function frequencia(p01: number): string {
  return `acontece em ${fmtPct(p01)} de cada 100 jogos assim`;
}

export function linhaPreco(bookOdd: number | null, fairOdd: number, futuro: boolean) {
  if (bookOdd == null || bookOdd <= 1) {
    return {
      texto: futuro
        ? `vale a partir de ${fmtOdd(fairOdd)}, mercado ainda sem preço`
        : `vale a partir de ${fmtOdd(fairOdd)}, sem preço que valha hoje`,
      abaixo: false,
      semPreco: true,
    };
  }
  const delta = bookOdd - fairOdd;
  const abaixo = delta < 0;
  return {
    texto: `mercado paga ${fmtOdd(bookOdd)}, ${abaixo ? "abaixo" : "acima"} do mínimo ${fmtOdd(fairOdd)} (${fmtDelta(delta)})`,
    abaixo,
    semPreco: false,
  };
}

export function stake(banca: number | null, valor: number | null): string {
  if (banca == null || valor == null) return "stake: defina sua banca";
  return `Da sua banca de ${fmtReais(banca)}: ${fmtReais(valor)}`;
}

export function avaliados(total: number, valem: number): string {
  if (valem === 0) return `${total} mercados avaliados, nenhum vale hoje`;
  return `${total} mercados avaliados, ${valem} ${valem === 1 ? "vale" : "valem"}`;
}

export function direcao(mercado: string, p01: number): string {
  const m = mercado.charAt(0).toLowerCase() + mercado.slice(1);
  return `Direção: ${m}, ${fmtPct(p01)} em cada 100 — sem preço que valha hoje`;
}

export function resultadoOntem(acertou: boolean, detalhe: string): string {
  return `${acertou ? "✓" : "×"} fechou com ${detalhe}`;
}

export const COPIAR = {
  rotulo: (odd: number) => `copiar odd ${fmtOdd(odd)}`,
  ok: (odd: number) => `${fmtOdd(odd)} copiado`,
  falhou: "não deu pra copiar — selecione o número",
};

const umaCasa = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export interface Origem { golsCasa: number | null; golsFora: number | null; golsLiga: number | null; escanteiosCasa: number | null; escanteiosFora: number | null; escanteiosLiga: number | null }
export function fraseOrigem(o: Origem, casa: string, fora: string, liga: string): string | null {
  if (o.golsCasa != null && o.golsFora != null && o.golsLiga != null)
    return `${casa} faz ${umaCasa.format(o.golsCasa)} gols por jogo em casa; ${fora} sofre ${umaCasa.format(o.golsFora)} fora; a ${liga} tem ${umaCasa.format(o.golsLiga)} por jogo.`;
  if (o.escanteiosCasa != null && o.escanteiosFora != null && o.escanteiosLiga != null)
    return `${casa} força ${umaCasa.format(o.escanteiosCasa)} escanteios por jogo em casa; ${fora} ${umaCasa.format(o.escanteiosFora)} fora; a ${liga} tem ${umaCasa.format(o.escanteiosLiga)} por jogo.`;
  return null;
}

export const VAZIOS = {
  diaSemJogos: (data: string) => `Nenhum jogo nas ligas escolhidas em ${data}.`,
  proximoDia: (dia: string) => `próximo dia com picks: ${dia}`,
  feedNaoCarregou: "Os jogos de hoje não carregaram.",
  tentarDeNovo: "Tentar de novo",
  carimbo: (hora: string) => `de ${hora}`,
  ligaSemDados: (liga: string) => `${liga}: sem dados da rodada`,
  jogoNaoEncontrado: "jogo não encontrado",
  verFeedDeHoje: "ver os jogos de hoje",
  resultadoPendente: "resultado ainda não conferido",
  recomendacaoPreJogo: "recomendação pré-jogo",
};
