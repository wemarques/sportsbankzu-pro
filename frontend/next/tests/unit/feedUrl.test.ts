import { describe, expect, it } from "vitest";
import { lerFeedUrl, escreverFeedUrl, diaParaApi } from "@/lib/feedUrl";

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
