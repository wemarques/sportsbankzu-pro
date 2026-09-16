import { describe, expect, it } from "vitest";
import { retornoRetroativo } from "@/lib/retornoRetroativo";
import type { LedgerPick } from "@/lib/ledgerApi";

function pick(p: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "m", league_id: "mls", kickoff_utc: null, familia: "Over/Under",
    market: "Over/Under", selection: "Over 2.5", published_prob: null, fair_odd: null,
    book_odd: null, classification: "SAFE", outcome: null, detail: null, ...p,
  };
}

describe("retornoRetroativo (#257) — aritmetica a mao, sem fronteira de arredondamento", () => {
  it("dois picks com preco (um paga stake>0, um cai a 0 pelo cap) + um sem preco", () => {
    const picks: LedgerPick[] = [
      // A: prob=0.55, odd=2.2, SAFE, outcome=1, banca=1000.
      //    b=1.2; kelly=(0.55*1.2-0.45)/1.2=(0.66-0.45)/1.2=0.175
      //    qk=0.175*0.25=0.04375 (< cap 0.05, nao bate no teto)
      //    stake=round(1000*0.04375*100)/100 = round(4375)/100 = 43.75
      //    P&L = stake*(odd-1) = 43.75*1.2 = 52.5
      pick({ match_id: "a", published_prob: 0.55, book_odd: 2.2, classification: "SAFE", outcome: 1 }),
      // B: prob=0.52, odd=1.9, NEUTRO_QUALIFICADO, outcome=0, banca=1000.
      //    b=0.9; kelly=(0.52*0.9-0.48)/0.9=(0.468-0.48)/0.9=-0.01333...
      //    qk=-0.01333*0.15=-0.002 -> capped a 0 (kelly negativo, sem floor NQ)
      //    stake=0 -> P&L=0 (ainda conta em n, tem preco)
      pick({ match_id: "b", published_prob: 0.52, book_odd: 1.9, classification: "NEUTRO_QUALIFICADO", outcome: 0 }),
      // C: sem book_odd — nunca precificado, nao entra no calculo de valor/n.
      pick({ match_id: "c", published_prob: 0.6, book_odd: null, classification: "SAFE", outcome: 1 }),
    ];
    const r = retornoRetroativo(picks, 1000);
    expect(r.valor).toBeCloseTo(52.5, 6);
    expect(r.pctBanca).toBeCloseTo(0.0525, 6);
    expect(r.n).toBe(2);
    expect(r.semPreco).toBe(1);
  });
  it("banca zero ou picks vazio: zero seguro, sem divisao por zero", () => {
    expect(retornoRetroativo([], 1000)).toEqual({ valor: 0, pctBanca: 0, n: 0, semPreco: 0 });
  });
});
