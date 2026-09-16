# Fixtures pinadas — 2026-09-15 + amanhã

## Resumo

**8 jogos cobrindo todos os estados que jogoView deriva:**

Capturados em 2026-09-16 via:
- 3 jogos 2026-09-15 (finished): `/fixtures?leagues=championship,...&date=today`
- 5 jogos 2026-09-16 (scheduled): `/fixtures?leagues=mls,brasileirao-serie-a,...&date=tomorrow`

| # | ID | Liga | Data/Status | Mercados | Rejected | Classifications | Estado (toJogoView, agora=2026-09-15T12:00Z) |
|---|---|------|-------------|----------|----------|---|---|
| 0 | Middlesbrough-Millwall | championship | 2026-09-15T18:45Z / finished | ✓ | ✓ | SAFE, NEUTRO | ontem_sem_desfecho |
| 1 | Bristol City-Lincoln City | championship | 2026-09-15T19:45Z / finished | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | ontem_sem_desfecho |
| 2 | Ajax-Willem II | eredivisie | 2026-09-15T... / finished | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | ontem_sem_desfecho |
| 3 | Botafogo-Grêmio | brasileirao-serie-a | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO | direcao |
| 4 | Atlético Madrid-Osasuna | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | vale |
| 5 | Deportivo La Coruña-Sevilla | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO | direcao |
| 6 | Levante-Athletic Bilbao | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | SAFE, NEUTRO_QUALIFICADO, NEUTRO | vale |
| 7 | Barcelona-Racing Santander | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | SAFE, NEUTRO | vale |

Fonte: `estado` por jogo lido de `frontend/next/tests/unit/__snapshots__/jogoView.test.ts.snap` (bloco "snapshot do fixture real"), na ordem do JSON.

## Cobertura de estados (conforme jogoView)

`EstadoJogo` tem 7 valores. Esta fixture, com `AGORA=2026-09-15T12:00:00Z`, cobre 3 deles com jogo real; os outros 4 não ocorrem neste JSON e só são exercitados por casos sintéticos em `tests/unit/jogoView.test.ts`.

- **ontem_sem_desfecho**: ✓ jogo real — jogos 0, 1, 2 (finished, sem resultado do ledger)
- **direcao (só NEUTRO, sem talão)**: ✓ jogo real — jogos 3, 5 (têm mercado NEUTRO com `book_odd` presente; sem SAFE/NEUTRO_QUALIFICADO)
- **vale (SAFE ou NEUTRO_QUALIFICADO)**: ✓ jogo real — jogos 4, 6, 7
- **amanha_sem_preco**: ✗ não coberto por jogo real. Os jogos 3 e 5 têm `datetime` futuro e `book_odd: null`, mas isso só produz `amanha_sem_preco` quando existe talão (SAFE/NEUTRO_QUALIFICADO) com `book_odd` nulo; como 3 e 5 só têm mercado NEUTRO, `talao` é `null` e o estado cai em `direcao`. Coberto por caso sintético em `jogoView.test.ts` ("amanha sem preco").
- **nada (NO_BET)**: ✗ não coberto por jogo real neste snapshot — nenhum dos 8 jogos cai em `nada` com `AGORA` fixado (todos têm talão ou NEUTRO). NO_BET em si é provado via `stats.rejected_insights` nos 8 jogos (NO_BET nunca atinge `mercados`, `ev_classification.py:743`), mas o *estado* `nada` da view é coberto só por dois casos sintéticos em `jogoView.test.ts` ("nada: so NO_BET" e "nada: mercados vazio").
- **em_jogo (live)**: ✗ não coberto por jogo real (não houve live na data). Coberto por caso sintético em `jogoView.test.ts` ("em jogo").
- **ontem (com placar do ledger)**: ✗ não coberto por jogo real nem por caso sintético. O `switch` em `src/lib/jogoView.ts` nunca atribui este valor hoje — só produz `ontem_sem_desfecho` para jogos passados/finalizados; `"ontem"` está no enum `EstadoJogo` mas é inalcançável na implementação atual.

## Campos verificados

Cada mercado em `mercados[]` contém: `mercado`, `classification`, `ev`, `edge`, `fair_odd`, `book_odd`, `calibrated_probability`, `reason_codes`.

- `fair_odd`: Presente em todos os mercados (ativos ou bloqueados)
- `book_odd`: Presente quando `odds_available: true`; `null` quando ausente (sem violação de contrato)

NO_BET markets residem em `stats.rejected_insights[]` com reason codes (`NEGATIVE_EV`, `INSUFFICIENT_EDGE`, etc.) — contendo o mesmo dicionário de mercado, apenas não selecionado para o talão.
