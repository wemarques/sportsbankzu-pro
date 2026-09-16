import { describe, expect, it } from "vitest";
import { TERMOS } from "@/lib/glossarioTermos";

describe("glossarioTermos (#257, spec §5)", () => {
  it("dez termos, ids unicos, cada um com titulo/explicacao/exemplo numerico", () => {
    expect(TERMOS).toHaveLength(10);
    const ids = TERMOS.map((t) => t.id);
    expect(new Set(ids).size).toBe(10);
    for (const t of TERMOS) {
      expect(t.titulo.length).toBeGreaterThan(0);
      expect(t.explicacao.length).toBeGreaterThan(0);
      expect(/\d/.test(t.exemplo)).toBe(true); // exemplo numerico real (spec §5)
    }
  });
  it("cobre os ids citados na spec: stake e brier", () => {
    expect(TERMOS.some((t) => t.id === "stake")).toBe(true);
    expect(TERMOS.some((t) => t.id === "brier")).toBe(true);
  });
});
