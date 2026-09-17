# e2e/fixtures/feed.json

Fonte do 5º item (`matches[4]`): `frontend/next/tests/fixtures/fixtures.2026-09-15.v1.json`, jogo
`la-liga-Levante UD-Athletic Club Bilbao-1789587000.0` (copiado verbatim — task 32-bis, #257).
Cobre a regra "dois valem, um talão" com 3 mercados avaliados de verdade (`mercados`) + 12
`stats.rejected_insights` (NO_BET) → `totalAvaliados = 15`, `totalValem = 2` (Cartões Under 4.5
SAFE edge 0,1096 = talão; BTTS — SIM NEUTRO_QUALIFICADO edge 0,0422 = segundo; Over 2.5 gols
NEUTRO não vale) — conferido em `jogoView.ts` (ver `multi-mercado.spec.ts`).

Desvio do brief: `datetime` foi para `2026-12-03T19:30:00Z`, não o mesmo dia (`2026-12-01`) dos
outros jogos agendados do fixture — `matches[2]` já é um "Levante UD"×"Athletic Club Bilbao" com
essa data (estado `nada`, `mercados: []`) e `deduplicateMatches` (`normalizeMatch.ts`) funde por
`time+time+data` (sem olhar `id`); mesma data colidiria e apagaria o card `nada` original em vez
de somar um 5º card. Data diferente, ainda futura e `scheduled`, evita a fusão e preserva os 4
estados existentes intactos.
