import { test, expect } from "@playwright/test";
import { stub } from "./helpers/stub";

// #262 — cabecalho fixo em todas as rotas, inclusive hero/login/register; data BRT; marca inteira.
for (const rota of ["/", "/jogos", "/banca", "/desempenho", "/glossario", "/login", "/register"]) {
  test(`banner com a marca em ${rota}`, async ({ page }) => {
    await stub(page);
    await page.goto(rota);
    const banner = page.getByRole("banner");
    await expect(banner).toBeVisible();
    // #262 fix round 1 — o monograma volta para DENTRO do <Link> (spec §1: nome "precedido
    // do monograma", ambos clicaveis); toHaveText no link inteiro pegaria "SBZ" + o nome
    // (mesma causa do ajuste no teste unitario). Nome acessivel + span do wordmark, nao o
    // link inteiro.
    const link = banner.getByRole("link", { name: "sportsbankzu, ir para os jogos" });
    await expect(link).toHaveAccessibleName("sportsbankzu, ir para os jogos");
    await expect(link.locator("span").first()).toHaveText("sportsbankzu");
    const box = await banner.boundingBox();
    expect(box?.y).toBe(0); expect(Math.round(box?.height ?? 0)).toBe(56);
  });
}
test("a data vem por extenso em BRT e nao ha segundo 'sportsbankzu' na pagina do hero", async ({ page, isMobile }) => {
  test.skip(isMobile, "data oculta no celular");
  await stub(page);
  await page.goto("/");
  // sem ancoras (^$): o banner tem o monograma decorativo (textContent "SBZ", #262) e o
  // link "sportsbankzu" antes da data — toContainText com regex ancorada exige que o
  // TEXTO INTEIRO do elemento bata, o que a data sozinha nunca cumpre com marca no mesmo
  // header; contains genuino e o que o nome do teste promete: a data aparece, formatada.
  await expect(page.getByRole("banner")).toContainText(/(domingo|segunda|terça|quarta|quinta|sexta|sábado), \d{1,2} de [a-zç]+/);
  expect(await page.getByText("sportsbankzu", { exact: true }).count()).toBe(1);
});
test("painel de detalhe fica abaixo do cabecalho ao rolar (1440x700)", async ({ page, isMobile }) => {
  // WebKit mobile nao suporta mouse.wheel; o viewport 1440x700 e desktop por definicao —
  // mesmo padrao da decisao do controller para o teste da data (#262, Task 3).
  test.skip(isMobile, "mouse.wheel nao suportado no WebKit mobile; teste e desktop (1440x700)");
  await page.setViewportSize({ width: 1440, height: 700 });
  await stub(page, { feed: "multi" });
  await page.goto("/jogos");
  await page.locator("article h2 a").first().click();
  await page.mouse.wheel(0, 600);
  const box = await page.getByRole("complementary", { name: "detalhe do jogo" }).boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(56);
});

test.describe("carimbo de leitura e da rota, nao do cabecalho (#262 §1)", () => {
  for (const rota of ["/jogos", "/desempenho"]) {
    test(`presente em ${rota}`, async ({ page }) => {
      await stub(page); await page.goto(rota);
      await expect(page.locator("[data-carimbo]")).toHaveText(/^lido às \d{2}:\d{2}$/);
      await expect(page.getByRole("banner").locator("[data-carimbo]")).toHaveCount(0);
    });
  }
  for (const rota of ["/banca", "/glossario", "/"]) {
    test(`ausente em ${rota}`, async ({ page }) => {
      await stub(page); await page.goto(rota);
      await expect(page.locator("[data-carimbo]")).toHaveCount(0);
    });
  }
});
