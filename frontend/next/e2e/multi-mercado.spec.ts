import { test, expect } from "@playwright/test";
import feed from "./fixtures/feed.json";
import ledgerDia from "./fixtures/ledger-dia.json";
import { stub } from "./helpers/stub";

/**
 * Task 32-bis (#257) — "dois valem, um talao" (spec §4.1/§4.3) de ponta a ponta.
 * Fixture: feed.matches[4], copia verbatim de
 * tests/fixtures/fixtures.2026-09-15.v1.json ("la-liga-Levante UD-Athletic
 * Club Bilbao-1789587000.0" — ver e2e/fixtures/README.md para a conta e o
 * desvio de datetime).
 *
 * N "avaliados" (jogoView.ts toJogoView): picks = mercados.map(toPick).filter =
 * 3 (Cartoes Under 4.5 SAFE edge .1096, BTTS - SIM NEUTRO_QUALIFICADO edge
 * .0422, Over 2.5 gols NEUTRO edge .0796) + recusados =
 * stats.rejected_insights.map(toPickRecusado).filter = 12 (todos com
 * deflated_prob em 0-100, nenhum 0/100 -> nenhum descartado) = 15 no total.
 * totalValem = picks vale (SAFE|NEUTRO_QUALIFICADO) = 2. Confirmado por
 * script node reproduzindo toPick/toPickRecusado/escolherTalao contra o
 * fixture final (task report).
 */
const jogo = feed.matches[4];
const id = jogo.id;
const N_AVALIADOS = 15;
const N_VALEM = 2;
const TALAO_ROTULO = "Cartões Under 4.5"; // fmtMercado("Cartoes Under 4.5")
const SEGUNDO_ROTULO = "BTTS — SIM"; // fmtMercado no-op (sem "Cartoes"/"Cartao")

test.describe("multi-mercado — dois valem, um talao (#257)", () => {
  test("card do Levante: talao, segundo pick sem botao, linha de avaliados", async ({ page }, info) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article").first()).toBeVisible();

    // feed.json ja tinha OUTRO "Levante UD x Athletic Club Bilbao" (matches[2],
    // estado "nada", mercados: [] — data distinta, ver README). So o nosso
    // card mostra o talao "Cartoes Under 4.5"; usa-lo para desambiguar.
    const card = page.locator("article").filter({ hasText: TALAO_ROTULO });
    await expect(card).toHaveCount(1);

    // Talao = heading h3 dentro da region "pick recomendado" (Talao.tsx renderiza {pick.mercado} cru)
    const talao = card.getByRole("region", { name: "pick recomendado" });
    await expect(talao.getByRole("heading", { name: TALAO_ROTULO })).toBeVisible();

    // Segundo pick: linha com "BTTS", fora da region do talao, sem botao "copiar".
    const linhaSegundo = card.locator("p", { hasText: "BTTS" }).filter({ hasNot: talao.locator("*") });
    await expect(linhaSegundo).toContainText(SEGUNDO_ROTULO);
    await expect(linhaSegundo.getByRole("button")).toHaveCount(0);
    // Unico botao "copiar" do card inteiro e o do talao.
    await expect(card.getByRole("button", { name: /copiar/ })).toHaveCount(1);

    // "N mercados avaliados, 2 valem - ver todos"
    await expect(card.getByText(`${N_AVALIADOS} mercados avaliados, ${N_VALEM} valem`)).toBeVisible();
    const verTodos = card.getByRole("link", { name: "ver todos" });
    const href = await verTodos.getAttribute("href");
    if (info.project.name === "mobile") {
      expect(href).toBe(`/jogos/${encodeURIComponent(id)}#mercados`);
    } else {
      // escreverFeedUrl usa URLSearchParams (espaco -> "+", nao "%20")
      const p = new URLSearchParams();
      p.set("jogo", id);
      expect(href).toBe(`/jogos?${p.toString()}#mercados`);
    }
  });

  test("desktop: abre o painel e a tabela tem os 15 mercados avaliados", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "painel lateral so no desktop");
    await stub(page);
    await page.goto("/jogos");
    const card = page.locator("article").filter({ hasText: TALAO_ROTULO });
    await card.locator("h2 a").click();
    await expect(page).toHaveURL(/jogo=/);

    const painel = page.getByRole("complementary", { name: "detalhe do jogo" });
    await expect(painel).toBeVisible();
    await expect(painel).toBeFocused();
    await expect(painel.getByRole("heading", { name: `Todos os mercados avaliados (${N_AVALIADOS})` })).toBeVisible();

    const linhas = painel.locator("table#mercados tbody tr");
    await expect(linhas).toHaveCount(N_AVALIADOS);
    // ordenados: [...picks vale/edge desc, ...recusados na ordem do fixture] (toJogoView)
    await expect(linhas.nth(0).locator("td").nth(0)).toHaveText(TALAO_ROTULO);
    await expect(linhas.nth(0).locator("td").nth(4)).toHaveText("vale");
    await expect(linhas.nth(1).locator("td").nth(0)).toHaveText(SEGUNDO_ROTULO);
    await expect(linhas.nth(1).locator("td").nth(4)).toHaveText("vale");
    await expect(linhas.nth(2).locator("td").nth(0)).toHaveText("Over 2.5 gols");
    await expect(linhas.nth(2).locator("td").nth(4)).toHaveText("não vale");
  });

  test("celular: toca no titulo e navega para a pagina de detalhe com a mesma tabela", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile");
    await stub(page);
    await page.goto("/jogos");
    const card = page.locator("article").filter({ hasText: TALAO_ROTULO });
    await card.locator("h2 a").click();
    await expect(page).toHaveURL(`/jogos/${encodeURIComponent(id)}`);

    await expect(page.getByRole("heading", { name: `Todos os mercados avaliados (${N_AVALIADOS})` })).toBeVisible();
    const linhas = page.locator("table#mercados tbody tr");
    await expect(linhas).toHaveCount(N_AVALIADOS);
    await expect(linhas.nth(0).locator("td").nth(0)).toHaveText(TALAO_ROTULO);
    await expect(linhas.nth(1).locator("td").nth(0)).toHaveText(SEGUNDO_ROTULO);
  });

  test("ledger (ontem): Guadalajara-Pumas ja tem 2 vale no fixture real", async ({ page }) => {
    // liga-mx-Guadalajara-Pumas UNAM-1789348020.0 (ledger-dia.json): talao =
    // Over/Under "Under 3.5" SAFE edge .1577 (outcome=1, detail "3 gols");
    // segundo = Cards "Over 3.5" NEUTRO_QUALIFICADO edge .0874 (> Corners
    // "Under 10.5" NQ edge .0715) -> ja existe um 2o vale, sem precisar
    // adicionar pick novo (conferido por script node reproduzindo
    // escolherTalao contra o fixture — ver task report).
    await stub(page);
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerDia) }));
    await page.goto("/jogos?dia=ontem");
    await expect(page.locator("article").first()).toBeVisible();

    const card = page.locator("article", { hasText: "Guadalajara" }).filter({ hasText: "Pumas UNAM" });
    await expect(card).toHaveCount(1);
    await expect(card).toHaveAttribute("data-estado", "ontem");
    await expect(card.getByText("✓ fechou com 3 gols")).toBeVisible();
    await expect(card.locator("p", { hasText: "Cartões Over 3.5" })).toBeVisible();
  });
});
