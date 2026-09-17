import { type Page } from "@playwright/test";
import feed from "../fixtures/feed.json";
import feedMulti from "../fixtures/feed-multi.json";
import ledgerAgregado from "../fixtures/ledger-agregado.json";
import ledgerPicks from "../fixtures/ledger-picks.json";

export async function stub(page: Page, opts: { vazio?: boolean; erro?: boolean; feed?: "padrao" | "multi" } = {}) {
  const dados = opts.feed === "multi" ? feedMulti : feed;
  await page.route("**/api/matches/fetch**", (route) => {
    if (opts.erro) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ matches: [], _error: { kind: "TIMEOUT", message: "x" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(opts.vazio ? { matches: [] } : dados) });
  });
  await page.route("**/api/matches/live**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
  await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
  // #256 (Task 25, R3) — hermetiza useMediaDasLigas (Task 24) e /desempenho: sem este
  // stub, qualquer teste que use stub() e monte um componente que leia o ledger
  // agregado bateria na rede de verdade.
  await page.route("**/api/ledger/agregado**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerAgregado) }));
  // #257 — hermetiza qualquer tela que busque picks individuais (BlocoRetorno).
  await page.route("**/api/ledger/picks**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerPicks) }));
  // #256 — so registra o fallback se o teste ainda nao tiver a sua propria rota
  // (ex.: ontem.spec.ts estuba **/api/ledger/dia** localmente com um fixture proprio,
  // que tem prioridade por ser registrado depois de stub() no teste).
  await page.route("**/api/ledger/dia**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, data: "1970-01-01", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 }, semana: {}, mes: {} }) }));
}
