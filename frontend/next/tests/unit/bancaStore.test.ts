import { beforeEach, describe, expect, it } from "vitest";
import { getBanca, setBanca, calcStake } from "@/lib/bancaStore";

describe("bancaStore (#254, spec §5)", () => {
  beforeEach(() => localStorage.clear());

  it("sem nada gravado a banca e indefinida, nao 1000", () => {
    expect(getBanca()).toBeNull();
  });
  it("grava e le", () => {
    expect(setBanca(1500)).toBe("ok");
    expect(getBanca()).toBe(1500);
  });
  it("valor invalido nao grava e devolve 'invalida'", () => {
    expect(setBanca(0)).toBe("invalida");
    expect(setBanca(NaN)).toBe("invalida");
    expect(getBanca()).toBeNull();
  });
  it("localStorage corrompido vira indefinida, sem throw", () => {
    localStorage.setItem("sportsbankzu-bankroll", "abc");
    expect(getBanca()).toBeNull();
  });
  it("le a banca do store antigo (mesma chave)", () => {
    localStorage.setItem("sportsbankzu-bankroll", "800");
    expect(getBanca()).toBe(800);
  });
  it("stake e o quarter kelly do BankrollCard, em reais", () => {
    // prob 0,58, odd 1,75, banca 1000: kelly = (0,58*0,75 - 0,42)/0,75 = 0,02; quarter = 0,005 → R$ 5
    expect(calcStake(0.58, 1.75, 1000, "SAFE")).toBeCloseTo(5, 5);
    expect(calcStake(0.58, 1.75, 0)).toBe(0);
  });
});
