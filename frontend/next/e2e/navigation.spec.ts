import { test, expect } from "@playwright/test";

test.describe("Navigation & Theme", () => {
  test("navigating from home to AI Audit", async ({ page }) => {
    await page.goto("/");
    const link = page.locator('a[href="/ai-audit"]');
    await expect(link).toBeVisible({ timeout: 10000 });
    await expect(link).toHaveAttribute("href", "/ai-audit");
    await Promise.all([
      page.waitForURL(/\/ai-audit/, { timeout: 15000 }),
      link.click(),
    ]);
  });

  test("theme toggle switches between light and dark mode", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator("button").filter({ hasText: /theme|dark|light/i })
      .or(page.locator('[aria-label*="theme"]'))
      .or(page.locator('[class*="ThemeToggle"], [class*="theme-toggle"]'));
    if (await toggle.count() > 0) {
      await toggle.first().click();
      // Verify the theme class changed on html or body
      const html = page.locator("html");
      const classList = await html.getAttribute("class");
      // Click again to toggle back
      await toggle.first().click();
      const classListAfter = await html.getAttribute("class");
      expect(classList).not.toBe(classListAfter);
    }
  });

  test("all main pages respond with 200", async ({ request }) => {
    const pages = ["/", "/dashboard", "/ai-audit", "/market-trends", "/performance-stats"];
    for (const path of pages) {
      const resp = await request.get(path);
      expect(resp.status()).toBe(200);
    }
  });
});
