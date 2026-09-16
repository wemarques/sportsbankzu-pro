# Fixtures pinadas — 2026-09-15 + amanhã

## Resumo

**8 jogos cobrindo todos os estados que jogoView deriva:**

Capturados em 2026-09-16 via:
- 3 jogos 2026-09-15 (finished): `/fixtures?leagues=championship,...&date=today`
- 5 jogos 2026-09-16 (scheduled): `/fixtures?leagues=mls,brasileirao-serie-a,...&date=tomorrow`

| # | ID | Liga | Data/Status | Mercados | Rejected | Classifications | Estado ilustrado |
|---|---|------|-------------|----------|----------|---|---|
| 0 | Middlesbrough-Millwall | championship | 2026-09-15T18:45Z / finished | ✓ | ✓ | SAFE, NEUTRO | vale (SAFE) |
| 1 | Bristol City-Lincoln City | championship | 2026-09-15T19:45Z / finished | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | direcao (NEUTRO) |
| 2 | Ajax-Willem II | eredivisie | 2026-09-15T... / finished | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | direcao (NEUTRO) |
| 3 | Botafogo-Grêmio | brasileirao-serie-a | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO | amanha_sem_preco (scheduled) |
| 4 | Atlético Madrid-Osasuna | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO_QUALIFICADO, NEUTRO | direcao (NEUTRO) |
| 5 | Deportivo La Coruña-Sevilla | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | NEUTRO | amanha_sem_preco (scheduled) |
| 6 | Levante-Athletic Bilbao | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | SAFE, NEUTRO_QUALIFICADO, NEUTRO | vale + direcao |
| 7 | Barcelona-Racing Santander | la-liga | 2026-09-16T... / scheduled | ✓ | ✓ | SAFE, NEUTRO | vale (SAFE) |

## Cobertura de estados (conforme jogoView)

- **vale (SAFE ou NEUTRO_QUALIFICADO)**: ✓ Jogos 0, 6, 7 têm SAFE
- **direcao (NEUTRO)**: ✓ Todos os jogos têm NEUTRO
- **nada (NO_BET)**: ✓ Provado por `stats.rejected_insights` em todos (8/8) — NO_BET nunca atinge `mercados` (ev_classification.py:743)
- **amanha_sem_preco (scheduled, mercados vazios ou com book_odd null)**: ✓ Jogos 3, 5 têm status=scheduled
- **em_jogo (live)**: Não capturado (não houve live na data)

## Campos verificados

Cada mercado em `mercados[]` contém: `mercado`, `classification`, `ev`, `edge`, `fair_odd`, `book_odd`, `calibrated_probability`, `reason_codes`.

- `fair_odd`: Presente em todos os mercados (ativos ou bloqueados)
- `book_odd`: Presente quando `odds_available: true`; `null` quando ausente (sem violação de contrato)

NO_BET markets residem em `stats.rejected_insights[]` com reason codes (`NEGATIVE_EV`, `INSUFFICIENT_EDGE`, etc.) — contendo o mesmo dicionário de mercado, apenas não selecionado para o talão.
