import { test, expect } from "@playwright/test";

test.describe("Home Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the header with sportsbank. branding and PRO badge", async ({ page }) => {
    await expect(page.locator("header")).toContainText("sportsbank.");
    await expect(page.locator("header")).toContainText("PRO");
  });

  test("shows search bar with Ctrl+K shortcut", async ({ page }) => {
    const searchButton = page.locator("header button", { hasText: "Buscar" });
    await expect(searchButton).toBeVisible();
    await expect(searchButton).toContainText("Ctrl+K");
  });

  test("opens search input when search button is clicked", async ({ page }) => {
    await page.locator("header button", { hasText: "Buscar" }).click();
    const input = page.locator('header input[type="text"]');
    await expect(input).toBeVisible();
    await expect(input).toBeFocused();
  });

  test("displays theme toggle in header", async ({ page }) => {
    const toggle = page.locator('button[aria-label="Alternar tema"]');
    await expect(toggle).toBeVisible();
  });

  test("displays notification bell in header", async ({ page }) => {
    const bell = page.locator('button[aria-label="Notificacoes"]');
    await expect(bell).toBeVisible();
  });

  test("renders date navigation with Hoje button", async ({ page }) => {
    await expect(page.getByText("Hoje")).toBeVisible();
    await expect(page.locator('button[aria-label="Dia anterior"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Proximo dia"]')).toBeVisible();
  });

  test("renders market tabs (1X2, BTTS, Gols, etc.)", async ({ page }) => {
    const nav = page.locator('nav[aria-label="Mercados"]');
    await expect(nav).toBeVisible();
    await expect(nav.getByText("1X2")).toBeVisible();
    await expect(nav.getByText("BTTS")).toBeVisible();
    await expect(nav.getByText("Gols")).toBeVisible();
    await expect(nav.getByText("Dupla Chance")).toBeVisible();
  });

  test("1X2 tab is active by default", async ({ page }) => {
    const tab = page.locator('nav[aria-label="Mercados"] button', { hasText: "1X2" });
    await expect(tab).toHaveClass(/text-primary/);
  });

  test("shows loading state or match content", async ({ page }) => {
    // Either loading indicator or empty state or match cards should be visible
    const content = page.locator("main");
    await expect(content).toBeVisible();
    const hasLoading = await page.getByText("Carregando jogos...").isVisible().catch(() => false);
    const hasEmpty = await page.getByText("Nenhum jogo disponivel para hoje.").isVisible().catch(() => false);
    const hasMatches = await content.locator("button").first().isVisible().catch(() => false);
    expect(hasLoading || hasEmpty || hasMatches).toBeTruthy();
  });

  test("detail panel shows placeholder when no match selected", async ({ page }) => {
    await expect(page.getByText("Selecione um jogo para ver os detalhes")).toBeVisible();
  });

  test("renders bottom navigation with Destaques, Radar Esportivo, ST Bots", async ({ page }) => {
    const bottomNav = page.locator('nav[aria-label="Navegacao principal"]');
    await expect(bottomNav).toBeVisible();
    await expect(bottomNav.getByText("Destaques")).toBeVisible();
    await expect(bottomNav.getByText("Radar Esportivo")).toBeVisible();
    await expect(bottomNav.getByText("ST Bots")).toBeVisible();
  });

  test("Filtros button toggles filter panel", async ({ page }) => {
    await page.getByText("Filtros").click();
    // After clicking, league filter chips should appear
    await expect(page.getByText("Premier League")).toBeVisible();
  });

  test("Favoritos button toggles active state", async ({ page }) => {
    const favBtn = page.getByText("Favoritos");
    await favBtn.click();
    await expect(favBtn).toHaveClass(/text-primary/);
  });
});
