import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test("redirects to dashboard", async ({ page }) => {
    await page.goto("/");
    await page.waitForURL("**/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("dashboard loads with scoretabs layout after redirect", async ({ page }) => {
    await page.goto("/");
    await page.waitForURL("**/dashboard");
    await expect(page.locator(".st-nav__logo")).toBeVisible();
    await expect(page.locator(".st-panel-left")).toBeVisible();
    await expect(page.locator(".detail-card-section")).toBeVisible();
  });
});
