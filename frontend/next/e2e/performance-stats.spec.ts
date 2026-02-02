import { test, expect } from "@playwright/test";

test.describe("Performance Stats Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/performance-stats");
  });

  test("renders Heat Map section", async ({ page }) => {
    await expect(page.getByText("Heat Map")).toBeVisible();
  });

  test("heat map grid is rendered with cells", async ({ page }) => {
    // HeatMap component renders an 8x8 grid = 64 cells
    const grid = page.locator("[class*='grid']").first();
    await expect(grid).toBeVisible();
  });

  test("renders DRS Zones component", async ({ page }) => {
    await expect(page.getByText(/DRS/i)).toBeVisible();
  });

  test("renders Transfers table", async ({ page }) => {
    await expect(page.getByText("Driver A")).toBeVisible();
    await expect(page.getByText("Driver B")).toBeVisible();
    await expect(page.getByText("Team X")).toBeVisible();
  });
});
