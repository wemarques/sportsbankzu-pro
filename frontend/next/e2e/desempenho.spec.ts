import { test, expect } from "@playwright/test";
import agregado from "./fixtures/ledger-agregado.json";

// Fixture REAL (#256, R1) — aritmética em e2e/fixtures/ledger-agregado.README.md.
// 42 acertos / 78 resolvidos = 0,538461... -> Math.round(53.8461) = 54.
// Over/Under: 25 / 37 = 0,675675... -> 68%. mls: 20 / 37 = 0,540540... -> 54%.
// Calibração — maior desvio entre os 5 buckets com n>0: bucket (0.9042, 0.5, n=2),
// desvio 0,4042 (o maior) -> "quando o painel disse 90 ... aconteceu 50 em cada 100".
test.describe("/desempenho (#256, spec §5)", () => {
  test("acerto, retorno honesto (null), por familia, calibracao, por liga", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    await page.goto("/desempenho");
    await expect(page.getByText("54 de cada 100 picks fechados")).toBeVisible(); // 42 acertos / 78 resolvidos
    await expect(page.getByText(/ainda não/)).toBeVisible(); // retorno null, sem numero inventado
    await expect(page.getByText("Over/Under")).toBeVisible();
    await expect(page.getByRole("img", { name: /Calibração/ })).toBeVisible();
    await expect(page.getByText(/17\/08–hoje/)).toBeVisible();
  });
  test("filtro de periodo escreve na URL", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    await page.goto("/desempenho");
    await page.getByRole("tab", { name: "7 dias" }).click();
    await expect(page).toHaveURL(/periodo=7d/);
  });
  test("sem picks fechados no periodo: mensagem e link para periodo maior", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...agregado, acerto: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 }, buckets: null, brier: null, amostra_curta: true, por_familia: {}, por_liga: {} }) }));
    await page.goto("/desempenho?periodo=7d");
    await expect(page.getByText("sem picks fechados neste período")).toBeVisible();
    await expect(page.getByRole("link", { name: /30 dias|temporada/ })).toBeVisible();
  });
});
