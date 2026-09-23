import { describe, expect, it } from "vitest";
import { fmtReais, fmtOdd, fmtDelta, fmtPct, fmtHora, fmtLigaHora, fmtDataCurta, fmtDataPorExtenso, proximaMeiaNoiteBrt } from "@/lib/formato";

describe("formato pt-BR (#254)", () => {
  it("reais com milhar e virgula", () => {
    expect(fmtReais(1000)).toBe("R$ 1.000,00");
    expect(fmtReais(25)).toBe("R$ 25,00");
    expect(fmtReais(312.4)).toBe("R$ 312,40");
  });
  it("odd com duas casas e virgula", () => {
    expect(fmtOdd(1.75)).toBe("1,75");
    expect(fmtOdd(2)).toBe("2,00");
  });
  it("delta com sinal e duas casas", () => {
    expect(fmtDelta(0.08)).toBe("+0,08");
    expect(fmtDelta(-0.13)).toBe("−0,13");
    expect(fmtDelta(0)).toBe("0,00");
  });
  it("pct arredonda para inteiro", () => {
    expect(fmtPct(0.5849)).toBe(58);
    expect(fmtPct(0.585)).toBe(59);
  });
  it("hora e data em America/Sao_Paulo", () => {
    expect(fmtHora("2026-09-09T23:30:00Z")).toBe("20:30");
    expect(fmtDataCurta("2026-09-09T23:30:00Z")).toBe("09/09");
    expect(fmtLigaHora("MLS", "2026-09-09T23:30:00Z")).toBe("MLS, 20:30");
  });
});

describe("data por extenso em BRT (#262, spec §1)", () => {
  it("terca 22/09 as 23:30 BRT (02:30Z do dia 23) ainda e terca, 22", () => {
    expect(fmtDataPorExtenso(new Date("2026-09-23T02:30:00Z"))).toBe("terça, 22 de setembro");
  });
  it("as 00:00 BRT (03:00Z) vira quarta, 23; domingo e sabado sem '-feira'", () => {
    expect(fmtDataPorExtenso(new Date("2026-09-23T03:00:00Z"))).toBe("quarta, 23 de setembro");
    expect(fmtDataPorExtenso(new Date("2026-09-20T15:00:00Z"))).toBe("domingo, 20 de setembro");
  });
  it("proxima meia-noite BRT e o proximo 03:00Z", () => {
    expect(proximaMeiaNoiteBrt(new Date("2026-09-23T02:30:00Z")).toISOString()).toBe("2026-09-23T03:00:00.000Z");
    expect(proximaMeiaNoiteBrt(new Date("2026-09-23T03:00:00Z")).toISOString()).toBe("2026-09-24T03:00:00.000Z");
  });
});
