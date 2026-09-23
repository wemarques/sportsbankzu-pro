import { describe, expect, it } from "vitest";
import { mesclarLote, quantosEsqueletos } from "@/lib/lotesFeed";
import type { JogoView } from "@/lib/jogoView";
const v = (id: string, kickoffIso: string, estado: JogoView["estado"] = "nada") => ({ id, kickoffIso, estado } as unknown as JogoView);

describe("lotes do feed (#262, spec §3)", () => {
  it("soma lotes, deduplica por id (o novo substitui) e ordena em jogo primeiro, depois por kickoff", () => {
    const a = [v("x", "2026-09-22T20:00:00Z"), v("y", "2026-09-22T18:00:00Z")];
    const b = [v("z", "2026-09-22T19:00:00Z", "em_jogo"), v("x", "2026-09-22T20:00:00Z", "vale")];
    const r = mesclarLote(a, b);
    expect(r.map((j) => j.id)).toEqual(["z", "y", "x"]);
    expect(r.find((j) => j.id === "x")!.estado).toBe("vale");
  });
  it("esqueletos = min(3, pendentes), nunca negativo", () => {
    expect(quantosEsqueletos(13)).toBe(3); expect(quantosEsqueletos(2)).toBe(2); expect(quantosEsqueletos(0)).toBe(0); expect(quantosEsqueletos(-1)).toBe(0);
  });
});
