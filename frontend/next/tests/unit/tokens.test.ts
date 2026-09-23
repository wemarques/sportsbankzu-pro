import { describe, expect, it } from "vitest";
import { TOKENS, PARES_PERMITIDOS, contraste } from "@/lib/tokens";
import { readFileSync } from "node:fs";
import path from "node:path";

describe("tokens (#254, spec §2)", () => {
  it("todo par (texto, fundo) usado na UI passa de 4,5:1", () => {
    for (const [texto, fundo, minimo] of PARES_PERMITIDOS) {
      const r = contraste(TOKENS[texto], TOKENS[fundo]);
      expect(r, `${texto} sobre ${fundo} = ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(minimo);
    }
  });

  it("confianca sobre talao e ilegivel — por isso o par nao esta na lista", () => {
    expect(contraste(TOKENS.confianca, TOKENS.talao)).toBeLessThan(3);
    expect(PARES_PERMITIDOS.some(([t, f]) => t === "confianca" && f === "talao")).toBe(false);
  });

  it("contra-texto sobre talao nao e um par permitido — o aviso de copia usa tinta-do-talao la dentro", () => {
    expect(PARES_PERMITIDOS.some(([t, f]) => t === "contra-texto" && f === "talao")).toBe(false);
  });

  it("texto-apagado sobre hover e o par mais fraco e ainda passa", () => {
    expect(contraste(TOKENS["texto-apagado"], TOKENS.hover)).toBeGreaterThanOrEqual(4.5);
  });

  it("nao ha verde na paleta", () => {
    for (const hex of Object.values(TOKENS)) {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      expect(g > r + 40 && g > b + 40, `${hex} puxa para o verde`).toBe(false);
    }
  });

  it("globals.css carrega os mesmos hex de tokens.ts", () => {
    const css = readFileSync(path.resolve(__dirname, "../../src/app/globals.css"), "utf8");
    for (const [nome, hex] of Object.entries(TOKENS)) {
      expect(css, `--sb-${nome}`).toContain(`--sb-${nome}: ${hex};`);
    }
  });

  it("#262: marca existe, e o mesmo hex de confianca, e passa sobre tinta/painel/hover", () => {
    expect(TOKENS.marca).toBe(TOKENS.confianca);
    for (const fundo of ["tinta", "painel", "hover"] as const) {
      expect(contraste(TOKENS.marca, TOKENS[fundo])).toBeGreaterThanOrEqual(4.5);
      expect(PARES_PERMITIDOS.some(([t, f]) => t === "marca" && f === fundo)).toBe(true);
    }
    expect(PARES_PERMITIDOS.some(([t, f]) => t === "marca" && f === "talao")).toBe(false);
  });
});
