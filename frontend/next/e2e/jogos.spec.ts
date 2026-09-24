import { test, expect } from "@playwright/test";
import feed from "./fixtures/feed.json";
import { stub } from "./helpers/stub";

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
    await page.getByRole("button", { name: "Championship" }).click();
    await expect(page).toHaveURL(/liga=championship/);
    await expect(page.locator("div[data-liga='championship'] article")).toHaveCount(2);
    await expect(page.locator("article[data-estado]")).toHaveCount(2);
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
    // #256: a mensagem segue a aba ativa (antes dizia "hoje" em qualquer aba)
    await expect(page.getByText("Os jogos de amanhã não carregaram.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar de novo" })).toBeVisible();
    await expect(page.locator("[data-carimbo]")).toHaveText(/^lido às \d\d:\d\d$/);
    await expect(page.locator("article[data-estado]")).toHaveCount(4, { timeout: 15000 });
  });
  test("desktop: ?jogo= abre o painel e voltar fecha", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "painel lateral so no desktop");
    await stub(page);
    await page.goto("/jogos");
    await page.locator("article[data-estado='vale'] h2 a").click();
    await expect(page).toHaveURL(/jogo=/);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeVisible();
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeFocused();
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
  test("/jogos/[id] inexistente: 'jogo não encontrado' + link", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos/nao-existe");
    await expect(page.getByText("jogo não encontrado")).toBeVisible();
    await expect(page.getByRole("link", { name: "ver os jogos de hoje" })).toHaveAttribute("href", "/jogos");
  });
  test("Mistral indisponivel: a secao some inteira", async ({ page }) => {
    await stub(page);
    await page.route("**/api/ai/match/**", (route) => route.fulfill({ status: 503, body: "{}" }));
    const id = encodeURIComponent(feed.matches[0].id);
    await page.goto(`/jogos/${id}`);
    await expect(page.getByRole("heading", { name: /Todos os mercados avaliados/ })).toBeVisible();
    await expect(page.getByText("Como o modelo vê o jogo")).toHaveCount(0);
  });
  test("numeros alinham pela virgula: 1,67 e 1,75 tem a mesma largura", async ({ page }) => {
    await stub(page); await page.goto("/jogos");
    const w = await page.evaluate(() => {
      const s = (t: string) => { const el = document.createElement("span"); el.className = "tnum"; el.style.font = getComputedStyle(document.body).font; el.textContent = t; document.body.append(el); const r = el.getBoundingClientRect().width; el.remove(); return r; };
      return [s("1,67"), s("1,75")];
    });
    expect(Math.abs(w[0] - w[1])).toBeLessThan(0.5);
  });
});
