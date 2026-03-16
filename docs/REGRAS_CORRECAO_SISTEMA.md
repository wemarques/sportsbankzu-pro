# Registro de Correções de Regras do Sistema

> **Objetivo:** Este arquivo documenta correções aplicadas ao sistema que devem ser consultadas quando erros semelhantes ocorrerem. Cada entrada descreve o problema, a causa raiz e as camadas de correção implementadas.

---

## 001 — Defesa contra odds alucinadas pela Mistral

**Data:** 2026-03-10
**Arquivos afetados:** `backend/services/mistral_analysis.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

O prompt da Mistral só passava 5 odds básicas (Casa, Empate, Fora, Over 2.5, BTTS Sim), mas não incluía Under 4.5 nem muitos outros mercados. A instrução dizia para "recomendar com mercado e odd" sem restringir às odds reais. Resultado: a IA inventava odds — ex: "Under 4.5 @1.95" — odd que não existia no mercado.

### Causa raiz

Falta de restrição no prompt + ausência de validação pós-processamento. A Mistral gerava recomendações com odds arbitrárias porque não havia constraint nem verificação.

### Correções aplicadas (3 camadas)

1. **Prompt expandido** — Agora passa 10 mercados de odds (Over 1.5–4.5, Under 2.5, BTTS Sim/Não) + instrução explícita: _"NAO invente odds que não estejam listadas"_.

2. **Instrução rígida no prompt** — _"A odd na recomendação DEVE ser uma das odds listadas em ODDS DO MERCADO. Se a odd de um mercado é N/A, NAO recomende esse mercado."_

3. **Validação pós-processamento** — Novo método `_validate_recommendation_odd()` que:
   - Extrai a odd da recomendação (ex: `@1.95`)
   - Compara com todas as odds reais (tolerância ±0.02)
   - Se encontra match → mantém
   - Se o mercado existe mas odd está errada → substitui pela odd real
   - Se o mercado não tem odd disponível → remove a odd falsa

### Lição aprendida

Nunca confiar que um LLM vai respeitar constraints implícitos. Sempre aplicar **defesa em profundidade**: instrução clara no prompt + validação programática na saída. Conforme a regra de investigação do projeto (CLAUDE.md), implementar guards em cada camada relevante.

---

## 002 — Reincidência: Under 4.5 @1.95 ainda alucinada (reforço da defesa)

**Data:** 2026-03-10
**Arquivos afetados:** `backend/services/mistral_analysis.py`
**Severidade:** Alta
**Status:** Corrigido
**Relacionado:** #001

### Problema identificado

Apesar da correção #001, a Mistral continuou inventando "Under 4.5 @1.95". O prompt listava 10 mercados mas **não incluía Under 3.5 nem Under 4.5** porque o `fixtures_service.py` não retorna essas keys nas odds (só retorna `over35`, `over45`, `under25`). A validação não encontrava "Under 4.5" no dict de odds reais, e apenas removia o `@1.95` — mas o mercado fantasma permanecia. Além disso, os `key_points` citavam odds falsas sem nenhuma validação.

### Causa raiz

1. **Odds Under derivadas não existiam no dict** — O sistema calcula Under 3.5/4.5 em `main.py` e `market_service.py` via `calcular_odd_under()`, mas esse valor nunca era passado no dict de odds para o Mistral
2. **Prompt não listava Under 3.5/4.5** — A Mistral via probabilidades `under35Prob`/`under45Prob` nos stats, sabia que o mercado existia, mas não tinha a odd real → inventava
3. **key_points sem validação** — Odds falsas apareciam nos pontos-chave sem ser sanitizadas

### Correções aplicadas (4 camadas)

1. **`_derive_under_odd()` novo método** — Calcula Under 3.5 e Under 4.5 a partir das odds Over correspondentes (fórmula complementar com margem de 5%), igual ao `calcular_odd_under()` do `market_service.py`

2. **Prompt expandido para 12 mercados** — Agora lista Under 3.5 e Under 4.5 com odds derivadas (ou N/A se Over não disponível). Adicionada instrução extra: _"Se um mercado mostra N/A, ele NAO esta disponivel"_ e _"Nos key_points, NAO cite odds de mercados que nao estejam listados"_

3. **Validação enriquecida** — `_validate_recommendation_odd()` agora deriva under35/under45 antes de buscar match, garantindo que "Under 4.5" encontra uma odd real derivada

4. **`_sanitize_key_points()` novo método** — Varre todos os key_points, extrai odds mencionadas (padrões `odd de X.XX`, `@X.XX`, `com odd X.XX`) e remove referências a odds que não existem nas odds reais

### Lição aprendida

A defesa em profundidade deve cobrir **todos os campos de saída**, não só o `recommendation`. Os `key_points` são narrativa livre e o LLM pode inserir odds inventadas em qualquer lugar. Além disso, se o sistema calcula um valor derivado internamente (Under a partir de Over), esse valor **deve ser passado ao LLM** — caso contrário o LLM sabe que o mercado existe (via probabilidades) mas não tem a odd real, e inventa.

---

## 003 — Integração API-Football v3 como fonte de dados complementar

**Data:** 2026-03-11
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/config/leagues_config.py`, `backend/routes/fixtures.py`, `backend/routes/live.py`, `backend/main.py`
**Severidade:** Média (melhoria de cobertura de dados)
**Status:** Implementado

### Problema identificado

O sistema dependia exclusivamente da FootyStats API como fonte de dados primária. Quando a FootyStats falhava (rate limit, manutenção, dados incompletos), os placares ao vivo ficavam indisponíveis e não havia fallback confiável. Além disso, dados como escalações, eventos de jogo (gols/cartões), estatísticas detalhadas de partida e lesões/suspensões não eram exibidos no dashboard principal — apenas na análise de IA.

### Causa raiz

O client da API-Football (`api_football_client.py`) existia mas era usado apenas na rota de análise de IA (`ai_analysis.py`) para consultas pontuais por jogo. Não havia:
1. Cache para evitar chamadas repetitivas
2. Suporte síncrono para uso no `ThreadPoolExecutor` do fixtures
3. Endpoints para standings, statistics, odds, H2H, lineups, events
4. Mapeamento de IDs das ligas internas para IDs numéricos da API-Football
5. Lógica de enrichment para sobrepor dados ao vivo sobre registros da FootyStats
6. Rotas dedicadas para dados ao vivo

### Correções aplicadas (5 camadas)

1. **Mapeamento de league IDs** (`leagues_config.py`) — Criado `API_FOOTBALL_LEAGUE_IDS` com 34 ligas mapeadas + helper `get_api_football_league_id()` para conversão automática de IDs internos para IDs numéricos da API-Football.

2. **Client expandido** (`api_football_client.py`) — Reescrito com:
   - Cache SQLite TTL (tabela `api_football_cache`, mesmo DB `api_cache.db`)
   - Suporte síncrono via `requests` (`_get_sync()`) com retry automático para 502/503/504/429
   - Novos endpoints: `get_fixtures_by_date()`, `get_live_fixtures()`, `get_standings()`, `get_team_statistics()`, `get_fixture_statistics()`, `get_fixture_events()`, `get_fixture_lineups()`, `get_odds()`, `get_predictions()`, `get_h2h()`, `get_injuries_sync()`
   - `extract_best_odds()` — extrai melhores odds com prioridade por bookmaker (Bet365, Pinnacle, 1xBet)
   - `fixtures_to_records()` — converte fixtures da API-Football para formato interno (usado como fallback)
   - `enrich_fixture_record()` — sobrepõe dados ao vivo sobre registros existentes da FootyStats

3. **Enrichment no fixtures route** (`fixtures.py`) — Nova função `_enrich_with_api_football()` que:
   - **Caso 1 (registros existem)**: busca fixtures da API-Football para a mesma liga/data e sobrepõe status, placar e minuto ao vivo (match por nome de time, tolerante a variações)
   - **Caso 2 (nenhum registro)**: usa API-Football como fallback completo, gerando registros com odds e probabilidades implícitas

4. **Rota live dedicada** (`routes/live.py`) — Novos endpoints:
   - `GET /live` — todos os jogos ao vivo (filtrável por liga)
   - `GET /live/fixture/{id}` — dados detalhados de um jogo (estatísticas, eventos, escalações, lesões)
   - `GET /live/standings` — classificação da liga via API-Football

5. **Wiring** (`main.py`) — Registro do router `live` na aplicação FastAPI.

### Configuração necessária

- **Variável de ambiente**: `API_FOOTBALL_KEY` — chave da API-Football v3
- **Onde configurar**: `.env` (local), Lambda (env vars), Vercel (env vars)
- **Comportamento sem chave**: sistema funciona normalmente, ignora chamadas à API-Football (graceful degradation)

### Regras de uso de API

- **Cache TTL padrão**: 5min (fixtures ao vivo), 30min (odds), 60min (stats/injuries), 360min (standings/H2H)
- **Retry**: 2 tentativas com 2s de backoff para status 502/503/504/429
- **Fallback chain atualizada**: FootyStats API → API-Football v3 → FootyStats todays-matches → CSV → Mock (dev only)

### Lição aprendida

Fontes de dados redundantes são essenciais em sistemas de produção. A integração foi feita em camadas independentes (client, enrichment, fallback, rota dedicada) para que cada uma possa falhar isoladamente sem afetar as demais. O cache SQLite com TTL diferenciado por endpoint evita estourar o rate limit da API-Football (100 req/dia no plano free, 7500/dia no plano pro).

---

## 004 — Auditoria API-Football: precisão de lesões, livescore e hierarquia de dados

**Data:** 2026-03-11
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/routes/ai_analysis.py`, `backend/services/mistral_analysis.py`
**Severidade:** Alta (dados imprecisos enviados à Mistral AI)
**Status:** Corrigido
**Relacionado:** #003

### Problema identificado

A integração API-Football (#003) funcionava, mas com três falhas de precisão que afetavam a qualidade da análise da Mistral AI:

1. **Lesões sem granularidade** — O endpoint `/injuries` retorna dois status distintos: `"Missing Fixture"` (desfalque confirmado) e `"Questionable"` (presença incerta). O sistema tratava ambos da mesma forma, marcando apenas `[DUVIDA]` para Questionable e nenhum tag para Missing. A Mistral não sabia diferenciar o impacto de um jogador com certeza ausente vs. um em dúvida.

2. **Cache excessivo de lesões** — A API-Football recomenda max 1 call/dia para `/injuries` (dados atualizados a cada 4h). O cache sync estava em 30 min (8x mais chamadas que o necessário), e o método async **não tinha cache nenhum** — batia na API toda vez.

3. **Busca imprecisa de fixtures** — A rota `ai_analysis.py` chamava `get_match_live_data()` sem passar `match_date`, `league_id` nem `season` — a busca na API-Football era feita apenas por nome de time na data do dia, falhando para jogos futuros/passados.

4. **Sem verificação de coverage** — Não havia checagem prévia para saber se a liga suporta dados de lesão (`coverage.injuries`). O sistema desperdiçava requests em ligas sem cobertura.

5. **Sem extração de league info** — `league.name`, `league.country` e `league.season` não eram extraídos da fixture da API-Football para contextualizar a análise.

6. **Sem hierarquia de dados** — FootyStats (fonte primária de form, H2H, stats, odds) e API-Football (fonte complementar de livescore e lesões) não tinham papéis claramente definidos. Uma falha na API-Football podia afetar o fluxo principal.

7. **Normalização fraca de nomes** — A "ponte" entre FootyStats e API-Football usava `str.lower()` + substring, falhando com variações comuns como acentos (`Atlético` vs `Atletico`), prefixos (`FC Barcelona` vs `Barcelona`), sufixos (`SC Freiburg` vs `Freiburg`).

### Causa raiz

A integração #003 focou na **infraestrutura** (client, cache, routes) mas não na **precisão dos dados** enviados ao LLM. Três lacunas:
1. O response do `/injuries` não era normalizado — o campo `player.type` era passado raw sem classificação
2. A rota de análise não extraía dados do match_data do FootyStats para alimentar a busca na API-Football
3. Não havia separação arquitetural entre fonte primária (FootyStats) e complementar (API-Football)

### Correções aplicadas (7 camadas)

#### Camada 1: Classificação de Lesões (`api_football_client.py`)
- Novo `_parse_injuries()` classifica cada jogador como `availability: "FORA"` ou `"DUVIDA"`
- Regra: `type == "Questionable"` → `DUVIDA`, tudo mais (Missing Fixture, Suspension, etc.) → `FORA`
- `_format_absences()` agora inclui o tag em cada jogador: `"Rashford (Knee) [FORA], Shaw (Hamstring) [DUVIDA]"`
- Prompt Mistral atualizado com nota explicativa: _"[FORA] = desfalque confirmado, [DUVIDA] = presença incerta"_

#### Camada 2: Cache de Lesões com TTL correto (`api_football_client.py`)
- `get_injuries()` (async) agora usa cache SQLite com TTL **240 min (4h)**, respeitando a frequência de atualização da API
- `get_injuries_sync()` TTL elevado de 30min para **240 min**
- Cache key baseado em `fixture_id`, evitando chamadas repetidas para o mesmo jogo

#### Camada 3: Verificação de Coverage (`api_football_client.py`)
- Novo `get_league_coverage(league_id, season)` busca flags de cobertura via `/leagues` com cache **24h (1440 min)**
- Novo `has_injury_coverage(league_id, season)` verifica se a liga suporta dados de lesão
- `get_match_live_data()` checa coverage **antes** de chamar `/injuries` — pula ligas sem cobertura
- **Fail-open**: se a verificação de coverage falhar, tenta buscar lesões de qualquer forma

#### Camada 4: Extração de League Info (`api_football_client.py`)
- Novo `extract_league_info(fixture)` extrai: `league_name`, `league_country`, `league_season`, `league_id`, `league_round`
- Injetado no contexto Mistral como: _"Premier League (England, Temporada 2025) — Regular Season - 28"_
- Prompt expandido com campo _"Liga/Competicao (API-Football)"_ no bloco de contexto

#### Camada 5: Ponte FootyStats → API-Football (`ai_analysis.py`)
- A rota agora extrai `match_date`, `league_id` (via `get_api_football_league_id()`) e `season` do `match_data` do FootyStats
- Esses dados são passados para `get_match_live_data()` como parâmetros de busca precisa
- `_match_to_ai_input()` agora inclui `datetime` e `season` no output dict

#### Camada 6: Hierarquia de Dados + Graceful Degradation (`ai_analysis.py`)
- Arquitetura definida: **FootyStats = PRIMÁRIO** (form, H2H, stats, odds, lineups) / **API-Football = COMPLEMENTAR** (livescore, injuries)
- Lógica condicional com `bridge_succeeded` — só injeta dados da API-Football se a fixture foi encontrada
- Se a ponte falha: `context.setdefault()` garante que dados do FootyStats nunca são sobrescritos
- Se a API-Football lança exceção: fallback silencioso com log de warning, fluxo continua normalmente

#### Camada 7: Normalização Robusta de Nomes (`api_football_client.py`)
- Novo `_normalize_team_name()` aplica: remoção de acentos (NFKD), lowercase, remoção de prefixos (FC, SC, AC, AFC...), remoção de pontuação
- Novo `_team_names_match()` usa: match exato pós-normalização → substring containment → token overlap (≥50% dos tokens menores)
- Testado com 8 pares reais: `FC Barcelona`↔`Barcelona` ✅, `Atlético Madrid`↔`Atletico Madrid` ✅, `SE Palmeiras`↔`Palmeiras` ✅, `SC Freiburg`↔`Freiburg` ✅
- Limitação conhecida: abreviações completamente diferentes (`Wolverhampton Wanderers` vs `Wolves`) não são detectadas — requer mapeamento manual futuro

### Formato de dados enviados à Mistral (exemplo)

```
CONTEXTO ADICIONAL:
- Forma Casa (ultimos 5): W, W, D, W, L           ← FootyStats (primário)
- Forma Fora (ultimos 5): L, D, W, W, W            ← FootyStats (primário)
- Confrontos diretos: Total: 12 jogos, Casa: 5...  ← FootyStats (primário)
- Liga/Competicao: Premier League (England, Temporada 2025) — Round 28  ← API-Football
- Lesoes/Suspensoes: Man Utd: Rashford (Knee) [FORA], Shaw (Hamstring) [DUVIDA] | Liverpool: Sem ausencias
  NOTA: [FORA] = desfalque confirmado, [DUVIDA] = presenca incerta
- Status ao Vivo: Segundo tempo em andamento: 67 min, Placar: 1 - 2  ← API-Football
```

### Exemplo de JSON retornado pela rota `/api/ai/match/{id}/analysis`

```json
{
  "summary": "Análise do jogo...",
  "key_points": ["Ponto 1...", "Ponto 2..."],
  "recommendation": "Over 2.5 @1.85",
  "confidence": 78,
  "last_updated": "11/03/2026 as 14:30",
  "match_live_data": {
    "fixture_id": 1035247,
    "status": "2H",
    "status_long": "Second Half",
    "minute": 67,
    "extra_time": null,
    "score": "1 - 2",
    "goals_home": 1,
    "goals_away": 2,
    "halftime_home": 0,
    "halftime_away": 1,
    "is_live": true,
    "is_finished": false
  }
}
```

### Lição aprendida

A integração de uma API externa não termina quando o client funciona — a **precisão dos dados enviados ao LLM** é tão importante quanto a conectividade. Três princípios aplicados:
1. **Normalize na entrada** — Classificar dados brutos (`Missing Fixture` → `FORA`) antes de passá-los ao LLM
2. **Respeite a hierarquia** — Fontes de dados devem ter papéis claros (primário vs complementar) com fallbacks independentes
3. **Bridging entre APIs exige normalização** — Nomes de times variam entre providers; normalização unicode + token overlap resolve 90% dos casos sem mapeamento manual

---

## 005 — Placar ao vivo congelado em 0-0 (ponte de nomes + crash silencioso)

**Data:** 2026-03-12
**Arquivos afetados:** `backend/routes/fixtures.py`, `backend/services/api_football_client.py`
**Severidade:** Alta (placar ao vivo não atualizava)
**Status:** Corrigido
**Relacionado:** #003, #004

### Problema identificado

Placares ao vivo exibiam "0 - 0" para todos os jogos, mesmo quando o status "HT" era capturado corretamente. Exemplo: `VIVO HT | Flamengo 0 - 0 Cruzeiro`.

### Causa raiz (3 bugs independentes)

**BUG 1 — Crash silencioso no `/fixtures`:** A função `_enrich_with_api_football()` (fixtures.py:303) chamava `.lower()` em `rec.get("homeTeam")`, mas `homeTeam` é um DICT `{"name": "Flamengo", "logo": "", ...}` nos records do `build_records_from_matches`. `.lower()` num dict gera `AttributeError`, capturado pelo `except Exception` na linha 323 — o enrichment **inteiro falhava silenciosamente** para TODOS os jogos.

**BUG 2 — Matching fraco no `/live-scores`:** O overlay de API-Football (fixtures.py:988-1008) usava `.lower().strip()` + substring simples. Para times brasileiros: `"atlético mineiro"` (FootyStats, com acento) vs `"atletico-mg"` (API-Football, sem acento, abreviado) — substring match retornava `False` porque nem um é substring do outro.

**BUG 3 — Period code não mapeado:** O método `enrich_fixture_record()` (api_football_client.py:760) setava `record["period"] = af_status` com códigos da API-Football ("1H", "2H") em vez do formato interno ("1T", "2T"). O frontend não reconhecia "1H"/"2H" como períodos válidos.

### Correções aplicadas (4 camadas)

#### Camada 1: Extração segura de nome do time (`fixtures.py`)
- `_enrich_with_api_football()` agora detecta se `homeTeam`/`awayTeam` é dict ou string
- Se dict: extrai `.get("name", "")`; se string: usa `str()` direto
- Elimina o crash silencioso que matava TODO o enrichment

#### Camada 2: Matching robusto via `_team_names_match()` (`fixtures.py`)
- **Ambas** as funções de enrichment (para `/fixtures` e `/live-scores`) agora usam `_afc._team_names_match()` em vez de `.lower()` + substring
- Matching inclui: remoção de acentos (NFKD), remoção de prefixos (FC, SC, CR, SE, EC...), token overlap ≥50%
- Testado com 12 pares reais: todos os times brasileiros matcham corretamente

#### Camada 3: Prefixos brasileiros no `_normalize_team_name()` (`api_football_client.py`)
- Adicionados prefixos comuns de clubes brasileiros/sul-americanos ao regex de remoção: `cr`, `se`, `ec`, `aa`, `ce`, `gr`, `csd`, `cn`, `cu`, `rcd`, `ud`, `sd`
- Agora "CR Flamengo" → "flamengo", "SE Palmeiras" → "palmeiras", "Cruzeiro EC" → "cruzeiro"

#### Camada 4: Mapeamento de period codes (`api_football_client.py`)
- `enrich_fixture_record()` agora mapeia `1H→1T`, `2H→2T`, `BT→HT`, `P→PEN` ao setar `record["period"]`
- Alinhado com o mesmo mapeamento já usado no endpoint `/live-scores` (que funcionava corretamente)

### Pares de nomes validados

| FootyStats | API-Football | Match? |
|---|---|---|
| Atlético Mineiro | Atletico-MG | ✅ |
| CR Flamengo | Flamengo | ✅ |
| SE Palmeiras | Palmeiras | ✅ |
| SC Corinthians | Corinthians | ✅ |
| Coritiba FC | Coritiba | ✅ |
| Cruzeiro EC | Cruzeiro | ✅ |
| São Paulo | Sao Paulo | ✅ |
| Grêmio | Gremio | ✅ |
| Botafogo FR | Botafogo | ✅ |
| Internacional | SC Internacional | ✅ |
| FC Barcelona | Barcelona | ✅ |
| Atlético Madrid | Atletico Madrid | ✅ |

### Lição aprendida

Três princípios violados simultaneamente:
1. **Nunca assuma o tipo de um campo** — `homeTeam` era dict em um endpoint e string em outro. Testar com `isinstance()` antes de operar.
2. **Reutilize funções de matching** — Havia `_team_names_match()` pronta e testada, mas dois locais de enrichment usavam matching ad-hoc fraco. DRY não é só sobre código duplicado, é sobre **lógica duplicada com qualidade inferior**.
3. **Exceções silenciosas escondem bugs críticos** — O `except Exception` genérico mascarou um crash que matava 100% do enrichment. Pelo menos logar a exceção permitiria diagnóstico imediato.

---

## 006 — Auditoria marcava mercados de escanteios sempre como ERROU (dados reais não lidos)

**Data:** 2026-03-12
**Arquivos afetados:** `frontend/next/src/lib/localAudit.ts`, `frontend/next/src/lib/leagues.ts`, `backend/routes/ai_analysis.py`, `backend/cron_handler.py`
**Severidade:** Alta (100% dos picks de escanteios avaliados como erro)
**Status:** Corrigido

### Problema identificado

O relatório de auditoria marcava **todos** os mercados de escanteios (Over 8.5, Over 9.5, Over 10.5) como ERROU, mesmo quando o jogo real confirmava o acerto. Exemplo: Bahia x Vitória teve 10 escanteios no total, mas:
- "Escanteios Over 8.5" (10 > 8.5 ✅) → marcado ERROU
- "Escanteios Over 9.5" (10 > 9.5 ✅) → marcado ERROU
- "Escanteios Over 10.5" (10 > 10.5 ❌) → marcado ERROU (este correto)

Resultado: acurácia de escanteios artificialmente em 0%, com a Mistral sugerindo reduzir `corner_multiplier` baseada em dados falsos.

### Causa raiz (3 bugs independentes, mesma falha conceitual)

**BUG 1 — Frontend `evaluatePick()` não tratava escanteios (PRINCIPAL):**
A função `evaluatePick()` em `localAudit.ts` (linhas 24-73) tratava Over/Under de **gols**, BTTS, Double Chance e 1X2, mas **não tinha nenhum branch para mercados de escanteios**. A string "Escanteios Over 8.5" contém "OVER" e "8.5", o que casava com o loop de Over/Under de gols (thresholds 0.5–4.5), mas "8.5" não está nesse range → nenhum `return` era atingido → o mercado caía no `return false` final (linha 72). **100% dos picks de escanteios eram avaliados como ERROU.**

**BUG 2 — Backend `/batch-audit` sem `total_corners` no `actual_result`:**
O endpoint `batch_audit()` em `ai_analysis.py` (linha 850) construía o dict `actual_result` com `total_goals`, `btts` e `result_1x2`, mas **não extraía nem incluía `total_corners`**. A função `_evaluate_pick_deterministic()` (linha 649) fazia `actual_result.get("total_corners", 0)` → sempre recebia 0 → `0 > 8.5` = False → ERROU. **Nota:** O `cron_handler.py` na função `_run_batch_audit()` (linha 151) já incluía `total_corners` corretamente — a inconsistência entre os dois caminhos mascarava o bug dependendo de como a auditoria era disparada.

**BUG 3 — Cron handler dupla evaluation sem `total_corners`:**
A avaliação de duplas (combinadas) no `cron_handler.py` (linha 267) construía `_actual_by_id` com `total_goals`, `btts` e `result_1x2`, mas **não incluía `total_corners`**. Qualquer dupla com perna de escanteios era avaliada com 0 escanteios.

**BUG 4 — Frontend `MatchActualResult` sem `totalCorners`:**
A interface `MatchActualResult` em `localAudit.ts` (linha 433) e o lookup `actualByKey` em `computeLocalCombinadas()` (linha 456) não incluíam dados de escanteios. Todas as duplas intra-jogo e inter-jogo com escanteios eram marcadas ERROU.

**BUG 5 — Tipo TypeScript `Match.stats` sem campos de corner count:**
A interface `Match` em `leagues.ts` não declarava `homeCornersCount` nem `awayCornersCount` no objeto `stats`, apesar do backend já enviar esses campos desde a correção #003 (via `fixtures_service.py` linha 918).

### Correções aplicadas (5 camadas)

#### Camada 1: `evaluatePick()` com suporte a escanteios (`localAudit.ts`)
- Adicionado parâmetro opcional `totalCorners?: number` à assinatura
- Novo branch **antes** do loop de Over/Under de gols: detecta `"ESCANTEIO"` ou `"CORNER"` no nome do mercado
- Avalia contra thresholds 7.5–12.5 usando `totalCorners > threshold` (Over) ou `totalCorners < threshold` (Under)
- Early return impede que o mercado caia no loop de gols

#### Camada 2: `actual_result` com `total_corners` no backend (`ai_analysis.py`)
- Extraído `homeCornersCount` / `awayCornersCount` do dict `stats` do match (com fallback para `home_team_corner_count`)
- Adicionado `"total_corners": total_corners` ao dict `actual_result` (linha 862)
- Log de debug para matches com picks de escanteios para facilitar troubleshooting futuro

#### Camada 3: Dupla evaluation com `total_corners` no cron handler (`cron_handler.py`)
- Extraído corners do `stats` de cada match na construção de `_actual_by_id`
- Adicionado `"total_corners": _tc` ao dict de resultado por match

#### Camada 4: `MatchActualResult` e `computeLocalCombinadas()` (`localAudit.ts`)
- Interface expandida com `totalCorners: number`
- Lookup `actualByKey` agora extrai `homeCornersCount + awayCornersCount` do `match.stats`
- `_evaluateDupla()` passa `totalCorners` para `evaluatePick()`

#### Camada 5: Tipo TypeScript (`leagues.ts`)
- Adicionados `homeCornersCount?: number` e `awayCornersCount?: number` à interface `Match.stats`
- Campos opcionais (não quebra compatibilidade com matches antigos sem dados de corner)

### Todos os call sites de `evaluatePick` atualizados

| Local | Contexto | Antes | Depois |
|---|---|---|---|
| `runLocalAudit()` linha 608 | Avaliação individual de picks | `evaluatePick(mercado, totalGoals, btts, result1x2)` | `evaluatePick(mercado, totalGoals, btts, result1x2, totalCorners)` |
| `_evaluateDupla()` linha 478-479 | Avaliação de duplas (intra/inter) | `evaluatePick(mercado, a.totalGoals, a.btts, a.result1x2)` | `evaluatePick(mercado, a.totalGoals, a.btts, a.result1x2, a.totalCorners)` |

### Impacto esperado (com dados do relatório citado)

| Mercado | Antes | Depois |
|---|---|---|
| Escanteios Over 8.5 (Bahia x Vitória, 10 corners) | ERROU | ACERTOU |
| Escanteios Over 9.5 (Bahia x Vitória, 10 corners) | ERROU | ACERTOU |
| Escanteios Over 10.5 (outro jogo com 11+ corners) | já era ACERTOU | ACERTOU |
| Todas as duplas com perna de escanteios | ERROU | Avaliação correta |
| Acurácia geral reportada | ~76.2% (deprimida) | Mais alta (picks corretos contabilizados) |

### Efeito cascata corrigido

Com escanteios sempre marcados ERROU, a Mistral AI sugeria:
- `corner_multiplier: 1 → 0.7` (redução de 30% na confiança de escanteios)
- Diagnóstico "Baixa acurácia em escanteios" e "SYSTEMATIC ERROR"

Essas sugestões eram **baseadas em dados falsos**. Se aplicadas, reduziriam a qualidade real das previsões de escanteios. A correção elimina esse viés: a Mistral agora recebe acurácia real para fundamentar suas sugestões.

### Lição aprendida

1. **Cada mercado precisa de teste explícito na avaliação** — A função `evaluatePick` foi escrita para gols, BTTS e 1X2, e escanteios foram adicionados como mercado depois sem atualizar o avaliador. Ao adicionar um novo mercado ao sistema (via `market_service.py`), o avaliador correspondente (`evaluatePick` no frontend e `_evaluate_pick_deterministic` no backend) **deve ser atualizado simultaneamente**.

2. **Dados falsos + AI = recomendações perigosas** — A Mistral sugeria reduzir multipliers de escanteios com 80% de confiança, baseada em 0% de acurácia que era artefato de um bug. Um loop de feedback AI-sobre-dados-errados pode degradar o modelo progressivamente. Sempre validar que os dados de entrada da avaliação são reais antes de confiar nas sugestões da AI.

3. **Paridade entre camadas de avaliação** — O sistema tinha 4 locais que avaliam picks (backend batch-audit, backend cron, frontend audit individual, frontend duplas). O cron handler tinha `total_corners` mas os outros 3 não. Quando a lógica de avaliação é replicada em múltiplas camadas, **todas devem ser atualizadas juntas** — usar uma única função compartilhada ou pelo menos um checklist de paridade.

---

## 007 — Livescore 0-0 em ligas árabes (Saudi Pro League)

**Data:** 2026-03-12
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Jogos ao vivo da Saudi Professional League (Al Hazm vs Al Kholood, Al Najma vs Dhamk, Neom SC vs Al Taawon) mostravam score congelado em 0-0 apesar de estarem em andamento. Mesmo padrão do bug #005/#006 mas para ligas árabes.

### Causa raiz (3 falhas)

1. **Name matching falha para nomes árabes:** O prefixo "al" (artigo "o/a" em árabe) NÃO era removido pelo `_normalize_team_name()`. Resultado: "Al Hazm" normalizava para "al hazm" e "Al-Hazem" para "al hazem" — diferentes. Token overlap funcionava por sorte (50% = "al"), mas era frágil e sujeito a falsos positivos (ex: "Al Hazm" matcharia "Al Hilal" com 50% overlap).

2. **Sem fuzzy matching para variantes de transliteração:** Nomes árabes têm múltiplas romanizações: "Hazm"/"Hazem", "Taawon"/"Taawoun", "Ettifaq"/"Al-Ittifaq". Sem matching fuzzy, esses pares falhavam.

3. **Sem fallback de season:** `get_fixtures_by_date(league=307, season=2025)` podia retornar 0 fixtures se a API-Football usar convenção de season diferente para a liga saudita. Sem fallback para `season+1`, a enrichment era silenciosamente abortada.

### Correções aplicadas (3 camadas)

1. **`_normalize_team_name` — Adição do prefixo "al"** ao regex de remoção de prefixos. Agora "Al Hazm" → "hazm", "Al-Hazem" → "hazem". Remove ruído do artigo árabe para matching mais preciso.

2. **`_team_names_match` — Fuzzy matching com SequenceMatcher:**
   - Threshold 0.8 (80% similaridade) para match direto entre nomes normalizados
   - Token-level fuzzy (0.75 threshold) para tokens individuais não coincidentes
   - Resultado: "hazm" ↔ "hazem" = 0.89 → MATCH; "taawon" ↔ "taawoun" = 0.92 → MATCH
   - Falsos positivos eliminados: "hazm" ↔ "hilal" = 0.40 → NO MATCH

3. **`_enrich_with_api_football` — Season fallback:** Se `get_fixtures_by_date()` retorna 0 fixtures, automaticamente tenta `season + 1`. Cobre casos onde a convenção de season difere da nossa expectativa.

4. **Logging diagnóstico aprimorado:** Quando matching falha no `/live-scores`, loga os nomes normalizados e amostras de fixtures da API-Football para depuração remota.

### Fluxo corrigido (Saudi Pro League)

```
1. GET /fixtures?leagues=professional-league&date=today
2. _enrich_with_api_football(lid="professional-league", ...)
   ├── season = 2025 (European convention)
   ├── get_fixtures_by_date(league=307, season=2025, date=...)
   ├── Se 0 fixtures → fallback: try season=2026          ← FIX #3
   ├── _team_names_match("Al Hazm", "Al-Hazem")
   │   ├── normalize: "hazm" vs "hazem"                   ← FIX #1 (remove "al")
   │   ├── fuzzy_match("hazm","hazem") = 0.89 ≥ 0.8      ← FIX #2
   │   └── MATCH
   └── enrich_fixture_record → score real overlay
3. GET /live-scores
   ├── get_live_fixtures() (sem filtro de season)
   ├── _team_names_match → agora funciona com nomes árabes
   └── Score atualizado em tempo real
```

### Lição aprendida

1. **"al" é o "FC" do mundo árabe** — Artigos e prefixos culturais (al-, el-, de, van, von) devem ser removidos na normalização. Cada nova região adicionada ao sistema pode introduzir novos prefixos.
2. **Transliteração é lossy** — Nomes árabes/japoneses/coreanos têm múltiplas romanizações válidas. Matching exato e substring NUNCA são suficientes; fuzzy matching é obrigatório para sistemas multi-região.
3. **Season fallback é seguro** — Tentar `season ± 1` quando 0 fixtures retorna é barato (1 request extra cached) e cobre erros de convenção para qualquer liga, não apenas Saudi.

---

## 008 — Placar "- : -" em jogos ao vivo + polling retorna vazio

**Data:** 2026-03-14
**Arquivos afetados:** `backend/routes/fixtures.py`, `frontend/next/src/app/api/matches/live/route.ts`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta (placar ao vivo nunca atualiza — mostra "- : -" ou 0-0 permanente)
**Status:** Corrigido
**Relacionado:** #005, #007

### Problema identificado

Jogo Atlético Nacional vs Llaneros (Colômbia, Liga DIMAYOR) mostrava placar `- : -` no dashboard apesar de estar ao vivo em 1-0 (gol de M. Uribe aos 2'). Mesmo após o intervalo (HT), o placar não atualizava. A análise AI (Mistral) corretamente mencionava "Placar atual (1-0)" no painel de análise, mas o card do jogo na lista permanecia com `- : -`.

### Causa raiz (3 falhas independentes e acumulativas)

**BUG 1 — FootyStats retorna `null` para goal counts de jogos recém-começados:**
O endpoint `get_match_live_details(match_id)` do FootyStats retorna `homeGoalCount=null` e `homeGoals="[]"` (array vazio) nos primeiros minutos de um jogo ao vivo. O backend exigia `_fb_home is not None and _fb_away is not None` (linha 896 de `fixtures.py`) para aceitar o resultado — com ambos `None`, `_detail_ok` permanecia `False` e o backend emitia `score: None`. O frontend renderizava `None` como `"- : -"` (fallback em `MatchCard.tsx:212`).

**Fluxo do bug:**
```
FootyStats /match/{id} → homeGoalCount=null, homeGoals="[]"
→ _fb_h_vals = [] (lista vazia)
→ _fb_home = None
→ _detail_ok = False
→ result.append({"score": None, ...})
→ Frontend: data.score ? "X - Y" : "- : -"  → "- : -"
```

**BUG 2 — Endpoint `/live-scores` retorna `{"matches": []}` permanentemente:**
O endpoint `/live-scores` do backend usa `footstats.get_live_scores()` que chama `todays-matches` **sem filtro de liga nem `season_id`**. Para certas ligas (incluindo Colômbia Primera A), o FootyStats retorna `{"success": true, "data": []}` (lista vazia) neste endpoint global, apesar de retornar dados corretamente via `league-matches` com `season_id`. Resultado: o polling a cada 30s via `/api/matches/live` nunca recebia dados para sobrepor ao placar.

**Evidência direta (produção):**
```
GET /api/matches/live → {"matches":[],"nextUpdate":60}     ← VAZIO
GET /api/matches/fetch?leagues=colombia-primera-a → Atlético Nacional vs Llaneros, score: {home:0, away:0}  ← TEM DADOS
```

**BUG 3 — Rota `/fixtures` também retorna score 0-0 (mesmo problema do BUG 1):**
A rota `/fixtures` (carga inicial) faz o mesmo fetch de `get_match_live_details()` e sofria do mesmo bug: goal counts `null` → descartados → `_has_goals_fb = False` → `match_score` nunca era definido para jogos ao vivo sem dados de gol. Além disso, `match_score` não era inicializado antes da verificação condicional (linha 646), arriscando `NameError`.

### Correções aplicadas (5 camadas)

#### Camada 1: API-Football como fonte PRIMÁRIA de live scores (`fixtures.py`)
- Quando FootyStats `todays-matches` retorna vazio (`raw_list = []`), o endpoint `/live-scores` agora chama diretamente `_afc.get_live_fixtures()` (cache 1min)
- Itera sobre todos os fixtures ao vivo da API-Football, extrai score real via `extract_live_data()`, e retorna como resultado principal
- Mapeia period codes (`1H→1T`, `2H→2T`, `BT→HT`, `P→PEN`) e status (`live`/`finished`)
- Log explícito: `[live-scores] FootyStats empty → API-Football primary: N matches`
- **Resultado**: placar 1-0 do Atlético Nacional vs Llaneros agora aparece diretamente da API-Football

#### Camada 2: Default 0-0 para jogos ao vivo sem goal data — `/live-scores` (`fixtures.py`)
- Quando `get_match_live_details()` retorna `success=true` mas goals são `null`, agora assume `_fb_home = 0` e `_fb_away = 0` (tratamento: "jogo existe mas ainda sem gols registrados")
- Quando `_detail_ok = False` (endpoint falha ou retorna dados insuficientes), agora emite `score: {"home": 0, "away": 0}` em vez de `score: None`
- O API-Football enrichment subsequente sobrescreve com o placar real quando disponível

#### Camada 3: Default 0-0 para jogos ao vivo sem goal data — `/fixtures` (`fixtures.py`)
- Mesmo tratamento de null → 0 para `_fb_h_final` e `_fb_a_final` no fetch de match detail
- `match_score` agora é inicializado com `{"home": 0, "away": 0}` para jogos `live` antes da verificação condicional
- Elimina risco de `NameError` e garante que jogos ao vivo sempre têm score renderizável

#### Camada 4: Fallback do polling via `/fixtures` no frontend (`route.ts`)
- Quando `/live-scores` retorna vazio (0 matches), a rota `/api/matches/live` agora faz **fallback** chamando `/fixtures?leagues=X&date=today` para as ligas com jogos ao vivo
- Filtra apenas records com `status === "live" || status === "finished"` do resultado
- Dupla defesa: mesmo que o Lambda não seja redeployado, o frontend tem fallback independente

#### Camada 5: Dashboard envia ligas ao vivo como parâmetro (`page.tsx`)
- Novo `useRef<string>` (`liveLeagueIdsRef`) rastreia IDs das ligas com jogos ao vivo
- Atualizado via `useEffect` sem re-criar o callback `fetchLiveScores`
- O polling passa `?leagues=colombia-primera-a,...` na URL do fetch para ativar o fallback

#### Camada 6: Logging diagnóstico (`route.ts`)
- Log quando `PY_BACKEND_URL` não está configurado (antes retornava silenciosamente vazio)
- Log do count de matches e latência quando o endpoint retorna OK
- Permite diagnóstico remoto via Vercel Runtime Logs

### Fluxo corrigido

```
1. Carga inicial: GET /api/matches/fetch?leagues=colombia-primera-a
   ├── Backend /fixtures → FootyStats league-matches + match-detail
   ├── homeGoalCount=null → default 0                              ← FIX Camada 3
   ├── match_score = {home: 0, away: 0}                            ← FIX Camada 3
   └── Frontend renderiza "0 - 0" (não mais "- : -")

2. Polling (cada 30s): GET /api/matches/live?leagues=colombia-primera-a
   ├── Backend /live-scores:
   │   ├── FootyStats todays-matches → {"data": []}               ← VAZIO
   │   ├── API-Football get_live_fixtures() → fixtures ao vivo     ← FIX Camada 1
   │   ├── extract_live_data() → score 1-0, period "1T", minute 4
   │   └── Retorna [{homeTeam: "Atletico Nacional", score: {home:1, away:0}, ...}]
   ├── Frontend overlay: match por nome normalizado
   └── Atualiza "0 - 0" → "1 - 0"
```

### Diferença entre "- : -" e "0 - 0"

| Situação | Antes | Depois |
|---|---|---|
| Jogo live, FootyStats retorna null goals | `- : -` (score=undefined) | `0 - 0` (score={home:0,away:0}) |
| Jogo live, FootyStats retorna 0-0 real | `0 - 0` | `0 - 0` |
| Polling, /live-scores vazio | Nunca atualiza | Fallback via /fixtures atualiza |
| Polling, API-Football match ok | Score real (ex: 1-0) | Score real (ex: 1-0) |

### Lição aprendida

1. **Endpoints "globais" vs "filtrados" podem ter comportamentos diferentes** — O FootyStats `todays-matches` (sem filtro) retorna vazio para certas ligas, mas `league-matches` (com `season_id`) funciona. Nunca assuma que dois endpoints da mesma API retornam os mesmos dados. Quando um falha, o outro pode ser fallback.

2. **`null` ≠ `0` ≠ "sem dados"** — O FootyStats retorna `homeGoalCount=null` para jogos ao vivo recém-começados, não `0`. O sistema tratava `null` como "dados indisponíveis" e descartava, quando na verdade significava "0 gols até agora". A semântica correta é: se a API confirma que o jogo existe (`success=true`), goals `null` deve ser tratado como `0`.

3. **Defesa em profundidade inclui o polling** — Corrigir o score na carga inicial não basta se o mecanismo de polling (que deveria atualizar a cada 30s) está permanentemente vazio. Cada camada da cadeia de atualização (carga → polling → overlay → render) deve ter fallback independente.

---

## 009 — Jogo ao vivo excluído da lista de jogos quando FootyStats o remove

**Data:** 2026-03-14
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Jogo da Liga Colombia DIMAYOR (Atlético Nacional 2-0 Llaneros, aos 79') desapareceu completamente da lista de jogos no dashboard. O endpoint `/fixtures?leagues=colombia-primera-a` retornava apenas 4 jogos futuros, omitindo o jogo em andamento.

### Causa raiz

O FootyStats pode remover jogos ao vivo da resposta de `league-matches` por vários motivos:
- O jogo foi movido para fora da página 1 (paginação por data)
- O status mudou para "complete" enquanto o jogo ainda estava em andamento
- Edge case de timezone (kickoff 01:30 UTC = 22:30 BRT do dia anterior) fazendo o date guard filtrar o jogo

Quando isso ocorre, a função `_enrich_with_api_football()` no CASE 1 (records existem) apenas enriquecia os records existentes via overlay. Jogos que a API-Football tinha mas o FootyStats não retornava eram **silenciosamente ignorados** — o loop de matching simplesmente não encontrava um record correspondente e seguia em frente.

O CASE 2 (usar API-Football como fallback completo) só era ativado quando `records` estava vazio E `found_via_api = False`. Como o FootyStats retornava 4 jogos futuros, `records` não estava vazio, e o CASE 2 nunca era ativado.

### Correção aplicada (1 camada)

**CASE 1b — Injeção de jogos ao vivo/finalizados da API-Football que o FootyStats removeu:**

Após o loop de enrichment do CASE 1, o código agora:
1. Identifica quais fixtures da API-Football **não** foram matched a nenhum record existente (nem por ID nem por nome de time)
2. Filtra apenas jogos com status live (`1H`, `HT`, `2H`, `ET`, `BT`, `P`, `LIVE`, `SUSP`, `INT`) ou finished (`FT`, `AET`, `PEN`)
3. Converte esses fixtures para records via `fixtures_to_records()` e os adiciona à lista

Isso garante que jogos ao vivo nunca desapareçam da lista, mesmo quando o FootyStats os remove.

### Fluxo corrigido

```
FootyStats league-matches → 4 jogos futuros (falta o jogo ao vivo)
                    ↓
_enrich_with_api_football() CASE 1:
  - Enriquece os 4 records existentes com dados da API-Football
  - CASE 1b (NOVO): API-Football tem 5 fixtures, 4 matched → 1 unmatched
    - O unmatched é Atlético Nacional vs Llaneros (status=2H, live)
    - Converte para record e injeta na lista
                    ↓
Resultado: 5 jogos retornados (4 futuros + 1 ao vivo)
```

### Lição aprendida

1. **Enrichment ≠ Fallback completo** — Enriquecer records existentes não é suficiente quando a fonte primária remove dados. O sistema precisa de lógica de "injeção" que adicione dados que a fonte secundária tem mas a primária perdeu.

2. **Fontes de dados não são monotônicas** — Não se pode assumir que um jogo que apareceu na lista vai continuar aparecendo. APIs externas podem remover jogos por paginação, mudança de status, ou limites de rate. O sistema deve compensar essas remoções usando fontes alternativas.

3. **O CASE 2 (fallback total) tem uma condição muito restritiva** — Só ativa quando `records` está completamente vazio. Isso significa que se o FootyStats retorna pelo menos 1 jogo (mesmo que irrelevante), o CASE 2 nunca roda. A solução correta é o CASE 1b, que opera dentro do CASE 1 para adicionar jogos faltantes.

---

## 010 — Status "started" do FootyStats não reconhecido como "live"

**Data:** 2026-03-14
**Arquivos afetados:** `backend/services/util_service.py`
**Severidade:** Crítica
**Status:** Corrigido

### Problema identificado

Jogo Atlético Nacional 2-0 Llaneros (87') com status `"started"` no FootyStats era tratado como `"scheduled"` pelo sistema. Isso causava:
1. Jogo ao vivo não aparecia como live no dashboard
2. Score não era exibido (jogos scheduled não mostram placar)
3. Jogo podia ser filtrado por guards de data/status

### Causa raiz

A função `status_map()` em `util_service.py` reconhecia `"live"`, `"inplay"`, `"playing"` e `"halftime"` como status live, mas **não incluía `"started"`**. O FootyStats usa `"started"` como status para jogos em andamento. Como `"started"` não estava no mapeamento, caía no `return "scheduled"` default.

### Correção aplicada (1 camada)

Adicionado `"started"` à lista de status reconhecidos como `"live"` em `status_map()`:

```python
# Antes:
if sl in ("live", "inplay", "playing", "halftime"):
    return "live"

# Depois:
if sl in ("live", "inplay", "playing", "halftime", "started"):
    return "live"
```

### Lição aprendida

1. **Sempre verificar os valores reais da API** — Em vez de assumir quais strings de status a API usa, verificar diretamente nos dados retornados. O FootyStats documenta "incomplete"/"complete" mas usa variações como "started" que não estão na documentação oficial.

2. **Mapeamentos de status devem ser exaustivos** — Quando a API adiciona novos valores de status, o fallback `return "scheduled"` silenciosamente descarta jogos ao vivo. É mais seguro logar um warning quando um status desconhecido é encontrado.

---

## 011 — Conformidade com documentação oficial API-Football (rate limit, timezone, paginação)

**Data:** 2026-03-14
**Arquivos afetados:** `backend/services/api_football_client.py`
**Severidade:** Média (prevenção de bugs futuros e otimização de quota)
**Status:** Implementado
**Relacionado:** #003, #004, #007

### Problema identificado

Auditoria do `api_football_client.py` contra a documentação oficial "How to Get Started with API-Football" (março 2026) revelou 3 lacunas que podiam causar bugs silenciosos e desperdício de quota:

1. **Rate limit não monitorado** — O response header `x-ratelimit-requests-remaining` (quota diária restante) nunca era lido. No plano Pro (7.500 req/dia), o sistema podia esgotar a quota sem aviso, causando falhas silenciosas em todos os endpoints da API-Football.

2. **Parâmetro `timezone` ausente** — `get_fixtures_by_date()` não passava timezone à API. O padrão da API é UTC, mas o sistema calcula datas em BRT (UTC-3). Resultado: jogos com kickoff entre 21:00-23:59 BRT (00:00-02:59 UTC do dia seguinte) podiam ser classificados na data errada. **Exemplo real:** O jogo Atlético Nacional vs Llaneros (kickoff 01:30 UTC = 22:30 BRT) podia cair no dia errado dependendo de como a API interpretava o `date` parameter.

3. **Paginação silenciosamente ignorada** — A API pagina em 10 results/página para `/odds` e 20/página para `/players`. O client lê apenas a primeira página via `data.get("response", [])` sem checar `paging.total`. Para fixtures com muitos bookmakers (ex: Premier League com 15+ bookmakers), odds de bookmakers a partir da página 2 eram silenciosamente descartadas.

### Causa raiz

A integração #003 implementou a infraestrutura correta (cache, retry, endpoints), mas não seguiu 3 recomendações explícitas da documentação oficial:
- _"Build the habit of checking these headers, especially on the free plan"_ (rate limit)
- _"Users in different countries see match kickoff times in their local time"_ (timezone)
- _"Always check paging on your first call before assuming you got the full dataset"_ (paginação)

### Correções aplicadas (3 camadas)

#### Camada 1: Monitoramento de rate limit (`_get_sync()`)

Após cada resposta bem-sucedida, o client agora lê o header `x-ratelimit-requests-remaining`:

```python
rl_remaining_day = resp.headers.get("x-ratelimit-requests-remaining")
if rl_remaining_day is not None:
    remaining = int(rl_remaining_day)
    if remaining <= 10:
        logger.warning(f"[api-football] Daily quota almost exhausted: {remaining} requests remaining")
    elif remaining <= 50:
        logger.info(f"[api-football] Daily quota: {remaining} requests remaining")
```

**Thresholds:**
- ≤ 10 requests restantes → `WARNING` (alerta crítico nos logs)
- ≤ 50 requests restantes → `INFO` (visibilidade para monitoramento)
- \> 50 → silencioso (sem poluição de logs)

#### Camada 2: Parâmetro `timezone` em `get_fixtures_by_date()`

```python
params: Dict[str, str] = {
    "league": str(league_id),
    "season": str(season),
    "date": match_date or date.today().isoformat(),
    "timezone": "America/Sao_Paulo",  # ← NOVO
}
```

**Impacto:** A API-Football agora retorna timestamps convertidos para BRT. Jogos com kickoff 22:30 BRT são corretamente classificados no dia BRT, eliminando o edge case de timezone que contribuiu para o desaparecimento do jogo Colombia (#009).

**Referência da documentação:** _"When you include it, all timestamps in the response are automatically converted to that timezone"_ — Os 425 valores válidos de timezone estão no endpoint `/timezone`.

#### Camada 3: Suporte a paginação

**3a. Warning genérico em `_get_sync()` para respostas paginadas não tratadas:**

```python
paging = data.get("paging", {})
total_pages = paging.get("total", 1)
if total_pages > 1 and current_page == 1 and "page" not in params:
    logger.warning(
        f"[api-football/{endpoint}] Response has {total_pages} pages "
        f"but only page 1 fetched ({data.get('results', 0)} results)"
    )
```

Isso garante que qualquer endpoint futuro com paginação não tratada será detectado imediatamente nos logs.

**3b. Paginação completa em `get_odds()`:**

```python
def get_odds(self, fixture_id: int, ttl_minutes: int = 30) -> List[Dict]:
    params = {"fixture": str(fixture_id)}
    data = self._get_sync("odds", params, ttl_minutes=ttl_minutes)
    results = data.get("response", [])

    # Handle pagination (odds paginate at 10/page)
    paging = data.get("paging", {})
    total_pages = paging.get("total", 1)
    if total_pages > 1:
        for page in range(2, min(total_pages + 1, 6)):  # Cap at 5 pages
            params["page"] = str(page)
            page_data = self._get_sync("odds", params, ttl_minutes=ttl_minutes)
            results.extend(page_data.get("response", []))

    return results
```

**Cap de 5 páginas** para evitar loops infinitos ou desperdício de quota em casos anômalos.

### Referência: Recomendações da documentação oficial vs implementação atual

| Recomendação oficial | Status antes | Status depois |
|---|---|---|
| Monitorar `x-ratelimit-requests-remaining` | ❌ Não implementado | ✅ Warning ≤10, Info ≤50 |
| Passar `timezone` para `/fixtures` | ❌ Ausente (default UTC) | ✅ `America/Sao_Paulo` |
| Checar `paging.total` em todas as chamadas | ❌ Ignorado silenciosamente | ✅ Warning genérico + paginação em `/odds` |
| Auth via `x-apisports-key` header | ✅ Correto desde #003 | ✅ Mantido |
| Base URL `v3.football.api-sports.io` | ✅ Correto desde #003 | ✅ Mantido |
| `live=all` para fixtures ao vivo | ✅ Correto desde #003 | ✅ Mantido |
| 16 status codes mapeados | ✅ Completo desde #003 | ✅ Mantido |
| Cache de logos/imagens (CDN rate limit) | ⚠️ Não aplicável (sem CDN próprio) | ⚠️ Mantido |
| Polling 15s live, 1h standings | ✅ 30s live (conservador), 6h standings | ✅ Mantido |

### Intervalos de polling recomendados (referência futura)

| Tipo de dado | Frequência de atualização da API | Polling recomendado | Nosso polling atual |
|---|---|---|---|
| Live fixtures (scores) | 15 segundos | 15-60s | 30s ✅ |
| Match statistics | 1 minuto | 1 minuto | Não implementado (futuro) |
| Match events (gols/cartões) | 15 segundos | 15-60s | Não implementado (futuro) |
| Standings | 1 hora | 1 hora | 6h cache ✅ |
| Injuries | 4 horas | 1x/dia | 4h cache ✅ |
| Odds (pré-match) | 3 horas | 3 horas | 30min cache ✅ |
| Lineups | Pré-jogo (30-60min antes) | 10-15min antes | Sob demanda ✅ |
| Reference data (leagues, teams) | Diário | 1x/dia ou startup | 6h cache ✅ |

### Lição aprendida

1. **Ler a documentação oficial da API antes de ir para produção** — A integração #003 foi construída a partir de exemplos e testes empíricos. Uma leitura detalhada da documentação teria evitado os 3 gaps desde o início. Documentação oficial > tentativa e erro.

2. **Headers de resposta contêm informação operacional crítica** — Rate limit, quota restante, e IDs de paginação são enviados em headers, não no body. Ignorá-los é como dirigir sem olhar o painel de combustível.

3. **Paginação silenciosa é a forma mais insidiosa de perda de dados** — Uma resposta com `paging.total: 3` e `results: 10` parece completa se você não checar o paging. Nenhum erro é lançado, nenhum warning aparece — os dados simplesmente não existem no resultado. Sempre validar `paging.total == 1` ou implementar loop de páginas.

4. **Timezone afeta mais que exibição** — Não é apenas sobre mostrar horários locais. O parâmetro `timezone` muda quais fixtures são retornados para uma dada `date`, porque o mesmo momento UTC pode ser dia 13 ou dia 14 dependendo do timezone. Isso foi parte do bug #009 (jogo Colombia com kickoff 01:30 UTC).

---

## 012 — Apostas em Sistema (System Bets) na Gestao de Banca

**Data:** 2026-03-14
**Arquivos afetados:** `frontend/next/src/lib/kelly.ts`, `frontend/next/src/components/BankrollCalculator.tsx`, `frontend/next/package.json`
**Severidade:** Feature (nova funcionalidade)
**Status:** Implementado
**Versao:** 3.7.0

### Contexto

Quando o filtro de EV positivo aprovava multiplos jogos no dia, o sistema apenas listava jogos soltos sem sugerir agrupamentos inteligentes para mitigar riscos. Usuarios precisavam de orientacao sobre como distribuir a banca entre combinacoes de apostas.

### Funcionalidades implementadas (5 regras de negocio)

#### Regra 1 — Calculadora de Sistema Integrada

- Botao "Montar Aposta em Sistema" aparece quando 3+ jogos possuem EV positivo
- Mostra visualmente as linhas de aposta (combinacoes menores) geradas
- Secao "Cenarios de Retorno" calcula ganhos parciais para cada quantidade de acertos
- Exemplo: "Se acertar 2 de 3 jogos, retorno estimado R$ X; se acertar os 3, retorno Y"
- Cada cenario indica com icone (check verde / X vermelho) se cobre o investimento total

**Implementacao:** Funcao `buildScenarios()` em `kelly.ts` itera de 0 a N hits, simulando quais combinacoes pagam em cada cenario. Tipo `SystemBetScenario` com campos `hitsRequired`, `winningCombos`, `estimatedReturn`, `netProfit`, `coversInvestment`.

#### Regra 2 — Distribuicao Automatica de Stake (Gestao de Risco)

- Cruza o Criterio de Kelly Fracionado com a logica de distribuicao de linhas
- O total ideal calculado por Kelly e dividido igualmente entre todas as linhas
- Exemplo: Kelly indica R$ 30,00 para sistema "2 de 3" (3 linhas) → Stake por linha: R$ 10,00
- Card explicativo na UI mostra a logica ao usuario
- Impede que o usuario invista o valor total de Kelly em cada linha separadamente

**Implementacao:** Campo `stakePerLine` em `SystemBetSuggestion`. Formula: `totalSystemStake / combos.length`. Cada combo recebe stake igual via loop.

#### Regra 3 — Recomendacao Dinamica de Nivel

- Algoritmo avalia quantidade de jogos +EV diarios e seleciona o formato automaticamente
- 3 jogos → **Trixie** (3 duplas + 1 tripla = 4 linhas) — protecao de banca padrao
- 5+ jogos → **Sistema 3/5** (10 combinacoes duplas) — para dias de alto volume
- Formato "2de3" (3 linhas apenas duplas) disponivel como alternativa conservadora

**Implementacao:** Funcao `pickSystemFormat()` em `kelly.ts` com array `SYSTEM_FORMATS` contendo definicoes de cada formato (`selectionCount`, `minK`, `maxK`).

#### Regra 4 — Banker (Ancoragem Algoritmica — Premium)

- Algoritmo identifica o jogo com maior score composto: `(probabilidade) × (1 + EV) × (1 + edge)`
- Marcado com badge dourado "Crown" e etiqueta "Premium" na UI
- Texto explicativo: "O Banker esta presente em todas as combinacoes e aumenta o retorno potencial, barateando o custo das multiplas linhas — mas a aposta inteira e perdida se o Banker falhar"

**Implementacao:** Funcao `selectBanker()` em `kelly.ts`. Tipo `BankerSelection` com campos `allocation`, `score`, `reason`. Integrado ao `SystemBetCard` com destaque visual diferenciado (cor dourada #ffd700).

#### Regra 5 — Filtro de Limite de Rentabilidade (Break-even)

- Antes de recomendar um sistema, calcula se o acerto minimo cobre o investimento total
- Para 3 selecoes: verifica se 2 de 3 acertos cobre o stake total das 4 linhas
- Para 5 selecoes: verifica se 3 de 5 acertos cobre o stake total das 10 linhas
- Se odds medias forem baixas (ex: 1.50) e nao garantirem autofinanciamento: sistema marcado como "Nao recomendado" com alerta vermelho, e recomenda apostas simples individuais
- Badge "Recomendado" (verde) aparece apenas quando o filtro aprova

**Implementacao:** Funcao `checkBreakEven()` em `kelly.ts`. Campos `passesBreakEven`, `breakEvenReason`, `recommended` em `SystemBetSuggestion`. UI adapta cores e mensagens conforme status.

### Correcao adicional (build fix)

- **Erro de build Vercel:** Prop `title` diretamente em icone `<ShieldAlert>` do lucide-react causava erro TS2322. Movido para wrapper `<span title="...">`.
- **Versao:** 3.6.0 → 3.6.1 (patch) → 3.7.0 (feature)

### Tipos novos adicionados

| Tipo | Descricao |
|---|---|
| `SystemBetScenario` | Cenario de retorno para N acertos: `hitsRequired`, `winningCombos`, `estimatedReturn`, `netProfit`, `coversInvestment` |
| `BankerSelection` | Selecao de ancora: `allocation`, `score`, `reason` |

### Campos novos em `SystemBetSuggestion`

| Campo | Tipo | Descricao |
|---|---|---|
| `headline` | `string` | Texto hero explicativo para o card principal |
| `stakePerLine` | `number` | Valor por linha (total / N combinacoes) |
| `scenarios` | `SystemBetScenario[]` | Breakdown de retornos para cada qtd de acertos |
| `banker` | `BankerSelection \| null` | Jogo ancora selecionado algoritmicamente |
| `passesBreakEven` | `boolean` | Se o sistema passa no filtro de rentabilidade |
| `breakEvenReason` | `string` | Motivo da rejeicao pelo filtro (se aplicavel) |
| `recommended` | `boolean` | Se o sistema e recomendado (passa todos os filtros) |

### Formatos de sistema suportados

| Formato | `SystemBetFormat` | Selecoes | Linhas | Descricao |
|---|---|---|---|---|
| Sistema 2/3 | `"2de3"` | 3 | 3 | Apenas duplas — lucra com 2 de 3 acertos |
| Trixie | `"trixie"` | 3 | 4 | 3 duplas + 1 tripla |
| Sistema 3/5 | `"3de5"` | 5 | 10 | 10 duplas — lucra com 3 de 5 acertos |

### Licao aprendida

1. **Dividir stake total por linhas e essencial** — Sem essa regra, o usuario tenderia a aplicar o valor integral de Kelly em cada combinacao, multiplicando o risco real por N linhas e destruindo a gestao de banca.

2. **Break-even filter protege contra falsa sensacao de seguranca** — Apostas em sistema com odds baixas (< 1.60) parecem seguras mas frequentemente nao cobrem o custo das multiplas linhas quando o cenario minimo ocorre.

3. **Banker e uma faca de dois gumes** — Aumenta retorno potencial e reduz custo, mas concentra risco. A UI deve sempre comunicar claramente que perder o Banker perde tudo.

---

## 013 — Aba "Duplas" não carrega jogos (resposta não-JSON do backend)

**Data:** 2026-03-15
**Arquivos afetados:** `backend/routes/combinadas.py`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

A aba "Duplas" no dashboard exibia o erro: `Unexpected token 'A', "An error o"... is not valid JSON`. Nenhuma dupla era carregada — tanto intra-jogo quanto inter-jogo ficavam vazias.

### Causa raiz (2 camadas)

1. **Backend sem tratamento de exceção** — O endpoint `/combinadas` chamava `get_fixtures()` e `gerar_combinadas()` sem try-catch. Quando uma exceção ocorria (ex: timeout da API externa, erro de parsing), o FastAPI propagava a exceção e retornava uma resposta HTML/texto de erro 500 em vez de JSON válido.

2. **Frontend sem validação de formato** — O dashboard chamava `res.json()` diretamente na resposta da API. Quando o Vercel recebia o erro do backend e retornava sua página padrão ("An error occurred..."), o `JSON.parse` falhava com `SyntaxError`, exibindo a mensagem técnica crua ao usuário.

### Correções aplicadas (3 camadas)

1. **Try-catch no backend (`combinadas.py`)** — Envolveu `get_fixtures()` e `gerar_combinadas()` em blocos try-except. Em caso de exceção, retorna JSON válido com arrays vazios e campo `_error` descrevendo o problema, em vez de crashar o endpoint.

2. **Parse seguro no frontend (`page.tsx`)** — Substituiu `res.json()` por `res.text()` + `JSON.parse()` dentro de try-catch. Se a resposta não for JSON válido, exibe mensagem amigável: "Servidor retornou resposta inválida (HTTP XXX). Tente novamente em instantes."

3. **Correção de tipo TypeScript** — Cast de `data._error` para `Record<string, unknown>` antes de acessar `.kind` e `.message`, corrigindo erro de build no Vercel: `Property 'kind' does not exist on type 'unknown'`.

### Lição aprendida

1. **Endpoints que chamam outros endpoints internos precisam de try-catch** — O `/combinadas` delegava para `get_fixtures()` (que é uma rota inteira com múltiplas fontes de dados). Qualquer falha nessa cadeia propagava como exceção não tratada, quebrando o contrato JSON da API.

2. **Nunca confiar que `res.json()` vai funcionar** — Respostas de infraestrutura (Vercel, AWS Lambda, nginx) podem retornar HTML/texto em situações de erro. Sempre parsear como texto primeiro e tentar JSON depois, com fallback amigável.

3. **TypeScript strict mode exige casts em objetos de erro** — Quando um campo é `unknown` (como `Record<string, unknown>`), acessar sub-propriedades sem cast causa erro de compilação. Usar `as Record<string, unknown>` antes de acessar propriedades aninhadas.

---

## 014 — Linha de Escanteios (Corner Progress Bar) nos cards de partida ao vivo

**Data:** 2026-03-15
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/routes/fixtures.py`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/app/api/matches/live/route.ts`, `frontend/next/src/components/CornerProgressBar.tsx` (novo), `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Feature (nova funcionalidade)
**Status:** Implementado

### Contexto

Quando o sistema gerava um prognostico de escanteios (ex: "Escanteios Over 8.5"), nao havia indicacao visual do progresso ao vivo em direcao a meta. O usuario precisava acompanhar manualmente o numero de escanteios durante o jogo.

### Funcionalidades implementadas (4 camadas)

#### Camada 1 — Engenharia de Dados (Backend)

- **`api_football_client.py`**: `extract_live_data()` agora extrai `home_corners` e `away_corners` do campo `statistics` inline do fixture retornado pelo endpoint `/fixtures?live=all` da API-Football v3. Percorre o array de estatisticas de cada time buscando `type === "Corner Kicks"`.
- **`fixtures.py`**: Rota `/live-scores` calcula `currentCorners` (soma de home + away corners) e inclui no objeto de cada partida retornada ao frontend.

#### Camada 2 — Tipagem e Fluxo de Dados (Frontend)

- **`leagues.ts`**: Campo `currentCorners?: number | null` adicionado ao tipo `Match`.
- **`live/route.ts`**: API route do Next.js repassa `currentCorners` no fallback via `/fixtures`.
- **`page.tsx`**: Live overlay (`fetchLiveScores`) faz merge de `currentCorners` no estado de cada match. Funcao `toDetailData()` repassa o valor para `MatchDetailData`.
- **`MatchDetailCard.tsx`**: Campo `currentCorners?: number | null` adicionado a interface `MatchDetailData`.

#### Camada 3 — Logica de Metas (Utilitario)

- **`CornerProgressBar.tsx`**: Funcao `extractTargetCorners(mercado)` extrai o alvo numerico do texto do prognostico usando regex.
  - `"Escanteios Over 8.5"` → `Math.ceil(8.5)` → **9**
  - `"Escanteios Over 9.5"` → `Math.ceil(9.5)` → **10**
  - Retorna `null` se o mercado nao for de escanteios.

#### Camada 4 — Componente Visual Premium

- **`CornerProgressBar.tsx`**: Componente React com design dark theme:
  - **Track**: Fundo escuro com `box-shadow inset` para profundidade
  - **Fill**: Gradiente teal (`#0d9488` → `#14b8a6`) com `transition-all 500ms ease-in-out`
  - **Badge dinamico**: Circulo na ponta da barra exibindo o numero atual de escanteios, cor teal com texto preto em alto contraste
  - **Estado "hit"**: Quando `currentCorners >= targetCorners`, cor muda para emerald (`#059669` → `#10b981`) com glow mais intenso
  - **Condicao de exibicao**: So renderiza quando `match.status === "live"` E existe um prognostico de escanteios E `currentCorners != null`
- **`match-detail-card.css`**: Classes `.cpb-root`, `.cpb-track`, `.cpb-fill`, `.cpb-badge` com variaveis CSS do tema existente

### Integracao no Card

O `CornerProgressBar` e renderizado dentro do loop de `match.predictions` no `MatchDetailCard.tsx`, logo abaixo de cada item de prognostico que contenha um mercado de escanteios. Cada prediction e envolvido em um `<div>` wrapper que contem o item original + a barra condicional.

### Fluxo de atualizacao em tempo real

1. `useLivePolling` dispara a cada 30s para jogos ao vivo
2. `/api/matches/live` chama backend `/live-scores`
3. Backend extrai corners via `extract_live_data()` do API-Football
4. Frontend faz merge de `currentCorners` no estado do match
5. React re-renderiza o `CornerProgressBar` com animacao suave de transicao

### Licao aprendida

1. **API-Football inline statistics**: O endpoint `/fixtures?live=all` retorna estatisticas inline no campo `statistics` de cada fixture — nao e necessario fazer chamadas extras a `/fixtures/statistics` para dados ao vivo como corners, posse de bola e chutes.

2. **Exibicao condicional em multiplas camadas**: A barra depende de 3 condicoes simultaneas (jogo ao vivo + prognostico de escanteios + dados de corners disponiveis). Todas as 3 devem ser verificadas no ponto de renderizacao para evitar erros visuais.

3. **Regex para parsing de mercados**: Usar `Math.ceil()` sobre o valor decimal do mercado (8.5 → 9) e a forma correta de definir a meta inteira, ja que "Over 8.5" significa "9 ou mais escanteios".

---

## 015 — CornerProgressBar invisível em jogos ao vivo (Path B sem overlay de corners)

**Data:** 2026-03-15
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

A barra de progresso de escanteios (`CornerProgressBar`) não aparecia em nenhum jogo ao vivo, mesmo quando havia prognósticos de escanteios (ex: "Escanteios Over 8.5", "Escanteios Over 10.5"). Jogos MLS como Real Salt Lake vs Austin exibiam os prognósticos normalmente, mas sem a barra visual de acompanhamento.

### Causa raiz (1 camada — backend)

A rota `/live-scores` possuía **dois caminhos** para montar a resposta de jogos ao vivo:

| Path | Condição | `currentCorners` |
|------|----------|-------------------|
| **Path A** (linhas 824-880) | FootyStats vazio → API-Football como fonte primária | Incluía `currentCorners` corretamente |
| **Path B** (linhas 1137-1213) | FootyStats retorna dados → API-Football enriquece score/minuto/período | **Não incluía `currentCorners`** |

No Path B, `extract_live_data(matched_fx)` era chamado e retornava `home_corners` e `away_corners`, mas esses valores eram **descartados**. Apenas `goals_home`, `goals_away`, `minute` e `status` eram utilizados para enriquecer o registro.

Como a maioria dos jogos ao vivo (incluindo MLS) passava pelo Path B (FootyStats retorna dados e API-Football apenas enriquece), o campo `currentCorners` nunca era incluído na resposta JSON — e o frontend, corretamente, não renderizava o `CornerProgressBar` (a condição `match.currentCorners != null` falhava).

### Correção aplicada

Adicionada lógica de agregação de corners no Path B (`fixtures.py`, bloco de enriquecimento), idêntica à do Path A:

```python
# Overlay corner kicks from API-Football
_corners: int | None = None
if ld.get("home_corners") is not None and ld.get("away_corners") is not None:
    _corners = ld["home_corners"] + ld["away_corners"]
elif ld.get("home_corners") is not None:
    _corners = ld["home_corners"]
elif ld.get("away_corners") is not None:
    _corners = ld["away_corners"]
if _corners is not None:
    rec["currentCorners"] = _corners
```

### Frontend — sem alterações necessárias

O componente `CornerProgressBar.tsx` e sua integração no `MatchDetailCard.tsx` já estavam corretos:
- `extractTargetCorners(pred.mercado)` extrai a meta do texto do prognóstico via regex
- Condição de renderização verifica 3 requisitos: `targetCorners != null && match.currentCorners != null && match.status === "live"`
- O problema era exclusivamente a ausência de `currentCorners` na resposta do backend

### Lição aprendida

1. **Caminhos duplicados exigem paridade de funcionalidade**: Quando uma rota possui múltiplos paths que constroem o mesmo tipo de resposta (Path A = fonte primária, Path B = enriquecimento), toda nova funcionalidade adicionada a um path deve ser replicada no outro. A feature de corners foi implementada apenas no Path A, mas a maioria dos jogos ao vivo usa o Path B.

2. **Investigação completa antes de assumir a causa**: O frontend estava correto — o bug era 100% no backend. Seguir o fluxo completo (backend → API route → frontend merge → condição de render) evitou correções desnecessárias no frontend.

3. **Dados descartados silenciosamente**: `extract_live_data()` já retornava `home_corners` e `away_corners` no Path B, mas o código chamador ignorava esses campos sem nenhum log. Dados extraídos mas não utilizados são um smell code que indica funcionalidade incompleta.

---

## 016 — Dados de escanteios ao vivo ausentes no contexto da análise Mistral AI

**Data:** 2026-03-15
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/services/mistral_analysis.py`
**Severidade:** Média
**Status:** Corrigido

### Problema identificado

A API-Football já extraía `home_corners` e `away_corners` via `extract_live_data()`, e esses dados já eram usados no frontend (CornerProgressBar, ver #014/#015). Porém, quando o sistema gerava a análise AI via Mistral, os dados de escanteios ao vivo **não eram incluídos no prompt**. Resultado: a Mistral recomendava mercados de Escanteios Over/Under sem saber quantos corners já haviam ocorrido durante o jogo, tornando a análise ao vivo desconectada da realidade.

### Causa raiz (2 camadas)

1. **`_format_live_status()` não incluía corners** — O método formatava apenas status, minuto e placar (ex: "Segundo tempo em andamento: 65 min, Placar: 2-1"), mas ignorava `home_corners` e `away_corners` presentes no `live_data`.

2. **Prompt sem instrução sobre corners ao vivo** — Mesmo que os corners estivessem na string de status, o prompt da Mistral não continha nenhuma instrução para avaliar ritmo de corners vs tempo restante ao recomendar mercados de escanteios.

### Correções aplicadas (2 camadas)

1. **`api_football_client.py` — `_format_live_status()`** — Agora extrai `home_corners` e `away_corners` do `live_data` e, quando ambos estão disponíveis, adiciona `Escanteios: X+Y=Z` à string de status. Exemplo de saída: `"Segundo tempo em andamento: 65 min, Placar: 2-1, Escanteios: 5+3=8"`. Funciona tanto para jogos ao vivo quanto para encerrados.

```python
home_corners = live_data.get("home_corners")
away_corners = live_data.get("away_corners")
corner_str = ""
if home_corners is not None and away_corners is not None:
    total = home_corners + away_corners
    corner_str = f", Escanteios: {home_corners}+{away_corners}={total}"
```

2. **`mistral_analysis.py` — `_build_prompt()`** — Duas adições ao prompt:
   - Na seção CONTEXTO ADICIONAL: nota explicativa após o campo `Status ao Vivo` instruindo a Mistral a usar dados de corners para avaliar mercados de escanteios ao vivo.
   - Na seção IMPORTANTE: instrução para analisar ritmo de corners vs tempo restante ao avaliar linhas de Escanteios Over/Under.

### Fluxo completo após correção

1. API-Football retorna fixture com `statistics` → `extract_live_data()` extrai `home_corners` e `away_corners`
2. `_format_live_status()` inclui `Escanteios: 5+3=8` na string de status
3. Rota `/ai/match/{id}/analysis` injeta `live_status` no contexto
4. `_build_prompt()` inclui o status no prompt com instrução para a Mistral usar os dados
5. Mistral analisa: "Já são 8 escanteios aos 65min, ritmo de ~7.4 corners/45min sugere Over 9.5 com boa probabilidade"

### Lição aprendida

1. **Dados disponíveis no sistema mas não conectados entre camadas** — O padrão de bug "dado extraído mas não propagado" se repetiu (#015 frontend, agora #016 AI). Sempre que um novo dado é adicionado ao pipeline, verificar **todos os consumidores**: frontend, prompt AI, cache, logs.

2. **Análise AI sem dados ao vivo é análise pré-jogo disfarçada** — Sem saber que já ocorreram 8 corners aos 65min, a Mistral analisa como se o jogo não tivesse começado. A qualidade da recomendação para mercados live depende criticamente de dados live no prompt.

3. **Instrução explícita no prompt é necessária** — Mesmo incluindo o dado no contexto, modelos de linguagem podem ignorá-lo se não houver instrução explícita para usá-lo. A nota "Compare o total atual com as linhas de escanteios e o tempo restante" garante que a Mistral processe ativamente a informação.

---

## 017 — Extração completa de estatísticas ao vivo e correção de viés BTTS na Mistral AI

**Data:** 2026-03-15
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/services/mistral_analysis.py`, `backend/routes/ai_analysis.py`
**Severidade:** Alta
**Status:** Corrigido
**Commit:** `87061c3`

### Problema identificado

1. **Dados táticos insuficientes para a Mistral** — O prompt da Mistral recebia apenas status, minuto, placar e escanteios ao vivo (#016), mas não incluía estatísticas detalhadas como chutes no alvo, posse de bola, faltas, cartões, passes e xG. Sem esses dados, a IA não conseguia avaliar a assimetria real de um jogo.

2. **Viés sistemático para BTTS** — A Mistral recomendava BTTS (Ambas Marcam) como opção padrão mesmo quando um dos times tinha 0 finalizações ou 0 chutes no alvo. Sem dados de pressão ofensiva no prompt, não havia base para refutar a recomendação.

3. **Busca sequencial de dados auxiliares** — O `get_match_live_data()` buscava injuries de forma isolada. Statistics e events não eram buscados, desperdiçando dados disponíveis na API-Football.

### Causa raiz (3 camadas)

1. **`api_football_client.py` sem versões async de statistics/events** — Os métodos `get_fixture_statistics()` e `get_fixture_events()` existiam apenas na versão síncrona, impedindo uso com `asyncio.gather`.

2. **Ausência de parsers estruturados** — As respostas brutas da API-Football para `/fixtures/statistics` e `/fixtures/events` não tinham funções de parsing que extraíssem campos em formato consumível pelo prompt.

3. **Prompt da Mistral sem regras anti-viés** — Não havia instrução explícita para a Mistral avaliar volume ofensivo antes de recomendar BTTS, nem alternativas priorizadas quando a assimetria fosse clara.

### Correções aplicadas (7 camadas)

#### Camada 1 — Versões async de statistics e events (`api_football_client.py`)

Dois novos métodos assíncronos com cache de 2 minutos (TTL curto para dados live):

```python
async def get_fixture_statistics_async(self, fixture_id: int) -> List[Dict]:
    """Fetch in-match statistics asynchronously (with sync cache fallback, TTL 2min)."""

async def get_fixture_events_async(self, fixture_id: int) -> List[Dict]:
    """Fetch match events asynchronously (with sync cache fallback, TTL 2min)."""
```

Ambos verificam cache antes de chamar a API e fazem graceful degradation (retornam `[]` em caso de erro).

#### Camada 2 — `parse_fixture_statistics()` (`api_football_client.py`)

Método estático que extrai todos os campos da resposta `/fixtures/statistics` em um dict estruturado `{home: {...}, away: {...}}`:

| Campo extraído | Chave no dict | Tipo |
|---|---|---|
| Ball Possession | `possession` | `int` (%) |
| Shots on Goal | `shots_on_goal` | `int` |
| Shots off Goal | `shots_off_goal` | `int` |
| Shots insidebox | `shots_inside_box` | `int` |
| Shots outsidebox | `shots_outside_box` | `int` |
| Goalkeeper Saves | `goalkeeper_saves` | `int` |
| Corner Kicks | `corner_kicks` | `int` |
| Fouls | `fouls` | `int` |
| Yellow Cards | `yellow_cards` | `int` |
| Red Cards | `red_cards` | `int` |
| Total Shots | `total_shots` | `int` |
| Blocked Shots | `shots_blocked` | `int` |
| Offsides | `offsides` | `int` |
| Total passes | `passes_total` | `int` |
| Passes accurate | `passes_accurate` | `int` |
| Passes % | `passes_pct` | `int` (%) |
| expected_goals | `expected_goals` | `float` |

Trata strings percentuais (`"65%"` → `65`) e conversões numéricas automaticamente.

#### Camada 3 — `parse_fixture_events()` (`api_football_client.py`)

Método estático que extrai eventos estruturados da resposta `/fixtures/events`:

| Lista | Campos |
|---|---|
| `goals` | `time`, `team`, `player`, `assist`, `detail` |
| `cards` | `time`, `team`, `player`, `card_type` (Amarelo/Vermelho), `detail` |
| `substitutions` | `time`, `team`, `player_in`, `player_out` |
| `red_card_events` | `time`, `team`, `player` (acesso rápido para regra anti-BTTS) |

Trata `time.extra` para acréscimos (ex: `"45+2"`).

#### Camada 4 — `get_match_live_data()` com `asyncio.gather` (`api_football_client.py`)

Modificação do método unificado para buscar statistics + events + injuries **em paralelo** com timeout de 8s por task:

```python
async def _fetch_statistics() -> List[Dict]:
    return await asyncio.wait_for(
        self.get_fixture_statistics_async(fixture_id), timeout=8.0
    )

async def _fetch_events() -> List[Dict]:
    return await asyncio.wait_for(
        self.get_fixture_events_async(fixture_id), timeout=8.0
    )

async def _fetch_injuries() -> List[Dict]:
    return await asyncio.wait_for(
        self.get_injuries(fixture_id), timeout=8.0
    )

raw_stats, raw_events, injuries = await asyncio.gather(
    _fetch_statistics(), _fetch_events(), _fetch_injuries()
)
```

**Graceful degradation:** cada task é envolvida em try/except — se uma falhar (timeout, erro de rede), as outras continuam normalmente. O resultado final inclui `match_statistics` e `match_events` parseados.

**Enriquecimento cruzado:** após o gather, possession e corners dos statistics detalhados são mesclados no `live_data` quando os dados inline estavam ausentes.

**Separação pré-jogo/ao vivo:** o `asyncio.gather` só executa para jogos live ou finalizados. Jogos pré-jogo buscam apenas injuries (sem statistics/events disponíveis).

#### Camada 5 — Posse de bola em `extract_live_data()` e `_format_live_status()` (`api_football_client.py`)

- `extract_live_data()` agora extrai `home_possession` e `away_possession` do campo `statistics` inline do fixture (tipo `"Ball Possession"`, valor `"65%"` → `65`).
- `_format_live_status()` inclui `Posse: 65%x35%` na string de status, junto com escanteios.
- Exemplo de saída: `"Segundo tempo em andamento: 65 min, Placar: 2-1, Posse: 65%x35%, Escanteios: 5+3=8"`.

#### Camada 6 — RAIO-X TÁTICO e contexto estendido (`mistral_analysis.py`)

Novo método `_format_extended_live_context()` que gera uma string densa de contexto tático:

```
Status: 65 min (2T). Placar: Team A 2-1 Team B.
DOMINIO: Posse (65% x 35%).
PRESSAO: Chutes no Alvo (5 x 1), Chutes na Area (8 x 2), Finalizacoes Totais (12 x 4), Escanteios (5 x 3 = 8).
DEFESA: Defesas do Goleiro (1 x 4), Chutes Bloqueados (2 x 1).
DISCIPLINA: Faltas (10 x 12), Amarelos (2 x 3), Vermelhos (0 x 1).
PASSES: Precisos (320 x 180), Total (400 x 250), Acerto (80% x 72%).
xG AO VIVO: 1.85 x 0.42.
EVENTOS: Gol de Team A (Player X) aos 23 min; Cartao Vermelho para Team B (Player Y) aos 55 min.
```

Injetado no prompt da Mistral como seção `RAIO-X TATICO AO VIVO` com instrução obrigatória de leitura.

#### Camada 7 — REGRA ANTI-VIÉS BTTS no prompt (`mistral_analysis.py`)

Reescrita da seção `IMPORTANTE` com regras explícitas:

- **BTTS só com evidência:** ambos os times devem ter 3+ chutes no alvo
- **0-1 chutes no alvo = EV+ negativo para BTTS:** não recomendar
- **0 finalizações totais = time não vai marcar:** recomendar BTTS Não ou ML
- **Posse > 65% com muitos chutes:** focar em ML do dominante ou Over gols
- **> 6 escanteios antes dos 60min:** considerar Escanteios Over
- **Cartão vermelho:** time com menos jogadores perde volume ofensivo
- **Hierarquia de alternativas:** ML > Over gols > Over escanteios > BTTS Não > BTTS Sim

### Integração no fluxo (`ai_analysis.py`)

A rota `/ai/match/{id}/analysis` agora:
1. Recebe `match_statistics` e `match_events` do `get_match_live_data()`
2. Chama `_format_extended_live_context()` para gerar o RAIO-X TÁTICO
3. Injeta como `context["live_data_extended"]` no prompt da Mistral
4. Log aprimorado: `has_stats=True/False`, `has_events=True/False`

### Campos novos no retorno de `get_match_live_data()`

| Campo | Tipo | Descrição |
|---|---|---|
| `match_statistics` | `Dict` | Statistics parseados `{home: {...}, away: {...}}` |
| `match_events` | `Dict` | Events parseados `{goals, cards, substitutions, red_card_events}` |
| `live_data.home_possession` | `int \| None` | Posse de bola do mandante (%) |
| `live_data.away_possession` | `int \| None` | Posse de bola do visitante (%) |

### Lição aprendida

1. **Dados disponíveis na API mas não consumidos = oportunidade perdida** — A API-Football sempre retornou statistics e events para jogos ao vivo, mas o sistema nunca os buscava. 17 campos estatísticos ficavam inacessíveis enquanto a Mistral tomava decisões com informação incompleta.

2. **`asyncio.gather` com timeout individual é o padrão correto para dados live** — Buscar 3 endpoints em série adiciona 3x a latência. Com gather + timeout de 8s por task, o tempo total é o do mais lento (não a soma), e falhas individuais não bloqueiam as demais.

3. **Viés de modelo requer contra-regras explícitas** — LLMs tendem a recomendar BTTS como "opção segura" porque é um mercado binário simples. Sem instrução explícita para avaliar volume ofensivo, o modelo ignora a assimetria do jogo. A regra "BTTS só com 3+ chutes no alvo de ambos" é uma heurística simples mas eficaz contra esse viés.

4. **Contexto denso > contexto verboso para LLMs** — O formato "DOMINIO: ... PRESSAO: ... DEFESA: ..." é mais eficiente que parágrafos descritivos. O modelo processa dados tabulares/estruturados melhor que prosa narrativa, e o prompt fica menor (menos tokens = mais espaço para reasoning).

---

## 018 — Remoção de submodule refs `.claude/worktrees` que quebravam CI

**Data:** 2026-03-15
**Arquivos afetados:** `.claude/worktrees/kind-vaughan`, `.claude/worktrees/sweet-elion`, `.gitignore`
**Severidade:** Alta
**Status:** Corrigido
**Commit:** `92392b5`

### Problema identificado

O CI (GitHub Actions) falhava na etapa de post-job cleanup com o erro:

```
fatal: No url found for submodule path '.claude/worktrees/kind-vaughan' in .gitmodules
```

O workflow não conseguia completar a etapa `git submodule foreach --recursive`, causando exit code 128.

### Causa raiz

Dois diretórios `.claude/worktrees/kind-vaughan` e `.claude/worktrees/sweet-elion` foram acidentalmente commitados como objetos git do tipo `160000 commit` (referências de submodule). Porém, não existia um arquivo `.gitmodules` definindo a URL desses submodules. O git interpretava as entradas como submodules sem configuração, quebrando qualquer operação de `git submodule`.

```
160000 commit 7d89acd1dee74be231c917fdb2c297c63e26d607  .claude/worktrees/kind-vaughan
160000 commit 281150987ba90bf1e26441d4863a54811d8234a5  .claude/worktrees/sweet-elion
```

Esses objetos eram resquícios de worktrees do Claude Code que foram tratados como submodules pelo git ao serem adicionados ao index.

### Correções aplicadas (2 camadas)

1. **Remoção dos objetos do index** — `git rm --cached` para remover ambas as entradas `160000 commit` do tree do repositório.

2. **`.gitignore` atualizado** — Adicionada a linha `.claude/worktrees/` ao `.gitignore` para impedir que worktrees futuros sejam commitados acidentalmente.

### Lição aprendida

1. **Worktrees do git criam referências `160000` quando adicionados ao index** — Um diretório que contém um repositório git independente (worktree) é tratado como gitlink (submodule ref) pelo `git add`. Sem um `.gitmodules` correspondente, a referência fica órfã e quebra `git submodule` commands.

2. **CI cleanup é sensível a submodules malformados** — O GitHub Actions executa `git submodule foreach --recursive` no post-job, e qualquer submodule sem URL no `.gitmodules` causa falha fatal. Isso pode bloquear **todos** os workflows do repositório.

3. **Diretórios de ferramentas devem estar no `.gitignore` desde o início** — `.claude/worktrees/`, assim como `node_modules/` e `.next/`, são artefatos locais que nunca devem ser versionados.

---

## 019 — Liga dinamarquesa misturada entre jogos da Premier League + Duplas HTTP 504

**Data:** 2026-03-15
**Arquivos afetados:** `frontend/next/src/components/MatchesList.tsx`, `backend/routes/combinadas.py`, `frontend/next/src/app/api/combinadas/route.ts`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado (2 bugs)

1. **Liga dinamarquesa entre jogos da EPL** — O jogo Esbjerg vs Hillerød (Superliga dinamarquesa) aparecia visualmente entre jogos da English Premier League no dashboard. As ligas não eram separadas corretamente na lista.

2. **Duplas HTTP 504 (Gateway Timeout)** — Ao clicar em "Duplas", o sistema retornava erro 504. O servidor não conseguia responder dentro do limite de tempo.

### Causa raiz

#### Bug 1 — Ordem de ligas não-determinística

1. **Backend ThreadPoolExecutor sem ordenação** — `fixtures.py` processa ligas em paralelo com `ThreadPoolExecutor`. Os resultados são mergeados com `out.extend(records)` na ordem de conclusão das threads (`as_completed`), que é não-determinística.

2. **Frontend sem sort de grupos** — `MatchesList.tsx` agrupa matches por `leagueId` usando `reduce()` e renderiza com `Object.entries()`, que preserva a ordem de inserção. Se a thread da Superliga terminar antes da Premier League, os jogos dinamarqueses aparecem primeiro.

#### Bug 2 — Duplas re-fetch + timeout math quebrado

1. **Re-fetch completo de fixtures** — O endpoint `/combinadas` (GET) chamava internamente `get_fixtures()`, que refazia TODAS as chamadas de API externas (FootyStats: resolve_season_id + get_league_matches + get_league_season_stats + get_league_teams = 4+ calls HTTP por liga). Com 10-20 ligas selecionadas, isso gerava 40-80+ chamadas HTTP.

2. **Timeout math incompatível** — `COMBINADAS_TIMEOUT_MS = 55_000` por tentativa + auto-retry = 110s potencial. Mas `maxDuration = 60` (limite do Vercel) → a função era morta aos 60s → HTTP 504.

3. **Trabalho duplicado** — O frontend já tinha todos os matches carregados em `allMatches` (com `predictions`/`mercados`), mas enviava apenas IDs de ligas ao backend, forçando re-fetch.

### Correções aplicadas (4 camadas)

#### Camada 1 — Ordenação de ligas no frontend (`MatchesList.tsx`)

Após o `reduce()` que agrupa matches por `leagueId`, os grupos são ordenados pela posição da liga em `AVAILABLE_LEAGUES`:

```typescript
const leagueOrder = AVAILABLE_LEAGUES.reduce((map, l, i) => { map[l.id] = i; return map; }, {} as Record<string, number>);
const sortedLeagueEntries = Object.entries(matchesByLeague).sort(
  ([a], [b]) => (leagueOrder[a] ?? 999) - (leagueOrder[b] ?? 999),
);
```

Ligas não mapeadas recebem posição 999 (ficam no final). A renderização agora usa `sortedLeagueEntries.map()` em vez de `Object.entries(matchesByLeague).map()`.

#### Camada 2 — Novo endpoint POST `/combinadas` (`backend/routes/combinadas.py`)

Endpoint que recebe os matches já carregados no corpo da requisição, eliminando o re-fetch:

```python
@router.post("/combinadas")
def combinadas_post(payload: Dict[str, Any] = Body(...)):
    jogos = payload.get("matches") or []
    # Map frontend "predictions" → backend "mercados"
    for jogo in jogos:
        if "mercados" not in jogo and "predictions" in jogo:
            jogo["mercados"] = jogo["predictions"]
    return _run_combinadas(jogos, tipos_list, min_status, limite_intra, limite_inter)
```

O endpoint GET legado é mantido para compatibilidade.

#### Camada 3 — Timeout corrigido (`frontend/next/src/app/api/combinadas/route.ts`)

- `COMBINADAS_TIMEOUT_MS` reduzido de 55s → 25s
- Retry condicionado a `result.durationMs < 30_000` (só retenta se sobra tempo)
- Nova rota POST que encaminha o body ao backend
- Rota GET legada mantida com mesma lógica de timeout

#### Camada 4 — `fetchCombinadas` usa POST com dados locais (`dashboard/page.tsx`)

```typescript
const payload = {
  matches: allMatches.map((m) => ({
    id: m.id, leagueId: m.leagueId, leagueName: m.leagueName,
    homeTeam: m.homeTeam.name, awayTeam: m.awayTeam.name,
    datetime: m.datetime, status: m.status, odds: m.odds,
    stats: m.stats, mercados: m.predictions,
  })),
  tipos: "intra,inter",
  min_status: minStatus,
  limite_intra: 10, limite_inter: 10,
};
const res = await fetch("/api/combinadas", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(payload),
});
```

Dependência do `useCallback` mudou de `[dateMode, combinadasLeagues]` para `[allMatches]`.

### Impacto na performance

| Métrica | Antes | Depois |
|---|---|---|
| Chamadas HTTP externas (duplas) | 40-80+ (re-fetch todas as ligas) | 0 (dados já carregados) |
| Latência esperada (duplas) | 30-90s (timeout frequente) | < 2s (CPU-only, sem I/O) |
| Timeout por tentativa | 55s | 25s |
| Tempo máximo total | 110s (> maxDuration 60s → 504) | 50s (< maxDuration 60s) |

### Lição aprendida

1. **Nunca re-buscar dados que o cliente já possui** — O padrão GET com league IDs forçava o backend a refazer todo o pipeline de coleta. Quando o frontend já tem os dados (matches com mercados), enviar via POST elimina 100% da latência de I/O externo.

2. **Timeout math deve considerar retries dentro do maxDuration** — `timeout_por_tentativa * max_tentativas < maxDuration` é uma invariante que deve ser respeitada. Caso contrário, o retry causa o próprio 504 que tenta evitar.

3. **Ordem de renderização no frontend não deve depender de ordem de I/O** — Quando dados vêm de processamento paralelo (threads, Promise.all, etc.), a ordem de chegada é não-determinística. Sempre aplicar sort explícito antes de renderizar.

---

## 020 — Auditoria marca duplas com escanteios como ERROU quando acertaram (homeCornersCount ausente no normalizeMatch)

**Data:** 2026-03-16
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta (relatório de auditoria incorreto)
**Status:** Corrigido
**Relacionado:** #006, #014

### Problema identificado

Duplas intra-jogo contendo mercados de escanteios (ex: "Under 3.5 gols" + "Escanteios Over 8.5") eram marcadas como **ERROU** no relatório de auditoria mesmo quando ambos os prognósticos acertaram. Exemplo: St. Mirren x Rangers — Under 3.5 gols e Escanteios Over 8.5 acertaram, mas o sistema exibia ERROU.

### Causa raiz

A função `normalizeMatch()` em `dashboard/page.tsx` transforma os dados do backend para o formato `Match` usado no frontend. O backend (`fixtures_service.py`) já envia `homeCornersCount` e `awayCornersCount` em `stats` para jogos finalizados. Porém, `normalizeMatch()` **não copiava** esses campos para o objeto `stats` de saída — copiava dezenas de outros campos (homeCornersPerMatch, awayCornersPerMatch, etc.) mas omitia os contadores reais de escanteios do jogo.

Resultado: ao construir `actualByKey` em `computeLocalCombinadas()` (`localAudit.ts`), o código usava `m.stats.homeCornersCount` e `m.stats.awayCornersCount`, que eram `undefined` → `totalCorners = 0`. Para "Escanteios Over 8.5", a avaliação `totalCorners > 8.5` retornava `false` (0 > 8.5) → ERROU, mesmo quando o jogo real teve 9+ escanteios.

### Correção aplicada

Adicionados `homeCornersCount` e `awayCornersCount` ao objeto `stats` em `normalizeMatch()`:

```typescript
homeCornersCount: item.stats?.homeCornersCount ?? item.home_team_corner_count ?? undefined,
awayCornersCount: item.stats?.awayCornersCount ?? item.away_team_corner_count ?? undefined,
```

Fallback para `item.home_team_corner_count` / `item.away_team_corner_count` caso o backend envie no nível raiz do match.

### Lição aprendida

1. **Paridade entre backend e frontend na transformação** — Quando o backend adiciona novos campos (ex: #006, #003) para auditoria ou exibição, a função de normalização do frontend deve ser atualizada para repassá-los. Campos omitidos na transformação são descartados silenciosamente.

2. **Auditoria depende de dados completos** — A avaliação de duplas com escanteios exige `totalCorners` real. Usar 0 como fallback para "dado ausente" gera falsos negativos (ERROU quando acertou). Considerar PENDENTE quando dados essenciais faltam seria mais seguro, mas a correção prioritária foi garantir que os dados cheguem.

---

## 021a — CornerProgressBar invisível em ligas sem estatísticas inline (ex: Brasileirão)

**Data:** 2026-03-15
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Corrigido
**Relacionado:** #014, #015

### Problema identificado

A `CornerProgressBar` não aparecia em jogos ao vivo de algumas ligas (ex: Internacional x Bahia — Brasileirão), mesmo com prognósticos de escanteios (Over 8.5, Over 9.5, etc.). O Path B (#015) já incluía `currentCorners` a partir de `extract_live_data()`, mas o endpoint `/fixtures?live=all` da API-Football **não retorna estatísticas inline** para todas as ligas — em algumas (como Brasileirão), o campo `statistics` vem vazio.

### Causa raiz

O `extract_live_data()` lê `home_corners` e `away_corners` do campo `fixture.statistics` da resposta de `/fixtures?live=all`. Para ligas onde a API não inclui estatísticas inline nessa resposta, esses campos ficam `None` e o `currentCorners` nunca é preenchido.

### Correção aplicada

Fallback em **ambos os paths** (Path A e Path B): quando `home_corners` e `away_corners` são `None` após `extract_live_data()`, fazer chamada explícita a `/fixtures/statistics` com o `fixture_id`:

```python
if _corners is None:
    _fx_id = matched_fx.get("fixture", {}).get("id")
    if _fx_id is not None:
        _raw_stats = _afc.get_fixture_statistics(int(_fx_id), ttl_minutes=2)
        if _raw_stats:
            _parsed = _afc.parse_fixture_statistics(_raw_stats)
            _hc = _parsed.get("home", {}).get("corner_kicks")
            _ac = _parsed.get("away", {}).get("corner_kicks")
            if _hc is not None and _ac is not None:
                _corners = int(_hc) + int(_ac)
```

O endpoint `/fixtures/statistics` retorna dados completos por liga, incluindo Brasileirão.

### Lição aprendida

A API-Football não garante paridade entre ligas: `/fixtures?live=all` pode incluir `statistics` para algumas ligas e não para outras. Sempre ter fallback para endpoints dedicados (`/fixtures/statistics`) quando dados essenciais estiverem ausentes.

---

## 021b — Placar e minuto ao vivo não atualizam automaticamente

**Data:** 2026-03-15
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/hooks/useLivePolling.ts`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

O placar e o tempo de jogo (ex: 68') não atualizavam automaticamente para jogos ao vivo. O jogo Internacional x Bahia já estava em 90' mas a tela continuava mostrando 68'.

### Causa raiz (2 camadas)

1. **computeLiveInfo confiava cegamente no backend** — Quando o backend fornecia `period` e `minute`, o frontend usava esses valores diretamente. O backend tem cache de 1 min (FootyStats/API-Football), então os dados podem ficar desatualizados por até 1 min. Com polling de 30s, em cenários de cache agressivo ou tab em segundo plano, o minuto exibido congelava.

2. **Sem fetch inicial no polling** — O `useLivePolling` iniciava o intervalo mas não executava o fetch imediatamente. O primeiro update só ocorria após 30s.

### Correções aplicadas

1. **computeLiveInfo usa max(backend, estimado)** — Sempre calcula o minuto estimado a partir do kickoff (`Date.now() - kickoff`). Quando o backend fornece `period`/`minute`, usa `max(backend, estimado)` para nunca exibir um minuto menor que o tempo real decorrido.

2. **toDetailData repassa period/minute de computeLiveInfo** — O `MatchDetailCard` recebe `period` e `minute` já computados, garantindo consistência na lista e no card de detalhe.

3. **Fetch inicial no useLivePolling** — Quando `hasLiveMatches` é true, executa `wrappedFetch()` imediatamente ao montar o efeito, evitando espera de 30s para o primeiro update.

4. **Tick de re-render a cada 30s** — `setInterval` que chama `setAllMatches(prev => [...prev])` quando há jogos ao vivo. Força re-render para que `computeLiveInfo` rode novamente com `Date.now()` atualizado, mesmo quando o backend retorna dados em cache.

### Lição aprendida

Dados ao vivo com cache no backend exigem defesa no frontend: usar estimativas locais (kickoff + tempo decorrido) como piso e nunca exibir valores inferiores ao tempo real. Re-renders periódicos garantem que a UI reflita o tempo atual mesmo sem novos dados da API.

---

## 021 — Jogos dinamarqueses (Esbjerg, Hvidovre) ainda misturados entre jogos da EPL

**Data:** 2026-03-15
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta
**Status:** Corrigido
**Relacionado:** #019

### Problema identificado

Apesar da correção #019 (ordenação por `leagueOrder` no frontend e backend), os jogos Esbjerg vs Hillerød e Hvidovre vs Kolding IF (Superliga dinamarquesa) continuavam aparecendo entre jogos da Premier League inglesa no dashboard.

### Causa raiz

1. **Fallback de leagueId incorreto** — Quando `item.leagueId` estava ausente ou indefinido, o código usava `AVAILABLE_LEAGUES[0]?.id` (Premier League) como fallback, atribuindo jogos de outras ligas ao grupo da EPL.

2. **Possível inconsistência backend** — O backend pode retornar `leagueId: "superliga"` (id da config) em vez de `"denmark-superliga"` (id do frontend), ou jogos dinamarqueses com leagueId errado em cenários de fallback/merge.

### Correções aplicadas

1. **Heurística por nomes de times** — Função `inferLeagueFromTeams(home, away)` com lista de times conhecidos da Superliga dinamarquesa (Esbjerg, Hillerød, Hvidovre, Kolding IF, etc.). Se o jogo contém um desses times, força `leagueId: "denmark-superliga"`.

2. **Normalização "superliga" → "denmark-superliga"** — Quando o backend retorna `leagueId: "superliga"`, o frontend converte para `"denmark-superliga"` para consistência com `AVAILABLE_LEAGUES`.

3. **Fallback de leagueId alterado** — Em vez de `AVAILABLE_LEAGUES[0]?.id`, usa `"unknown"` quando `item.leagueId` está ausente. Evita atribuir incorretamente à Premier League; jogos com leagueId desconhecido vão para um grupo no final (posição 999).

### Lição aprendida

Quando a ordenação por liga não resolve mistura de jogos, investigar se o `leagueId` está correto na origem. Heurísticas baseadas em nomes de times são uma camada de defesa útil quando há inconsistência entre backend e frontend ou em fluxos de fallback.

---

## 021c — CornerProgressBar continua invisível (parser robusto + placeholder)

**Data:** 2026-02-05
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/routes/fixtures.py`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta
**Status:** Corrigido
**Relacionado:** #021a

### Problema identificado

Apesar da correção #021a (fallback para `/fixtures/statistics`), a `CornerProgressBar` continuava invisível em jogos ao vivo com prognósticos de escanteios (Over 8.5, Over 9.5, etc.).

### Causa raiz (hipóteses)

1. **Parser sensível a variações** — O `parse_fixture_statistics` usava match exato em `stat_key_map`. A API-Football pode retornar "Corner kicks" (k minúsculo) ou estrutura alternativa.
2. **Merge por nomes** — "SC Internacional" vs "Internacional" poderia falhar no match por nomes de times.
3. **Ausência de feedback** — Quando `currentCorners` era null, nada era exibido; o usuário não sabia se a funcionalidade existia ou estava carregando.

### Correções aplicadas

1. **`_extract_corners_from_stats()`** — Nova função em `api_football_client.py` que aceita múltiplos formatos de resposta, faz match case-insensitive para "corner" no `type`, e retorna `(home_corners, away_corners)`.
2. **Fallback no parse** — `parse_fixture_statistics` passou a aceitar "Corner kicks" (k minúsculo) e estrutura alternativa (team_block como lista de stats).
3. **Uso prioritário** — Path A e Path B em `fixtures.py` usam `_extract_corners_from_stats` primeiro; `parse_fixture_statistics` como fallback.
4. **Logging INFO** — Quando o fallback de corners falha, loga `fixture_id`, `raw_stats_len` e `first_block_keys` para diagnóstico.
5. **Placeholder** — Quando `targetCorners != null`, `status === "live"` mas `currentCorners == null`, exibe "Escanteios: aguardando dados...".
6. **normalizeTeamName** — Remoção de prefixos comuns (SC, EC, FC, etc.) para melhor match "SC Internacional" ↔ "Internacional".
7. **Log em dev** — `console.log` quando `currentCorners` é aplicado no merge (apenas em desenvolvimento).

### Lição aprendida

APIs externas variam em formato e nomenclatura. Parsers defensivos com match case-insensitive e suporte a estruturas alternativas aumentam resiliência. Placeholders melhoram UX e ajudam a distinguir "carregando" de "não disponível".

---

## 022 — League mismatch: correções gravadas com `league="ALL"` invisíveis para queries por liga específica

**Data:** 2026-02-05
**Arquivos afetados:** `backend/audit.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Correções aplicadas via batch audit e resultados de auditoria em lote eram gravadas com `league="ALL"`. Ao consultar correções ativas por liga específica (ex: `get_active_corrections("premier-league")`), a query usava `WHERE league = ?`, excluindo registros com `league="ALL"`. Essas correções globais ficavam invisíveis para o fluxo de análise por liga.

### Causa raiz

Em `ai_analysis.py`, `log_audit_result` e `log_correction` usam `league="ALL"` para batch audit (não há liga única). Em `audit.py`, `get_active_corrections(league)` filtra com `WHERE league = ?`, sem considerar que `"ALL"` deve ser retornado para qualquer liga.

### Correção aplicada

Em `get_active_corrections(league)`: quando `league` é informado, incluir também registros com `league="ALL"`:

```python
WHERE (league = ? OR league = 'ALL') AND status = 'applied'
```

### Lição aprendida

Quando correções/auditorias podem ser globais (`league="ALL"`), as queries por liga devem incluir esses registros para que ajustes aplicados em lote tenham efeito em todas as ligas.

---

## 023 — Erro de tipo TypeScript no campo `period` de `computeLiveInfo`

**Data:** 2026-02-05
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Média
**Status:** Corrigido

### Problema identificado

A função `computeLiveInfo` retornava `{ period: string; minute: number | null }`, mas o tipo `Match` e os consumidores esperam `period` como `"1T" | "HT" | "2T"`. O tipo `string` genérico causava incompatibilidade de tipo ao passar para componentes que esperam a união literal.

### Causa raiz

O retorno de `computeLiveInfo` usava `period: string` em vez do tipo literal `"1T" | "HT" | "2T"`, pois as atribuições (`period = "1T"`, `period = "HT"`, etc.) inferiam `string` por padrão.

### Correção aplicada

Tipar explicitamente o retorno como `{ period: "1T" | "HT" | "2T"; minute: number | null } | null` e garantir que todas as atribuições usem `as const` ou cast adequado para preservar o tipo literal.

### Lição aprendida

Funções que retornam valores de um conjunto fixo devem usar tipos de união literal em vez de `string` para garantir type-safety nos consumidores.

---

<!-- Novas correções devem ser adicionadas abaixo, seguindo o mesmo formato -->
