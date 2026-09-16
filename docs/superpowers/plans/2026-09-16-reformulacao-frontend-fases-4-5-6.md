# Reformulação do frontend — plano 3 (fases 4, 5 e 6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar a reformulação do frontend: trazer "ontem" (com desfecho) para o feed e criar `/desempenho` a partir do ledger (fase 4); hero com redirect por cookie, `/glossario`, navegação final e links contextuais (fase 5); rodada 2 do teste de 5 segundos, `/jogos` como padrão e remoção das rotas antigas com backup (fase 6).

**Architecture:** Fase 4 lê exclusivamente `/ledger/dia` e `/ledger/agregado` (fase 1, já implantados) — nunca `/fixtures` recomputado — para honrar a "fonte única" da spec §6.3: o que o usuário vê é o que foi **publicado**, não um prognóstico refeito hoje. Um mapeador puro novo, `lib/jogoViewOntem.ts`, converte os picks do ledger (que não têm nome de time nem rótulo bonito de mercado) em `JogoView`/`PickView` — os MESMOS tipos que `lib/jogoView.ts` já produz para hoje/amanhã — para que `CardJogo`, `Talao` e `Detalhe` (fase 3) sirvam "ontem" sem nenhuma mudança. Fase 5 adiciona a porta de entrada (hero) e o cookie de retorno em `middleware.ts`, que hoje redireciona `/` para `/dashboard` incondicionalmente. Fase 6 é operação de corte: tag/branch de backup, a rodada 2 do teste de 5 s (conduzida pelo dono, este plano só prepara o material), e a remoção das rotas legadas com prova de que o corte não deixa link morto sem tratamento.

**Tech Stack:** Next.js 15 (App Router), React 18, Tailwind 3, Vitest + Testing Library, Playwright (E2E, regressão visual, axe). Nenhuma mudança em `backend/` além de uma leitura adicional dentro de `ledger_leitura.py` já existente (nenhum novo endpoint).

**Spec:** `docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md` — sobretudo §3 (IA/rotas), §4 (talão e estados), §5 (telas restantes), §6 (componentes e contratos), §7 (validação), §8 (ordem de build), §9 (fora do escopo). Planos irmãos: `docs/superpowers/plans/2026-09-15-reformulacao-frontend-fases-0-2-3.md` (fases 0/2/3 — este plano consome `Talao`, `BotaoCopiar`, `CardJogo`, `Detalhe`, `EscalaConfianca`, `TabelaMercados`, `DiaTabs`, `LigaChips`, `Feed`, `feedUrl.ts`, `jogoView.ts`, `bancaStore.ts`, `copy.ts`, `formato.ts`, `tokens.ts` pelos nomes e caminhos que esse plano define, sem redefini-los) e `docs/superpowers/plans/2026-09-15-reformulacao-frontend-fase-1-backend.md` (fase 1 — `GET /ledger/dia`, `GET /ledger/agregado`, proxies `/api/ledger/dia`, `/api/ledger/agregado`, já implantados: commits `4eaff30`…`427a6be` em `main`).

## Estado real do código nesta data (2026-09-16, verificado antes de escrever este plano)

- Fase 0, fase 1 e fase 2: **prontas e mergeadas** (`backend/services/ledger_leitura.py`, `backend/routes/ledger.py`, `frontend/next/src/app/api/ledger/{dia,agregado}/route.ts`, `frontend/next/src/lib/jogoView.ts`, `normalizeMatch.ts`, `copy.ts`, `formato.ts`, `tokens.ts`, `bancaStore.ts`, `reasonCodes.ts` existem no branch).
- Fase 3 (Tasks 12–19 do plano 1) está **em andamento em paralelo** a este plano: só `tests/unit/Talao.test.tsx` existe hoje (untracked). `CardJogo`, `Talao`, `Feed.tsx`, `Detalhe.tsx`, `EscalaConfianca.tsx`, `TabelaMercados.tsx`, `feedUrl.ts`, `/jogos`, `/jogos/[id]`, `/banca` **ainda não existem no disco** no momento em que este plano foi escrito. As Tasks 20+ abaixo pressupõem que a fase 3 fechou (Global Constraint da fase 4) e usam os nomes/assinaturas exatos definidos no plano 1 (citados com número de linha onde ajuda).
- `src/lib/jogoView.ts` hoje: `toJogoView` **nunca** produz o estado `"ontem"` — só `"ontem_sem_desfecho"` para `status === "finished"` ou `kickoff < agora − 3h` (`jogoView.ts:64`), e `resultado` é sempre `null` (`jogoView.ts:76`). `CardJogo` (definido no plano 1, Task 14) já sabe renderizar `"ontem"` e `"ontem_sem_desfecho"` lendo `jogo.resultado` — a Task 21 deste plano é o que falta para o switch ser alcançado.
- `src/middleware.ts` hoje: redireciona **todo** acesso a `/` para `/dashboard`, sem condição (`middleware.ts:9-11`). `src/app/page.tsx` hoje: `redirect("/dashboard")` — nunca executa porque o middleware intercepta antes.
- Rotas legadas confirmadas (para a Task 37, fase 6): `src/app/dashboard/page.tsx` (2.499 linhas), `src/app/duplas/page.tsx` (11 linhas, importa `Dashboard` com `initialView="duplas"`), `src/app/destaques/page.tsx` (idem, `"recomendadas"`), `src/app/campeonatos/page.tsx` (idem, `"campeonatos"`), `src/app/glossario/page.tsx` (idem, `"glossario"` — **este caminho é reaproveitado pela Task 30 da fase 5**, não apagado, seu conteúdo é substituído), `src/app/bankroll/page.tsx` (`BankrollCalculator`), `src/app/match/[id]/page.tsx`, `src/app/performance-stats/page.tsx` (323 linhas), `src/app/ai-audit/page.tsx`, `src/app/admin/reliability/page.tsx` (232 linhas). Ficam como arquivo sem link (não apagar): `login`, `register`, `admin-activate`, `admin-deactivate`, `debug-live`, `ferramentas` — exatamente a lista da spec §3.

## Decisões de projeto tomadas para fechar lacunas que a spec deixa em aberto

1. **Fonte de "ontem" é só o ledger, nunca `/fixtures` recomputado.** Chamar `/fixtures?date=<ontem>` para "ontem" repetiria o erro que a spec critica em `audit_results` (§6.3, §0): o pipeline rodaria de novo com o modelo de HOJE sobre um jogo de ontem, produzindo números diferentes dos que foram publicados. `/ledger/dia` já é o registro imutável do que foi publicado — é a única fonte usada.
2. **Nomes de time não vêm do ledger** (o payload de `/ledger/dia`, spec §6.3, não tem `casa`/`fora` — confirmado lendo `backend/services/ledger_leitura.py::_pick_json`, que só serializa `match_id, league_id, kickoff_utc, familia, market, selection, published_prob, fair_odd, book_odd, classification, outcome, detail`). `match_id` segue o formato `{league_id}-{casa}-{fora}-{epoch}` (confirmado em `backend/services/prediction_ledger.py:236`, comentário de `kickoff_da_linha`, e nos IDs reais do payload de produção citados na tarefa: `"liga-mx-Guadalajara-Pumas UNAM-1789348020.0"`). A Task 21 extrai `casa`/`fora` removendo o prefixo `league_id-` (que já vem separado no próprio pick, sem ambiguidade) e o sufixo epoch (mesma regra de `kickoff_da_linha`); nenhum nome de time observado nos exemplos reais contém hífen interno. Fallback documentado e testado para o caso raro de um time com hífen: ver Task 21.
3. **Rótulo de mercado no ledger é bruto, não o "Mais de X" da spec.** `prediction_ledger` grava `market`/`selection` (`backend/services/prediction_ledger.py:710-711`, `montar_linha(... market=m.market_type, selection=m.selection ...)`), não o `display_label` bonito que `MarketOutput.to_legacy_mercado()` monta em `backend/models/market_output.py:164`. A Task 21 replica os mesmos seis padrões de formatação que `display_label` usa em `backend/services/ev_classification.py` (linhas 1005, 1056/1097, 1120, 1335/1413, 1488/1514 — 1X2, Over/Under, BTTS, Corners, Cards), com fallback ao texto bruto para o que não reconhecer. **Isto é uma aproximação, não uma cópia exata do texto publicado** (o texto exato não foi gravado em lugar nenhum); a Task 21 inclui um passo de verificação empírica contra linhas reais do ledger antes de fechar a tarefa.
4. **Margem da escala de confiança fica `null`.** A spec (§4.3) mostra "margem de 52 a 64" no detalhe, mas nenhum código no repositório calcula um intervalo de confiança por pick (nem Wilson, nem Wald) — inventar essa conta aqui seria uma mudança de cálculo estatístico não auditada, e a spec §9 exclui mudança de cálculo do pipeline deste projeto. A Task 24 wire **só** `nJogos` (de `/ledger/agregado`, que é dado real) e mantém `margem={null}`; a escala já trata esse caso (spec §4.3 Detalhe, `EscalaConfianca.tsx` do plano 1 mostra o ponto sem zona quando `margem` é nulo). Está registrado abaixo como pergunta em aberto para o dono.
5. **Segmented control "Dia | Rodada" (spec §3) não entra neste plano.** A tabela de dependências da spec (§8) lista fase 4 como "Ontem no feed, `/desempenho`" e fase 5/6 sem mencionar o controle Dia|Rodada; a única referência a ele é uma nota de fechamento da fase 3 ("o que ficou para o plano 3"), sem comportamento de "Rodada" definido em lugar nenhum da spec (o que ela mostra é a lista de dias — Ontem/Hoje/Amanhã — já construída na fase 3 como `DiaTabs`). Implementar um modo "Rodada" sem especificação seria inventar comportamento não pedido (SDD Etapa 3). Fica como pergunta em aberto para o dono, não como tarefa.
6. **Cookie do redirect (fase 5):** nome `sbz_visitou`, valor `"1"`, `Max-Age=15552000` (180 dias), `Path=/`, sem `httpOnly` (não é dado sensível, é uma preferência de UI), `SameSite=Lax`. Barato e reversível: apagar o cookie no navegador volta ao comportamento de primeira visita.

---

## Global Constraints

- Tokens, fontes, cor e glifo de estado — as mesmas regras do plano 1 (spec §2): `confianca` nunca dentro do talão; `✓`/`×`/`↓` são os únicos glifos de estado; Zilla Slab só em veredito/times/títulos, Source Sans 3 em corpo e **toda coluna de números** (`tnum`), Barlow Condensed só em `components/marca/` e `app/page.tsx` — travado por `npm run lint:fonts`.
- Copy pt-BR acentuada, sempre via `lib/copy.ts` (novas funções entram lá, não como string solta em componente) — travado por `npm run lint:accents`.
- Estado na URL: `/jogos` já usa `?dia=&liga=&jogo=` (plano 1); `/desempenho` usa `?periodo=&familia=&liga=` (Task 25 define `lib/desempenhoUrl.ts`, mesmo padrão de `lib/feedUrl.ts`).
- `Array.from(set)` em vez de spread de `Set` — o `tsconfig` não tem `target` (regra herdada da fase 2, `f212773`).
- **Fonte única do que o usuário vê é o ledger** (spec §6.3): nenhuma tela nova recomputa probabilidade; "ontem" e "/desempenho" só leem `/ledger/dia` e `/ledger/agregado`.
- **`retorno` em `/ledger/agregado` é sempre `{valor: null, pct_banca: null, motivo: "stake_nao_gravado_no_ledger"}`** (confirmado em `backend/services/ledger_leitura.py:301-307` — `stake` nunca foi gravado no ledger, produtor não muda neste plano). `/desempenho` mostra essa ausência de forma honesta (Task 25), nunca inventa um número.
- `MIN_N_BRIER = 20` (proibição 8): `brier`/`buckets` vêm `null` do backend abaixo do piso — a tela escreve "amostra curta", nunca calcula por conta própria.
- Nenhuma mudança em `backend/modeling/` nem em classificação/threshold/deflação (proibições 1-13). O único código Python tocado por este plano é leitura já existente.
- Proibido `.get(k, alternativa)` no caminho de decisão (proibição 15) em qualquer trecho Python tocado.
- Cada fase fecha com: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test` verdes, entrada em `docs/REGISTRO_CORRECOES.md` (fase 4 = **#256**, fase 5 = **#257**, fase 6 = **#258**) + linha em `docs/INDICE_REGRAS.md`, espelho dos 4 arquivos de regra para `c:\painel_apostas\sportsbank-pro\`, commit e push em `main`. Todo teste novo cita o número da fase (`#256`/`#257`/`#258`).
- Commits terminam com `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Armadilha de ferramenta (declarar antes de implementar):** a ferramenta `Write` decodifica escapes `\uXXXX` em glifos reais ao gravar código-fonte. Qualquer string com `\u2713` (✓), `\u00d7` (×), `\u2193` (↓), `\u2014` (—) ou similar deve ser escrita como o **glifo literal** no arquivo (copiar o caractere, não a sequência de escape) — se um passo desta tarefa colar uma sequência `\uXXXX`, o implementador confere com `xxd`/`hexdump` que o byte gravado é o do glifo (ex.: `✓` = `E2 9C 93` em UTF-8), não a string `\`, `u`, `2`, `7`... literal.
- Nenhuma tarefa desta fase altera `backend/modeling/calibragem/` ou o ciclo de escrita do #248 — proibição 16 continua intacta; `CALIBRAGEM_ENABLED` continua `false`.
- **Toda tarefa que toca UI traz o diff visual no relatório; approve do dono** (emenda 2026-09-16, portão da fase 3).
- **Identificadores em template literal disparam `lint:accents`** — resolver com allowlist comentada, nunca afrouxando o lint (emenda 2026-09-16, portão da fase 3).

---

## Fase 4 — Ontem no feed, `/desempenho`

Depende de: fase 1 (backend, pronta) e fase 3 (feed/talão/detalhe — Tasks 12-19 do plano 1, em andamento; as tarefas abaixo assumem que `Talao`, `CardJogo`, `Feed.tsx`, `feedUrl.ts`, `Detalhe.tsx`, `EscalaConfianca.tsx` existem nos caminhos do plano 1).

### Task 20: `lib/ledgerApi.ts` — cliente tipado dos dois proxies

**Files:**
- Create: `frontend/next/src/lib/ledgerApi.ts`, `frontend/next/tests/unit/ledgerApi.test.ts`

**Interfaces:**
- Consumes: `fetch` (global), os proxies `/api/ledger/dia` e `/api/ledger/agregado` (fase 1) — contrato exato: `200 { ok: true, ...payload }` ou `400/503 { ok: false, error: { kind: string; message: string } }` (`frontend/next/src/app/api/ledger/dia/route.ts`, linhas 74-107 do plano 1).
- Produces: `LedgerPick`, `LedgerDia`, `LedgerSegmento`, `LedgerBucket`, `LedgerAgregado` (tipos), `ResultadoLedger<T>`, `getLedgerDia(data: string): Promise<ResultadoLedger<LedgerDia>>`, `getLedgerAgregado(periodo: "7d"|"30d"|"temporada", familia?: string, liga?: string): Promise<ResultadoLedger<LedgerAgregado>>`.

- [ ] **Step 1: Teste (falha: módulo não existe)**

`tests/unit/ledgerApi.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { getLedgerDia, getLedgerAgregado } from "@/lib/ledgerApi";

function stubFetch(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    status,
    json: () => Promise.resolve(body),
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("ledgerApi (#256)", () => {
  it("getLedgerDia: sucesso devolve dados sem o envelope 'ok'", async () => {
    stubFetch({ ok: true, data: "2026-09-14", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
    const r = await getLedgerDia("2026-09-14");
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.dados).toEqual({ data: "2026-09-14", picks: [], resumo: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
  });
  it("getLedgerDia: erro estruturado do proxy vira 'erro'", async () => {
    stubFetch({ ok: false, error: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório" } }, 400);
    const r = await getLedgerDia("lixo");
    expect(r).toEqual({ ok: false, erro: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório" } });
  });
  it("getLedgerDia: falha de rede (fetch rejeita) vira NETWORK_ERROR, nunca lança", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const r = await getLedgerDia("2026-09-14");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.erro.kind).toBe("NETWORK_ERROR");
  });
  it("getLedgerAgregado: monta querystring com periodo/familia/liga", async () => {
    stubFetch({ ok: true, periodo: "7d", familia: "Corners", liga: "mls", acerto: { picks: 1, acertos: 1, jogos: 1, resolvidos: 1 } });
    await getLedgerAgregado("7d", "Corners", "mls");
    const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(chamada).toContain("periodo=7d");
    expect(chamada).toContain("familia=Corners");
    expect(chamada).toContain("liga=mls");
  });
  it("getLedgerAgregado: sem familia/liga nao manda os parametros", async () => {
    stubFetch({ ok: true, periodo: "30d", acerto: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 } });
    await getLedgerAgregado("30d");
    const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(chamada).not.toContain("familia=");
    expect(chamada).not.toContain("liga=");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run tests/unit/ledgerApi.test.ts` → `Cannot find module '@/lib/ledgerApi'`.

- [ ] **Step 3: Implementar**

`src/lib/ledgerApi.ts`:
```ts
/**
 * #256 — cliente tipado dos proxies `/api/ledger/dia` e `/api/ledger/agregado`
 * (fase 1, contrato em `frontend/next/src/app/api/ledger/{dia,agregado}/route.ts`:
 * `200 { ok: true, ...payload }` ou `400|503 { ok: false, error: { kind, message } }`).
 * Nunca lança: falha de rede vira `{ ok: false, erro: { kind: "NETWORK_ERROR", ... } }`.
 */

export interface LedgerPick {
  match_id: string;
  league_id: string;
  kickoff_utc: string | null;
  familia: string;
  market: string;
  selection: string;
  published_prob: number | null;
  fair_odd: number | null;
  book_odd: number | null;
  classification: string;
  outcome: 0 | 1 | null;
  detail: string | null;
}

/** `resolvidos` (picks individuais com outcome != null) é adicionado pela
 * Task 20-bis (backend) — é o único denominador válido para "X de cada 100
 * picks": `picks` inclui não-resolvidos, `jogos` conta partidas distintas
 * (pode ser MENOR que `acertos` quando dois picks do mesmo jogo acertam). */
export interface LedgerResumo { picks: number; acertos: number; jogos: number; resolvidos: number }

export interface LedgerDia {
  data: string;
  picks: LedgerPick[];
  resumo: LedgerResumo;
  semana: Record<string, LedgerResumo>;
  mes: Record<string, LedgerResumo>;
}

export interface LedgerSegmento { picks: number; acertos: number; n_jogos: number; resolvidos: number; brier: number | null }
export interface LedgerBucket { prob_media: number | null; freq_real: number | null; n: number }

export interface LedgerAgregado {
  periodo: string;
  familia: string | null;
  liga: string | null;
  acerto: { picks: number; acertos: number; jogos: number; resolvidos: number };
  retorno: { valor: number | null; pct_banca: number | null; motivo: string | null };
  brier: number | null;
  amostra_curta: boolean;
  por_familia: Record<string, LedgerSegmento>;
  por_liga: Record<string, LedgerSegmento>;
  buckets: LedgerBucket[] | null;
}

export type ResultadoLedger<T> =
  | { ok: true; dados: T }
  | { ok: false; erro: { kind: string; message: string } };

async function chamar<T>(url: string): Promise<ResultadoLedger<T>> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    const corpo = await res.json();
    if (!corpo.ok) {
      return { ok: false, erro: corpo.error ?? { kind: "UNKNOWN", message: "falha desconhecida" } };
    }
    const { ok: _ok, ...dados } = corpo;
    return { ok: true, dados: dados as T };
  } catch {
    return { ok: false, erro: { kind: "NETWORK_ERROR", message: "sem conexão com o servidor" } };
  }
}

export function getLedgerDia(data: string): Promise<ResultadoLedger<LedgerDia>> {
  return chamar<LedgerDia>(`/api/ledger/dia?data=${encodeURIComponent(data)}`);
}

export function getLedgerAgregado(
  periodo: "7d" | "30d" | "temporada",
  familia?: string,
  liga?: string,
): Promise<ResultadoLedger<LedgerAgregado>> {
  const params = new URLSearchParams({ periodo });
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);
  return chamar<LedgerAgregado>(`/api/ledger/agregado?${params.toString()}`);
}
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/ledgerApi.test.ts` → PASS (5 testes).
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/ledgerApi.ts frontend/next/tests/unit/ledgerApi.test.ts && git commit -m "feat(front): cliente tipado dos proxies /api/ledger (#256)"`

**Nota:** este arquivo usa `resolvidos` nos tipos e fixtures acima porque assume que a Task 20-bis (backend, abaixo) já fechou. Rodar as duas tarefas nesta ordem.

---

### Task 20-bis: backend — `resolvidos` em `_resumo`/`_segmento`/`agregado()`

**Por quê (Etapa 1, achado no code review deste plano).** A frase planejada para `/desempenho` ("X de cada 100 picks acertaram") precisa de uma fração `acertos / algo` que nunca ultrapasse 100%. `acertos / jogos` **não serve**: `jogos` conta partidas distintas e `acertos` conta PICKS individuais — se dois picks do mesmo jogo acertam, `acertos` sobe 2 e `jogos` sobe só 1. Medido em produção (`/ledger/agregado?periodo=7d`, 2026-09-16): `{"picks":73,"acertos":38,"jogos":37}` — 38 acertos em apenas 37 jogos é **correto**, não um bug de dado (múltiplos picks acertando no mesmo jogo), mas torna `acertos/jogos` = 103% sem sentido como "de cada 100 picks". O denominador certo é a contagem de **picks individuais já com desfecho** (`outcome != null`), que por construção é sempre ≥ `acertos`.

**Rastreabilidade.** Produtor/consumidor são o mesmo módulo, só uma leitura adicional: `backend/services/ledger_leitura.py::_resumo` (linhas 163-170 do arquivo hoje) já itera `contados`/`resolvidos` para calcular `picks`/`acertos`/`jogos` — `resolvidos` é `len()` de uma lista que a função já constrói, não uma consulta nova ao banco.

**Critérios de aceite.**
- `_resumo(linhas)["resolvidos"]` == número de linhas com `classification` em `(SAFE, NEUTRO_QUALIFICADO)` e `outcome is not None`.
- `dia()["resumo"]`, `dia()["semana"][familia]`, `dia()["mes"][familia]` — todos chamam `_resumo` direto, então já carregam `resolvidos` sem mudança adicional de código nessas funções.
- `_segmento(linhas)["resolvidos"]` == o mesmo valor de `_resumo(linhas)["resolvidos"]` (repassado, não recalculado).
- `agregado(...)["acerto"]["resolvidos"]` == `_segmento(contados)["resolvidos"]`.
- `por_familia`/`por_liga` (cada um um `_segmento`) também carregam `resolvidos` — efeito colateral aceito do repasse, não uma obrigação nova de contrato (nenhuma tela exige esse campo ali ainda).

**Contratos de saída (Etapa 2-bis).** Campo novo: `resolvidos` em `_resumo`/`_segmento`/`dia()`/`agregado()["acerto"|"por_familia"|"por_liga"]`. Consumidores externos: só o frontend novo desta mesma fase (`lib/ledgerApi.ts`, Task 20 — já escrito assumindo este campo). Nenhum outro módulo do backend chama `_resumo`/`_segmento`/`dia`/`agregado` (confirmado: `backend/routes/ledger.py` é o único chamador de `dia`/`agregado`, e nenhuma outra rota importa `ledger_leitura`). Não quebra nada existente — campo aditivo em dict, sem remoção.

**Files:**
- Modify: `backend/services/ledger_leitura.py`
- Create: `tests/test_256_resolvidos.py`

- [ ] **Step 1: Teste (falha: chave `resolvidos` não existe)**

`tests/test_256_resolvidos.py`:
```python
# -*- coding: utf-8 -*-
"""#256 — `_resumo`/`_segmento`/`agregado()['acerto']` ganham `resolvidos`
(picks individuais com outcome != null), porque `acertos/jogos` nao e uma
fracao valida: `jogos` conta partidas distintas, `acertos` conta PICKS
individuais corretos, e mais de um pick pode acertar no mesmo jogo (medido em
producao 2026-09-16: picks=73, acertos=38, jogos=37 — 38 > 37 e correto, nao
um bug de dado). `resolvidos` e o denominador que NUNCA fica menor que
`acertos`, por construcao.
"""
from datetime import datetime, timedelta, timezone

from backend.services import ledger_leitura as L

_UTC = timezone.utc


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._linhas

    def close(self):
        pass


class _Conn:
    def __init__(self, linhas):
        self.cur = _Cursor(linhas)

    def cursor(self):
        return self.cur

    def close(self):
        pass


def _linha(match_id, market, selection, prob, book_odd, classification,
          published_at, kickoff_utc, outcome=None, detail=None,
          league_id="premier-league"):
    return (match_id, league_id, market, selection, prob, book_odd,
            classification, published_at, kickoff_utc, outcome, detail)


def test_dois_picks_no_mesmo_jogo_acertando_nao_estoura_100_por_cento(monkeypatch):
    """acertos=2, jogos=1 (o caso real de producao, em miniatura) —
    acertos/jogos daria 200%; acertos/resolvidos da 100%, o numero valido."""
    k = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, detail={"total_goals": 3}),
        _linha("m1", "Corners", "Over 6.5", 0.58, 1.75, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, detail={"total_corners": 8}),
    ]
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r = L.dia("2026-09-14")
    assert r["resumo"] == {"picks": 2, "acertos": 2, "jogos": 1, "resolvidos": 2}


def test_segmento_e_agregado_carregam_resolvidos(monkeypatch):
    linhas = []
    base = datetime(2026, 9, 1, 12, 0, tzinfo=_UTC)
    for i in range(25):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(
            f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < 15 else 0, detail={"total_goals": 3},
        ))
    # 5 picks nunca resolvidos (outcome None) — contam em `picks`, NAO em `resolvidos`.
    for i in range(25, 30):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
                              kickoff - timedelta(hours=2), kickoff, outcome=None))
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["acerto"]["picks"] == 30
    assert r["acerto"]["resolvidos"] == 25
    assert r["acerto"]["acertos"] == 15
    assert r["acerto"]["jogos"] == 25
    # por_familia e por_liga tambem carregam o campo (repasse de _segmento).
    assert r["por_familia"]["Over/Under"]["resolvidos"] == 25
```

Run: `python -m pytest -q -o addopts="" tests/test_256_resolvidos.py`
Expected: FAIL — `KeyError: 'resolvidos'`.

- [ ] **Step 2: Implementar**

Em `backend/services/ledger_leitura.py`, `_resumo` ganha a chave (o resto do corpo não muda — `resolvidos` já existia como variável local, só não era exposta):
```python
def _resumo(linhas: List[Dict[str, Any]]) -> Dict[str, int]:
    contados = [l for l in linhas if l["classification"] in _PICKS_CONTADOS]
    resolvidos = [l for l in contados if l["outcome"] is not None]
    return {
        "picks": len(contados),
        "acertos": sum(1 for l in resolvidos if l["outcome"]),
        "jogos": len({l["match_id"] for l in resolvidos}),
        "resolvidos": len(resolvidos),
    }
```

`_segmento` repassa o valor (não recalcula):
```python
def _segmento(linhas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Picks/acertos/n_jogos/resolvidos + Brier com o piso MIN_N=20 em JOGOS (#079).
    Retorna `n_jogos` (nao `jogos`) para o contrato de saida de `por_familia`/`por_liga`."""
    r = _resumo(linhas)
    resolvidos = [l for l in linhas
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]
    brier = None
    if r["jogos"] >= MIN_N:
        brier = round(_brier(
            [l["published_prob"] for l in resolvidos],
            [l["outcome"] for l in resolvidos],
        ), 4)
    return {"picks": r["picks"], "acertos": r["acertos"], "n_jogos": r["jogos"],
            "resolvidos": r["resolvidos"], "brier": brier}
```

`agregado()` carrega o campo no dict `acerto` (única linha nova):
```python
    return {
        "periodo": periodo, "familia": familia, "liga": liga,
        "acerto": {"picks": resumo_geral["picks"], "acertos": resumo_geral["acertos"],
                  "jogos": resumo_geral["n_jogos"], "resolvidos": resumo_geral["resolvidos"]},
        # #255: stake nunca e gravado no ledger — ver Global Constraints do plano.
        "retorno": {"valor": None, "pct_banca": None,
                   "motivo": "stake_nao_gravado_no_ledger"},
        "brier": resumo_geral["brier"],
        "amostra_curta": resumo_geral["n_jogos"] < MIN_N,
        "por_familia": por_familia,
        "por_liga": por_liga,
        "buckets": buckets,
    }
```
(`por_familia`/`por_liga` já são dicts de `_segmento(...)` — carregam `resolvidos` automaticamente, sem editar essas linhas.)

- [ ] **Step 3: Rodar e ver passar**

Run: `python -m pytest -q -o addopts="" tests/test_256_resolvidos.py`
Expected: PASS (2 testes).

Run: `python -m pytest -q -o addopts="" tests/test_255_ledger_leitura.py`
Expected: PASS — os testes da fase 1 comparam dicts completos com `==` em alguns pontos (ex.: `test_dia_resumo_acertos_e_jogos` usa asserts de campo, não `==` do dict inteiro, então sobrevivem à chave nova sem alteração; conferir cada um antes de seguir — se algum comparar o dict `resumo`/`acerto` inteiro com `==` e quebrar por causa da chave nova, ATUALIZAR aquele teste para incluir `resolvidos` no dict esperado, é uma consequência aceita e prevista desta tarefa, não uma regressão).

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde.

- [ ] **Step 4: Commit**

```bash
git add backend/services/ledger_leitura.py tests/test_256_resolvidos.py
git commit -m "$(cat <<'EOF'
feat(backend): resolvidos em _resumo/_segmento/agregado — denominador valido para "de cada 100 picks" (#256)

acertos/jogos podia passar de 100% (varios picks acertando no mesmo jogo,
medido em producao: 38 acertos em 37 jogos). resolvidos (picks individuais
com outcome != null) e sempre >= acertos, por construcao.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

**Nota para a Task 27 (fechamento da fase):** este commit toca `backend/**` — o push do fechamento da fase 4 dispara `deploy-lambda.yml` automaticamente (CLAUDE.md, seção Finalização), não é preciso rodar `scripts/deploy_lambda.py` à parte.

---

### Task 21: `lib/jogoViewOntem.ts` — picks do ledger viram `JogoView`

**Por quê (Etapa 1).** `toJogoView` (`lib/jogoView.ts`) só enxerga o payload de `/fixtures`, que para um jogo passado seria **recomputado**, não o que foi publicado (decisão de projeto #1 no topo deste plano). Esta tarefa cria o caminho paralelo, só para ontem, que constrói o MESMO tipo `JogoView`/`PickView` a partir do ledger, para `CardJogo`/`Talao`/`Detalhe` (fase 3) funcionarem sem alteração.

**Rastreabilidade (produtor → consumidor).** Produtor: `backend/services/ledger_leitura.py::_pick_json` (via `GET /ledger/dia`, Task 20). Consumidor: `Feed.tsx` (Task 22). Campos usados, confirmados no código do produtor: `match_id` (formato `{league_id}-{casa}-{fora}-{epoch}`, `backend/services/prediction_ledger.py:236`), `league_id`, `market`, `selection`, `published_prob`, `fair_odd`, `book_odd`, `classification`, `outcome`, `detail`. Nenhum campo é inferido sem essa leitura.

**Critérios de aceite.**
- `parseTimesDoMatchId("mls-Toronto-Nashville SC-1788985800.0", "mls")` → `{ casa: "Toronto", fora: "Nashville SC" }`.
- `parseTimesDoMatchId("liga-mx-Guadalajara-Pumas UNAM-1789348020.0", "liga-mx")` → `{ casa: "Guadalajara", fora: "Pumas UNAM" }` (exemplo real de produção, citado na tarefa).
- Time com hífen interno (não observado nos exemplos reais, mas coberto): a função nunca lança — devolve `casa` = string inteira, `fora` = `""`.
- `toJogoViewOntem`: entre os picks do mesmo jogo, escolhe o talão pela MESMA regra de `escolherTalao` (maior edge, empate por chance); `estado` é `"ontem"` quando o talão tem `outcome` não nulo, `"ontem_sem_desfecho"` quando é nulo, `"direcao"` quando não há talão (só NEUTRO — `/ledger/dia` nunca inclui `NO_BET`, confirmado no `WHERE` de `_SQL_JANELA`).
- `resultado.acertou` é `outcome === 1`; `resultado.detalhe` é o campo `detail` já textual (`"8 escanteios"`, vindo pronto de `_detalhe_textual` no backend).

**Cenários de borda.** Pick sem `book_odd` (não publicado com preço): ainda vale para o talão se `classification` for SAFE/NQ (a spec não exige preço para ser o pick de ontem — o preço mínimo já é mostrado via `fairOdd`). Pick com `published_prob` ou `fair_odd` nulos (não deveria ocorrer — `_SQL_JANELA` filtra `published_prob IS NOT NULL`, e `_fair_odd` deriva de `published_prob`; ainda assim a função filtra defensivamente e não quebra).

- [ ] **Step 1: Teste**

`tests/unit/jogoViewOntem.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { parseTimesDoMatchId, formatarSelecaoLedger, agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import type { LedgerPick } from "@/lib/ledgerApi";

function pick(over: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "mls-Toronto-Nashville SC-1788985800.0", league_id: "mls",
    kickoff_utc: "2026-09-14T23:30:00+00:00", familia: "Corners", market: "Corners",
    selection: "Corners Over 6.5", published_prob: 0.585, fair_odd: 1.67, book_odd: 1.75,
    classification: "SAFE", outcome: null, detail: null, ...over,
  };
}

describe("parseTimesDoMatchId (#256)", () => {
  it("formato padrao liga-casa-fora-epoch", () => {
    expect(parseTimesDoMatchId("mls-Toronto-Nashville SC-1788985800.0", "mls"))
      .toEqual({ casa: "Toronto", fora: "Nashville SC" });
  });
  it("liga com hifen no proprio slug (exemplo real de producao)", () => {
    expect(parseTimesDoMatchId("liga-mx-Guadalajara-Pumas UNAM-1789348020.0", "liga-mx"))
      .toEqual({ casa: "Guadalajara", fora: "Pumas UNAM" });
  });
  it("time com hifen interno nao quebra — cai no fallback documentado", () => {
    const r = parseTimesDoMatchId("premier-league-Newcastle-United-Arsenal-1788985800.0", "premier-league");
    expect(r.fora === "" || (r.casa.length > 0 && r.fora.length > 0)).toBe(true);
  });
});

describe("formatarSelecaoLedger (#256, aproximacao do display_label — ver decisao 3 do plano)", () => {
  it("Over/Under acrescenta 'gols' quando falta", () => {
    expect(formatarSelecaoLedger("Over/Under", "Under 3.5")).toBe("Under 3.5 gols");
  });
  it("Corners troca o prefixo por Escanteios", () => {
    expect(formatarSelecaoLedger("Corners", "Corners Over 6.5")).toBe("Escanteios Over 6.5");
  });
  it("Cards vira Cartões com acento (fmtMercado)", () => {
    expect(formatarSelecaoLedger("Cards", "Over 3.5")).toBe("Cartões Over 3.5");
  });
  it("BTTS mapeia Yes/No", () => {
    expect(formatarSelecaoLedger("BTTS", "BTTS Yes")).toBe("Ambos marcam — SIM");
    expect(formatarSelecaoLedger("BTTS", "BTTS No")).toBe("Ambos marcam — NÃO");
  });
  it("desconhecido cai no texto bruto", () => {
    expect(formatarSelecaoLedger("Outro", "X")).toBe("X");
  });
});

describe("toJogoViewOntem (#256, spec §4.2)", () => {
  it("estado 'ontem' quando o talao tem outcome", () => {
    const picks = [pick({ outcome: 1, detail: "8 escanteios" })];
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", picks);
    expect(v.estado).toBe("ontem");
    expect(v.resultado).toEqual({ acertou: true, detalhe: "8 escanteios" });
    expect(v.casa).toBe("Toronto"); expect(v.fora).toBe("Nashville SC");
    expect(v.talao?.mercado).toBe("Escanteios Over 6.5");
  });
  it("estado 'ontem_sem_desfecho' quando outcome e nulo", () => {
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", [pick({ outcome: null })]);
    expect(v.estado).toBe("ontem_sem_desfecho");
    expect(v.resultado).toBeNull();
  });
  it("erro: sem talao (so NEUTRO), estado 'direcao'", () => {
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS",
      [pick({ classification: "NEUTRO", outcome: 0, detail: "5 escanteios" })]);
    expect(v.estado).toBe("direcao");
    expect(v.direcao?.mercado).toBe("Escanteios Over 6.5");
  });
  it("escolhe o talao pela mesma regra de escolherTalao (maior edge)", () => {
    const picks = [
      pick({ market: "Corners", selection: "Corners Over 6.5", book_odd: 1.70, fair_odd: 1.67, outcome: 1, detail: "8 escanteios" }),
      pick({ market: "Cards", selection: "Over 2.5", published_prob: 0.60, book_odd: 2.10, fair_odd: 1.67, outcome: 0, detail: "1 cartão" }),
    ];
    const v = toJogoViewOntem("mls-Toronto-Nashville SC-1788985800.0", "mls", "MLS", picks);
    expect(v.talao?.mercado).toBe("Cartões Over 2.5"); // edge: 0.60 - 1/2.10 ≈ 0,1238 > 0.585 - 1/1.70 ≈ -0,0032 (o pick de Corners fica com edge NEGATIVO — book_odd 1.70 abaixo do que a chance publicada sugeriria)
    expect(v.resultado).toEqual({ acertou: false, detalhe: "1 cartão" });
  });
});

describe("agruparPorJogo", () => {
  it("agrupa picks pelo match_id", () => {
    const a = pick({ match_id: "j1" }), b = pick({ match_id: "j1", market: "Cards" }), c = pick({ match_id: "j2" });
    const m = agruparPorJogo([a, b, c]);
    expect(m.get("j1")).toHaveLength(2);
    expect(m.get("j2")).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar** — `npx vitest run tests/unit/jogoViewOntem.test.ts`.

- [ ] **Step 3: Implementar**

`src/lib/jogoViewOntem.ts`:
```ts
/**
 * #256 — picks do `/ledger/dia` viram `JogoView`/`PickView` (os MESMOS tipos
 * de `lib/jogoView.ts`), para "ontem" reaproveitar `CardJogo`/`Talao`/`Detalhe`
 * sem alteração. Fonte única (spec §6.3): NUNCA chama `/fixtures` para dias
 * passados — só o que foi publicado, via ledger.
 */
import type { JogoView, PickView } from "@/lib/jogoView";
import { escolherTalao } from "@/lib/jogoView";
import type { LedgerPick } from "@/lib/ledgerApi";
import { fmtMercado } from "@/lib/classifications";

const VALE = new Set(["SAFE", "NEUTRO_QUALIFICADO"]);

/**
 * `match_id` = `{league_id}-{casa}-{fora}-{epoch}` (backend/services/
 * prediction_ledger.py:236, kickoff_da_linha). `league_id` já vem separado no
 * próprio pick — remover esse prefixo exato elimina a ambiguidade de slugs
 * de liga com hífen (ex.: "liga-mx", "premier-league"). O sufixo epoch é
 * removido com a mesma regra do backend (`rsplit` do último `-` numérico).
 * Nenhum nome de time com hífen interno foi observado nos exemplos reais de
 * produção auditados para a Task 21 (#256); se aparecer, o fallback abaixo
 * NUNCA lança — devolve a string inteira em `casa` e `fora` vazio.
 */
export function parseTimesDoMatchId(matchId: string, leagueId: string): { casa: string; fora: string } {
  const prefixo = `${leagueId}-`;
  const semLiga = matchId.startsWith(prefixo) ? matchId.slice(prefixo.length) : matchId;
  const semEpoch = semLiga.replace(/-\d+(\.\d+)?$/, "");
  const partes = semEpoch.split("-");
  if (partes.length !== 2 || !partes[0] || !partes[1]) return { casa: semEpoch, fora: "" };
  return { casa: partes[0], fora: partes[1] };
}

/**
 * Aproxima o `display_label` que o backend monta em `ev_classification.py`
 * (linhas 1005, 1056/1097, 1120, 1335/1413, 1488/1514) a partir de
 * `market`/`selection` — o `prediction_ledger` NÃO grava `display_label`
 * (só `market`/`selection`, `prediction_ledger.py:710-711`), então o texto
 * exato publicado não pode ser recuperado; isto é uma reconstrução, não uma
 * cópia. Verificar empiricamente contra linhas reais antes de fechar a
 * tarefa (Step 5 abaixo).
 */
export function formatarSelecaoLedger(market: string, selection: string): string {
  const s = (selection || "").trim();
  switch (market) {
    case "Over/Under":
      return fmtMercado(/gols?$/i.test(s) ? s : `${s} gols`);
    case "Corners":
      return fmtMercado(s.replace(/^Corners\s*/i, "Escanteios "));
    case "Cards":
      return fmtMercado(`Cartoes ${s.replace(/^Cards\s*/i, "")}`.trim());
    case "BTTS":
      return /yes/i.test(s) ? "Ambos marcam \u2014 SIM" : "Ambos marcam \u2014 N\u00c3O";
    default:
      return fmtMercado(s);
  }
}

export function agruparPorJogo(picks: LedgerPick[]): Map<string, LedgerPick[]> {
  const mapa = new Map<string, LedgerPick[]>();
  for (const p of picks) {
    const lista = mapa.get(p.match_id) ?? [];
    lista.push(p);
    mapa.set(p.match_id, lista);
  }
  return mapa;
}

export function toJogoViewOntem(
  matchId: string, leagueId: string, ligaNome: string, picksDoJogo: LedgerPick[],
): JogoView {
  const { casa, fora } = parseTimesDoMatchId(matchId, leagueId);
  const kickoffIso = picksDoJogo.find((p) => p.kickoff_utc)?.kickoff_utc ?? "";
  const pares = picksDoJogo
    .filter((p) => p.published_prob != null && p.fair_odd != null)
    .map((p) => ({
      raw: p,
      view: {
        mercado: formatarSelecaoLedger(p.market, p.selection),
        prob01: p.published_prob as number,
        fairOdd: p.fair_odd as number,
        bookOdd: p.book_odd,
        edge: p.book_odd != null && p.book_odd > 1
          ? Number(((p.published_prob as number) - 1 / p.book_odd).toFixed(4))
          : null,
        ev: null,
        classification: p.classification,
        motivo: "",
        vale: VALE.has(p.classification),
      } as PickView,
    }));
  const picks = pares.map((x) => x.view);
  const { talao, segundo } = escolherTalao(picks);
  const parDoTalao = talao ? pares.find((x) => x.view === talao) : undefined;
  const resultado = parDoTalao && parDoTalao.raw.outcome != null
    ? { acertou: parDoTalao.raw.outcome === 1, detalhe: parDoTalao.raw.detail ?? "" }
    : null;
  const estado: JogoView["estado"] = talao ? (resultado ? "ontem" : "ontem_sem_desfecho") : "direcao";

  return {
    id: matchId, ligaId: leagueId, ligaNome, casa, fora, kickoffIso, estado,
    talao, segundo,
    direcao: talao ? null : (picks.find((p) => p.classification === "NEUTRO") ?? null),
    mercados: picks, totalAvaliados: picks.length, totalValem: picks.filter((p) => p.vale).length,
    aoVivo: null, resultado,
    origem: { golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null },
  };
}
```

- [ ] **Step 4: Rodar e ver passar** — `npx vitest run tests/unit/jogoViewOntem.test.ts` → PASS.

- [ ] **Step 5: Verificação empírica do rótulo (Etapa 2, obrigatória antes de fechar — critério de bloqueio)**

Rodar contra dados reais (RDS local ou staging, sem escrever nada), com uma amostra grande o bastante para medir proporção, não só olhar exemplos:
```bash
curl -s "https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/ledger/dia?data=2026-09-14" \
  | python -c "
import json, sys
d = json.load(sys.stdin)
CONHECIDOS = {'Over/Under', 'Corners', 'Cards', 'BTTS'}
picks = d['picks']
default = [p for p in picks if p['market'] not in CONHECIDOS]
for p in picks:
    print(p['market'], '|', p['selection'])
pct = 100 * len(default) / len(picks) if picks else 0
print(f'--- {len(default)}/{len(picks)} ({pct:.1f}%) caem no default (market fora de {sorted(CONHECIDOS)}) ---')
"
```
Repetir para 2-3 datas diferentes (dias com volume normal de picks) e somar os totais, para a proporção não depender de um dia atípico.

**Critério de bloqueio:** se o `default` (fallback genérico de `formatarSelecaoLedger`) responder por **mais de 10%** dos picks somados, a tarefa **não fecha** — acrescentar um `case` ao switch para o(s) `market` mais frequente(s) fora da lista (candidatos prováveis: `"1X2"`, `"Double Chance"`), com teste, e medir de novo. Abaixo de 10%, seguir. Anotar o percentual exato medido (não uma estimativa) no REGISTRO da Task 27.

**Fora do escopo deste plano:** se a causa raiz for "o texto exato do `display_label` nunca foi gravado" (decisão de projeto #3), a correção definitiva é o PRODUTOR (`backend/services/prediction_ledger.py::linhas_do_bundle`/`montar_linha`) passar a gravar `display_label` como coluna nova em `prediction_ledger` — mudança de schema e de produtor, fora do escopo deste plano (que é só leitura). Registrar como item de acompanhamento no REGISTRO da Task 27, não implementar aqui.

- [ ] **Step 6: Commit** — `git add frontend/next/src/lib/jogoViewOntem.ts frontend/next/tests/unit/jogoViewOntem.test.ts && git commit -m "feat(front): jogoViewOntem — picks do ledger viram JogoView (#256)"`

---

### Task 22: Ligar "ontem" ao `Feed.tsx`

**Files:**
- Modify: `frontend/next/src/app/jogos/Feed.tsx` (definido no plano 1, Task 15), `frontend/next/src/lib/feedUrl.ts` (idem), `frontend/next/src/lib/copy.ts` (fase 0 — `VAZIOS.feedNaoCarregou` ganha o dia como parâmetro)
- Create: `frontend/next/tests/unit/feedUrl.test.ts` (acrescentar caso), `frontend/next/e2e/ontem.spec.ts`, `frontend/next/e2e/fixtures/ledger-dia.json`

**Interfaces:**
- Consumes: `getLedgerDia` (Task 20), `agruparPorJogo`, `toJogoViewOntem` (Task 21), `ACTIVE_LEAGUES`, `toBackendLeagueId` (`lib/leagues.ts`).
- Produces: `diaISOOntem(agora: Date): string` em `lib/feedUrl.ts`; `VAZIOS.feedNaoCarregou(dia?: "ontem" | "hoje" | "amanha"): string` (troca a constante da fase 0 por função — default `"hoje"` preserva o texto que o plano 1 já testa).

- [ ] **Step 1: Teste de `diaISOOntem` (puro, injeta `agora` — nunca lê o relógio)**

Acrescentar a `tests/unit/feedUrl.test.ts` (arquivo já existe da fase 3; se por ordem de execução esta task rodar antes, criar o arquivo com o conteúdo do plano 1, Task 15, Step 1, mais o bloco abaixo):
```ts
import { diaISOOntem } from "@/lib/feedUrl";

describe("diaISOOntem (#256) — BRT fixo UTC-3, mesma convencao das outras datas do app", () => {
  it("meio-dia UTC de hoje vira o dia anterior em BRT", () => {
    expect(diaISOOntem(new Date("2026-09-16T12:00:00Z"))).toBe("2026-09-15");
  });
  it("madrugada UTC (ainda tarde do dia anterior em BRT) tambem cai um dia", () => {
    expect(diaISOOntem(new Date("2026-09-16T02:00:00Z"))).toBe("2026-09-14");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar em `lib/feedUrl.ts`**

Acrescentar ao arquivo (não remover o que já existe):
```ts
/**
 * #256 — data ISO (YYYY-MM-DD) do dia anterior, em BRT fixo (UTC-3, sem
 * horário de verão desde 2019 — mesma convenção informal do resto do app,
 * que já usa BRT fixo para "today"/"tomorrow" em `backend/routes/fixtures.py`).
 * Pura: recebe `agora`, nunca lê o relógio — testável sem mock de tempo.
 */
export function diaISOOntem(agora: Date): string {
  const brtOntem = new Date(agora.getTime() - 3 * 3600_000 - 24 * 3600_000);
  return brtOntem.toISOString().slice(0, 10);
}
```

- [ ] **Step 3: Rodar e ver passar** — `npx vitest run tests/unit/feedUrl.test.ts`.

- [ ] **Step 4: Fixture e teste E2E (falha: Feed ainda não busca o ledger)**

`e2e/fixtures/ledger-dia.json` (uma resposta de `/api/ledger/dia` com dois jogos: um com talão e desfecho, outro sem talão):
```json
{
  "ok": true,
  "data": "2026-09-15",
  "picks": [
    { "match_id": "mls-Toronto-Nashville SC-1789344000.0", "league_id": "mls", "kickoff_utc": "2026-09-15T23:30:00+00:00", "familia": "Corners", "market": "Corners", "selection": "Corners Over 6.5", "published_prob": 0.585, "fair_odd": 1.67, "book_odd": 1.75, "classification": "SAFE", "outcome": 1, "detail": "8 escanteios" },
    { "match_id": "la-liga-Levante-Athletic Bilbao-1789347600.0", "league_id": "la-liga", "kickoff_utc": "2026-09-15T22:00:00+00:00", "familia": "Over/Under", "market": "Over/Under", "selection": "Under 3.5", "published_prob": 0.55, "fair_odd": 1.81, "book_odd": null, "classification": "NEUTRO", "outcome": 0, "detail": "3 gols" }
  ],
  "resumo": { "picks": 1, "acertos": 1, "jogos": 1, "resolvidos": 1 },
  "semana": {}, "mes": {}
}
```
(o segundo jogo é NEUTRO — `resumo` só conta SAFE/NEUTRO_QUALIFICADO, `_PICKS_CONTADOS` em `ledger_leitura.py` — por isso `picks: 1`, não 2.)

`e2e/ontem.spec.ts`:
```ts
import { test, expect } from "@playwright/test";
import ledgerDia from "./fixtures/ledger-dia.json";

test.describe("/jogos?dia=ontem (#256, spec §4.2)", () => {
  test("talao com desfecho mostra a faixa de resultado; jogo so-NEUTRO cai em direcao", async ({ page }) => {
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerDia) }));
    await page.goto("/jogos?dia=ontem");
    await expect(page.locator("article[data-estado='ontem']")).toHaveCount(1);
    await expect(page.getByText("\u2713 fechou com 8 escanteios")).toBeVisible();
    await expect(page.locator("article[data-estado='direcao']")).toHaveCount(1);
  });
  test("ledger fora do ar: mensagem, sem recomputar via /fixtures", async ({ page }) => {
    await page.route("**/api/ledger/dia**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ ok: false, error: { kind: "BACKEND_ERROR", message: "x" } }) }));
    let chamouFixtures = false;
    await page.route("**/api/matches/fetch**", (route) => { chamouFixtures = true; route.continue(); });
    await page.goto("/jogos?dia=ontem");
    await expect(page.getByText("Os jogos de ontem não carregaram.")).toBeVisible();
    expect(chamouFixtures).toBe(false);
  });
});
```

- [ ] **Step 5: `VAZIOS.feedNaoCarregou` ganha o dia como parâmetro**

Em `src/lib/copy.ts` (fase 0), **substituir exatamente este trecho** (a constante de string dentro de `VAZIOS`):
```ts
  feedNaoCarregou: "Os jogos de hoje não carregaram.",
```
por:
```ts
  /** #256 — parametrizado por dia; sem argumento continua igual ao texto que
   * o plano 1 já testa ("Os jogos de hoje não carregaram."). */
  feedNaoCarregou: (dia: "ontem" | "hoje" | "amanha" = "hoje") =>
    `Os jogos ${dia === "ontem" ? "de ontem" : dia === "amanha" ? "de amanhã" : "de hoje"} não carregaram.`,
```
(as outras chaves de `VAZIOS` — `tentarDeNovo`, `carimbo`, `ligaSemDados`, etc. — não mudam.)

- [ ] **Step 6: Ligar ao `Feed.tsx`**

Em `src/app/jogos/Feed.tsx` (arquivo do plano 1, Task 15), os imports ganham:
```ts
import { getLedgerDia } from "@/lib/ledgerApi";
import { agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import { lerFeedUrl, escreverFeedUrl, diaParaApi, diaISOOntem, type Dia } from "@/lib/feedUrl";
import { toBackendLeagueId } from "@/lib/leagues";
import { ResumoDoDia } from "@/components/feed/ResumoDoDia";
```
(a última linha antecipa a Task 23 — se rodar esta task antes, criar um placeholder `export function ResumoDoDia() { return null; }` em `src/components/feed/ResumoDoDia.tsx` e deixar a Task 23 substituir.)

O componente ganha um novo estado, `resumoOntem`, e a função `carregarOntem`:
```ts
const [resumoOntem, setResumoOntem] = useState<{ picks: number; acertos: number; jogos: number; resolvidos: number } | null>(null);

const carregarOntem = useCallback(async () => {
  setCarregando(true);
  const data = diaISOOntem(new Date());
  const r = await getLedgerDia(data);
  if (!r.ok) { setErro(true); setJogos(ultimoBom.current); setCarregando(false); return; }
  const porJogo = agruparPorJogo(r.dados.picks);
  const views = Array.from(porJogo.entries()).map(([matchId, picksDoJogo]) => {
    const leagueId = picksDoJogo[0].league_id;
    const liga = ligas.find((l) => toBackendLeagueId(l.id) === leagueId);
    return toJogoViewOntem(matchId, liga?.id ?? leagueId, liga?.nome ?? leagueId, picksDoJogo);
  }).sort((a, b) => a.kickoffIso.localeCompare(b.kickoffIso));
  ultimoBom.current = views; setJogos(views); setResumoOntem(r.dados.resumo);
  setCarimbo(fmtHora(new Date().toISOString())); setErro(false); setCarregando(false);
}, [ligas]);
```

O `carregar` do plano 1 (Task 15) é hoje, **por inteiro**:
```ts
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
```
**Substituir exatamente este trecho** por:
```ts
const carregar = useCallback(async () => {
  if (url.dia === "ontem") { await carregarOntem(); return; }
  const date = diaParaApi(url.dia);
  if (!date) { setJogos([]); setCarregando(false); return; }
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
}, [url.dia, ligas, carregarOntem]);
```
(a única mudança de corpo é a primeira linha, que desvia para `carregarOntem`; o resto é idêntico ao plano 1 — a lista de dependências ganha `carregarOntem`.)

No JSX do banner de erro do plano 1 (Task 15), que hoje é:
```tsx
{erro && (
  <p className="my-2 text-[14px]" role="status">
    {VAZIOS.feedNaoCarregou} <button onClick={carregar} className="sb-foco underline">{VAZIOS.tentarDeNovo}</button>
    {carimbo && <span className="ml-2 text-[var(--sb-texto-apagado)]">{VAZIOS.carimbo(carimbo)}</span>}
  </p>
)}
```
**Substituir exatamente este trecho** por (única mudança: `feedNaoCarregou` vira chamada de função com `url.dia`):
```tsx
{erro && (
  <p className="my-2 text-[14px]" role="status">
    {VAZIOS.feedNaoCarregou(url.dia)} <button onClick={carregar} className="sb-foco underline">{VAZIOS.tentarDeNovo}</button>
    {carimbo && <span className="ml-2 text-[var(--sb-texto-apagado)]">{VAZIOS.carimbo(carimbo)}</span>}
  </p>
)}
```

Por fim, acrescentar `{url.dia === "ontem" && <ResumoDoDia resumo={resumoOntem} />}` logo abaixo de `<LigaChips .../>` no JSX.

`diaParaApi("ontem")` continua devolvendo `null` (não muda — só documenta que "ontem" agora tem fonte própria, via comentário atualizado: trocar `/** \`ontem\` vem de /ledger/dia (plano 3); ate la o feed mostra o vazio "sem fonte". */` por `/** "ontem" nao usa este mapeamento — Feed.tsx chama getLedgerDia direto (#256). */`).

- [ ] **Step 7: Rodar** — `npx tsc --noEmit`; `npx playwright test e2e/ontem.spec.ts`; `npm run lint:accents`.
- [ ] **Step 8: Commit** — `git add frontend/next/src/app/jogos/Feed.tsx frontend/next/src/lib/feedUrl.ts frontend/next/src/lib/copy.ts frontend/next/tests/unit/feedUrl.test.ts frontend/next/e2e/ontem.spec.ts frontend/next/e2e/fixtures/ledger-dia.json && git commit -m "feat(front): dia=ontem busca o ledger, nunca recomputa (#256)"`

---

### Task 23: `ResumoDoDia` — a frase de acerto no topo de "ontem"

**Files:**
- Create: `frontend/next/src/components/feed/ResumoDoDia.tsx`, `frontend/next/tests/unit/ResumoDoDia.test.tsx`
- Modify: `frontend/next/src/lib/copy.ts` (fase 0 — nova função `resumoDoDia`)

**Interfaces:**
- Produces: `<ResumoDoDia resumo={{ picks: number; acertos: number; jogos: number } | null} />`, `resumoDoDia(acertos: number, picks: number, jogos: number): string` em `lib/copy.ts`.

- [ ] **Step 1: Teste**

Acrescentar a `tests/unit/copy.test.ts`:
```ts
import { resumoDoDia } from "@/lib/copy";

describe("resumoDoDia (#256)", () => {
  it("frase de acerto agregado do dia", () => {
    expect(resumoDoDia(3, 4, 4)).toBe("Ontem: 3 de 4 picks acertaram em 4 jogos");
  });
});
```

`tests/unit/ResumoDoDia.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResumoDoDia } from "@/components/feed/ResumoDoDia";

describe("ResumoDoDia (#256, spec §4.5 — sem reais por pick em ontem)", () => {
  it("mostra acerto agregado do dia", () => {
    render(<ResumoDoDia resumo={{ picks: 4, acertos: 3, jogos: 4 }} />);
    expect(screen.getByText("Ontem: 3 de 4 picks acertaram em 4 jogos")).toBeInTheDocument();
  });
  it("sem picks contados, nao renderiza nada", () => {
    const { container } = render(<ResumoDoDia resumo={{ picks: 0, acertos: 0, jogos: 0 }} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("resumo nulo (ainda carregando), nao renderiza nada", () => {
    const { container } = render(<ResumoDoDia resumo={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

Em `src/lib/copy.ts`, acrescentar:
```ts
/** #256 — spec §4.5: sem reais por pick em "ontem", só a contagem de acerto. */
export function resumoDoDia(acertos: number, picks: number, jogos: number): string {
  return `Ontem: ${acertos} de ${picks} picks acertaram em ${jogos} jogos`;
}
```

`src/components/feed/ResumoDoDia.tsx`:
```tsx
import { resumoDoDia } from "@/lib/copy";

/** #256 — spec §4.5: sem reais por pick em "ontem" (extrato de aposta vira
 * painel de resultado); só a contagem de acerto. Dinheiro fica em /desempenho. */
export function ResumoDoDia({ resumo }: { resumo: { picks: number; acertos: number; jogos: number } | null }) {
  if (!resumo || resumo.picks === 0) return null;
  return (
    <p className="tnum my-2 text-[14px]" role="status">
      {resumoDoDia(resumo.acertos, resumo.picks, resumo.jogos)}
    </p>
  );
}
```

- [ ] **Step 3: Rodar e ver passar; conferir `lint:accents`.** — `npx vitest run tests/unit/copy.test.ts tests/unit/ResumoDoDia.test.tsx`
- [ ] **Step 4: Substituir o placeholder da Task 22 (se criado) e commitar** — `git add frontend/next/src/components/feed/ResumoDoDia.tsx frontend/next/src/lib/copy.ts frontend/next/tests/unit/ResumoDoDia.test.tsx frontend/next/tests/unit/copy.test.ts && git commit -m "feat(front): ResumoDoDia no topo de ontem (#256)"`

---

### Task 24: Confiança na liga usa dado real do ledger, não constante fixa

**Por quê.** `src/lib/confiancaLiga.ts` (plano 1, Task 13) tem `MEDIA_DAS_LIGAS = 0.58` como constante fixa "medida em 2026-09-15", e `Detalhe.tsx` (plano 1, Task 16) passa `margem={null}` e `nJogos={confianca?.nSamples ?? null}` — `nSamples` é o tamanho da amostra de TREINO do modelo ML, não "jogos medidos" pelo ledger que a spec (§4.3) descreve. Esta tarefa troca as duas fontes por `/ledger/agregado`, sem inventar um intervalo de confiança (decisão de projeto #4 — `margem` continua `null`, não há cálculo estatístico auditado para produzi-la).

**Files:**
- Create: `frontend/next/src/hooks/useMediaDasLigas.ts`, `frontend/next/tests/unit/useMediaDasLigas.test.ts`
- Modify: `frontend/next/src/lib/confiancaLiga.ts` (plano 1), `frontend/next/src/components/feed/LinhaConfianca.tsx` (idem), `frontend/next/src/components/detalhe/Detalhe.tsx` (idem)

**Interfaces:**
- Produces: `useMediaDasLigas(): number | null` (hook; `null` enquanto carrega ou se a chamada falhar — quem consome usa `?? 0.58` como piso documentado, nunca afirma "média das ligas" sem dado).
- Consumes: `getLedgerAgregado("temporada")` (Task 20).

- [ ] **Step 1: Teste do hook**

`tests/unit/useMediaDasLigas.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useMediaDasLigas } from "@/hooks/useMediaDasLigas";

afterEach(() => vi.unstubAllGlobals());

describe("useMediaDasLigas (#256)", () => {
  it("calcula acertos/picks do agregado da temporada", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({ ok: true, periodo: "temporada", acerto: { picks: 100, acertos: 59, jogos: 90 } }),
    }));
    const { result } = renderHook(() => useMediaDasLigas());
    await waitFor(() => expect(result.current).toBe(0.59));
  });
  it("falha ou sem picks: null, nunca 0 ou NaN", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const { result } = renderHook(() => useMediaDasLigas());
    await waitFor(() => expect(result.current).toBeNull());
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

`src/hooks/useMediaDasLigas.ts`:
```ts
"use client";
import { useEffect, useState } from "react";
import { getLedgerAgregado } from "@/lib/ledgerApi";

/** #256 — acerto medio de TODAS as ligas na temporada, do ledger (fonte
 * unica). `null` enquanto carrega ou se falhar — quem le decide o piso. */
export function useMediaDasLigas(): number | null {
  const [media, setMedia] = useState<number | null>(null);
  useEffect(() => {
    let vivo = true;
    getLedgerAgregado("temporada").then((r) => {
      if (!vivo || !r.ok) return;
      const { picks, acertos } = r.dados.acerto;
      if (picks > 0) setMedia(Number((acertos / picks).toFixed(4)));
    }).catch(() => {});
    return () => { vivo = false; };
  }, []);
  return media;
}
```

`src/lib/confiancaLiga.ts` (plano 1) é hoje, **por inteiro**:
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
**Substituir exatamente este trecho** por:
```ts
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
/** #254-b — os quatro estados do #250 viram uma frase de operador (spec §4.1). */
const PISO_SEM_DADO = 0.58; // #256: usado so enquanto /ledger/agregado nao respondeu
const FAIXA = 0.04;

export function fraseConfianca(c: LeagueConfidence | null, ligaNome: string, mediaDasLigas: number | null = null) {
  const media = mediaDasLigas ?? PISO_SEM_DADO;
  if (!c || c.level === "UNVERIFIED") return { texto: `${ligaNome}: confiança não verificada`, numero: null, semBase: true };
  if (c.level === "POISSON") return { texto: `${ligaNome}: modelo geral, sem histórico próprio`, numero: null, semBase: true };
  const n = c.nSamples ?? 0;
  if (c.level === "ML_SUPPRESSED" || c.accuracy == null || n < 20) {
    return { texto: `${ligaNome}: ${n} jogos medidos, ainda sem base`, numero: n, semBase: true };
  }
  const rel = c.accuracy - media;
  const onde = rel > FAIXA ? "acima da média" : rel < -FAIXA ? "abaixo da média" : "na média das ligas";
  return { texto: `${ligaNome}: ${n} jogos medidos, acerto ${onde}`, numero: n, semBase: false };
}
```
(única mudança de comportamento: `MEDIA_DAS_LIGAS` fixo vira `media`, resolvido do parâmetro com fallback a `PISO_SEM_DADO` — os testes do plano 1 em `tests/unit/linhas.test.tsx` chamam `fraseConfianca(conf({}), "MLS")` sem o terceiro argumento, então continuam recebendo `PISO_SEM_DADO = 0.58`, idêntico ao valor fixo de antes.)

`src/components/feed/LinhaConfianca.tsx` (plano 1, Task 13) é hoje, **por inteiro**:
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
**Substituir exatamente este trecho** por (única mudança: chama `useMediaDasLigas()` e repassa como terceiro argumento):
```tsx
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { fraseConfianca } from "@/lib/confiancaLiga";
import { useMediaDasLigas } from "@/hooks/useMediaDasLigas";

export function LinhaConfianca({ confianca, ligaNome }: { confianca: LeagueConfidence | null; ligaNome: string }) {
  const media = useMediaDasLigas();
  const f = fraseConfianca(confianca, ligaNome, media);
  if (f.semBase || f.numero == null) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{f.texto}</p>;
  const [antes, depois] = f.texto.split(String(f.numero));
  return (
    <p className="text-[13px]">
      {antes}<span className="tnum font-semibold text-[var(--sb-confianca)]">{f.numero}</span>{depois}
    </p>
  );
}
```

`src/components/detalhe/Detalhe.tsx` (plano 1, Task 16) é hoje, **por inteiro**:
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
Duas chamadas usam `confianca?.nSamples ?? null` (a `EscalaConfianca` e a `DeOndeVemONumero`) — as DUAS trocam para o dado do ledger. **Substituir exatamente este trecho** por:
```tsx
import { useEffect, useState } from "react";
import type { JogoView } from "@/lib/jogoView";
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { getLedgerAgregado } from "@/lib/ledgerApi";
import { Talao } from "@/components/feed/Talao";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { ComoOModeloVe } from "@/components/detalhe/ComoOModeloVe";
import { DeOndeVemONumero } from "@/components/detalhe/DeOndeVemONumero";
import { fmtDataCurta, fmtHora } from "@/lib/formato";

export function Detalhe({ jogo, confianca }: { jogo: JogoView; confianca: LeagueConfidence | null }) {
  const [nJogosLedger, setNJogosLedger] = useState<number | null>(null);
  useEffect(() => {
    let vivo = true;
    getLedgerAgregado("temporada", undefined, jogo.ligaId).then((r) => {
      if (vivo && r.ok) setNJogosLedger(r.dados.por_liga[jogo.ligaId]?.n_jogos ?? null);
    }).catch(() => {});
    return () => { vivo = false; };
  }, [jogo.ligaId]);

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
          <EscalaConfianca prob01={jogo.talao.prob01} margem={null} nJogos={nJogosLedger} liga={jogo.ligaNome} />
        </section>
      )}
      <section className="mt-6">
        <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Todos os mercados avaliados ({jogo.totalAvaliados})</h3>
        <div className="overflow-x-auto"><TabelaMercados mercados={jogo.mercados} /></div>
      </section>
      <ComoOModeloVe matchId={jogo.id} />
      <DeOndeVemONumero jogo={jogo} nJogos={nJogosLedger} />
    </div>
  );
}
```
**Nota:** `EscalaConfianca` só escreve `nJogos` no texto quando `margem` não é `null` (ver `EscalaConfianca.tsx`, plano 1: `margem && nJogos != null ? "... em X jogos medidos ..." : "... em cada 100 na LIGA"`). Como `margem` continua `null` aqui (decisão de projeto #4), `nJogos` chega correto em `EscalaConfianca` mas não aparece no texto dela hoje — só em `DeOndeVemONumero`, que sempre mostra `{nJogos} jogos medidos` quando não é nulo. O teste abaixo prova que as duas chamadas migraram do valor antigo (`confianca.nSamples`), não que as duas o EXIBEM (uma delas fica muda até `margem` deixar de ser `null`).

- [ ] **Step 3: Teste — as duas chamadas migraram, nenhuma mostra o valor antigo de treino ML**

Acrescentar a `tests/unit/detalhe.test.tsx` (plano 1):
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Detalhe } from "@/components/detalhe/Detalhe";
import type { JogoView, PickView } from "@/lib/jogoView";

afterEach(() => vi.unstubAllGlobals());

const p = (o: Partial<PickView>): PickView => ({ mercado: "x", prob01: 0.5, fairOdd: 2, bookOdd: 2.1, edge: 0.05, ev: 0.05, classification: "SAFE", motivo: "", vale: true, ...o });
const jogo: JogoView = {
  id: "j1", ligaId: "mls", ligaNome: "MLS", casa: "Toronto", fora: "Nashville SC", kickoffIso: "2026-09-09T23:30:00Z",
  estado: "vale", talao: p({}), segundo: null, direcao: null, mercados: [p({})], totalAvaliados: 1, totalValem: 1,
  aoVivo: null, resultado: null,
  origem: { golsCasa: null, golsFora: null, golsLiga: null, escanteiosCasa: null, escanteiosFora: null, escanteiosLiga: null },
};

describe("Detalhe usa nJogos do ledger nos dois lugares, nao mais o treino ML (#256)", () => {
  it("nenhuma das duas chamadas mostra confianca.nSamples (999); DeOndeVemONumero mostra o numero do ledger (40)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({
        ok: true, periodo: "temporada",
        por_liga: { mls: { picks: 12, acertos: 7, n_jogos: 40, resolvidos: 12, brier: 0.24 } },
      }),
    }));
    render(<Detalhe jogo={jogo} confianca={{ leagueId: "mls", level: "ML_ACTIVE", brier: 0.2, accuracy: 0.58, nSamples: 999, trainedAt: null }} />);
    await waitFor(() => expect(screen.getByText(/40 jogos medidos/)).toBeInTheDocument());
    expect(screen.queryByText(/999/)).toBeNull();
  });
});
```

- [ ] **Step 4: Rodar** — `npx vitest run tests/unit/useMediaDasLigas.test.ts tests/unit/linhas.test.tsx tests/unit/detalhe.test.tsx` (os dois últimos são do plano 1 — conferir que continuam verdes com a assinatura nova, que preserva o comportamento antigo via parâmetro opcional).
- [ ] **Step 5: Commit** — `git add frontend/next/src/hooks/useMediaDasLigas.ts frontend/next/src/lib/confiancaLiga.ts frontend/next/src/components/feed/LinhaConfianca.tsx frontend/next/src/components/detalhe/Detalhe.tsx frontend/next/tests/unit/useMediaDasLigas.test.ts frontend/next/tests/unit/detalhe.test.tsx && git commit -m "feat(front): media das ligas e jogos medidos vem do ledger, nao de constante/treino ML (#256)"`

---

### Task 25: `/desempenho`

**Nota sobre `acertos/jogos` (achado no code review deste plano).** `jogos` conta partidas distintas; `acertos` conta PICKS individuais corretos — mais de um pick pode acertar na mesma partida, então `acertos` pode superar `jogos` (medido em produção: `{"picks":73,"acertos":38,"jogos":37}`, 2026-09-16). `acertos / jogos` pode passar de 100% e não serve para "X de cada 100 picks". Esta tarefa usa `acerto.resolvidos` (Task 20-bis) como denominador — sempre ≥ `acertos`, por construção — e o mesmo vale para as colunas de acerto de `TabelaSegmentos` (`por_familia`/`por_liga`, que também têm `resolvidos` desde a Task 20-bis).

**Files:**
- Create: `frontend/next/src/lib/desempenhoUrl.ts`, `frontend/next/src/components/desempenho/TabelaSegmentos.tsx`, `frontend/next/src/components/desempenho/GraficoCalibracao.tsx`, `frontend/next/src/app/desempenho/page.tsx`, `frontend/next/src/app/desempenho/Painel.tsx`, `frontend/next/tests/unit/desempenhoUrl.test.ts`, `frontend/next/tests/unit/GraficoCalibracao.test.tsx`, `frontend/next/e2e/desempenho.spec.ts`, `frontend/next/e2e/fixtures/ledger-agregado.json`
- Modify: `frontend/next/src/lib/copy.ts` (fase 0 — `DESEMPENHO` e `fraseAcerto`)

**Interfaces:**
- Consumes: `getLedgerAgregado` (Task 20), `ACTIVE_LEAGUES` (`lib/leagues.ts`), `fmtPct`, `fmtReais` (`lib/formato.ts`).
- Produces: `lerDesempenhoUrl(params): DesempenhoUrl`, `escreverDesempenhoUrl(e): string`, `periodoPorExtenso(periodo, hoje): string`, `fraseAcerto(acertos, resolvidos, jogos): string` e `DESEMPENHO` (objeto de rótulos, ambos em `lib/copy.ts`).

- [ ] **Step 1: Teste de `desempenhoUrl.ts`**

`tests/unit/desempenhoUrl.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { lerDesempenhoUrl, escreverDesempenhoUrl, periodoPorExtenso } from "@/lib/desempenhoUrl";

describe("estado de /desempenho na URL (spec §5)", () => {
  it("padrao: 30d, sem familia/liga", () => {
    expect(lerDesempenhoUrl(new URLSearchParams(""))).toEqual({ periodo: "30d", familia: null, liga: null });
  });
  it("le e escreve os tres parametros", () => {
    const e = lerDesempenhoUrl(new URLSearchParams("periodo=7d&familia=Corners&liga=mls"));
    expect(e).toEqual({ periodo: "7d", familia: "Corners", liga: "mls" });
    expect(escreverDesempenhoUrl(e)).toBe("/desempenho?periodo=7d&familia=Corners&liga=mls");
  });
  it("periodo invalido cai no padrao", () => {
    expect(lerDesempenhoUrl(new URLSearchParams("periodo=1ano")).periodo).toBe("30d");
  });
  it("periodo por extenso — o operador nao confia em palavra magica (spec §5)", () => {
    expect(periodoPorExtenso("temporada", new Date("2026-09-16"))).toBe("03/09\u2013hoje");
    expect(periodoPorExtenso("7d", new Date("2026-09-16T12:00:00Z"))).toBe("09/09\u2013hoje");
    expect(periodoPorExtenso("30d", new Date("2026-09-16T12:00:00Z"))).toBe("17/08\u2013hoje");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

`src/lib/desempenhoUrl.ts`:
```ts
export type Periodo = "7d" | "30d" | "temporada";
export interface DesempenhoUrl { periodo: Periodo; familia: string | null; liga: string | null }
const PERIODOS: Periodo[] = ["7d", "30d", "temporada"];

export function lerDesempenhoUrl(params: URLSearchParams): DesempenhoUrl {
  const periodo = params.get("periodo");
  return {
    periodo: PERIODOS.includes(periodo as Periodo) ? (periodo as Periodo) : "30d",
    familia: params.get("familia") || null,
    liga: params.get("liga") || null,
  };
}

export function escreverDesempenhoUrl(e: DesempenhoUrl): string {
  const p = new URLSearchParams();
  if (e.periodo !== "30d") p.set("periodo", e.periodo);
  if (e.familia) p.set("familia", e.familia);
  if (e.liga) p.set("liga", e.liga);
  const q = p.toString();
  return q ? `/desempenho?${q}` : "/desempenho";
}

const _2DIG = (n: number) => String(n).padStart(2, "0");

/** Texto por extenso do periodo ativo (spec §5): "03/09–hoje" em vez de
 * confiar no rotulo do segmento. `hoje` e injetado — nunca le o relogio. */
export function periodoPorExtenso(periodo: Periodo, hoje: Date): string {
  if (periodo === "temporada") return "03/09\u2013hoje";
  const dias = periodo === "7d" ? 7 : 30;
  const inicio = new Date(hoje.getTime() - dias * 86_400_000);
  return `${_2DIG(inicio.getUTCDate())}/${_2DIG(inicio.getUTCMonth() + 1)}\u2013hoje`;
}
```

- [ ] **Step 3: Rodar e ver passar** — `npx vitest run tests/unit/desempenhoUrl.test.ts`.

- [ ] **Step 4: Teste do gráfico de calibração**

`tests/unit/GraficoCalibracao.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraficoCalibracao } from "@/components/desempenho/GraficoCalibracao";

describe("GraficoCalibracao (spec §5 — unico visual da tela, leitura em uma frase)", () => {
  it("amostra curta: buckets nulo", () => {
    render(<GraficoCalibracao buckets={null} />);
    expect(screen.getByText("amostra curta")).toBeInTheDocument();
  });
  it("desenha os pontos com n>0 e a frase do maior desvio; tabela sr-only com todos", () => {
    render(<GraficoCalibracao buckets={[
      { prob_media: 0.55, freq_real: 0.60, n: 30 },
      { prob_media: null, freq_real: null, n: 0 },
      { prob_media: 0.82, freq_real: 0.60, n: 22 },
    ]} />);
    const fig = screen.getByRole("img");
    expect(fig.getAttribute("aria-label")).toContain("quando o painel disse 82");
    expect(fig.getAttribute("aria-label")).toContain("aconteceu 60 em cada 100");
    expect(screen.getAllByRole("row")).toHaveLength(3); // cabecalho + 2 pontos com n>0
  });
});
```

- [ ] **Step 5: Rodar e ver falhar; implementar os componentes**

`src/components/desempenho/GraficoCalibracao.tsx`:
```tsx
import type { LedgerBucket } from "@/lib/ledgerApi";
import { fmtPct } from "@/lib/formato";

/** Dispersao pt-BR: eixo x = probabilidade dita, eixo y = frequencia real,
 * diagonal tracejada = calibracao perfeita. Sem biblioteca de grafico — SVG
 * puro, mesmo espirito de EscalaConfianca.tsx (plano 1). */
export function GraficoCalibracao({ buckets }: { buckets: LedgerBucket[] | null }) {
  if (!buckets) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">amostra curta</p>;
  const pontos = buckets.filter(
    (b): b is { prob_media: number; freq_real: number; n: number } => b.n > 0 && b.prob_media != null && b.freq_real != null,
  );
  if (pontos.length === 0) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">amostra curta</p>;

  const W = 260, H = 260, PAD = 24;
  const x = (v: number) => PAD + v * (W - 2 * PAD);
  const y = (v: number) => H - PAD - v * (H - 2 * PAD);
  const pior = pontos.reduce((acc, b) => {
    const d = Math.abs(b.prob_media - b.freq_real);
    return d > acc.d ? { b, d } : acc;
  }, { b: pontos[0], d: -1 });
  const frase = `quando o painel disse ${fmtPct(pior.b.prob_media)}, aconteceu ${fmtPct(pior.b.freq_real)} em cada 100`;

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`Calibração: ${frase}`}>
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--sb-linha)" strokeDasharray="4 4" />
        {pontos.map((b) => (
          <circle key={b.prob_media} cx={x(b.prob_media)} cy={y(b.freq_real)}
            r={3 + Math.min(6, b.n / 10)} fill="var(--sb-confianca)" />
        ))}
      </svg>
      <figcaption className="mt-1 text-[14px]">{frase}</figcaption>
      <table className="sr-only">
        <caption>Calibração por faixa de probabilidade</caption>
        <thead><tr><th scope="col">probabilidade média</th><th scope="col">frequência real</th><th scope="col">jogos</th></tr></thead>
        <tbody>{pontos.map((b) => (
          <tr key={b.prob_media}><td>{fmtPct(b.prob_media)}</td><td>{fmtPct(b.freq_real)}</td><td>{b.n}</td></tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
```

`src/components/desempenho/TabelaSegmentos.tsx`:
```tsx
import type { LedgerSegmento } from "@/lib/ledgerApi";
import { fmtPct } from "@/lib/formato";

/** #256 — coluna "acerto" usa `resolvidos` (picks individuais com desfecho),
 * NUNCA `n_jogos` (partidas distintas) — o mesmo motivo do `acerto` de topo
 * de `Painel.tsx`: mais de um pick pode acertar na mesma partida, e
 * `acertos/n_jogos` pode passar de 100%. */
export function TabelaSegmentos({ titulo, linhas }: { titulo: string; linhas: Record<string, LedgerSegmento> }) {
  const entradas = Object.entries(linhas).filter(([, s]) => s.picks > 0);
  if (entradas.length === 0) return null;
  return (
    <table className="w-full text-[14px]">
      <caption className="mb-1 text-left font-[family-name:var(--font-slab)] text-[18px] font-semibold">{titulo}</caption>
      <thead><tr className="text-left text-[13px] text-[var(--sb-texto-apagado)]">
        <th scope="col" className="py-1 font-normal">nome</th>
        <th scope="col" className="py-1 text-right font-normal">picks</th>
        <th scope="col" className="py-1 text-right font-normal">acerto</th>
        <th scope="col" className="py-1 text-right font-normal">Brier (menor é melhor)</th>
      </tr></thead>
      <tbody>{entradas.map(([nome, s]) => (
        <tr key={nome} className="border-t border-[var(--sb-linha)]">
          <td className="py-2">{nome}</td>
          <td className="tnum py-2 text-right">{s.picks}</td>
          <td className="tnum py-2 text-right">{s.resolvidos > 0 ? `${fmtPct(s.acertos / s.resolvidos)}%` : "amostra curta"}</td>
          <td className="tnum py-2 text-right">{s.brier != null ? s.brier.toFixed(4) : "amostra curta"}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}
```

- [ ] **Step 6: Rodar e ver passar** — `npx vitest run tests/unit/GraficoCalibracao.test.tsx`.

- [ ] **Step 7: `copy.ts` — rótulos e a frase de acerto (denominador `resolvidos`)**

Acrescentar a `tests/unit/copy.test.ts`:
```ts
import { fraseAcerto, DESEMPENHO } from "@/lib/copy";

describe("fraseAcerto (#256) — denominador e resolvidos, nunca jogos", () => {
  it("38 acertos em 60 resolvidos, 37 jogos: 63 de cada 100", () => {
    expect(fraseAcerto(38, 60, 37)).toBe("63 de cada 100 picks fechados · 37 jogos");
  });
  it("resolvidos zero nunca divide — chamada defensiva, mesmo que o chamador ja proteja", () => {
    expect(fraseAcerto(0, 0, 0)).toBe("0 de cada 100 picks fechados · 0 jogos");
  });
});

describe("DESEMPENHO (#256) — rotulos centralizados", () => {
  it("tem os titulos e mensagens da tela", () => {
    expect(DESEMPENHO.tituloAcerto).toBe("Acerto");
    expect(DESEMPENHO.tituloRetorno).toBe("Na sua banca atual");
    expect(DESEMPENHO.tituloCalibracao).toBe("Calibração");
    expect(DESEMPENHO.semPicksFechados).toBe("sem picks fechados neste período");
    expect(DESEMPENHO.retornoIndisponivel).toBe("retorno em dinheiro ainda não disponível — o stake de cada pick não é gravado no ledger");
  });
});
```

Em `src/lib/copy.ts`, acrescentar:
```ts
/** #256 — "de cada 100 picks FECHADOS" (resolvidos), nunca "jogos": jogos
 * conta partidas distintas e pode ser MENOR que acertos quando mais de um
 * pick acerta na mesma partida (medido em produção: 38 acertos, 37 jogos).
 * `resolvidos` e sempre >= acertos, por construcao — nunca passa de 100%. */
export function fraseAcerto(acertos: number, resolvidos: number, jogos: number): string {
  const pct = resolvidos > 0 ? fmtPct(acertos / resolvidos) : 0;
  return `${pct} de cada 100 picks fechados · ${jogos} jogos`;
}

export const DESEMPENHO = {
  tituloAcerto: "Acerto",
  tituloRetorno: "Na sua banca atual",
  tituloCalibracao: "Calibração",
  semPicksFechados: "sem picks fechados neste período",
  retornoIndisponivel: "retorno em dinheiro ainda não disponível — o stake de cada pick não é gravado no ledger",
};
```

Rodar e ver passar: `npx vitest run tests/unit/copy.test.ts`; `npm run lint:accents`.

- [ ] **Step 8: Fixture, E2E e a página**

`e2e/fixtures/ledger-agregado.json` — aritmética conferida à mão (comentário fora do JSON, o arquivo real não leva comentário):
- `acerto`: `picks=73` (todos SAFE/NQ contados), `resolvidos=60` (picks com desfecho — inclui os 13 ainda sem desfecho: `73−60=13`), `acertos=38` (⊆ `resolvidos`, `38≤60` ✓), `jogos=37` (partidas distintas entre os 60 resolvidos — plausível: alguns jogos tiveram 2 picks resolvidos). `38/60 = 0,6333…` → `fmtPct` arredonda para **63**.
- `por_familia.Over/Under`: `picks=34`, `resolvidos=28` (`≤34` ✓), `acertos=22` (`≤28` ✓), `n_jogos=26` (`≤28` ✓, quase todos os jogos com só 1 pick resolvido). `22/28 = 0,7857` → 79%.
- `por_liga.mls`: `picks=12`, `resolvidos=11` (`≤12` ✓), `acertos=7` (`≤11` ✓), `n_jogos=10` (`≤11` ✓). `7/11 = 0,6364` → 64%.
- `buckets`: cada `n` é uma contagem de PICKS resolvidos (não de jogos) — a soma tem que bater com `acerto.resolvidos` (60), não com `jogos` (37): `35 + 25 = 60`.
```json
{
  "ok": true, "periodo": "30d", "familia": null, "liga": null,
  "acerto": { "picks": 73, "acertos": 38, "jogos": 37, "resolvidos": 60 },
  "retorno": { "valor": null, "pct_banca": null, "motivo": "stake_nao_gravado_no_ledger" },
  "brier": 0.2529, "amostra_curta": false,
  "por_familia": { "Over/Under": { "picks": 34, "acertos": 22, "n_jogos": 26, "resolvidos": 28, "brier": 0.2183 } },
  "por_liga": { "mls": { "picks": 12, "acertos": 7, "n_jogos": 10, "resolvidos": 11, "brier": 0.24 } },
  "buckets": [
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": 0.55, "freq_real": 0.58, "n": 35 },
    { "prob_media": 0.63, "freq_real": 0.60, "n": 25 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 },
    { "prob_media": null, "freq_real": null, "n": 0 }
  ]
}
```

`e2e/desempenho.spec.ts`:
```ts
import { test, expect } from "@playwright/test";
import agregado from "./fixtures/ledger-agregado.json";

test.describe("/desempenho (#256, spec §5)", () => {
  test("acerto, retorno honesto (null), por familia, calibracao, por liga", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    await page.goto("/desempenho");
    await expect(page.getByText("63 de cada 100 picks fechados")).toBeVisible(); // 38 acertos / 60 resolvidos
    await expect(page.getByText(/ainda não/)).toBeVisible(); // retorno null, sem numero inventado
    await expect(page.getByText("Over/Under")).toBeVisible();
    await expect(page.getByRole("img", { name: /Calibração/ })).toBeVisible();
    await expect(page.getByText(/17\/08\u2013hoje/)).toBeVisible();
  });
  test("filtro de periodo escreve na URL", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
    await page.goto("/desempenho");
    await page.getByRole("tab", { name: "7 dias" }).click();
    await expect(page).toHaveURL(/periodo=7d/);
  });
  test("sem picks fechados no periodo: mensagem e link para periodo maior", async ({ page }) => {
    await page.route("**/api/ledger/agregado**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...agregado, acerto: { picks: 0, acertos: 0, jogos: 0, resolvidos: 0 }, buckets: null, brier: null, amostra_curta: true, por_familia: {}, por_liga: {} }) }));
    await page.goto("/desempenho?periodo=7d");
    await expect(page.getByText("sem picks fechados neste período")).toBeVisible();
    await expect(page.getByRole("link", { name: /30 dias|temporada/ })).toBeVisible();
  });
});
```

`src/app/desempenho/Painel.tsx` (client):
```tsx
"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getLedgerAgregado, type LedgerAgregado } from "@/lib/ledgerApi";
import { lerDesempenhoUrl, escreverDesempenhoUrl, periodoPorExtenso, type Periodo } from "@/lib/desempenhoUrl";
import { ACTIVE_LEAGUES } from "@/lib/leagues";
import { fmtPct, fmtReais } from "@/lib/formato";
import { fraseAcerto, DESEMPENHO } from "@/lib/copy";
import { TabelaSegmentos } from "@/components/desempenho/TabelaSegmentos";
import { GraficoCalibracao } from "@/components/desempenho/GraficoCalibracao";

const ROTULO: Record<Periodo, string> = { "7d": "7 dias", "30d": "30 dias", temporada: "Temporada" };

export function Painel() {
  const router = useRouter();
  const params = useSearchParams();
  const url = useMemo(() => lerDesempenhoUrl(params), [params]);
  const [dados, setDados] = useState<LedgerAgregado | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    let vivo = true;
    getLedgerAgregado(url.periodo, url.familia ?? undefined, url.liga ?? undefined).then((r) => {
      if (!vivo) return;
      if (!r.ok) { setErro(true); return; }
      setErro(false); setDados(r.dados);
    });
    return () => { vivo = false; };
  }, [url.periodo, url.familia, url.liga]);

  const ir = (mudanca: Partial<typeof url>) => router.push(escreverDesempenhoUrl({ ...url, ...mudanca }));

  if (erro) return <p className="p-4 text-[14px]">Os dados de desempenho não carregaram.</p>;
  if (!dados) return null;

  // #256: nunca dividir por resolvidos == 0 — jogos == 0 implica resolvidos
  // == 0 (jogos so existe entre picks resolvidos), checar resolvidos e o
  // mais direto (a condicao que a divisao de fraseAcerto depende).
  const semPicksFechados = dados.acerto.resolvidos === 0;

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 text-[var(--sb-texto)]">
      <h1 className="font-[family-name:var(--font-slab)] text-[28px] font-bold">Desempenho</h1>
      <div role="tablist" aria-label="período" className="mt-3 flex gap-1 border-b border-[var(--sb-linha)]">
        {(["7d", "30d", "temporada"] as Periodo[]).map((p) => (
          <button key={p} role="tab" aria-selected={p === url.periodo} onClick={() => ir({ periodo: p })}
            className="sb-foco px-3 py-2 text-[14px] aria-selected:border-b-2 aria-selected:border-[var(--sb-texto)] aria-selected:font-semibold">
            {ROTULO[p]}
          </button>
        ))}
        <span className="tnum ml-2 self-center text-[13px] text-[var(--sb-texto-apagado)]">
          {periodoPorExtenso(url.periodo, new Date())}
        </span>
      </div>

      {semPicksFechados ? (
        <p className="my-6 text-[14px] text-[var(--sb-texto-apagado)]">
          {DESEMPENHO.semPicksFechados} —{" "}
          <button className="sb-foco underline" onClick={() => ir({ periodo: url.periodo === "7d" ? "30d" : "temporada" })}>
            ver {url.periodo === "7d" ? "30 dias" : "a temporada"}
          </button>
        </p>
      ) : (
        <>
          <section className="mt-6">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloAcerto}</h2>
            <p className="tnum text-[16px]">{fraseAcerto(dados.acerto.acertos, dados.acerto.resolvidos, dados.acerto.jogos)}</p>
          </section>

          <section className="mt-4">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloRetorno}</h2>
            {dados.retorno.valor == null ? (
              <p className="text-[14px] text-[var(--sb-texto-apagado)]">{DESEMPENHO.retornoIndisponivel}</p>
            ) : (
              <p className="tnum text-[16px]">{fmtReais(dados.retorno.valor)} ({fmtPct(dados.retorno.pct_banca ?? 0)}%)</p>
            )}
          </section>

          <section className="mt-6"><TabelaSegmentos titulo="Por família" linhas={dados.por_familia} /></section>

          <section className="mt-6">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloCalibracao}</h2>
            <GraficoCalibracao buckets={dados.buckets} />
          </section>

          <section className="mt-6">
            <TabelaSegmentos titulo="Por liga" linhas={dados.por_liga} />
          </section>
        </>
      )}

      <div className="mt-6 flex flex-wrap gap-2 text-[13px]">
        {ACTIVE_LEAGUES().map((l) => (
          <button key={l.id} aria-pressed={url.liga === l.id} onClick={() => ir({ liga: url.liga === l.id ? null : l.id })}
            className="sb-foco rounded-full border border-[var(--sb-linha)] px-3 py-1 aria-pressed:border-[var(--sb-texto)]">
            {l.name}
          </button>
        ))}
      </div>
    </div>
  );
}
```

`src/app/desempenho/page.tsx`:
```tsx
import { Suspense } from "react";
import { Painel } from "./Painel";
export const metadata = { title: "Desempenho — SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-screen bg-[var(--sb-tinta)]"><Suspense><Painel /></Suspense></main>;
}
```

- [ ] **Step 9: Rodar** — `npx tsc --noEmit`; `npx playwright test e2e/desempenho.spec.ts`; `npm run lint:accents`.
- [ ] **Step 10: Commit** — `git add frontend/next/src/lib/desempenhoUrl.ts frontend/next/src/lib/copy.ts frontend/next/src/components/desempenho frontend/next/src/app/desempenho frontend/next/tests/unit/desempenhoUrl.test.ts frontend/next/tests/unit/copy.test.ts frontend/next/tests/unit/GraficoCalibracao.test.tsx frontend/next/e2e/desempenho.spec.ts frontend/next/e2e/fixtures/ledger-agregado.json && git commit -m "feat(front): /desempenho a partir do ledger, retorno honesto quando null, resolvidos como denominador (#256)"`

---

### Task 26: axe em `/jogos?dia=ontem` e `/desempenho`

**Files:**
- Modify: `frontend/next/e2e/a11y.spec.ts` (criado no plano 1, Task 18)

- [ ] **Step 1:** Acrescentar `/jogos?dia=ontem` (com o stub de `e2e/ontem.spec.ts`) e `/desempenho` (com o stub de `e2e/desempenho.spec.ts`) ao laço `for (const rota of [...])` do arquivo — mesma estrutura, sem duplicar o `AxeBuilder`.
- [ ] **Step 2:** Rodar `npx playwright test e2e/a11y.spec.ts`; corrigir qualquer violação `serious`/`critical` antes de prosseguir (não abafar).
- [ ] **Step 3:** Commit — `git add frontend/next/e2e/a11y.spec.ts && git commit -m "test(front): axe em ontem e desempenho (#256)"`

---

### Task 27: Fechar a fase 4

- [ ] **Step 1:** Suíte completa: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test`, mais `python -m pytest -q -o addopts=""` (Task 20-bis toca `backend/`). Expected: verde.
- [ ] **Step 2:** Entrada `## 256 — Reformulação do frontend, fase 4: ontem no feed e /desempenho` em `docs/REGISTRO_CORRECOES.md`, formato do CLAUDE.md:
  - **Problema:** `toJogoView` nunca produzia o estado `ontem` (só `ontem_sem_desfecho`); não havia tela de desempenho agregado honesta (as antigas liam `audit_results`, prognóstico recomputado); `acertos/jogos` podia passar de 100% (achado no code review deste plano — medido em produção: `picks=73, acertos=38, jogos=37`).
  - **Causa raiz:** nenhum consumidor do ledger existia no frontend antes desta fase; `jogos` (partidas distintas) nunca foi o denominador certo para "de cada 100 picks" porque mais de um pick pode acertar na mesma partida.
  - **Correções por camada:** `backend/services/ledger_leitura.py` (Task 20-bis — `resolvidos` em `_resumo`/`_segmento`/`agregado()`), `lib/ledgerApi.ts` (cliente), `lib/jogoViewOntem.ts` (mapeador puro; **colar aqui o percentual real medido no Step 5 da Task 21** — quantas linhas caíram no `default` de `formatarSelecaoLedger`, nas 2-3 datas medidas), `Feed.tsx` (liga "ontem" ao ledger, nunca a `/fixtures`), `/desempenho` (retorno honesto quando `null`, `resolvidos` como denominador do acerto), `confiancaLiga`/`Detalhe` (dado real em vez de constante/treino ML).
  - **Contratos de saída (Etapa 2-bis):** campo novo `resolvidos` em `_resumo`/`_segmento`/`dia()`/`agregado()["acerto"|"por_familia"|"por_liga"]` (Task 20-bis) — aditivo, único consumidor é o frontend desta mesma fase; nenhuma rota nem script externo lê essas funções.
  - **Prova empírica:** placar de testes antes/depois (frontend `vitest`/`playwright` e backend `pytest`), percentual real de linhas no fallback de `formatarSelecaoLedger` (Task 21, Step 5).
  - **Acompanhamento fora do escopo:** se o fallback de `formatarSelecaoLedger` ficar acima de 10% mesmo depois de cobrir os `market` mais frequentes, abrir um plano à parte para o produtor (`prediction_ledger.linhas_do_bundle`) gravar `display_label` como coluna nova.
  - **Etapa 5:** não se aplica (não há laço de escrita em produção nesta fase — `resolvidos` é leitura, não escrita).
- [ ] **Step 3:** Linha em `docs/INDICE_REGRAS.md` após a última entrada da fase 3.
- [ ] **Step 4:** Espelhar os 4 docs para `c:\painel_apostas\sportsbank-pro\`, `git add -A frontend/next backend docs`, commit `docs: REGISTRO #256 fase 4`, `git push origin HEAD:main`, acompanhar o CI — **este push dispara o deploy da Lambda** (`deploy-lambda.yml`, o commit da Task 20-bis toca `backend/**`); conferir `curl -s https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/health` depois do deploy.
- [ ] **Step 5:** **Gate da fase:** aguardar o "ok" do dono antes de iniciar a fase 5.

---
## Fase 5 — Hero, redirect por cookie, `/glossario`, navegação final, links contextuais

Depende de: fase 3 (feed/talão pronto) e fase 4 (ledger no feed — o hero usa a frase de acerto do ledger).

### Task 25-bis: linha de dinheiro do /desempenho — retorno retroativo "na sua banca atual"

**Por quê.** O bloco de dinheiro de `/desempenho` (Task 25) hoje mostra sempre `DESEMPENHO.retornoIndisponivel` porque `retorno.valor` de `/ledger/agregado` é `null` — `stake` nunca foi gravado no ledger (Global Constraint da fase 4, `backend/services/ledger_leitura.py:314-315`) e este plano não muda o produtor (proibição 5, "não duplicar Kelly no backend"). Decisão do dono (Welligton, portão da fase 4), opção (a): calcular o retorno **no cliente**, aplicando a regra de stake de HOJE (`calcStake`, `frontend/next/src/lib/bancaStore.ts:59`) a cada pick FECHADO do período, usando os campos já publicados no ledger (`published_prob`, `book_odd`, `classification`, `outcome`) — nunca recalculando probabilidade nem Kelly no backend. O rótulo deixa claro que é retrospectivo ("na sua banca atual"), não uma promessa: o stake de ontem, se o operador tivesse banca definida e seguisse a régua atual, teria sido X.

**Files:**
- Modify: `backend/services/ledger_leitura.py`, `backend/routes/ledger.py`, `frontend/next/src/lib/ledgerApi.ts`, `frontend/next/src/lib/copy.ts`, `frontend/next/src/app/desempenho/Painel.tsx`, `frontend/next/e2e/helpers/stub.ts`, `frontend/next/e2e/desempenho.spec.ts`
- Create: `frontend/next/src/app/api/ledger/picks/route.ts`, `frontend/next/src/lib/retornoRetroativo.ts`, `tests/test_257_ledger_picks.py`, `frontend/next/tests/unit/retornoRetroativo.test.ts`, `frontend/next/e2e/fixtures/ledger-picks.json`, `frontend/next/e2e/fixtures/ledger-picks.README.md`

**Interfaces:**
- Consumes: `_janela_periodo`, `_buscar_janela`, `_PICKS_CONTADOS`, `_pick_json`, `classificar_familia`, `_FOLGA_PUBLICACAO_DIAS` (todos já existem em `backend/services/ledger_leitura.py`); `calcStake(prob01: number, odd: number, banca: number, classification?: string): number` e `useBanca(): [number | null, ...]` (`frontend/next/src/lib/bancaStore.ts`); `LedgerPick`, `ResultadoLedger<T>` (`lib/ledgerApi.ts`); `fmtReais`, `fmtPct` (`lib/formato.ts`); `DESEMPENHO` (`lib/copy.ts`, Task 25).
- Produces: `ledger_leitura.picks(periodo: str, familia: Optional[str] = None, liga: Optional[str] = None, hoje: Optional[datetime] = None) -> {periodo, familia, liga, picks: [...]}` (backend); `GET /ledger/picks?periodo=&familia=&liga=`; `getLedgerPicks(periodo, familia?, liga?): Promise<ResultadoLedger<LedgerPicks>>` e o tipo `LedgerPicks` (`lib/ledgerApi.ts`); `retornoRetroativo(picks: LedgerPick[], banca: number): { valor: number; pctBanca: number; n: number; semPreco: number }` (`lib/retornoRetroativo.ts`); `DESEMPENHO.definaBanca`, `DESEMPENHO.retornoNaBancaAtual`, `DESEMPENHO.retornoSemPicks` (`lib/copy.ts`) — usados só por `Painel.tsx` desta tarefa, nenhum outro consumidor.

**Contrato de saída (Etapa 2-bis).** Campo novo: nenhum campo de banco é escrito — `picks()` é leitura pura, mesma classe de `dia()`/`agregado()`. Consumidor externo do endpoint novo `GET /ledger/picks`: só o proxy `app/api/ledger/picks/route.ts` e `Painel.tsx` desta tarefa; nenhuma rota nem script fora deste plano lê `ledger_leitura.picks`.

- [ ] **Step 1: Teste do backend — `picks()` conta o mesmo que `agregado()["acerto"]["resolvidos"]`**

`tests/test_257_ledger_picks.py`:
```python
# -*- coding: utf-8 -*-
"""#257 — GET /ledger/picks: linhas individuais resolvidas do periodo, para o
/desempenho calcular o retorno retroativo no cliente (stake nunca gravado no
ledger). `picks()` usa a MESMA janela e o MESMO filtro de `agregado()`
(_janela_periodo, _buscar_janela, classificar_familia) — o teste principal
prova que as duas contagens batem nos mesmos dublês."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ledger_leitura as L
from tests.test_256_resolvidos import _Conn, _linha

_UTC = timezone.utc
client = TestClient(app)


def test_len_picks_bate_com_acerto_resolvidos_do_agregado(monkeypatch):
    linhas = []
    base = datetime(2026, 9, 10, 12, 0, tzinfo=_UTC)
    for i in range(25):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(
            f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < 15 else 0, detail={"total_goals": 3},
        ))
    for i in range(25, 30):  # 5 picks sem desfecho — nao entram em picks()
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
                              kickoff - timedelta(hours=2), kickoff, outcome=None))
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    hoje = datetime(2026, 9, 20, tzinfo=_UTC)
    agregado = L.agregado("temporada", hoje=hoje)
    picks = L.picks("temporada", hoje=hoje)
    assert len(picks["picks"]) == agregado["acerto"]["resolvidos"] == 25
    assert all(p["outcome"] is not None for p in picks["picks"])


def test_picks_filtra_por_familia_e_liga_como_agregado(monkeypatch):
    k = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, league_id="mls"),
        _linha("m2", "Corners", "Over 6.5", 0.58, 1.75, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, league_id="premier-league"),
    ]
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    hoje = datetime(2026, 9, 20, tzinfo=_UTC)
    r = L.picks("temporada", familia="Over/Under", hoje=hoje)
    assert len(r["picks"]) == 1
    assert r["picks"][0]["match_id"] == "m1"
    r2 = L.picks("temporada", liga="premier-league", hoje=hoje)
    assert len(r2["picks"]) == 1
    assert r2["picks"][0]["match_id"] == "m2"


def test_rota_ledger_picks_registrada_e_ok(monkeypatch):
    monkeypatch.setattr(L, "picks", lambda periodo, familia=None, liga=None: {
        "periodo": periodo, "familia": familia, "liga": liga, "picks": [],
    })
    r = client.get("/ledger/picks", params={"periodo": "7d"})
    assert r.status_code == 200
    assert r.json()["periodo"] == "7d"
    assert "/ledger/picks" in app.openapi()["paths"]


def test_rota_ledger_picks_periodo_invalido_400(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise ValueError(f"periodo invalido: {periodo!r}")
    monkeypatch.setattr(L, "picks", _falha)
    r = client.get("/ledger/picks", params={"periodo": "1ano"})
    assert r.status_code == 400
```

- [ ] **Step 2: Rodar e ver falhar** — `python -m pytest -q tests/test_257_ledger_picks.py`. Esperado: `AttributeError`/`ImportError` (`picks` não existe) e `404` na rota.

- [ ] **Step 3: Implementar `picks()` em `backend/services/ledger_leitura.py`**

Acrescentar após `agregado()` (fim do arquivo):
```python
def picks(periodo: str, familia: Optional[str] = None,
         liga: Optional[str] = None, hoje: Optional[datetime] = None
         ) -> Dict[str, Any]:
    """#257 — linhas individuais RESOLVIDAS do periodo, cruas (sem agregar),
    para o /desempenho calcular o retorno retroativo no cliente (stake nunca
    gravado no ledger — Global Constraint da fase 4). Mesma janela e mesmo
    filtro de `agregado()` — nao reimplementar a regra em paralelo
    (proibicao 5); teste `tests/test_257_ledger_picks.py` prova que
    `len(picks) == agregado()["acerto"]["resolvidos"]` nos mesmos dubles."""
    inicio, fim = _janela_periodo(periodo, hoje)
    linhas = _buscar_janela(inicio - timedelta(days=_FOLGA_PUBLICACAO_DIAS), fim)
    na_janela = [l for l in linhas
                 if l.get("kickoff_utc") is not None and inicio <= l["kickoff_utc"] < fim]

    contados = na_janela
    if liga:
        contados = [l for l in contados if l["league_id"] == liga]
    if familia:
        contados = [l for l in contados
                   if classificar_familia(l["market"], l["selection"]) == familia]

    resolvidos = [l for l in contados
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]

    return {
        "periodo": periodo, "familia": familia, "liga": liga,
        "picks": [_pick_json(l) for l in resolvidos],
    }
```

- [ ] **Step 4: Rota `GET /ledger/picks` em `backend/routes/ledger.py`**

Acrescentar após `ledger_agregado`:
```python
@router.get("/ledger/picks")
async def ledger_picks(
    periodo: str = Query("30d", description="7d|30d|temporada"),
    familia: Optional[str] = Query(None),
    liga: Optional[str] = Query(None),
):
    try:
        return ledger_leitura.picks(periodo, familia, liga)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")
```

Rodar: `python -m pytest -q tests/test_257_ledger_picks.py`. Esperado: verde (4 testes). Commit — `git add backend/services/ledger_leitura.py backend/routes/ledger.py tests/test_257_ledger_picks.py && git commit -m "feat(backend): GET /ledger/picks — linhas resolvidas do periodo, leitura pura (#257)"`

- [ ] **Step 5: Proxy Next `app/api/ledger/picks/route.ts`**

Mesmo padrão de `app/api/ledger/agregado/route.ts` (linha por linha):
```ts
import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #257 — proxy de `GET /ledger/picks` (Lambda). Mesmo padrao de
 * `api/ledger/agregado/route.ts`.
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function statusDoErro(kind?: string, message?: string): number {
  if (kind === "HTTP_ERROR") {
    const m = /^HTTP (\d+):/.exec(message ?? "");
    if (m) return Number(m[1]);
  }
  return 503;
}

export async function GET(request: Request) {
  if (!getBackendUrl()) {
    return Response.json(
      { ok: false, error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL não configurado" } },
      { status: 503 },
    );
  }

  const { searchParams } = new URL(request.url);
  const periodo = searchParams.get("periodo") ?? "30d";
  const params = new URLSearchParams({ periodo });
  const familia = searchParams.get("familia");
  const liga = searchParams.get("liga");
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);

  const result = await fetchBackend(`/ledger/picks?${params.toString()}`, { timeoutMs: 25_000 });
  if (!result.ok) {
    const status = statusDoErro(result.error?.kind, result.error?.message);
    console.error(`[ledger/picks] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`);
    return Response.json(
      {
        ok: false,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível carregar os picks do período.",
        },
      },
      { status },
    );
  }
  return Response.json({ ok: true, ...(result.data as Record<string, unknown>) });
}
```

- [ ] **Step 6: `lib/ledgerApi.ts` — `LedgerPicks` e `getLedgerPicks`**

Acrescentar a `tests/unit/ledgerApi.test.ts` (dentro do `describe("ledgerApi (#256)")` existente, mesmas funções `stubFetch`/`afterEach`):
```ts
it("getLedgerPicks: monta querystring e devolve os picks", async () => {
  stubFetch({
    ok: true, periodo: "30d", familia: null, liga: null,
    picks: [{ match_id: "m1", league_id: "mls", kickoff_utc: null, familia: "Over/Under",
             market: "Over/Under", selection: "Over 2.5", published_prob: 0.6, fair_odd: 1.67,
             book_odd: 1.8, classification: "SAFE", outcome: 1, detail: null }],
  });
  const r = await getLedgerPicks("30d");
  expect(r.ok).toBe(true);
  if (r.ok) expect(r.dados.picks).toHaveLength(1);
  const chamada = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
  expect(chamada).toContain("periodo=30d");
});
it("getLedgerPicks: erro estruturado vira 'erro'", async () => {
  stubFetch({ ok: false, error: { kind: "BACKEND_ERROR", message: "falha" } }, 503);
  const r = await getLedgerPicks("30d");
  expect(r.ok).toBe(false);
  if (r.ok === false) expect(r.erro.kind).toBe("BACKEND_ERROR");
});
```
(acrescentar `getLedgerPicks` ao `import` do topo do arquivo.)

Rodar e ver falhar (`getLedgerPicks` não existe); implementar em `src/lib/ledgerApi.ts`, logo após `LedgerAgregado`:
```ts
/** #257 — picks individuais RESOLVIDOS do período (sem agregar), para o
 * retorno retroativo em `lib/retornoRetroativo.ts`. */
export interface LedgerPicks {
  periodo: string;
  familia: string | null;
  liga: string | null;
  picks: LedgerPick[];
}

export function getLedgerPicks(
  periodo: "7d" | "30d" | "temporada",
  familia?: string,
  liga?: string,
): Promise<ResultadoLedger<LedgerPicks>> {
  const params = new URLSearchParams({ periodo });
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);
  return chamar<LedgerPicks>(`/api/ledger/picks?${params.toString()}`);
}
```

- [ ] **Step 7: Rodar e ver passar** — `npx vitest run tests/unit/ledgerApi.test.ts`. Commit — `git add frontend/next/src/lib/ledgerApi.ts frontend/next/src/app/api/ledger/picks frontend/next/tests/unit/ledgerApi.test.ts && git commit -m "feat(front): GET /api/ledger/picks + getLedgerPicks (#257)"`

- [ ] **Step 8: `lib/retornoRetroativo.ts` — cálculo puro do P&L retroativo**

`tests/unit/retornoRetroativo.test.ts` — fixture com dois picks calculados à mão, longe de fronteira de arredondamento:
```ts
import { describe, expect, it } from "vitest";
import { retornoRetroativo } from "@/lib/retornoRetroativo";
import type { LedgerPick } from "@/lib/ledgerApi";

function pick(p: Partial<LedgerPick>): LedgerPick {
  return {
    match_id: "m", league_id: "mls", kickoff_utc: null, familia: "Over/Under",
    market: "Over/Under", selection: "Over 2.5", published_prob: null, fair_odd: null,
    book_odd: null, classification: "SAFE", outcome: null, detail: null, ...p,
  };
}

describe("retornoRetroativo (#257) — aritmetica a mao, sem fronteira de arredondamento", () => {
  it("dois picks com preco (um paga stake>0, um cai a 0 pelo cap) + um sem preco", () => {
    const picks: LedgerPick[] = [
      // A: prob=0.55, odd=2.2, SAFE, outcome=1, banca=1000.
      //    b=1.2; kelly=(0.55*1.2-0.45)/1.2=(0.66-0.45)/1.2=0.175
      //    qk=0.175*0.25=0.04375 (< cap 0.05, nao bate no teto)
      //    stake=round(1000*0.04375*100)/100 = round(4375)/100 = 43.75
      //    P&L = stake*(odd-1) = 43.75*1.2 = 52.5
      pick({ match_id: "a", published_prob: 0.55, book_odd: 2.2, classification: "SAFE", outcome: 1 }),
      // B: prob=0.52, odd=1.9, NEUTRO_QUALIFICADO, outcome=0, banca=1000.
      //    b=0.9; kelly=(0.52*0.9-0.48)/0.9=(0.468-0.48)/0.9=-0.01333...
      //    qk=-0.01333*0.15=-0.002 -> capped a 0 (kelly negativo, sem floor NQ)
      //    stake=0 -> P&L=0 (ainda conta em n, tem preco)
      pick({ match_id: "b", published_prob: 0.52, book_odd: 1.9, classification: "NEUTRO_QUALIFICADO", outcome: 0 }),
      // C: sem book_odd — nunca precificado, nao entra no calculo de valor/n.
      pick({ match_id: "c", published_prob: 0.6, book_odd: null, classification: "SAFE", outcome: 1 }),
    ];
    const r = retornoRetroativo(picks, 1000);
    expect(r.valor).toBeCloseTo(52.5, 6);
    expect(r.pctBanca).toBeCloseTo(0.0525, 6);
    expect(r.n).toBe(2);
    expect(r.semPreco).toBe(1);
  });
  it("banca zero ou picks vazio: zero seguro, sem divisao por zero", () => {
    expect(retornoRetroativo([], 1000)).toEqual({ valor: 0, pctBanca: 0, n: 0, semPreco: 0 });
  });
});
```

- [ ] **Step 9: Rodar e ver falhar; implementar**

`src/lib/retornoRetroativo.ts`:
```ts
/** #257 — retorno retroativo: aplica a regra de stake de HOJE (`calcStake`,
 * Quarter Kelly — não duplicado, só chamado) a cada pick FECHADO do período,
 * usando os campos já publicados no ledger. Nunca recalcula probabilidade
 * nem Kelly no backend (proibição 5). `outcome` é `0|1` (nunca `null` aqui —
 * `lib/ledgerApi.ts::getLedgerPicks` só devolve picks resolvidos). */
import type { LedgerPick } from "@/lib/ledgerApi";
import { calcStake } from "@/lib/bancaStore";

export interface RetornoRetroativo {
  valor: number;
  pctBanca: number;
  n: number;
  semPreco: number;
}

export function retornoRetroativo(picks: LedgerPick[], banca: number): RetornoRetroativo {
  let valor = 0;
  let n = 0;
  let semPreco = 0;
  for (const p of picks) {
    if (p.book_odd == null || p.published_prob == null) {
      semPreco += 1;
      continue;
    }
    const stake = calcStake(p.published_prob, p.book_odd, banca, p.classification);
    valor += p.outcome ? stake * (p.book_odd - 1) : -stake;
    n += 1;
  }
  return { valor, pctBanca: banca > 0 ? valor / banca : 0, n, semPreco };
}
```

- [ ] **Step 10: Rodar e ver passar** — `npx vitest run tests/unit/retornoRetroativo.test.ts`. Commit — `git add frontend/next/src/lib/retornoRetroativo.ts frontend/next/tests/unit/retornoRetroativo.test.ts && git commit -m "feat(front): retornoRetroativo — P&L com o stake de hoje sobre picks fechados (#257)"`

- [ ] **Step 11: `copy.ts` — rótulos novos (`retornoIndisponivel` fica, só não é mais usado por `Painel.tsx`)**

Acrescentar a `tests/unit/copy.test.ts`:
```ts
describe("DESEMPENHO (#257) — retorno retroativo", () => {
  it("tem os rotulos novos do bloco de dinheiro", () => {
    expect(DESEMPENHO.definaBanca).toBe("defina sua banca para ver o retorno em dinheiro");
    expect(DESEMPENHO.retornoNaBancaAtual).toBe("seguindo o stake sugerido, na sua banca atual");
    expect(DESEMPENHO.retornoSemPicks).toBe("sem picks fechados com preço neste período");
  });
});
```
Em `src/lib/copy.ts`, dentro do objeto `DESEMPENHO` (acrescentar as três chaves, sem remover `retornoIndisponivel` — string órfã, inofensiva, documentada como tal no comentário):
```ts
export const DESEMPENHO = {
  tituloAcerto: "Acerto",
  tituloRetorno: "Na sua banca atual",
  tituloCalibracao: "Calibração",
  semPicksFechados: "sem picks fechados neste período",
  // #257: retornoIndisponivel fica sem uso em Painel.tsx a partir desta tarefa
  // (substituido pelo calculo retroativo) — nao removido para nao quebrar o
  // teste que a citava antes; nenhuma tela mais renderiza esta string.
  retornoIndisponivel: "retorno em dinheiro ainda não disponível — o stake de cada pick não é gravado no ledger",
  definaBanca: "defina sua banca para ver o retorno em dinheiro",
  retornoNaBancaAtual: "seguindo o stake sugerido, na sua banca atual",
  retornoSemPicks: "sem picks fechados com preço neste período",
};
```
Rodar: `npx vitest run tests/unit/copy.test.ts`; `npm run lint:accents`.

- [ ] **Step 12: `Painel.tsx` — bloco de dinheiro**

Trocar os imports do topo (`src/app/desempenho/Painel.tsx`) de:
```ts
import { useEffect, useMemo, useState } from "react";
```
para:
```ts
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useBanca } from "@/lib/bancaStore";
import { getLedgerPicks } from "@/lib/ledgerApi";
import { retornoRetroativo } from "@/lib/retornoRetroativo";
```
(mantém os demais imports já existentes da Task 25: `getLedgerAgregado`, `lerDesempenhoUrl`/`escreverDesempenhoUrl`/`periodoPorExtenso`, `ACTIVE_LEAGUES`, `fmtPct`/`fmtReais`, `fraseAcerto`/`DESEMPENHO`, `TabelaSegmentos`, `GraficoCalibracao`.)

Substituir a seção "Na sua banca atual" (Task 25, dentro de `<>...</>`) por um subcomponente novo, declarado no mesmo arquivo, acima de `Painel`:
```tsx
function BlocoRetorno({ periodo, familia, liga }: { periodo: Periodo; familia: string | null; liga: string | null }) {
  const [banca] = useBanca();
  const [retorno, setRetorno] = useState<{ valor: number; pctBanca: number; n: number } | null>(null);
  const [semPicks, setSemPicks] = useState(false);
  const geracao = useRef(0);

  useEffect(() => {
    if (banca == null) { setRetorno(null); setSemPicks(false); return; }
    const minha = ++geracao.current;
    getLedgerPicks(periodo, familia ?? undefined, liga ?? undefined).then((r) => {
      if (minha !== geracao.current) return;   // outra carga mais nova ja partiu (mesma guarda de Feed.tsx)
      if (!r.ok) { setRetorno(null); setSemPicks(false); return; }
      const calculo = retornoRetroativo(r.dados.picks, banca);
      if (calculo.n === 0) { setRetorno(null); setSemPicks(true); return; }
      setSemPicks(false);
      setRetorno(calculo);
    });
  }, [periodo, familia, liga, banca]);

  if (banca == null) {
    return (
      <p className="text-[14px] text-[var(--sb-texto-apagado)]">
        {DESEMPENHO.definaBanca}{" "}
        <Link href="/banca" className="sb-foco underline">definir banca</Link>
      </p>
    );
  }
  if (semPicks) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">{DESEMPENHO.retornoSemPicks}</p>;
  if (!retorno) return null;
  return (
    <p className="tnum text-[16px]">
      {fmtReais(retorno.valor)} ({fmtPct(retorno.pctBanca)}%) — {DESEMPENHO.retornoNaBancaAtual} ({retorno.n} picks com preço)
    </p>
  );
}
```
E, dentro de `Painel`, trocar o bloco:
```tsx
{dados.retorno.valor == null ? (
  <p className="text-[14px] text-[var(--sb-texto-apagado)]">{DESEMPENHO.retornoIndisponivel}</p>
) : (
  <p className="tnum text-[16px]">{fmtReais(dados.retorno.valor)} ({fmtPct(dados.retorno.pct_banca ?? 0)}%)</p>
)}
```
por:
```tsx
<BlocoRetorno periodo={url.periodo} familia={url.familia} liga={url.liga} />
```

- [ ] **Step 13: Rodar** — `npx tsc --noEmit`; `npm run lint:fonts`; `npm run lint:accents`.

- [ ] **Step 14: Fixture real e README de proveniência**

`ledger-agregado.README.md` (Task 25) documenta a captura real de 2026-09-16: 14 requisições `GET /ledger/dia?data=D` para D = 2026-09-03..2026-09-16 na Function URL de produção, das quais a união de `picks` filtrada por `classification ∈ {SAFE, NEUTRO_QUALIFICADO}` e `outcome != null` deu **78 linhas** (= `ledger-agregado.json.acerto.resolvidos`, conferido no arquivo). `ledger-picks.json` reusa a MESMA fonte, não uma nova captura:

1. Repetir as mesmas 14 requisições `GET https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/ledger/dia?data=D` (D = 2026-09-03..2026-09-16).
2. Unir os `picks` das 14 respostas, filtrar `classification ∈ {"SAFE", "NEUTRO_QUALIFICADO"}` e `outcome != null` — mesma regra de `ledger_leitura.picks()` (Step 3).
3. Gravar `frontend/next/e2e/fixtures/ledger-picks.json`:
```json
{ "ok": true, "periodo": "temporada", "familia": null, "liga": null, "picks": [ /* as 78 linhas, cada uma no formato LedgerPick — match_id, league_id, kickoff_utc, familia, market, selection, published_prob, fair_odd, book_odd, classification, outcome, detail */ ] }
```
4. Verificação de consistência obrigatória antes de commitar: `picks.length === 78` (bate com `ledger-agregado.json.acerto.resolvidos`, já conferido nesta tarefa) e todo `outcome` é `0` ou `1`, nunca `null`.

`frontend/next/e2e/fixtures/ledger-picks.README.md`:
```markdown
# `ledger-picks.json` — proveniência (Task 25-bis, #257)

**Mesma fonte de `ledger-agregado.json`** (ver `ledger-agregado.README.md`), não uma nova captura: união dos `picks` das 14 respostas `GET /ledger/dia?data=D` (D=2026-09-03..2026-09-16) da Function URL de produção, filtrada por `classification ∈ {SAFE, NEUTRO_QUALIFICADO}` e `outcome != null` — mesma regra de `ledger_leitura.picks()`.

`picks.length == 78`, igual a `ledger-agregado.json.acerto.resolvidos` — checagem cruzada obrigatória (as duas fixtures têm que concordar, senão os testes que comparam as duas telas ficam inconsistentes entre si).
```

- [ ] **Step 15: `e2e/helpers/stub.ts` — hermetizar o novo endpoint**

```ts
import ledgerPicks from "../fixtures/ledger-picks.json";
```
(acrescentar ao topo, junto dos outros imports de fixture) e, no corpo de `stub()`, após a rota `**/api/ledger/agregado**`:
```ts
// #257 — hermetiza qualquer tela que busque picks individuais (BlocoRetorno).
await page.route("**/api/ledger/picks**", (route) =>
  route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ledgerPicks) }));
```

- [ ] **Step 16: `e2e/desempenho.spec.ts` — teste do valor renderizado com banca fixa**

Seguindo o estilo já usado neste arquivo (cada teste estuba `**/api/ledger/agregado**` na mão, sem usar `stub()`), acrescentar um `page.route` dedicado para `**/api/ledger/picks**` com uma fixture pequena, calculada à mão (mesma aritmética do Step 8 — não a fixture real de 78 linhas, cujo P&L não é praticável de conferir à mão em um comentário):
```ts
test("retorno retroativo com banca definida", async ({ page, context }) => {
  await page.route("**/api/ledger/agregado**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
  // Mesmos dois picks e mesma conta do Step 8 (retornoRetroativo.test.ts):
  // A: prob 0.55, odd 2.2, SAFE, outcome 1, banca 1000 -> stake 43.75, P&L +52.5
  // B: prob 0.52, odd 1.9, NEUTRO_QUALIFICADO, outcome 0, banca 1000 -> stake 0, P&L 0
  // total valor = 52.5; pctBanca = 52.5/1000 = 0.0525 -> fmtPct = 5; fmtReais(52.5) = "R$ 52,50"
  await page.route("**/api/ledger/picks**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      ok: true, periodo: "30d", familia: null, liga: null,
      picks: [
        { match_id: "a", league_id: "mls", kickoff_utc: null, familia: "Over/Under", market: "Over/Under",
          selection: "Over 2.5", published_prob: 0.55, fair_odd: 1.82, book_odd: 2.2, classification: "SAFE", outcome: 1, detail: null },
        { match_id: "b", league_id: "mls", kickoff_utc: null, familia: "Over/Under", market: "Over/Under",
          selection: "Over 1.5", published_prob: 0.52, fair_odd: 1.92, book_odd: 1.9, classification: "NEUTRO_QUALIFICADO", outcome: 0, detail: null },
      ],
    }) }));
  await context.addInitScript(() => window.localStorage.setItem("sportsbankzu-bankroll", "1000"));
  await page.goto("/desempenho");
  await expect(page.getByText("R$ 52,50")).toBeVisible();
  await expect(page.getByText(/5%/)).toBeVisible();
  await expect(page.getByText(DESEMPENHO_RETORNO_NA_BANCA)).toBeVisible();
});
test("sem banca definida: link honesto para /banca, nenhum numero inventado", async ({ page, context }) => {
  await context.clearCookies();
  await page.route("**/api/ledger/agregado**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(agregado) }));
  await page.route("**/api/ledger/picks**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, periodo: "30d", familia: null, liga: null, picks: [] }) }));
  await page.goto("/desempenho");
  await expect(page.getByRole("link", { name: "definir banca" })).toBeVisible();
});
```
No topo do arquivo, junto do import de `agregado`, acrescentar a constante usada acima (string literal, não vinda de `@/lib/copy` — e2e não importa módulo de app):
```ts
const DESEMPENHO_RETORNO_NA_BANCA = "seguindo o stake sugerido, na sua banca atual";
```
Rodar: `npx playwright test e2e/desempenho.spec.ts`.

- [ ] **Step 17: Screenshots para o dono (nota visual)** — `/desempenho` não é referência visual do design (Global Constraint da fase 3), mas toda tarefa de UI traz diff visual no relatório: capturar print do bloco "Na sua banca atual" nos três estados (banca indefinida, com retorno, sem picks com preço) e anexar ao relatório de code review desta tarefa.

- [ ] **Step 18: Commit** — `git add frontend/next/src/app/desempenho/Painel.tsx frontend/next/src/lib/copy.ts frontend/next/tests/unit/copy.test.ts frontend/next/e2e/helpers/stub.ts frontend/next/e2e/desempenho.spec.ts frontend/next/e2e/fixtures/ledger-picks.json frontend/next/e2e/fixtures/ledger-picks.README.md && git commit -m "feat(front): retorno retroativo na banca atual em /desempenho, honesto quando sem banca/picks (#257)"`

---

### Task 28: `components/marca/Hero.tsx` + `app/page.tsx`

**Por quê.** `src/app/page.tsx` hoje faz `redirect("/dashboard")` (morto — o middleware intercepta antes, ver Task 29). A spec (§5) pede: headline em duas linhas (Slab/Barlow — linguagem A), frase de acerto vinda do ledger (some se `n < 20`), CTA "Ver os jogos de hoje" + "Entrar · Criar conta", e um talão real como prova (o de maior edge hoje; sem pick válido hoje, o de ontem com a faixa de resultado; sem nenhum, o slot some).

**Files:**
- Create: `frontend/next/src/components/marca/Hero.tsx`, `frontend/next/tests/unit/Hero.test.tsx`
- Modify: `frontend/next/src/app/page.tsx`

**Interfaces:**
- Consumes: `getLedgerAgregado("30d")` (Task 20), `getMatchesByLeague` + `normalizeMatch` + `deduplicateMatches` + `toJogoView` (fase 2/3, para o talão de hoje), `ACTIVE_LEAGUES`, `fonteMarca` (`components/marca/fonteMarca.ts`, fase 0), `Talao` (fase 3).
- Produces: `<Hero />`, `fraseAcertoHero(acerto01: number, jogos: number, minimoJogos: number): string | null` (em `lib/copy.ts` — `null` quando `jogos < minimoJogos`, chamado com `minimoJogos=20`, mesmo piso `MIN_N_BRIER` do backend, spec §5 "some se n < 20 jogos"), `HERO` (objeto de rótulos: headline e os dois CTAs, também em `lib/copy.ts`).

- [ ] **Step 1: Teste de `fraseAcertoHero` (puro, em `copy.ts`)**

Acrescentar a `tests/unit/copy.test.ts`:
```ts
import { fraseAcertoHero, HERO } from "@/lib/copy";

describe("fraseAcertoHero (#257, spec §5)", () => {
  it("com amostra suficiente", () => {
    expect(fraseAcertoHero(0.58, 221, 20)).toBe("nos últimos 30 dias: 58 de cada 100 picks acertaram em 221 jogos");
  });
  it("abaixo do piso MIN_N_BRIER=20, nulo", () => {
    expect(fraseAcertoHero(0.5, 10, 19)).toBeNull();
  });
});

describe("HERO (#257) — headline e CTAs centralizados", () => {
  it("tem as duas linhas do headline e os dois CTAs", () => {
    expect(HERO.headlineLinha1).toBe("O veredito em primeiro plano.");
    expect(HERO.headlineLinha2).toBe("O rigor um nível abaixo.");
    expect(HERO.ctaJogos).toBe("Ver os jogos de hoje");
    expect(HERO.ctaEntrar).toBe("Entrar · Criar conta");
  });
});
```
Implementar em `src/lib/copy.ts`:
```ts
/** #257 — frase de prova do hero (spec §5). Mesmo piso do backend (MIN_N_BRIER=20,
 * proibição 8) — abaixo dele a frase some em vez de afirmar sobre amostra curta. */
export function fraseAcertoHero(acerto01: number, jogos: number, minimoJogos: number): string | null {
  if (jogos < minimoJogos) return null;
  return `nos últimos 30 dias: ${fmtPct(acerto01)} de cada 100 picks acertaram em ${jogos} jogos`;
}

/** #257 — headline (linguagem A, spec §5) e os dois CTAs do hero, centralizados
 * como o resto da copy do app. */
export const HERO = {
  headlineLinha1: "O veredito em primeiro plano.",
  headlineLinha2: "O rigor um nível abaixo.",
  ctaJogos: "Ver os jogos de hoje",
  ctaEntrar: "Entrar · Criar conta",
};
```
(chamada como `fraseAcertoHero(acertos/picks, jogos, 20)` pelo componente — a função não conhece o piso por conta própria, recebe explícito, para o teste não depender de uma constante importada de outro módulo.)

- [ ] **Step 2: Teste do componente**

`tests/unit/Hero.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { Hero } from "@/components/marca/Hero";

afterEach(() => vi.unstubAllGlobals());

function stubFetchSequence(respostas: Array<{ url: RegExp; body: unknown; status?: number }>) {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    const achou = respostas.find((r) => r.url.test(url));
    return Promise.resolve({ status: achou?.status ?? 200, json: () => Promise.resolve(achou?.body ?? {}) });
  }));
}

describe("Hero (#257, spec §5)", () => {
  it("mostra a frase de acerto quando ha amostra e o CTA duplo", async () => {
    stubFetchSequence([
      { url: /ledger\/agregado/, body: { ok: true, acerto: { picks: 380, acertos: 221, jogos: 221 } } },
      { url: /matches\/fetch/, body: { matches: [] } },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByText(/de cada 100 picks acertaram/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Ver os jogos de hoje" })).toHaveAttribute("href", "/jogos");
    expect(screen.getByRole("link", { name: /Entrar/ })).toBeInTheDocument();
  });
  it("amostra curta: a frase de acerto some, o resto da tela continua", async () => {
    stubFetchSequence([
      { url: /ledger\/agregado/, body: { ok: true, acerto: { picks: 10, acertos: 5, jogos: 10 } } },
      { url: /matches\/fetch/, body: { matches: [] } },
    ]);
    render(<Hero />);
    await waitFor(() => expect(screen.getByRole("link", { name: "Ver os jogos de hoje" })).toBeInTheDocument());
    expect(screen.queryByText(/de cada 100 picks acertaram/)).toBeNull();
  });
});
```

- [ ] **Step 3: Rodar e ver falhar; implementar**

`src/components/marca/Hero.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getLedgerAgregado } from "@/lib/ledgerApi";
import { getMatchesByLeague } from "@/lib/api";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { ACTIVE_LEAGUES, type Match } from "@/lib/leagues";
import { fraseAcertoHero, HERO } from "@/lib/copy";
import { Talao } from "@/components/feed/Talao";
import { fonteMarca } from "@/components/marca/fonteMarca";

const MIN_N_HERO = 20; // mesmo piso do backend, MIN_N_BRIER (#079)

export function Hero() {
  const [frase, setFrase] = useState<string | null>(null);
  const [talaoProva, setTalaoProva] = useState<JogoView | null>(null);

  useEffect(() => {
    let vivo = true;
    getLedgerAgregado("30d").then((r) => {
      if (!vivo || !r.ok) return;
      const { picks, acertos, jogos } = r.dados.acerto;
      setFrase(fraseAcertoHero(picks > 0 ? acertos / picks : 0, jogos, MIN_N_HERO));
    }).catch(() => {});

    const ligas = ACTIVE_LEAGUES().map((l) => l.id).join(",");
    getMatchesByLeague(ligas, "today").then((res) => {
      if (!vivo) return;
      const agora = new Date();
      const views = deduplicateMatches(
        (res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)),
      ).map((m: Match) => toJogoView(m, agora));
      const valem = views.filter((v) => v.talao).sort((a, b) => (b.talao!.edge ?? -1) - (a.talao!.edge ?? -1));
      if (valem[0]) setTalaoProva(valem[0]);
    }).catch(() => {});

    return () => { vivo = false; };
  }, []);

  return (
    <section className="mx-auto flex min-h-screen max-w-[720px] flex-col items-center justify-center gap-6 px-4 text-center text-[var(--sb-texto)]">
      <h1 className={`${fonteMarca.className} text-[36px] font-bold leading-tight`}>
        {HERO.headlineLinha1}
        <br />{HERO.headlineLinha2}
      </h1>
      {frase && <p className="tnum text-[16px] text-[var(--sb-texto-apagado)]">{frase}</p>}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/jogos" className="sb-foco rounded-[var(--sb-raio-painel)] border border-[var(--sb-texto)] px-5 py-2.5 text-[16px] font-semibold">
          {HERO.ctaJogos}
        </Link>
        <Link href="/login" className="sb-foco text-[14px] underline">{HERO.ctaEntrar}</Link>
      </div>
      {talaoProva?.talao && (
        <div className="w-full max-w-[420px] text-left">
          <Talao pick={talaoProva.talao} futuro={talaoProva.estado === "amanha_sem_preco"} preJogo={false} />
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: `app/page.tsx`**

Substituir o conteúdo por:
```tsx
import { Hero } from "@/components/marca/Hero";
export const metadata = { title: "SportsBankZU Pro" };
export default function Page() {
  return <main className="min-h-screen bg-[var(--sb-tinta)]"><Hero /></main>;
}
```

- [ ] **Step 5: Rodar** — `npx vitest run tests/unit/Hero.test.tsx tests/unit/copy.test.ts`; `npx tsc --noEmit`; `npm run lint:fonts` (Barlow só aqui e em `app/page.tsx` — `fonteMarca` é importado só por `Hero.tsx`, que só é importado por `app/page.tsx`: guarda intacta).
- [ ] **Step 6: Commit** — `git add frontend/next/src/components/marca/Hero.tsx frontend/next/src/app/page.tsx frontend/next/src/lib/copy.ts frontend/next/tests/unit/Hero.test.tsx frontend/next/tests/unit/copy.test.ts && git commit -m "feat(front): hero com prova real do ledger (#257)"`

---

### Task 29: `middleware.ts` — redirect por cookie

**Por quê.** `src/middleware.ts` hoje redireciona `/` para `/dashboard` sem condição (linha 9-11) — o hero da Task 28 nunca seria visto. A spec (§3) pede: hero em `/` só para primeira visita/deslogado; quem retorna (cookie lido no server, sem flash) vai para `/jogos?dia=hoje`. Decisão de projeto #6 (topo do plano): cookie `sbz_visitou`, `Max-Age=15552000` (180 dias), `Path=/`, `SameSite=Lax`, sem `httpOnly`.

**Files:**
- Modify: `frontend/next/src/middleware.ts`
- Create: `frontend/next/e2e/hero-redirect.spec.ts`

- [ ] **Step 1: Teste E2E (falha: middleware ainda redireciona incondicionalmente)**

`e2e/hero-redirect.spec.ts`:
```ts
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
```

- [ ] **Step 2: Rodar e ver falhar** — `npx playwright test e2e/hero-redirect.spec.ts`.

- [ ] **Step 3: Implementar**

`src/middleware.ts`:
```ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// TODO #136: reativar auth quando RDS/Vercel estiver configurado
// Por enquanto, todas as rotas são públicas. Sem verificação de token.

const COOKIE_VISITOU = "sbz_visitou";
const TTL_VISITOU_S = 60 * 60 * 24 * 180; // 180 dias — #257, decisão de projeto

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const visitou = req.cookies.get(COOKIE_VISITOU)?.value === "1";

  // #257: "/" é o hero só na primeira visita/deslogado (spec §3). Quem já
  // visitou vai direto para o feed, sem flash do hero (decisão no server).
  if (pathname === "/") {
    if (visitou) {
      const resposta = NextResponse.redirect(new URL("/jogos", req.url));
      resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
      return resposta;
    }
    const resposta = NextResponse.next();
    resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
    return resposta;
  }

  // Qualquer visita a /jogos também marca "já visitou" — quem chega direto
  // por link compartilhado não vê o hero na próxima vez que abrir "/".
  if (pathname.startsWith("/jogos") && !visitou) {
    const resposta = NextResponse.next();
    resposta.cookies.set(COOKIE_VISITOU, "1", { maxAge: TTL_VISITOU_S, path: "/", sameSite: "lax" });
    return resposta;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logos).*)"],
};
```

`src/app/page.tsx` (Task 28) deixa de ser alcançável por quem já visitou — o middleware intercepta antes de renderizar, mesmo padrão de hoje.

- [ ] **Step 4: Rodar** — `npx playwright test e2e/hero-redirect.spec.ts` → PASS.
- [ ] **Step 5: Commit** — `git add frontend/next/src/middleware.ts frontend/next/e2e/hero-redirect.spec.ts && git commit -m "feat(front): redirect da raiz por cookie sbz_visitou, 180 dias (#257)"`

---

### Task 30: `/glossario` — dez termos, âncora por id

**Por quê.** `src/app/glossario/page.tsx` hoje reexporta `Dashboard` com `initialView="glossario"` (11 linhas). A spec (§5) pede uma tela própria: dez termos com exemplo numérico real, âncora por `id`, sem busca. `lib/copy.ts` já usa `{term:id|texto}` (`comTermos`, fase 0) esperando que cada `id` tenha uma âncora em `/glossario#id`.

**Files:**
- Create: `frontend/next/src/lib/glossarioTermos.ts`, `frontend/next/tests/unit/glossarioTermos.test.ts`, `frontend/next/e2e/glossario.spec.ts`
- Modify: `frontend/next/src/app/glossario/page.tsx` (substituir o conteúdo — o caminho do arquivo é reaproveitado, não um arquivo novo)

**Interfaces:**
- Produces: `TERMOS: { id: string; titulo: string; explicacao: string; exemplo: string }[]` (exportado, os 10 ids citados na spec §5: `chance, minimo, paga, edge, stake, jogos-medidos, calibracao, brier, direcao, corredor`).

- [ ] **Step 1: Teste — todo `id` usado em `comTermos` no resto do app tem entrada aqui**

`tests/unit/glossarioTermos.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { TERMOS } from "@/lib/glossarioTermos";

describe("glossarioTermos (#257, spec §5)", () => {
  it("dez termos, ids unicos, cada um com titulo/explicacao/exemplo numerico", () => {
    expect(TERMOS).toHaveLength(10);
    const ids = TERMOS.map((t) => t.id);
    expect(new Set(ids).size).toBe(10);
    for (const t of TERMOS) {
      expect(t.titulo.length).toBeGreaterThan(0);
      expect(t.explicacao.length).toBeGreaterThan(0);
      expect(/\d/.test(t.exemplo)).toBe(true); // exemplo numerico real (spec §5)
    }
  });
  it("cobre os ids citados na spec: stake e brier", () => {
    expect(TERMOS.some((t) => t.id === "stake")).toBe(true);
    expect(TERMOS.some((t) => t.id === "brier")).toBe(true);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

`src/lib/glossarioTermos.ts`:
```ts
/** #257 — os dez termos do glossário (spec §5), com exemplo numérico real
 * (mesmos números do card de exemplo da spec §4.1: Toronto × Nashville SC). */
export interface TermoGlossario { id: string; titulo: string; explicacao: string; exemplo: string }

export const TERMOS: TermoGlossario[] = [
  { id: "chance", titulo: "Chance", explicacao: "a frequência que o modelo espera para esse resultado, em cada 100 jogos parecidos.", exemplo: "58 em cada 100 jogos assim terminam com mais de 6,5 escanteios." },
  { id: "minimo", titulo: "Mínimo", explicacao: "a odd abaixo da qual apostar deixa de valer a pena, dada a chance calculada.", exemplo: "com chance de 58%, vale a partir de 1,67." },
  { id: "paga", titulo: "Paga", explicacao: "a odd que a casa de apostas está oferecendo agora para esse mercado.", exemplo: "mercado paga 1,75." },
  { id: "edge", titulo: "Edge", explicacao: "a diferença entre a chance calculada e a chance implícita na odd da casa — quanto maior, mais a odd está \"errada\" a favor de quem aposta.", exemplo: "chance 58% − chance implícita em 1,75 (57%) = edge de 0,01 (1pp)." },
  { id: "stake", titulo: "Stake", explicacao: "quanto apostar nesse pick, calculado como uma fração da sua banca pelo critério de Kelly, reduzido a um quarto por segurança.", exemplo: "numa banca de R$ 1.000, um pick com edge de 8pp sugere R$ 25." },
  { id: "jogos-medidos", titulo: "Jogos medidos", explicacao: "quantos jogos dessa liga entraram na conta de acerto que o painel mostra — quanto menor, menos confiável é a média.", exemplo: "MLS: 40 jogos medidos." },
  { id: "calibracao", titulo: "Calibração", explicacao: "o quanto as chances que o painel diz batem com o que de fato acontece, olhando muitos picks juntos.", exemplo: "quando o painel disse 60, aconteceu 57 em cada 100." },
  { id: "brier", titulo: "Brier", explicacao: "uma nota de erro da previsão: quanto menor, melhor calibrado está o modelo. Zero é perfeito, 0,25 é o mesmo que \"não sei\".", exemplo: "Brier de 0,2529 nos últimos 30 dias." },
  { id: "direcao", titulo: "Direção", explicacao: "quando o modelo aponta um lado mas não há preço bom o bastante para recomendar apostar.", exemplo: "Direção: mais de 2,5 gols, 57 em cada 100 — sem preço que valha hoje." },
  { id: "corredor", titulo: "Corredor", explicacao: "mercados que se sobrepõem (ex.: mais de 2,5 gols e ambos marcam) não competem pelo talão ao mesmo tempo, para não recomendar duas apostas que dependem do mesmo resultado.", exemplo: "só um mercado do corredor de gols vira talão por jogo." },
];
```

`src/app/glossario/page.tsx` (substitui o conteúdo inteiro):
```tsx
import { TERMOS } from "@/lib/glossarioTermos";

export const metadata = { title: "Glossário — SportsBankZU Pro" };

export default function GlossarioPage() {
  return (
    <main className="mx-auto max-w-[720px] px-4 py-8 text-[var(--sb-texto)]">
      <h1 className="font-[family-name:var(--font-slab)] text-[28px] font-bold">Glossário</h1>
      <dl className="mt-6 space-y-6">
        {TERMOS.map((t) => (
          <div key={t.id} id={t.id} className="scroll-mt-4 border-t border-[var(--sb-linha)] pt-4">
            <dt className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{t.titulo}</dt>
            <dd className="mt-1 max-w-[70ch] text-[14px]">{t.explicacao}</dd>
            <dd className="tnum mt-1 max-w-[70ch] text-[14px] text-[var(--sb-texto-apagado)]">{t.exemplo}</dd>
          </div>
        ))}
      </dl>
    </main>
  );
}
```

- [ ] **Step 3: E2E — âncora funciona**

`e2e/glossario.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("/glossario#stake ancora no termo certo (#257)", async ({ page }) => {
  await page.goto("/glossario#stake");
  await expect(page.locator("#stake")).toBeInViewport();
  await expect(page.locator("#stake dt")).toHaveText("Stake");
});
```

- [ ] **Step 4: Rodar** — `npx vitest run tests/unit/glossarioTermos.test.ts`; `npx playwright test e2e/glossario.spec.ts`; `npm run lint:accents`.
- [ ] **Step 5: Commit** — `git add frontend/next/src/lib/glossarioTermos.ts frontend/next/src/app/glossario/page.tsx frontend/next/tests/unit/glossarioTermos.test.ts frontend/next/e2e/glossario.spec.ts && git commit -m "feat(front): /glossario com dez termos e exemplo numerico (#257)"`

---

### Task 31: Navegação final — barra inferior (celular) e sidebar (desktop)

**Por quê.** A spec (§3) define: celular, barra inferior com três itens (Jogos · Banca · Desempenho); desktop, sidebar com quatro (Jogos · Banca · Desempenho · Glossário). Hoje `layout.tsx` não tem navegação própria da reformulação (só `ThemeToggle`/`SessionProvider`, herdados do dashboard antigo).

**Files:**
- Create: `frontend/next/src/components/nav/Navegacao.tsx`, `frontend/next/tests/unit/Navegacao.test.tsx`
- Modify: `frontend/next/src/app/layout.tsx`, `frontend/next/src/app/banca/page.tsx` (micro-fix: `<h1>Banca</h1>`, título da tela — spec §5; emenda 2026-09-16, portão da fase 3)

**Interfaces:**
- Produces: `<Navegacao />` — client component, um único componente decide barra vs. sidebar por CSS/breakpoint (evita duas árvores de link divergindo); esconde-se em `/`, `/login`, `/register`.

- [ ] **Step 1: Teste**

`tests/unit/Navegacao.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Navegacao } from "@/components/nav/Navegacao";

vi.mock("next/navigation", () => ({ usePathname: () => "/jogos" }));

describe("Navegacao (#257, spec §3)", () => {
  it("quatro links, Jogos marcado como ativo em /jogos", () => {
    render(<Navegacao />);
    const jogos = screen.getByRole("link", { name: "Jogos" });
    const banca = screen.getByRole("link", { name: "Banca" });
    const desempenho = screen.getByRole("link", { name: "Desempenho" });
    const glossario = screen.getByRole("link", { name: "Glossário" });
    expect(jogos).toHaveAttribute("aria-current", "page");
    expect(banca).toHaveAttribute("href", "/banca");
    expect(desempenho).toHaveAttribute("href", "/desempenho");
    expect(glossario).toHaveAttribute("href", "/glossario");
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

`src/components/nav/Navegacao.tsx`:
```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITENS = [
  { href: "/jogos", rotulo: "Jogos" },
  { href: "/banca", rotulo: "Banca" },
  { href: "/desempenho", rotulo: "Desempenho" },
  { href: "/glossario", rotulo: "Glossário" },
] as const;

/** #257 — celular: barra inferior com 3 (sem Glossário, spec §3); desktop:
 * sidebar com os 4. Um componente, CSS decide o layout por breakpoint — evita
 * duas árvores de link divergindo. Some em "/" (hero), "/login", "/register". */
export function Navegacao() {
  const pathname = usePathname();
  const ESCONDIDA = new Set(["/", "/login", "/register"]);
  if (ESCONDIDA.has(pathname)) return null;

  return (
    <nav aria-label="navegação principal">
      <ul className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-[var(--sb-linha)] bg-[var(--sb-painel)] py-2 lg:static lg:inset-auto lg:z-auto lg:w-[200px] lg:flex-col lg:gap-1 lg:border-t-0 lg:border-r lg:py-6">
        {ITENS.map((item, i) => (
          <li key={item.href} className={i === 3 ? "hidden lg:block" : ""}>
            <Link
              href={item.href}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              className="sb-foco block rounded-[var(--sb-raio-painel)] px-3 py-2 text-center text-[13px] aria-[current=page]:font-semibold aria-[current=page]:text-[var(--sb-texto)] lg:text-left lg:text-[14px]"
            >
              {item.rotulo}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

`src/app/layout.tsx` real (verificado 2026-09-16) tem 30 linhas; substituir exatamente este trecho (emenda 2026-09-16, portão da fase 3, corrige o `// ...` elíptico da versão anterior deste plano) pelo conteúdo literal completo do arquivo depois da mudança:
```tsx
import "./globals.css";
import "@/styles/scoretabs-dashboard.css";
import "@/styles/match-detail-card.css";
import { Zilla_Slab, Source_Sans_3 } from "next/font/google";
import { ThemeProvider } from "../components/theme-provider";
import { ThemeToggle } from "../components/ThemeToggle";
import { SessionProvider } from "../components/SessionProvider";
import { Navegacao } from "@/components/nav/Navegacao";

const slab = Zilla_Slab({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-slab", display: "swap" });
const sans = Source_Sans_3({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-sans", display: "swap" });

export const metadata = {
  title: "SportsBankZU Pro",
  description: "Dashboard de análise esportiva profissional",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${slab.variable} ${sans.variable}`}>
      <body>
        <SessionProvider>
          <ThemeProvider>
            <ThemeToggle />
            <div className="lg:flex">
              <Navegacao />
              <div className="flex-1 pb-16 lg:pb-0">{children}</div>
            </div>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
```
(`pb-16` no conteúdo abre espaço para a barra inferior fixa no celular; a sidebar do desktop não precisa disso porque não é `fixed`.)

- [ ] **Step 3: Rodar** — `npx vitest run tests/unit/Navegacao.test.tsx`; `npx tsc --noEmit`.
- [ ] **Step 3-bis: Micro-fix — `<h1>` em `/banca`** (emenda 2026-09-16, portão da fase 3). `frontend/next/src/app/banca/page.tsx` hoje (verificado 2026-09-16) não tem título; substituir exatamente este trecho:
```tsx
    <main className="min-h-screen bg-[var(--sb-tinta)] px-4 py-6">
      <FormBanca />
    </main>
```
por:
```tsx
    <main className="min-h-screen bg-[var(--sb-tinta)] px-4 py-6">
      <h1 className="mb-4 text-[22px] font-semibold text-[var(--sb-texto)]">Banca</h1>
      <FormBanca />
    </main>
```
**Referência visual:** este `<h1>` muda o layout de `/banca` — as duas capturas de `frontend/next/e2e/visual.spec.ts` (`banca-indefinida.png`, `banca-definida.png`) ficam desatualizadas; rodar `npx playwright test --update-snapshots -g "banca"` e **o dono (Welligton) aprova o diff antes do commit** (regra global desta seção).
- [ ] **Step 4: Verificar visualmente que o dashboard antigo não quebrou** — `npm run dev`, abrir `/dashboard`: a barra/sidebar aparece ao lado (aceitável, registrar como mudança consciente — o dashboard sai de circulação na fase 6; não vale a pena esconder `Navegacao` ali também).
- [ ] **Step 5: Commit** — `git add frontend/next/src/components/nav frontend/next/src/app/layout.tsx frontend/next/src/app/banca/page.tsx frontend/next/tests/unit/Navegacao.test.tsx frontend/next/e2e/visual.spec.ts-snapshots && git commit -m "feat(front): navegacao final — barra inferior, sidebar e titulo de /banca (#257)"`

---

### Task 32: Links contextuais — `comTermos` ganha um consumidor

**Por quê.** `lib/copy.ts` (fase 0) já expõe `comTermos(template)`, que separa `{term:id|texto}` em trechos com `termo`, mas nada no app consome esse retorno ainda — os templates com `{term:...}` nunca viram link de verdade. Esta tarefa cria o componente que renderiza `Trecho[]` como texto com `<Link>` embutido, e aplica em pelo menos um lugar real do fluxo (a frase de stake do card, que a spec §4.4 lista como candidata a `{term:edge|edge}`).

**Files:**
- Create: `frontend/next/src/components/TextoComTermos.tsx`, `frontend/next/tests/unit/TextoComTermos.test.tsx`
- Modify: `frontend/next/src/lib/copy.ts` (novo template de stake com token), `frontend/next/src/components/feed/LinhaStake.tsx` (fase 3, consumir o novo componente)

**Interfaces:**
- Produces: `<TextoComTermos texto={string} />` — roda `comTermos` e renderiza, com cada `termo` virando `<Link href="/glossario#id">`.

- [ ] **Step 1: Teste**

`tests/unit/TextoComTermos.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TextoComTermos } from "@/components/TextoComTermos";

describe("TextoComTermos (#257)", () => {
  it("texto sem termo passa direto", () => {
    render(<TextoComTermos texto="sem termo aqui" />);
    expect(screen.getByText("sem termo aqui")).toBeInTheDocument();
  });
  it("{term:id|texto} vira link para /glossario#id", () => {
    render(<TextoComTermos texto="o {term:edge|edge} de hoje" />);
    const link = screen.getByRole("link", { name: "edge" });
    expect(link).toHaveAttribute("href", "/glossario#edge");
    expect(screen.getByText(/^o /)).toBeInTheDocument();
    expect(screen.getByText(/de hoje$/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar; implementar**

`src/components/TextoComTermos.tsx`:
```tsx
import Link from "next/link";
import { comTermos } from "@/lib/copy";

/** #257 — primeiro consumidor de `comTermos` (fase 0, `lib/copy.ts`): um
 * template com `{term:id|texto}` vira texto com link embutido para o
 * glossário, sem o componente que chama precisar saber o formato. */
export function TextoComTermos({ texto }: { texto: string }) {
  return (
    <>
      {comTermos(texto).map((trecho, i) =>
        "termo" in trecho
          ? <Link key={i} href={`/glossario#${trecho.termo}`} className="sb-foco underline">{trecho.texto}</Link>
          : <span key={i}>{trecho.texto}</span>,
      )}
    </>
  );
}
```

Em `src/lib/copy.ts`, acrescentar uma variante do template de stake com token (a `stake()` existente continua devolvendo string pura, usada onde não há link possível, ex.: `aria-label`):
```ts
/** Variante com token de glossário, para LinhaStake renderizar com TextoComTermos.
 * `stake()` (acima) continua devolvendo string pura. */
export function stakeComTermo(banca: number | null, valor: number | null): string {
  if (banca == null || valor == null) return "stake: defina sua {term:stake|banca}";
  return `Da sua banca de ${fmtReais(banca)}: ${fmtReais(valor)}`;
}
```
Em `src/components/feed/LinhaStake.tsx` (fase 3), trocar `<span>{stake(banca, valor)}</span>` (caso COM banca) por `<span><TextoComTermos texto={stakeComTermo(banca, valor)} /></span>`; o caso SEM banca mantém `stake(null, null)` dentro do `<Link href="/banca">` existente (é já um link, não precisa de token) — conferir contra `tests/unit/linhas.test.tsx` (fase 3) antes de commitar: se algum teste existente quebrar por causa da troca, ele testava o texto puro do caso COM banca e deve ser atualizado para `screen.getByText(/Da sua banca de/)` continuar passando (o texto visível não muda, só passa a ter o link do glossário embutido).

- [ ] **Step 3: Rodar** — `npx vitest run tests/unit/TextoComTermos.test.tsx tests/unit/copy.test.ts tests/unit/linhas.test.tsx`; `npm run lint:accents`.
- [ ] **Step 4: Commit** — `git add frontend/next/src/components/TextoComTermos.tsx frontend/next/src/lib/copy.ts frontend/next/src/components/feed/LinhaStake.tsx frontend/next/tests/unit/TextoComTermos.test.tsx && git commit -m "feat(front): TextoComTermos liga copy.ts ao glossario (#257)"`

---

### Task 33: Fechar a fase 5

- [ ] **Step 1:** Suíte completa: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test`. Expected: verde.
- [ ] **Step 2:** Entrada `## 257 — Reformulação do frontend, fase 5: hero, redirect por cookie, glossário, navegação` em `docs/REGISTRO_CORRECOES.md`:
  - **Problema:** `/` era um redirect morto para `/dashboard`; `/glossario` reexportava o dashboard; não havia navegação própria da reformulação; `comTermos` (fase 0) não tinha consumidor.
  - **Causa raiz:** hero, cookie e glossário eram entregas da fase 5, não construídas antes.
  - **Correções por camada:** `Hero.tsx` + `page.tsx`, `middleware.ts` (cookie `sbz_visitou`), `glossario/page.tsx` (conteúdo próprio), `Navegacao.tsx` + `layout.tsx`, `TextoComTermos.tsx`.
  - **Contratos de saída:** nenhum campo de backend escrito; `Hero` lê `/ledger/agregado` e `/api/matches/fetch` (leituras já auditadas).
  - **Prova empírica:** placar de testes, prova do cookie sendo gravado (Playwright `context.cookies()`).
  - **Etapa 5:** não se aplica.
- [ ] **Step 3:** Linha em `docs/INDICE_REGRAS.md`.
- [ ] **Step 4:** Espelhar os 4 docs, commit `docs: REGISTRO #257 fase 5`, push, CI verde.
- [ ] **Step 4-bis: Precondição do gate — rodada 1 do teste de 5 s** (emenda 2026-09-16, portão da fase 3). A spec §7 marca a rodada 1 como o portão desta fase (não mais mockup pré-build); confirmar que o REGISTRO #254-b tem o resultado real da rodada 1 preenchido (acerto por perfil, tempo mediano) **antes** do Step 5 — sem isso o Step 5 não abre.
- [ ] **Step 5:** **Gate da fase:** aguardar o "ok" do dono antes de iniciar a fase 6.

---
## Fase 6 — Rodada 2 do teste de 5s, `/jogos` vira padrão, remoção das rotas antigas

Depende de: fase 5 (hero, navegação, glossário completos — o produto novo precisa estar navegável de ponta a ponta antes de apagar o antigo).

### Task 34: Tag e branch de backup ANTES de qualquer remoção

**Por quê.** Proibição operacional explícita do dono (regras deste plano) e spec §8: "tag e branch de backup antes de apagar". Isto tem que ser uma tarefa própria, executada e verificada antes de a Task 37 tocar em qualquer arquivo — nunca implícita em outro passo.

**Files:** nenhum (operação de git).

- [ ] **Step 1:** Confirmar que a fase 5 está fechada e mergeada em `main` (`git log --oneline -1 origin/main` bate com o commit de fechamento da Task 33).
- [ ] **Step 2:** Criar a tag e o branch de backup, apontando para o `main` atual:
```bash
git fetch origin main
git tag backup-pre-corte-legado-fase6 origin/main
git push origin backup-pre-corte-legado-fase6
git branch backup-legado-fase6 origin/main
git push origin backup-legado-fase6
```
- [ ] **Step 3:** Verificar que os dois existem no remoto: `git ls-remote origin | grep -E "backup-pre-corte-legado-fase6|backup-legado-fase6"` → duas linhas.
- [ ] **Step 4:** Registrar no REGISTRO da Task 39 o hash exato (`git rev-parse backup-pre-corte-legado-fase6`) para quem precisar reverter saber exatamente de onde partir.

---

### Task 35: `/jogos` vira o padrão da raiz

**Por quê.** A spec (§8, entrega da fase 6) marca "`/jogos` vira padrão". Depois da Task 34 (backup) e antes da Task 37 (remoção), o site inteiro passa a assumir `/jogos` como destino de qualquer navegação sem direção — não só o cookie de retorno (Task 29), mas também o fallback de erro (`/jogos/[id]` inexistente já aponta para `/jogos`, fase 3) e qualquer link morto remanescente das rotas apagadas na Task 37.

**Files:**
- Modify: `frontend/next/src/middleware.ts` (Task 29)
- Create: `frontend/next/e2e/rotas-legadas.spec.ts` (parte 1 — o resto entra na Task 38)

**Interfaces:**
- Nenhuma nova; ajusta o comportamento do middleware existente.

- [ ] **Step 1: Decisão e teste**

A Task 29 já faz `/` redirecionar para `/jogos` quando `sbz_visitou=1`. O que falta para "`/jogos` vira padrão" de fato: qualquer rota que **não exista mais** depois da Task 37 deve cair em `/jogos` (ou 404 explícito — ver critério na Task 38), nunca num 500 ou numa página em branco. Next.js já faz isso nativamente (rota inexistente → 404 do App Router) — esta tarefa só confirma que o comportamento é o desejado e documenta a exceção: rotas que ficam como arquivo sem link (`login`, `register`, `admin-activate`, `admin-deactivate`, `debug-live`, `ferramentas`, spec §3) continuam respondendo 200, só saem da navegação (já feito na Task 31).

`e2e/rotas-legadas.spec.ts` (início — a Task 38 acrescenta o resto depois da remoção):
```ts
import { test, expect } from "@playwright/test";

test.describe("raiz e destino padrao (#258, spec §8)", () => {
  test("/ com cookie de retorno vai para /jogos", async ({ page, context }) => {
    await context.addCookies([{ name: "sbz_visitou", value: "1", domain: "localhost", path: "/" }]);
    await page.route("**/api/matches/fetch**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ matches: [] }) }));
    await page.route("**/api/ml/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, leagues: {} }) }));
    await page.goto("/");
    await expect(page).toHaveURL(/\/jogos/);
  });
  test("rotas que ficam sem link ainda respondem (nao viram 404 por engano)", async ({ page }) => {
    for (const rota of ["/login", "/register"]) {
      const resp = await page.goto(rota);
      expect(resp?.status()).toBeLessThan(400);
    }
  });
});
```

- [ ] **Step 2:** Rodar `npx playwright test e2e/rotas-legadas.spec.ts` → PASS (já passa com o código da Task 29 — esta tarefa é a prova formal de que "vira padrão" está coberto, não uma implementação nova).
- [ ] **Step 3:** Commit — `git add frontend/next/e2e/rotas-legadas.spec.ts && git commit -m "test(front): /jogos como destino padrao apos o cookie (#258)"`

---

### Task 36: Rodada 2 do teste de 5 segundos — preparar o material (o dono conduz)

**Por quê.** Spec §7: "Rodada 2 sobre o produto construído, na fase 6", com o mesmo critério pré-registrado da rodada 1 (plano 1, Task 19, Step 3): **acerto ≥ 80% por perfil e tempo mediano ≤ 5 s no objeto de decisão**. Rodada 1 foi portão da fase 5 (emenda 2026-09-16, portão da fase 3). Este plano **não executa** o teste com pessoas — só prepara o material e o molde de resultado. A condução (4-6 pessoas por perfil casual/analítico, mostrar a tela por 5 s, perguntar "qual mercado e qual odd mínima?") é do dono, fora do escopo de um agente.

**Files:**
- Create: `frontend/next/scripts/capturar-telas-teste-5s.mjs`, `docs/superpowers/testes/2026-XX-XX-teste-5s-rodada-2-RESULTADO.md` (molde, preenchido pelo dono depois)

- [ ] **Step 1: Script que captura as duas telas do produto construído (não mockup — o objeto de decisão real)**

`scripts/capturar-telas-teste-5s.mjs`:
```js
#!/usr/bin/env node
/**
 * #258 — captura as duas telas da rodada 2 do teste de 5s (spec §7), a
 * partir do PRODUTO construído (não do mockup da rodada 1). Roda contra
 * `next dev`/`next start` já de pé em localhost:3001, com Playwright já
 * instalado (devDependency existente desde a fase 3, Task 18).
 */
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const OUT = "docs/superpowers/testes/rodada-2-telas";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

// Tela 1: o card "vale" em /jogos (objeto de decisao). Ajustar a URL para um
// dia real com pick SAFE antes de rodar.
await page.goto("http://localhost:3001/jogos");
await page.waitForSelector("article[data-estado='vale']", { timeout: 15_000 });
await page.locator("article[data-estado='vale']").first().screenshot({ path: `${OUT}/tela-1-talao.png` });

// Tela 2: a tabela de mercados no detalhe (objeto de rigor).
const href = await page.locator("article[data-estado='vale'] h2 a").first().getAttribute("href");
await page.goto(`http://localhost:3001${href}`);
await page.waitForSelector("table#mercados");
await page.locator("table#mercados").screenshot({ path: `${OUT}/tela-2-tabela.png` });

await browser.close();
console.log(`Telas salvas em ${OUT}/. Rodar a rodada 2 com estas duas imagens.`);
```

- [ ] **Step 2: Molde de resultado (preenchido pelo dono após a rodada, não pelo agente)**

`docs/superpowers/testes/2026-XX-XX-teste-5s-rodada-2-RESULTADO.md` (renomear `XX-XX` para a data real ao preencher):
```markdown
# Teste de 5 segundos — rodada 2 (produto construído)

**Critério pré-registrado (spec §7, mesmo da rodada 1):** acerto >= 80% por
perfil e tempo mediano <= 5 s no objeto de decisão (tela 1, o talão).

**Telas usadas:** `rodada-2-telas/tela-1-talao.png` (objeto de decisão),
`rodada-2-telas/tela-2-tabela.png` (objeto de rigor, tabela do detalhe).

## Perfil casual (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%) · **Tempo mediano:** __ s

## Perfil analítico (4-6 pessoas)

| # | Acertou mercado? | Acertou odd mínima? | Tempo (s) | Confiança (1-5) |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |

**Acerto do perfil:** __/__ (__%) · **Tempo mediano:** __ s

## Veredito

- [ ] Critério atingido nos dois perfis (>= 80% acerto, <= 5s mediana) — a
      seção 4 da spec fica como está.
- [ ] Critério NÃO atingido — abrir uma entrada nova no REGISTRO com o que a
      seção 4 precisa mudar, ANTES de fechar a fase 6.

Preenchido por: __________ em __________.
```

- [ ] **Step 3:** Rodar `node scripts/capturar-telas-teste-5s.mjs` contra `next dev` local, confirmar que as duas imagens saem legíveis.
- [ ] **Step 4:** Entregar as duas imagens e o molde ao dono; a condução do teste em si acontece fora deste plano. **O resultado preenchido entra no REGISTRO da Task 39 com os números reais — nunca inventados aqui.**
- [ ] **Step 5: Commit** — `git add frontend/next/scripts/capturar-telas-teste-5s.mjs docs/superpowers/testes && git commit -m "chore(front): material da rodada 2 do teste de 5s (#258)"`

---

### Task 37: Remover as rotas legadas

**Por quê.** Spec §8: "tag e branch de backup antes de apagar `dashboard/page.tsx`, `duplas`, `destaques`, `campeonatos` e as rotas mortas". A tabela de IA da spec (§3, coluna "Substitui") dá a lista completa de "rotas mortas": `bankroll` (substituído por `/banca`), `match/[id]` (por `/jogos/[id]`), `performance-stats`, `ai-audit`, `admin/reliability` (pelos três, por `/desempenho`). `glossario` **não entra aqui** — seu caminho foi reaproveitado pela Task 30 (fase 5), já não é mais o dashboard reexportado. **Remoção consciente, não omissão** (emenda 2026-09-16, portão da fase 3, espelha spec §3/§8 linha 6): este corte também remove as visões de "rodada"/semana que viviam no `dashboard` legado — não há substituto na reformulação, `Rodada` no segmented control de `/jogos` fica pós-reformulação (spec §3).

**Pré-condição:** Task 34 (backup) concluída e verificada.

**Files:**
- Delete: `frontend/next/src/app/dashboard/` (2.499 linhas), `frontend/next/src/app/duplas/`, `frontend/next/src/app/destaques/`, `frontend/next/src/app/campeonatos/`, `frontend/next/src/app/bankroll/`, `frontend/next/src/app/match/`, `frontend/next/src/app/performance-stats/`, `frontend/next/src/app/ai-audit/`, `frontend/next/src/app/admin/reliability/`
- Modify: `frontend/next/src/middleware.ts` (a rota de redirect `"/dashboard"` não existe mais em lugar nenhum do código — conferir que nada mais referencia `/dashboard` como destino)

- [ ] **Step 1: Inventário de quem ainda referencia as rotas a apagar, antes de apagar**

```bash
cd frontend/next
grep -rn "from \"\.\./dashboard/page\"\|from \"@/app/dashboard" src/app --include="*.tsx" \
  | grep -v "src/app/dashboard/page.tsx"
grep -rln "/dashboard\b\|/bankroll\b\|/performance-stats\b\|/ai-audit\b\|/admin/reliability\b\|/match/\[id\]\|/duplas\b\|/destaques\b\|/campeonatos\b" src --include="*.tsx" --include="*.ts" \
  | grep -v -E "app/(dashboard|duplas|destaques|campeonatos|bankroll|match|performance-stats|ai-audit|admin/reliability)/"
```
Expected: o primeiro comando só encontra `duplas/page.tsx`, `destaques/page.tsx`, `campeonatos/page.tsx` (que também saem — apagados juntos, não sobra import morto). O segundo comando não deve encontrar nada fora das próprias pastas a apagar; se encontrar (ex.: um link em `components/` ou `layout.tsx` apontando para `/dashboard`), resolver ANTES do Step 2 — trocar o link para `/jogos` (ou o substituto correto da tabela da spec).

- [ ] **Step 2: Apagar os diretórios**

```bash
git rm -r frontend/next/src/app/dashboard
git rm -r frontend/next/src/app/duplas
git rm -r frontend/next/src/app/destaques
git rm -r frontend/next/src/app/campeonatos
git rm -r frontend/next/src/app/bankroll
git rm -r frontend/next/src/app/match
git rm -r frontend/next/src/app/performance-stats
git rm -r frontend/next/src/app/ai-audit
git rm -r frontend/next/src/app/admin/reliability
```

- [ ] **Step 3: Apagar componentes órfãos (só os que ficam sem NENHUM importador depois do Step 2) — guardar a saída real**

```bash
for c in BankrollCalculator MatchDetailCard DestaquesDoDia AuditReportCard AIReviewDashboard BatchAuditPanel ReliabilityCard; do
  echo "=== $c ===" | tee -a /tmp/orfaos-256.txt
  grep -rln "$c" frontend/next/src --include="*.tsx" --include="*.ts" | grep -v "components/$c" | tee -a /tmp/orfaos-256.txt
done
cat /tmp/orfaos-256.txt
```
Para cada componente cujo único resultado seja o próprio arquivo de definição (nenhum importador fora dele), `git rm` o arquivo. Não apagar nenhum componente que ainda apareça em outro lugar (ex.: `BankrollCard.tsx` continua vivo — `bancaStore.ts`, fase 0, importa `calcQuarterKelly` de lá; não confundir com `BankrollCalculator.tsx`, que é só da tela antiga). **Guardar o conteúdo de `/tmp/orfaos-256.txt`** — a saída real (não um resumo) entra literalmente no REGISTRO da Task 39 (achado do code review deste plano — a lista de candidatos foi montada por inspeção, não por grep completo no momento em que o plano foi escrito; a prova de que cada um apagado era de fato órfão é essa saída).

- [ ] **Step 4: `tsc` e build confirmam que nada ficou pendurado**

```bash
npx tsc --noEmit
npm run build
```
Expected: sem erro de import não resolvido. Se `tsc` apontar um import morto que o Step 1 não pegou, corrigir e voltar ao Step 1 para reconferir (não seguir com erro de build).

- [ ] **Step 5: Rodar a suíte inteira**

```bash
npm run lint:accents && npm run lint:fonts && npx vitest run && npx playwright test
```
Expected: verde. Testes antigos que só existiam para as rotas apagadas (`e2e/dashboard.spec.ts`, `e2e/ai-audit.spec.ts` se existirem e testarem só o legado) também são removidos neste passo — `git rm` os specs cujo alvo não existe mais, e não apenas o código de produção.

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(front): remove dashboard e rotas legadas — /jogos e /desempenho as substituem (#258)

Backup em tag backup-pre-corte-legado-fase6 e branch backup-legado-fase6
(Task 34) antes desta remocao. Rotas removidas: dashboard, duplas,
destaques, campeonatos, bankroll, match/[id], performance-stats, ai-audit,
admin/reliability — todas substituidas por /jogos, /jogos/[id], /banca e
/desempenho (spec §3, coluna "Substitui").

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 38: Prova de que o corte não deixa link morto sem tratamento

**Files:**
- Modify: `frontend/next/e2e/rotas-legadas.spec.ts` (Task 35)

- [ ] **Step 1:** Acrescentar ao arquivo:
```ts
test.describe("rotas removidas (#258) — 404 previsivel, nunca 500 ou pagina em branco", () => {
  for (const rota of ["/dashboard", "/duplas", "/destaques", "/campeonatos", "/bankroll", "/match/qualquer-id", "/performance-stats", "/ai-audit", "/admin/reliability"]) {
    test(`${rota} responde 404 (nao 500)`, async ({ page }) => {
      const resp = await page.goto(rota);
      expect(resp?.status()).toBe(404);
    });
  }
});
```
- [ ] **Step 2:** Rodar `npx playwright test e2e/rotas-legadas.spec.ts` → PASS (as nove rotas + as duas da Task 35).
- [ ] **Step 3:** Commit — `git add frontend/next/e2e/rotas-legadas.spec.ts && git commit -m "test(front): prova que as rotas removidas dao 404, nunca 500 (#258)"`

---

### Task 39: Fechar a fase 6 — e a reformulação

- [ ] **Step 1:** Suíte completa: `npm run lint:accents && npm run lint:fonts && npx tsc --noEmit && npx vitest run && npx playwright test`. Expected: verde.
- [ ] **Step 2:** Confirmar com o dono que a Task 36 (rodada 2 do teste de 5s) foi conduzida e o molde de resultado preenchido. **Se o critério não foi atingido, esta tarefa NÃO fecha** até uma decisão registrada (reverter a seção 4 da spec ou aceitar o resultado com justificativa) — a spec §7 trata o critério como pré-registrado, não como formalidade.
- [ ] **Step 3:** Entrada `## 258 — Reformulação do frontend, fase 6: corte do legado e rodada 2 do teste de 5s` em `docs/REGISTRO_CORRECOES.md`:
  - **Problema:** o dashboard antigo (2.499 linhas, 43 `useState`) e sete rotas legadas continuavam no ar depois que `/jogos`, `/banca`, `/desempenho` e `/glossario` os substituíram.
  - **Causa raiz:** a spec (§8) definia o corte como a última fase, depois de validação — não antes.
  - **Correções por camada:** backup (tag `backup-pre-corte-legado-fase6`, hash `<preencher com o Step 4 da Task 34>`), remoção de 9 diretórios de rota, prova de 404 em todas as rotas removidas, e **colar aqui o conteúdo literal de `/tmp/orfaos-256.txt`** (Task 37, Step 3) — a saída real do grep por componente órfão, não um resumo, para provar que cada componente apagado não tinha importador fora do próprio arquivo.
  - **Prova empírica:** resultado real da rodada 2 do teste de 5s (colar a tabela preenchida da Task 36 — números reais, não estimados), placar de testes antes/depois do corte, saída de `npm run build` sem import quebrado.
  - **Contratos de saída:** nenhum campo de backend tocado nesta fase.
  - **Etapa 5:** não se aplica (nenhum laço de escrita em produção).
- [ ] **Step 4:** Linha em `docs/INDICE_REGRAS.md`.
- [ ] **Step 5:** Espelhar os 4 docs, commit `docs: REGISTRO #258 fase 6 — reformulacao do frontend concluida`, push, CI verde.
- [ ] **Step 6:** Validar em produção: `curl -s https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/health` (backend intacto — este plano não tocou `backend/` além de leitura já existente) e abrir a URL do Vercel em `/` e `/jogos` para confirmar visualmente.

---

## Auto-revisão

**Cobertura da spec §5/§8 (itens que este plano precisava fechar):**
- §5 Hero: Task 28 (headline, frase de acerto do ledger com corte em n<20, CTA duplo, talão real, some se não houver nenhum — o `talaoProva` fica `null` e a seção não renderiza).
- §5 `/banca`: já fechado na fase 3 (Task 17 do plano 1) — sem tarefa nova aqui.
- §5 `/desempenho`: Task 25 (ordem desfecho→calibração, filtros na URL, período por extenso, retorno honesto quando `null`, calibração com leitura em uma frase + tabela sr-only, por liga com "amostra curta").
- §5 `/desempenho`, retorno em dinheiro: Task 25-bis (decisão do dono, opção a — retorno retroativo calculado no cliente com o stake de hoje sobre picks fechados; honesto quando banca indefinida ou sem picks com preço).
- §5 `/glossario`: Task 30 (dez termos, âncora por id, sem busca).
- §5 estados vazios/erro transversais: "sem picks fechados" coberto na Task 25; os demais (dia sem jogos, backend fora, liga sem dados, `/jogos/[id]` inexistente, Mistral indisponível) já são da fase 3 (plano 1) — não repetidos aqui, só o de `/desempenho` que é novo desta fase.
- §8 fase 4 (Ontem no feed, `/desempenho`): Tasks 20, 20-bis, 21-27.
- §8 fase 5 (Hero, redirect por cookie, `/glossario`, navegação final, links contextuais): Tasks 25-bis, 28-33.
- §8 fase 6 (rodada 2, `/jogos` padrão, backup antes de apagar, corte do legado): Tasks 34-39.
- §7 fonte única (`ResumoDoDia` de `/ontem` == agregado de `/desempenho` no mesmo período): ambos leem exclusivamente `/ledger/dia`/`/ledger/agregado`, nenhum recomputa — arquitetural, não precisa de teste de igualdade adicional porque não há dois caminhos de cálculo (só um: o backend).
- §7 axe: Task 26 estende `a11y.spec.ts` (fase 3) para `/jogos?dia=ontem` e `/desempenho`.

**Itens da spec deliberadamente fora deste plano (declarados, não esquecidos):** segmented control "Dia | Rodada" (decisão de projeto #5) e margem estatística por pick na escala de confiança (decisão de projeto #4) — ambos abaixo, como perguntas para o dono.

**Varredura de placeholder:** nenhum "TBD"/"implementar depois" ficou em passo de código; os únicos campos em branco propositais são o molde de resultado da Task 36 (que só o dono preenche, com números reais de pessoas de verdade) e o hash de commit da Task 34/39 (preenchido no momento da execução, não pode ser escrito antes de o backup existir).

**Consistência de nomes:** `JogoView`/`PickView`/`escolherTalao` (fase 2), `Talao`/`CardJogo`/`Detalhe`/`EscalaConfianca`/`TabelaMercados`/`feedUrl.ts`/`Feed.tsx` (fase 3) são consumidos pelos nomes exatos do plano 1, nunca redefinidos. `getLedgerDia`/`getLedgerAgregado`/`LedgerPick`/`LedgerDia`/`LedgerAgregado` (Task 20) são usados com a mesma grafia em todas as tarefas seguintes (21, 22, 24, 25, 28). `resolvidos` (Task 20-bis) é o mesmo nome do campo Python (`_resumo`/`_segmento`/`agregado()`) e do campo TypeScript (`LedgerResumo`/`LedgerSegmento`/`LedgerAgregado.acerto`) — sem tradução no meio do caminho.

### Revisão de código — fixes aplicados nesta rodada

Um segundo revisor (com acesso ao plano 1 e aos contratos de backend) encontrou 4 problemas de precisão numérica/código incompleto e 2 menores. Todos corrigidos in-place:

- **Denominador inválido para "de cada 100 picks" (crítico).** `acertos/jogos` podia passar de 100% (medido em produção: 38 acertos em 37 jogos — múltiplos picks acertando na mesma partida). Adicionada a **Task 20-bis** (backend, nova): `_resumo`/`_segmento`/`agregado()["acerto"|"por_familia"|"por_liga"]` ganham `resolvidos` (picks individuais com desfecho, sempre ≥ `acertos`). `LedgerResumo`/`LedgerSegmento`/`LedgerAgregado.acerto` (Task 20) ganham o campo; `Painel.tsx` e `TabelaSegmentos` (Task 25) passam a dividir por `resolvidos`, nunca por `jogos`/`n_jogos`; a fixture de `/desempenho` foi reconstruída com aritmética conferida à mão (comentário ao lado de cada número) e a asserção do e2e mudou de "38 de cada 100 picks" (impossível) para "63 de cada 100 picks fechados" (`38/60`).
- **`nJogos` só migrado em um dos dois lugares (importante).** `Detalhe.tsx` (plano 1) passa `confianca?.nSamples` duas vezes — `EscalaConfianca` e `DeOndeVemONumero`. A Task 24 agora mostra as DUAS chamadas migradas para `nJogosLedger`, com um teste que prova que nenhuma delas mostra o valor antigo (`999`, um `nSamples` propositalmente diferente do `n_jogos` do ledger, `40`) e que a visível (`DeOndeVemONumero`) mostra o número certo.
- **Código elíptico não transcrevível (importante).** Quatro trechos com `// ...` (Task 22 `carregar`; Task 24 `confiancaLiga.ts`, `LinhaConfianca.tsx` — achado adicional da mesma classe de problema ao reler a tarefa — e `Detalhe.tsx`) viraram "antes" (código literal do plano 1) → "substituir exatamente este trecho" → "depois" (código literal completo), sem reticências.
- **Strings novas fora de `copy.ts` (importante).** `ResumoDoDia` (Task 23), `Painel.tsx` (Task 25 — títulos e as duas mensagens de estado) e `Hero.tsx` (Task 28 — headline e os dois CTAs) tinham texto direto no JSX. Todas viraram funções/constantes em `lib/copy.ts` (`resumoDoDia`, `DESEMPENHO`, `fraseAcerto`, `HERO`), com teste próprio.
- **Mensagem de erro do feed não diferenciava o dia (menor).** `VAZIOS.feedNaoCarregou` virou função `(dia?: "ontem"|"hoje"|"amanha")`, com `"hoje"` como default (o texto que o plano 1 já testa não muda); o call site em `Feed.tsx` (Task 22) passa `url.dia` explicitamente, e o teste de `e2e/ontem.spec.ts` passou a esperar "Os jogos de ontem não carregaram."
- **Comentário aritmético errado (menor).** `0.585 − 1/1.70 ≈ −0,0032`, não `0,0026` (Task 21, teste de `escolhe o talao pela mesma regra`) — o pick de Corners naquele teste tem edge NEGATIVO, o que o comentário corrigido agora deixa explícito.

## Perguntas em aberto para o dono (Welligton)

1. **Segmented control "Dia | Rodada" (spec §3).** Não há especificação de comportamento para o modo "Rodada" em lugar nenhum da spec, e a tabela de dependências (§8) não lista essa entrega em fase nenhuma — só uma nota solta de fechamento da fase 3. Este plano não a implementa (decisão de projeto #5). Confirma que fica de fora desta leva, ou é para especificar e encaixar antes da fase 6 fechar?
2. **Margem estatística na `EscalaConfianca` (spec §4.3, "margem de 52 a 64").** Não existe cálculo de intervalo de confiança por pick em lugar nenhum do backend hoje; a Task 24 deste plano só troca `nJogos` para vir do ledger e mantém `margem={null}` (decisão de projeto #4), para não inventar uma conta estatística nova sem SDD própria. Se a margem é importante para a fase 6, precisa de uma spec de cálculo (provavelmente Wilson ou Wald sobre `buckets`) e um novo ciclo de auditoria — quer abrir isso como plano à parte?

**Resolvidas no code review deste plano (não ficam mais em aberto — viraram regra executável na tarefa):**
- **Rótulo de mercado aproximado em "ontem" (decisão de projeto #3, Task 21).** Antes: pergunta aberta sobre aceitar a aproximação. Agora: a Task 21, Step 5, tem **critério de bloqueio explícito** — acima de 10% de picks caindo no fallback genérico de `formatarSelecaoLedger`, a tarefa não fecha até cobrir os `market` mais frequentes; o percentual real medido entra no REGISTRO da Task 27; se mesmo assim ficar alto, o item vira acompanhamento fora do escopo (produtor gravar `display_label`), não uma decisão implícita.
- **Componentes órfãos da Task 37.** Antes: pergunta sobre se a lista de candidatos estava completa. Agora: o Step 3 da Task 37 guarda a saída real do `grep` por componente em `/tmp/orfaos-256.txt`, e a Task 39 cola esse conteúdo literal no REGISTRO #258 — a prova de "zero importador fora do próprio arquivo" fica registrada, não apenas afirmada.
