/** #257 — retorno retroativo: aplica a regra de stake de HOJE (`calcStake`,
 * Quarter Kelly — não duplicado, só chamado) a cada pick FECHADO do período,
 * usando os campos já publicados no ledger. Nunca recalcula probabilidade
 * nem Kelly no backend (proibição 5). `outcome` é `0|1` (nunca `null` aqui —
 * `lib/ledgerApi.ts::getLedgerPicks` só devolve picks resolvidos). */
import type { LedgerPick } from "@/lib/ledgerApi";
import { calcStake } from "@/lib/bancaStore";

export interface RetornoRetroativo {
  valor: number;
  pctBanca: number;
  n: number;
  semPreco: number;
}

export function retornoRetroativo(picks: LedgerPick[], banca: number): RetornoRetroativo {
  let valor = 0;
  let n = 0;
  let semPreco = 0;
  for (const p of picks) {
    if (p.book_odd == null || p.published_prob == null) {
      semPreco += 1;
      continue;
    }
    const stake = calcStake(p.published_prob, p.book_odd, banca, p.classification);
    valor += p.outcome ? stake * (p.book_odd - 1) : -stake;
    n += 1;
  }
  return { valor, pctBanca: banca > 0 ? valor / banca : 0, n, semPreco };
}
