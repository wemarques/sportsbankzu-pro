/**
 * #254-a — `Match` → `JogoView` (spec §4.2). Funcao PURA: todo estado que
 * parece "de view" (book_odd nulo + data futura, live) e derivado aqui; o
 * CardJogo e um switch sobre `estado` e nao calcula nada.
 */
import type { Match, MatchPrediction } from "@/lib/leagues";
import { fmtMercado } from "@/lib/classifications";
import { motivoRecusa } from "@/lib/reasonCodes";
import { getLiveClock } from "@/lib/liveClock";

export type EstadoJogo = "vale" | "direcao" | "nada" | "amanha_sem_preco" | "em_jogo" | "ontem" | "ontem_sem_desfecho";

export interface PickView {
  mercado: string; prob01: number; fairOdd: number; bookOdd: number | null;
  edge: number | null; ev: number | null; classification: string; motivo: string; vale: boolean;
}

export interface JogoView {
  id: string; ligaId: string; ligaNome: string; casa: string; fora: string; kickoffIso: string;
  estado: EstadoJogo;
  talao: PickView | null; segundo: PickView | null; direcao: PickView | null;
  mercados: PickView[]; totalAvaliados: number; totalValem: number;
  aoVivo: { periodo: string | null; minuto: number | null; placar: string | null } | null;
  resultado: { acertou: boolean; detalhe: string } | null;
}

const VALE = new Set(["SAFE", "NEUTRO_QUALIFICADO"]);
const TRES_HORAS = 3 * 3600_000;

function toPick(p: MatchPrediction): PickView | null {
  const prob = p.calibrated_probability ?? (p.prob_max != null ? p.prob_max / 100 : null);
  const fair = p.fair_odd ?? (prob ? 1 / prob : null);
  if (prob == null || fair == null) return null;
  const classification = p.classification ?? p.status ?? "NEUTRO";
  return {
    mercado: fmtMercado(p.mercado), prob01: prob, fairOdd: fair,
    bookOdd: p.book_odd != null && p.book_odd > 1 ? p.book_odd : null,
    edge: p.edge ?? null, ev: p.ev ?? null, classification,
    motivo: VALE.has(classification) ? "" : motivoRecusa(p.reason_codes ?? []),
    vale: VALE.has(classification),
  };
}

export function escolherTalao(picks: PickView[]): { talao: PickView | null; segundo: PickView | null } {
  const valem = picks.filter((p) => p.vale).sort((a, b) =>
    (b.edge ?? -Infinity) - (a.edge ?? -Infinity) || b.prob01 - a.prob01);
  return { talao: valem[0] ?? null, segundo: valem[1] ?? null };
}

export function toJogoView(m: Match, agora: Date): JogoView {
  const picks = (m.predictions ?? []).map(toPick).filter((p): p is PickView => p !== null);
  const { talao, segundo } = escolherTalao(picks);
  const ordenados = [...picks].sort((a, b) => Number(b.vale) - Number(a.vale) || (b.edge ?? -1) - (a.edge ?? -1));
  const kickoff = new Date(m.datetime).getTime();
  const clock = m.status === "live" ? getLiveClock(m, agora.getTime()) : null;
  const aoVivo = m.status === "live"
    ? { periodo: clock?.period ?? m.period ?? null, minuto: clock?.minute ?? m.minute ?? null,
        placar: m.score ? `${m.score.home}\u2013${m.score.away}` : null }
    : null;
  const direcao = talao ? null : ordenados.find((p) => p.classification === "NEUTRO") ?? null;

  let estado: EstadoJogo;
  if (m.status === "live") estado = "em_jogo";
  else if (m.status === "finished" || kickoff < agora.getTime() - TRES_HORAS) estado = "ontem_sem_desfecho";
  else if (talao && talao.bookOdd === null && kickoff > agora.getTime()) estado = "amanha_sem_preco";
  else if (talao) estado = "vale";
  else if (direcao) estado = "direcao";
  else estado = "nada";

  const totalAvaliados = picks.length + (m.rejectedInsights?.length ?? 0);

  return {
    id: m.id, ligaId: m.leagueId, ligaNome: m.leagueName, casa: m.homeTeam.name, fora: m.awayTeam.name,
    kickoffIso: m.datetime, estado, talao, segundo, direcao, mercados: ordenados,
    totalAvaliados, totalValem: picks.filter((p) => p.vale).length,
    aoVivo, resultado: null,
  };
}
