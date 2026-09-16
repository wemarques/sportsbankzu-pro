import { test, expect } from "@playwright/test";

test("/glossario#stake ancora no termo certo (#257)", async ({ page }) => {
  await page.goto("/glossario#stake");
  await expect(page.locator("#stake")).toBeInViewport();
  await expect(page.locator("#stake dt")).toHaveText("Stake");
});
