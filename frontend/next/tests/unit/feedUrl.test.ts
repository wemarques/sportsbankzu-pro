import { describe, expect, it } from "vitest";
import { lerFeedUrl, escreverFeedUrl, diaParaApi, diaISOOntem, chaveDoDia } from "@/lib/feedUrl";

describe("estado do feed vive na URL (spec §3)", () => {
  it("padrao: hoje, todas, sem jogo", () => {
    expect(lerFeedUrl(new URLSearchParams(""))).toEqual({ dia: "hoje", liga: "todas", jogo: null });
  });
  it("le e escreve os tres parametros", () => {
    const e = lerFeedUrl(new URLSearchParams("dia=amanha&liga=mls&jogo=j1"));
    expect(e).toEqual({ dia: "amanha", liga: "mls", jogo: "j1" });
    expect(escreverFeedUrl(e)).toBe("/jogos?dia=amanha&liga=mls&jogo=j1");
    expect(escreverFeedUrl({ dia: "hoje", liga: "todas", jogo: null })).toBe("/jogos");
  });
  it("valor invalido cai no padrao", () => {
    expect(lerFeedUrl(new URLSearchParams("dia=semana")).dia).toBe("hoje");
  });
  it("mapeia para o parametro do backend; ontem nao tem fonte ate o plano 3", () => {
    expect(diaParaApi("hoje")).toBe("today");
    expect(diaParaApi("amanha")).toBe("tomorrow");
    expect(diaParaApi("ontem")).toBeNull();
  });
});

describe("diaISOOntem (#256) — BRT fixo UTC-3, mesma convencao das outras datas do app", () => {
  it("meio-dia UTC de hoje vira o dia anterior em BRT", () => {
    expect(diaISOOntem(new Date("2026-09-16T12:00:00Z"))).toBe("2026-09-15");
  });
  it("madrugada UTC (ainda tarde do dia anterior em BRT) tambem cai um dia", () => {
    expect(diaISOOntem(new Date("2026-09-16T02:00:00Z"))).toBe("2026-09-14");
  });
});

describe("chaveDoDia (#262 fix wave) — diasLidos chaveado pela data ISO, nao pelo rotulo", () => {
  it("ontem, hoje e amanha viram tres datas ISO consecutivas", () => {
    const agora = new Date("2026-09-23T02:30:00Z");
    expect(chaveDoDia("ontem", agora)).toBe("2026-09-21");
    expect(chaveDoDia("hoje", agora)).toBe("2026-09-22");
    expect(chaveDoDia("amanha", agora)).toBe("2026-09-23");
  });
});
