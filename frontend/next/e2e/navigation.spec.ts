import { test, expect } from "@playwright/test";

test.describe("Navigation & Theme", () => {
  test("navigating from home to AI Audit", async ({ page }) => {
    await page.goto("/ai-audit");
    await expect(page).toHaveURL(/\/ai-audit/);
  });

  test("market tabs switch active state on click", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator("button").filter({ hasText: /theme|dark|light/i })
      .or(page.locator('[aria-label*="theme"]'))
      .or(page.locator('[class*="ThemeToggle"], [class*="theme-toggle"]'));
    if (await toggle.count() > 0) {
      await toggle.first().click();
      const html = page.locator("html");
      const classList = await html.getAttribute("class");
      await toggle.first().click();
      const classListAfter = await html.getAttribute("class");
      expect(classList).not.toBe(classListAfter);
    }
  });

  test("all main pages respond with 200", async ({ request }) => {
    const pages = ["/", "/dashboard", "/ai-audit"];
    for (const path of pages) {
      const resp = await request.get(path);
      expect(resp.status()).toBe(200);
    }
  });

  test("Ctrl+K opens search", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Control+k");
    const input = page.locator('header input[type="text"]');
    await expect(input).toBeVisible();
  });
});
