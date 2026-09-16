import { test, expect, type Page } from "@playwright/test";
import feed from "./fixtures/feed.json";

async function stub(page: Page, opts: { vazio?: boolean; erro?: boolean } = {}) {
  await page.route("**/api/matches/fetch**", (route) => {
    if (opts.erro) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ matches: [], _error: { kind: "TIMEOUT", message: "x" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(opts.vazio ? { matches: [] } : feed) });
  });
  await page.route("**/api/matches/live**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
  await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
}

test.describe("/jogos (#254-b)", () => {
  test("um card por jogo, cada um no seu estado", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
    for (const e of ["vale", "direcao", "nada", "em_jogo"]) await expect(page.locator(`article[data-estado='${e}']`)).toHaveCount(1);
    await expect(page.getByRole("region", { name: "pick recomendado" })).toHaveCount(2); // vale + em_jogo
  });
  test("tabs de dia e chips de liga escrevem na URL", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await page.getByRole("tab", { name: "Amanhã" }).click();
    await expect(page).toHaveURL(/dia=amanha/);
    await page.getByRole("button", { name: "MLS" }).click();
    await expect(page).toHaveURL(/liga=mls/);
    await expect(page.locator("article[data-estado]")).toHaveCount(await page.locator("article[data-liga='mls']").count());
  });
  test("dia sem jogos: frase e link para o proximo dia", async ({ page }) => {
    await stub(page, { vazio: true });
    await page.goto("/jogos");
    await expect(page.getByText(/Nenhum jogo nas ligas escolhidas/)).toBeVisible();
    await expect(page.getByRole("link", { name: /próximo dia/ })).toBeVisible();
  });
  test("backend fora: mensagem, tentar de novo, e o ultimo feed fica com carimbo", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
    await stub(page, { erro: true });
    await page.getByRole("tab", { name: "Amanhã" }).click();
    await expect(page.getByText("Os jogos de hoje não carregaram.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar de novo" })).toBeVisible();
    await expect(page.getByText(/^de \d\d:\d\d$/)).toBeVisible();
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
  });
  test("desktop: ?jogo= abre o painel e voltar fecha", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "painel lateral so no desktop");
    await stub(page);
    await page.goto("/jogos");
    await page.locator("article[data-estado='vale'] h2 a").click();
    await expect(page).toHaveURL(/jogo=/);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeVisible();
    await page.goBack();
    await expect(page).not.toHaveURL(/jogo=/);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeHidden();
  });
  test("mobile: tocar no card navega para /jogos/[id]", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile");
    await stub(page);
    await page.goto("/jogos");
    await page.locator("article[data-estado='vale'] h2 a").click();
    await expect(page).toHaveURL(/\/jogos\/[^?]+$/);
  });
  test("acessibilidade basica: foco visivel no primeiro link", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article").first()).toBeVisible();
    await page.keyboard.press("Tab");
    const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineWidth);
    expect(outline).not.toBe("0px");
  });
});
