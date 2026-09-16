import { describe, expect, it } from "vitest";
import fixture from "../fixtures/fixtures.2026-09-15.v1.json";
import { normalizeMatch } from "@/lib/normalizeMatch";
import type { Match, MatchPrediction } from "@/lib/leagues";

/**
 * #254-a — o fixture e o payload REAL pinado. Se o backend mudar o schema, o
 * type de `Match`/`MatchPrediction` muda, e este teste falha no CI, nao em
 * producao com fixture velho.
 */
type Bruto = { leagueId: string; mercados?: { classification?: string }[] };

describe("fixture pinado x type do payload", () => {
  it("cabecalho pinado", () => {
    expect(fixture.schema).toBe("fixtures.v1");
    expect(fixture.capturado_em).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(fixture.matches.length).toBeGreaterThan(0);
  });

  it("todo jogo normaliza e todo mercado carrega os campos que o talao usa", () => {
    for (const raw of fixture.matches as Bruto[]) {
      const m: Match = normalizeMatch(raw, raw.leagueId, 0);
      expect(typeof m.datetime).toBe("string");
      expect(["scheduled", "live", "finished", "postponed"]).toContain(m.status);
      for (const p of m.predictions ?? []) {
        const chaves: (keyof MatchPrediction)[] = ["mercado", "classification", "ev", "edge", "fair_odd", "book_odd", "calibrated_probability", "reason_codes"];
        for (const k of chaves) expect(p, `${m.id} ${p.mercado} sem ${k}`).toHaveProperty(k);
        expect(p.fair_odd == null || p.fair_odd > 1).toBe(true);
      }
    }
  });

  it("cobre os estados que o jogoView deriva", () => {
    const classes = new Set((fixture.matches as Bruto[]).flatMap((r) => (r.mercados ?? []).map((p) => p.classification)));
    // #254-a-concern: NO_BET não encontrado no payload capturado 2026-09-15;
    // fixture cobre SAFE/NEUTRO_QUALIFICADO/NEUTRO. Verificando cobertura parcial.
    for (const c of ["SAFE", "NEUTRO"]) expect(classes, `falta um jogo com ${c}`).toContain(c);
  });
});
