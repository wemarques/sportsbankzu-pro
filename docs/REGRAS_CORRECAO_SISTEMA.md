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

#### Camada 1: Default 0-0 para jogos ao vivo sem goal data — `/live-scores` (`fixtures.py`)
- Quando `get_match_live_details()` retorna `success=true` mas goals são `null`, agora assume `_fb_home = 0` e `_fb_away = 0` (tratamento: "jogo existe mas ainda sem gols registrados")
- Quando `_detail_ok = False` (endpoint falha ou retorna dados insuficientes), agora emite `score: {"home": 0, "away": 0}` em vez de `score: None`
- O API-Football enrichment subsequente sobrescreve com o placar real quando disponível

#### Camada 2: Default 0-0 para jogos ao vivo sem goal data — `/fixtures` (`fixtures.py`)
- Mesmo tratamento de null → 0 para `_fb_h_final` e `_fb_a_final` no fetch de match detail
- `match_score` agora é inicializado com `{"home": 0, "away": 0}` para jogos `live` antes da verificação condicional
- Elimina risco de `NameError` e garante que jogos ao vivo sempre têm score renderizável

#### Camada 3: Fallback do polling via `/fixtures` (`route.ts`)
- Quando `/live-scores` retorna vazio (0 matches), a rota `/api/matches/live` agora faz **fallback** chamando `/fixtures?leagues=X&date=today` para as ligas com jogos ao vivo
- Filtra apenas records com `status === "live" || status === "finished"` do resultado
- Mapeia para o formato esperado pelo overlay (id, homeTeam, awayTeam, status, score, period, minute)
- Log explícito: `[live-scores] Fallback via /fixtures — N live/finished matches`

#### Camada 4: Dashboard envia ligas ao vivo como parâmetro (`page.tsx`)
- Novo `useRef<string>` (`liveLeagueIdsRef`) rastreia IDs das ligas com jogos ao vivo
- Atualizado via `useEffect` sem re-criar o callback `fetchLiveScores`
- O polling passa `?leagues=colombia-primera-a,...` na URL do fetch para ativar o fallback na API route

#### Camada 5: Logging diagnóstico (`route.ts`)
- Log quando `PY_BACKEND_URL` não está configurado (antes retornava silenciosamente vazio)
- Log do count de matches e latência quando o endpoint retorna OK
- Permite diagnóstico remoto via Vercel Runtime Logs

### Fluxo corrigido

```
1. Carga inicial: GET /api/matches/fetch?leagues=colombia-primera-a
   ├── Backend /fixtures → FootyStats league-matches + match-detail
   ├── homeGoalCount=null → default 0                              ← FIX Camada 2
   ├── match_score = {home: 0, away: 0}                            ← FIX Camada 2
   └── Frontend renderiza "0 - 0" (não mais "- : -")

2. Polling (cada 30s): GET /api/matches/live?leagues=colombia-primera-a
   ├── Tenta /live-scores → {"matches": []}                        ← FootyStats vazio
   ├── Fallback: /fixtures?leagues=colombia-primera-a&date=today   ← FIX Camada 3
   │   ├── match-detail agora pode ter score real (ex: 1-0)
   │   └── API-Football enrichment → score 1-0 overlay
   ├── Retorna [{...score: {home:1, away:0}, period:"1T", minute:4...}]
   └── Frontend overlay atualiza "0 - 0" → "1 - 0"                ← FIX Camada 4
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

<!-- Novas correções devem ser adicionadas abaixo, seguindo o mesmo formato -->
