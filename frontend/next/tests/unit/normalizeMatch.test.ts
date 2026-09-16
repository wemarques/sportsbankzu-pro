import { describe, expect, it } from "vitest";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";

const bruto = {
  id: "mls-Toronto-Nashville SC-1788985800.0",
  leagueId: "mls",
  homeTeam: { name: "Toronto", logo: "", form: [], rating: 0 },
  awayTeam: { name: "Nashville SC", logo: "", form: [], rating: 0 },
  datetime: "2026-09-09T23:30:00Z",
  status: "scheduled",
  odds: { home: 3.03, draw: 3.4, away: 2.2 },
  stats: { homeWinProb: 30, drawProb: 29, awayWinProb: 41, avgGoals: 2.9,
           homeCornersPerMatch: 5.1, awayCornersPerMatch: 4.6, leagueAvgCorners: 9.8 },
  mercados: [{ mercado: "Escanteios Over 6.5", status: "SAFE", prob_min: 57, prob_max: 59,
               odd_minima: 1.75, classification: "SAFE", ev: 0.015, edge: 0.08,
               fair_odd: 1.67, book_odd: 1.75, calibrated_probability: 0.585, reason_codes: ["POSITIVE_EV"] }],
};

describe("normalizeMatch extraido (#254-a)", () => {
  it("mapeia liga, times, data e mercados como a pagina fazia", () => {
    const m = normalizeMatch(bruto, "mls", 0);
    expect(m.leagueId).toBe("usa-mls");
    expect(m.homeTeam.name).toBe("Toronto");
    expect(m.datetime).toBe("2026-09-09T23:30:00Z");
    expect(m.predictions?.[0]?.fair_odd).toBe(1.67);
    expect(m.stats.homeCornersPerMatch).toBe(5.1);
  });
  it("dedup mantem um registro por par de times e data", () => {
    const a = normalizeMatch(bruto, "mls", 0);
    const b = normalizeMatch({ ...bruto, id: "outro", mercados: [] }, "mls", 1);
    expect(deduplicateMatches([a, b])).toHaveLength(1);
  });
});
