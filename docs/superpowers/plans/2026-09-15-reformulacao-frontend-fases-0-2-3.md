# Reformulação do frontend — plano 1 (fases 0, 2 e 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar as guardas de design (fase 0), o mapeador puro `jogoView` (fase 2) e o feed novo em `/jogos` com talão, detalhe e banca (fase 3), ao lado do dashboard atual, sem tocar em cálculo do pipeline.

**Architecture:** Tokens e fontes entram em `globals.css` com testes que os travam (contraste, família, `tnum`). O payload de `/fixtures` é mapeado por uma função pura (`lib/jogoView.ts`) que deriva um enum de estado e escolhe o talão; os componentes de `components/feed/` e `components/detalhe/` só renderizam esse tipo. Todo estado vive na URL; a banca vive no `localStorage` com estado "indefinida".

**Tech Stack:** Next.js 15 (App Router), React 18, Tailwind 3, `next/font/google`, Vitest (novo, unit), Playwright (E2E + regressão visual + axe via `@axe-core/playwright`, novo).

**Spec:** `docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md` — o plano argumenta a partir dela; executores leem os dois.

**Planos irmãos:** fase 1 (backend: `/ledger/dia`, `/ledger/agregado`, contrato `fair_odd`/`book_odd`, prompt Mistral) tem plano próprio; fases 4–6 ganham o terceiro plano quando este e o da fase 1 fecharem.

## Global Constraints

- Tokens (spec §2), hex exatos: `tinta #15161A`, `painel #22242B`, `linha #2C2E36`, `hover #262830`, `texto #E6E4DD`, `texto-apagado #93959C`, `talao #E3D9AE`, `tinta-do-talao #1B1710`, `tinta-apoiada #4A4436`, `confianca #4FB3BF`, `contra-texto #E8665A`, `contra #E0533F`. Sem verde. Sem sombras.
- `confianca` **nunca** dentro do talão. Cor nunca é a única portadora de estado: `✓` acerto, `×` erro, `↓` abaixo. Recomendação não tem glifo.
- Fontes: Zilla Slab (veredito, times, stake, títulos), Source Sans 3 (corpo e **toda coluna de números**, `tabular-nums`), Barlow Condensed **só** em `src/components/marca/` e `src/app/page.tsx`. `Inter` sai. Escala 13·14·16·18·22·28·36.
- Copy pt-BR acentuada (`npm run lint:accents` verde); vírgula decimal; "MLS, 20:30" (sem ponto médio); sem eyebrow em caixa alta, sem mono para rótulos, sem seta em botão.
- Talão = maior `edge` entre `classification ∈ {SAFE, NEUTRO_QUALIFICADO}`; empate → maior `calibrated_probability`. "vale a partir de" = `fair_odd`; "mercado paga" = `book_odd`.
- Estado na URL (`?dia=`, `?liga=`, `?jogo=`); único estado fora dela: a banca.
- Nenhuma mudança em `backend/` neste plano. Nenhuma mudança visual no dashboard atual (rotas novas nascem ao lado).
- Cada fase fecha com: `npm run lint:accents`, `npx tsc --noEmit`, `npx vitest run`, `npx playwright test`, entrada em `docs/REGISTRO_CORRECOES.md` + linha em `docs/INDICE_REGRAS.md`, espelho dos docs (`cp` para `c:\painel_apostas\sportsbank-pro\docs\`), commit e push na `main`.
- Commits terminam com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## Estrutura de arquivos

Tudo em `frontend/next/`.

| Arquivo | Responsabilidade |
|---|---|
| `src/app/globals.css` (modificar) | tokens novos em `:root` (bloco `/* #254 tokens */`), classes `.tnum`; os tokens antigos ficam até a fase 6 |
| `src/app/layout.tsx` (modificar) | carrega Zilla Slab e Source Sans 3 via `next/font/google` como variáveis CSS |
| `src/lib/tokens.ts` (criar) | os hex como constantes exportadas — fonte única para CSS e testes |
| `src/lib/formato.ts` (criar) | formatação pt-BR: número, reais, odd, delta, hora |
| `src/lib/copy.ts` (criar) | todas as frases da UI como funções; tokens `{term:x}` → links de glossário |
| `src/lib/bancaStore.ts` (criar) | leitura/gravação da banca com estado `null` (indefinida); reaproveita a chave de `bankrollStore.ts` |
| `src/lib/normalizeMatch.ts` (criar) | `normalizeMatch` e helpers extraídos de `dashboard/page.tsx`, sem mudança |
| `src/lib/jogoView.ts` (criar) | `Match → JogoView`: enum de estado, escolha do talão, segundo pick, contagens |
| `src/lib/reasonCodes.ts` (criar) | `reason_code → duas palavras` |
| `src/lib/confiancaLiga.ts` (criar) | `LeagueConfidence → frase` (os quatro estados do #250) |
| `src/components/feed/*.tsx` (criar) | `DiaTabs`, `LigaChips`, `CardJogo`, `Talao`, `LinhaStake`, `LinhaConfianca`, `LinhaSegundoPick`, `LinhaAvaliados`, `BotaoCopiar` |
| `src/components/detalhe/*.tsx` (criar) | `EscalaConfianca`, `TabelaMercados`, `DeOndeVemONumero`, `ComoOModeloVe` |
| `src/app/jogos/page.tsx`, `src/app/jogos/[id]/page.tsx`, `src/app/banca/page.tsx` (criar) | páginas |
| `tests/unit/**` (criar) | Vitest |
| `tests/fixtures/*.json` (criar) | payloads reais pinados |
| `scripts/check-fonts.mjs` (criar) | lint de família |
| `e2e/jogos.spec.ts`, `e2e/banca.spec.ts`, `e2e/visual.spec.ts` (criar) | Playwright |

Numeração de registro: este trabalho é o **#254** no `REGISTRO_CORRECOES.md` (fase 0 = #254, fase 2 = #254-a, fase 3 = #254-b).

---

## Fase 0 — Guardas

### Task 1: Vitest e os tokens travados por teste de contraste

**Files:**
- Create: `frontend/next/vitest.config.ts`, `frontend/next/src/lib/tokens.ts`, `frontend/next/tests/unit/tokens.test.ts`
- Modify: `frontend/next/package.json` (scripts e devDependencies), `frontend/next/src/app/globals.css` (fim do arquivo)

**Interfaces:**
- Produces: `TOKENS` (objeto `Record<NomeToken, string>`) e `PARES_PERMITIDOS` (lista `[texto, fundo, minimo]`) em `src/lib/tokens.ts`; classes CSS `--sb-*` em `:root`.

- [ ] **Step 1: Instalar o Vitest e adicionar o script**

Run (em `frontend/next`): `npm i -D vitest@^2 @vitest/coverage-v8@^2 jsdom@^24 @testing-library/react@^16 @testing-library/jest-dom@^6`

Em `package.json`, dentro de `"scripts"`, adicionar:
```json
"test:unit": "vitest run",
"test:unit:watch": "vitest"
```

Criar `vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["tests/unit/setup.ts"],
  },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```

Criar `tests/unit/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Escrever o teste de contraste (falha: `tokens.ts` não existe)**

`tests/unit/tokens.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { TOKENS, PARES_PERMITIDOS, contraste } from "@/lib/tokens";

describe("tokens (#254, spec §2)", () => {
  it("todo par (texto, fundo) usado na UI passa de 4,5:1", () => {
    for (const [texto, fundo, minimo] of PARES_PERMITIDOS) {
      const r = contraste(TOKENS[texto], TOKENS[fundo]);
      expect(r, `${texto} sobre ${fundo} = ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(minimo);
    }
  });

  it("confianca sobre talao e ilegivel — por isso o par nao esta na lista", () => {
    expect(contraste(TOKENS.confianca, TOKENS.talao)).toBeLessThan(3);
    expect(PARES_PERMITIDOS.some(([t, f]) => t === "confianca" && f === "talao")).toBe(false);
  });

  it("texto-apagado sobre hover e o par mais fraco e ainda passa", () => {
    expect(contraste(TOKENS["texto-apagado"], TOKENS.hover)).toBeGreaterThanOrEqual(4.5);
  });

  it("nao ha verde na paleta", () => {
    for (const hex of Object.values(TOKENS)) {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      expect(g > r + 40 && g > b + 40, `${hex} puxa para o verde`).toBe(false);
    }
  });
});
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `npx vitest run tests/unit/tokens.test.ts`
Expected: FAIL — `Cannot find module '@/lib/tokens'`.

- [ ] **Step 4: Criar `src/lib/tokens.ts`**

```ts
/**
 * #254 — tokens da reformulacao (spec §2). Fonte unica: o CSS em globals.css
 * copia estes hex; o teste de contraste le daqui. Um significado por cor.
 */
export const TOKENS = {
  tinta: "#15161A",
  painel: "#22242B",
  linha: "#2C2E36",
  hover: "#262830",
  texto: "#E6E4DD",
  "texto-apagado": "#93959C",
  talao: "#E3D9AE",
  "tinta-do-talao": "#1B1710",
  "tinta-apoiada": "#4A4436",
  confianca: "#4FB3BF",
  "contra-texto": "#E8665A",
  contra: "#E0533F",
} as const;

export type NomeToken = keyof typeof TOKENS;

/**
 * Pares (texto, fundo, minimo WCAG) que a UI de fato produz — hover incluido.
 * Todo componente novo que combine texto e superficie de outro jeito adiciona
 * o par aqui; o teste e a fonte de verdade, a tabela da spec documenta.
 */
export const PARES_PERMITIDOS: ReadonlyArray<readonly [NomeToken, NomeToken, number]> = [
  ["texto", "tinta", 4.5],
  ["texto", "painel", 4.5],
  ["texto", "hover", 4.5],
  ["texto-apagado", "tinta", 4.5],
  ["texto-apagado", "painel", 4.5],
  ["texto-apagado", "hover", 4.5],
  ["confianca", "tinta", 4.5],
  ["confianca", "painel", 4.5],
  ["confianca", "hover", 4.5],
  ["contra-texto", "tinta", 4.5],
  ["contra-texto", "painel", 4.5],
  ["contra-texto", "hover", 4.5],
  ["tinta-do-talao", "talao", 4.5],
  ["tinta-apoiada", "talao", 4.5],
];

function luminancia(hex: string): number {
  const canal = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

/** Razao de contraste WCAG 2.1 (>= 1). */
export function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npx vitest run tests/unit/tokens.test.ts`
Expected: PASS (4 testes). Se `texto-apagado sobre hover` falhar, o hex está errado — a spec fixa `#93959C` (4,91:1).

- [ ] **Step 6: Expor os tokens no CSS**

Ao fim de `src/app/globals.css`, acrescentar:
```css
/* #254 tokens da reformulacao — copia de src/lib/tokens.ts (o teste trava os hex) */
:root {
  --sb-tinta: #15161A;
  --sb-painel: #22242B;
  --sb-linha: #2C2E36;
  --sb-hover: #262830;
  --sb-texto: #E6E4DD;
  --sb-texto-apagado: #93959C;
  --sb-talao: #E3D9AE;
  --sb-tinta-do-talao: #1B1710;
  --sb-tinta-apoiada: #4A4436;
  --sb-confianca: #4FB3BF;
  --sb-contra-texto: #E8665A;
  --sb-contra: #E0533F;
  --sb-raio-talao: 4px;
  --sb-raio-painel: 8px;
}
.tnum { font-variant-numeric: tabular-nums; }
.sb-foco:focus-visible { outline: 2px solid var(--sb-texto); outline-offset: 2px; }
```

- [ ] **Step 7: Teste que o CSS e o TS não divergem**

Acrescentar a `tests/unit/tokens.test.ts`:
```ts
import { readFileSync } from "node:fs";
import path from "node:path";

it("globals.css carrega os mesmos hex de tokens.ts", () => {
  const css = readFileSync(path.resolve(__dirname, "../../src/app/globals.css"), "utf8");
  for (const [nome, hex] of Object.entries(TOKENS)) {
    expect(css, `--sb-${nome}`).toContain(`--sb-${nome}: ${hex};`);
  }
});
```

Run: `npx vitest run tests/unit/tokens.test.ts` — Expected: PASS (5 testes).

- [ ] **Step 8: Commit**

```bash
git add frontend/next/package.json frontend/next/package-lock.json frontend/next/vitest.config.ts frontend/next/tests/unit frontend/next/src/lib/tokens.ts frontend/next/src/app/globals.css
git commit -m "feat(front): tokens #254 travados por teste de contraste; vitest (#254)"
```

---

### Task 2: Fontes e o lint de família

**Files:**
- Modify: `frontend/next/src/app/layout.tsx`
- Create: `frontend/next/scripts/check-fonts.mjs`, `frontend/next/src/components/marca/fonteMarca.ts`
- Modify: `frontend/next/package.json` (script `lint:fonts`), `.github/workflows/ci.yml` (passo `npm run lint:fonts` logo após `lint:accents`)

**Interfaces:**
- Produces: variáveis CSS `--font-slab` (Zilla Slab) e `--font-sans` (Source Sans 3) no `<html>`; `fonteMarca` (Barlow Condensed) exportada só de `components/marca/fonteMarca.ts`.

- [ ] **Step 1: Escrever o lint (falha: hoje `Inter` está no layout)**

`scripts/check-fonts.mjs`:
```js
#!/usr/bin/env node
/**
 * #254 — guarda de familias tipograficas (spec §2).
 * Barlow Condensed so em src/components/marca e src/app/page.tsx.
 * Inter em lugar nenhum. Falha com a lista de ocorrencias.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../src", import.meta.url));
const PERMITIDO_BARLOW = [join("components", "marca"), join("app", "page.tsx")];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== "node_modules") yield* walk(p); }
    else if (/\.(tsx|ts|css)$/.test(name)) yield p;
  }
}

const violacoes = [];
for (const file of walk(ROOT)) {
  const rel = relative(ROOT, file);
  const src = readFileSync(file, "utf8");
  if (/\bInter\b/.test(src) && /next\/font|font-family|fontFamily/.test(src)) {
    violacoes.push(`${rel}: Inter`);
  }
  if (/Barlow/.test(src) && !PERMITIDO_BARLOW.some((ok) => rel.startsWith(ok))) {
    violacoes.push(`${rel}: Barlow Condensed fora de components/marca`);
  }
}
if (violacoes.length) {
  console.error(`✗ lint:fonts — ${violacoes.length} violacao(oes):\n  ` + violacoes.join("\n  "));
  process.exit(1);
}
console.log("✓ lint:fonts — familias no lugar.");
```

Em `package.json` scripts: `"lint:fonts": "node scripts/check-fonts.mjs"`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm run lint:fonts`
Expected: exit 1 com `app/layout.tsx: Inter` (o layout atual usa `Inter` de `next/font/google`).

- [ ] **Step 3: Trocar as fontes no layout**

Em `src/app/layout.tsx`, substituir o import e o uso de `Inter` por:
```tsx
import { Zilla_Slab, Source_Sans_3 } from "next/font/google";

const slab = Zilla_Slab({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-slab", display: "swap" });
const sans = Source_Sans_3({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-sans", display: "swap" });
```
e no `<html>`: `className={`${slab.variable} ${sans.variable}`}`. No `<body>`, manter as classes existentes e acrescentar `font-[family-name:var(--font-sans)]` **somente** se o body hoje aplica `inter.className`; caso contrário, não mexer no body (o dashboard antigo continua com o que tinha via CSS próprio).

Criar `src/components/marca/fonteMarca.ts`:
```ts
import { Barlow_Condensed } from "next/font/google";
/** Voz da marca (linguagem A). So o hero e o card social importam daqui. */
export const fonteMarca = Barlow_Condensed({ subsets: ["latin"], weight: ["500", "700"], display: "swap" });
```

- [ ] **Step 4: Rodar e ver passar; conferir o tipo**

Run: `npm run lint:fonts` — Expected: `✓ lint:fonts`.
Run: `npx tsc --noEmit` — Expected: sem erros.
Run: `npm run dev` e abrir `/dashboard`: a página continua igual (o dashboard usa `--font-size-*` e classes próprias; a única mudança é a família do body, aceita nesta fase porque Inter tem de sair — registrar no REGISTRO como mudança consciente).

- [ ] **Step 5: CI**

Em `.github/workflows/ci.yml`, logo após a linha `run: npm run lint:accents`, acrescentar um passo idêntico com `run: npm run lint:fonts`, e após ele `run: npm run test:unit`.

- [ ] **Step 6: Commit**

```bash
git add frontend/next/src/app/layout.tsx frontend/next/scripts/check-fonts.mjs frontend/next/src/components/marca/fonteMarca.ts frontend/next/package.json .github/workflows/ci.yml
git commit -m "feat(front): Zilla Slab + Source Sans 3; Barlow so na marca; lint:fonts (#254)"
```

---

### Task 3: `formato.ts` — pt-BR num ponto só

**Files:**
- Create: `frontend/next/src/lib/formato.ts`, `frontend/next/tests/unit/formato.test.ts`

**Interfaces:**
- Produces: `fmtReais(v: number): string`, `fmtOdd(v: number): string`, `fmtDelta(v: number): string`, `fmtPct(p01: number): number` (inteiro 0–100), `fmtHora(iso: string): string`, `fmtDataCurta(iso: string): string`, `fmtLigaHora(liga: string, iso: string): string`.

- [ ] **Step 1: Teste**

`tests/unit/formato.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { fmtReais, fmtOdd, fmtDelta, fmtPct, fmtHora, fmtLigaHora, fmtDataCurta } from "@/lib/formato";

describe("formato pt-BR (#254)", () => {
  it("reais com milhar e virgula", () => {
    expect(fmtReais(1000)).toBe("R$ 1.000,00");
    expect(fmtReais(25)).toBe("R$ 25,00");
    expect(fmtReais(312.4)).toBe("R$ 312,40");
  });
  it("odd com duas casas e virgula", () => {
    expect(fmtOdd(1.75)).toBe("1,75");
    expect(fmtOdd(2)).toBe("2,00");
  });
  it("delta com sinal e duas casas", () => {
    expect(fmtDelta(0.08)).toBe("+0,08");
    expect(fmtDelta(-0.13)).toBe("−0,13");
    expect(fmtDelta(0)).toBe("0,00");
  });
  it("pct arredonda para inteiro", () => {
    expect(fmtPct(0.5849)).toBe(58);
    expect(fmtPct(0.585)).toBe(59);
  });
  it("hora e data em America/Sao_Paulo", () => {
    expect(fmtHora("2026-09-09T23:30:00Z")).toBe("20:30");
    expect(fmtDataCurta("2026-09-09T23:30:00Z")).toBe("09/09");
    expect(fmtLigaHora("MLS", "2026-09-09T23:30:00Z")).toBe("MLS, 20:30");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run tests/unit/formato.test.ts` → `Cannot find module '@/lib/formato'`.

- [ ] **Step 3: Implementar**

`src/lib/formato.ts`:
```ts
/** #254 — formatacao pt-BR, um ponto so (spec §4.4). Virgula decimal sempre. */
const FUSO = "America/Sao_Paulo";
const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2 });
const duasCasas = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function fmtReais(v: number): string {
  // Intl usa espaco nao separavel entre "R$" e o numero; normaliza para espaco comum.
  return reais.format(v).replace(/\u00a0/g, " ");
}
export function fmtOdd(v: number): string {
  return duasCasas.format(v);
}
export function fmtDelta(v: number): string {
  const abs = duasCasas.format(Math.abs(v));
  if (Math.abs(v) < 0.005) return abs;
  return (v > 0 ? "+" : "\u2212") + abs;
}
export function fmtPct(p01: number): number {
  return Math.round(p01 * 100);
}
export function fmtHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: FUSO }).format(new Date(iso));
}
export function fmtDataCurta(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: FUSO }).format(new Date(iso));
}
export function fmtLigaHora(liga: string, iso: string): string {
  return `${liga}, ${fmtHora(iso)}`;
}
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/formato.test.ts` → PASS.
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/formato.ts frontend/next/tests/unit/formato.test.ts && git commit -m "feat(front): formato pt-BR (#254)"`

---

### Task 4: `copy.ts` — as frases, com tokens de glossário

**Files:**
- Create: `frontend/next/src/lib/copy.ts`, `frontend/next/src/lib/reasonCodes.ts`, `frontend/next/tests/unit/copy.test.ts`

**Interfaces:**
- Produces (todas puras, devolvem `string` ou `Trecho[]`):
  - `type Trecho = { texto: string } | { termo: string; texto: string }` e `comTermos(template: string): Trecho[]` — `{term:edge|texto}` vira `{termo:"edge", texto:"texto"}`.
  - `frequencia(p01): string` → "acontece em 58 de cada 100 jogos assim"
  - `linhaPreco(bookOdd: number|null, fairOdd: number, futuro: boolean): { texto: string; abaixo: boolean; semPreco: boolean }`
  - `stake(banca: number|null, valor: number|null): string`
  - `avaliados(total: number, valem: number): string`
  - `direcao(mercado: string, p01: number): string`
  - `resultadoOntem(acertou: boolean, detalhe: string): string`
  - `motivoRecusa(codes: string[]): string` (em `reasonCodes.ts`, duas palavras)

- [ ] **Step 1: Teste**

`tests/unit/copy.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import * as C from "@/lib/copy";
import { motivoRecusa } from "@/lib/reasonCodes";

describe("copy (#254, spec §4.4)", () => {
  it("frequencia", () => {
    expect(C.frequencia(0.5849)).toBe("acontece em 58 de cada 100 jogos assim");
  });
  it("linha de preco acima do minimo", () => {
    expect(C.linhaPreco(1.75, 1.67, false)).toEqual({
      texto: "mercado paga 1,75, acima do mínimo 1,67 (+0,08)", abaixo: false, semPreco: false,
    });
  });
  it("linha de preco abaixo do minimo", () => {
    expect(C.linhaPreco(1.62, 1.75, false)).toEqual({
      texto: "mercado paga 1,62, abaixo do mínimo 1,75 (−0,13)", abaixo: true, semPreco: false,
    });
  });
  it("sem preco: amanha e hoje", () => {
    expect(C.linhaPreco(null, 1.67, true).texto).toBe("vale a partir de 1,67, mercado ainda sem preço");
    expect(C.linhaPreco(null, 1.67, false).texto).toBe("vale a partir de 1,67, sem preço que valha hoje");
  });
  it("stake com e sem banca", () => {
    expect(C.stake(1000, 25)).toBe("Da sua banca de R$ 1.000,00: R$ 25,00");
    expect(C.stake(null, null)).toBe("stake: defina sua banca");
  });
  it("avaliados e direcao", () => {
    expect(C.avaliados(12, 2)).toBe("12 mercados avaliados, 2 valem");
    expect(C.avaliados(12, 0)).toBe("12 mercados avaliados, nenhum vale hoje");
    expect(C.direcao("Mais de 2,5 gols", 0.57)).toBe("Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje");
  });
  it("resultado de ontem", () => {
    expect(C.resultadoOntem(true, "8 escanteios")).toBe("✓ fechou com 8 escanteios");
    expect(C.resultadoOntem(false, "5 escanteios")).toBe("× fechou com 5 escanteios");
  });
  it("tokens de glossario viram trechos", () => {
    expect(C.comTermos("o {term:edge|edge} de hoje")).toEqual([
      { texto: "o " }, { termo: "edge", texto: "edge" }, { texto: " de hoje" },
    ]);
  });
  it("motivo de recusa em duas palavras, o primeiro codigo conhecido manda", () => {
    expect(motivoRecusa(["NEGATIVE_EV"])).toBe("sem valor");
    expect(motivoRecusa(["LOW_DATA_QUALITY", "NEGATIVE_EV"])).toBe("amostra curta");
    expect(motivoRecusa(["NO_ODDS_AVAILABLE"])).toBe("sem preço");
    expect(motivoRecusa([])).toBe("não vale");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run tests/unit/copy.test.ts`.

- [ ] **Step 3: Implementar `copy.ts`**

```ts
/** #254 — toda frase da UI nasce aqui (spec §4.4). Numero antes de nome. */
import { fmtDelta, fmtOdd, fmtPct, fmtReais } from "@/lib/formato";

export type Trecho = { texto: string } | { termo: string; texto: string };

/** `{term:edge|edge}` → trecho com termo; o componente vira link /glossario#edge. */
export function comTermos(template: string): Trecho[] {
  const out: Trecho[] = [];
  const re = /\{term:([a-z0-9-]+)\|([^}]+)\}/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(template)) !== null) {
    if (m.index > ultimo) out.push({ texto: template.slice(ultimo, m.index) });
    out.push({ termo: m[1], texto: m[2] });
    ultimo = m.index + m[0].length;
  }
  if (ultimo < template.length) out.push({ texto: template.slice(ultimo) });
  return out;
}

export function frequencia(p01: number): string {
  return `acontece em ${fmtPct(p01)} de cada 100 jogos assim`;
}

export function linhaPreco(bookOdd: number | null, fairOdd: number, futuro: boolean) {
  if (bookOdd == null || bookOdd <= 1) {
    return {
      texto: futuro
        ? `vale a partir de ${fmtOdd(fairOdd)}, mercado ainda sem preço`
        : `vale a partir de ${fmtOdd(fairOdd)}, sem preço que valha hoje`,
      abaixo: false,
      semPreco: true,
    };
  }
  const delta = bookOdd - fairOdd;
  const abaixo = delta < 0;
  return {
    texto: `mercado paga ${fmtOdd(bookOdd)}, ${abaixo ? "abaixo" : "acima"} do mínimo ${fmtOdd(fairOdd)} (${fmtDelta(delta)})`,
    abaixo,
    semPreco: false,
  };
}

export function stake(banca: number | null, valor: number | null): string {
  if (banca == null || valor == null) return "stake: defina sua banca";
  return `Da sua banca de ${fmtReais(banca)}: ${fmtReais(valor)}`;
}

export function avaliados(total: number, valem: number): string {
  if (valem === 0) return `${total} mercados avaliados, nenhum vale hoje`;
  return `${total} mercados avaliados, ${valem} ${valem === 1 ? "vale" : "valem"}`;
}

export function direcao(mercado: string, p01: number): string {
  const m = mercado.charAt(0).toLowerCase() + mercado.slice(1);
  return `Direção: ${m}, ${fmtPct(p01)} em cada 100 — sem preço que valha hoje`;
}

export function resultadoOntem(acertou: boolean, detalhe: string): string {
  return `${acertou ? "✓" : "×"} fechou com ${detalhe}`;
}

export const COPIAR = {
  rotulo: (odd: number) => `copiar odd ${fmtOdd(odd)}`,
  ok: (odd: number) => `${fmtOdd(odd)} copiado`,
  falhou: "não deu pra copiar — selecione o número",
};

export const VAZIOS = {
  diaSemJogos: (data: string) => `Nenhum jogo nas ligas escolhidas em ${data}.`,
  proximoDia: (dia: string) => `próximo dia com picks: ${dia}`,
  feedNaoCarregou: "Os jogos de hoje não carregaram.",
  tentarDeNovo: "Tentar de novo",
  carimbo: (hora: string) => `de ${hora}`,
  ligaSemDados: (liga: string) => `${liga}: sem dados da rodada`,
  jogoNaoEncontrado: "jogo não encontrado",
  verFeedDeHoje: "ver os jogos de hoje",
  resultadoPendente: "resultado ainda não conferido",
  recomendacaoPreJogo: "recomendação pré-jogo",
};
```

`src/lib/reasonCodes.ts`:
```ts
/** #254 — reason_code do backend → duas palavras (spec §4.3). Ordem = prioridade. */
const MAPA: ReadonlyArray<readonly [string, string]> = [
  ["LOW_DATA_QUALITY", "amostra curta"],
  ["DATA_MISSING", "amostra curta"],
  ["EARLY_SEASON_FALLBACK", "início de temporada"],
  ["NO_ODDS_AVAILABLE", "sem preço"],
  ["ODDS_TOO_LOW", "odd baixa"],
  ["NEGATIVE_EV", "sem valor"],
  ["EV_FLOOR_DROP", "sem valor"],
  ["INSUFFICIENT_EDGE", "margem curta"],
  ["HIGH_MARKET_CORRELATION", "corredor"],
  ["CORNER_ENGINE_NO_BET", "motor vetou"],
  ["REGIME_BLOCKED", "regime bloqueado"],
  ["SAFE_CIRCUIT_BREAKER", "SAFE pausado"],
  ["HIGH_PREDICTION_RISK", "risco alto"],
  ["SUSPICIOUS_EV", "EV suspeito"],
  ["DIRECTION_AGAINST_PROJFT", "contra a projeção"],
  ["COVERAGE_INSUFFICIENT", "cobertura curta"],
];

export function motivoRecusa(codes: string[]): string {
  for (const [code, frase] of MAPA) if (codes.includes(code)) return frase;
  return "não vale";
}
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/copy.test.ts` → PASS. Rodar `npm run lint:accents` → verde (as frases têm acento).
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/copy.ts frontend/next/src/lib/reasonCodes.ts frontend/next/tests/unit/copy.test.ts && git commit -m "feat(front): copy centralizada com tokens de glossario (#254)"`

---

### Task 5: `bancaStore.ts` — a banca pode ser indefinida

**Files:**
- Create: `frontend/next/src/lib/bancaStore.ts`, `frontend/next/tests/unit/bancaStore.test.ts`
- Não modificar `src/lib/bankrollStore.ts` (o dashboard antigo continua lendo `DEFAULT_BANKROLL = 1000` até a fase 6).

**Interfaces:**
- Produces: `getBanca(): number | null`, `setBanca(v: number): "ok" | "invalida"`, `useBanca(): [number | null, (v: number) => "ok" | "invalida"]`, `calcStake(prob01: number, odd: number, banca: number, classification?: string): number` (delega a `calcQuarterKelly` de `components/BankrollCard.tsx`, sem copiar a fórmula).
- Mesma chave `sportsbankzu-bankroll` de `bankrollStore.ts`: banca definida numa tela vale na outra.

- [ ] **Step 1: Teste**

`tests/unit/bancaStore.test.ts`:
```ts
import { beforeEach, describe, expect, it } from "vitest";
import { getBanca, setBanca, calcStake } from "@/lib/bancaStore";

describe("bancaStore (#254, spec §5)", () => {
  beforeEach(() => localStorage.clear());

  it("sem nada gravado a banca e indefinida, nao 1000", () => {
    expect(getBanca()).toBeNull();
  });
  it("grava e le", () => {
    expect(setBanca(1500)).toBe("ok");
    expect(getBanca()).toBe(1500);
  });
  it("valor invalido nao grava e devolve 'invalida'", () => {
    expect(setBanca(0)).toBe("invalida");
    expect(setBanca(NaN)).toBe("invalida");
    expect(getBanca()).toBeNull();
  });
  it("localStorage corrompido vira indefinida, sem throw", () => {
    localStorage.setItem("sportsbankzu-bankroll", "abc");
    expect(getBanca()).toBeNull();
  });
  it("le a banca do store antigo (mesma chave)", () => {
    localStorage.setItem("sportsbankzu-bankroll", "800");
    expect(getBanca()).toBe(800);
  });
  it("stake e o quarter kelly do BankrollCard, em reais", () => {
    // prob 0,58, odd 1,75, banca 1000: kelly = (0,58*0,75 - 0,42)/0,75 = 0,02; quarter = 0,005 → R$ 5
    expect(calcStake(0.58, 1.75, 1000, "SAFE")).toBeCloseTo(5, 5);
    expect(calcStake(0.58, 1.75, 0)).toBe(0);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run tests/unit/bancaStore.test.ts`.

- [ ] **Step 3: Implementar**

`src/lib/bancaStore.ts`:
```ts
/**
 * #254 — banca com estado INDEFINIDO (spec §5). O store antigo (`bankrollStore.ts`)
 * presume 1000; um usuario novo nao pode ver "R$ 25" nascido de uma banca
 * presumida. Mesma chave do store antigo: a banca definida aqui vale la.
 */
import { useSyncExternalStore } from "react";
import { calcQuarterKelly } from "@/components/BankrollCard";

const KEY = "sportsbankzu-bankroll";
const EVENTO = "sbz:bankroll-change";

function positivo(raw: unknown): number | null {
  const v = typeof raw === "string" ? parseFloat(raw) : typeof raw === "number" ? raw : NaN;
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function getBanca(): number | null {
  if (typeof window === "undefined") return null;
  try {
    return positivo(localStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export function setBanca(v: number): "ok" | "invalida" {
  const val = positivo(v);
  if (val === null) return "invalida";
  try {
    localStorage.setItem(KEY, String(val));
  } catch {
    /* sem persistencia: o evento abaixo ainda propaga o valor em memoria */
  }
  try {
    window.dispatchEvent(new CustomEvent(EVENTO, { detail: val }));
  } catch {
    /* noop */
  }
  return "ok";
}

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => { if (e.key === null || e.key === KEY) onChange(); };
  window.addEventListener("storage", onStorage);
  window.addEventListener(EVENTO, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(EVENTO, onChange);
  };
}

export function useBanca(): [number | null, (v: number) => "ok" | "invalida"] {
  const valor = useSyncExternalStore(subscribe, getBanca, () => null);
  return [valor, setBanca];
}

/** Stake em reais. A formula e a do BankrollCard (Quarter Kelly com caps) — nao duplicar. */
export function calcStake(prob01: number, odd: number, banca: number, classification?: string): number {
  return calcQuarterKelly(prob01, odd, banca, classification).stake;
}
```

- [ ] **Step 4: Rodar e ver passar.** Se `calcQuarterKelly` devolver `stake` arredondado de outro jeito, ajustar a asserção ao valor real **depois de ler a função** (`components/BankrollCard.tsx:35-60`) — a regra é "a conta não muda", não "a conta é 5".
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/bancaStore.ts frontend/next/tests/unit/bancaStore.test.ts && git commit -m "feat(front): banca com estado indefinido (#254)"`

---

### Task 6: `lint:accents` funcionando no Windows

**Files:**
- Modify: `frontend/next/scripts/check-accents.mjs:16`

- [ ] **Step 1: Reproduzir** — Run (Windows): `npm run lint:accents`. Expected hoje: `ENOENT ... '/C:/painel_apostas/...'` — `new URL(...).pathname` produz `/C:/...`.

- [ ] **Step 2: Corrigir**

Trocar a linha `const ROOT = new URL("../src", import.meta.url).pathname;` por:
```js
import { fileURLToPath } from "node:url";
const ROOT = fileURLToPath(new URL("../src", import.meta.url));
```

- [ ] **Step 3: Verificar** — `npm run lint:accents` roda no Windows e no Linux (CI) com o mesmo resultado. Se acusar violações pré-existentes (o #250 deixou 22), **não** corrigir aqui: registrar o número no REGISTRO e seguir; as telas novas nascem limpas.
- [ ] **Step 4: Commit** — `git commit -am "fix(front): lint:accents no Windows (fileURLToPath) (#254)"`

---

### Task 7: Fechar a fase 0 — REGISTRO, espelho, push

- [ ] **Step 1:** Rodar tudo: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test --project=chromium`. Expected: verde (os E2E antigos não mudam; se `dashboard.spec` quebrar, é a troca de fonte no body — o teste antigo não olha fonte, então investigar antes de tocar).
- [ ] **Step 2:** Entrada `## 254 — Reformulação do frontend, fase 0: guardas de design` em `docs/REGISTRO_CORRECOES.md` (formato do CLAUDE.md: Problema, Causa, Correções por camada, Prova empírica com a saída do `vitest` e do `lint:fonts` antes/depois, Contratos de saída: "nenhum campo de backend; body troca de Inter para Source Sans 3 — mudança visual consciente no dashboard antigo", Etapa 5: não se aplica). Linha em `docs/INDICE_REGRAS.md` após `| 253-b |`.
- [ ] **Step 3:** Espelhar (`cp` dos 3 docs e do CLAUDE.md para `c:\painel_apostas\sportsbank-pro\`), `git add -A frontend/next docs`, commit `docs: REGISTRO #254 fase 0`, `git push origin HEAD:main`, acompanhar o CI.

---

## Fase 2 — `jogoView` sem mudança visual

### Task 8: Extrair `normalizeMatch` da página, byte a byte

**Files:**
- Create: `frontend/next/src/lib/normalizeMatch.ts`
- Modify: `frontend/next/src/app/dashboard/page.tsx` (remover as funções movidas, importar de `@/lib/normalizeMatch`)
- Create: `frontend/next/tests/unit/normalizeMatch.test.ts`

**Interfaces:**
- Produces: `normalizeMatch(item: unknown, leagueId: string, idx: number): Match`, `deduplicateMatches(matches: Match[]): Match[]`, `resolveTeamAlias(name: string): string`, `normalizeTeamName(name: string): string` — **mesmas assinaturas e mesmo corpo** que hoje em `dashboard/page.tsx:177-627` (`safeOdd`, `TEAM_ALIASES`, `normalizeTeamName`, `resolveTeamAlias`, `deduplicateMatches`, `matchRichness`, `mergeMatchData`, `KNOWN_DANISH_TEAMS`, `inferLeagueFromTeams`, `normalizeMatch`).

- [ ] **Step 1: Teste de equivalência (falha: módulo não existe)**

`tests/unit/normalizeMatch.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";

const bruto = {
  id: "mls-Toronto-Nashville SC-1788985800.0",
  leagueId: "mls",
  homeTeam: { name: "Toronto", logo: "", form: [], rating: 0 },
  awayTeam: { name: "Nashville SC", logo: "", form: [], rating: 0 },
  datetime: "2026-09-09T23:30:00Z",
  status: "scheduled",
  odds: { home: 3.03, draw: 3.4, away: 2.2 },
  stats: { homeWinProb: 30, drawProb: 29, awayWinProb: 41, avgGoals: 2.9,
           homeCornersPerMatch: 5.1, awayCornersPerMatch: 4.6, leagueAvgCorners: 9.8 },
  mercados: [{ mercado: "Escanteios Over 6.5", status: "SAFE", prob_min: 57, prob_max: 59,
               odd_minima: 1.75, classification: "SAFE", ev: 0.015, edge: 0.08,
               fair_odd: 1.67, book_odd: 1.75, calibrated_probability: 0.585, reason_codes: ["POSITIVE_EV"] }],
};

describe("normalizeMatch extraido (#254-a)", () => {
  it("mapeia liga, times, data e mercados como a pagina fazia", () => {
    const m = normalizeMatch(bruto, "mls", 0);
    expect(m.leagueId).toBe("usa-mls");
    expect(m.homeTeam.name).toBe("Toronto");
    expect(m.datetime).toBe("2026-09-09T23:30:00Z");
    expect(m.predictions?.[0]?.fair_odd).toBe(1.67);
    expect(m.stats.homeCornersPerMatch).toBe(5.1);
  });
  it("dedup mantem um registro por par de times e data", () => {
    const a = normalizeMatch(bruto, "mls", 0);
    const b = normalizeMatch({ ...bruto, id: "outro", mercados: [] }, "mls", 1);
    expect(deduplicateMatches([a, b])).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Mover o código**

Criar `src/lib/normalizeMatch.ts` com o cabeçalho:
```ts
/**
 * #254-a — mapeador do payload de /fixtures para `Match`, EXTRAIDO de
 * app/dashboard/page.tsx sem alteracao de comportamento. Fase 2 da spec de
 * reformulacao: primeiro testavel, depois redesenhado.
 */
import { AVAILABLE_LEAGUES, type Match } from "@/lib/leagues";
```
e, abaixo, **recortar e colar** de `dashboard/page.tsx` — sem editar uma linha — os blocos, nesta ordem: `safeOdd` (l.177), `TEAM_ALIASES` (l.183), `normalizeTeamName`, `resolveTeamAlias`, `deduplicateMatches`, `matchRichness`, `mergeMatchData`, `KNOWN_DANISH_TEAMS`, `inferLeagueFromTeams`, `normalizeMatch`. Prefixar com `export` as quatro da interface acima. Se alguma dessas funções usar outro helper da página (`formatTime`, `AVAILABLE_LEAGUES`…), mover ou importar; `tsc` aponta.

Em `dashboard/page.tsx`, apagar os blocos movidos e acrescentar:
```ts
import { normalizeMatch, deduplicateMatches, resolveTeamAlias, normalizeTeamName } from "@/lib/normalizeMatch";
```
(só os nomes que a página ainda usa — `tsc` diz quais).

- [ ] **Step 4: Provar zero mudança**

Run: `npx tsc --noEmit && npx vitest run tests/unit/normalizeMatch.test.ts` → PASS.
Run: `npx playwright test --project=chromium e2e/dashboard.spec.ts e2e/league-confidence.spec.ts` → o mesmo resultado de antes da task (anotar o placar antes e depois).
Run: `git diff --stat` — a página só perde linhas; `git diff -M --color-moved=plain` mostra os blocos como movidos, sem edição.

- [ ] **Step 5: Commit** — `git add -A frontend/next/src frontend/next/tests && git commit -m "refactor(front): normalizeMatch extraido da pagina, zero mudanca visual (#254-a)"`

---

### Task 9: Fixtures pinadas por data e versão, com teste de contrato

**Files:**
- Create: `frontend/next/tests/fixtures/fixtures.2026-09-15.v1.json`, `frontend/next/tests/fixtures/README.md`, `frontend/next/tests/unit/fixtures.contract.test.ts`, `frontend/next/scripts/capturar-fixture.mjs`

**Interfaces:**
- Produces: um JSON `{ schema: "fixtures.v1", capturado_em: "…Z", fonte: "/fixtures?leagues=…&date=…", matches: [...] }` com **um jogo real por estado** do enum (`vale`, `direcao`, `nada`, `amanha_sem_preco`, `em_jogo`); os estados `ontem*` entram no plano 3 com `/ledger/dia`.

- [ ] **Step 1: Script de captura**

`scripts/capturar-fixture.mjs`:
```js
#!/usr/bin/env node
/** #254-a — captura o payload real da Lambda e pina data + versao de schema. */
import { writeFileSync } from "node:fs";
const BASE = "https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws";
const [leagues = "mls,brasileirao-serie-b,premier-league", date = "today"] = process.argv.slice(2);
const res = await fetch(`${BASE}/fixtures?leagues=${leagues}&date=${date}`);
const body = await res.json();
const hoje = new Date().toISOString().slice(0, 10);
const out = { schema: "fixtures.v1", capturado_em: new Date().toISOString(), fonte: `/fixtures?leagues=${leagues}&date=${date}`, matches: body.matches ?? [] };
const path = `tests/fixtures/fixtures.${hoje}.v1.json`;
writeFileSync(path, JSON.stringify(out, null, 2));
console.log(`${out.matches.length} jogos → ${path}`);
```
Run: `node scripts/capturar-fixture.mjs`. Abrir o JSON e **conferir à mão** que existe ao menos um jogo com `classification: "SAFE"` ou `"NEUTRO_QUALIFICADO"`, um só com `NEUTRO`, um só `NO_BET`; se faltar estado, capturar outra liga/data (`date=tomorrow` dá `amanha_sem_preco`) e juntar os `matches` num arquivo só, anotando no `README.md` de onde veio cada jogo. Renomear o arquivo final para `fixtures.2026-09-15.v1.json` (a data é a da captura; se for outro dia, atualizar o import nos testes).

- [ ] **Step 2: Teste de contrato (falha até o fixture existir e bater com o type)**

`tests/unit/fixtures.contract.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import fixture from "../fixtures/fixtures.2026-09-15.v1.json";
import { normalizeMatch } from "@/lib/normalizeMatch";
import type { Match, MatchPrediction } from "@/lib/leagues";

/**
 * #254-a — o fixture e o payload REAL pinado. Se o backend mudar o schema, o
 * type de `Match`/`MatchPrediction` muda, e este teste falha no CI, nao em
 * producao com fixture velho.
 */
type Bruto = { leagueId: string; mercados?: { classification?: string }[] };

describe("fixture pinado x type do payload", () => {
  it("cabecalho pinado", () => {
    expect(fixture.schema).toBe("fixtures.v1");
    expect(fixture.capturado_em).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(fixture.matches.length).toBeGreaterThan(0);
  });

  it("todo jogo normaliza e todo mercado carrega os campos que o talao usa", () => {
    for (const raw of fixture.matches as Bruto[]) {
      const m: Match = normalizeMatch(raw, raw.leagueId, 0);
      expect(typeof m.datetime).toBe("string");
      expect(["scheduled", "live", "finished", "postponed"]).toContain(m.status);
      for (const p of m.predictions ?? []) {
        const chaves: (keyof MatchPrediction)[] = ["mercado", "classification", "ev", "edge", "fair_odd", "book_odd", "calibrated_probability", "reason_codes"];
        for (const k of chaves) expect(p, `${m.id} ${p.mercado} sem ${k}`).toHaveProperty(k);
        expect(p.fair_odd == null || p.fair_odd > 1).toBe(true);
      }
    }
  });

  it("cobre os estados que o jogoView deriva", () => {
    const classes = new Set((fixture.matches as Bruto[]).flatMap((r) => (r.mercados ?? []).map((p) => p.classification)));
    for (const c of ["SAFE", "NEUTRO", "NO_BET"]) expect(classes, `falta um jogo com ${c}`).toContain(c);
  });
});
```
(`tsconfig` já tem `resolveJsonModule: true`.)

- [ ] **Step 3: Rodar e ver passar** — `npx vitest run tests/unit/fixtures.contract.test.ts`. Se `fair_odd` vier ausente em algum mercado, isso é achado de contrato: abrir item no plano da fase 1, e ajustar o teste para exigir presença só onde `book_odd` existe até lá.

- [ ] **Step 4: Commit** — `git add frontend/next/tests/fixtures frontend/next/tests/unit/fixtures.contract.test.ts frontend/next/scripts/capturar-fixture.mjs && git commit -m "test(front): fixture real pinado + teste de contrato (#254-a)"`

---

### Task 10: `jogoView.ts` — o enum de estados e a regra do talão

**Files:**
- Create: `frontend/next/src/lib/jogoView.ts`, `frontend/next/tests/unit/jogoView.test.ts`

**Interfaces:**
- Produces:
```ts
export type EstadoJogo = "vale" | "direcao" | "nada" | "amanha_sem_preco" | "em_jogo" | "ontem" | "ontem_sem_desfecho";
export interface PickView { mercado: string; prob01: number; fairOdd: number; bookOdd: number | null; edge: number | null; ev: number | null; classification: string; motivo: string; vale: boolean; }
export interface JogoView {
  id: string; ligaId: string; ligaNome: string; casa: string; fora: string; kickoffIso: string;
  estado: EstadoJogo;
  talao: PickView | null;        // o pick recomendado
  segundo: PickView | null;      // o segundo que vale
  direcao: PickView | null;      // so no estado "direcao"
  mercados: PickView[];          // todos, ordenados: valem, depois por edge desc
  totalAvaliados: number; totalValem: number;
  aoVivo: { periodo: string | null; minuto: number | null; placar: string | null } | null;
  resultado: { acertou: boolean; detalhe: string } | null;   // preenchido no plano 3
}
export function toJogoView(m: Match, agora: Date): JogoView;
export function escolherTalao(picks: PickView[]): { talao: PickView | null; segundo: PickView | null };
```

- [ ] **Step 1: Teste**

`tests/unit/jogoView.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { escolherTalao, toJogoView, type PickView } from "@/lib/jogoView";
import { normalizeMatch } from "@/lib/normalizeMatch";
import fixture from "../fixtures/fixtures.2026-09-15.v1.json";

const AGORA = new Date("2026-09-15T12:00:00Z");

function pick(over: Partial<PickView>): PickView {
  return { mercado: "x", prob01: 0.5, fairOdd: 2, bookOdd: 2.1, edge: 0.05, ev: 0.05,
           classification: "SAFE", motivo: "", vale: true, ...over };
}

describe("escolherTalao (spec §4.1)", () => {
  it("maior edge vence", () => {
    const a = pick({ mercado: "a", edge: 0.08 }), b = pick({ mercado: "b", edge: 0.03 });
    expect(escolherTalao([b, a])).toEqual({ talao: a, segundo: b });
  });
  it("empate de edge: maior chance", () => {
    const a = pick({ mercado: "a", edge: 0.05, prob01: 0.58 }), b = pick({ mercado: "b", edge: 0.05, prob01: 0.61 });
    expect(escolherTalao([a, b]).talao).toBe(b);
  });
  it("so quem vale disputa; sem ninguem, nulo", () => {
    const n = pick({ mercado: "n", vale: false, classification: "NEUTRO", edge: 0.9 });
    expect(escolherTalao([n])).toEqual({ talao: null, segundo: null });
  });
});

describe("toJogoView — estados (spec §4.2)", () => {
  const base = {
    id: "j1", leagueId: "mls", homeTeam: { name: "Toronto" }, awayTeam: { name: "Nashville SC" },
    datetime: "2026-09-15T23:30:00Z", status: "scheduled", odds: {}, stats: {},
  };
  const merc = (classification: string, extra = {}) => ({
    mercado: "Escanteios Over 6.5", status: classification, prob_min: 57, prob_max: 59, odd_minima: 1.75,
    classification, ev: 0.01, edge: 0.08, fair_odd: 1.67, book_odd: 1.75, calibrated_probability: 0.585,
    reason_codes: [], ...extra,
  });
  const view = (raw: object) => toJogoView(normalizeMatch(raw, "mls", 0), AGORA);

  it("vale", () => {
    const v = view({ ...base, mercados: [merc("SAFE"), merc("NEUTRO_QUALIFICADO", { mercado: "Cartoes Over 2.5", edge: 0.03 })] });
    expect(v.estado).toBe("vale");
    expect(v.talao?.mercado).toBe("Escanteios Over 6.5");
    expect(v.segundo?.mercado).toBe("Cartões Over 2.5");
    expect(v.totalAvaliados).toBe(2); expect(v.totalValem).toBe(2);
  });
  it("direcao: so NEUTRO", () => {
    const v = view({ ...base, mercados: [merc("NEUTRO", { mercado: "Over 2.5 gols", book_odd: 1.62, fair_odd: 1.75, edge: -0.13 })] });
    expect(v.estado).toBe("direcao"); expect(v.talao).toBeNull(); expect(v.direcao?.mercado).toBe("Over 2.5 gols");
  });
  it("nada: so NO_BET", () => {
    expect(view({ ...base, mercados: [merc("NO_BET", { reason_codes: ["NEGATIVE_EV"] })] }).estado).toBe("nada");
  });
  it("amanha sem preco: data futura e book_odd nulo no talao", () => {
    const v = view({ ...base, datetime: "2026-09-16T23:30:00Z", mercados: [merc("SAFE", { book_odd: null })] });
    expect(v.estado).toBe("amanha_sem_preco"); expect(v.talao?.bookOdd).toBeNull();
  });
  it("em jogo", () => {
    const v = view({ ...base, status: "live", period: "2T", minute: 61, score: { home: 1, away: 0 }, mercados: [merc("SAFE")] });
    expect(v.estado).toBe("em_jogo"); expect(v.aoVivo).toEqual({ periodo: "2T", minuto: 61, placar: "1–0" });
  });
  it("ontem sem desfecho: jogo encerrado sem resultado do ledger", () => {
    expect(view({ ...base, datetime: "2026-09-14T23:30:00Z", status: "finished", mercados: [merc("SAFE")] }).estado).toBe("ontem_sem_desfecho");
  });
  it("motivo de recusa em duas palavras", () => {
    const v = view({ ...base, mercados: [merc("NO_BET", { reason_codes: ["LOW_DATA_QUALITY"] })] });
    expect(v.mercados[0].motivo).toBe("amostra curta");
  });
  it("fixture real: todo jogo cai num estado e o talao, quando existe, vale", () => {
    for (const raw of fixture.matches as { leagueId: string }[]) {
      const v = toJogoView(normalizeMatch(raw, raw.leagueId, 0), AGORA);
      expect(["vale", "direcao", "nada", "amanha_sem_preco", "em_jogo", "ontem", "ontem_sem_desfecho"]).toContain(v.estado);
      if (v.talao) expect(v.talao.vale).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar `src/lib/jogoView.ts`**

```ts
/**
 * #254-a — `Match` → `JogoView` (spec §4.2). Funcao PURA: todo estado que
 * parece "de view" (book_odd nulo + data futura, live) e derivado aqui; o
 * CardJogo e um switch sobre `estado` e nao calcula nada.
 */
import type { Match, MatchPrediction } from "@/lib/leagues";
import { fmtMercado } from "@/lib/classifications";
import { motivoRecusa } from "@/lib/reasonCodes";
import { getLiveClock } from "@/lib/liveClock";

export type EstadoJogo = "vale" | "direcao" | "nada" | "amanha_sem_preco" | "em_jogo" | "ontem" | "ontem_sem_desfecho";

export interface PickView {
  mercado: string; prob01: number; fairOdd: number; bookOdd: number | null;
  edge: number | null; ev: number | null; classification: string; motivo: string; vale: boolean;
}

export interface JogoView {
  id: string; ligaId: string; ligaNome: string; casa: string; fora: string; kickoffIso: string;
  estado: EstadoJogo;
  talao: PickView | null; segundo: PickView | null; direcao: PickView | null;
  mercados: PickView[]; totalAvaliados: number; totalValem: number;
  aoVivo: { periodo: string | null; minuto: number | null; placar: string | null } | null;
  resultado: { acertou: boolean; detalhe: string } | null;
}

const VALE = new Set(["SAFE", "NEUTRO_QUALIFICADO"]);
const TRES_HORAS = 3 * 3600_000;

function toPick(p: MatchPrediction): PickView | null {
  const prob = p.calibrated_probability ?? (p.prob_max != null ? p.prob_max / 100 : null);
  const fair = p.fair_odd ?? (prob ? 1 / prob : null);
  if (prob == null || fair == null) return null;
  const classification = p.classification ?? p.status ?? "NEUTRO";
  return {
    mercado: fmtMercado(p.mercado), prob01: prob, fairOdd: fair,
    bookOdd: p.book_odd != null && p.book_odd > 1 ? p.book_odd : null,
    edge: p.edge ?? null, ev: p.ev ?? null, classification,
    motivo: VALE.has(classification) ? "" : motivoRecusa(p.reason_codes ?? []),
    vale: VALE.has(classification),
  };
}

export function escolherTalao(picks: PickView[]): { talao: PickView | null; segundo: PickView | null } {
  const valem = picks.filter((p) => p.vale).sort((a, b) =>
    (b.edge ?? -Infinity) - (a.edge ?? -Infinity) || b.prob01 - a.prob01);
  return { talao: valem[0] ?? null, segundo: valem[1] ?? null };
}

export function toJogoView(m: Match, agora: Date): JogoView {
  const picks = (m.predictions ?? []).map(toPick).filter((p): p is PickView => p !== null);
  const { talao, segundo } = escolherTalao(picks);
  const ordenados = [...picks].sort((a, b) => Number(b.vale) - Number(a.vale) || (b.edge ?? -1) - (a.edge ?? -1));
  const kickoff = new Date(m.datetime).getTime();
  const clock = m.status === "live" ? getLiveClock(m, agora.getTime()) : null;
  const aoVivo = m.status === "live"
    ? { periodo: clock?.period ?? m.period ?? null, minuto: clock?.minute ?? m.minute ?? null,
        placar: m.score ? `${m.score.home}\u2013${m.score.away}` : null }
    : null;
  const direcao = talao ? null : ordenados.find((p) => p.classification === "NEUTRO") ?? null;

  let estado: EstadoJogo;
  if (m.status === "live") estado = "em_jogo";
  else if (m.status === "finished" || kickoff < agora.getTime() - TRES_HORAS) estado = "ontem_sem_desfecho";
  else if (talao && talao.bookOdd === null && kickoff > agora.getTime()) estado = "amanha_sem_preco";
  else if (talao) estado = "vale";
  else if (direcao) estado = "direcao";
  else estado = "nada";

  return {
    id: m.id, ligaId: m.leagueId, ligaNome: m.leagueName, casa: m.homeTeam.name, fora: m.awayTeam.name,
    kickoffIso: m.datetime, estado, talao, segundo, direcao, mercados: ordenados,
    totalAvaliados: picks.length, totalValem: picks.filter((p) => p.vale).length,
    aoVivo, resultado: null,
  };
}
```
Nota: `getLiveClock` recebe `LiveClockSource` (`src/lib/liveClock.ts:100-120`); se `Match` não for aceito direto, passar só os campos que o type pede. `LiveClock` expõe `period` e `minute` — conferir os nomes no arquivo antes de usar.

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/jogoView.test.ts` e `npx tsc --noEmit`.
- [ ] **Step 5: Snapshot do fixture** — acrescentar ao teste:
```ts
it("snapshot do fixture real", () => {
  const views = (fixture.matches as { leagueId: string }[]).map((r) => toJogoView(normalizeMatch(r, r.leagueId, 0), AGORA));
  expect(views.map((v) => ({ id: v.id, estado: v.estado, talao: v.talao?.mercado ?? null, valem: v.totalValem }))).toMatchSnapshot();
});
```
Rodar uma vez para gravar `tests/unit/__snapshots__/jogoView.test.ts.snap`; **ler o snapshot** e conferir que cada jogo caiu no estado esperado pelo README do fixture.
- [ ] **Step 6: Commit** — `git add frontend/next/src/lib/jogoView.ts frontend/next/tests/unit && git commit -m "feat(front): jogoView puro com enum de estados e regra do talao (#254-a)"`

---

### Task 11: Fechar a fase 2 — REGISTRO, espelho, push

- [ ] **Step 1:** `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test --project=chromium` → verde; dashboard visualmente idêntico (abrir `/dashboard` e comparar com o screenshot da fase 0).
- [ ] **Step 2:** Entrada `## 254-a — Reformulação do frontend, fase 2: jogoView puro, zero mudança visual` no REGISTRO (Prova empírica: `git diff --color-moved` mostrando só movimento; placar do Playwright igual antes/depois; snapshot do fixture com um jogo por estado). Linha no INDICE.
- [ ] **Step 3:** Espelhar, commit `docs: REGISTRO #254-a fase 2`, push, CI.

---

## Fase 3 — `/jogos`: feed, talão, detalhe e banca

Convenções desta fase: componentes em `"use client"` só quando têm estado ou handlers; classes Tailwind com valores arbitrários dos tokens (`bg-[var(--sb-painel)]`), sem cor fora dos tokens; toda string visível vem de `lib/copy.ts`. Testes de componente com Testing Library (Vitest + jsdom); estados e URL com Playwright.

### Task 12: `Talao` e `BotaoCopiar`

**Files:**
- Create: `frontend/next/src/components/feed/Talao.tsx`, `frontend/next/src/components/feed/BotaoCopiar.tsx`, `frontend/next/tests/unit/Talao.test.tsx`

**Interfaces:**
- Consumes: `PickView` (Task 10), `frequencia`, `linhaPreco`, `COPIAR`, `VAZIOS` (Task 4), `fmtOdd` (Task 3).
- Produces: `<Talao pick={PickView} futuro={boolean} preJogo={boolean} />` e `<BotaoCopiar odd={number} sobre?="talao" | "painel" />`.

- [ ] **Step 1: Teste**

`tests/unit/Talao.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Talao } from "@/components/feed/Talao";

const pick = { mercado: "Mais de 6,5 escanteios", prob01: 0.585, fairOdd: 1.67, bookOdd: 1.75,
               edge: 0.08, ev: 0.02, classification: "SAFE", motivo: "", vale: true };

describe("Talao (spec §4.1)", () => {
  it("veredito, frequencia e linha de preco", () => {
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    expect(screen.getByRole("heading", { name: "Mais de 6,5 escanteios" })).toBeInTheDocument();
    expect(screen.getByText("acontece em 58 de cada 100 jogos assim")).toBeInTheDocument();
    expect(screen.getByText("mercado paga 1,75, acima do mínimo 1,67 (+0,08)")).toBeInTheDocument();
  });
  it("abaixo do minimo: glifo ↓ e data-estado; sem cor de contra dentro do talao", () => {
    render(<Talao pick={{ ...pick, bookOdd: 1.62, fairOdd: 1.75 }} futuro={false} preJogo={false} />);
    const linha = screen.getByText(/abaixo do mínimo 1,75/);
    expect(linha).toHaveAttribute("data-estado", "abaixo");
    expect(linha.textContent?.startsWith("↓")).toBe(true);
    expect(linha).not.toHaveStyle({ color: "var(--sb-contra-texto)" });
  });
  it("amanha sem preco nao mostra botao de copiar", () => {
    render(<Talao pick={{ ...pick, bookOdd: null }} futuro preJogo={false} />);
    expect(screen.getByText("vale a partir de 1,67, mercado ainda sem preço")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /copiar/ })).toBeNull();
  });
  it("em jogo: sufixo recomendacao pre-jogo", () => {
    render(<Talao pick={pick} futuro={false} preJogo />);
    expect(screen.getByText("recomendação pré-jogo")).toBeInTheDocument();
  });
  it("copiar copia so o numero e confirma no mesmo slot", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    fireEvent.click(screen.getByRole("button", { name: "copiar odd 1,75" }));
    expect(writeText).toHaveBeenCalledWith("1.75");
    await waitFor(() => expect(screen.getByText("1,75 copiado")).toBeInTheDocument());
  });
  it("clipboard negado: contra-texto inline, sem toast", async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("negado")) } });
    render(<Talao pick={pick} futuro={false} preJogo={false} />);
    fireEvent.click(screen.getByRole("button", { name: "copiar odd 1,75" }));
    await waitFor(() => expect(screen.getByText("não deu pra copiar — selecione o número")).toBeInTheDocument());
  });
  it("nada dentro do talao usa a cor confianca", () => {
    const { container } = render(<Talao pick={pick} futuro={false} preJogo={false} />);
    expect(container.innerHTML).not.toContain("--sb-confianca");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`src/components/feed/BotaoCopiar.tsx`:
```tsx
"use client";
import { useState } from "react";
import { COPIAR } from "@/lib/copy";

/** Copia so o numero da odd; confirma ou avisa no MESMO slot (sem layout shift). */
export function BotaoCopiar({ odd, sobre = "talao" }: { odd: number; sobre?: "talao" | "painel" }) {
  const [estado, setEstado] = useState<"parado" | "ok" | "falhou">("parado");
  async function copiar() {
    try {
      await navigator.clipboard.writeText(String(odd));
      setEstado("ok");
    } catch {
      setEstado("falhou");
    }
    setTimeout(() => setEstado("parado"), 2500);
  }
  return (
    <span className="inline-flex min-h-[28px] items-center gap-2 text-[14px]">
      {estado === "ok" && <span aria-live="polite">{COPIAR.ok(odd)}</span>}
      {estado === "falhou" && <span aria-live="polite" className="text-[var(--sb-contra-texto)]">{COPIAR.falhou}</span>}
      {estado === "parado" && (
        <button type="button" onClick={copiar} aria-label={COPIAR.rotulo(odd)}
          className={`sb-foco rounded-[4px] border px-2 py-0.5 text-[13px] ${sobre === "talao"
            ? "border-[var(--sb-tinta-apoiada)] text-[var(--sb-tinta-do-talao)]"
            : "border-[var(--sb-linha)] text-[var(--sb-texto)]"}`}>
          copiar
        </button>
      )}
    </span>
  );
}
```

`src/components/feed/Talao.tsx`:
```tsx
import type { PickView } from "@/lib/jogoView";
import { frequencia, linhaPreco, VAZIOS } from "@/lib/copy";
import { BotaoCopiar } from "@/components/feed/BotaoCopiar";

/**
 * O pick recomendado — o unico objeto amarelo da tela (spec §4.1). Dentro
 * dele so `tinta-do-talao` e `tinta-apoiada`; `confianca` nunca entra (1,7:1).
 */
export function Talao({ pick, futuro, preJogo }: { pick: PickView; futuro: boolean; preJogo: boolean }) {
  const preco = linhaPreco(pick.bookOdd, pick.fairOdd, futuro);
  return (
    <section className="sb-talao relative my-3 rounded-[var(--sb-raio-talao)] bg-[var(--sb-talao)] px-4 pb-3 pt-4 text-[var(--sb-tinta-do-talao)]"
      aria-label="pick recomendado">
      <h3 className="font-[family-name:var(--font-slab)] text-[28px] font-bold leading-[1.05]">{pick.mercado}</h3>
      <p className="mt-1 text-[14px] text-[var(--sb-tinta-apoiada)]">{frequencia(pick.prob01)}</p>
      <div className="my-3 border-t border-dashed border-[var(--sb-tinta-apoiada)]" aria-hidden="true" />
      <p className="tnum text-[14px] font-semibold" data-estado={preco.abaixo ? "abaixo" : preco.semPreco ? "sem-preco" : "acima"}>
        {preco.abaixo ? "↓ " : ""}{preco.texto}
        {preJogo && <span className="ml-2 font-normal text-[var(--sb-tinta-apoiada)]">{VAZIOS.recomendacaoPreJogo}</span>}
      </p>
      {!preco.semPreco && pick.bookOdd != null && (
        <div className="mt-2 flex justify-end"><BotaoCopiar odd={pick.bookOdd} /></div>
      )}
    </section>
  );
}
```
Por que a linha "abaixo" no talão **não** usa `contra-texto`: `#E8665A` sobre `#E3D9AE` dá ~2,3:1. Dentro do talão só tinta; o estado vai no glifo `↓` e no `data-estado`. A cor `contra-texto` só aparece fora do talão (tabela do detalhe, faixa de ontem). Acrescentar ao teste de tokens: `expect(PARES_PERMITIDOS.some(([t, f]) => t === "contra-texto" && f === "talao")).toBe(false)`.

As meias-luas do talão (recorte lateral) em `globals.css`:
```css
.sb-talao::before, .sb-talao::after {
  content: ""; position: absolute; top: 50%; width: 14px; height: 14px; margin-top: -7px;
  border-radius: 50%; background: var(--sb-painel);
}
.sb-talao::before { left: -7px; } .sb-talao::after { right: -7px; }
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/Talao.test.tsx`; `npm run lint:accents`.
- [ ] **Step 5: Commit** — `git add frontend/next/src/components/feed frontend/next/tests/unit/Talao.test.tsx frontend/next/src/app/globals.css && git commit -m "feat(front): Talao e BotaoCopiar (#254-b)"`

---

### Task 13: Linhas do card — stake, confiança, segundo pick, avaliados

**Files:**
- Create: `frontend/next/src/lib/confiancaLiga.ts`, `frontend/next/src/components/feed/LinhaStake.tsx`, `frontend/next/src/components/feed/LinhaConfianca.tsx`, `frontend/next/src/components/feed/LinhaSegundoPick.tsx`, `frontend/next/src/components/feed/LinhaAvaliados.tsx`, `frontend/next/tests/unit/linhas.test.tsx`

**Interfaces:**
- Consumes: `LeagueConfidence` (`hooks/useLeagueClassifications.ts`), `useBanca`, `calcStake` (Task 5), `stake`, `avaliados` (Task 4), `fmtPct`, `fmtOdd`, `fmtDelta`.
- Produces:
  - `fraseConfianca(c: LeagueConfidence | null, ligaNome: string): { texto: string; numero: number | null; semBase: boolean }` em `lib/confiancaLiga.ts`
  - `<LinhaStake pick={PickView} />` (lê a banca do store)
  - `<LinhaConfianca confianca={LeagueConfidence | null} ligaNome={string} />`
  - `<LinhaSegundoPick pick={PickView} />`
  - `<LinhaAvaliados total={number} valem={number} href={string} />`

- [ ] **Step 1: Teste**

`tests/unit/linhas.test.tsx`:
```tsx
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { fraseConfianca } from "@/lib/confiancaLiga";
import { LinhaStake } from "@/components/feed/LinhaStake";
import { LinhaConfianca } from "@/components/feed/LinhaConfianca";
import { LinhaSegundoPick } from "@/components/feed/LinhaSegundoPick";
import { LinhaAvaliados } from "@/components/feed/LinhaAvaliados";
import { setBanca } from "@/lib/bancaStore";

const pick = { mercado: "Mais de 2,5 cartões", prob01: 0.59, fairOdd: 1.67, bookOdd: 1.7,
               edge: 0.03, ev: 0.003, classification: "NEUTRO_QUALIFICADO", motivo: "", vale: true };
const conf = (over: object) => ({ leagueId: "mls", level: "ML_ACTIVE", brier: 0.2, accuracy: 0.58, nSamples: 40, trainedAt: null, ...over } as never);

describe("fraseConfianca (os 4 estados do #250 sem sigla)", () => {
  it("ML_ACTIVE com accuracy na media", () => {
    expect(fraseConfianca(conf({}), "MLS")).toEqual({ texto: "MLS: 40 jogos medidos, acerto na média das ligas", numero: 40, semBase: false });
  });
  it("acima e abaixo da media", () => {
    expect(fraseConfianca(conf({ accuracy: 0.66 }), "MLS").texto).toContain("acima da média");
    expect(fraseConfianca(conf({ accuracy: 0.5 }), "MLS").texto).toContain("abaixo da média");
  });
  it("POISSON e ML_SUPPRESSED: modelo geral, sem afirmar acerto", () => {
    expect(fraseConfianca(conf({ level: "POISSON", accuracy: null, nSamples: null }), "MLS")).toEqual({ texto: "MLS: modelo geral, sem histórico próprio", numero: null, semBase: true });
    expect(fraseConfianca(conf({ level: "ML_SUPPRESSED", nSamples: 6, accuracy: null }), "MLS")).toEqual({ texto: "MLS: 6 jogos medidos, ainda sem base", numero: 6, semBase: true });
  });
  it("UNVERIFIED ou nulo: nao afirma nada", () => {
    expect(fraseConfianca(null, "MLS")).toEqual({ texto: "MLS: confiança não verificada", numero: null, semBase: true });
  });
});

describe("linhas do card", () => {
  beforeEach(() => localStorage.clear());
  it("stake com banca definida", () => {
    setBanca(1000);
    render(<LinhaStake pick={pick} />);
    expect(screen.getByText(/Da sua banca de R\$ 1\.000,00: R\$/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ajustar" })).toHaveAttribute("href", "/banca");
  });
  it("stake sem banca: chama para definir", () => {
    render(<LinhaStake pick={pick} />);
    expect(screen.getByRole("link", { name: "stake: defina sua banca" })).toHaveAttribute("href", "/banca");
  });
  it("confianca: numero em teal, semBase em texto-apagado", () => {
    const { rerender } = render(<LinhaConfianca confianca={conf({})} ligaNome="MLS" />);
    expect(screen.getByText("40")).toHaveClass("text-[var(--sb-confianca)]");
    rerender(<LinhaConfianca confianca={null} ligaNome="MLS" />);
    expect(screen.getByText(/não verificada/)).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("segundo pick: frase completa, sem botao", () => {
    render(<LinhaSegundoPick pick={pick} />);
    expect(screen.getByText("Mais de 2,5 cartões")).toBeInTheDocument();
    expect(screen.getByText("59 em 100, paga 1,70 (+0,03)")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("avaliados com link para #mercados", () => {
    render(<LinhaAvaliados total={12} valem={2} href="/jogos/j1#mercados" />);
    expect(screen.getByRole("link", { name: "ver todos" })).toHaveAttribute("href", "/jogos/j1#mercados");
    expect(screen.getByText(/12 mercados avaliados, 2 valem/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`src/lib/confiancaLiga.ts`:
```ts
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
/** #254-b — os quatro estados do #250 viram uma frase de operador (spec §4.1). */
const MEDIA_DAS_LIGAS = 0.58; // acerto medio medido no ledger em 2026-09-15 (spec §5); atualizar com /ledger/agregado no plano 3
const FAIXA = 0.04;

export function fraseConfianca(c: LeagueConfidence | null, ligaNome: string) {
  if (!c || c.level === "UNVERIFIED") return { texto: `${ligaNome}: confiança não verificada`, numero: null, semBase: true };
  if (c.level === "POISSON") return { texto: `${ligaNome}: modelo geral, sem histórico próprio`, numero: null, semBase: true };
  const n = c.nSamples ?? 0;
  if (c.level === "ML_SUPPRESSED" || c.accuracy == null || n < 20) {
    return { texto: `${ligaNome}: ${n} jogos medidos, ainda sem base`, numero: n, semBase: true };
  }
  const rel = c.accuracy - MEDIA_DAS_LIGAS;
  const onde = rel > FAIXA ? "acima da média" : rel < -FAIXA ? "abaixo da média" : "na média das ligas";
  return { texto: `${ligaNome}: ${n} jogos medidos, acerto ${onde}`, numero: n, semBase: false };
}
```

`src/components/feed/LinhaStake.tsx`:
```tsx
"use client";
import Link from "next/link";
import type { PickView } from "@/lib/jogoView";
import { useBanca, calcStake } from "@/lib/bancaStore";
import { stake } from "@/lib/copy";

export function LinhaStake({ pick }: { pick: PickView }) {
  const [banca] = useBanca();
  if (banca == null || pick.bookOdd == null) {
    return <p className="text-[14px]"><Link href="/banca" className="sb-foco underline">{stake(null, null)}</Link></p>;
  }
  const valor = calcStake(pick.prob01, pick.bookOdd, banca, pick.classification);
  return (
    <p className="tnum flex justify-between text-[14px]">
      <span>{stake(banca, valor)}</span>
      <Link href="/banca" className="sb-foco underline">ajustar</Link>
    </p>
  );
}
```

`src/components/feed/LinhaConfianca.tsx`:
```tsx
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { fraseConfianca } from "@/lib/confiancaLiga";

export function LinhaConfianca({ confianca, ligaNome }: { confianca: LeagueConfidence | null; ligaNome: string }) {
  const f = fraseConfianca(confianca, ligaNome);
  if (f.semBase || f.numero == null) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{f.texto}</p>;
  const [antes, depois] = f.texto.split(String(f.numero));
  return (
    <p className="text-[13px]">
      {antes}<span className="tnum font-semibold text-[var(--sb-confianca)]">{f.numero}</span>{depois}
    </p>
  );
}
```

`src/components/feed/LinhaSegundoPick.tsx`:
```tsx
import type { PickView } from "@/lib/jogoView";
import { fmtDelta, fmtOdd, fmtPct } from "@/lib/formato";

export function LinhaSegundoPick({ pick }: { pick: PickView }) {
  const preco = pick.bookOdd != null ? `paga ${fmtOdd(pick.bookOdd)} (${fmtDelta(pick.bookOdd - pick.fairOdd)})` : `a partir de ${fmtOdd(pick.fairOdd)}`;
  return (
    <p className="flex justify-between gap-3 text-[14px]">
      <span>{pick.mercado}</span>
      <span className="tnum">{fmtPct(pick.prob01)} em 100, {preco}</span>
    </p>
  );
}
```

`src/components/feed/LinhaAvaliados.tsx`:
```tsx
import Link from "next/link";
import { avaliados } from "@/lib/copy";

export function LinhaAvaliados({ total, valem, href }: { total: number; valem: number; href: string }) {
  return (
    <p className="text-[13px] text-[var(--sb-texto-apagado)]">
      {avaliados(total, valem)} — <Link href={href} className="sb-foco text-[var(--sb-texto)] underline">ver todos</Link>
    </p>
  );
}
```

- [ ] **Step 4: Rodar e ver passar; lint de acentos.**
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/confiancaLiga.ts frontend/next/src/components/feed frontend/next/tests/unit/linhas.test.tsx && git commit -m "feat(front): linhas do card e frase de confianca sem sigla (#254-b)"`

---

### Task 14: `CardJogo` — o switch sobre o estado

**Files:**
- Create: `frontend/next/src/components/feed/CardJogo.tsx`, `frontend/next/tests/unit/CardJogo.test.tsx`

**Interfaces:**
- Consumes: `JogoView` (Task 10), `Talao`, as quatro linhas (Tasks 12–13), `direcao`, `avaliados`, `resultadoOntem`, `VAZIOS` (Task 4), `fmtLigaHora`.
- Produces: `<CardJogo jogo={JogoView} confianca={LeagueConfidence | null} selecionado={boolean} onAbrir?={(id) => void} hrefDetalhe={string} />` — sem `onAbrir` (celular) o titulo e um `<Link>` para `hrefDetalhe`.

- [ ] **Step 1: Teste**

`tests/unit/CardJogo.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CardJogo } from "@/components/feed/CardJogo";
import type { JogoView, PickView } from "@/lib/jogoView";

const p = (o: Partial<PickView>): PickView => ({ mercado: "Mais de 6,5 escanteios", prob01: 0.585, fairOdd: 1.67, bookOdd: 1.75, edge: 0.08, ev: 0.02, classification: "SAFE", motivo: "", vale: true, ...o });
const base: JogoView = { id: "j1", ligaId: "mls", ligaNome: "MLS", casa: "Toronto", fora: "Nashville SC", kickoffIso: "2026-09-09T23:30:00Z",
  estado: "vale", talao: p({}), segundo: null, direcao: null, mercados: [p({})], totalAvaliados: 12, totalValem: 1, aoVivo: null, resultado: null };
const render_ = (j: JogoView) => render(<CardJogo jogo={j} confianca={null} selecionado={false} onAbrir={() => {}} hrefDetalhe="/jogos/j1" />);

describe("CardJogo e um switch sobre o estado (spec §4.2)", () => {
  it("vale: talao + stake + confianca + avaliados; cabecalho 'MLS, 20:30'", () => {
    render_(base);
    expect(screen.getByText("MLS, 20:30")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "pick recomendado" })).toBeInTheDocument();
    expect(screen.getByText(/12 mercados avaliados, 1 vale/)).toBeInTheDocument();
  });
  it("direcao: sem talao, sem stake, frase de direcao", () => {
    render_({ ...base, estado: "direcao", talao: null, direcao: p({ mercado: "Mais de 2,5 gols", prob01: 0.57, classification: "NEUTRO", vale: false }) });
    expect(screen.queryByRole("region", { name: "pick recomendado" })).toBeNull();
    expect(screen.getByText("Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje")).toBeInTheDocument();
    expect(screen.queryByText(/banca/)).toBeNull();
  });
  it("nada: uma linha colapsada", () => {
    render_({ ...base, estado: "nada", talao: null, totalValem: 0 });
    expect(screen.getByText("12 mercados avaliados, nenhum vale hoje")).toBeInTheDocument();
  });
  it("em jogo: periodo, minuto, placar", () => {
    render_({ ...base, estado: "em_jogo", aoVivo: { periodo: "2T", minuto: 61, placar: "1–0" } });
    expect(screen.getByText("2T, 61' 1–0")).toBeInTheDocument();
    expect(screen.getByText("recomendação pré-jogo")).toBeInTheDocument();
  });
  it("ontem: faixa de resultado com glifo", () => {
    render_({ ...base, estado: "ontem", resultado: { acertou: false, detalhe: "5 escanteios" } });
    expect(screen.getByText("× fechou com 5 escanteios")).toHaveClass("text-[var(--sb-contra-texto)]");
  });
  it("ontem sem desfecho", () => {
    render_({ ...base, estado: "ontem_sem_desfecho" });
    expect(screen.getByText("resultado ainda não conferido")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar `src/components/feed/CardJogo.tsx`**

```tsx
"use client";
import Link from "next/link";
import type { JogoView } from "@/lib/jogoView";
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { Talao } from "@/components/feed/Talao";
import { LinhaStake } from "@/components/feed/LinhaStake";
import { LinhaConfianca } from "@/components/feed/LinhaConfianca";
import { LinhaSegundoPick } from "@/components/feed/LinhaSegundoPick";
import { LinhaAvaliados } from "@/components/feed/LinhaAvaliados";
import { avaliados, direcao, resultadoOntem, VAZIOS } from "@/lib/copy";
import { fmtLigaHora } from "@/lib/formato";

interface Props { jogo: JogoView; confianca: LeagueConfidence | null; selecionado: boolean; onAbrir?: (id: string) => void; hrefDetalhe: string; }

/** Nao calcula nada: le `jogo.estado` e escolhe o que mostrar (spec §4.2). */
export function CardJogo({ jogo, confianca, selecionado, onAbrir, hrefDetalhe }: Props) {
  const topo = jogo.aoVivo
    ? `${jogo.aoVivo.periodo ?? ""}${jogo.aoVivo.minuto != null ? `, ${jogo.aoVivo.minuto}'` : ""}${jogo.aoVivo.placar ? ` ${jogo.aoVivo.placar}` : ""}`.trim()
    : fmtLigaHora(jogo.ligaNome, jogo.kickoffIso);
  const corpo = (() => {
    switch (jogo.estado) {
      case "nada":
        return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{avaliados(jogo.totalAvaliados, 0)}</p>;
      case "direcao":
        return (
          <>
            <p className="text-[16px]">{direcao(jogo.direcao!.mercado, jogo.direcao!.prob01)}</p>
            <LinhaConfianca confianca={confianca} ligaNome={jogo.ligaNome} />
            <LinhaAvaliados total={jogo.totalAvaliados} valem={0} href={`${hrefDetalhe}#mercados`} />
          </>
        );
      default: {
        const t = jogo.talao;
        if (!t) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{avaliados(jogo.totalAvaliados, 0)}</p>;
        return (
          <>
            <Talao pick={t} futuro={jogo.estado === "amanha_sem_preco"} preJogo={jogo.estado === "em_jogo"} />
            {jogo.estado === "ontem" && jogo.resultado && (
              <p className={jogo.resultado.acertou ? "text-[14px]" : "text-[14px] text-[var(--sb-contra-texto)]"}>
                {resultadoOntem(jogo.resultado.acertou, jogo.resultado.detalhe)}
              </p>
            )}
            {jogo.estado === "ontem_sem_desfecho" && <p className="text-[13px] text-[var(--sb-texto-apagado)]">{VAZIOS.resultadoPendente}</p>}
            {(jogo.estado === "vale" || jogo.estado === "em_jogo") && <LinhaStake pick={t} />}
            <LinhaConfianca confianca={confianca} ligaNome={jogo.ligaNome} />
            {jogo.segundo && <LinhaSegundoPick pick={jogo.segundo} />}
            <LinhaAvaliados total={jogo.totalAvaliados} valem={jogo.totalValem} href={`${hrefDetalhe}#mercados`} />
          </>
        );
      }
    }
  })();
  return (
    <article data-estado={jogo.estado} data-selecionado={selecionado}
      className="space-y-2 rounded-[var(--sb-raio-painel)] border border-[var(--sb-linha)] bg-[var(--sb-painel)] p-4 hover:bg-[var(--sb-hover)] data-[selecionado=true]:border-[var(--sb-texto)]">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">
          <Link href={hrefDetalhe} onClick={(e) => { if (onAbrir) { e.preventDefault(); onAbrir(jogo.id); } }} className="sb-foco">
            {jogo.casa} × {jogo.fora}
          </Link>
        </h2>
        <span className="tnum text-[13px] text-[var(--sb-texto-apagado)]">{topo}</span>
      </header>
      {corpo}
    </article>
  );
}
```
- [ ] **Step 4: Rodar e ver passar.**
- [ ] **Step 5: Commit** — `git add frontend/next/src/components/feed/CardJogo.tsx frontend/next/tests/unit/CardJogo.test.tsx && git commit -m "feat(front): CardJogo, switch sobre o estado (#254-b)"`

---

### Task 15: `/jogos` — feed com estado na URL

**Files:**
- Create: `frontend/next/src/app/jogos/page.tsx`, `frontend/next/src/app/jogos/Feed.tsx`, `frontend/next/src/components/feed/DiaTabs.tsx`, `frontend/next/src/components/feed/LigaChips.tsx`, `frontend/next/src/lib/feedUrl.ts`, `frontend/next/tests/unit/feedUrl.test.ts`, `frontend/next/e2e/jogos.spec.ts`, `frontend/next/e2e/fixtures/feed.json`

**Interfaces:**
- Consumes: `getMatchesByLeague(leagues: string, date?: string)` (`lib/api.ts`), `normalizeMatch`, `deduplicateMatches` (Task 8), `toJogoView` (Task 10), `useLeagueClassifications` (hook existente), `useLivePolling`, `useMediaQuery`, `ACTIVE_LEAGUES()` (`lib/leagues.ts`), `CardJogo`.
- Produces: `lerFeedUrl(params: URLSearchParams): { dia: "ontem" | "hoje" | "amanha"; liga: string | "todas"; jogo: string | null }`, `escreverFeedUrl(estado): string`, `diaParaApi(dia): "today" | "tomorrow"`.

- [ ] **Step 1: Teste da URL**

`tests/unit/feedUrl.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { lerFeedUrl, escreverFeedUrl, diaParaApi } from "@/lib/feedUrl";

describe("estado do feed vive na URL (spec §3)", () => {
  it("padrao: hoje, todas, sem jogo", () => {
    expect(lerFeedUrl(new URLSearchParams(""))).toEqual({ dia: "hoje", liga: "todas", jogo: null });
  });
  it("le e escreve os tres parametros", () => {
    const e = lerFeedUrl(new URLSearchParams("dia=amanha&liga=mls&jogo=j1"));
    expect(e).toEqual({ dia: "amanha", liga: "mls", jogo: "j1" });
    expect(escreverFeedUrl(e)).toBe("/jogos?dia=amanha&liga=mls&jogo=j1");
    expect(escreverFeedUrl({ dia: "hoje", liga: "todas", jogo: null })).toBe("/jogos");
  });
  it("valor invalido cai no padrao", () => {
    expect(lerFeedUrl(new URLSearchParams("dia=semana")).dia).toBe("hoje");
  });
  it("mapeia para o parametro do backend; ontem nao tem fonte ate o plano 3", () => {
    expect(diaParaApi("hoje")).toBe("today");
    expect(diaParaApi("amanha")).toBe("tomorrow");
    expect(diaParaApi("ontem")).toBeNull();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar `src/lib/feedUrl.ts`**

```ts
export type Dia = "ontem" | "hoje" | "amanha";
export interface FeedUrl { dia: Dia; liga: string; jogo: string | null }
const DIAS: Dia[] = ["ontem", "hoje", "amanha"];

export function lerFeedUrl(params: URLSearchParams): FeedUrl {
  const dia = params.get("dia");
  return {
    dia: DIAS.includes(dia as Dia) ? (dia as Dia) : "hoje",
    liga: params.get("liga") || "todas",
    jogo: params.get("jogo") || null,
  };
}
export function escreverFeedUrl(e: FeedUrl): string {
  const p = new URLSearchParams();
  if (e.dia !== "hoje") p.set("dia", e.dia);
  if (e.liga !== "todas") p.set("liga", e.liga);
  if (e.jogo) p.set("jogo", e.jogo);
  const q = p.toString();
  return q ? `/jogos?${q}` : "/jogos";
}
/** `ontem` vem de /ledger/dia (plano 3); ate la o feed mostra o vazio "sem fonte". */
export function diaParaApi(dia: Dia): "today" | "tomorrow" | null {
  return dia === "hoje" ? "today" : dia === "amanha" ? "tomorrow" : null;
}
```
Rodar o teste → PASS. Commit: `git add frontend/next/src/lib/feedUrl.ts frontend/next/tests/unit/feedUrl.test.ts && git commit -m "feat(front): estado do feed na URL (#254-b)"`.

- [ ] **Step 3: Fixture e teste E2E do feed (falha: rota não existe)**

`e2e/fixtures/feed.json`: copiar `tests/fixtures/fixtures.2026-09-15.v1.json` e reduzir a **quatro** jogos, um por estado (`vale`, `direcao`, `nada`, `em_jogo`), com `leagueId` em duas ligas distintas. Manter o campo `matches` no mesmo formato que `/api/matches/fetch` devolve (`{ matches: [...] }`).

`e2e/jogos.spec.ts`:
```ts
import { test, expect, type Page } from "@playwright/test";
import feed from "./fixtures/feed.json";

async function stub(page: Page, opts: { vazio?: boolean; erro?: boolean } = {}) {
  await page.route("**/api/matches/fetch**", (route) => {
    if (opts.erro) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ matches: [], _error: { kind: "TIMEOUT", message: "x" } }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(opts.vazio ? { matches: [] } : feed) });
  });
  await page.route("**/api/matches/live**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
  await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
}

test.describe("/jogos (#254-b)", () => {
  test("um card por jogo, cada um no seu estado", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
    for (const e of ["vale", "direcao", "nada", "em_jogo"]) await expect(page.locator(`article[data-estado='${e}']`)).toHaveCount(1);
    await expect(page.getByRole("region", { name: "pick recomendado" })).toHaveCount(2); // vale + em_jogo
  });
  test("tabs de dia e chips de liga escrevem na URL", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await page.getByRole("tab", { name: "Amanhã" }).click();
    await expect(page).toHaveURL(/dia=amanha/);
    await page.getByRole("button", { name: "MLS" }).click();
    await expect(page).toHaveURL(/liga=mls/);
    await expect(page.locator("article[data-estado]")).toHaveCount(await page.locator("article[data-liga='mls']").count());
  });
  test("dia sem jogos: frase e link para o proximo dia", async ({ page }) => {
    await stub(page, { vazio: true });
    await page.goto("/jogos");
    await expect(page.getByText(/Nenhum jogo nas ligas escolhidas/)).toBeVisible();
    await expect(page.getByRole("link", { name: /próximo dia/ })).toBeVisible();
  });
  test("backend fora: mensagem, tentar de novo, e o ultimo feed fica com carimbo", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
    await stub(page, { erro: true });
    await page.getByRole("tab", { name: "Amanhã" }).click();
    await expect(page.getByText("Os jogos de hoje não carregaram.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar de novo" })).toBeVisible();
    await expect(page.getByText(/^de \d\d:\d\d$/)).toBeVisible();
    await expect(page.locator("article[data-estado]")).toHaveCount(4);
  });
  test("desktop: ?jogo= abre o painel e voltar fecha", async ({ page }, info) => {
    test.skip(info.project.name === "mobile", "painel lateral so no desktop");
    await stub(page);
    await page.goto("/jogos");
    await page.locator("article[data-estado='vale'] h2 a").click();
    await expect(page).toHaveURL(/jogo=/);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeVisible();
    await page.goBack();
    await expect(page).not.toHaveURL(/jogo=/);
    await expect(page.getByRole("complementary", { name: "detalhe do jogo" })).toBeHidden();
  });
  test("mobile: tocar no card navega para /jogos/[id]", async ({ page }, info) => {
    test.skip(info.project.name !== "mobile");
    await stub(page);
    await page.goto("/jogos");
    await page.locator("article[data-estado='vale'] h2 a").click();
    await expect(page).toHaveURL(/\/jogos\/[^?]+$/);
  });
  test("acessibilidade basica: foco visivel no primeiro link", async ({ page }) => {
    await stub(page);
    await page.goto("/jogos");
    await page.keyboard.press("Tab");
    const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineWidth);
    expect(outline).not.toBe("0px");
  });
});
```

- [ ] **Step 4: Implementar `DiaTabs`, `LigaChips`, `Feed` e a página**

`src/components/feed/DiaTabs.tsx`:
```tsx
"use client";
import type { Dia } from "@/lib/feedUrl";
const ROTULO: Record<Dia, string> = { ontem: "Ontem", hoje: "Hoje", amanha: "Amanhã" };
export function DiaTabs({ dia, onChange }: { dia: Dia; onChange: (d: Dia) => void }) {
  return (
    <div role="tablist" aria-label="dia" className="flex gap-1 border-b border-[var(--sb-linha)]">
      {(["ontem", "hoje", "amanha"] as Dia[]).map((d) => (
        <button key={d} role="tab" aria-selected={d === dia} onClick={() => onChange(d)}
          className="sb-foco px-3 py-2 text-[14px] aria-selected:border-b-2 aria-selected:border-[var(--sb-texto)] aria-selected:font-semibold">
          {ROTULO[d]}
        </button>
      ))}
    </div>
  );
}
```

`src/components/feed/LigaChips.tsx`:
```tsx
"use client";
export function LigaChips({ ligas, ativa, onChange }: { ligas: { id: string; nome: string }[]; ativa: string; onChange: (id: string) => void }) {
  const todas = [{ id: "todas", nome: "todas" }, ...ligas];
  return (
    <div className="relative">
      <div className="flex gap-2 overflow-x-auto whitespace-nowrap py-2 [scrollbar-width:none]" aria-label="ligas">
        {todas.map((l) => (
          <button key={l.id} type="button" aria-pressed={l.id === ativa} onClick={() => onChange(l.id)}
            className="sb-foco rounded-full border border-[var(--sb-linha)] px-3 py-1 text-[13px] aria-pressed:border-[var(--sb-texto)] aria-pressed:bg-[var(--sb-hover)]">
            {l.nome}
          </button>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[var(--sb-tinta)]" aria-hidden="true" />
    </div>
  );
}
```

`src/app/jogos/Feed.tsx` (client):
```tsx
"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { getMatchesByLeague } from "@/lib/api";
import { ACTIVE_LEAGUES, type Match } from "@/lib/leagues";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { lerFeedUrl, escreverFeedUrl, diaParaApi, type Dia } from "@/lib/feedUrl";
import { useLeagueClassifications } from "@/hooks/useLeagueClassifications";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useLivePolling } from "@/hooks/useLivePolling";
import { fmtHora, fmtDataCurta } from "@/lib/formato";
import { VAZIOS } from "@/lib/copy";
import { DiaTabs } from "@/components/feed/DiaTabs";
import { LigaChips } from "@/components/feed/LigaChips";
import { CardJogo } from "@/components/feed/CardJogo";
import { Detalhe } from "@/components/detalhe/Detalhe";

export function Feed() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const url = useMemo(() => lerFeedUrl(params), [params]);
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const confianca = useLeagueClassifications();
  const ligas = useMemo(() => ACTIVE_LEAGUES().map((l) => ({ id: l.id, nome: l.name })), []);

  const [jogos, setJogos] = useState<JogoView[]>([]);
  const [carimbo, setCarimbo] = useState<string | null>(null);   // hora do ultimo feed bom
  const [erro, setErro] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const ultimoBom = useRef<JogoView[]>([]);

  const carregar = useCallback(async () => {
    const date = diaParaApi(url.dia);
    if (!date) { setJogos([]); setCarregando(false); return; }   // ontem: plano 3
    setCarregando(true);
    try {
      const res = await getMatchesByLeague(ligas.map((l) => l.id).join(","), date);
      if (res._error) throw new Error(res._error.message);
      const agora = new Date();
      const views = deduplicateMatches((res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)))
        .map((m: Match) => toJogoView(m, agora))
        .sort((a, b) => Number(b.estado === "em_jogo") - Number(a.estado === "em_jogo") || a.kickoffIso.localeCompare(b.kickoffIso));
      ultimoBom.current = views; setJogos(views); setCarimbo(fmtHora(agora.toISOString())); setErro(false);
    } catch {
      setErro(true); setJogos(ultimoBom.current);
    } finally { setCarregando(false); }
  }, [url.dia, ligas]);

  useEffect(() => { carregar(); }, [carregar]);
  // Polling pausa com a aba oculta (spec §3): so recarrega se a pagina esta visivel.
  const carregarSeVisivel = useCallback(() => (document.visibilityState === "visible" ? carregar() : Promise.resolve()), [carregar]);
  useLivePolling(carregarSeVisivel, { hasMatches: jogos.length > 0, hasLiveMatches: jogos.some((j) => j.estado === "em_jogo") });

  const ir = (mudanca: Partial<typeof url>, push = false) => {
    const href = escreverFeedUrl({ ...url, ...mudanca });
    push ? router.push(href) : router.replace(href);
  };
  const visiveis = url.liga === "todas" ? jogos : jogos.filter((j) => j.ligaId === url.liga || j.ligaId.endsWith(url.liga));
  const aberto = visiveis.find((j) => j.id === url.jogo) ?? null;

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-3 text-[var(--sb-texto)] lg:grid lg:grid-cols-[minmax(340px,1fr)_minmax(420px,1.2fr)] lg:gap-6">
      <div>
        <DiaTabs dia={url.dia} onChange={(dia) => ir({ dia, jogo: null })} />
        <LigaChips ligas={ligas} ativa={url.liga} onChange={(liga) => ir({ liga, jogo: null })} />
        {erro && (
          <p className="my-2 text-[14px]" role="status">
            {VAZIOS.feedNaoCarregou} <button onClick={carregar} className="sb-foco underline">{VAZIOS.tentarDeNovo}</button>
            {carimbo && <span className="ml-2 text-[var(--sb-texto-apagado)]">{VAZIOS.carimbo(carimbo)}</span>}
          </p>
        )}
        {!carregando && visiveis.length === 0 && !erro && (
          <p className="my-6 text-[14px] text-[var(--sb-texto-apagado)]">
            {VAZIOS.diaSemJogos(fmtDataCurta(new Date().toISOString()))}{" "}
            <button className="sb-foco underline" onClick={() => ir({ dia: url.dia === "hoje" ? "amanha" : "hoje" })}>{VAZIOS.proximoDia(url.dia === "hoje" ? "amanhã" : "hoje")}</button>
          </p>
        )}
        <div className="space-y-3 py-3">
          {visiveis.map((j) => (
            <div key={j.id} data-liga={j.ligaId}>
              <CardJogo jogo={j} confianca={confianca.get(j.ligaId)} selecionado={j.id === url.jogo}
                hrefDetalhe={`/jogos/${encodeURIComponent(j.id)}`}
                onAbrir={isMobile ? undefined : (id) => ir({ jogo: id }, true)} />
            </div>
          ))}
        </div>
      </div>
      {!isMobile && aberto && (
        <aside aria-label="detalhe do jogo" className="sticky top-4 self-start">
          <Detalhe jogo={aberto} confianca={confianca.get(aberto.ligaId)} />
        </aside>
      )}
    </div>
  );
}
```
No celular `onAbrir` é `undefined` e o `<Link>` do título navega para `/jogos/[id]`; no desktop `?jogo=` entra com `push`, então voltar fecha o painel.

`src/app/jogos/page.tsx`:
```tsx
import { Suspense } from "react";
import { Feed } from "./Feed";
export const metadata = { title: "Jogos — SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-screen bg-[var(--sb-tinta)]"><Suspense><Feed /></Suspense></main>;
}
```

- [ ] **Step 5: Rodar** — `npx tsc --noEmit`; `npx playwright test e2e/jogos.spec.ts` (chromium e mobile). O teste do painel depende do `Detalhe` da Task 16: até lá, criar `src/components/detalhe/Detalhe.tsx` com um placeholder **que a Task 16 substitui**: `export function Detalhe({ jogo }: { jogo: JogoView; confianca: unknown }) { return <p>{jogo.casa} × {jogo.fora}</p>; }`.
- [ ] **Step 6: Commit** — `git add frontend/next/src/app/jogos frontend/next/src/components frontend/next/e2e/jogos.spec.ts frontend/next/e2e/fixtures && git commit -m "feat(front): /jogos com feed, tabs, chips e estado na URL (#254-b)"`

---

### Task 16: Detalhe — escala, tabela, "de onde vem", texto

**Files:**
- Create: `frontend/next/src/components/detalhe/Detalhe.tsx` (substitui o placeholder), `EscalaConfianca.tsx`, `TabelaMercados.tsx`, `DeOndeVemONumero.tsx`, `ComoOModeloVe.tsx`, `frontend/next/src/app/jogos/[id]/page.tsx`, `frontend/next/tests/unit/detalhe.test.tsx`
- Modify: `frontend/next/src/lib/jogoView.ts` (acrescentar `origem` ao `JogoView`)

**Interfaces:**
- Consumes: `getAiMatchAnalysis(matchId)` (`lib/api.ts`), `fmtOdd`, `fmtPct`, `COPIAR`, `motivoRecusa` via `PickView.motivo`.
- Produces: `JogoView.origem: Origem` (type exportado de `lib/copy.ts`; `copy` não importa `jogoView`, sem ciclo) preenchido em `toJogoView` a partir de `stats.homeAvgTotalGoals`, `awayAvgTotalGoals`, `avgGoals`, `homeCornersPerMatch`, `awayCornersPerMatch`, `leagueAvgCorners` (`null` quando o campo é `0`/ausente — o `normalizeMatch` grava `0` para ausente, e `0` não é média válida); `fraseOrigem(o, casa, fora, liga): string | null` em `lib/copy.ts`.

- [ ] **Step 1: Teste**

`tests/unit/detalhe.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { fraseOrigem } from "@/lib/copy";
import type { PickView } from "@/lib/jogoView";

const p = (o: Partial<PickView>): PickView => ({ mercado: "x", prob01: 0.5, fairOdd: 2, bookOdd: 2.1, edge: 0.05, ev: 0.05, classification: "SAFE", motivo: "", vale: true, ...o });

describe("detalhe (spec §4.3)", () => {
  it("escala: aria-label com a frase inteira; marca e zona", () => {
    render(<EscalaConfianca prob01={0.58} margem={[0.52, 0.64]} nJogos={40} liga="MLS" />);
    const fig = screen.getByRole("img");
    expect(fig).toHaveAttribute("aria-label", "58 em cada 100, com margem de 52 a 64, em 40 jogos medidos da MLS");
    expect(screen.getByText("50")).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("tabela: cabecalhos, status em texto, copiar so em quem vale, recusados apagados", () => {
    render(<TabelaMercados mercados={[
      p({ mercado: "Mais de 6,5 escanteios", prob01: 0.58, fairOdd: 1.67, bookOdd: 1.75 }),
      p({ mercado: "Mais de 2,5 gols", prob01: 0.57, fairOdd: 1.75, bookOdd: 1.62, classification: "NEUTRO", vale: false, motivo: "sem valor" }),
      p({ mercado: "Ambos marcam", prob01: 0.51, fairOdd: 1.96, bookOdd: null, classification: "NO_BET", vale: false, motivo: "sem preço" }),
    ]} />);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["mercado", "chance", "mínima", "paga", "status", ""]);
    expect(screen.getByText("vale")).toBeInTheDocument();
    expect(screen.getByText("↓ abaixo do mínimo")).toHaveClass("text-[var(--sb-contra-texto)]");
    expect(screen.getByText("sem preço")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /copiar odd/ })).toHaveLength(1);
    expect(screen.getByText("Ambos marcam").closest("tr")).toHaveClass("text-[var(--sb-texto-apagado)]");
  });
  it("de onde vem o numero: frase com unidade; campo ausente some", () => {
    expect(fraseOrigem({ golsCasa: 3, golsFora: 2.5, golsLiga: 4.9, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "Toronto", "Nashville", "MLS"))
      .toBe("Toronto faz 3,0 gols por jogo em casa; Nashville sofre 2,5 fora; a MLS tem 4,9 por jogo.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: 5.1, escanteiosFora: 4.6, escanteiosLiga: 9.8 }, "Toronto", "Nashville", "MLS"))
      .toBe("Toronto força 5,1 escanteios por jogo em casa; Nashville 4,6 fora; a MLS tem 9,8 por jogo.");
    expect(fraseOrigem({ golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null }, "a", "b", "c")).toBeNull();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

Em `lib/jogoView.ts`, `import { type Origem } from "@/lib/copy"`, acrescentar `origem: Origem` ao `JogoView` e, em `toJogoView`:
```ts
const n = (v: unknown) => (typeof v === "number" && v > 0 ? v : null);
origem: { golsCasa: n(m.stats.homeAvgTotalGoals), golsFora: n(m.stats.awayAvgTotalGoals), golsLiga: n(m.stats.avgGoals),
          escanteiosCasa: n(m.stats.homeCornersPerMatch), escanteiosFora: n(m.stats.awayCornersPerMatch), escanteiosLiga: n(m.stats.leagueAvgCorners) },
```
(atualizar o `base` dos testes de `jogoView` e `CardJogo` com `origem` nulo).

Em `lib/copy.ts`:
```ts
const umaCasa = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export interface Origem { golsCasa: number | null; golsFora: number | null; golsLiga: number | null; escanteiosCasa: number | null; escanteiosFora: number | null; escanteiosLiga: number | null }
export function fraseOrigem(o: Origem, casa: string, fora: string, liga: string): string | null {
  if (o.golsCasa != null && o.golsFora != null && o.golsLiga != null)
    return `${casa} faz ${umaCasa.format(o.golsCasa)} gols por jogo em casa; ${fora} sofre ${umaCasa.format(o.golsFora)} fora; a ${liga} tem ${umaCasa.format(o.golsLiga)} por jogo.`;
  if (o.escanteiosCasa != null && o.escanteiosFora != null && o.escanteiosLiga != null)
    return `${casa} força ${umaCasa.format(o.escanteiosCasa)} escanteios por jogo em casa; ${fora} ${umaCasa.format(o.escanteiosFora)} fora; a ${liga} tem ${umaCasa.format(o.escanteiosLiga)} por jogo.`;
  return null;
}
```
Verificação de contrato (Etapa 2): `homeAvgTotalGoals` — confirmar em `backend/services/fixtures_service.py` se é "gols marcados em casa" ou "total de gols nos jogos em casa". Se for total, a frase muda para "os jogos do Toronto em casa têm 3,0 gols". **Não publicar a frase sem essa leitura**; anotar o resultado no REGISTRO.

`src/components/detalhe/EscalaConfianca.tsx`:
```tsx
import { fmtPct } from "@/lib/formato";
export function EscalaConfianca({ prob01, margem, nJogos, liga }: { prob01: number; margem: [number, number] | null; nJogos: number | null; liga: string }) {
  const p = fmtPct(prob01);
  const frase = margem && nJogos != null
    ? `${p} em cada 100, com margem de ${fmtPct(margem[0])} a ${fmtPct(margem[1])}, em ${nJogos} jogos medidos da ${liga}`
    : `${p} em cada 100 na ${liga}`;
  return (
    <figure>
      <div role="img" aria-label={frase} className="relative my-3 h-8">
        <div className="absolute inset-x-0 top-[14px] h-[2px] bg-[var(--sb-linha)]" />
        {[0, 25, 50, 75, 100].map((t) => <div key={t} className="absolute top-[9px] h-3 w-px bg-[var(--sb-linha)]" style={{ left: `${t}%` }} />)}
        {margem && <div className="absolute top-3 h-[6px] rounded-[3px] bg-[var(--sb-confianca)]" style={{ left: `${margem[0] * 100}%`, width: `${(margem[1] - margem[0]) * 100}%` }} />}
        <div className="absolute top-1 h-[22px] w-[2px] bg-[var(--sb-texto)]" style={{ left: `${prob01 * 100}%` }} />
      </div>
      <div className="tnum flex justify-between text-[13px] text-[var(--sb-texto-apagado)]" aria-hidden="true"><span>0</span><span>50</span><span>100</span></div>
      <figcaption className="mt-1 text-[14px]">{frase}</figcaption>
    </figure>
  );
}
```
Margem: `Match` não traz intervalo hoje; `Detalhe` passa `margem={null}` e `nJogos={confianca?.nSamples ?? null}` até o plano 3 trazer os buckets do ledger. A escala sem zona é honesta: mostra o ponto e diz "na MLS".

`src/components/detalhe/TabelaMercados.tsx`:
```tsx
import type { PickView } from "@/lib/jogoView";
import { fmtOdd, fmtPct } from "@/lib/formato";
import { BotaoCopiar } from "@/components/feed/BotaoCopiar";

function status(p: PickView) {
  if (p.vale) return { texto: "vale", classe: "" };
  if (p.bookOdd == null) return { texto: "sem preço", classe: "" };
  if (p.bookOdd < p.fairOdd) return { texto: "↓ abaixo do mínimo", classe: "text-[var(--sb-contra-texto)]" };
  return { texto: p.motivo || "não vale", classe: "" };
}

export function TabelaMercados({ mercados }: { mercados: PickView[] }) {
  return (
    <table id="mercados" className="w-full text-[14px]">
      <thead><tr className="text-left text-[13px] text-[var(--sb-texto-apagado)]">
        <th scope="col" className="py-1 font-normal">mercado</th><th scope="col" className="py-1 text-right font-normal">chance</th>
        <th scope="col" className="py-1 text-right font-normal">mínima</th><th scope="col" className="py-1 text-right font-normal">paga</th>
        <th scope="col" className="py-1 font-normal">status</th><th scope="col" className="py-1 font-normal"></th>
      </tr></thead>
      <tbody>
        {mercados.map((p) => { const s = status(p); return (
          <tr key={p.mercado} className={`border-t border-[var(--sb-linha)] ${p.vale ? "" : "text-[var(--sb-texto-apagado)]"}`}>
            <td className="py-2">{p.mercado}</td>
            <td className="tnum py-2 text-right">{fmtPct(p.prob01)}%</td>
            <td className="tnum py-2 text-right">{fmtOdd(p.fairOdd)}</td>
            <td className="tnum py-2 text-right">{p.bookOdd != null ? fmtOdd(p.bookOdd) : "—"}</td>
            <td className={`py-2 ${s.classe}`}>{s.texto}</td>
            <td className="py-2">{p.vale && p.bookOdd != null && <BotaoCopiar odd={p.bookOdd} sobre="painel" />}</td>
          </tr>); })}
      </tbody>
    </table>
  );
}
```
`BotaoCopiar` dentro da tabela fica sobre `painel`: passar `sobre="painel"` (prop da Task 12).

`src/components/detalhe/ComoOModeloVe.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import { getAiMatchAnalysis } from "@/lib/api";
/** Texto narrativo (contrato Mistral #082). Indisponivel → a secao SOME inteira (spec §5). */
export function ComoOModeloVe({ matchId }: { matchId: string }) {
  const [texto, setTexto] = useState<{ summary: string; key_points: string[] } | null>(null);
  useEffect(() => {
    let vivo = true;
    getAiMatchAnalysis(matchId).then((r) => { if (vivo && r && r.confidence > 0) setTexto({ summary: r.summary, key_points: r.key_points ?? [] }); }).catch(() => {});
    return () => { vivo = false; };
  }, [matchId]);
  if (!texto) return null;
  return (
    <section className="mt-6">
      <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Como o modelo vê o jogo</h3>
      <p className="mt-2 max-w-[70ch] text-[14px]">{texto.summary}</p>
      {texto.key_points.length > 0 && <ul className="mt-2 list-disc pl-5 text-[14px]">{texto.key_points.map((k) => <li key={k}>{k}</li>)}</ul>}
    </section>
  );
}
```
Conferir a assinatura real de `getAiMatchAnalysis` em `lib/api.ts:240-260` (parâmetros e forma do retorno) antes de usar; ajustar os nomes ao que existe.

`src/components/detalhe/DeOndeVemONumero.tsx`:
```tsx
import Link from "next/link";
import type { JogoView } from "@/lib/jogoView";
import { fraseOrigem } from "@/lib/copy";
export function DeOndeVemONumero({ jogo, nJogos }: { jogo: JogoView; nJogos: number | null }) {
  const frase = fraseOrigem(jogo.origem, jogo.casa, jogo.fora, jogo.ligaNome);
  if (!frase && nJogos == null) return null;
  return (
    <section className="mt-6 text-[14px]">
      <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">De onde vem o número</h3>
      {frase && <p className="mt-2 max-w-[70ch]">{frase}</p>}
      {nJogos != null && <p className="mt-1 text-[var(--sb-texto-apagado)]">{nJogos} jogos medidos — <Link href="/desempenho" className="sb-foco underline">ver calibração</Link></p>}
    </section>
  );
}
```

`src/components/detalhe/Detalhe.tsx`:
```tsx
import type { JogoView } from "@/lib/jogoView";
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { Talao } from "@/components/feed/Talao";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { ComoOModeloVe } from "@/components/detalhe/ComoOModeloVe";
import { DeOndeVemONumero } from "@/components/detalhe/DeOndeVemONumero";
import { fmtDataCurta, fmtHora } from "@/lib/formato";

export function Detalhe({ jogo, confianca }: { jogo: JogoView; confianca: LeagueConfidence | null }) {
  return (
    <div className="rounded-[var(--sb-raio-painel)] border border-[var(--sb-linha)] bg-[var(--sb-painel)] p-4">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="font-[family-name:var(--font-slab)] text-[22px] font-semibold">{jogo.casa} × {jogo.fora}</h2>
        <span className="tnum text-[13px] text-[var(--sb-texto-apagado)]">{jogo.ligaNome}, {fmtDataCurta(jogo.kickoffIso)}, {fmtHora(jogo.kickoffIso)}</span>
      </header>
      {jogo.talao && <Talao pick={jogo.talao} futuro={jogo.estado === "amanha_sem_preco"} preJogo={jogo.estado === "em_jogo"} />}
      {jogo.talao && (
        <section className="mt-4">
          <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Confiança nesta liga</h3>
          <EscalaConfianca prob01={jogo.talao.prob01} margem={null} nJogos={confianca?.nSamples ?? null} liga={jogo.ligaNome} />
        </section>
      )}
      <section className="mt-6">
        <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Todos os mercados avaliados ({jogo.totalAvaliados})</h3>
        <div className="overflow-x-auto"><TabelaMercados mercados={jogo.mercados} /></div>
      </section>
      <ComoOModeloVe matchId={jogo.id} />
      <DeOndeVemONumero jogo={jogo} nJogos={confianca?.nSamples ?? null} />
    </div>
  );
}
```

`src/app/jogos/[id]/page.tsx` (client via componente `DetalhePagina`): carrega o feed do dia atual (`getMatchesByLeague` com `today`, depois `tomorrow`) e procura o `id`; achou → `<Detalhe>`; não achou → `VAZIOS.jogoNaoEncontrado` + link `/jogos` com `VAZIOS.verFeedDeHoje`. Sem cache próprio: é a mesma chamada do feed, e o Next reaproveita a resposta no `fetch` do servidor quando existir.

- [ ] **Step 3: E2E** — acrescentar a `e2e/jogos.spec.ts`:
```ts
test("/jogos/[id] inexistente: 'jogo não encontrado' + link", async ({ page }) => {
  await stub(page);
  await page.goto("/jogos/nao-existe");
  await expect(page.getByText("jogo não encontrado")).toBeVisible();
  await expect(page.getByRole("link", { name: "ver os jogos de hoje" })).toHaveAttribute("href", "/jogos");
});
test("Mistral indisponivel: a secao some inteira", async ({ page }) => {
  await stub(page);
  await page.route("**/api/ai/match/**", (route) => route.fulfill({ status: 503, body: "{}" }));
  const id = encodeURIComponent(feed.matches[0].id);
  await page.goto(`/jogos/${id}`);
  await expect(page.getByRole("heading", { name: /Todos os mercados avaliados/ })).toBeVisible();
  await expect(page.getByText("Como o modelo vê o jogo")).toHaveCount(0);
});
```
- [ ] **Step 4: Rodar** — `npx vitest run && npx tsc --noEmit && npx playwright test e2e/jogos.spec.ts`.
- [ ] **Step 5: Commit** — `git add -A frontend/next/src frontend/next/tests frontend/next/e2e && git commit -m "feat(front): detalhe com escala, tabela, origem e texto (#254-b)"`

---

### Task 17: `/banca`

**Files:**
- Create: `frontend/next/src/app/banca/page.tsx`, `frontend/next/src/app/banca/FormBanca.tsx`, `frontend/next/e2e/banca.spec.ts`

**Interfaces:**
- Consumes: `useBanca` (Task 5), `fmtReais`, `calcStake`.

- [ ] **Step 1: E2E (falha: rota não existe)**

`e2e/banca.spec.ts`:
```ts
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
```

- [ ] **Step 2: Implementar**

`src/app/banca/FormBanca.tsx`:
```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useBanca, calcStake } from "@/lib/bancaStore";
import { fmtReais } from "@/lib/formato";

export function FormBanca() {
  const [banca, setBanca] = useBanca();
  const [valor, setValor] = useState("");
  const [msg, setMsg] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(null);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  useEffect(() => { if (banca != null && valor === "") setValor(String(banca).replace(".", ",")); }, [banca, valor]);

  function salvar(e: React.FormEvent) {
    e.preventDefault();
    const n = parseFloat(valor.replace(/\./g, "").replace(",", "."));
    if (setBanca(n) === "invalida") { setMsg({ tipo: "erro", texto: "banca precisa ser um valor em reais" }); return; }
    setMsg({ tipo: "ok", texto: "banca salva" });
  }
  // consequencia: o maior stake que um pick SAFE sugeriria hoje (prob 0,60, odd 1,90 → cap de 5%)
  const teto = banca != null ? calcStake(0.6, 1.9, banca, "SAFE") : null;
  return (
    <form onSubmit={salvar} className="max-w-[70ch] space-y-3 text-[var(--sb-texto)]">
      <label className="block text-[16px]" htmlFor="banca">Sua banca</label>
      <input id="banca" ref={ref} inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)}
        className="sb-foco tnum w-full rounded-[var(--sb-raio-painel)] border border-[var(--sb-linha)] bg-[var(--sb-painel)] px-3 py-2 text-[22px]" placeholder="R$ 0,00" />
      <div className="flex items-center gap-3">
        <button type="submit" className="sb-foco rounded-[var(--sb-raio-painel)] border border-[var(--sb-texto)] px-4 py-2 text-[14px]">Salvar banca</button>
        <span className={`min-h-[20px] text-[14px] ${msg?.tipo === "erro" ? "text-[var(--sb-contra-texto)]" : ""}`} aria-live="polite">{msg?.texto ?? ""}</span>
      </div>
      {banca == null
        ? <p className="text-[14px] text-[var(--sb-texto-apagado)]">Defina a banca para ver quanto apostar em cada jogo.</p>
        : <p className="text-[14px]">Cada pick sugere uma fração dela, hoje até {fmtReais(teto ?? 0)} por jogo.</p>}
      <p className="text-[13px]"><Link href="/glossario#stake" className="sb-foco underline">Como a fração é calculada</Link></p>
    </form>
  );
}
```
`src/app/banca/page.tsx`: `<main className="min-h-screen bg-[var(--sb-tinta)] px-4 py-6"><FormBanca /></main>`.

- [ ] **Step 3: Rodar** — `npx playwright test e2e/banca.spec.ts`; `npm run lint:accents`.
- [ ] **Step 4: Commit** — `git add frontend/next/src/app/banca frontend/next/e2e/banca.spec.ts && git commit -m "feat(front): /banca com estado indefinido (#254-b)"`

---

### Task 18: Regressão visual e axe

**Files:**
- Create: `frontend/next/e2e/visual.spec.ts`, `frontend/next/e2e/a11y.spec.ts`
- Modify: `frontend/next/playwright.config.ts` (projetos `visual-mobile` 390×844 e `visual-desktop` 1440×900, `reducedMotion: "reduce"`, `toHaveScreenshot: { maxDiffPixelRatio: 0.001 }`), `frontend/next/package.json` (`@axe-core/playwright`)

- [ ] **Step 1:** `npm i -D @axe-core/playwright`.
- [ ] **Step 2:** `playwright.config.ts` — acrescentar aos `projects`:
```ts
{ name: "visual-mobile", testMatch: /visual\.spec\.ts/, use: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, reducedMotion: "reduce" } },
{ name: "visual-desktop", testMatch: /visual\.spec\.ts/, use: { viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" } },
```
e, no topo do `defineConfig`: `expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: "disabled" } }`. Os projetos `chromium`/`mobile` ganham `testIgnore: /visual\.spec\.ts/`.
- [ ] **Step 3:** `e2e/visual.spec.ts` — usa o `stub` de `jogos.spec.ts` (extrair para `e2e/helpers/stub.ts`), abre `/jogos`, `/jogos?jogo=<id do vale>` (desktop), `/jogos/<id>`, `/banca` (indefinida e definida via `addInitScript`), e chama `await expect(page).toHaveScreenshot(\`${nome}.png\`, { fullPage: true })` para cada. Primeira execução grava as referências (`--update-snapshots`); **dono do approve de diff: Welligton** — o CI falha em diferença > 0,1% e a atualização das referências é um commit separado, revisado.
- [ ] **Step 4:** `e2e/a11y.spec.ts`:
```ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { stub } from "./helpers/stub";
for (const rota of ["/jogos", "/banca"]) {
  test(`axe sem violacoes serias em ${rota}`, async ({ page }) => {
    await stub(page);
    await page.goto(rota);
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(r.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""))).toEqual([]);
  });
}
```
- [ ] **Step 5:** Rodar `npx playwright test`; commit `test(front): regressao visual e axe (#254-b)`.

---

### Task 19: Fechar a fase 3

- [ ] **Step 1:** Suíte completa verde: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test`.
- [ ] **Step 2:** Teste da largura de números (spec §7) — em `e2e/jogos.spec.ts`:
```ts
test("numeros alinham pela virgula: 1,67 e 1,75 tem a mesma largura", async ({ page }) => {
  await stub(page); await page.goto("/jogos");
  const w = await page.evaluate(() => {
    const s = (t: string) => { const el = document.createElement("span"); el.className = "tnum"; el.style.font = getComputedStyle(document.body).font; el.textContent = t; document.body.append(el); const r = el.getBoundingClientRect().width; el.remove(); return r; };
    return [s("1,67"), s("1,75")];
  });
  expect(Math.abs(w[0] - w[1])).toBeLessThan(0.5);
});
```
- [ ] **Step 3:** Rodada 1 do teste de 5 segundos (spec §7): gerar as duas telas estáticas a partir do produto (`/jogos` com o card "vale" e `/jogos/[id]` com a tabela), 4–6 pessoas por perfil, registrar acerto/tempo/confiança; **critério: acerto ≥ 80% por perfil e mediana ≤ 5 s no talão**. Se falhar, voltar à spec §4 antes de seguir para o plano 3.
- [ ] **Step 4:** Entrada `## 254-b — Reformulação do frontend, fase 3: /jogos, talão, detalhe e banca` no REGISTRO com: prova empírica (E2E por estado, screenshots de referência, axe), contratos de saída (nenhum campo de backend escrito; leitores novos de `/api/matches/fetch`, `/api/ml/status`, `/api/ai/match/*`), o resultado da leitura de `homeAvgTotalGoals` (Task 16), o placar da rodada 1 do teste de 5 s, e o que ficou para o plano 3: `?dia=ontem` (precisa de `/ledger/dia`), o segmented control Dia | Rodada (`date=week` já existe no backend; entra junto com "ontem" para os três dias nascerem coerentes), a margem da escala e `MEDIA_DAS_LIGAS` vindos de `/ledger/agregado`. Linha no INDICE. `CLAUDE.md`: acrescentar em "Comandos" `npm run test:unit`, `npm run lint:fonts`.
- [ ] **Step 5:** Espelhar, commit, push, CI verde. O dashboard antigo continua sendo a rota padrão até a fase 6.
