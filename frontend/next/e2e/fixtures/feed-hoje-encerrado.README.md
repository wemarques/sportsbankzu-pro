# e2e/fixtures/feed-hoje-encerrado.json + ledger-dia-hoje.json (#261)

Par usado só por `e2e/hoje-desfecho.spec.ts`, via `page.route` local no próprio spec (não passa por
`stub()`/`e2e/helpers/stub.ts` — segue o mesmo padrão que `ontem.spec.ts` já usa para estubar
`**/api/ledger/dia**` com fixture próprio). Não editam `feed.json`/`feed-multi.json`/`ledger-dia.json`
nem nenhum outro fixture existente.

**Base real:** `id`/`leagueId`/times/`datetime`/`score`/`odds`/`stats` de `matches[0]` do jogo real
Cuiabá × Náutico capturado em 2026-09-21 (mesma fonte de `tests/unit/fixtures/producao-2026-09-21-cuiaba-nautico-*.json`
— ver README lá para a URL exata e a data de captura).

**Adaptado (não é captura verbatim) — e por quê:** o jogo real, na consulta feita em 22/09, não tinha
nenhum mercado `SAFE`/`NEUTRO_QUALIFICADO` (`mercados` real: 2 itens, ambos `NEUTRO` — o pipeline
recalcula `/fixtures` a cada chamada, então a classificação vista hoje não é a publicada no momento do
apito). Sem um talão `vale`, o card nunca mostra a faixa `✓ fechou com…`/`✗ fechou com…` (`CardJogo.tsx`:
a faixa só aparece com `jogo.talao` presente), então o cenário de aceite da #261 ("card mostra a faixa")
não tem exemplo real disponível nesta data. `feed-hoje-encerrado.json` troca o único item de `mercados`
por um `SAFE` sintético (`Escanteios Over 6.5`, `book_odd 1.75`, `fair_odd 1.67`) mantendo liga/times/
kickoff/`status: "finished"` reais; `ledger-dia-hoje.json` tem um pick real-mente-formatado (mesmos
campos e formato de `/ledger/dia`) para o mesmo jogo, mesmo mercado (`Corners`/`Corners Over 6.5`, que
`formatarSelecaoLedger` converte para o mesmo texto `Escanteios Over 6.5` do talão), com `outcome: 1` e
`detail: "8 escanteios"`.

Os três casos de aceite do brief:
1. **Desfecho no ledger** → `page.route("**/api/ledger/dia**", ...)` devolve `ledger-dia-hoje.json` →
   card mostra `✓ fechou com 8 escanteios`.
2. **Ledger sem desfecho** → sem override local de `/api/ledger/dia`, cai no fallback de `stub()`
   (`e2e/helpers/stub.ts`, picks sempre `[]`) → nenhum pick casa → "resultado ainda não conferido".
3. **Ledger fora do ar (503)** → `page.route` devolve 503 → mesmo texto do caso 2, sem `erro` na tela
   (o feed é a fonte primária; o ledger é enriquecimento).
