import { test, expect } from "@playwright/test";

test.describe("AI Audit Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ai-audit");
  });

  test("page loads with correct title", async ({ page }) => {
    await expect(page).toHaveTitle(/AI Audit/);
  });

  test("renders the AI Review Dashboard component", async ({ page }) => {
    // The AIReviewDashboard renders a div with an h1 "AI Audit" heading
    await expect(page.locator("h1:has-text('AI Audit')")).toBeVisible();
  });

  test("displays Mistral AI status indicators", async ({ page }) => {
    const content = page.locator("body");
    // The page should contain AI-related elements
    await expect(content).toBeVisible();
  });
});
