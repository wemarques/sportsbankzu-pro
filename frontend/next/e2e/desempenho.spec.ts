import { test, expect } from "@playwright/test";
import agregado from "./fixtures/ledger-agregado.json";

const DESEMPENHO_RETORNO_NA_BANCA = "seguindo o stake sugerido, na sua banca atual";

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
    // #257: sem banca, a linha de dinheiro pede a banca (decisão (a) do dono); a frase "indisponível" saiu de Painel
    await expect(page.getByText("defina sua banca para ver o retorno em dinheiro")).toBeVisible();
    await expect(page.getByText("Over/Under")).toBeVisible();
    await expect(page.getByRole("img", { name: /Calibração/ })).toBeVisible();
    await expect(page.getByText(/\d{2}\/\d{2}–hoje/)).toBeVisible();
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
  test("retorno retroativo com banca definida", async ({ page, context }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    // Mesmos dois picks e mesma conta do Step 8 (retornoRetroativo.test.ts):
    // A: prob 0.55, odd 2.2, SAFE, outcome 1, banca 1000 -> stake 43.75, P&L +52.5
    // B: prob 0.52, odd 1.9, NEUTRO_QUALIFICADO, outcome 0, banca 1000 -> stake 0, P&L 0
    // total valor = 52.5; pctBanca = 52.5/1000 = 0.0525 -> fmtPct = 5; fmtReais(52.5) = "R$ 52,50"
    await page.route("**/api/ledger/picks**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        ok: true, periodo: "30d", familia: null, liga: null,
        picks: [
          { match_id: "a", league_id: "mls", kickoff_utc: null, familia: "Over/Under", market: "Over/Under",
            selection: "Over 2.5", published_prob: 0.55, fair_odd: 1.82, book_odd: 2.2, classification: "SAFE", outcome: 1, detail: null },
          { match_id: "b", league_id: "mls", kickoff_utc: null, familia: "Over/Under", market: "Over/Under",
            selection: "Over 1.5", published_prob: 0.52, fair_odd: 1.92, book_odd: 1.9, classification: "NEUTRO_QUALIFICADO", outcome: 0, detail: null },
        ],
      }) }));
    await context.addInitScript(() => window.localStorage.setItem("sportsbankzu-bankroll", "1000"));
    await page.goto("/desempenho");
    await expect(page.getByText("R$ 52,50")).toBeVisible();
    // #257 fix round 1 — /5%/ colidia com celulas reais de TabelaSegmentos (ex.: "45%");
    // frase completa e unica.
    await expect(page.getByText("R$ 52,50 (5%) — seguindo o stake sugerido, na sua banca atual")).toBeVisible();
    await expect(page.getByText(DESEMPENHO_RETORNO_NA_BANCA)).toBeVisible();
  });
  test("sem banca definida: link honesto para /banca, nenhum numero inventado", async ({ page, context }) => {
    await context.clearCookies();
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    await page.route("**/api/ledger/picks**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, periodo: "30d", familia: null, liga: null, picks: [] }) }));
    await page.goto("/desempenho");
    await expect(page.getByRole("link", { name: "definir banca" })).toBeVisible();
  });
});
