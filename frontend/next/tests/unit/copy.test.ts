import { describe, expect, it } from "vitest";
import * as C from "@/lib/copy";
import { motivoRecusa } from "@/lib/reasonCodes";
import { fraseAcertoHero, HERO } from "@/lib/copy";

describe("copy (#254, spec §4.4)", () => {
  it("frequencia", () => {
    expect(C.frequencia(0.5849)).toBe("acontece em 58 de cada 100 jogos assim");
  });
  it("linha de preco acima do minimo", () => {
    expect(C.linhaPreco(1.75, 1.67, false)).toEqual({
      texto: "mercado paga 1,75, acima do mínimo 1,67 (+0,08)", abaixo: false, semPreco: false,
    });
  });
  it("linha de preco abaixo do minimo", () => {
    expect(C.linhaPreco(1.62, 1.75, false)).toEqual({
      texto: "mercado paga 1,62, abaixo do mínimo 1,75 (−0,13)", abaixo: true, semPreco: false,
    });
  });
  it("sem preco: amanha e hoje", () => {
    expect(C.linhaPreco(null, 1.67, true).texto).toBe("vale a partir de 1,67, mercado ainda sem preço");
    expect(C.linhaPreco(null, 1.67, false).texto).toBe("vale a partir de 1,67, sem preço que valha hoje");
  });
  it("stake com e sem banca", () => {
    expect(C.stake(1000, 25)).toBe("Da sua banca de R$ 1.000,00: R$ 25,00");
    expect(C.stake(null, null)).toBe("stake: defina sua banca");
  });
  it("stakeComTermo: token no valor com banca, sem token sem banca (#257 fix round 1)", () => {
    expect(C.stakeComTermo(1000, 25)).toBe("Da sua banca de R$ 1.000,00: {term:stake|R$ 25,00}");
    expect(C.stakeComTermo(null, null)).toBe("stake: defina sua banca");
  });
  it("avaliados e direcao", () => {
    expect(C.avaliados(12, 2)).toBe("12 mercados avaliados, 2 valem");
    expect(C.avaliados(12, 0)).toBe("12 mercados avaliados, nenhum vale hoje");
    expect(C.avaliados(1, 1)).toBe("1 mercado avaliado, 1 vale");
    expect(C.avaliados(1, 0)).toBe("1 mercado avaliado, nenhum vale hoje");
    expect(C.direcao("Mais de 2,5 gols", 0.57)).toBe("Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje");
    expect(C.direcao("BTTS - Sim", 0.56)).toBe("Direção: BTTS - Sim, 56 em cada 100 — sem preço que valha hoje");
  });
  it("resultado de ontem", () => {
    expect(C.resultadoOntem(true, "8 escanteios")).toBe("✓ fechou com 8 escanteios");
    expect(C.resultadoOntem(false, "5 escanteios")).toBe("× fechou com 5 escanteios");
  });
  it("tokens de glossario viram trechos", () => {
    expect(C.comTermos("o {term:edge|edge} de hoje")).toEqual([
      { texto: "o " }, { termo: "edge", texto: "edge" }, { texto: " de hoje" },
    ]);
  });
  it("motivo de recusa em duas palavras, o primeiro codigo conhecido manda", () => {
    expect(motivoRecusa(["NEGATIVE_EV"])).toBe("sem valor");
    expect(motivoRecusa(["LOW_DATA_QUALITY", "NEGATIVE_EV"])).toBe("amostra curta");
    expect(motivoRecusa(["NO_ODDS_AVAILABLE"])).toBe("sem preço");
    expect(motivoRecusa([])).toBe("não vale");
  });
  it("resumoDoDia (#256)", () => {
    expect(C.resumoDoDia(3, 4, 4)).toBe("Ontem: 3 de 4 picks fechados acertaram em 4 jogos");
  });
});

describe("fraseAcerto (#256) — denominador e resolvidos, nunca jogos", () => {
  it("38 acertos em 60 resolvidos, 37 jogos: 63 de cada 100", () => {
    expect(C.fraseAcerto(38, 60, 37)).toBe("63 de cada 100 picks fechados · 37 jogos");
  });
  it("resolvidos zero nunca divide — chamada defensiva, mesmo que o chamador ja proteja", () => {
    expect(C.fraseAcerto(0, 0, 0)).toBe("0 de cada 100 picks fechados · 0 jogos");
  });
});

describe("DESEMPENHO (#256) — rotulos centralizados", () => {
  it("tem os titulos e mensagens da tela", () => {
    expect(C.DESEMPENHO.tituloAcerto).toBe("Acerto");
    expect(C.DESEMPENHO.tituloRetorno).toBe("Na sua banca atual");
    expect(C.DESEMPENHO.tituloCalibracao).toBe("Calibração");
    expect(C.DESEMPENHO.semPicksFechados).toBe("sem picks fechados neste período");
    expect(C.DESEMPENHO.retornoIndisponivel).toBe("retorno em dinheiro ainda não disponível — o stake de cada pick não é gravado no ledger");
  });
});

describe("DESEMPENHO (#257) — retorno retroativo", () => {
  it("tem os rotulos novos do bloco de dinheiro", () => {
    expect(C.DESEMPENHO.definaBanca).toBe("defina sua banca para ver o retorno em dinheiro");
    expect(C.DESEMPENHO.retornoNaBancaAtual).toBe("seguindo o stake sugerido, na sua banca atual");
    expect(C.DESEMPENHO.retornoSemPicks).toBe("sem picks fechados com preço neste período");
  });
});

describe("fraseAcertoHero (#257, spec §5) — mesmo denominador de fraseAcerto: resolvidos, nunca jogos", () => {
  it("amostra suficiente (jogos=22 >= piso): acertos 26 / resolvidos 40 -> 65", () => {
    expect(fraseAcertoHero(26, 40, 22)).toBe("65 de cada 100 picks fechados nos últimos 30 dias, em 22 jogos");
  });
  it("abaixo do piso MIN_N_BRIER=20 (jogos=19), nulo", () => {
    expect(fraseAcertoHero(10, 15, 19)).toBeNull();
  });
  it("jogos=20, piso inclusive: mostra a frase (12/20 -> 60)", () => {
    expect(fraseAcertoHero(12, 20, 20)).toBe("60 de cada 100 picks fechados nos últimos 30 dias, em 20 jogos");
  });
});

describe("HERO (#257) — headline, CTAs e frase de vazio", () => {
  it("tem as duas linhas do headline, os tres CTAs e a frase de sem-talao", () => {
    expect(HERO.headlineLinha1).toBe("O veredito em primeiro plano.");
    expect(HERO.headlineLinha2).toBe("O rigor um nível abaixo.");
    expect(HERO.ctaJogos).toBe("Ver os jogos de hoje");
    expect(HERO.ctaEntrar).toBe("Entrar");
    expect(HERO.ctaCriarConta).toBe("Criar conta");
    expect(HERO.semTalao).toBe("Sem talão publicado hoje ou ontem.");
  });
});

it("#262 carimbo", () => { expect(C.CARIMBO.lidoAs("19:04")).toBe("lido às 19:04"); });
