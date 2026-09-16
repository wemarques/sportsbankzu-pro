import { describe, expect, it } from "vitest";
import { lerDesempenhoUrl, escreverDesempenhoUrl, periodoPorExtenso } from "@/lib/desempenhoUrl";

describe("estado de /desempenho na URL (spec §5)", () => {
  it("padrao: 30d, sem familia/liga", () => {
    expect(lerDesempenhoUrl(new URLSearchParams(""))).toEqual({ periodo: "30d", familia: null, liga: null });
  });
  it("le e escreve os tres parametros", () => {
    const e = lerDesempenhoUrl(new URLSearchParams("periodo=7d&familia=Corners&liga=mls"));
    expect(e).toEqual({ periodo: "7d", familia: "Corners", liga: "mls" });
    expect(escreverDesempenhoUrl(e)).toBe("/desempenho?periodo=7d&familia=Corners&liga=mls");
  });
  it("periodo invalido cai no padrao", () => {
    expect(lerDesempenhoUrl(new URLSearchParams("periodo=1ano")).periodo).toBe("30d");
  });
  it("periodo por extenso — o operador nao confia em palavra magica (spec §5)", () => {
    expect(periodoPorExtenso("temporada", new Date("2026-09-16"))).toBe("03/09–hoje");
    expect(periodoPorExtenso("7d", new Date("2026-09-16T12:00:00Z"))).toBe("09/09–hoje");
    expect(periodoPorExtenso("30d", new Date("2026-09-16T12:00:00Z"))).toBe("17/08–hoje");
  });
});
