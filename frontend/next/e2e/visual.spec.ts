import { test, expect } from "@playwright/test";
import feed from "./fixtures/feed.json";
import { stub } from "./helpers/stub";

// #254-b — referencias de regressao visual (spec §7). Um jogo "vale" fixo
// (feed.matches[0]) alimenta as telas de painel/detalhe. Projetos
// visual-mobile/visual-desktop: local-only, ver REGISTRO #254-b (R1).
const idVale = feed.matches[0].id;

test.describe("regressao visual (#254-b)", () => {
  test("feed", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article").first()).toBeVisible();
    await expect(page).toHaveScreenshot("feed.png", { fullPage: true });
  });

  test("painel (desktop)", async ({ page }, info) => {
    test.skip(info.project.name !== "visual-desktop", "painel lateral so no desktop");
    await stub(page);
    await page.goto(`/jogos?jogo=${encodeURIComponent(idVale)}`);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeVisible();
    await expect(page).toHaveScreenshot("painel.png", { fullPage: true });
  });

  test("detalhe", async ({ page }) => {
    await stub(page);
    await page.goto(`/jogos/${encodeURIComponent(idVale)}`);
    await expect(page.getByRole("heading", { name: /Todos os mercados avaliados/ })).toBeVisible();
    await expect(page).toHaveScreenshot("detalhe.png", { fullPage: true });
  });

  test("banca indefinida", async ({ page }) => {
    await page.goto("/banca");
    await expect(page.getByLabel("Sua banca")).toBeVisible();
    await expect(page).toHaveScreenshot("banca-indefinida.png", { fullPage: true });
  });

  test("banca definida", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("sportsbankzu-bankroll", "1000"));
    await page.goto("/banca");
    await expect(page.getByLabel("Sua banca")).toBeVisible();
    await expect(page).toHaveScreenshot("banca-definida.png", { fullPage: true });
  });
});
