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
    // SAFE ou NEUTRO_QUALIFICADO = "vale"; NEUTRO = "direcao". NO_BET nunca chega a `mercados`
    // (ev_classification.py:743): vive em stats.rejected_insights — e a prova de que o motor recusou.
    expect([...classes].some((c) => c === "SAFE" || c === "NEUTRO_QUALIFICADO"), "falta um jogo que vale").toBe(true);
    expect(classes, "falta um jogo com NEUTRO").toContain("NEUTRO");
    const brutos = fixture.matches as (Bruto & { status?: string; stats?: { rejected_insights?: unknown[] } })[];
    expect(brutos.some((r) => (r.stats?.rejected_insights?.length ?? 0) > 0), "falta um jogo com mercados recusados").toBe(true);
    expect(brutos.some((r) => r.status === "scheduled"), "falta um jogo ainda por jogar (date=tomorrow)").toBe(true);
  });
});
