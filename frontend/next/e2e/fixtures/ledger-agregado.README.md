# `ledger-agregado.json` — proveniência (Task 25, R1)

**REAL**, não sintética. Construída em 2026-09-16 a partir de 15 requisições GET (somatepto do orçamento de 20 do controller):

1. `GET /ledger/agregado?periodo=temporada` (1 requisição) na Function URL de produção. Confirma que o backend em produção (`cf62142`, ainda não deployado) **não** devolve `resolvidos` em nenhum nível (`acerto`, `por_familia`, `por_liga`) — só `picks`, `acertos`, `n_jogos`/`jogos`, `brier`. Todos os demais campos do fixture (`picks`, `acertos`, `jogos`/`n_jogos`, `brier`, `buckets`) vieram **literalmente** dessa resposta, sem edição.
2. `GET /ledger/dia?data=D` para D = 2026-09-03 .. 2026-09-16 (14 requisições, uma por dia da temporada até hoje). Cada dia devolve `picks: LedgerPick[]` com `classification`, `outcome` (`0|1|null`), `familia`, `league_id`, `match_id`.

## Derivação de `resolvidos`

`resolvidos` = contagem de `LedgerPick` com `outcome != null`, filtrando primeiro por `classification ∈ {SAFE, NEUTRO_QUALIFICADO}` — esse filtro foi descoberto batendo `82` (o `acerto.picks` do agregado) contra a soma bruta das 14 respostas diárias: soma bruta = 489 picks (não bate); separando por classificação, `NEUTRO=407, NEUTRO_QUALIFICADO=52, SAFE=30` → `52+30=82` bate exatamente. Confirma que `/ledger/agregado` conta só SAFE+NQ.

Com esse filtro aplicado nas 14 respostas diárias e somando por dia:

- **Total:** `picks=82, resolvidos=78, acertos=42`, `jogos` (match_id distintos entre os resolvidos) `=46`. `acertos=42` e `jogos=46` batem **exatamente** com os valores devolvidos pelo agregado real (`acerto.acertos=42, acerto.jogos=46`) — validação cruzada independente de que a metodologia de derivação reproduz o que o backend já calcula, só faltando persistir/expor `resolvidos`.
- **Por família:** `n_jogos` derivado bateu exatamente com o `n_jogos` do agregado real em toda família com picks (Over/Under 31, Cards 19, BTTS 8, Corners 11) — mesma checagem cruzada.
  - Over/Under: `resolvidos=37` (todos os 37 picks já têm desfecho)
  - Cards: `resolvidos=20` (de 21 picks — 1 pendente)
  - BTTS: `resolvidos=8` (de 11 — 3 pendentes)
  - Corners: `resolvidos=13` (todos os 13)
- **Por liga:** mesma checagem cruzada bateu em toda liga com picks > 0 (ex.: mls `n_jogos=18` real vs. derivado 18; brasileirao-serie-b `n_jogos=6` vs. derivado 6). `resolvidos` por liga: `mls=37, brasileirao-serie-b=9, liga-mx=10, serie-a=4, championship=4, premiership=4, colombian-primera-a=2, eredivisie=2, league-one=2, brasileirao-serie-a=1, primeira-liga=1, la-liga=1, superliga=1`; ligas com `picks=0` no agregado real ficam com `resolvidos=0`.
- **`buckets`:** soma de `n` = `13+35+20+8+2 = 78` = `acerto.resolvidos` (78) — bate com a regra do brief ("a soma tem que bater com `resolvidos`, não com `jogos`"), porque cada bucket conta PICKS resolvidos, não partidas.

## Aritmética das strings do e2e (à mão, a partir do fixture acima)

- Acerto geral: `42 / 78 = 0,538461...` → `fmtPct` (`Math.round(p*100)`) → `Math.round(53.8461) = 54` → **"54 de cada 100 picks fechados · 46 jogos"**.
- Por família, Over/Under: `25 / 37 = 0,675675...` → `Math.round(67.5675) = 68` → **68%**.
- Por liga, mls: `20 / 37 = 0,540540...` → `Math.round(54.054) = 54` → **54%**.
- Calibração — maior desvio `|prob_media − freq_real|` entre os 5 buckets com `n>0`:
  - 0,5761 vs 0,4615 → 0,1146
  - 0,6506 vs 0,4571 → 0,1935
  - 0,7362 vs 0,65 → 0,0862
  - 0,8569 vs 0,75 → 0,1069
  - 0,9042 vs 0,5 → **0,4042** (maior — só 2 jogos nesse bucket, amostra pequena, desvio real de produção)
  - `fmtPct(0.9042)=90`, `fmtPct(0.5)=50` → frase esperada: **"quando o painel disse 90, aconteceu 50 em cada 100"**.
- `periodoPorExtenso("temporada", qualquer data)` é fixo em `"03/09–hoje"` (início da temporada hardcoded no brief, não depende do fixture). A tela abre com `periodo=30d` por padrão (nenhum parâmetro na URL) — `periodoPorExtenso("30d", hoje real do teste)`, que em 2026-09-16 é `"17/08–hoje"` (mesma conta do teste unitário de `desempenhoUrl.test.ts`, não injetada, o e2e roda no dia real).

## Limitação documentada

O stub do e2e (`**/api/ledger/agregado**`) responde ao mesmo fixture para qualquer combinação de `periodo|familia|liga` da querystring — os números acima vieram de uma consulta real `periodo=temporada`, mas o teste principal navega para `/desempenho` (padrão `periodo=30d`). O rótulo "17/08–hoje" exibido vem de `periodoPorExtenso(url.periodo, hoje)`, que é puro e não lê o payload — não há inconsistência visível, mas o dado numérico exibido tecnicamente é da temporada inteira, não dos últimos 30 dias. Aceito porque (a) o objetivo do teste é provar que a tela usa `resolvidos` como denominador e mostra retorno null honestamente, não validar filtragem por período no backend (isso é coberto pelo contrato de `getLedgerAgregado`, já teste em `ledgerApi`), e (b) qualquer refinamento exigiria estubar respostas diferentes por querystring, o que o `route.fulfill` único do brief não faz.
