import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { stub } from "./helpers/stub";
for (const rota of ["/jogos", "/banca"]) {
  test(`axe sem violacoes serias em ${rota}`, async ({ page }) => {
    await stub(page);
    await page.goto(rota);
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(r.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
  });
}
