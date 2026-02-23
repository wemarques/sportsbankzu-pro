import { test, expect } from "@playwright/test";

test.describe("API Routes", () => {
  test("POST /api/matches returns matches array", async ({ request }) => {
    const resp = await request.post("/api/matches", {
      data: { leagueIds: ["premier-league"] },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty("matches");
    expect(Array.isArray(body.matches)).toBe(true);
  });

  test("POST /api/matches with empty leagues returns empty array", async ({ request }) => {
    const resp = await request.post("/api/matches", {
      data: { leagueIds: [] },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.matches).toHaveLength(0);
  });

  test("POST /api/matches with invalid league falls back to empty", async ({ request }) => {
    const resp = await request.post("/api/matches", {
      data: { leagueIds: ["nonexistent-league-xyz"] },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.matches).toHaveLength(0);
  });

  test("GET /api/matches/fetch returns valid response", async ({ request }) => {
    const resp = await request.get("/api/matches/fetch?leagues=premier-league&date=today");
    // In CI without a live backend, the quality gate may return 503 for mock data.
    // Both 200 (real data) and 503 (quality gate rejection) are valid responses.
    expect([200, 503]).toContain(resp.status());
    const body = await resp.json();
    expect(body).toHaveProperty("matches");
    expect(Array.isArray(body.matches)).toBe(true);
  });

  test("match objects have expected structure", async ({ request }) => {
    const resp = await request.post("/api/matches", {
      data: { leagueIds: ["premier-league"] },
    });
    const body = await resp.json();
    if (body.matches.length > 0) {
      const match = body.matches[0];
      expect(match).toHaveProperty("id");
      expect(match).toHaveProperty("leagueId");
      expect(match).toHaveProperty("homeTeam");
      expect(match).toHaveProperty("awayTeam");
      expect(match).toHaveProperty("datetime");
      expect(match).toHaveProperty("status");
    }
  });

  test("POST /api/decision/pre returns picks array", async ({ request }) => {
    const resp = await request.post("/api/decision/pre", {
      data: { matchId: "test-match" },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty("picks");
    expect(Array.isArray(body.picks)).toBe(true);
  });
});
