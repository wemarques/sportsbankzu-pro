import { type Page } from "@playwright/test";
import feed from "../fixtures/feed.json";

export async function stub(page: Page, opts: { vazio?: boolean; erro?: boolean } = {}) {
  await page.route("**/api/matches/fetch**", (route) => {
    if (opts.erro) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ matches: [], _error: { kind: "TIMEOUT", message: "x" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(opts.vazio ? { matches: [] } : feed) });
  });
  await page.route("**/api/matches/live**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
  await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
}
