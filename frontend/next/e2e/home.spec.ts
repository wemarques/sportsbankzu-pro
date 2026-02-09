import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the header with SportsBank Pro branding", async ({ page }) => {
    await expect(page.locator("header")).toContainText("SportsBank Pro");
  });

  test("shows bank balance input with default value", async ({ page }) => {
    const input = page.locator('header input[type="number"]');
    await expect(input).toBeVisible();
    await expect(input).toHaveValue("80");
  });

  test("updates bank balance when user types a new value", async ({ page }) => {
    const input = page.locator('header input[type="number"]');
    await input.fill("500");
    await expect(input).toHaveValue("500");
  });

  test("displays the AI Audit link in the header", async ({ page }) => {
    const link = page.locator('a[href="/ai-audit"]');
    await expect(link).toBeVisible();
    await expect(link).toContainText("AI Audit");
  });

  test("renders risk configuration sidebar", async ({ page }) => {
    await expect(page.getByText("Configurações de Risco")).toBeVisible();
  });

  test("kelly fraction slider updates displayed value", async ({ page }) => {
    const slider = page.locator('aside input[type="range"]');
    await slider.fill("50");
    await expect(page.locator("aside")).toContainText("50%");
  });

  test("strategy dropdown has all options", async ({ page }) => {
    const select = page.locator("aside select");
    await expect(select).toBeVisible();
    const options = select.locator("option");
    await expect(options).toHaveCount(3);
    await expect(options.nth(0)).toHaveText("Conservador");
    await expect(options.nth(1)).toHaveText("Moderado");
    await expect(options.nth(2)).toHaveText("Agressivo");
  });

  test("displays daily and per-bet limits", async ({ page }) => {
    await expect(page.locator("aside")).toContainText("Limite diário");
    await expect(page.locator("aside")).toContainText("Limite por aposta");
  });

  test("renders stats grid with key metrics", async ({ page }) => {
    await expect(page.getByText("Jogos analisados")).toBeVisible();
    // Usando um seletor mais específico para evitar conflito com múltiplos elementos "Value bets"
    // ou garantindo que pegamos o primeiro visível
    const valueBetsLabel = page.getByText("Value bets").first();
    await expect(valueBetsLabel).toBeVisible();
  });

  test("renders value bets table with match data", async ({ page }) => {
    await expect(page.getByText("Aston Villa vs Bournemouth")).toBeVisible();
    await expect(page.getByText("Crystal Palace vs Brighton")).toBeVisible();
    await expect(page.getByText("Nottingham Forest vs Leeds")).toBeVisible();
  });

  test("renders bank evolution chart", async ({ page }) => {
    await expect(page.getByText("Evolução da Banca")).toBeVisible();
    const canvas = page.locator("canvas");
    await expect(canvas).toBeVisible();
  });

  test("stake fixed button triggers alert", async ({ page }) => {
    page.on("dialog", (dialog) => dialog.accept());
    await page.getByText("Aplicar Stake Fixo (2%)").click();
  });
});
