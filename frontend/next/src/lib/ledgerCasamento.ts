/**
 * #261 — casamento de jogo entre `JogoView` (produtor: `/api/matches/fetch`
 * → `normalizeMatch` → `toJogoView`) e `LedgerPick` (produtor: `/ledger/dia`),
 * usado pelo enriquecimento da aba Hoje (spec 2026-09-15, emenda #261 §4.2).
 *
 * PROIBIDO comparar id cru (spec): os dois produtores grafam o id de forma
 * diferente — fixture: `championship-Middlesbrough-Millwall-1798920000`
 * (epoch inteiro, sem `.0`); ledger: `primeira-liga-Sporting Braga-GD Estoril
 * Praia-1789415100.0` (epoch com `.0`, `backend/services/prediction_ledger.py`
 * `kickoff_da_linha`). O casamento é por liga + kickoff + times, nunca pelo id.
 */
import type { JogoView } from "@/lib/jogoView";
import type { LedgerPick } from "@/lib/ledgerApi";
import { toBackendLeagueId } from "@/lib/leagues";
import { parseTimesDoMatchId } from "@/lib/jogoViewOntem";

/** minúsculas, sem acento, sem espaços/hífens (spec §4.2, emenda #261). */
function normalizarTime(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[\s-]+/g, "");
}

/**
 * Epoch (segundos) do kickoff do pick: `kickoff_utc` quando presente (linhas
 * gravadas desde #252-c); nas linhas antigas (nulas) sai do sufixo epoch do
 * `match_id` — regra única em `prediction_ledger.kickoff_da_linha` (mesma
 * regra documentada em CLAUDE.md e usada por `jogoViewOntem.ts`).
 */
function epochDoPick(pick: LedgerPick): number | null {
  if (pick.kickoff_utc) {
    const t = Date.parse(pick.kickoff_utc);
    if (!Number.isNaN(t)) return Math.round(t / 1000);
  }
  const m = pick.match_id.match(/-(\d+(?:\.\d+)?)$/);
  return m ? Math.round(parseFloat(m[1])) : null;
}

/**
 * Mesmo jogo, comparando o que os dois produtores realmente compartilham:
 * liga (via `toBackendLeagueId`), kickoff (tolerância 0) e times normalizados.
 * NUNCA compara `view.id`/`pick.match_id` cru.
 */
export function mesmoJogo(view: JogoView, pick: LedgerPick): boolean {
  if (toBackendLeagueId(view.ligaId) !== pick.league_id) return false;

  const epochPick = epochDoPick(pick);
  const epochView = Math.round(Date.parse(view.kickoffIso) / 1000);
  if (epochPick == null || Number.isNaN(epochView) || epochPick !== epochView) return false;

  const { casa, fora } = parseTimesDoMatchId(pick.match_id, pick.league_id);
  return normalizarTime(casa) === normalizarTime(view.casa) && normalizarTime(fora) === normalizarTime(view.fora);
}
