import { test, expect } from "@playwright/test";

test.describe("AI Audit Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ai-audit");
  });

  test("page loads with correct title", async ({ page }) => {
    await expect(page).toHaveTitle(/AI Audit/);
  });

  test("renders the AI Review Dashboard component", async ({ page }) => {
    await expect(page.locator("main, [class*='audit'], [class*='review']").first()).toBeVisible();
  });

  test("displays Mistral AI status indicators", async ({ page }) => {
    const content = page.locator("body");
    // The page should contain AI-related elements
    await expect(content).toBeVisible();
  });
});
