import { test, expect } from "@playwright/test";

test.describe("Home Page (#257 — hero substitui o redirect fixo para /dashboard)", () => {
  test("primeira visita: fica em / e mostra o hero", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("link", { name: "Ver os jogos de hoje" })).toBeVisible();
  });

  test("visita grava o cookie sbz_visitou; visita seguinte redireciona para /jogos", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    const cookies = await context.cookies();
    expect(cookies.find((c) => c.name === "sbz_visitou")?.value).toBe("1");
    await page.goto("/");
    await expect(page).toHaveURL(/\/jogos/);
  });
});
