#!/usr/bin/env node
/**
 * #258 — captura as tres telas da rodada 2 do teste de 5s (spec §7), a
 * partir do PRODUTO construido (nao do mockup da rodada 1). Roda contra
 * `next start` ja de pe (padrao localhost:3001), com Playwright ja
 * instalado (devDependency existente desde a fase 3, Task 18).
 *
 * Tres telas x dois viewports (celular 390x844, desktop 1440x900) = 6 PNGs:
 *   tela-1-talao-{viewport}.png  — /jogos, o card "vale" (objeto de decisao)
 *   tela-2-tabela-{viewport}.png — detalhe do jogo, table#mercados (objeto de rigor)
 *   tela-3-hero-{viewport}.png   — "/", primeira visita, hero (compreensao)
 *
 * Uso:
 *   node scripts/capturar-telas-teste-5s.mjs [--base=http://localhost:3001] [--dia=hoje|amanha]
 *
 * Sem --dia: tenta "hoje" e depois "amanha". Se nenhum dos dois tiver um
 * jogo "vale" no feed real, o script NAO fabrica card nenhum — encerra com
 * mensagem clara e codigo de saida != 0, mas ainda assim salva as telas de
 * hero (que nao dependem de haver pick), para o material nao ficar vazio.
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const args = process.argv.slice(2);
function flag(name, def) {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : def;
}

const BASE = (flag("base", "http://localhost:3001")).replace(/\/+$/, "");
const DIA_FIXA = flag("dia", null); // "hoje" | "amanha" | null (tenta os dois)
if (DIA_FIXA && !["hoje", "amanha"].includes(DIA_FIXA)) {
  console.error(`--dia invalido: "${DIA_FIXA}". Use "hoje" ou "amanha".`);
  process.exit(2);
}

// Independente do cwd de onde `node` foi chamado: o script vive em
// frontend/next/scripts/, a raiz do repo fica dois niveis acima, e a saida
// sempre vai para <raiz>/docs/superpowers/testes/rodada-2-telas.
const RAIZ_REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const OUT = join(RAIZ_REPO, "docs", "superpowers", "testes", "rodada-2-telas");
mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { label: "mobile", width: 390, height: 844 },
  { label: "desktop", width: 1440, height: 900 },
];

function urlDoFeed(dia) {
  return dia === "amanha" ? `${BASE}/jogos?dia=amanha` : `${BASE}/jogos`;
}

const browser = await chromium.launch();

/**
 * Descobre, com um browsing context descartavel, qual dia tem um jogo
 * "vale" real no feed (nao fabrica nada — so procura). Retorna
 * { dia, id, titulo } ou null se nenhum dos dias pedidos tiver vale.
 */
async function acharJogoVale() {
  const dias = DIA_FIXA ? [DIA_FIXA] : ["hoje", "amanha"];
  const sonda = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await sonda.newPage();
  try {
    for (const dia of dias) {
      await page.goto(urlDoFeed(dia), { waitUntil: "domcontentloaded" });
      try {
        await page.waitForSelector("article[data-estado='vale']", { timeout: 15_000 });
      } catch {
        console.log(`[capturar-telas] dia=${dia}: nenhum jogo "vale" no feed em ${urlDoFeed(dia)}.`);
        continue;
      }
      const cartao = page.locator("article[data-estado='vale']").first();
      const link = cartao.locator("h2 a").first();
      const titulo = (await link.textContent())?.trim() ?? "(sem titulo)";
      const href = await link.getAttribute("href");
      if (!href) continue;
      const id = decodeURIComponent(new URL(href, BASE).pathname.split("/").pop() ?? "");
      return { dia, id, titulo };
    }
    return null;
  } finally {
    await sonda.close();
  }
}

const achado = await acharJogoVale();
if (!achado) {
  const dias = DIA_FIXA ? [DIA_FIXA] : ["hoje", "amanha"];
  console.error(
    `[capturar-telas] Nenhum jogo "vale" encontrado em ${BASE} para ${dias.join(" nem ")}. ` +
      `NAO fabricando card — capturando so as telas de hero abaixo (nao dependem de pick).`,
  );
}

// #258 diagnostico-B-C: o texto exato de HERO.semTalao (frontend/next/src/lib/copy.ts)
// — hardcoded aqui porque este script roda com node puro (.mjs), sem loader
// de TypeScript, e nao pode importar copy.ts diretamente. Se o texto mudar
// em copy.ts, atualizar esta constante junto.
const HERO_SEM_TALAO = "Sem talão publicado hoje ou ontem.";

/**
 * Tela 3 (hero, "/"): sempre em contexto novo/sem cookies — primeira visita
 * real. diagnostico-B-C mediu o card-prova levando ate ~7.3s (fan-out de 13
 * ligas) para resolver — bem acima do waitForTimeout(1500) fixo que a rodada
 * 1 usava. Aqui a espera e uma corrida (Promise.race) entre os dois
 * desfechos possiveis do Hero.tsx: o <article> do card-prova OU a frase
 * HERO.semTalao (fallback quando nao ha talao nem hoje nem ontem) — o que
 * vier primeiro, ate 30s.
 */
async function capturarHero(viewport) {
  const ctx = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
  await ctx.clearCookies();
  const page = await ctx.newPage();
  const inicio = Date.now();
  await page.goto(`${BASE}/`, { waitUntil: "load" });
  await page.waitForSelector("main");

  const esperaCard = page.waitForSelector("article", { timeout: 30_000 }).then(() => "card");
  const esperaFrase = page
    .waitForFunction(
      (texto) => document.body.textContent?.includes(texto) ?? false,
      HERO_SEM_TALAO,
      { timeout: 30_000 },
    )
    .then(() => "frase");

  let ramo;
  try {
    ramo = await Promise.race([esperaCard, esperaFrase]);
  } catch {
    ramo = "timeout";
  }
  const segundos = Number(((Date.now() - inicio) / 1000).toFixed(2));

  let detalhe;
  if (ramo === "card") {
    const cartao = page.locator("article").first();
    const estado = await cartao.getAttribute("data-estado").catch(() => null);
    const titulo = (await cartao.locator("h2 a").first().textContent().catch(() => null))?.trim();
    detalhe = `card (${titulo ?? "titulo desconhecido"}, estado=${estado ?? "desconhecido"})`;
  } else if (ramo === "frase") {
    detalhe = "frase HERO.semTalao";
  } else {
    detalhe = "timeout — nem card nem frase renderizaram em 30s";
  }
  console.log(`[capturar-telas] hero ${viewport.label}: ${detalhe}, ${segundos}s desde o goto.`);

  await page.screenshot({ path: `${OUT}/tela-3-hero-${viewport.label}.png` });
  await ctx.close();
  return { viewport: viewport.label, ramo: detalhe, segundos };
}

/** Telas 1 e 2 (talao + tabela), so se um jogo "vale" foi encontrado. */
async function capturarTalaoETabela(viewport, jogo) {
  const ctx = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
  const page = await ctx.newPage();

  await page.goto(urlDoFeed(jogo.dia), { waitUntil: "domcontentloaded" });
  await page.waitForSelector("article[data-estado='vale']", { timeout: 15_000 });
  const cartao = page.locator("article[data-estado='vale']").first();
  await cartao.screenshot({ path: `${OUT}/tela-1-talao-${viewport.label}.png` });

  const link = cartao.locator("h2 a").first();
  if (viewport.width < 1024) {
    // celular: navegacao de pagina cheia para /jogos/<id>
    const href = await link.getAttribute("href");
    await page.goto(`${BASE}${href}`, { waitUntil: "domcontentloaded" });
  } else {
    // desktop: clique abre o painel lateral na propria /jogos (SPA, sem navegacao)
    await link.click();
  }
  await page.waitForSelector("table#mercados", { timeout: 15_000 });

  // #258 diagnostico-B-C: o painel de detalhe e um <aside sticky> cuja altura
  // de container e a propria altura do aside — ele "gruda" no topo e nunca
  // desgruda por scroll. `locator.screenshot()` usa um clip do CDP limitado a
  // viewport renderizada; se o rodape da tabela (rect.bottom) cai fora dela,
  // essa regiao nunca foi pintada nesse frame e o buffer devolve a cor de
  // fundo do body (o bloco navy solido do print). Fix: redimensionar a
  // viewport para caber rect.bottom antes de tirar o print. Loop curto porque
  // o reflow do redimensionamento pode mudar rect.bottom de novo.
  let alturaViewport = viewport.height;
  for (let tentativa = 0; tentativa < 3; tentativa++) {
    const bottom = await page.locator("table#mercados").evaluate((el) => el.getBoundingClientRect().bottom);
    const necessaria = Math.ceil(bottom + 16);
    if (necessaria <= alturaViewport) break;
    alturaViewport = necessaria;
    await page.setViewportSize({ width: viewport.width, height: alturaViewport });
  }

  await page.locator("table#mercados").screenshot({ path: `${OUT}/tela-2-tabela-${viewport.label}.png` });

  await ctx.close();
}

const resultadosHero = [];
for (const vp of VIEWPORTS) {
  resultadosHero.push(await capturarHero(vp));
  if (achado) await capturarTalaoETabela(vp, achado);
}

await browser.close();

if (achado) {
  console.log(`[capturar-telas] Jogo capturado: "${achado.titulo}" (dia=${achado.dia}, id=${achado.id}).`);
  console.log(`[capturar-telas] 6 PNGs salvos em ${OUT}/.`);
  process.exit(0);
} else {
  console.log(`[capturar-telas] Apenas as telas de hero foram salvas em ${OUT}/ (2 PNGs). Ver LEIA-ME.md.`);
  process.exit(1);
}
