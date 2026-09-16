import { test, expect } from "@playwright/test";
import ledgerDia from "./fixtures/ledger-dia.json";

test.describe("/jogos?dia=ontem (#256, spec §4.2)", () => {
  test("talao com desfecho mostra a faixa de resultado; jogo so-NEUTRO cai em direcao", async ({ page }) => {
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerDia) }));
    await page.goto("/jogos?dia=ontem");
    await expect(page.locator("article[data-estado='ontem']")).toHaveCount(1);
    await expect(page.getByText("✓ fechou com 3 gols")).toBeVisible();
    await expect(page.locator("article[data-estado='direcao']")).toHaveCount(1);
  });
  test("ledger fora do ar: mensagem, sem recomputar via /fixtures", async ({ page }) => {
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ ok: false, error: { kind: "BACKEND_ERROR", message: "x" } }) }));
    let chamouFixtures = false;
    await page.route("**/api/matches/fetch**", (route) => { chamouFixtures = true; route.continue(); });
    await page.goto("/jogos?dia=ontem");
    await expect(page.getByText("Os jogos de ontem não carregaram.")).toBeVisible();
    expect(chamouFixtures).toBe(false);
  });
});
