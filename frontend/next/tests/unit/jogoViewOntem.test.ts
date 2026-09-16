import { describe, expect, it } from "vitest";
import { parseTimesDoMatchId, formatarSelecaoLedger, agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import type { LedgerPick } from "@/lib/ledgerApi";

function pick(over: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "mls-Toronto-Nashville SC-1788985800.0", league_id: "mls",
    kickoff_utc: "2026-09-14T23:30:00+00:00", familia: "Corners", market: "Corners",
    selection: "Corners Over 6.5", published_prob: 0.585, fair_odd: 1.67, book_odd: 1.75,
    classification: "SAFE", outcome: null, detail: null, ...over,
  };
}

describe("parseTimesDoMatchId (#256)", () => {
  it("formato padrao liga-casa-fora-epoch", () => {
    expect(parseTimesDoMatchId("mls-Toronto-Nashville SC-1788985800.0", "mls"))
      .toEqual({ casa: "Toronto", fora: "Nashville SC" });
  });
  it("liga com hifen no proprio slug (exemplo real de producao)", () => {
    expect(parseTimesDoMatchId("liga-mx-Guadalajara-Pumas UNAM-1789348020.0", "liga-mx"))
      .toEqual({ casa: "Guadalajara", fora: "Pumas UNAM" });
  });
  it("time com hifen interno nao quebra — cai no fallback documentado", () => {
    const r = parseTimesDoMatchId("premier-league-Newcastle-United-Arsenal-1788985800.0", "premier-league");
    expect(r.fora === "" || (r.casa.length > 0 && r.fora.length > 0)).toBe(true);
  });
});

describe("formatarSelecaoLedger (#256, aproximacao do display_label — ver decisao 3 do plano)", () => {
  it("Over/Under acrescenta 'gols' quando falta", () => {
    expect(formatarSelecaoLedger("Over/Under", "Under 3.5")).toBe("Under 3.5 gols");
  });
  it("Corners troca o prefixo por Escanteios", () => {
    expect(formatarSelecaoLedger("Corners", "Corners Over 6.5")).toBe("Escanteios Over 6.5");
  });
  it("Cards vira Cartões com acento (fmtMercado)", () => {
    expect(formatarSelecaoLedger("Cards", "Over 3.5")).toBe("Cartões Over 3.5");
  });
  it("BTTS mapeia Yes/No", () => {
    expect(formatarSelecaoLedger("BTTS", "BTTS Yes")).toBe("Ambos marcam — SIM");
    expect(formatarSelecaoLedger("BTTS", "BTTS No")).toBe("Ambos marcam — NÃO");
  });
  it("desconhecido cai no texto bruto", () => {
    expect(formatarSelecaoLedger("Outro", "X")).toBe("X");
  });
});

describe("toJogoViewOntem (#256, spec §4.2)", () => {
  it("estado 'ontem' quando o talao tem outcome", () => {
    const picks = [pick({ outcome: 1, detail: "8 escanteios" })];
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", picks);
    expect(v.estado).toBe("ontem");
    expect(v.resultado).toEqual({ acertou: true, detalhe: "8 escanteios" });
    expect(v.casa).toBe("Toronto"); expect(v.fora).toBe("Nashville SC");
    expect(v.talao?.mercado).toBe("Escanteios Over 6.5");
  });
  it("estado 'ontem_sem_desfecho' quando outcome e nulo", () => {
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", [pick({ outcome: null })]);
    expect(v.estado).toBe("ontem_sem_desfecho");
    expect(v.resultado).toBeNull();
  });
  it("erro: sem talao (so NEUTRO), estado 'direcao'", () => {
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS",
      [pick({ classification: "NEUTRO", outcome: 0, detail: "5 escanteios" })]);
    expect(v.estado).toBe("direcao");
    expect(v.direcao?.mercado).toBe("Escanteios Over 6.5");
  });
  it("escolhe o talao pela mesma regra de escolherTalao (maior edge)", () => {
    const picks = [
      pick({ market: "Corners", selection: "Corners Over 6.5", book_odd: 1.70, fair_odd: 1.67, outcome: 1, detail: "8 escanteios" }),
      pick({ market: "Cards", selection: "Over 2.5", published_prob: 0.60, book_odd: 2.10, fair_odd: 1.67, outcome: 0, detail: "1 cartão" }),
    ];
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", picks);
    expect(v.talao?.mercado).toBe("Cartões Over 2.5"); // edge: 0.60 - 1/2.10 ≈ 0,1238 > 0.585 - 1/1.70 ≈ -0,0032 (o pick de Corners fica com edge NEGATIVO — book_odd 1.70 abaixo do que a chance publicada sugeriria)
    expect(v.resultado).toEqual({ acertou: false, detalhe: "1 cartão" });
  });
});

describe("agruparPorJogo", () => {
  it("agrupa picks pelo match_id", () => {
    const a = pick({ match_id: "j1" }), b = pick({ match_id: "j1", market: "Cards" }), c = pick({ match_id: "j2" });
    const m = agruparPorJogo([a, b, c]);
    expect(m.get("j1")).toHaveLength(2);
    expect(m.get("j2")).toHaveLength(1);
  });
});
