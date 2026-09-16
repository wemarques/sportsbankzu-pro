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
  const avaliadosTxt = total === 1 ? "1 mercado avaliado" : `${total} mercados avaliados`;
  if (valem === 0) return `${avaliadosTxt}, nenhum vale hoje`;
  return `${avaliadosTxt}, ${valem} ${valem === 1 ? "vale" : "valem"}`;
}

export function direcao(mercado: string, p01: number): string {
  const m = /^[A-Z][a-z]/.test(mercado) ? mercado.charAt(0).toLowerCase() + mercado.slice(1) : mercado;
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
/**
 * #254-b fix round 1 — golsCasa/golsFora vem de `average_total_goals_per_match`
 * (fixtures_service.py:1336-1337; FootyStats seasonAVG_overall) e escanteiosCasa/
 * escanteiosFora de `team_corners_per_match` (fixtures_service.py:1263-1264):
 * media do TIME na temporada inteira, sem separar jogos de casa/fora. A frase
 * nao pode afirmar "em casa"/"fora" — descreve o dado como ele e.
 */
export function fraseOrigem(o: Origem, casa: string, fora: string, liga: string): string | null {
  if (o.golsCasa != null && o.golsFora != null && o.golsLiga != null)
    return `Nos jogos do ${casa} saem ${umaCasa.format(o.golsCasa)} gols por partida na temporada; nos do ${fora}, ${umaCasa.format(o.golsFora)}; média da ${liga}: ${umaCasa.format(o.golsLiga)}.`;
  if (o.escanteiosCasa != null && o.escanteiosFora != null && o.escanteiosLiga != null)
    return `${casa} cobra ${umaCasa.format(o.escanteiosCasa)} escanteios por jogo na temporada; ${fora}, ${umaCasa.format(o.escanteiosFora)}; média da ${liga}: ${umaCasa.format(o.escanteiosLiga)}.`;
  return null;
}

/** #256 — spec §4.5: sem reais por pick em "ontem", só a contagem de acerto. */
export function resumoDoDia(acertos: number, resolvidos: number, jogos: number): string {
  return `Ontem: ${acertos} de ${resolvidos} picks fechados acertaram em ${jogos} jogos`;
}

/** #256 — "de cada 100 picks FECHADOS" (resolvidos), nunca "jogos": jogos
 * conta partidas distintas e pode ser MENOR que acertos quando mais de um
 * pick acerta na mesma partida (medido em produção: 38 acertos, 37 jogos).
 * `resolvidos` e sempre >= acertos, por construcao — nunca passa de 100%. */
export function fraseAcerto(acertos: number, resolvidos: number, jogos: number): string {
  const pct = resolvidos > 0 ? fmtPct(acertos / resolvidos) : 0;
  return `${pct} de cada 100 picks fechados · ${jogos} jogos`;
}

export const DESEMPENHO = {
  tituloAcerto: "Acerto",
  tituloRetorno: "Na sua banca atual",
  tituloCalibracao: "Calibração",
  semPicksFechados: "sem picks fechados neste período",
  retornoIndisponivel: "retorno em dinheiro ainda não disponível — o stake de cada pick não é gravado no ledger",
};

export const VAZIOS = {
  diaSemJogos: (data: string) => `Nenhum jogo nas ligas escolhidas em ${data}.`,
  proximoDia: (dia: string) => `próximo dia com picks: ${dia}`,
  /** #256 — parametrizado por dia; sem argumento continua igual ao texto que
   * o plano 1 já testa ("Os jogos de hoje não carregaram."). */
  feedNaoCarregou: (dia: "ontem" | "hoje" | "amanha" = "hoje") =>
    `Os jogos ${dia === "ontem" ? "de ontem" : dia === "amanha" ? "de amanhã" : "de hoje"} não carregaram.`,
  tentarDeNovo: "Tentar de novo",
  carimbo: (hora: string) => `de ${hora}`,
  ligaSemDados: (liga: string) => `${liga}: sem dados da rodada`,
  jogoNaoEncontrado: "jogo não encontrado",
  verFeedDeHoje: "ver os jogos de hoje",
  resultadoPendente: "resultado ainda não conferido",
  recomendacaoPreJogo: "recomendação pré-jogo",
};
