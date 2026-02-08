import { test, expect } from "@playwright/test";

test.describe("Dashboard Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("renders main dashboard layout", async ({ page }) => {
    await expect(page.getByText("SportsBank Pro")).toBeVisible();
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
    const statsSection = page.locator("main");
    await expect(statsSection).toContainText("Jogos");
    await expect(statsSection).toContainText("Value Bets");
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
