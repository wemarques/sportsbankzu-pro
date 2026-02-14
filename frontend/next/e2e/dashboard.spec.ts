import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
    // ⚠️ AGUARDAR CARREGAMENTO COMPLETO DA PÁGINA
    await page.waitForLoadState("networkidle");
    // ⚠️ OPCIONAL: Aguardar API de dados se necessário
    // await page.waitForResponse(resp => resp.url().includes('/api/') && resp.status() === 200);
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

<<<<<<< HEAD
  test("displays stats cards with numeric values", async ({ page }) => {
    // Foca na grid de cards específica que tem 4 colunas (onde estão os stats principais)
    // para evitar ambiguidade com outras grids na página
    const statsGrid = page.locator("div.grid.grid-cols-1.md\\:grid-cols-4");
    
    // Verifica se a grid específica está visível
    await expect(statsGrid).toBeVisible();
    
    // ⚠️ Correção: Verificar texto dentro da grid, não a grid inteira
    await expect(statsGrid.getByText(/Jogos|Analysed Matches/i)).toBeVisible();
    await expect(statsGrid.getByText(/Value Bets/i)).toBeVisible();
=======
  test("renders match list area", async ({ page }) => {
    await expect(page.locator(".st-match-list")).toBeVisible();
>>>>>>> 0c00c9ab08668fbab72dd0bf90ecc3d63ffd35d0
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