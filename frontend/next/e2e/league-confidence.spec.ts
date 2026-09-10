import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { join } from "path";

const ROOT = join(__dirname, "..");
const REPO = join(ROOT, "..", "..");

/**
 * #250 — guarda de VOCABULARIO.
 *
 * O selo quebrou uma vez por manter uma tabela de ids escrita a mao que
 * divergia da canonica do backend em 4 das 22 ligas (brasileirao-serie-a,
 * brasileirao-serie-b, league-one, premiership). O teste compara a constante
 * do frontend com `backend/config/leagues_config.py::LEAGUE_ID_ALIASES` e
 * falha assim que as duas se separarem.
 */
function parsePythonAliases(): Record<string, string> {
  const py = readFileSync(join(REPO, "backend", "config", "leagues_config.py"), "utf-8");
  const start = py.indexOf("LEAGUE_ID_ALIASES = {");
  expect(start, "LEAGUE_ID_ALIASES nao encontrado no leagues_config.py").toBeGreaterThan(-1);
  const block = py.slice(start, py.indexOf("}", start));
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/"([^"]+)":\s*"([^"]+)"/g)) out[m[1]] = m[2];
  return out;
}

function parseTsAliases(): Record<string, string> {
  const ts = readFileSync(join(ROOT, "src", "lib", "leagues.ts"), "utf-8");
  const start = ts.indexOf("export const FRONTEND_TO_BACKEND_LEAGUE_ID");
  expect(start, "FRONTEND_TO_BACKEND_LEAGUE_ID nao encontrado").toBeGreaterThan(-1);
  const block = ts.slice(start, ts.indexOf("};", start));
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/"([^"]+)":\s*"([^"]+)"/g)) out[m[1]] = m[2];
  return out;
}

test.describe("#250 vocabulario de ids de liga", () => {
  test("mapa do frontend e espelho exato do mapa do backend", () => {
    const py = parsePythonAliases();
    const ts = parseTsAliases();
    expect(Object.keys(ts).length).toBe(22);
    expect(ts).toEqual(py);
  });

  test("todo id de AVAILABLE_LEAGUES tem traducao canonica", () => {
    const leagues = readFileSync(join(ROOT, "src", "lib", "leagues.ts"), "utf-8");
    const blk = leagues.slice(leagues.indexOf("export const AVAILABLE_LEAGUES"));
    const ids = [...blk.matchAll(/^ {4}id: "([^"]+)"/gm)].map((m) => m[1]);
    const ts = parseTsAliases();
    expect(ids.length).toBe(22);
    for (const id of ids) {
      expect(ts[id], `AVAILABLE_LEAGUES tem "${id}" sem traducao no mapa canonico`).toBeTruthy();
    }
  });
});

/**
 * #250 — o selo so existe dentro de um grupo de liga, e o grupo so existe se
 * houver jogo. Contra a Lambda real o dashboard fica a merce de 429/dia sem
 * jogos e o teste vira skip silencioso — que nao prova nada. Aqui o feed de
 * jogos e estubado no browser (contorna a rota Next inteira), entao o selo
 * SEMPRE renderiza e as asercoes de honestidade rodam de verdade.
 */
async function stubMatches(page: import("@playwright/test").Page) {
  await page.route("**/api/matches/fetch**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        _dataSource: "e2e-stub",
        matches: [
          {
            id: "e2e-250-1",
            leagueId: "premier-league",
            leagueName: "Premier League",
            homeTeam: "Arsenal",
            awayTeam: "Chelsea",
            datetime: new Date(Date.now() + 3 * 3600_000).toISOString(),
            status: "scheduled",
            odds: { home: 2.1, draw: 3.4, away: 3.6 },
            stats: { homeWinProb: 45, drawProb: 27, awayWinProb: 28 },
          },
        ],
      }),
    }),
  );
  await page.route("**/api/matches/live**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }),
  );
}

test.describe("#250 honestidade do selo de confianca", () => {
  // O selo vive no painel de LISTA de ligas, que no mobile (<=1024px) e
  // substituido pela tela de detalhe assim que um jogo e auto-selecionado
  // (`dashboard/page.tsx:1935` — `!isMobile || !selectedMatchId`). Comportamento
  // pre-existente do produto, nao do #250: no mobile nao ha selo para auditar.
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      testInfo.project.name === "mobile",
      "selo so existe no painel de lista (desktop)",
    );
  });

  test("sem modelo, o tooltip nao afirma modelo treinado", async ({ page }) => {
    await stubMatches(page);
    await page.route("**/api/ml/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          leagues: {
            "premier-league": {
              available: false,
              trained_at: null,
              validation_brier: null,
              n_samples: null,
            },
          },
        }),
      }),
    );
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    const badges = page.locator(".league-confidence-badge");
    await expect(badges.first()).toBeAttached();
    const n = await badges.count();
    expect(n, "o feed estubado deve produzir ao menos um selo").toBeGreaterThan(0);

    for (let i = 0; i < n; i++) {
      const label = await badges.nth(i).getAttribute("data-confidence-level");
      const text = (await badges.nth(i).getAttribute("aria-label")) ?? "";
      if (label !== "ML_ACTIVE") {
        expect(text, `selo ${label} afirmando modelo treinado`).not.toMatch(/treinado com \d+ jogos/i);
      }
      // Requisito 4: nunca a data literal do componente antigo.
      expect(text).not.toContain("20/03/2026");
    }
  });

  test("backend indisponivel degrada para nao verificado", async ({ page }) => {
    await stubMatches(page);
    await page.route("**/api/ml/status", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ ok: false, leagues: null, error: { kind: "TIMEOUT" } }),
      }),
    );
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    const badges = page.locator(".league-confidence-badge");
    await expect(badges.first()).toBeAttached();
    const n = await badges.count();
    expect(n, "o feed estubado deve produzir ao menos um selo").toBeGreaterThan(0);

    for (let i = 0; i < n; i++) {
      await expect(badges.nth(i)).toHaveAttribute("data-confidence-level", "UNVERIFIED");
      const text = (await badges.nth(i).getAttribute("aria-label")) ?? "";
      expect(text).toMatch(/não foi possível verificar/i);
      expect(text).not.toMatch(/treinado com \d+ jogos/i);
    }
  });

  test("GET /api/ml/status responde ok:true ou 503 honesto", async ({ request }) => {
    const resp = await request.get("/api/ml/status");
    expect([200, 503]).toContain(resp.status());
    const body = await resp.json();
    expect(body).toHaveProperty("ok");
    if (body.ok) {
      expect(body.leagues).toBeTruthy();
    } else {
      // Requisito 2: falha nunca vem disfarcada de dado.
      expect(body.leagues).toBeNull();
    }
  });
});
