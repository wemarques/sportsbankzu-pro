import { test, expect } from "@playwright/test";
import { stub } from "./helpers/stub";
import feedHojeEncerrado from "./fixtures/feed-hoje-encerrado.json";
import ledgerDiaHoje from "./fixtures/ledger-dia-hoje.json";

/**
 * #261 — aba Hoje, jogo encerrado: o talão vem do feed (`/api/matches/fetch`);
 * o desfecho vem do `/ledger/dia` do próprio dia, casado por liga + kickoff +
 * times (nunca por id cru — spec 2026-09-15, emenda #261 §4.2). Os 3 casos
 * de aceite do brief. Fixtures em `e2e/fixtures/feed-hoje-encerrado.README.md`.
 */
test.describe("/jogos aba Hoje, jogo encerrado mostra o desfecho do ledger (#261)", () => {
  test("desfecho no ledger para o mercado do talao: card mostra a faixa", async ({ page }) => {
    await stub(page);
    await page.route("**/api/matches/fetch**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(feedHojeEncerrado) }));
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerDiaHoje) }));
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado='ontem']")).toHaveCount(1);
    await expect(page.getByText("✓ fechou com 8 escanteios")).toBeVisible();
    await expect(page.getByText("resultado ainda não conferido")).toHaveCount(0);
  });

  test("ledger sem desfecho para este jogo: mensagem de pendente", async ({ page }) => {
    await stub(page); // fallback de /api/ledger/dia em stub.ts: picks sempre []
    await page.route("**/api/matches/fetch**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(feedHojeEncerrado) }));
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado='ontem_sem_desfecho']")).toHaveCount(1);
    await expect(page.getByText("resultado ainda não conferido")).toBeVisible();
  });

  test("ledger fora do ar (503): mesma mensagem, sem erro na tela", async ({ page }) => {
    await stub(page);
    await page.route("**/api/matches/fetch**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(feedHojeEncerrado) }));
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ ok: false, error: { kind: "BACKEND_ERROR", message: "x" } }) }));
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado='ontem_sem_desfecho']")).toHaveCount(1);
    await expect(page.getByText("resultado ainda não conferido")).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0); // sem banner de erro do feed (o feed carregou; so o ledger falhou)
  });

  test("sem jogo encerrado no feed: direcao/nada intocados, ledger de hoje nem e chamado", async ({ page }) => {
    let chamouLedgerDia = false;
    await stub(page); // feed.json padrao: 1 "direcao" e 1 "nada", nenhum "finished"/>3h
    await page.route("**/api/ledger/dia**", (route) => {
      chamouLedgerDia = true;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, data: "1970-01-01", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 }, semana: {}, mes: {} }) });
    });
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado='direcao']")).toHaveCount(1);
    await expect(page.locator("article[data-estado='nada']")).toHaveCount(1);
    expect(chamouLedgerDia).toBe(false);
  });
});
