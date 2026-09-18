import { test, expect } from "@playwright/test";
import { stub } from "./helpers/stub";

// #258: status, não renderização — page.goto acopla a asserção ao HMR do dev server (projeto mobile).
test.describe("raiz e destino padrao (#258, spec §8)", () => {
  test("/ com cookie de retorno vai para /jogos", async ({ page, context }) => {
    await context.addCookies([{ name: "sbz_visitou", value: "1", domain: "localhost", path: "/" }]);
    await stub(page, { vazio: true });
    await page.goto("/");
    await expect(page).toHaveURL(/\/jogos/);
  });
  test("rotas que ficam sem link ainda respondem (nao viram 404 por engano)", async ({ request }) => {
    for (const rota of ["/login", "/register"]) {
      const resp = await request.get(rota);
      expect(resp.status()).toBeLessThan(400);
    }
  });
});

test.describe("rotas removidas (#258) — 404 previsivel, nunca 500 ou pagina em branco", () => {
  for (const rota of ["/dashboard", "/duplas", "/destaques", "/campeonatos", "/ferramentas", "/bankroll",
    "/match/qualquer-id", "/performance-stats", "/ai-audit", "/admin/reliability"]) {
    test(`${rota} responde 404 (nao 500)`, async ({ request }) => {
      const resp = await request.get(rota);
      expect(resp.status()).toBe(404);
    });
  }
});

test.describe("rotas de API removidas (#258) — 404 previsivel", () => {
  test("POST /api/ai/batch-audit responde 404", async ({ request }) => {
    const resp = await request.post("/api/ai/batch-audit");
    expect(resp.status()).toBe(404);
  });
  test("POST /api/ai/batch-audit/evaluate responde 404", async ({ request }) => {
    const resp = await request.post("/api/ai/batch-audit/evaluate");
    expect(resp.status()).toBe(404);
  });
  test("POST /api/ai/batch-audit/apply responde 404", async ({ request }) => {
    const resp = await request.post("/api/ai/batch-audit/apply");
    expect(resp.status()).toBe(404);
  });
  test("POST /api/ai/match/qualquer-id/audit responde 404", async ({ request }) => {
    const resp = await request.post("/api/ai/match/qualquer-id/audit");
    expect(resp.status()).toBe(404);
  });
  test("POST /api/ai/match/qualquer-id/audit/apply responde 404", async ({ request }) => {
    const resp = await request.post("/api/ai/match/qualquer-id/audit/apply");
    expect(resp.status()).toBe(404);
  });
  test("GET /api/ai/match/qualquer-id/analysis nao responde 404 (rota sobrevivente)", async ({ request }) => {
    const resp = await request.get("/api/ai/match/qualquer-id/analysis");
    expect(resp.status()).not.toBe(404);
  });
});
