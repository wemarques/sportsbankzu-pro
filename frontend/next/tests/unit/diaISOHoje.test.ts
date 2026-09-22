import { describe, expect, it } from "vitest";
import { diaISOHoje, diaISOOntem } from "@/lib/feedUrl";

/**
 * #261 — `diaISOHoje` reusa a mesma regra de `diaISOOntem` (BRT fixo UTC-3,
 * `tests/unit/feedUrl.test.ts` intocado prova que `diaISOOntem` continua com
 * o mesmo comportamento depois da extração de `diaISOEmBrt`).
 */
describe("diaISOHoje (#261) — BRT fixo UTC-3, mesma convencao de diaISOOntem", () => {
  it("meio-dia UTC ainda e o mesmo dia em BRT", () => {
    expect(diaISOHoje(new Date("2026-09-16T12:00:00Z"))).toBe("2026-09-16");
  });
  it("madrugada UTC (ainda e o dia anterior em BRT)", () => {
    expect(diaISOHoje(new Date("2026-09-16T02:00:00Z"))).toBe("2026-09-15");
  });
  it("e sempre um dia depois de diaISOOntem, para o mesmo instante", () => {
    const agora = new Date("2026-09-21T15:00:00Z");
    const ontem = new Date(diaISOOntem(agora) + "T12:00:00Z");
    const hoje = new Date(diaISOHoje(agora) + "T12:00:00Z");
    expect(hoje.getTime() - ontem.getTime()).toBe(24 * 3600_000);
  });
});
