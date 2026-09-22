/**
 * #256 — picks do `/ledger/dia` viram `JogoView`/`PickView` (os MESMOS tipos
 * de `lib/jogoView.ts`), para "ontem" reaproveitar `CardJogo`/`Talao`/`Detalhe`
 * sem alteração. Fonte única (spec §6.3): NUNCA chama `/fixtures` para dias
 * passados — só o que foi publicado, via ledger.
 */
import type { JogoView, PickView } from "@/lib/jogoView";
import { escolherTalao } from "@/lib/jogoView";
import type { LedgerPick } from "@/lib/ledgerApi";
import { fmtMercado } from "@/lib/classifications";

const VALE = new Set(["SAFE", "NEUTRO_QUALIFICADO"]);

/**
 * `match_id` = `{league_id}-{casa}-{fora}-{epoch}` (backend/services/
 * prediction_ledger.py:236, kickoff_da_linha). `league_id` já vem separado no
 * próprio pick — remover esse prefixo exato elimina a ambiguidade de slugs
 * de liga com hífen (ex.: "liga-mx", "premier-league"). O sufixo epoch é
 * removido com a mesma regra do backend (`rsplit` do último `-` numérico).
 * Nenhum nome de time com hífen interno foi observado nos exemplos reais de
 * produção auditados para a Task 21 (#256); se aparecer, o fallback abaixo
 * NUNCA lança — devolve a string inteira em `casa` e `fora` vazio.
 */
export function parseTimesDoMatchId(matchId: string, leagueId: string): { casa: string; fora: string } {
  const prefixo = `${leagueId}-`;
  const semLiga = matchId.startsWith(prefixo) ? matchId.slice(prefixo.length) : matchId;
  const semEpoch = semLiga.replace(/-\d+(\.\d+)?$/, "");
  const partes = semEpoch.split("-");
  if (partes.length !== 2 || !partes[0] || !partes[1]) return { casa: semEpoch, fora: "" };
  return { casa: partes[0], fora: partes[1] };
}

/**
 * Aproxima o `display_label` que o backend monta em `ev_classification.py`
 * (linhas 1005, 1056/1097, 1120, 1335/1413, 1488/1514) a partir de
 * `market`/`selection` — o `prediction_ledger` NÃO grava `display_label`
 * (só `market`/`selection`, `prediction_ledger.py:710-711`), então o texto
 * exato publicado não pode ser recuperado; isto é uma reconstrução, não uma
 * cópia. Verificar empiricamente contra linhas reais antes de fechar a
 * tarefa (Step 5 abaixo).
 */
export function formatarSelecaoLedger(market: string, selection: string): string {
  const s = (selection || "").trim();
  switch (market) {
    case "Over/Under":
      return fmtMercado(/gols?$/i.test(s) ? s : `${s} gols`);
    case "Corners":
      return fmtMercado(s.replace(/^Corners\s*/i, "Escanteios "));
    case "Cards":
      return fmtMercado(`Cartoes ${s.replace(/^Cards\s*/i, "")}`.trim());
    case "BTTS":
      return /yes/i.test(s) ? "Ambos marcam — SIM" : "Ambos marcam — NÃO";
    default:
      return fmtMercado(s);
  }
}

/**
 * #261 — extraído de `toJogoViewOntem` para reuso no enriquecimento da aba
 * Hoje (`app/jogos/Feed.tsx`): mesma regra, um lugar só. Acha, entre os picks
 * do jogo, o que corresponde ao talão (por `mercado` formatado — o ledger não
 * grava `display_label`, só `market`/`selection`; `formatarSelecaoLedger`
 * reconstrói o mesmo texto que `toPick`/`fmtMercado` produzem do lado do
 * feed) e monta o resultado a partir do `outcome`/`detail` publicados. Sem
 * talão, sem pick casado ou sem `outcome` ainda → `null` (sem desfecho).
 */
export function resultadoDoLedger(talao: PickView | null, picksDoJogo: LedgerPick[]): JogoView["resultado"] {
  if (!talao) return null;
  const pick = picksDoJogo.find((p) => formatarSelecaoLedger(p.market, p.selection) === talao.mercado);
  if (!pick || pick.outcome == null) return null;
  return { acertou: pick.outcome === 1, detalhe: pick.detail ?? "" };
}

export function agruparPorJogo(picks: LedgerPick[]): Map<string, LedgerPick[]> {
  const mapa = new Map<string, LedgerPick[]>();
  for (const p of picks) {
    const lista = mapa.get(p.match_id) ?? [];
    lista.push(p);
    mapa.set(p.match_id, lista);
  }
  return mapa;
}

export function toJogoViewOntem(
  matchId: string, leagueId: string, ligaNome: string, picksDoJogo: LedgerPick[],
): JogoView {
  const { casa, fora } = parseTimesDoMatchId(matchId, leagueId);
  const kickoffIso = picksDoJogo.find((p) => p.kickoff_utc)?.kickoff_utc ?? "";
  const pares = picksDoJogo
    .filter((p) => p.published_prob != null && p.fair_odd != null)
    .map((p) => ({
      raw: p,
      view: {
        mercado: formatarSelecaoLedger(p.market, p.selection),
        prob01: p.published_prob as number,
        fairOdd: p.fair_odd as number,
        bookOdd: p.book_odd,
        edge: p.book_odd != null && p.book_odd > 1
          ? Number(((p.published_prob as number) - 1 / p.book_odd).toFixed(4))
          : null,
        ev: null,
        classification: p.classification,
        motivo: "",
        vale: VALE.has(p.classification),
      } as PickView,
    }));
  const picks = pares.map((x) => x.view);
  const { talao, segundo } = escolherTalao(picks);
  const resultado = resultadoDoLedger(talao, picksDoJogo);
  const estado: JogoView["estado"] = talao ? (resultado ? "ontem" : "ontem_sem_desfecho") : "direcao";

  return {
    id: matchId, ligaId: leagueId, ligaNome, casa, fora, kickoffIso, estado,
    talao, segundo,
    direcao: talao ? null : (picks.find((p) => p.classification === "NEUTRO") ?? null),
    mercados: picks, totalAvaliados: picks.length, totalValem: picks.filter((p) => p.vale).length,
    aoVivo: null, resultado,
    origem: { golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null },
  };
}
