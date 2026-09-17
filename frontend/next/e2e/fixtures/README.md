# e2e/fixtures/feed.json e feed-multi.json

`feed.json` é o fixture padrão (4 jogos) — usado por `stub()` sem opções (todos os specs, exceto
`multi-mercado.spec.ts`) e **intocado** por esta task (fix round 1: restaurado ao conteúdo de
`4055130`, `git show 4055130:frontend/next/e2e/fixtures/feed.json`).

`feed-multi.json` = os mesmos 4 jogos de `feed.json` + um 5º item (`matches[4]`), fonte
`frontend/next/tests/fixtures/fixtures.2026-09-15.v1.json`, jogo
`la-liga-Levante UD-Athletic Club Bilbao-1789587000.0` (copiado verbatim — task 32-bis, #257).
Servido só quando o teste chama `stub(page, { feed: "multi" })` (`e2e/helpers/stub.ts`), o que
mantém `feed.json`/todos os outros specs (`jogos.spec.ts`, `visual.spec.ts`, `a11y.spec.ts`) em 4
jogos, sem regressão de contagem.

Cobre a regra "dois valem, um talão" com 3 mercados avaliados de verdade (`mercados`) + 12
`stats.rejected_insights` (NO_BET) → `totalAvaliados = 15`, `totalValem = 2` (Cartões Under 4.5
SAFE edge 0,1096 = talão; BTTS — SIM NEUTRO_QUALIFICADO edge 0,0422 = segundo; Over 2.5 gols
NEUTRO não vale) — conferido em `jogoView.ts` (ver `multi-mercado.spec.ts`).

Desvio do brief: `datetime` foi para `2026-12-03T19:30:00Z`, não o mesmo dia (`2026-12-01`) dos
outros jogos agendados do fixture — `matches[2]` já é um "Levante UD"×"Athletic Club Bilbao" com
essa data (estado `nada`, `mercados: []`) e `deduplicateMatches` (`normalizeMatch.ts`) funde por
`time+time+data` (sem olhar `id`); mesma data colidiria e apagaria o card `nada` original em vez
de somar um 5º card. Data diferente, ainda futura e `scheduled`, evita a fusão e preserva os 4
estados existentes intactos — o card do jogo novo em `multi-mercado.spec.ts` ainda precisa se
desambiguar do `matches[2]` por texto (mesmos nomes de time), pois ambos aparecem juntos em
`feed-multi.json`.
