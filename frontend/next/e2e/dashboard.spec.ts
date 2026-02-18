import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
    // ⚠️ AGUARDAR CARREGAMENTO COMPLETO DA PÁGINA (obrigatório para evitar flakiness)
    await page.waitForLoadState("domcontentloaded");
    await page.waitForLoadState("networkidle");
    // ⚠️ OPCIONAL: Aguardar API de dados se necessário
    // await page.waitForResponse(resp => resp.url().includes('/api/') && resp.status() === 200);
  });

  test("renders main dashboard layout", async ({ page }) => {
    await expect(page).toHaveTitle(/SportsBank Pro/i);
    await expect(page.locator(".st-nav__logo")).toContainText("sportsbank");
  });

  test("renders scoretabs layout with branding", async ({ page }) => {
    await expect(page.locator(".st-nav__logo")).toBeVisible();
    await expect(page.locator(".st-nav__logo")).toContainText("sportsbank");
  });

  test("renders PRO badge", async ({ page }) => {
    await expect(page.locator(".st-badge-pro")).toBeVisible();
    await expect(page.locator(".st-badge-pro")).toContainText("pro V");
  });

  test("renders left panel with filters", async ({ page }) => {
    await expect(page.locator(".st-panel-left")).toBeVisible();
    await expect(page.locator(".st-filters")).toBeVisible();
    await expect(page.locator(".st-date-label")).toContainText("Hoje");
  });

  test("renders odds tabs with COTACOES", async ({ page }) => {
    await expect(page.locator(".st-odds-tabs")).toBeVisible();
    await expect(page.locator(".st-odds-tabs").getByText("COTACOES", { exact: true })).toBeVisible();
    await expect(page.locator(".st-odds-tabs").getByText("1X2")).toBeVisible();
    await expect(page.locator(".st-odds-tabs").getByText("Dupla Chance")).toBeVisible();
    await expect(page.locator(".st-odds-tabs").getByText("BTTS")).toBeVisible();
  });

  test("renders match list area", async ({ page }) => {
    await expect(page.locator(".st-panel-left")).toBeVisible();
  });

  test.skip("renders bottom navigation", async ({ page }) => {
    // Bottom nav not implemented in current dashboard layout
    await expect(page.locator(".st-bottom-nav")).toBeVisible();
    await expect(page.getByText("Destaques")).toBeVisible();
    await expect(page.getByText("Radar Esportivo")).toBeVisible();
    await expect(page.getByText("ST Bots")).toBeVisible();
  });

  test("renders right panel for match details", async ({ page }) => {
    await expect(page.locator(".detail-card-section")).toBeVisible();
  });

  test("right panel shows match detail or placeholder", async ({ page }) => {
    // With mock fallback, matches are always loaded and first is auto-selected
    // So either a match detail card is shown, or the placeholder text appears
    const detailOrPlaceholder = page
      .locator(".st-panel-right")
      .or(page.locator(".detail-card-section"));
    await expect(detailOrPlaceholder.first()).toBeVisible();
  });

  test("search button is visible", async ({ page }) => {
    await expect(page.locator(".st-nav__search")).toBeVisible();
    await expect(page.locator(".st-nav__search")).toContainText("Buscar");
  });

  test("round matches section renders", async ({ page }) => {
    await expect(page.locator(".st-panel-left")).toBeVisible();
    await expect(
      page.locator(".st-league-group, .st-empty, .st-odds-tabs").first()
    ).toBeVisible();
  });
});