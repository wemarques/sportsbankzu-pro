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

  it("todo token {term:id|...} usado no codigo tem entrada no glossario", () => {
    const fs = require("node:fs") as typeof import("node:fs");
    const path = require("node:path") as typeof import("node:path");
    const raiz = path.resolve(__dirname, "../../src");
    const usados = new Set<string>();
    const anda = (dir: string) => {
      for (const nome of fs.readdirSync(dir)) {
        const p = path.join(dir, nome);
        if (fs.statSync(p).isDirectory()) anda(p);
        else if (/\.(ts|tsx)$/.test(nome)) {
          for (const m of Array.from(fs.readFileSync(p, "utf8").matchAll(/\{term:([a-z0-9-]+)\|/g))) usados.add(m[1]);
        }
      }
    };
    anda(raiz);
    const ids = new Set(TERMOS.map((t) => t.id));
    for (const id of Array.from(usados)) expect(ids.has(id), `token {term:${id}} sem entrada no glossario`).toBe(true);
  });
});
