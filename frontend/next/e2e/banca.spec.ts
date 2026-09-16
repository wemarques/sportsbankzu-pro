import { test, expect } from "@playwright/test";

test.describe("/banca (#254-b, spec §5)", () => {
  test("indefinida: input vazio e chamada para definir; salvar confirma no mesmo slot", async ({ page }) => {
    await page.goto("/banca");
    const input = page.getByLabel("Sua banca");
    await expect(input).toBeFocused();
    await expect(input).toHaveValue("");
    await expect(page.getByText("Defina a banca para ver quanto apostar em cada jogo.")).toBeVisible();
    await input.fill("1000");
    await page.getByRole("button", { name: "Salvar banca" }).click();
    await expect(page.getByText("banca salva")).toBeVisible();
    await expect(page.getByText(/até R\$ .* por jogo/)).toBeVisible();
  });
  test("valor invalido: contra-texto inline", async ({ page }) => {
    await page.goto("/banca");
    await page.getByLabel("Sua banca").fill("abc");
    await page.getByRole("button", { name: "Salvar banca" }).click();
    await expect(page.getByText("banca precisa ser um valor em reais")).toBeVisible();
  });
  test("localStorage corrompido: trata como indefinida", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("sportsbankzu-bankroll", "{{"));
    await page.goto("/banca");
    await expect(page.getByLabel("Sua banca")).toHaveValue("");
  });
});
