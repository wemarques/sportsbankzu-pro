# Fixtures pinadas — 2026-09-15

## Resumo

Capturado em 2026-09-16T01:17:23.702Z via `/fixtures?leagues=championship,bundesliga,eredivisie&date=today` (data de jogo = 2026-09-15).

3 jogos, cobrindo:

| ID (league-home-away) | Data | Status | Classifications presentes | Observações |
|---|---|---|---|---|
| championship-Middlesbrough-Millwall | 2026-09-15T18:45:00Z | finished | NEUTRO_QUALIFICADO | 2 mercados |
| championship-Preston-Bristol City | 2026-09-15T19:45:00Z | finished | SAFE | SAFE em "Over 2.5 gols"; 1 mercado NEUTRO_QUALIFICADO |
| bundesliga-Mainz-Freiburg | 2026-09-15T14:30:00Z | finished | NEUTRO_QUALIFICADO, SAFE | Mixed classifications |

## Cobertura de estados

- **SAFE**: Sim (Preston vs Bristol City, "Over 2.5 gols")
- **NEUTRO**: Sim (via NEUTRO_QUALIFICADO em todos os jogos)
- **NO_BET**: **Não encontrado** — Padrão #254-a ainda em evolução ou requer estado específico de dados que não estava no date=today.

## Campos verificados

Cada mercado contém: `mercado`, `classification`, `ev`, `edge`, `fair_odd`, `book_odd`, `calibrated_probability`, `reason_codes`.

Nota: `fair_odd` está presente em todos; `book_odd` ausente em alguns mercados com `odds_available: false` (conforme padrão).
