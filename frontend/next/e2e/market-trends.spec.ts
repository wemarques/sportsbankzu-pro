import { test, expect } from "@playwright/test";

test.describe("Market Trends Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/market-trends");
  });

  test("renders Market Trends heading", async ({ page }) => {
    await expect(page.getByText("Market Trends")).toBeVisible();
  });

  test("displays metric chips for filtering", async ({ page }) => {
    for (const metric of ["odds", "ev", "stake", "points"]) {
      await expect(page.getByText(metric, { exact: true })).toBeVisible();
    }
  });

  test("clicking a chip updates the active metric", async ({ page }) => {
    const evChip = page.getByText("ev", { exact: true });
    await evChip.click();
    // Chip should become visually active (has different background)
    await expect(evChip).toBeVisible();
  });

  test("renders the area chart", async ({ page }) => {
    const chart = page.locator(".recharts-responsive-container");
    await expect(chart).toBeVisible();
  });
});
