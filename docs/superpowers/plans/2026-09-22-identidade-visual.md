# Identidade visual (#262) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao produto novo cabeçalho fixo com marca e data, cor de identidade teal, profundidade nos cards, carregamento por camadas com esqueleto honesto, monograma SBZ e estados vazios com arte — sem tocar no talão validado.

**Architecture:** Tudo no frontend Next (`frontend/next`). Um token novo (`--sb-marca`) e uma classe de superfície (`.sb-card`) em `globals.css`/`tokens.ts`; um componente de cabeçalho cliente com relógio BRT; o feed passa a consumir o `onBatchReady` que `getMatchesByLeague` já expõe, somando lotes a uma lista ordenada e encolhendo o esqueleto; estados vazios ganham o monograma. Nenhum backend, nenhuma rota nova.

**Tech Stack:** Next.js 15 (App Router), React, Tailwind (classes utilitárias + tokens CSS), Vitest + Testing Library (jsdom), Playwright (chromium contra build de produção; mobile em dev; visual local-only), axe.

**Spec:** `docs/superpowers/specs/2026-09-22-identidade-visual-design.md` (com errata de 2026-09-22). Spec-mãe: `docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md`.

## Global Constraints

- Copy só em `src/lib/copy.ts`; toda frase nova passa por `npm run lint:accents`. Identificador em template literal que dispare o lint = PARAR e escalar; o allowlist de `scripts/check-accents.mjs` nunca é afrouxado pelo implementador.
- `npm run lint:fonts`: Barlow (`fonteMarca`) só na marca (cabeçalho e monograma) e na headline do hero, que já existia.
- Tokens: hex vivem em `src/lib/tokens.ts` e são copiados em `src/app/globals.css`; `tests/unit/tokens.test.ts` trava os dois. Todo par (texto, fundo) novo entra em `PARES_PERMITIDOS`.
- Talão intocado: `--sb-talao: #E3D9AE`, sem sombra, sem teal. Faixas de desfecho e vermelho de contra intocados.
- Honestidade do carregamento (spec §3): "Nenhum jogo…" só com todos os lotes respondidos e lista vazia; nunca por tempo; nenhum número de latência na copy.
- Geometria (spec §1): cabeçalho `fixed`, 56 px; sidebar `sticky top: 56px; height: calc(100vh - 56px)`; painel de detalhe `top: calc(56px + 1rem)`, `max-height: calc(100vh - 56px - 2rem)`.
- Processo (dono): commit por task, mensagem com `(#262)`; nunca commitar com check vermelho; `rm -f tsconfig.tsbuildinfo` antes do `tsc`; `git checkout -- next-env.d.ts tsconfig.json` depois do `next build`; nunca `git stash`; nunca `git push` (o controller faz); testes existentes não são editados sem ruling (exceção declarada na Task 1: `tokens.test.ts` ganha asserções novas, não perde nenhuma); referências visuais (`e2e/*-snapshots/*-win32.png`) só mudam na Task 7, depois do approve por imagem do dono; toda task que toca UI anexa screenshot 390 e 1440 px ao relatório.
- Portão por task: `npm run lint:accents && npm run lint:fonts && rm -f tsconfig.tsbuildinfo && npx tsc --noEmit -p tsconfig.json && npm run test:unit && npm run build && CI=1 npx playwright test --project=chromium`; o visual (`--project=visual-desktop --project=visual-mobile`) roda e o diff é ANEXADO, não corrigido, até a Task 7.

---

## Mapa de arquivos

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `src/lib/tokens.ts`, `src/app/globals.css` | token `marca`, pares de contraste, `.sb-card`, `.sb-esqueleto`, sublinhado teal | 1, 5 |
| `src/components/feed/LigaChips.tsx`, `src/components/nav/Navegacao.tsx`, `src/components/feed/CardJogo.tsx`, `src/components/detalhe/Detalhe.tsx` | teal em seleção e navegação; superfície `.sb-card` | 1 |
| `src/components/marca/MonogramaSBZ.tsx`, `public/marca/sbz.svg`, `scripts/gerar-icones.mjs`, `src/app/icon.png`, `src/app/apple-icon.png`, `public/marca/icon-192.png`, `public/marca/icon-512.png`, `src/app/manifest.ts` | monograma e ícones | 2 |
| `src/lib/formato.ts`, `src/components/marca/Cabecalho.tsx`, `src/app/layout.tsx`, `src/app/jogos/Feed.tsx` (aside) | cabeçalho fixo, data BRT, geometria | 3 |
| `src/lib/copy.ts` (`MARCA`, `CARIMBO`, `CARREGANDO`) | copy nova | 3, 4, 5 |
| `src/app/jogos/Feed.tsx`, `src/app/desempenho/Painel.tsx` | carimbo no topo do conteúdo | 4 |
| `src/lib/lotesFeed.ts`, `src/components/feed/EsqueletoCard.tsx`, `src/components/detalhe/EsqueletoDetalhe.tsx`, `src/app/desempenho/EsqueletoDesempenho.tsx`, `src/app/jogos/Feed.tsx`, `src/app/jogos/[id]/page.tsx`, `src/app/desempenho/Painel.tsx`, `src/lib/api.ts` (export `numeroDeLotes`) | carregamento por camadas e esqueletos | 5 |
| `src/components/marca/EstadoVazio.tsx` + usos em Feed, Hero, Painel, `/banca` | estados vazios com arte | 6 |
| `e2e/cabecalho.spec.ts`, `e2e/carregando.spec.ts`, `e2e/visual.spec.ts-snapshots/*` | prova e2e; referências | 3, 4, 5, 7 |
| `docs/REGISTRO_CORRECOES.md` (#262), `docs/INDICE_REGRAS.md`, `docs/REGRAS_ATIVAS.md` | fechamento | 7 |

---

### Task 1: Token `marca`, superfície `.sb-card`, teal na seleção e na navegação

**Files:**
- Modify: `frontend/next/src/lib/tokens.ts`, `frontend/next/src/app/globals.css`
- Modify: `frontend/next/src/components/feed/LigaChips.tsx`, `frontend/next/src/components/nav/Navegacao.tsx`, `frontend/next/src/components/feed/CardJogo.tsx` (linhas 55-57, o `<article>`), `frontend/next/src/components/detalhe/Detalhe.tsx` (linha 22, o `<div>` raiz)
- Test: `frontend/next/tests/unit/tokens.test.ts` (só acrescenta), `frontend/next/tests/unit/LigaChips.test.tsx` (novo), `frontend/next/tests/unit/Navegacao.test.tsx` (só acrescenta um `it`)

**Interfaces:**
- Produces: `TOKENS.marca = "#4FB3BF"`, CSS `--sb-marca`, classe `.sb-card`, regra global `a { text-decoration-color: var(--sb-marca) }`.

- [ ] **Step 1: Teste do token e dos pares (vermelho)** — acrescentar ao fim de `tests/unit/tokens.test.ts`, dentro do `describe`:

```ts
  it("#262: marca existe, e o mesmo hex de confianca, e passa sobre tinta/painel/hover", () => {
    expect(TOKENS.marca).toBe(TOKENS.confianca);
    for (const fundo of ["tinta", "painel", "hover"] as const) {
      expect(contraste(TOKENS.marca, TOKENS[fundo])).toBeGreaterThanOrEqual(4.5);
      expect(PARES_PERMITIDOS.some(([t, f]) => t === "marca" && f === fundo)).toBe(true);
    }
    expect(PARES_PERMITIDOS.some(([t]) => t === "marca" && PARES_PERMITIDOS.find(([tt, f]) => tt === t && f === "talao"))).toBe(false);
  });
```

- [ ] **Step 2: Rodar** `npx vitest run tests/unit/tokens.test.ts` → FAIL (`TOKENS.marca` undefined).

- [ ] **Step 3: Implementar** em `src/lib/tokens.ts`: acrescentar `marca: "#4FB3BF",` após `confianca` (com comentário `// #262 — "a casa": marca, navegação ativa, seleção. Mesmo hex de confianca, token distinto de propósito.`) e os pares `["marca", "tinta", 4.5], ["marca", "painel", 4.5], ["marca", "hover", 4.5],` em `PARES_PERMITIDOS`. Em `globals.css`, no bloco `:root`, após `--sb-confianca`: `--sb-marca: #4FB3BF;`. Após o bloco `.sb-foco`, acrescentar:

```css
/* #262 — superficie com profundidade (spec §2: painel sobre tinta + borda + sombra baixa). Talao NAO usa. */
.sb-card { background: var(--sb-painel); border: 1px solid var(--sb-linha); border-radius: var(--sb-raio-painel); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); }
/* #262 — sublinhado na cor da casa; o texto do link continua na cor do texto. */
a { text-decoration-color: var(--sb-marca); }
```

- [ ] **Step 4: Rodar** `npx vitest run tests/unit/tokens.test.ts` → PASS (inclusive "globals.css carrega os mesmos hex").

- [ ] **Step 5: Teste dos chips (vermelho)** — criar `tests/unit/LigaChips.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LigaChips } from "@/components/feed/LigaChips";

describe("LigaChips (#262, spec §2)", () => {
  const ligas = [{ id: "premier-league", nome: "Premier League" }, { id: "championship", nome: "Championship" }];
  it("selecionado leva teal na borda e no texto; nao selecionado nao leva teal em lugar nenhum", () => {
    render(<LigaChips ligas={ligas} ativa="premier-league" onChange={vi.fn()} />);
    const sel = screen.getByRole("button", { name: "Premier League" });
    const nao = screen.getByRole("button", { name: "Championship" });
    expect(sel).toHaveAttribute("aria-pressed", "true");
    expect(sel.className).toContain("aria-pressed:border-[var(--sb-marca)]");
    expect(sel.className).toContain("aria-pressed:text-[var(--sb-marca)]");
    expect(sel.className).not.toContain("aria-pressed:bg-");
    expect(nao.className).toContain("hover:bg-[var(--sb-hover)]");
    expect(nao.className).not.toMatch(/hover:border|hover:text/);
  });
});
```

- [ ] **Step 6: Rodar** `npx vitest run tests/unit/LigaChips.test.tsx` → FAIL (classes antigas `aria-pressed:border-[var(--sb-texto)] aria-pressed:bg-[var(--sb-hover)]`).

- [ ] **Step 7: Implementar** em `LigaChips.tsx`, a `className` do botão vira:

```tsx
className="sb-foco rounded-full border border-[var(--sb-linha)] bg-[var(--sb-painel)] px-3 py-1 text-[13px] hover:bg-[var(--sb-hover)] aria-pressed:border-[var(--sb-marca)] aria-pressed:text-[var(--sb-marca)]"
```

- [ ] **Step 8: Teste da navegação (acrescentar `it` em `tests/unit/Navegacao.test.tsx`, dentro do `describe`):**

```tsx
  it("#262: o item ativo leva teal, os demais nao", () => {
    pathname = "/banca";
    render(<Navegacao />);
    const banca = screen.getByRole("link", { name: "Banca" });
    expect(banca.className).toContain("aria-[current=page]:text-[var(--sb-marca)]");
    expect(banca.className).not.toContain("aria-[current=page]:text-[var(--sb-texto)]");
  });
```

- [ ] **Step 9: Rodar** → FAIL. **Implementar** em `Navegacao.tsx`: na `className` do `<Link>`, trocar `aria-[current=page]:text-[var(--sb-texto)]` por `aria-[current=page]:text-[var(--sb-marca)]`. Rodar → PASS.

- [ ] **Step 10: Superfícies.** `CardJogo.tsx`, `<article>`: `className="sb-card space-y-2 p-4 hover:bg-[var(--sb-hover)] data-[selecionado=true]:border-[var(--sb-marca)]"` (sai `rounded-… border border-… bg-…` e o `border-[var(--sb-texto)]`). `Detalhe.tsx`, `<div>` raiz: `className="sb-card p-4"`. `tests/unit/CardJogo.test.tsx` e `detalhe.test.tsx` não afirmam classes de borda (conferir com `grep -n "sb-texto)\]\|border-\[" tests/unit/CardJogo.test.tsx tests/unit/detalhe.test.tsx`; se afirmarem, PARAR e escalar).

- [ ] **Step 11: Portão da task** (Global Constraints) + `CI=1 npx playwright test --project=visual-desktop --project=visual-mobile` → diffs esperados nas 9 telas (borda/sombra/teal); anexar `test-results/**/*-diff.png` ao relatório, NÃO atualizar referências. Registrar no relatório os contrastes: `contraste("#4FB3BF","#22242B")`, `contraste("#4FB3BF","#15161A")`, `contraste("#4FB3BF","#262830")` (imprimir com `node -e` importando por `npx tsx` ou copiando a função).

- [ ] **Step 12: Commit**
```bash
git add src/lib/tokens.ts src/app/globals.css src/components/feed/LigaChips.tsx src/components/nav/Navegacao.tsx src/components/feed/CardJogo.tsx src/components/detalhe/Detalhe.tsx tests/unit/tokens.test.ts tests/unit/LigaChips.test.tsx tests/unit/Navegacao.test.tsx
git commit -m "feat(front): token marca, superficie sb-card, teal na selecao e na navegacao (#262)"
```

---

### Task 2: Monograma SBZ e ícones da aplicação

**Files:**
- Create: `frontend/next/public/marca/sbz.svg`, `frontend/next/src/components/marca/MonogramaSBZ.tsx`, `frontend/next/scripts/gerar-icones.mjs`, `frontend/next/src/app/manifest.ts`
- Create (gerados pelo script, commitados): `frontend/next/src/app/icon.png` (32×32), `frontend/next/src/app/apple-icon.png` (180×180), `frontend/next/public/marca/icon-192.png`, `frontend/next/public/marca/icon-512.png`
- Test: `frontend/next/tests/unit/MonogramaSBZ.test.tsx`

**Interfaces:**
- Produces: `MonogramaSBZ({ tamanho?: number; decorativo?: boolean; apagado?: boolean })` — SVG inline; `decorativo` (padrão `true`) põe `aria-hidden="true"`; `apagado` troca teal por `--sb-texto-apagado`. `manifest.ts` padrão do Next (`MetadataRoute.Manifest`). Ícones em `src/app/icon.png` e `apple-icon.png` são captados automaticamente pelo App Router (file-based metadata).

**Desvio declarado (registrar no #262):** a spec pede letras convertidas em caminho; sem ferramenta de fontes no repositório, o SVG-fonte usa `<text>` com pilha `Barlow Condensed, Arial Narrow, Arial, sans-serif`, e os PNGs (que são o que o navegador e o celular mostram) são renderizados pelo script com a fonte carregada, ficando independentes de fonte.

- [ ] **Step 1: Teste (vermelho)** — `tests/unit/MonogramaSBZ.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";

describe("MonogramaSBZ (#262, spec §4)", () => {
  it("decorativo por padrao, 24 px, letras SBZ em teal sobre tinta", () => {
    const { container } = render(<MonogramaSBZ />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg.querySelector("rect")).toHaveAttribute("fill", "var(--sb-tinta)");
    expect(svg.querySelector("text")).toHaveTextContent("SBZ");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-marca)");
  });
  it("apagado troca a cor e nao decorativo ganha titulo acessivel", () => {
    const { container } = render(<MonogramaSBZ tamanho={48} apagado decorativo={false} />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("role", "img");
    expect(svg.querySelector("title")).toHaveTextContent("sportsbankzu");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-texto-apagado)");
  });
});
```

- [ ] **Step 2: Rodar** → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar** `src/components/marca/MonogramaSBZ.tsx`:

```tsx
import { fonteMarca } from "@/components/marca/fonteMarca";

/** #262 — monograma "SBZ" (spec §4): teal sobre tinta, canto 4 px. So versao escura. */
export function MonogramaSBZ({ tamanho = 24, decorativo = true, apagado = false }: { tamanho?: number; decorativo?: boolean; apagado?: boolean }) {
  const cor = apagado ? "var(--sb-texto-apagado)" : "var(--sb-marca)";
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 64 64" aria-hidden={decorativo ? "true" : undefined} role={decorativo ? undefined : "img"} className={fonteMarca.className}>
      {!decorativo && <title>sportsbankzu</title>}
      <rect width="64" height="64" rx="10" fill="var(--sb-tinta)" />
      <text x="32" y="43" textAnchor="middle" fontSize="30" fontWeight="700" letterSpacing="1" fill={cor}>SBZ</text>
    </svg>
  );
}
```

- [ ] **Step 4: Rodar** → PASS. `npm run lint:fonts` → verde (Barlow só via `fonteMarca`, que o lint já conhece).

- [ ] **Step 5: SVG-fonte e script de ícones.** `public/marca/sbz.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"><rect width="64" height="64" rx="10" fill="#15161A"/><text x="32" y="43" text-anchor="middle" font-family="Barlow Condensed, Arial Narrow, Arial, sans-serif" font-size="30" font-weight="700" letter-spacing="1" fill="#4FB3BF">SBZ</text></svg>
```

`scripts/gerar-icones.mjs` (roda com o Playwright já instalado; carrega a fonte do Google só nesta página descartável):

```js
#!/usr/bin/env node
// #262 — gera os PNGs do monograma SBZ a partir de public/marca/sbz.svg com a fonte real carregada.
import { chromium } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
const svg = readFileSync("public/marca/sbz.svg", "utf8");
const html = `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&display=swap"><style>body{margin:0;background:#15161A}#m{display:block}</style><div id="m">${svg}</div>`;
const alvos = [["src/app/icon.png", 32], ["src/app/apple-icon.png", 180], ["public/marca/icon-192.png", 192], ["public/marca/icon-512.png", 512]];
mkdirSync("public/marca", { recursive: true });
const b = await chromium.launch(); const p = await b.newPage();
await p.setContent(html); await p.evaluate(() => document.fonts.ready);
for (const [saida, px] of alvos) {
  await p.setViewportSize({ width: px, height: px });
  await p.evaluate((px) => { const s = document.querySelector("svg"); s.setAttribute("width", String(px)); s.setAttribute("height", String(px)); }, px);
  await p.locator("svg").screenshot({ path: saida, omitBackground: false });
  console.log("gerado", saida, px);
}
await b.close();
```

Rodar `node scripts/gerar-icones.mjs`; abrir os quatro PNGs e anexar ao relatório. **Se o de 32 px virar mancha** (letras ilegíveis), aplicar a alternativa da spec: gerar `icon.png` com o texto "S" (trocar temporariamente o `<text>` no `evaluate`) e registrar a decisão no relatório para o #262.

- [ ] **Step 6: `manifest.ts`** em `src/app/`:

```ts
import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "sportsbankzu", short_name: "sportsbankzu", start_url: "/jogos", display: "standalone",
    background_color: "#15161A", theme_color: "#15161A",
    icons: [{ src: "/marca/icon-192.png", sizes: "192x192", type: "image/png" }, { src: "/marca/icon-512.png", sizes: "512x512", type: "image/png" }],
  };
}
```

- [ ] **Step 7: Prova.** `npm run build` → rotas `/icon.png`, `/apple-icon.png`, `/manifest.webmanifest` listadas na saída do build (colar). Após `CI=1 npx playwright test --project=chromium` (suíte inteira, deve seguir verde), `curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/icon.png` = 200 com o servidor de produção de pé (encerrar depois).

- [ ] **Step 8: Commit**
```bash
git add public/marca/sbz.svg public/marca/icon-192.png public/marca/icon-512.png src/app/icon.png src/app/apple-icon.png src/app/manifest.ts src/components/marca/MonogramaSBZ.tsx scripts/gerar-icones.mjs tests/unit/MonogramaSBZ.test.tsx
git commit -m "feat(front): monograma SBZ, favicon e icones da aplicacao (#262)"
```

---

### Task 3: Cabeçalho fixo com marca e data BRT; geometria do sticky

**Files:**
- Modify: `frontend/next/src/lib/formato.ts`, `frontend/next/src/lib/copy.ts`, `frontend/next/src/app/layout.tsx`, `frontend/next/src/components/nav/Navegacao.tsx` (classe do `<nav>`), `frontend/next/src/app/jogos/Feed.tsx` (linha do `<aside>`)
- Create: `frontend/next/src/components/marca/Cabecalho.tsx`
- Test: `frontend/next/tests/unit/formato.test.ts` (só acrescenta), `frontend/next/tests/unit/Cabecalho.test.tsx` (novo), `frontend/next/e2e/cabecalho.spec.ts` (novo)

**Interfaces:**
- Produces: `fmtDataPorExtenso(agora: Date): string` → "terça, 22 de setembro"; `proximaMeiaNoiteBrt(agora: Date): Date`; `MARCA = { parte1: "sportsbank", parte2: "zu", nome: "sportsbankzu", ariaLink: "sportsbankzu, ir para os jogos" }`; componente `Cabecalho()` cliente; constante CSS de altura: 56 px (`h-14`, `pt-14`, `top-14`).

- [ ] **Step 1: Testes do formatador (acrescentar em `tests/unit/formato.test.ts`):**

```ts
import { fmtDataPorExtenso, proximaMeiaNoiteBrt } from "@/lib/formato";
describe("data por extenso em BRT (#262, spec §1)", () => {
  it("terca 22/09 as 23:30 BRT (02:30Z do dia 23) ainda e terca, 22", () => {
    expect(fmtDataPorExtenso(new Date("2026-09-23T02:30:00Z"))).toBe("terça, 22 de setembro");
  });
  it("as 00:00 BRT (03:00Z) vira quarta, 23; domingo e sabado sem '-feira'", () => {
    expect(fmtDataPorExtenso(new Date("2026-09-23T03:00:00Z"))).toBe("quarta, 23 de setembro");
    expect(fmtDataPorExtenso(new Date("2026-09-20T15:00:00Z"))).toBe("domingo, 20 de setembro");
  });
  it("proxima meia-noite BRT e o proximo 03:00Z", () => {
    expect(proximaMeiaNoiteBrt(new Date("2026-09-23T02:30:00Z")).toISOString()).toBe("2026-09-23T03:00:00.000Z");
    expect(proximaMeiaNoiteBrt(new Date("2026-09-23T03:00:00Z")).toISOString()).toBe("2026-09-24T03:00:00.000Z");
  });
});
```

- [ ] **Step 2: Rodar** → FAIL. **Implementar** em `formato.ts`:

```ts
/** #262 — "terça, 22 de setembro" no dia do operador (BRT). Sem ano, sem "-feira". */
export function fmtDataPorExtenso(agora: Date): string {
  const partes = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: FUSO }).formatToParts(agora);
  const pegar = (t: string) => partes.find((p) => p.type === t)?.value ?? "";
  return `${pegar("weekday").replace("-feira", "")}, ${pegar("day")} de ${pegar("month")}`;
}
/** #262 — proximo 00:00 BRT (= 03:00Z, UTC-3 fixo), para o cabecalho virar a data sem refresh. */
export function proximaMeiaNoiteBrt(agora: Date): Date {
  const DESLOC = 3 * 3600_000;
  const brt = new Date(agora.getTime() - DESLOC);
  const meiaNoiteBrt = Date.UTC(brt.getUTCFullYear(), brt.getUTCMonth(), brt.getUTCDate() + 1);
  return new Date(meiaNoiteBrt + DESLOC);
}
```

Rodar → PASS.

- [ ] **Step 3: Copy.** Em `copy.ts`, acrescentar:

```ts
/** #262 — marca no cabecalho (spec §1): nome inteiro sempre; "zu" e a parte em teal. */
export const MARCA = { parte1: "sportsbank", parte2: "zu", nome: "sportsbankzu", ariaLink: "sportsbankzu, ir para os jogos" } as const;
```

- [ ] **Step 4: Teste do cabeçalho (vermelho)** — `tests/unit/Cabecalho.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { Cabecalho } from "@/components/marca/Cabecalho";

describe("Cabecalho (#262, spec §1)", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date("2026-09-23T02:59:00Z")); });
  afterEach(() => vi.useRealTimers());
  it("banner com a marca inteira, link para /jogos e a data BRT", () => {
    render(<Cabecalho />);
    const banner = screen.getByRole("banner");
    const link = screen.getByRole("link", { name: "sportsbankzu, ir para os jogos" });
    expect(link).toHaveAttribute("href", "/jogos");
    expect(link.textContent).toBe("sportsbankzu");
    expect(banner).toHaveTextContent("terça, 22 de setembro");
  });
  it("vira a data no cliente a meia-noite BRT, sem refresh", () => {
    render(<Cabecalho />);
    act(() => { vi.advanceTimersByTime(61_000); });
    expect(screen.getByRole("banner")).toHaveTextContent("quarta, 23 de setembro");
  });
});
```

- [ ] **Step 5: Rodar** → FAIL. **Implementar** `src/components/marca/Cabecalho.tsx`:

```tsx
"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fonteMarca } from "@/components/marca/fonteMarca";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";
import { fmtDataPorExtenso, proximaMeiaNoiteBrt } from "@/lib/formato";
import { MARCA } from "@/lib/copy";

/** #262 — barra fixa de 56 px em todas as rotas: marca + data do operador (BRT).
 * O carimbo de leitura NAO mora aqui (spec §1): e da rota. */
export function Cabecalho() {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const t = setTimeout(() => setAgora(new Date()), proximaMeiaNoiteBrt(agora).getTime() - agora.getTime() + 1000);
    return () => clearTimeout(t);
  }, [agora]);
  return (
    <header role="banner" className="fixed inset-x-0 top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--sb-linha)] bg-[var(--sb-painel)] px-4">
      <Link href="/jogos" aria-label={MARCA.ariaLink} className="sb-foco flex items-center gap-2 no-underline">
        <MonogramaSBZ tamanho={22} />
        <span className={`${fonteMarca.className} text-[22px] font-bold leading-none tracking-tight text-[var(--sb-texto)]`}>{MARCA.parte1}<span className="text-[var(--sb-marca)]">{MARCA.parte2}</span></span>
      </Link>
      <span className="hidden text-[14px] text-[var(--sb-texto-apagado)] sm:block">{fmtDataPorExtenso(agora)}</span>
    </header>
  );
}
```

Rodar → PASS (o `useEffect` agenda 61 s no cenário; `advanceTimersByTime(61_000)` dispara e re-renderiza).

- [ ] **Step 6: Layout e geometria.** `layout.tsx`: importar `Cabecalho`; dentro de `<ThemeProvider>`, antes do `<div className="min-h-screen …">`, inserir `<Cabecalho />`; o `div` vira `className="min-h-screen bg-[var(--sb-tinta)] pt-14 lg:flex"`. `Navegacao.tsx`, `<nav>`: `className="lg:sticky lg:top-14 lg:h-[calc(100vh-56px)] lg:w-[200px] lg:self-start lg:overflow-y-auto lg:border-r lg:border-[var(--sb-linha)] lg:bg-[var(--sb-painel)]"` (sai `lg:self-stretch`). `Feed.tsx`, `<aside>`: `className="sticky top-[calc(56px+1rem)] self-start lg:max-h-[calc(100vh-56px-2rem)] lg:overflow-y-auto"`. `tests/unit/Navegacao.test.tsx` não afirma classes de layout (conferir).

- [ ] **Step 7: E2E (vermelho antes do layout, verde depois)** — `e2e/cabecalho.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { stub } from "./helpers/stub";

// #262 — cabecalho fixo em todas as rotas, inclusive hero/login/register; data BRT; marca inteira.
for (const rota of ["/", "/jogos", "/banca", "/desempenho", "/glossario", "/login", "/register"]) {
  test(`banner com a marca em ${rota}`, async ({ page }) => {
    await stub(page);
    await page.goto(rota);
    const banner = page.getByRole("banner");
    await expect(banner).toBeVisible();
    await expect(banner.getByRole("link", { name: "sportsbankzu, ir para os jogos" })).toHaveText("sportsbankzu");
    const box = await banner.boundingBox();
    expect(box?.y).toBe(0); expect(Math.round(box?.height ?? 0)).toBe(56);
  });
}
test("a data vem por extenso em BRT e nao ha segundo 'sportsbankzu' na pagina do hero", async ({ page }) => {
  await stub(page);
  await page.goto("/");
  await expect(page.getByRole("banner")).toContainText(/^(domingo|segunda|terça|quarta|quinta|sexta|sábado), \d{1,2} de [a-zç]+$/);
  expect(await page.getByText("sportsbankzu", { exact: true }).count()).toBe(1);
});
test("painel de detalhe fica abaixo do cabecalho ao rolar (1440x700)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  await stub(page, { feed: "multi" });
  await page.goto("/jogos");
  await page.locator("article h2 a").first().click();
  await page.mouse.wheel(0, 600);
  const box = await page.getByRole("complementary", { name: "detalhe do jogo" }).boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(56);
});
```

Rodar `CI=1 npx playwright test e2e/cabecalho.spec.ts --project=chromium` (build de produção) → PASS. `npx playwright test e2e/cabecalho.spec.ts --project=mobile` → PASS (a data está oculta no celular; o teste da data roda no desktop — se falhar no mobile por isso, envolver com `test.skip(isMobile)` do fixture do Playwright).

- [ ] **Step 8: Portão + visual anexado (diffs esperados: todas as telas ganham 56 px no topo).** Screenshot 390 e 1440 do `/jogos` para o relatório.

- [ ] **Step 9: Commit**
```bash
git add src/lib/formato.ts src/lib/copy.ts src/components/marca/Cabecalho.tsx src/app/layout.tsx src/components/nav/Navegacao.tsx src/app/jogos/Feed.tsx tests/unit/formato.test.ts tests/unit/Cabecalho.test.tsx e2e/cabecalho.spec.ts
git commit -m "feat(front): cabecalho fixo com marca e data BRT; sidebar e painel abaixo dele (#262)"
```

---

### Task 4: Carimbo de leitura no topo do conteúdo de `/jogos` e `/desempenho`

**Files:**
- Modify: `frontend/next/src/lib/copy.ts`, `frontend/next/src/app/jogos/Feed.tsx`, `frontend/next/src/app/desempenho/Painel.tsx`
- Test: `frontend/next/tests/unit/copy.test.ts` (só acrescenta), `frontend/next/e2e/cabecalho.spec.ts` (só acrescenta)

**Interfaces:**
- Produces: `CARIMBO = { lidoAs: (hora: string) => \`lido às ${hora}\` }`. No Feed, `carimbo` (estado já existente, `fmtHora`) renderizado acima de `DiaTabs` quando não nulo. No Painel de desempenho, estado novo `carimbo: string | null` preenchido com `fmtHora(new Date().toISOString())` no sucesso da carga.

- [ ] **Step 1: Teste da copy** (acrescentar em `copy.test.ts`): `it("#262 carimbo", () => { expect(C.CARIMBO.lidoAs("19:04")).toBe("lido às 19:04"); });` → FAIL → implementar `export const CARIMBO = { lidoAs: (hora: string) => \`lido às ${hora}\` } as const;` → PASS. `npm run lint:accents` verde ("às" com crase; "lido" sem acento é correto).

- [ ] **Step 2: Feed.** Em `Feed.tsx`, importar `CARIMBO` e, dentro do primeiro `<div>` do grid, antes de `<DiaTabs …/>`, inserir:

```tsx
        {carimbo && <p className="tnum text-right text-[12px] text-[var(--sb-texto-apagado)]" data-carimbo>{CARIMBO.lidoAs(carimbo)}</p>}
```

- [ ] **Step 3: Painel de desempenho.** Em `Painel.tsx`, no componente que carrega `dados` (linha ~57): `const [carimbo, setCarimbo] = useState<string | null>(null);` e, no ramo de sucesso do `useEffect` que faz `setDados(...)`, acrescentar `setCarimbo(fmtHora(new Date().toISOString()));` (importar `fmtHora` de `@/lib/formato` e `CARIMBO` de `@/lib/copy`). No JSX raiz do painel, primeira linha: `{carimbo && <p className="tnum text-right text-[12px] text-[var(--sb-texto-apagado)]" data-carimbo>{CARIMBO.lidoAs(carimbo)}</p>}`.

- [ ] **Step 4: E2E** (acrescentar em `e2e/cabecalho.spec.ts`):

```ts
test.describe("carimbo de leitura e da rota, nao do cabecalho (#262 §1)", () => {
  for (const rota of ["/jogos", "/desempenho"]) {
    test(`presente em ${rota}`, async ({ page }) => {
      await stub(page); await page.goto(rota);
      await expect(page.locator("[data-carimbo]")).toHaveText(/^lido às \d{2}:\d{2}$/);
      await expect(page.getByRole("banner").locator("[data-carimbo]")).toHaveCount(0);
    });
  }
  for (const rota of ["/banca", "/glossario", "/"]) {
    test(`ausente em ${rota}`, async ({ page }) => {
      await stub(page); await page.goto(rota);
      await expect(page.locator("[data-carimbo]")).toHaveCount(0);
    });
  }
});
```

Rodar chromium (prod) → PASS.

- [ ] **Step 5: Portão + commit**
```bash
git add src/lib/copy.ts src/app/jogos/Feed.tsx src/app/desempenho/Painel.tsx tests/unit/copy.test.ts e2e/cabecalho.spec.ts
git commit -m "feat(front): carimbo 'lido as' no topo de /jogos e /desempenho (#262)"
```

---

### Task 5: Carregamento por camadas e esqueleto honesto

**Files:**
- Create: `frontend/next/src/lib/lotesFeed.ts`, `frontend/next/src/components/feed/EsqueletoCard.tsx`, `frontend/next/src/components/detalhe/EsqueletoDetalhe.tsx`, `frontend/next/src/app/desempenho/EsqueletoDesempenho.tsx`
- Modify: `frontend/next/src/lib/api.ts` (export `numeroDeLotes`), `frontend/next/src/lib/copy.ts` (`CARREGANDO`), `frontend/next/src/app/globals.css` (`.sb-esqueleto`), `frontend/next/src/app/jogos/Feed.tsx`, `frontend/next/src/app/jogos/[id]/page.tsx`, `frontend/next/src/app/desempenho/Painel.tsx`
- Test: `frontend/next/tests/unit/lotesFeed.test.ts`, `frontend/next/tests/unit/copy.test.ts` (acrescenta), `frontend/next/tests/unit/EsqueletoCard.test.tsx`, `frontend/next/e2e/carregando.spec.ts`

**Interfaces:**
- Consumes: `getMatchesByLeague(leagues, date, onBatchReady?)` de `lib/api.ts` (chama `onBatchReady(res)` uma vez por lote; hoje `LEAGUES_PER_BATCH = 1`).
- Produces: `numeroDeLotes(nLigas: number): number` (em `api.ts`, = `Math.ceil(nLigas / LEAGUES_PER_BATCH)`); `mesclarLote(atual: JogoView[], novas: JogoView[]): JogoView[]` (dedup por `id`, a nova substitui a antiga, ordena em-jogo primeiro e depois por `kickoffIso`); `quantosEsqueletos(pendentes: number): number` (= `Math.max(0, Math.min(3, pendentes))`); `CARREGANDO = { buscando(dia), progresso(dia, lidas, n), desempenho }`; `EsqueletoCard()`, `EsqueletoDetalhe()`, `EsqueletoDesempenho()` — todos `aria-hidden="true"`.

- [ ] **Step 1: Testes puros (vermelho)** — `tests/unit/lotesFeed.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { mesclarLote, quantosEsqueletos } from "@/lib/lotesFeed";
import type { JogoView } from "@/lib/jogoView";
const v = (id: string, kickoffIso: string, estado: JogoView["estado"] = "nada") => ({ id, kickoffIso, estado } as unknown as JogoView);

describe("lotes do feed (#262, spec §3)", () => {
  it("soma lotes, deduplica por id (o novo substitui) e ordena em jogo primeiro, depois por kickoff", () => {
    const a = [v("x", "2026-09-22T20:00:00Z"), v("y", "2026-09-22T18:00:00Z")];
    const b = [v("z", "2026-09-22T19:00:00Z", "em_jogo"), v("x", "2026-09-22T20:00:00Z", "vale")];
    const r = mesclarLote(a, b);
    expect(r.map((j) => j.id)).toEqual(["z", "y", "x"]);
    expect(r.find((j) => j.id === "x")!.estado).toBe("vale");
  });
  it("esqueletos = min(3, pendentes), nunca negativo", () => {
    expect(quantosEsqueletos(13)).toBe(3); expect(quantosEsqueletos(2)).toBe(2); expect(quantosEsqueletos(0)).toBe(0); expect(quantosEsqueletos(-1)).toBe(0);
  });
});
```

E em `copy.test.ts`:

```ts
  it("#262 carregando: progresso com numeros dinamicos e sem latencia na frase", () => {
    expect(C.CARREGANDO.buscando("hoje")).toBe("buscando os jogos de hoje");
    expect(C.CARREGANDO.buscando("amanha")).toBe("buscando os jogos de amanhã");
    expect(C.CARREGANDO.progresso("ontem", 4, 13)).toBe("buscando os jogos de ontem: 4 de 13 ligas lidas");
    expect(C.CARREGANDO.progresso("hoje", 1, 1)).toBe("buscando os jogos de hoje: 1 de 1 liga lida");
    expect(C.CARREGANDO.desempenho).toBe("buscando o desempenho");
    expect(JSON.stringify(C.CARREGANDO)).not.toMatch(/segundo/);
  });
```

- [ ] **Step 2: Rodar** → FAIL. **Implementar** `src/lib/lotesFeed.ts`:

```ts
import type { JogoView } from "@/lib/jogoView";
/** #262 — soma um lote ao feed: dedup por id (novo substitui), em jogo primeiro, depois kickoff. */
export function mesclarLote(atual: JogoView[], novas: JogoView[]): JogoView[] {
  const porId = new Map(atual.map((j) => [j.id, j]));
  for (const j of novas) porId.set(j.id, j);
  return Array.from(porId.values())
    .sort((a, b) => Number(b.estado === "em_jogo") - Number(a.estado === "em_jogo") || a.kickoffIso.localeCompare(b.kickoffIso));
}
/** #262 — cards-esqueleto na tela = min(3, lotes pendentes). */
export function quantosEsqueletos(pendentes: number): number {
  return Math.max(0, Math.min(3, pendentes));
}
```

Em `copy.ts`:

```ts
/** #262 — carregamento honesto (spec §3): nunca um numero de latencia; numeros sempre calculados. */
const DIA_EXTENSO = { ontem: "ontem", hoje: "hoje", amanha: "amanhã" } as const;
export const CARREGANDO = {
  buscando: (dia: "ontem" | "hoje" | "amanha") => `buscando os jogos de ${DIA_EXTENSO[dia]}`,
  progresso: (dia: "ontem" | "hoje" | "amanha", lidas: number, n: number) =>
    `buscando os jogos de ${DIA_EXTENSO[dia]}: ${lidas} de ${n} ${n === 1 ? "liga lida" : "ligas lidas"}`,
  desempenho: "buscando o desempenho",
} as const;
```

Em `api.ts`, após `MAX_CONCURRENT`: `export function numeroDeLotes(nLigas: number): number { return Math.ceil(nLigas / LEAGUES_PER_BATCH); }`. Rodar → PASS. `npm run lint:accents` verde.

- [ ] **Step 3: Esqueleto (teste vermelho)** — `tests/unit/EsqueletoCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { EsqueletoCard } from "@/components/feed/EsqueletoCard";
describe("EsqueletoCard (#262, spec §3)", () => {
  it("e decorativo, usa a superficie sb-card e quatro blocos", () => {
    const { container } = render(<EsqueletoCard />);
    const raiz = container.firstElementChild!;
    expect(raiz).toHaveAttribute("aria-hidden", "true");
    expect(raiz.className).toContain("sb-card");
    expect(raiz.querySelectorAll(".sb-esqueleto")).toHaveLength(4);
  });
});
```

**Implementar** `src/components/feed/EsqueletoCard.tsx`:

```tsx
/** #262 — card-esqueleto (spec §3): decorativo; so o role="status" da lista anuncia. */
export function EsqueletoCard() {
  return (
    <div aria-hidden="true" className="sb-card space-y-3 p-4">
      <div className="sb-esqueleto h-[18px] w-[55%]" />
      <div className="sb-esqueleto h-[72px] w-full" />
      <div className="sb-esqueleto h-[14px] w-[70%]" />
      <div className="sb-esqueleto h-[14px] w-[45%]" />
    </div>
  );
}
```

`globals.css`, após `.sb-card`:

```css
/* #262 — blocos do esqueleto: apagado a 30 %, pulsando devagar; sem movimento com reduced-motion. */
.sb-esqueleto { border-radius: 3px; background: var(--sb-texto-apagado); opacity: 0.3; animation: sb-pulsa 1.6s ease-in-out infinite; }
@keyframes sb-pulsa { 0%, 100% { opacity: 0.3; } 50% { opacity: 0.15; } }
@media (prefers-reduced-motion: reduce) { .sb-esqueleto { animation: none; } }
```

`EsqueletoDetalhe.tsx` (mesma forma: `aria-hidden`, `sb-card p-4`, blocos: título 22 px 60 %, talão 72 px, linha 14 px 80 %, tabela 120 px) e `EsqueletoDesempenho.tsx` (`aria-hidden`, três blocos `sb-card` em coluna: 48 px, 120 px, 160 px, com `<p role="status" className="sr-only">{CARREGANDO.desempenho}</p>` ao lado, fora do `aria-hidden`). Rodar → PASS.

- [ ] **Step 4: Feed por camadas.** Em `Feed.tsx`, importar `numeroDeLotes` de `@/lib/api`, `mesclarLote, quantosEsqueletos` de `@/lib/lotesFeed`, `CARREGANDO` de `@/lib/copy`, `EsqueletoCard`. Estados novos: `const [lotesLidos, setLotesLidos] = useState(0); const [mostrarProgresso, setMostrarProgresso] = useState(false); const timerProgresso = useRef<ReturnType<typeof setTimeout> | null>(null);`. Substituir o corpo do ramo não-ontem de `carregar` por:

```tsx
    setCarregando(true); setLotesLidos(0);
    const temLeituraBoa = ultimoBom.current.length > 0;
    setMostrarProgresso(false);
    if (timerProgresso.current) clearTimeout(timerProgresso.current);
    timerProgresso.current = setTimeout(() => { if (minha === geracao.current) setMostrarProgresso(true); }, 1500);
    const agora = new Date();
    let acumulado: JogoView[] = temLeituraBoa ? ultimoBom.current : [];
    let lidos = 0;
    try {
      const res = await getMatchesByLeague(ligas.map((l) => l.id).join(","), date, (lote) => {
        if (minha !== geracao.current) return;
        lidos += 1; setLotesLidos(lidos);
        const novas = deduplicateMatches((lote.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)))
          .map((m: Match) => toJogoView(m, agora));
        // Sem leitura boa, a lista cresce lote a lote (spec §3, "por camadas"); com leitura boa,
        // a lista antiga fica na tela ate a carga terminar (troca sem piscar).
        if (!temLeituraBoa) { acumulado = mesclarLote(acumulado, novas); setJogos(acumulado); }
        else acumulado = mesclarLote(lidos === 1 ? [] : acumulado, novas);
      });
      if (minha !== geracao.current) return;
      if (res._error) throw new Error(res._error.message);
      let views = acumulado;
      if (url.dia === "hoje" && views.some((v) => v.estado === "ontem_sem_desfecho")) {
        const rLedger = await getLedgerDia(diaISOHoje(agora));
        if (minha !== geracao.current) return;
        if (rLedger.ok) views = aplicarDesfechosDeHoje(views, rLedger.dados.picks);
      }
      ultimoBom.current = views; setJogos(views); setCarimbo(fmtHora(agora.toISOString())); setErro(false);
    } catch {
      if (minha !== geracao.current) return;
      setErro(true); setJogos(ultimoBom.current);
    } finally {
      if (minha === geracao.current) { setCarregando(false); if (timerProgresso.current) clearTimeout(timerProgresso.current); setMostrarProgresso(false); }
    }
```

Atenção: `deduplicateMatches` continua sendo aplicado por lote; a dedup ENTRE lotes é por `id` em `mesclarLote` (o dedup por time+data de `deduplicateMatches` só vale dentro do lote — registrar no relatório que um mesmo jogo vindo de duas ligas diferentes não é caso real, pois cada liga tem seus jogos). No JSX, depois do `.map` dos cards e dentro do mesmo `<div className="space-y-3 py-3">`:

```tsx
          {carregando && ultimoBom.current.length === 0 && (
            <div aria-busy="true" data-esqueleto>
              <p role="status" className="sr-only">{mostrarProgresso ? CARREGANDO.progresso(url.dia, lotesLidos, numeroDeLotes(ligas.length)) : CARREGANDO.buscando(url.dia)}</p>
              <div className="space-y-3">{Array.from({ length: quantosEsqueletos(numeroDeLotes(ligas.length) - lotesLidos) }, (_, i) => <EsqueletoCard key={i} />)}</div>
              {mostrarProgresso && <p className="mt-2 text-[13px] text-[var(--sb-texto-apagado)]" data-progresso>{CARREGANDO.progresso(url.dia, lotesLidos, numeroDeLotes(ligas.length))}</p>}
            </div>
          )}
```

A condição do vazio já é `!carregando && visiveis.length === 0 && !erro` (só com todos os lotes). Conferir que a aba Ontem (`carregarOntem`) também mostra esqueleto: envolver `carregarOntem` com o mesmo `setCarregando(true)`/timer (uma chamada só; `lotesLidos` fica 0 e `numeroDeLotes(1)`), usando `CARREGANDO.buscando("ontem")`.

- [ ] **Step 5: `/jogos/[id]` e `/desempenho`.** Em `src/app/jogos/[id]/page.tsx` (leitura antes de editar), onde hoje o componente retorna `null`/texto enquanto busca o jogo, renderizar `<EsqueletoDetalhe />` mais `<p role="status" className="sr-only">{CARREGANDO.buscando("hoje")}</p>`; em `Painel.tsx`, onde `dados === null && !erro`, renderizar `<EsqueletoDesempenho />`. Se `[id]/page.tsx` não tiver estado de carga explícito (jogo vem síncrono de cache), registrar no relatório e não inventar um.

- [ ] **Step 6: E2E de honestidade** — `e2e/carregando.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import feed from "./fixtures/feed.json";
import { stub } from "./helpers/stub";

// #262 §3 — lotes chegam em tempos diferentes; "Nenhum jogo" nunca antes do ultimo lote.
async function feedPorCamadas(page: import("@playwright/test").Page) {
  await stub(page, { vazio: true });
  await page.route("**/api/matches/fetch**", async (route) => {
    const u = new URL(route.request().url()); const liga = u.searchParams.get("leagues") ?? "";
    const espera = liga === "premier-league" ? 1000 : liga === "championship" ? 3000 : 5000;
    await new Promise((r) => setTimeout(r, espera));
    const corpo = liga === "premier-league" ? { matches: feed.matches.filter((m) => m.leagueId === "premier-league") } : { matches: [] };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(corpo) });
  });
}

test("cards do primeiro lote aparecem antes dos demais; progresso conta; vazio so no fim", async ({ page }) => {
  await feedPorCamadas(page);
  await page.goto("/jogos");
  await expect(page.locator("[data-esqueleto]")).toBeVisible();
  await expect(page.locator("[data-progresso]")).toContainText(/buscando os jogos de hoje: \d+ de \d+ ligas lidas/, { timeout: 2500 });
  await expect(page.locator("article").first()).toBeVisible({ timeout: 2500 });
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  await page.waitForTimeout(1500);
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  await expect(page.locator("[data-esqueleto]")).toHaveCount(0, { timeout: 8000 });
});
test("todos os lotes vazios: 'Nenhum jogo' so depois do ultimo lote", async ({ page }) => {
  await stub(page, { vazio: true });
  await page.route("**/api/matches/fetch**", async (route) => { await new Promise((r) => setTimeout(r, 2000)); await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }); });
  await page.goto("/jogos");
  await expect(page.locator("[data-esqueleto]")).toBeVisible();
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toHaveCount(0);
  await expect(page.getByText(/Nenhum jogo nas ligas/)).toBeVisible({ timeout: 15000 });
  await expect(page.locator("[data-esqueleto]")).toHaveCount(0);
});
test("prefers-reduced-motion desliga a animacao do esqueleto", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await feedPorCamadas(page);
  await page.goto("/jogos");
  const nome = await page.locator(".sb-esqueleto").first().evaluate((el) => getComputedStyle(el).animationName);
  expect(nome).toBe("none");
});
```

Nota: o fixture `feed.json` precisa ter `leagueId: "premier-league"` em ao menos um jogo — conferir com `grep -c premier-league e2e/fixtures/feed.json`; se não tiver, usar a liga que tiver (`championship`) trocando os dois nomes no helper. Rodar chromium (prod) → PASS; mobile → PASS.

- [ ] **Step 7: Portão + screenshots (390/1440 do esqueleto com a frase de progresso, capturados com o feed atrasado) + commit**
```bash
git add src/lib/lotesFeed.ts src/lib/api.ts src/lib/copy.ts src/app/globals.css src/components/feed/EsqueletoCard.tsx src/components/detalhe/EsqueletoDetalhe.tsx src/app/desempenho/EsqueletoDesempenho.tsx src/app/jogos/Feed.tsx src/app/jogos/[id]/page.tsx src/app/desempenho/Painel.tsx tests/unit/lotesFeed.test.ts tests/unit/copy.test.ts tests/unit/EsqueletoCard.test.tsx e2e/carregando.spec.ts
git commit -m "feat(front): feed por camadas com esqueleto honesto e frase de progresso (#262)"
```

---

### Task 6: Estados vazios com o monograma

**Files:**
- Create: `frontend/next/src/components/marca/EstadoVazio.tsx`
- Modify: `frontend/next/src/app/jogos/Feed.tsx` (bloco `VAZIOS.diaSemJogos`), `frontend/next/src/components/marca/Hero.tsx` (bloco `HERO.semTalao`), `frontend/next/src/app/desempenho/Painel.tsx` (bloco `DESEMPENHO.semPicksFechados`), `frontend/next/src/app/banca/page.tsx` ou o componente que mostra a banca indefinida (localizar com `grep -rn "indefinida\|definaBanca" src/app/banca src/components`)
- Test: `frontend/next/tests/unit/EstadoVazio.test.tsx`

**Interfaces:**
- Produces: `EstadoVazio({ children }: { children: React.ReactNode })` — `<div className="my-6 grid justify-items-center gap-2 text-center text-[14px] text-[var(--sb-texto-apagado)]"><MonogramaSBZ tamanho={48} apagado />{children}</div>`. Os textos existentes (e seus links) passam a ser `children`; nenhuma frase muda.

- [ ] **Step 1: Teste (vermelho)** — `tests/unit/EstadoVazio.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EstadoVazio } from "@/components/marca/EstadoVazio";
describe("EstadoVazio (#262, spec §4)", () => {
  it("monograma apagado e decorativo acima do texto; o texto e o mesmo", () => {
    const { container } = render(<EstadoVazio><p>Nenhum jogo nas ligas escolhidas em 22/09.</p></EstadoVazio>);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg.querySelector("text")).toHaveAttribute("fill", "var(--sb-texto-apagado)");
    expect(screen.getByText("Nenhum jogo nas ligas escolhidas em 22/09.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implementar** o componente conforme a interface; rodar → PASS.

- [ ] **Step 3: Usos.** Feed: envolver o `<p className="my-6 …">{VAZIOS.diaSemJogos(...)} <Link…/></p>` em `<EstadoVazio>` (o `<p>` perde `my-6`, mantém o resto). Hero: o mesmo para a frase `HERO.semTalao`. Painel de desempenho: `DESEMPENHO.semPicksFechados`. Banca indefinida: o bloco que mostra `DESEMPENHO.definaBanca` ou o texto de banca indefinida em `/banca`. Os testes existentes desses componentes (`Hero.test.tsx`, `detalhe.test.tsx`, etc.) afirmam texto, não estrutura — rodar a suíte inteira; se algum quebrar por seletor estrutural, PARAR e escalar.

- [ ] **Step 4: Prova.** `CI=1 npx playwright test e2e/jogos.spec.ts e2e/hero-redirect.spec.ts e2e/desempenho*.spec.ts --project=chromium` verde; screenshot 390/1440 do `/jogos` com `stub(page, { vazio: true })` para o relatório; visual anexado (diffs esperados em banca-indefinida).

- [ ] **Step 5: Commit**
```bash
git add src/components/marca/EstadoVazio.tsx src/app/jogos/Feed.tsx src/components/marca/Hero.tsx src/app/desempenho/Painel.tsx src/app/banca tests/unit/EstadoVazio.test.tsx
git commit -m "feat(front): estados vazios com o monograma SBZ (#262)"
```

---

### Task 7: Referências visuais, axe, REGISTRO #262 e fechamento (controller)

**Files:**
- Modify (só após approve por imagem do dono): `frontend/next/e2e/visual.spec.ts-snapshots/*-win32.png`
- Modify: `docs/REGISTRO_CORRECOES.md`, `docs/INDICE_REGRAS.md`, `docs/REGRAS_ATIVAS.md`, espelhos em `c:\painel_apostas\sportsbank-pro\docs\`

- [ ] **Step 1:** Suíte completa sobre o último commit da Task 6 (Global Constraints) + `npx playwright test --project=mobile` + axe (`e2e/a11y.spec.ts`) — tudo verde, exceto o visual, que gera as 9 novas capturas em `test-results/`.
- [ ] **Step 2:** Página de approve para o dono (mesmo molde das fases 4/5): nova × referência × diff por tela, com o checklist da spec §2/§3 (um bold por tela; teal só onde a §2 lista; talão intocado; chip selecionado ≠ hover; esqueleto e frase de progresso; monograma nos vazios). Esperar o approve.
- [ ] **Step 3:** Com o approve: `CI=1 npx playwright test --project=visual-desktop --project=visual-mobile --update-snapshots`, commit separado `test(front): referencias visuais da identidade (#262, approve do dono em <data>)`.
- [ ] **Step 4:** REGISTRO `## 262 — Identidade visual: cabeçalho, cor de marca, profundidade, carregamento por camadas e arte` com: problema (crítica do dono, telas), causa (spec da reformulação escolheu sobriedade sem marca e sem estado de carregamento), correções por camada (uma linha por task com hash), contrastes medidos (Task 1), desvios declarados (SVG com `<text>`; favicon "S" se aplicado; `[id]` sem estado de carga se for o caso), prova (placar unit/e2e/visual, screenshots), Etapa 2-bis (nenhum campo escrito; consumidor novo: nenhum), lição. INDICE: linha 262. REGRAS_ATIVAS: regra permanente "carregamento honesto: nenhum estado vazio por tempo; esqueleto só sem leitura boa; nenhum número de latência na copy (#262)". M5 do #258: marcado como fechado por emenda.
- [ ] **Step 5:** Espelhar os 4 docs, commit `docs: REGISTRO #262 — identidade visual concluída`, push único do lote (Tasks 1–7), CI verde, validação em produção: `role=banner` em `/`, `/jogos`, `/banca`; favicon 200; esqueleto visível numa primeira carga sem cache (headless, throttling de rede) e "Nenhum jogo" ausente durante a carga.

---

## Auto-revisão

**Cobertura da spec:** §1 cabeçalho, data BRT, virada de dia, carimbo por rota, geometria → Tasks 3 e 4. §2 token, teal em marca/nav/chip/sublinhado/card selecionado, chip não selecionado, `.sb-card`, talão intocado, contrastes → Task 1 (Detalhe e CardJogo) e 7 (registro). §3 leitura boa vs esqueleto, por camadas com `onBatchReady`, `min(3, pendentes)`, frase de progresso aos 1,5 s, timeout de 55 s → erro atual, vazio só no fim, `aria-hidden`/`aria-busy`/status, reduced-motion, detalhe e desempenho, aba Ontem → Task 5. §4 monograma SBZ, ícones, estados vazios, sem ilustração no feed → Tasks 2 e 6. §5 fora do escopo e M5 → Task 7 (registro). §6 arquivos → mapa. §7 validação → cada task + Task 7. §8 ordem → Tasks 1–7. §9 decisões → Task 7 registra.

**Placeholders:** nenhum "TBD"; os únicos condicionais são decisões previstas na spec (favicon "S"; `[id]` sem estado de carga), com instrução de registrar.

**Consistência de nomes:** `MonogramaSBZ` (Tasks 2, 3, 6); `CARREGANDO.buscando/progresso/desempenho` (Task 5; Task 5 Step 5 usa `buscando`); `CARIMBO.lidoAs` (Task 4); `MARCA.parte1/parte2/ariaLink` (Task 3); `mesclarLote`/`quantosEsqueletos`/`numeroDeLotes` (Task 5); `.sb-card` (Tasks 1, 5); `.sb-esqueleto` (Task 5); `data-carimbo`, `data-esqueleto`, `data-progresso` (Tasks 4, 5 e seus e2e).
