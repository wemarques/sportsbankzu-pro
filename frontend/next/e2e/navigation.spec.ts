import { test, expect } from "@playwright/test";

test.describe("Navigation & Theme", () => {
  test("theme toggle switches between light and dark mode", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator('button[aria-label="Alternar tema"]');
    await expect(toggle).toBeVisible();

    // Get initial theme
    const initialTheme = await page.locator("html").getAttribute("data-theme");

    // Click to toggle
    await toggle.click();
    const newTheme = await page.locator("html").getAttribute("data-theme");
    expect(newTheme).not.toBe(initialTheme);

    // Click again to toggle back
    await toggle.click();
    const restoredTheme = await page.locator("html").getAttribute("data-theme");
    expect(restoredTheme).toBe(initialTheme);
  });

  test("market tabs switch active state on click", async ({ page }) => {
    await page.goto("/");
    const nav = page.locator('nav[aria-label="Mercados"]');

    // Click BTTS tab
    await nav.getByText("BTTS").click();
    await expect(nav.getByText("BTTS")).toHaveClass(/text-primary/);

    // Click Gols tab
    await nav.getByText("Gols").click();
    await expect(nav.getByText("Gols")).toHaveClass(/text-primary/);
  });

  test("bottom navigation tabs switch on click", async ({ page }) => {
    await page.goto("/");
    const bottomNav = page.locator('nav[aria-label="Navegacao principal"]');

    await bottomNav.getByText("Radar Esportivo").click();
    await expect(bottomNav.getByText("Radar Esportivo")).toHaveClass(/text-primary/);

    await bottomNav.getByText("ST Bots").click();
    await expect(bottomNav.getByText("ST Bots")).toHaveClass(/text-primary/);
  });

  test("date navigation arrows change the date label", async ({ page }) => {
    await page.goto("/");

    // Initially shows "Hoje"
    await expect(page.getByText("Hoje")).toBeVisible();

    // Click next day
    await page.locator('button[aria-label="Proximo dia"]').click();

    // Should no longer show "Hoje" - should show a formatted date
    await expect(page.getByText("Hoje")).not.toBeVisible();
  });

  test("all main pages respond with 200", async ({ request }) => {
    const pages = ["/", "/dashboard", "/ai-audit", "/market-trends", "/performance-stats"];
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
