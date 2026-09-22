# tests/unit/fixtures/ — par real Cuiabá × Náutico (#261)

Capturado em 2026-09-22, leitura pura (sem mutação), contra a Lambda de produção:

- `producao-2026-09-21-cuiaba-nautico-feed.json`: `GET .../fixtures?leagues=brasileirao-serie-b&date=2026-09-21`
  (`matches[0]`, o único jogo da liga nessa data). Reduzido: `odds` cortado às chaves 1X2/O-U 2.5/BTTS,
  `stats` cortado a `avgGoals` + `rejected_insights: []` (a lista real tinha 11 itens, nenhum usado pelos
  testes deste arquivo), `mercados` mantido inteiro (2 itens, ambos `NEUTRO` — nenhum mercado deste jogo
  específico fechou como `SAFE`/`NEUTRO_QUALIFICADO` na consulta ao vivo de 22/09; o pipeline recalcula
  `/fixtures` a cada chamada, então a classificação vista agora não é necessariamente a publicada no ledger
  no momento do apito — comportamento preexistente, não introduzido por esta task). Campos como
  `corner_governance`, `banda`, `_mistral_context` foram removidos por não afetarem `mesmoJogo`/`toJogoView`
  nestes testes.
- `producao-2026-09-21-cuiaba-nautico-ledger.json`: `GET .../ledger/dia?data=2026-09-21` (11 picks reais para
  este `match_id`; reduzido a 3, um por família de mercado presente — `Corners Over 4.5` (outcome 1, "11
  escanteios"), `Cards Over 2.5` (outcome 0, "2 cartões"), `Over/Under Under 3.5` (outcome 1, "3 gols") —
  linhas mantidas verbatim, sem editar valor algum.

`match_id` do ledger e `id` do fixture são **idênticos** neste par real (mesmo formato, epoch com `.0`) —
prova que o casamento por liga+kickoff+times funciona quando os ids batem. A prova de que `mesmoJogo` **não**
depende de os ids baterem (a divergência de formato que motivou a #261, exemplificada na spec com
`championship-Middlesbrough-Millwall-1798920000` vs. `...-1789415100.0`) está em
`tests/unit/ledgerCasamento.test.ts`, com pares sintéticos onde o sufixo epoch do id do feed não tem `.0` e o
do ledger tem — mesmo jogo, ids com formato diferente.

Nenhum pick deste jogo real tem `classification` `SAFE`/`NEUTRO_QUALIFICADO` — por isso não serve para
provar o cenário de aceite "card mostra a faixa `✓ fechou com…`" (que exige um talão vale + outcome
resolvido). Esse cenário é coberto em `e2e/fixtures/feed-hoje-encerrado.json` +
`e2e/fixtures/ledger-dia-hoje.json` (ver README ao lado), adaptados a partir da estrutura real deste mesmo
jogo — README lá documenta exatamente o que foi adaptado e por quê.
