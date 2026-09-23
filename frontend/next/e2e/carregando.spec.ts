import { test, expect } from "@playwright/test";
import feed from "./fixtures/feed.json";
import { stub } from "./helpers/stub";

// #262 §3 — lotes chegam em tempos diferentes; "Nenhum jogo" nunca antes do ultimo lote.
async function feedPorCamadas(page: import("@playwright/test").Page) {
  await stub(page, { vazio: true });
  await page.route("**/api/matches/fetch**", async (route) => {
    const u = new URL(route.request().url()); const liga = u.searchParams.get("leagues") ?? "";
    const espera = liga === "championship" ? 1000 : liga === "la-liga" ? 3000 : 5000;
    await new Promise((r) => setTimeout(r, espera));
    const corpo = liga === "championship" ? { matches: feed.matches.filter((m) => m.leagueId === "championship") } : { matches: [] };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(corpo) });
  });
}

test("cards do primeiro lote aparecem antes dos demais; progresso conta; vazio so no fim", async ({ page }) => {
  await feedPorCamadas(page);
  await page.goto("/jogos");
  await expect(page.locator("[data-esqueleto]")).toBeVisible();
  await expect(page.locator("[data-progresso]")).toContainText(/buscando os jogos de hoje: \d+ de \d+ ligas lidas/, { timeout: 2500 });
  await expect(page.locator("article").first()).toBeVisible({ timeout: 2500 });
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  await page.waitForTimeout(1500);
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  // #262 — 13 ligas ativas, MAX_CONCURRENT=4: as 11 ligas de 5s formam 3 ondas
  // sob o limite de concorrencia (~15-16s no pior caso); 8s (valor do brief)
  // e curto demais para esta topologia real — medido, nao suposto.
  await expect(page.locator("[data-esqueleto]")).toHaveCount(0, { timeout: 20000 });
});
test("todos os lotes vazios: 'Nenhum jogo' so depois do ultimo lote", async ({ page }) => {
  await stub(page, { vazio: true });
  await page.route("**/api/matches/fetch**", async (route) => { await new Promise((r) => setTimeout(r, 2000)); await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }); });
  await page.goto("/jogos");
  await expect(page.locator("[data-esqueleto]")).toBeVisible();
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toBeVisible({ timeout: 15000 });
  await expect(page.locator("[data-esqueleto]")).toHaveCount(0);
});
test("prefers-reduced-motion desliga a animacao do esqueleto", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await feedPorCamadas(page);
  await page.goto("/jogos");
  const nome = await page.locator(".sb-esqueleto").first().evaluate((el) => getComputedStyle(el).animationName);
  expect(nome).toBe("none");
});
