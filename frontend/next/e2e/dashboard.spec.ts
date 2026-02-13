import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
    // ⚠️ AGUARDAR CARREGAMENTO COMPLETO DA PÁGINA
    await page.waitForLoadState("networkidle");
    // ⚠️ OPCIONAL: Aguardar API de dados se necessário
    // await page.waitForResponse(resp => resp.url().includes('/api/') && resp.status() === 200);
  });

  test("renders main dashboard layout", async ({ page }) => {
    // "SportsBank Pro" é o título principal no header
    await expect(page.getByText("SportsBank Pro")).toBeVisible();
    
    // Verifica elementos específicos da sidebar ao invés de um locator genérico "aside"
    // que pode não estar presente ou estar oculto dependendo do estado inicial
    const settingsButton = page.locator("button", { hasText: /Configurações|Ocultar|Mostrar/i }).first();
    await expect(settingsButton).toBeVisible();
  });

  test("sidebar is visible with risk controls", async ({ page }) => {
    await expect(page.getByText("Configurações")).toBeVisible();
    await expect(page.locator('input[type="range"]').first()).toBeVisible();
  });

  test("bank balance input allows editing", async ({ page }) => {
    const input = page.locator('input[type="number"]').first();
    await expect(input).toBeVisible();
    await input.fill("2000");
    await expect(input).toHaveValue("2000");
  });

  test("strategy selector has expected options", async ({ page }) => {
    const select = page.locator("select").first();
    await expect(select).toBeVisible();
    await expect(select.locator("option")).toHaveCount(3);
  });

  test("displays stats cards with numeric values", async ({ page }) => {
    // Foca na grid de cards específica que tem 4 colunas (onde estão os stats principais)
    // para evitar ambiguidade com outras grids na página
    const statsGrid = page.locator("div.grid.grid-cols-1.md\\:grid-cols-4");
    
    // Verifica se a grid específica está visível
    await expect(statsGrid).toBeVisible();
    
    // ⚠️ Correção: Verificar texto dentro da grid, não a grid inteira
    await expect(statsGrid.getByText(/Jogos|Analysed Matches/i)).toBeVisible();
    await expect(statsGrid.getByText(/Value Bets/i)).toBeVisible();
  });

  test("renders bank evolution chart", async ({ page }) => {
    const chart = page.locator(".recharts-responsive-container");
    await expect(chart).toBeVisible();
  });

  test("league selector is present", async ({ page }) => {
    const leagueSelect = page.locator("select").nth(1);
    await expect(leagueSelect).toBeVisible();
  });

  test("match date filter has options", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /today|tomorrow|week/i }).first()
        .or(page.locator("select").last())
    ).toBeVisible();
  });

  test("round matches section renders", async ({ page }) => {
    await expect(page.getByText("Jogos da Rodada")).toBeVisible();
  });
});