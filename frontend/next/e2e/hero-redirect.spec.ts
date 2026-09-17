import { test, expect } from "@playwright/test";

test.describe("redirect por cookie na raiz (#257, spec §3)", () => {
  test("primeira visita (sem cookie): fica em / e mostra o hero", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("link", { name: "Ver os jogos de hoje" })).toBeVisible();
  });
  test("visitar / grava o cookie sbz_visitou", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    const cookies = await context.cookies();
    const c = cookies.find((k) => k.name === "sbz_visitou");
    expect(c?.value).toBe("1");
    expect(c?.path).toBe("/");
  });
  test("com o cookie: / redireciona para /jogos, sem flash do hero", async ({ page, context }) => {
    await context.addCookies([{ name: "sbz_visitou", value: "1", domain: "localhost", path: "/" }]);
    await page.goto("/");
    await expect(page).toHaveURL(/\/jogos/);
  });
  test("visitar /jogos tambem grava o cookie (quem chega direto por link nao ve o hero de novo)", async ({ page, context }) => {
    await context.clearCookies();
    await page.route("**/api/matches/fetch**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
    await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
    await page.goto("/jogos");
    const cookies = await context.cookies();
    expect(cookies.find((k) => k.name === "sbz_visitou")?.value).toBe("1");
  });
});
