import { test, expect } from "@playwright/test";
import { stub } from "./helpers/stub";

test.describe("raiz e destino padrao (#258, spec §8)", () => {
  test("/ com cookie de retorno vai para /jogos", async ({ page, context }) => {
    await context.addCookies([{ name: "sbz_visitou", value: "1", domain: "localhost", path: "/" }]);
    await stub(page, { vazio: true });
    await page.goto("/");
    await expect(page).toHaveURL(/\/jogos/);
  });
  test("rotas que ficam sem link ainda respondem (nao viram 404 por engano)", async ({ page }) => {
    for (const rota of ["/login", "/register"]) {
      const resp = await page.goto(rota);
      expect(resp?.status()).toBeLessThan(400);
    }
  });
});
