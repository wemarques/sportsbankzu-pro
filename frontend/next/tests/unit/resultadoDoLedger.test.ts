import { describe, expect, it } from "vitest";
import { resultadoDoLedger } from "@/lib/jogoViewOntem";
import type { PickView } from "@/lib/jogoView";
import type { LedgerPick } from "@/lib/ledgerApi";

/**
 * #261 — `resultadoDoLedger` foi extraído de `toJogoViewOntem` (mesma regra,
 * agora reusada pelo enriquecimento da aba Hoje). A prova de equivalência com
 * o comportamento anterior de "ontem" está em `tests/unit/jogoViewOntem.test.ts`
 * (arquivo intocado por esta task, roda contra o `toJogoViewOntem` já
 * refatorado e continua verde: 13/13).
 */

function talao(over: Partial<PickView> = {}): PickView {
  return {
    mercado: "Escanteios Over 6.5", prob01: 0.585, fairOdd: 1.67, bookOdd: 1.75,
    edge: 0.1, ev: null, classification: "SAFE", motivo: "", vale: true, ...over,
  };
}

function pick(over: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "mls-Toronto-Nashville SC-1788985800.0", league_id: "mls",
    kickoff_utc: "2026-09-14T23:30:00+00:00", familia: "Corners", market: "Corners",
    selection: "Corners Over 6.5", published_prob: 0.585, fair_odd: 1.67, book_odd: 1.75,
    classification: "SAFE", outcome: null, detail: null, ...over,
  };
}

describe("resultadoDoLedger (#261)", () => {
  it("sem talao: null, sem nem olhar os picks", () => {
    expect(resultadoDoLedger(null, [pick({ outcome: 1, detail: "8 escanteios" })])).toBeNull();
  });

  it("talao com pick casado e outcome 1: acertou", () => {
    expect(resultadoDoLedger(talao(), [pick({ outcome: 1, detail: "8 escanteios" })]))
      .toEqual({ acertou: true, detalhe: "8 escanteios" });
  });

  it("talao com pick casado e outcome 0: errou", () => {
    expect(resultadoDoLedger(talao(), [pick({ outcome: 0, detail: "5 escanteios" })]))
      .toEqual({ acertou: false, detalhe: "5 escanteios" });
  });

  it("talao com pick casado mas outcome ainda nulo: sem desfecho", () => {
    expect(resultadoDoLedger(talao(), [pick({ outcome: null })])).toBeNull();
  });

  it("nenhum pick do mesmo mercado do talao (mercado formatado nao bate): sem desfecho", () => {
    expect(resultadoDoLedger(talao({ mercado: "Cartões Over 2.5" }), [pick({ outcome: 1, detail: "8 escanteios" })]))
      .toBeNull();
  });

  it("lista de picks vazia: sem desfecho", () => {
    expect(resultadoDoLedger(talao(), [])).toBeNull();
  });

  it("detail ausente vira string vazia (nao undefined)", () => {
    expect(resultadoDoLedger(talao(), [pick({ outcome: 1, detail: null })]))
      .toEqual({ acertou: true, detalhe: "" });
  });
});
