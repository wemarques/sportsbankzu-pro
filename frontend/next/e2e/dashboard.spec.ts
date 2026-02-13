import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("renders scoretabs layout with branding", async ({ page }) => {
    await expect(page.locator(".st-nav__logo")).toBeVisible();
    await expect(page.locator(".st-nav__logo")).toContainText("sportsbank");
  });

  test("renders PRO badge", async ({ page }) => {
    await expect(page.locator(".st-badge-pro")).toBeVisible();
    await expect(page.locator(".st-badge-pro")).toContainText("PRO");
  });

  test("renders left panel with filters", async ({ page }) => {
    await expect(page.locator(".st-panel-left")).toBeVisible();
    await expect(page.locator(".st-filters")).toBeVisible();
    await expect(page.locator(".st-date-label")).toContainText("Hoje");
  });

  test("renders odds tabs with COTACOES", async ({ page }) => {
    await expect(page.locator(".st-odds-tabs")).toBeVisible();
    await expect(page.getByText("COTACOES")).toBeVisible();
    await expect(page.getByText("1X2")).toBeVisible();
    await expect(page.getByText("Dupla Chance")).toBeVisible();
    await expect(page.getByText("BTTS")).toBeVisible();
  });

  test("renders match list area", async ({ page }) => {
    await expect(page.locator(".st-match-list")).toBeVisible();
  });

  test("renders bottom navigation", async ({ page }) => {
    await expect(page.locator(".st-bottom-nav")).toBeVisible();
    await expect(page.getByText("Destaques")).toBeVisible();
    await expect(page.getByText("Radar Esportivo")).toBeVisible();
    await expect(page.getByText("ST Bots")).toBeVisible();
  });

  test("renders right panel for match details", async ({ page }) => {
    await expect(page.locator(".st-panel-right")).toBeVisible();
  });

  test("right panel shows placeholder when no match selected", async ({ page }) => {
    await expect(page.getByText("Selecione um jogo para ver os detalhes")).toBeVisible();
  });

  test("search button is visible", async ({ page }) => {
    await expect(page.locator(".st-nav__search")).toBeVisible();
    await expect(page.locator(".st-nav__search")).toContainText("Buscar");
  });
});
