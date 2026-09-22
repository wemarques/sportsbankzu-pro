import { describe, expect, it } from "vitest";
import { normalizeMatch } from "@/lib/normalizeMatch";
import { AVAILABLE_LEAGUES, toBackendLeagueId } from "@/lib/leagues";

// #259 — para cada liga do catalogo, o id que o backend devolve (via
// toBackendLeagueId, a mesma traducao que o fetch usa) tem que resolver para
// o nome oficial em normalizeMatch. Usa AVAILABLE_LEAGUES (22) em vez de
// ACTIVE_LEAGUES() (13): scotland-premiership — uma das 3 ligas que
// motivaram o fix (#259) — esta com active:false hoje, e a prova de
// "vermelho nas 3 ligas" exige cobri-la.
describe("normalizeMatch resolve nome de liga pelo mapa oficial (#259)", () => {
  for (const liga of AVAILABLE_LEAGUES) {
    const backendId = toBackendLeagueId(liga.id);
    it(`${liga.id} (backend "${backendId}") -> leagueName "${liga.name}"`, () => {
      const bruto = {
        home_team: "Equipe Casa",
        away_team: "Equipe Visitante",
        match_date: "2026-09-22T21:30:00Z",
      };
      const m = normalizeMatch(bruto, backendId, 0);
      expect(m.leagueName).toBe(liga.name);
    });
  }

  it("id de backend desconhecido devolve o proprio id como nome (#250)", () => {
    const bruto = {
      home_team: "Equipe Casa",
      away_team: "Equipe Visitante",
      match_date: "2026-09-22T21:30:00Z",
    };
    const m = normalizeMatch(bruto, "liga-inexistente-xyz", 0);
    expect(m.leagueName).toBe("liga-inexistente-xyz");
  });
});
