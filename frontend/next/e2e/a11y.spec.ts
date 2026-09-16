import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { stub } from "./helpers/stub";
for (const rota of ["/jogos", "/banca", "/jogos?dia=ontem", "/desempenho"]) {
  test(`axe sem violacoes serias em ${rota}`, async ({ page }) => {
    await stub(page);
    await page.goto(rota);

    // Wait for page to be fully hydrated before analyzing
    await page.waitForLoadState("networkidle");

    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(r.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
  });
}
