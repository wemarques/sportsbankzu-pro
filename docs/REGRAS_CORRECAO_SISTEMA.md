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

## 024 — Filtros de Status, Ordenação Prioritária e Separador Visual

**Data:** 2026-03-16
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Melhoria (UX)
**Status:** Implementado

### Problema identificado

O botão "Filtros em breve" era estático e não funcional. Além disso, as ligas brasileiras (Serie A e B) não tinham prioridade na exibição, dificultando a análise em dias com muitos jogos simultâneos. Não havia separação visual entre ligas nacionais e internacionais.

### Correções aplicadas (3 funcionalidades)

1. **Filtro de Status Funcional** — O botão "Filtros em breve" foi substituído por um `<select>` dropdown estilizado com 4 opções:
   - "Todos os Jogos" (padrão)
   - "Ao Vivo" (filtra `m.status === "live"`)
   - "Finalizados" (filtra `m.status === "finished"`)
   - "Não Iniciados" (filtra `m.status === "scheduled"`)
   - Estado React `statusFilter` adicionado ao componente Dashboard
   - Filtro integrado ao `displayMatches` useMemo

2. **Ordenação Prioritária** — A lógica de ordenação das ligas no `leagueGroups` useMemo foi refatorada:
   - **Prioridade 0:** Brazil Serie A (ID `brazil-serie-a`)
   - **Prioridade 1:** Brazil Serie B (ID `brazil-serie-b`)
   - **Prioridade 2:** Demais ligas em ordem alfabética por nome
   - Dentro de cada liga, jogos ordenados por horário (mantido)

3. **Separador Visual** — Linha divisória com gradiente e label "Ligas Internacionais" inserida automaticamente entre a última liga brasileira e a primeira liga internacional na renderização do `leagueGroups.map()`.

### Lição aprendida

Funcionalidades de filtragem e ordenação devem usar os IDs estáveis das ligas (`brazil-serie-a`, `brazil-serie-b`) em vez de string matching no nome, garantindo robustez contra mudanças de nomenclatura na API externa.

---

## 025 — Dropdown ilegível no tema escuro + Premier League como "unknown"

**Data:** 2026-03-16
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`, `backend/services/api_football_client.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

1. **Dropdown ilegível** — O `<select>` de filtros usava `var(--bg-secondary)` como background, mas o dropdown nativo do browser renderiza as `<option>` com fundo branco, tornando o texto invisível no tema escuro.

2. **Premier League como "unknown"** — Jogos vindos do API-Football (fallback quando FootyStats não retorna dados) apareciam com liga "unknown". Ex: Brentford vs Wolves exibido sem identificação de liga.

### Causa raiz

1. **Dropdown:** Elementos `<option>` do HTML nativo ignoram muitos estilos CSS, mas respeitam `background` e `color` inline. O `<select>` não tinha esses estilos nas options.

2. **EPL "unknown":** Em `api_football_client.py` linha 1345, o campo do record era `"league": league_id` em vez de `"leagueId": league_id`. O frontend espera `leagueId` (tipo `Match`). Sem esse campo, o fallback `item.leagueId ?? "unknown"` era acionado.

### Correções aplicadas (defesa em profundidade)

1. **Backend** — `api_football_client.py`: campo renomeado de `"league"` para `"leagueId"` no `fixtures_to_records()`.

2. **Frontend (defesa)** — `page.tsx`: normalização agora usa `item.leagueId ?? item.league ?? "unknown"` em ambos os pontos de normalização, garantindo que mesmo dados com campo antigo sejam tratados.

3. **Frontend (dropdown)** — Estilo inline com cores fixas do tema escuro (`#1a1a2e` background, `#e0e0e0` text) aplicado tanto no `<select>` quanto em cada `<option>`, evitando o problema de herança do browser.

### Lição aprendida

Ao criar records que trafegam entre backend e frontend, sempre validar que os nomes dos campos correspondem exatamente ao tipo TypeScript esperado. Um campo `"league"` vs `"leagueId"` pode causar fallback silencioso para "unknown" sem erro visível.

---

## 026 — Jogos duplicados por apelido vs nome completo (Wolves / Wolverhampton Wanderers)

**Data:** 2026-03-16
**Arquivos afetados:** `backend/services/api_football_client.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

O mesmo jogo (ex: Brentford vs Wolves) aparecia duplicado no dashboard:
1. Primeira entrada: "Brentford vs Wolves" (dados do API-Football com nome abreviado) — VIVO HT, placar 2-1
2. Segunda entrada: "Brentford vs Wolverhampton Wanderers" (dados do FootyStats com nome completo) — VIVO 2T, placar 0-0

O segundo registro era injetado como "jogo novo" porque o sistema não reconhecia "Wolves" como "Wolverhampton Wanderers".

### Causa raiz

A função `_team_names_match()` em `api_football_client.py` usava 4 estratégias de matching:
1. Exact match após normalização
2. Substring containment
3. Fuzzy match (SequenceMatcher ≥ 0.8)
4. Token overlap (≥ 50%)

Nenhuma dessas estratégias consegue resolver "Wolves" → "Wolverhampton Wanderers":
- **Substring:** "wolves" NÃO está contido em "wolverhampton wanderers"
- **Fuzzy:** ratio("wolves", "wolverhampton wanderers") ≈ 0.34 (muito abaixo de 0.8)
- **Token overlap:** {"wolves"} ∩ {"wolverhampton", "wanderers"} = ∅ (zero overlap)

Resultado: na etapa de injeção (CASE 1b em `fixtures.py:349-392`), o jogo do API-Football não era reconhecido como duplicata e era adicionado como novo registro.

### Correções aplicadas (defesa em profundidade — 4 camadas)

1. **Mapa de aliases (backend)** — Novo dicionário `_TEAM_ALIASES` em `api_football_client.py` com ~40 mapeamentos de apelidos/abreviações para nomes canônicos. Exemplos:
   - `"wolves"` → `"wolverhampton wanderers"`
   - `"man united"` / `"man utd"` → `"manchester united"`
   - `"spurs"` → `"tottenham hotspur"`
   - `"psg"` → `"paris saint germain"`
   - Times brasileiros: `"corinthians"`, `"palmeiras"`, `"flamengo"`, etc.

2. **Método `_resolve_alias()` (backend)** — Novo método estático que consulta o alias map antes de comparar. Integrado como primeira etapa do `_team_names_match()`:
   - Resolve ambos os nomes para forma canônica via alias map
   - Se canônicos são iguais → match imediato (antes de fuzzy/token)
   - Também verifica substring nos nomes canônicos

3. **Deduplicação pós-enrichment (backend)** — Nova função `_deduplicate_records()` em `fixtures.py` que é executada APÓS `_enrich_with_api_football()`:
   - Gera chave canônica por jogo via `_resolve_alias()` para cada time
   - Quando duplicatas são detectadas, mantém o record com maior "richness" (mais odds, predictions, stats)
   - Faz merge de dados live (score, status, period, minute) do record descartado para o mantido
   - Log detalhado de cada deduplicação para diagnóstico

4. **Deduplicação no frontend (page.tsx)** — Nova função `deduplicateMatches()` + mapa `TEAM_ALIASES`:
   - Aplica `resolveTeamAlias()` antes de comparar nomes de times
   - Executada após `normalizeMatch()` em AMBOS os code paths (fetch inicial + refetch)
   - Live score overlay (`fetchLiveScores`) também usa `resolveTeamAlias()` para matching
   - Merge inteligente: preserva odds/predictions do record mais rico + score/status do live

### Fluxo corrigido

```
Backend (_enrich_with_api_football):
  _team_names_match("Wolverhampton Wanderers", "Wolves")
    → _resolve_alias → "wolverhampton wanderers" == "wolverhampton wanderers" → ✓ match
    → FootyStats record é enriched com score ao vivo

Backend (_deduplicate_records — safety net):
  Se por qualquer razão o enrichment falhar e dois records chegarem:
    → chave canônica idêntica → mantém o mais rico, merge dados live

Frontend (deduplicateMatches — safety net final):
  Se backend enviar duplicatas (cache, timing, etc.):
    → resolveTeamAlias("Wolves") === resolveTeamAlias("Wolverhampton Wanderers")
    → Remove duplicata, mantém match com mais dados
```

### Lição aprendida

1. Fuzzy matching e token overlap são insuficientes para resolver apelidos populares de times. Um dicionário estático de aliases é necessário como primeira camada.
2. Prevenir a criação de duplicatas (alias no matching) NÃO é suficiente sozinho — dados em cache, race conditions e fontes múltiplas podem reintroduzir duplicatas. É necessário um passo final de deduplicação (defesa em profundidade).
3. Deduplicação deve existir em AMBAS as camadas (backend e frontend) porque o frontend pode receber dados de cache do browser ou de versões não-atualizadas do backend (Vercel, Lambda).

---

## 027 — Fallback de ID de match usava índice numérico em vez de nomes canônicos

**Data:** 2026-03-16
**Arquivos afetados:** `backend/services/fixtures_service.py`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Média
**Status:** Corrigido

### Problema identificado

Quando o match não possuía um `id` válido da API, o sistema gerava um ID de fallback usando o índice numérico do loop (`idx`). Isso causava:
1. IDs instáveis entre requests (o mesmo jogo podia receber `idx=3` ou `idx=7` dependendo da ordem)
2. Falha no deduplicador ao comparar IDs de fontes diferentes
3. Match detail cards não abriam corretamente quando o ID mudava entre refetches

### Causa raiz

O fallback de ID era construído como `f"{league_id}_{idx}"` em vez de usar os nomes dos times como parte da chave.

### Correção aplicada

Substituído o fallback por um ID baseado em nomes canônicos dos times:
- `f"{league_id}_{canon_home}_{canon_away}"` usando `_resolve_alias()` para garantir consistência
- Remove o uso de `idx` completamente do gerador de IDs
- Garante que o mesmo jogo sempre recebe o mesmo ID, independente da ordem de processamento

### Lição aprendida

IDs de fallback devem ser determinísticos e baseados em propriedades imutáveis do dado (nomes de times), nunca em posição ordinal do processamento.

---

## 028 — Pipeline preditivo de 5 camadas com contrato unificado de saída

**Data:** 2026-03-17
**Arquivos afetados:**
- Novos: `backend/models/market_output.py`, `backend/services/data_governance.py`, `backend/modeling/poisson_matrix.py`, `backend/modeling/corners_engine.py`, `backend/services/ev_classification.py`, `backend/services/bankroll_engine.py`, `backend/services/correlation_matrix.py`, `backend/routes/market_analysis.py`
- Modificados: `backend/services/market_service.py`, `backend/services/combinadas_service.py`, `backend/main.py`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/lib/kelly.ts`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Evolução arquitetural (não é correção de bug)
**Status:** Implementado

### Problema identificado

O pipeline de prognósticos tinha diversas limitações:
1. **Mercados derivados independentemente** — Over/Under, BTTS e 1X2 eram calculados por lógicas separadas, sem garantia de consistência probabilística
2. **Sem contrato unificado** — cada mercado retornava campos diferentes, dificultando o frontend e o bankroll
3. **Classificação binária** — apenas SAFE ou NEUTRO, sem graduação intermediária para multiples
4. **EV calculado sem odd real** — o sistema gerava sugestões de stake mesmo sem confirmar odd de bookmaker
5. **Escanteios sem motor próprio** — usava apenas dados crus do FootyStats, sem modelagem Poisson
6. **Sem controle de correlação** — multiples podiam combinar mercados redundantes (ex: 1X2 Home + DC 1X)
7. **Sem caps de exposição** — sem limite por jogo, dia ou mercado no bankroll

### Solução implementada — 5 camadas

#### Camada 1: Governança de Dados (`data_governance.py` + `market_output.py`)

**Contrato único `MarketOutput`** com campos obrigatórios:
- `market_type`, `selection`, `raw_probability`, `calibrated_probability`
- `fair_odd`, `book_odd`, `ev`, `edge`
- `classification`, `reason_codes`, `data_quality_score`, `odds_available`, `source_flags`

**`data_quality_score`** (0-1) calculado com base em:
- Disponibilidade de probabilidades core (25%)
- Disponibilidade de lambdas/xG (15%)
- Disponibilidade de odds reais (25%)
- Probabilidades auxiliares Under/BTTS/Corners (15%)
- Odds de escanteios (10%)
- Maturidade da temporada (10%)

**Early season detection**: se `matches_played < 5`, todas as classificações SAFE são rebaixadas para NEUTRO_QUALIFICADO.

#### Camada 2: Motor Preditivo (`poisson_matrix.py` + `corners_engine.py`)

**Matriz de scoreline Poisson**: a partir de `lambda_home` e `lambda_away`, gera uma matriz completa de probabilidades `P(home=h, away=a)` para `h,a ∈ [0,8]`. Todos os mercados de gols são derivados dessa matriz:
- **1X2**: soma das probabilidades onde `h>a`, `h==a`, `h<a`
- **Over/Under**: soma onde `h+a > threshold` para 0.5, 1.5, 2.5, 3.5, 4.5
- **BTTS**: soma onde `h>=1 AND a>=1`
- **Double Chance**: derivado aritmeticamente do 1X2 (`dc_1x = home + draw`)

Isso garante consistência matemática: `P(home) + P(draw) + P(away) = 1.0000`.

**Motor de escanteios dedicado**: estima `λ_corners` combinando:
- Corners pró/contra dos times (60% direto + 30% cruzado + 10% liga)
- Aplica Poisson para derivar `P(Over 8.5)`, `P(Over 9.5)`, `P(Over 10.5)`, `P(Over 11.5)`
- Blend com pré-match potentials do FootyStats quando disponíveis (60% FS + 40% Poisson)

#### Camada 3: EV + Classificação (`ev_classification.py`)

**4 níveis de classificação**:

| Classificação | Stake | Múltiplas | System Bets |
|---------------|-------|-----------|-------------|
| **SAFE** | 100% Kelly | Elegível | Elegível |
| **NEUTRO_QUALIFICADO** | 60% Kelly | Elegível | Elegível |
| **NEUTRO** | 0 (exibe prob/fair odd) | Não elegível | Não elegível |
| **NO_BET** | 0 | Bloqueado | Bloqueado |

**Regra de NEUTRO qualificado**: um NEUTRO é promovido se:
- EV >= 2%
- Data quality >= 0.40
- Probabilidade calibrada >= 50%
- Odds reais disponíveis

**EV real** só é calculado quando `book_odd` está confirmada. Sem odd real, o mercado mostra apenas probabilidade e fair odd, sem stake.

**Thresholds dinâmicos por mercado** (com fallback hardcoded):
- 1X2: SAFE >= 55%, NEUTRO >= 42%
- Over/Under: SAFE >= 68%, NEUTRO >= 58%
- BTTS: SAFE >= 70%, NEUTRO >= 60%
- Double Chance: SAFE >= 75%, NEUTRO >= 65%
- Corners: SAFE >= 65%, NEUTRO >= 55%

**Reason codes**: `LOW_DATA_QUALITY`, `NO_ODDS_AVAILABLE`, `NEGATIVE_EV`, `INSUFFICIENT_EDGE`, `EARLY_SEASON_FALLBACK`, `HIGH_MARKET_CORRELATION`, `LINEUP_UNCERTAINTY`, `POSITIVE_EV`, `STRONG_EDGE`, `HIGH_CALIBRATED_PROB`, etc.

#### Camada 4: Bankroll (`bankroll_engine.py`)

- **Quarter Kelly** como padrão (multiplicador 0.25)
- **Multiplicador por classificação**: SAFE=1.0, NEUTRO_Q=0.60, NEUTRO/NO_BET=0.0
- **Caps**: 5% por aposta, 8% por jogo, 30% por dia, 15% por tipo de mercado
- **Haircuts multiplicativos**:
  - -15% se `data_quality < 0.4`
  - -20% se early season
  - -10% se lineup não confirmada
  - -10% se injuries relevantes
  - -15% se alta correlação entre picks
  - -10% se mercado volátil
- **Sem stake quando sem odd real**: exibe probabilidade e fair odd, não gera R$

#### Camada 5: System Bets + Correlação (`correlation_matrix.py`)

**Matriz de correlação entre mercados do mesmo jogo**:
- **Bloqueado** (corr > 0.60 ou redundante): 1X2 Home + DC 1X, Under 3.5 + Under 4.5, Over 2.5 + Over 3.5
- **Permitido com cuidado** (0.3-0.6): Over 2.5 + BTTS (0.50), 1X2 Home + Over 2.5 (0.35)
- **Permitido livremente** (<0.3): 1X2 + Corners, Under + Corners

**Regras de elegibilidade para múltiplas**:
- Permitidos: SAFE + NEUTRO_QUALIFICADO
- Bloqueados: NO_BET, mercados sem odd real, quality < 0.30
- Até 2 seleções por jogo (desde que não redundantes e correlação < 0.60)
- Haircut de exposição quando 2 picks do mesmo jogo: `max(0.5, 1.0 - corr * 0.5)`

**System bets**: viabilidade via break-even filter (retorno mínimo com N-1 acertos deve cobrir investimento).

### Integração com código existente

- `market_service.py`: nova função `selecionar_mercados_v2()` com fallback automático para lógica legacy
- `combinadas_service.py`: integrada com `correlation_matrix.py` via `_check_correlation()`; aceita `NEUTRO_QUALIFICADO`
- `main.py`: registra rota `/analysis/match` e `/analysis/batch`
- Calibrator existente (`calibrator.py`) reutilizado integralmente na camada 3
- Market validator (`market_validator.py`) continua sendo aplicado após classificação

### Frontend

- `leagues.ts`: novos tipos `MarketClassification`, `ReasonCode`, `MatchPrediction` com campos estendidos
- `kelly.ts`: `CLASSIFICATION_STAKE_MULTIPLIER` aplicado no cálculo de Kelly; haircuts por reason codes
- `MatchDetailCard.tsx`: exibe EV%, odd da casa, fair odd, stake sugerida, quality score e reason codes
- `match-detail-card.css`: estilos para NEUTRO_QUALIFICADO (roxo) e NO_BET

### Decisão de design — sem restrição excessiva

A política **não** restringe o sistema a "só SAFE":
- NEUTRO_QUALIFICADO mantém volume útil (elegível para stakes e múltiplas com 60% Kelly)
- 2 seleções por jogo são permitidas (não restrito a 1)
- Correlação bloqueia apenas pares verdadeiramente redundantes
- Thresholds de NEUTRO são acessíveis (42% para 1X2, 58% para O/U)

### Lição aprendida

1. Derivar todos os mercados de gols da mesma matriz Poisson elimina inconsistências probabilísticas
2. NEUTRO qualificado é essencial para manter volume útil sem comprometer qualidade
3. Correlação entre mercados deve ser tratada com matriz explícita, não regras ad-hoc
4. Stake zero quando odd não está confirmada previne EV fantasma

---

## 029 — ML pipeline improvements

**Data:** 2026-03-17
**Arquivos afetados:** `backend/ml/train_model.py`, `backend/ml/predictor.py`, `backend/ml/feature_engineering.py`, `backend/ml/market_models.py`, `backend/routes/ml.py`, `backend/cron_handler.py`, `cli/commands/ml.py`
**Severidade:** Alta (evolução arquitetural ML)
**Status:** Implementado
**Commits:** `64fd2e6`, `23797a1`, `dd40f7d`, `614e603`

**Alias:** Pipeline ML — 8 melhorias de qualidade + temporal decay + quality gate Poisson

### Problema identificado

O pipeline ML tinha múltiplas fraquezas que comprometiam a qualidade das previsões:
1. **Sem comparação no-odds** — impossível saber se o ML adicionava valor além das odds de mercado
2. **Calibradores desatualizados** — não eram retreinados automaticamente após auditorias
3. **Ligas fracas ativas** — ligas com Brier >= 0.63 continuavam usando ML em vez de fallback Poisson
4. **Sem gating de eficiência** — ML ativado mesmo quando o mercado já era eficiente (odds próximas do outcome real)
5. **Hiperparâmetros fixos** — mesma profundidade de árvore para 200 e 2000 amostras
6. **Sem decaimento temporal** — jogos de 2 anos atrás tinham o mesmo peso que jogos recentes
7. **Sem ECE** — calibração avaliada apenas por Brier, sem Expected Calibration Error
8. **Market models sem quality gate** — modelos O/U e BTTS publicados mesmo quando piores que Poisson

### Correções aplicadas (3 iterações)

#### Iteração 1 — 8 melhorias (`64fd2e6`)

1. **No-odds variant**: treina modelo sem features `implied_odds` para medir valor incremental do ML
2. **Auto-retrain calibrators**: `cron_handler.py` retreina calibradores após batch audit
3. **Auto-deactivate**: ligas com Brier >= 0.63 desativadas automaticamente
4. **Market efficiency gating**: calcula R² de odds vs outcome; ML só ativa quando mercado é ineficiente
5. **Adaptive hyperparameters**: árvores mais rasas para amostras < 600
6. **Temporal decay**: peso `0.95^weeks_ago` para reduzir drift
7. **ECE + reliability diagram**: adicionados à validação walk-forward
8. **Market models dedicados**: modelos O/U e BTTS integrados ao pipeline de retrain e inferência

#### Iteração 2 — Temporal decay v2 + quality gate baseline (`23797a1`)

- **Temporal decay corrigido**: usa timestamps reais dos jogos (não índice sequencial); half-life configurável (default 26 semanas); piso mínimo de 0.05 para evitar colapso de amostras efetivas
- **Quality gate baseline**: calcula Brier de preditor constante (base rate) durante treinamento; salva `beats_baseline` e `brier_baseline` no `.pkl`; `predict_market()` retorna `None` (fallback Poisson) se modelo falhou no gate

#### Iteração 3 — Poisson benchmark + sanity check cronológico (`dd40f7d`)

- **Gate Poisson real**: substitui gate baseline (p*(1-p)) por comparação com Brier do Poisson calculado no mesmo split de validação, usando mesmas lambdas da produção (`home_goals_scored_avg_r5` / `away_goals_scored_avg_r5`); salva `brier_ml`, `brier_poisson`, `beats_poisson` no `.pkl`
- **Sanity check cronológico**: verifica se timestamps estão em ordem ascendente antes do walk-forward; ordena automaticamente se necessário; loga `first_date`, `last_date`, `sorted` por liga

#### Hotfix — f-string format (`614e603`)

- Corrigido erro de formato condicional em `logger.info` (`brier_poisson:.4f if...`) que impedia treinamento de market models
- Adicionado `scripts/retrain_synthetic.py` para validação offline quando API FootyStats indisponível

### Lição aprendida

1. **Quality gate deve comparar com o fallback real** — Brier baseline (preditor constante) é um limiar muito baixo. O benchmark correto é o Poisson que o sistema já usa como fallback. Se ML não bate Poisson, publicar o modelo desperdiça recursos e piora previsões.

2. **Temporal decay precisa de timestamps reais** — Usar índice sequencial (`n_samples/4`) como proxy temporal introduz viés quando dados não são uniformemente espaçados. Timestamps reais com half-life configurável são mais robustos.

3. **Iterar incrementalmente é mais seguro** — As 3 iterações (implementação → correção decay/gate → upgrade para Poisson benchmark) permitiram validar cada mudança isoladamente em vez de um big-bang arriscado.

---

## 030 — ML retrain validate + promote workflows

**Data:** 2026-03-17
**Arquivos afetados:** `.github/workflows/ml-retrain-validate.yml` (novo), `.github/workflows/ml-retrain-promote.yml` (novo), `scripts/retrain_validate.py` (novo), `.gitignore`
**Severidade:** Evolução operacional
**Status:** Implementado
**Commits:** `e469a7b`, `f617064`, `aaf46d6`, `697e515` (ver também `91e998c` — scaffold inicial do split validate/promote)

**Alias:** ML Ops — workflows de validação e promoção com auditoria completa

### Problema identificado

O pipeline ML usava um workflow monolítico (`ml-retrain.yml`) que treinava e publicava modelos em S3 no mesmo job. Não havia:
1. Separação entre validação e deploy
2. Aprovação humana antes de publicar modelos em produção
3. Auditoria de artefatos (summaries, classificações por liga, metadados)
4. Verificação de proveniência do run de validação
5. Proteção contra publicação de pipelines incompletos

### Solução implementada — 2 workflows separados

#### Workflow 1: `ml-retrain-validate.yml`
- **Schedule**: terça 09:00 UTC (06:00 BRT)
- Executa pipeline completo: treina 1X2 + market models com dados reais da API
- Gera artefatos de auditoria: `training_summary.json`, `league_classifications.json`, `market_models_summary.json`, metadados por liga, `retrain.log`
- **Integrity check**: step dedicado verifica que todos os artefatos obrigatórios existem e não estão vazios (exit 1 em caso de falha)
- Artefatos nomeados com `run_number + sha` para rastreabilidade, retenção de 90 dias
- **NÃO publica em S3** — apenas valida

#### Workflow 2: `ml-retrain-promote.yml`
- **Manual only** (`workflow_dispatch`) — sem schedule automático
- Requer `environment: production` (aprovação via GitHub Environments)
- Recebe `validation_run_number` como input
- **Provenance check**: verifica via GH API que o run pertence a um validate bem-sucedido
- Opção de **dry run** para validação sem upload
- Publica TODOS os modelos (incluindo DEACTIVATED — gates de inferência decidem ativação)
- Copia summaries para `s3://.ml_audit/` com timestamp para trilha de auditoria

#### Script: `retrain_validate.py`
- Orquestra o pipeline completo incluindo todas as 8 melhorias do #029
- Exit code 1 em: zero ligas, >50% falharam, <100 partidas, artefatos ausentes
- Garante que pipelines incompletos não são tratados como sucesso

#### Hotfixes de workflow (`697e515`)
- Corrigido step de verificação que usava `run_number` como `run_id` na API do GitHub
- `download-artifact` usando `pattern` (glob) em vez de `name` (exact match)
- `download-artifact` com `run-id` explícito (buscava no run corrente em vez do de validação)

### Lição aprendida

1. **"Publicar em S3" ≠ "ativar em inferência"** — A elegibilidade é decidida em runtime pelos gates do `predictor.py` (Brier, beats_poisson, etc.), não pelo deploy. Isso permite publicar todos os modelos e deixar a decisão para o código de inferência.

2. **Provenance check é essencial** — Sem verificar que o `validation_run_number` pertence a um run de validate bem-sucedido, um promote poderia apontar para um run qualquer (ou inexistente).

3. **Workflows do GitHub Actions com cross-run artifacts são complexos** — `download-artifact` exige `run-id` (não `run-number`), e busca por nome exige `pattern` para glob. Testado em 3 iterações até funcionar corretamente.

---

## 031 — Market Reference Signal governance

**Data:** 2026-03-17
**Arquivos afetados:** `backend/services/market_reference_signal.py` (novo), `backend/services/market_service.py`, `backend/audit.py`, `backend/ai/prompt_templates.py`, `frontend/next/src/lib/api.ts`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/lib/localAudit.ts`, `frontend/next/src/components/BatchAuditPanel.tsx`, `tests/unit/test_market_reference_signal.py` (novo)
**Severidade:** Alta (nova camada de governança)
**Status:** Implementado
**Commit:** `21ed430`

**Alias:** Camada de governança Market Reference Signal

### Problema identificado

Picks individuais eram classificados (SAFE/NEUTRO/etc.) apenas com base em probabilidade e EV do jogo específico, sem considerar a **qualidade estrutural** do pipeline para aquele mercado naquela liga. Exemplo: um mercado O/U 2.5 poderia ser classificado como SAFE mesmo quando o modelo de mercado O/U estava desativado (fallback Poisson puro) ou quando a liga não tinha ML ativo para 1X2.

### Solução implementada — Market Reference Signal

#### Backend: `market_reference_signal.py`

Novo serviço que computa um **sinal de qualidade estrutural** por liga+mercado com 3 níveis:

| Sinal | Significado | Quando aplicado |
|-------|-------------|-----------------|
| **SAFE** | Pipeline completo e confiável | ML 1X2 ativo + market model ativo para o mercado |
| **NEUTRO** | Pipeline parcial ou fallback | ML 1X2 ativo mas sem market model, ou Corners (default) |
| **RESTRITO** | Pipeline indisponível | Liga sem ML ativo, ou market model falhou quality gate |

**`apply_signal_capping()`**: enriquece cada mercado com:
- `rawClassification`: classificação original do pick
- `finalClassification`: classificação após capping pelo sinal (nunca sobe, pode descer)
- `wasCappedByMarketSignal`: flag booleano
- Metadados do sinal (`signal_level`, `source`)

#### Integração

- **`market_service.py`**: integrado em ambos os paths V2 e legacy
- **`audit.py`**: correções automáticas de MARKET_REFERENCE_SIGNAL bloqueadas (v1 — requer avaliação manual)
- **`prompt_templates.py`**: estatísticas do signal incluídas no contexto da auditoria Mistral

#### Frontend

- **`MatchDetailCard.tsx`**: badge "Ref: SAFE/NEUTRO/RESTRITO" em cada mercado
- **`localAudit.ts`**: contadores de capping; usa `finalClassification` para accuracy
- **`BatchAuditPanel.tsx`**: exibe stats de capping quando picks foram limitados pelo signal

#### Testes

24 testes unitários cobrindo: computação do signal, capping, compatibilidade com auditoria, bloqueio de correções automáticas, e detecção de categoria de mercado.

### Lição aprendida

1. **Classificação individual não basta** — Um pick pode parecer SAFE pela probabilidade/EV, mas se o pipeline que gerou esses números é fraco (sem ML, sem market model), a confiança real é menor. O signal atua como **teto**, não como piso.

2. **Capping é mais seguro que substituição** — O signal nunca promove uma classificação, apenas rebaixa. Isso garante que a lógica existente de EV/probabilidade não é anulada, apenas limitada.

3. **Bloqueio de correção automática para features novas** — Ao introduzir uma nova camada de governança, é prudente bloquear correções automáticas na auditoria até que o comportamento seja validado em produção.

---

## 032 — Live score stuck at 0-0 + centralized merge

**Data:** 2026-03-17
**Arquivos afetados:** `backend/routes/fixtures.py`, `backend/services/footstats_client.py`, `backend/services/live_score_merge.py` (novo), `tests/unit/test_live_score_merge.py` (novo)
**Severidade:** Alta
**Status:** Corrigido
**Commits:** `1d812c4`, `ff620b1`, `00b9c48`

**Alias:** Placar ao vivo travado em 0-0 para jogos em andamento (A-League, etc.)

### Problema identificado

Jogos ao vivo (ex: A-League, MLS) exibiam placar 0-0 no dashboard mesmo quando já havia gols. O placar não atualizava em tempo real, mostrando dados pré-jogo durante toda a partida.

### Causa raiz (3 camadas)

1. **Colisão de cache** — `get_match_details()` (TTL 60min) e `get_match_live_details()` (TTL 30s) compartilhavam a mesma chave de cache, pois ambas chamam o mesmo endpoint FootyStats com parâmetros idênticos. Um fetch de detalhes pré-jogo servia dados estáticos 0-0 por até 60 minutos.

2. **Overwrite incondicional de placar** — Quando o endpoint de detalhe retornava 0-0 (dados stale), o código sobrescrevia incondicionalmente placares válidos vindos do `todays-matches`. Não havia guard para manter o placar mais alto.

3. **Early exit em falha de detalhe** — Quando o endpoint de detalhe falhava, o código emitia 0-0 hardcoded e pulava (`continue`) o enriquecimento via API-Football, eliminando a última chance de obter o placar correto.

### Correções aplicadas (3 iterações)

#### Iteração 1 — Fix das 3 causas raiz (`1d812c4`)

1. **Cache namespace**: adicionado parâmetro `_cache_ns` para diferenciar entries de detalhe (TTL longo) vs live (TTL curto), removido antes de enviar à API
2. **Guard de placar**: comparação de total de gols antes de sobrescrever — mantém o placar mais alto
3. **Fall-through em falha**: removido `continue` para permitir enriquecimento via API-Football mesmo quando detalhe falha

#### Iteração 2 — Merge centralizado com prioridade (`ff620b1`)

Extraída toda a lógica de merge de placar para `live_score_merge.py` com:
- **Prioridade de fontes**: API-Football > match detail > todays-matches > fallback 0-0
- **Guarda monotônica**: placar nunca decresce (previne regressão de 2-1 para 0-0)
- **Resolução de conflitos laterais**: quando fontes divergem no mesmo total, escolhe pela prioridade
- **Campos de observabilidade**: `scoreSourceFinal`, `scoreConflictDetected`, `apiFootballOverlayApplied`
- **17 testes de regressão** cobrindo 7 cenários especificados

#### Iteração 3 — Logging diagnóstico (`00b9c48`)

- Tags `[live-scores][diag]` e `[live-scores][diag-af]` em cada match ao vivo
- Loga cada fonte de placar (todays-matches, match-detail, API-Football), decisão de merge, detecção de conflito e fonte final escolhida
- Permite debugging end-to-end de propagação de placar em produção

### Lição aprendida

1. **Cache keys devem incluir contexto de uso** — Mesmo endpoint com mesmos parâmetros pode ter semânticas diferentes (detalhe pré-jogo vs atualização live). Namespace de cache evita colisões silenciosas.

2. **Merge de múltiplas fontes exige prioridade explícita e monotonia** — Com 3-4 fontes de placar, regras ad-hoc em diferentes pontos do código geram comportamento imprevisível. Uma função centralizada com prioridade declarada e guarda monotônica é mais robusta e testável.

3. **Observabilidade retroativa é cara** — Sem logs de diagnóstico, o bug de "placar travado" exigiu análise manual do código para identificar qual fonte estava prevalecendo. Campos de observabilidade (`scoreSourceFinal`, `scoreConflictDetected`) permitem diagnosticar problemas semelhantes em produção sem code review.

---

## 033 — Corners Engine v2: Motor bidirecional com ladder Over/Under 4.5-12.5

**Data:** 2026-03-18
**Arquivos afetados:** `backend/modeling/corners_engine.py` (reescrito), `backend/modeling/corners/price_ladder.py` (novo), `backend/modeling/corners/predictor.py` (atualizado)
**Severidade:** Evolução arquitetural
**Status:** Implementado
**Commits:** `52d5f39`, `5bed500`, `64dfd6b`
**PRs:** #126, #127

### Problema identificado

O Corners Engine v1 era unidirecional — calculava apenas probabilidades Over (8.5, 9.5, 10.5, 11.5) usando Poisson com blend fixo de FootyStats potentials. Não existiam mercados Under de escanteios, e a cobertura de linhas era limitada.

### Solução implementada

1. **Motor bidirecional** — Reescrita completa para gerar tanto Over quanto Under para cada linha, usando `1 - P(Over)` com ajuste de margem para derivar odds Under
2. **Ladder expandido [4.5-12.5]** — Nova `price_ladder.py` que gera probabilidades para 9 linhas (4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5) em ambas direções
3. **Overround consistente** — Fórmula de derivação Under: `1/(OVERROUND - implied_over)` com margem de 6%
4. **CI/CD fixes** — Correções de imports e type errors que quebravam build

### Lição aprendida

Motor unidirecional (só Over) limita o universo de apostas e impede que o sistema identifique valor em mercados Under de escanteios, que frequentemente oferecem EV positivo em ligas defensivas.

---

## 034 — Corner Betting Governance Framework: 3 modelos candidatos + estados operacionais

**Data:** 2026-03-17
**Arquivos afetados:** `backend/modeling/corners/negative_binomial.py` (novo), `backend/modeling/corners/poisson_model.py` (novo), `backend/modeling/corners/ml_regression.py` (novo), `backend/modeling/corners/features.py` (novo), `backend/modeling/corners/benchmarks.py` (novo), `backend/modeling/corners/champion_selector.py` (novo), `backend/modeling/corners/operational_states.py` (novo)
**Severidade:** Evolução arquitetural
**Status:** Implementado
**Commits:** `5771950`, `0ac2153`
**PR:** #123

### Problema identificado

O motor de escanteios usava apenas Poisson simples sem benchmarking formal, sem seleção de modelo por liga/linha, e sem estados operacionais graduados.

### Solução implementada

1. **3 modelos candidatos** — Negative Binomial (NB2, baseline primário), Poisson (baseline secundário), GBR Supervised Regression (candidato ML)
2. **Benchmarking formal** (`benchmarks.py`) — Comparação por Brier Score, LogLoss, ECE, ROI simulado
3. **Champion/fallback selection** (`champion_selector.py`) — Score composto seleciona melhor modelo por liga e por linha, com fallback automático
4. **Estados operacionais graduados** (`operational_states.py`) — RESTRICTED → NEUTRAL → ACTIVE_GUARDED → ACTIVE, com promoção baseada em evidência acumulada
5. **Feature engineering dedicado** (`features.py`) — Pipeline de features específicas para escanteios

### Lição aprendida

Governança formal de modelos (benchmark + seleção + estados operacionais) é necessária para prevenir publicação de modelos piores que o fallback. O padrão de champion/fallback por granularidade (liga×linha) permite que cada combinação use o melhor modelo disponível.

---

## 035 — Ativação do Pipeline V2: 6 módulos (M1-M6)

**Data:** 2026-03-18
**Arquivos afetados:** `backend/services/fixtures_service.py`, `backend/modeling/xg_filter.py`, `backend/main.py`, `backend/models/safe_bets.py`, `backend/ai/prompt_templates.py`, `backend/config/league_dna.py`
**Severidade:** Alta (mudança de pipeline de produção)
**Status:** Implementado
**Commit:** `756139b`
**PR:** #128

### Problema identificado

O Pipeline B (5 camadas, regra #028) estava implementado mas inativo. O `fixtures_service.py` ainda chamava `selecionar_mercados_jogo` (pipeline A legado). Além disso, o chaos detector não bloqueava picks SAFE, o xG filter era unidirecional (só penalizava SORTE_ALTA), e existia código duplicado no `main.py`.

### Solução implementada — 6 módulos

1. **M1: Switch para V2** — `fixtures_service.py` agora chama `selecionar_mercados_v2()` (ativa EV, calibração, corner governance)
2. **M2: Chaos blocker** — Chaos detector agora rebaixa SAFE → NEUTRO para jogos caóticos
3. **M3: xG bidirecional** — `xg_filter.py` agora ajusta lambda PARA CIMA para times com azar (xG >> gols), não apenas para baixo
4. **M4: Remoção de duplicata** — `selecionar_mercados_jogo()` do `main.py` (linha 842) marcado como deprecated
5. **M5: 3 novas estratégias Safe Bets** — Under 2.5, BTTS YES, Over 2.5
6. **M6: Prompts Mistral especializados** — Prompts diferentes por família de mercado (gols, corners, cartões)

### Lição aprendida

Ativar o pipeline V2 requer ativação simultânea de todas as defesas (chaos blocker, xG bidirecional) para evitar que mercados de baixa qualidade sejam classificados como SAFE pelo novo pipeline.

---

## 036 — Deduplicação de mercados: corners, gols e filtro NO_BET

**Data:** 2026-03-18
**Arquivos afetados:** `backend/services/market_service.py`, `backend/services/ev_classification.py`
**Severidade:** Média
**Status:** Implementado
**Commits:** `199c4c3`, `29e2708`, `1bce85e`, `1e8ff74`
**PRs:** #128, #129

### Problema identificado

O pipeline V2 gerava múltiplas linhas por família de mercado (ex: Over 8.5, 9.5, 10.5, 11.5 corners), todas aparecendo no dashboard. Isso sobrecarregava a UI e confundia o usuário. Além disso, mercados NO_BET apareciam na saída.

### Correções aplicadas

1. **Corner dedup** — Função compartilhada que mantém apenas a melhor linha por direção (melhor Over + melhor Under), aplicada em ambos os paths V2 e legacy
2. **Goal dedup** — Mantém apenas melhor Over e melhor Under por jogo
3. **NO_BET filter** — Mercados com classificação NO_BET removidos da saída final
4. **Sort por classificação** — SAFE primeiro, depois NEUTRO_QUALIFICADO, depois NEUTRO

### Lição aprendida

Quando o pipeline gera múltiplas variantes do mesmo mercado, a UI precisa de uma camada de deduplicação que selecione a melhor opção. Sem isso, o volume de output cresce exponencialmente com o número de linhas.

---

## 037 — Correção da fórmula de overround para Under + filtros de redundância

**Data:** 2026-03-19
**Arquivos afetados:** `backend/services/market_service.py`, `backend/services/ev_classification.py`, `backend/modeling/corners/price_ladder.py`
**Severidade:** Alta (odds incorretas)
**Status:** Corrigido
**Commits:** `a4e9420`, `d2ac843`

### Problema identificado

1. **Fórmula de Under errada** — Under odds eram derivadas como `1/((1-implied_over)/OVERROUND)` em vez de `1/(OVERROUND - implied_over)`. Isso gerava odds Under sistematicamente erradas, inflando EV
2. **EV fantasma** — Mercados com EV > 40% eram aceitos sem questionamento
3. **Redundância 1X2/DC** — Quando 1X2 Home e DC 1X apareciam juntos, ambos ficavam no output
4. **Corridor bets** — Over X.5 + Under (X+1).5 apareciam simultaneamente

### Correções aplicadas

1. **Fórmula corrigida** — `1/(OVERROUND - implied_over)` aplicada em `market_service.py`, `ev_classification.py` e `price_ladder.py`
2. **EV sanity cap** — Novo reason code `SUSPICIOUS_EV` para EV > 40% (provável erro de dados)
3. **Filtro 1X2/DC** — Quando ambos aparecem, mantém apenas o de maior probabilidade
4. **Filtro corridor** — Quando Over X.5 e Under (X+1).5 aparecem, mantém apenas o de maior probabilidade

### Lição aprendida

Fórmulas de derivação de odds (Over→Under) devem ser validadas com exemplos numéricos reais antes de deploy. EV > 40% é quase sempre erro de dados, não oportunidade real.

---

## 038 — Odds Under reais + enrichment API-Football/Mistral + estádio

**Data:** 2026-03-19
**Arquivos afetados:** `backend/services/fixtures_service.py`, `backend/services/api_football_client.py`, `backend/ai/match_analysis_service.py`
**Severidade:** Média (melhoria de dados)
**Status:** Implementado
**Commits:** `cc85e07`, `38f1c14`, `c803ae3`

### Problema identificado

1. Under odds eram derivadas matematicamente mas odds Under reais da API-Football não eram usadas
2. Dados pré-jogo da API-Football não enriqueciam o record de fixtures
3. Informações de estádio/venue não eram propagadas para o frontend

### Correções aplicadas

1. **Under odds reais** — Quando disponíveis via API-Football, usar odds Under reais em vez de derivadas
2. **API-Football enrichment** — Dados pré-jogo (H2H, standings, statistics) enriquecem fixtures
3. **Estádio propagado** — Campo venue/stadium da API-Football inserido no record do match

### Lição aprendida

Odds reais sempre devem ter prioridade sobre odds derivadas. A derivação matemática é um fallback, não a fonte primária.

---

## 039 — Enriquecimento do prompt Mistral: +40 campos de dados

**Data:** 2026-03-19
**Arquivos afetados:** `backend/ai/match_analysis_service.py`
**Severidade:** Média (melhoria de qualidade da análise AI)
**Status:** Implementado
**Commit:** `9a28292`

### Problema identificado

O prompt da Mistral recebia apenas ~15 campos (lambda, probs 1X2, Over 2.5, BTTS, xG, shots, posse, corners). Dados disponíveis como cartões, faltas, clean sheets, FTS%, Win%, médias da liga, posição na tabela e corner potentials não eram enviados — resultando em análises superficiais.

### Correção aplicada

Expansão do prompt para ~55 campos organizados em 8 categorias:
- **Ofensivos**: xG sofrido, chutes no alvo, média total gols/jogo
- **Defensivos**: Clean Sheet %, Failed To Score %
- **% por time**: Win %, Over 2.5 %, BTTS %
- **Escanteios**: Potenciais O8.5/9.5/10.5 da FootyStats
- **Cartões**: Cartões/jogo casa e fora (era zero no prompt anterior)
- **Faltas**: Faltas/jogo casa e fora (era zero)
- **Médias da liga**: Corners, cartões, faltas, CS%, Over 2.5%, xG, vantagem casa
- **Posição**: Posição na liga de cada time

Instrução atualizada para exigir comentários sobre corners e cartões nos key_points quando dados existirem.

### Lição aprendida

O LLM só pode analisar o que recebe. Dados disponíveis no backend mas não passados no prompt são invisíveis para a análise AI. Sempre auditar quais campos o prompt recebe vs quais estão disponíveis.

---

## 040 — UI: EV% real + redesign do painel AI Analysis

**Data:** 2026-03-19
**Arquivos afetados:** `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Média (UX)
**Status:** Implementado
**Commits:** `30f5a48`, `be07432`

### Problema identificado

1. O EV% exibido era sempre "EV+" sem valor numérico real
2. O painel de AI Analysis não mostrava reason codes da classificação
3. Sem glossário para explicar termos técnicos ao usuário

### Correções aplicadas

1. **EV% real** — Exibe valor numérico com sinal correto e cor (verde positivo, vermelho negativo)
2. **Reason code tags** — Cada mercado mostra tags visuais dos reason codes (LOW_DATA_QUALITY, POSITIVE_EV, etc.)
3. **Glossary tab** — Aba de glossário com explicações dos termos técnicos
4. **Layout responsivo** — Redesign do painel para melhor legibilidade mobile

### Lição aprendida

Mostrar dados técnicos (EV, reason codes) sem contexto confunde o usuário. Glossário integrado e formatação visual (cores, tags) transformam dados brutos em informação acionável.

---

## 041 — Auditoria: priorização de lambda root cause + endpoint de revert

**Data:** 2026-03-19
**Arquivos afetados:** `backend/audit.py`, `backend/routes/correction.py`, `frontend/next/src/app/api/correction/`
**Severidade:** Alta (governança de correções)
**Status:** Implementado
**Commits:** `b733759`, `c15ebdd`, `0583b0d`

### Problema identificado

1. O sistema de auditoria tratava erros de threshold como causa raiz quando o verdadeiro problema era lambda incorreto
2. Correções de threshold com >15% de alteração eram aplicadas automaticamente, mascarando problemas de lambda
3. Não havia forma de reverter uma correção incorreta
4. PostgreSQL ON CONFLICT falhava sem UNIQUE constraints

### Correções aplicadas

1. **Priorização no prompt de auditoria** — Instrução à Mistral para priorizar lambda > pesos > thresholds
2. **Bloqueio de correções grandes** — Threshold corrections com >15% de mudança bloqueadas (provavelmente problema de lambda)
3. **Endpoint /correction/revert** — Permite reverter correções incorretas via API
4. **Next.js proxy route** — Frontend pode chamar o endpoint de revert
5. **UNIQUE constraints** — Adicionados ao audit.py para PostgreSQL ON CONFLICT funcionar

### Lição aprendida

Correções automáticas devem tratar a causa raiz (lambda) antes dos sintomas (thresholds). Bloqueio de correções grandes evita que o sistema "conserte" mascarando o problema real. Endpoint de revert é essencial para governança.

---

## 042 — Recalibração de thresholds: auditoria de 27 jogos com 0% SAFE accuracy

> **SUPERADO:** Thresholds globais foram substituídos por thresholds **per-league** calibrados automaticamente em **#055** (safe_prob por heurística de qualidade Brier). Os valores fixos desta regra servem apenas como defaults/fallback.

**Data:** 2026-03-19
**Arquivos afetados:** `backend/services/ev_classification.py`
**Severidade:** Crítica
**Status:** Implementado
**Commit:** `7b5e135`

### Problema identificado

Auditoria de 27 jogos revelou 0% de accuracy para mercados classificados como SAFE. Os thresholds definidos na regra #028 eram muito permissivos.

### Correções aplicadas

| Parâmetro | Antes | Depois |
|-----------|-------|--------|
| safe_prob 1X2 | 55% | 62% |
| safe_prob O/U | 68% | 75% |
| safe_prob Corners | 65% | 72% |
| safe_ev (todos) | 4-5% | 6-8% |
| SAFE condição | EV >= safe_ev | EV >= safe_ev AND edge >= safe_edge |
| NEUTRO aceita EV < 0 | Sim (até -3%) | Não |
| NEUTRO-Q min_ev | 2% | 5% |
| NEUTRO-Q min_edge | 0% | 3% |
| min_quality | 0.30 | 0.40-0.45 |

### Lição aprendida

Thresholds teóricos devem ser validados com dados reais de auditoria antes de confiar neles. A primeira auditoria real revelou que 0% dos picks SAFE acertaram — indicando thresholds gravemente permissivos. Calibração contínua via auditoria é obrigatória.

---

## 043 — Recalibração emergencial: circuit breaker SAFE + deflação lambda 15%

> **SUPERADO:** Os alertas desta regra foram substituídos por calibração **per-league**:
> - SAFE circuit breaker → reativado per-league em **#054** (ex.: 36/37 ligas com `safe_enabled=true`)
> - Lambda deflation 0.85 → per-league em **#052–#053** (Dixon-Coles, grid 0.80–1.50)
> - BTTS deflation 0.80 → per-league em **#054–#056** (calibrado contra `seasonBTTSPercentage`)
> - Corners redução 20% → per-league em **#055–#056** (Brier + season stats)
> - Thresholds endurecidos → per-league em **#055** (safe_prob por Brier)
>
> Os critérios de remoção originais não se aplicam mais da mesma forma; a calibração automática per-league substituiu as deflações fixas globais.

**Data:** 2026-03-20
**Arquivos afetados:** `backend/services/ev_classification.py`, `backend/modeling/lambda_calculator.py`, `backend/modeling/corners_engine.py`
**Severidade:** Crítica (emergencial)
**Status:** Implementado
**Commit:** `3b10063`

### Problema identificado

Duas auditorias consecutivas com SAFE accuracy = 0% e Brier Score em tendência crítica (0.2611 → 0.3071). Over goals com 0% accuracy. BTTS caindo de 66.7% para 0%. Lambda error = 0.90 (limite = 0.5) indicando superestimação sistemática.

### Correções aplicadas

1. **Circuit breaker SAFE** — Toda classificação SAFE rebaixada para NEUTRO_QUALIFICADO até reativação manual
2. **Lambda deflation 0.85** — Fator multiplicativo de 0.85 nos lambdas para mercados O/U
3. **BTTS deflation 0.80** — Fator mais agressivo para BTTS (era o mercado mais incorreto)
4. **Corners reduction 20%** — Projeção de corners reduzida em 20%
5. **H2H filter** — Adicionado filtro de confrontos diretos para corners

**Critérios de reativação do SAFE:**
- 3 auditorias consecutivas com accuracy > 50%
- Lambda error < 0.5
- Brier Score < 0.25

### Lição aprendida

Quando o modelo superestima sistematicamente (lambda error alto), a correção mais rápida é deflação uniforme enquanto investiga a causa raiz. Circuit breaker SAFE é uma medida de proteção essencial — impede que o sistema recomende com confiança alta quando comprovadamente erra.

---

## 044 — AuditReportCard + League Confidence Badges

**Data:** 2026-03-19/20
**Arquivos afetados:** `frontend/next/src/components/AuditReportCard.tsx` (novo), `frontend/next/src/components/LeagueConfidenceBadge.tsx` (novo)
**Severidade:** Média (UX/observabilidade)
**Status:** Implementado
**Commits:** `243db1e`, `5842da9`

### Problema identificado

Resultados de auditoria eram exibidos apenas em formato técnico (JSON/tabela), sem resumo executivo nem indicação visual de confiança por liga.

### Correções aplicadas

1. **AuditReportCard** — Componente com resumo executivo da auditoria, copy-to-clipboard para compartilhamento, toggle Detalhado/Report Card
2. **League Confidence Badges** — Badges visuais por liga com tooltip mostrando métricas (Brier, accuracy, lambda error)

### Lição aprendida

Dados de auditoria são inúteis se não são acessíveis ao operador. Resumo visual + copy para clipboard permitem avaliação e compartilhamento rápidos.

---

## 045 — Expansão de market models: 5 → 20 modelos binários (corners, cards, Over 0.5)

**Data:** 2026-03-20
**Arquivos afetados:** `backend/ml/market_models.py`, `backend/ml/train_model.py`
**Severidade:** Evolução arquitetural
**Status:** Implementado
**Commit:** `409bff1`

### Problema identificado

O pipeline ML tinha apenas 5 modelos binários (Over 1.5-4.5 + BTTS). Mercados de corners e cartões não tinham modelos ML dedicados.

### Correção aplicada

Expansão de 5 para 20 modelos por liga:
- **Gols**: +1 modelo (Over 0.5) → total 6 (Over 0.5-4.5 + BTTS)
- **Corners**: +8 modelos novos (Over 4.5 a Over 11.5)
- **Cartões**: +6 modelos novos (Over 0.5 a Over 5.5)

Todos seguem o mesmo pipeline com quality gate Poisson (#029) e temporal decay.

### Lição aprendida

Expandir modelos ML para novos mercados é barato quando o pipeline já tem quality gates robustos — modelos ruins são automaticamente desativados pelo gate Poisson.

---

## 046 — Health/DB endpoint + remoção de credenciais placeholder

**Data:** 2026-03-20
**Arquivos afetados:** `backend/routes/health.py`, `scripts/test_postgres_connection.py`, `scripts/migrate_sqlite_to_postgres.py`
**Severidade:** Alta (infraestrutura)
**Status:** Implementado
**Commits:** `604ab94`, `a0a55fb`

### Problema identificado

1. Não havia endpoint para verificar conectividade do banco de dados em produção
2. Scripts de migração e teste tinham `"seu_host_postgres"` como valor default — credencial placeholder que causava erro HTTP 500 na auditoria (#032 já documentava o sintoma)
3. Não havia diagnóstico da tabela de auditoria

### Correções aplicadas

1. **GET /health/db** — Testa conectividade PostgreSQL (ou SQLite fallback), retorna status, tipo de backend, presença de env vars
2. **GET /health/db/diag** — Diagnóstico da tabela de auditoria (contagem, últimas entradas)
3. **Remoção de defaults placeholder** — Scripts agora exigem env vars configuradas, sem fallback para `"seu_host_postgres"`

### Lição aprendida

Credenciais placeholder em scripts nunca devem ter fallback funcional — devem falhar explicitamente quando não configuradas. Endpoint /health/db é essencial para diagnóstico rápido de problemas de conexão.

---

## 047 — Mistral timeout/retry + Copa do Brasil + separadores visuais

**Data:** 2026-03-20
**Arquivos afetados:** `backend/ai/match_analysis_service.py`, `backend/config/leagues_config.py`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/components/PredictionBadge.tsx`
**Severidade:** Média
**Status:** Implementado
**Commit:** `d8ef882`

### Problema identificado

1. Mistral API falhava silenciosamente em timeouts, retornando confidence=0 sem retry
2. Copa do Brasil não estava configurada no sistema
3. Badges de predição tinham campos grudados sem separador visual

### Correções aplicadas

1. **Retry com backoff** — 2 tentativas com backoff em erros transientes (timeout, connection reset). Só retorna confidence=0 após esgotar retries
2. **Copa do Brasil** — Adicionada ao backend (league ID 73), frontend AVAILABLE_LEAGUES, aliases, e CALENDAR_YEAR_LEAGUES
3. **Separadores visuais** — Spans "|" explícitos entre campos do badge (status, mercado, prob, odds)

### Lição aprendida

APIs externas devem sempre ter retry com backoff — um único timeout não deve invalidar a análise. Timeout de 60s é necessário para prompts enriquecidos com 55+ campos.

---

## 048 — Live fallback "- : -" → 0-0 para jogos sem dados de placar

**Data:** 2026-03-18
**Arquivos afetados:** `frontend/next/src/components/MatchCard.tsx`
**Severidade:** Baixa (UX)
**Status:** Implementado
**Commit:** `a5109cd`
**PR:** #125

### Problema identificado

Jogos ao vivo sem dados de placar da API exibiam "- : -" no dashboard, causando confusão visual.

### Correção aplicada

Fallback para 0-0 quando API não retorna dados de placar, com indicador visual de que o placar pode não estar atualizado.

### Lição aprendida

Exibir dados ausentes como "- : -" é menos informativo que 0-0 com disclaimer. O usuário entende "0-0" como "jogo começou, aguardando dados" melhor do que traço.

---

## 049 — Format string bug em market_models log (WORSE_THAN_POISSON)

**Data:** 2026-03-20
**Arquivos afetados:** `backend/ml/market_models.py`
**Severidade:** Baixa (bug de log)
**Status:** Corrigido
**Commit:** `d8d786b`

### Problema identificado

F-string condicional no logger.info de market models gerava exceção ao tentar formatar `brier_poisson:.4f if...`, impedindo log de modelos que falharam no quality gate.

### Correção aplicada

Formato condicional corrigido para avaliar a condição antes da formatação.

### Lição aprendida

F-strings com expressões condicionais complexas são propensas a erros de sintaxe. Usar variável intermediária para o valor formatado é mais seguro.

---

> **Sincronização:** Entradas **#050–#055** alinhadas ao ficheiro canónico em [`wemarques/sportsbankzu-pro` — `docs/REGRAS_CORRECAO_SISTEMA.md`](https://github.com/wemarques/sportsbankzu-pro/blob/main/docs/REGRAS_CORRECAO_SISTEMA.md) (branch `main`).

## 050 — Relatório V3: backtesting, calibração, SAFE monitoring e feedback loop Mistral

**Data:** 2026-03-20
**Arquivos afetados:** `backend/services/backtesting.py` (novo), `backend/routes/backtesting.py` (novo), `backend/routes/health.py`, `backend/audit.py`, `backend/ai/prompt_templates.py`, `backend/main.py`, `REVIEW.md` (novo), `.github/workflows/claude-review.yml` (novo)
**Severidade:** Média (infraestrutura de monitoramento)
**Status:** Implementado

### Funcionalidades adicionadas

1. **Backtesting service** (`backend/services/backtesting.py`) — 6 métricas: Brier score, log-loss, calibration bins, ROI, lambda error, hit rate. Lê dados do audit DB via funções existentes em `audit.py`.

2. **API routes** (`backend/routes/backtesting.py`) — 3 endpoints:
   - `GET /backtesting/run` — executa backtesting com filtros de liga/mercado/período
   - `GET /backtesting/safe-reactivation` — avalia critérios de reativação do SAFE (#043)
   - `GET /backtesting/calibration-search` — grid search para parâmetros calibráveis

3. **Health endpoints** (`backend/routes/health.py`):
   - `GET /health/safe-status` — estado do circuit breaker SAFE + métricas de reativação
   - `GET /health/calibration-params` — inventário completo de parâmetros calibráveis

4. **Feedback loop Mistral** (`backend/audit.py` + `backend/ai/prompt_templates.py`):
   - `log_mistral_prediction()` — armazena predições Mistral para feedback
   - `get_mistral_accuracy()` — calcula accuracy por liga/mercado
   - `_build_feedback_block()` — injeta histórico de acurácia no prompt quando ≥10 predições disponíveis

5. **PR Review automation** (`REVIEW.md` + `.github/workflows/claude-review.yml`) — Claude Code Review action para revisão automática de PRs com regras de bloqueio baseadas nas REGRAS.

### Critérios de reativação SAFE (#043)

O endpoint `/backtesting/safe-reactivation` verifica 3 critérios:
- ≥3 auditorias com accuracy > 50%
- Brier score < 0.25
- Lambda error médio < 0.5

Todos devem ser atendidos para recomendar reativação do circuit breaker.

### Lição aprendida

Monitoramento contínuo (backtesting + feedback loop) é essencial para validar calibrações antes de reativar features desabilitadas por baixa performance. O pipeline V3 fecha o ciclo: previsão → auditoria → backtesting → recalibração.

---

## 051 — Lambda error null no backtesting + relatórios por liga e mercado

**Data:** 2026-03-20
**Arquivos afetados:** `backend/cron_handler.py`, `backend/routes/backtesting.py`
**Severidade:** Alta (backtesting incompleto)
**Status:** Corrigido

### Problema identificado

O endpoint `/health/safe-status` retornava `lambda_error: null`, impedindo avaliação completa dos critérios de reativação do SAFE (#043). O backtesting de ROI também não funcionava porque as odds não eram gravadas.

### Causa raiz

O `cron_handler.py` chamava `audit_db.log_pick()` com context contendo apenas `regime` e `source`. Os dados necessários para lambda error (lambdaHome, lambdaAway, goals_home, goals_away) e para ROI (odd do pick) existiam no escopo mas não eram passados.

### Correções aplicadas (5 camadas)

1. **Context enriquecido** — `log_pick()` agora recebe lambdas (Home/Away/Total), gols reais (home/away/total), corners totais, classificação e data_quality no context
2. **predicted_probs enriquecido** — Agora inclui `odd` e `book_odd` para cálculo de ROI no backtesting
3. **Backfill endpoint** — `POST /backtesting/backfill-lambda` preenche picks existentes copiando lambda data de picks irmãos do mesmo jogo
4. **Relatório por liga** — `GET /backtesting/by-league` com flag `needs_calibration` por liga
5. **Relatório por mercado** — `GET /backtesting/by-market` com filtro opcional por liga

### Lição aprendida

Ao criar um sistema de métricas (backtesting), verificar que os dados necessários são gravados na ORIGEM (log_pick). Criar o consumer (backtesting) sem verificar o producer (cron_handler) resulta em métricas null. Conforme regra de investigação #2: trace o fluxo completo.

---

## 052 — Calibração por liga: remoção da deflação uniforme + treino com 4 temporadas

**Data:** 2026-03-21
**Arquivos afetados:**
- Novos: `backend/services/league_calibrator.py`
- Modificados: `backend/modeling/poisson_matrix.py`, `backend/modeling/corners/predictor.py`, `backend/services/ev_classification.py`, `backend/routes/backtesting.py`, `backend/routes/health.py`
**Severidade:** Crítica (mudança fundamental no pipeline)
**Status:** Implementado

### Problema identificado

A deflação uniforme (#043) — lambda 0.85, BTTS 0.80, corners 0.80 — era aplicada igualmente a todas as ligas. O backtesting by-league revelou que:
- Ligas com bom desempenho (Colômbia 80%, Turquia 75%) eram PREJUDICADAS pela deflação
- Ligas ruins (Brasil 39%) não melhoravam o suficiente com a deflação uniforme
- Cada liga tem perfil estatístico diferente que exige calibração individual

### Solução implementada — Calibração por liga

1. **league_calibrator.py** — Serviço que busca 4 temporadas de dados históricos por liga via FootyStats, roda grid search para encontrar fatores ótimos de lambda deflation (O/U e BTTS separados), pesos de lambda (temporada/recente), fator de corners, e status do SAFE
2. **Remoção de constantes uniformes** — `LAMBDA_DEFLATION_FACTOR`, `BTTS_DEFLATION_FACTOR` e `CORNER_DEFLATION_FACTOR` substituídos por funções que leem da corrections DB por liga
3. **SAFE por liga** — `SAFE_CIRCUIT_BREAKER_ENABLED` global mantido como override de emergência, mas cada liga agora tem status individual baseado na calibração
4. **Endpoints** — `POST /backtesting/calibrate` (roda calibração) e `GET /backtesting/calibration-status` (mostra estado por liga)
5. **Integração com sistema existente** — Usa `get_active_corrections(league)` e `log_correction()` do audit.py, que já são lidos pelo fixtures_service.py

### Parâmetros calibrados por liga

| Parâmetro | Range de Grid Search | Default (sem calibração) |
|-----------|---------------------|--------------------------|
| lambda_deflation_ou | 0.70 - 1.10 | 1.0 (sem deflação) |
| lambda_deflation_btts | 0.70 - 1.05 | 1.0 (sem deflação) |
| corner_factor | 0.70 - 1.20 | 1.0 |
| lambda_weight_season | 0.40 - 0.70 | 0.60 |
| lambda_weight_recent | 0.30 - 0.60 | 0.40 |
| safe_enabled | true/false | false (conservador) |

### Lição aprendida

1. **Deflação uniforme é um band-aid** — Resolve o sintoma (superestimação) mas prejudica ligas que não tinham o problema. Calibração individual é a solução correta.
2. **4 temporadas com decay temporal** dão massa de dados suficiente (200+ jogos por liga) para grid search robusto enquanto dão mais peso às tendências recentes.
3. **SAFE por liga** permite que ligas bem calibradas tenham picks SAFE enquanto ligas problemáticas permanecem conservadoras.

---

## 053 — Fix lambda underestimation root cause (Dixon-Coles) + expanded calibration

**Data:** 2026-03-21
**Arquivos afetados:** `backend/modeling/lambda_calculator.py`, `backend/services/league_calibrator.py`, `backend/routes/backtesting.py`, `backend/main.py`, `backend/modeling/chaos_detector.py`, `backend/modeling/xg_filter.py`, `backend/modeling/market_validator.py`, test files
**Severidade:** Crítica
**Status:** Implementado

### Problema identificado

Calibração (#052) revelou que TODOS os 28 leagues calibrados atingiram o teto do grid (`lambda_deflation_ou = 1.10`). Isso indicava um problema **sistemático na fórmula** de lambda, não variação por liga.

### Causa raiz

**Double-counting do fator defensivo** na fórmula original de `calcular_lambda_dinamico()`:
- Fórmula antiga: `λ = gols_ponderados × fator_defesa_adversario`
- `gols_ponderados` já reflete os adversários enfrentados (é a média de gols marcados)
- Multiplicar novamente pela defesa adversária aplica a correção defensiva **duas vezes**
- Resultado: lambda **sistematicamente subestimado** → previsões conservadoras demais → deflation 1.10 (ceiling) era necessário para compensar

### Correções aplicadas

**Camada 1 — Lambda Calculator (formula fix):**
- Reescrito `calcular_lambda_dinamico()` com modelo **Dixon-Coles de forças relativas**
- Nova fórmula: `λ = media_liga_per_team × ataque_relativo × defesa_relativa_adversario`
  - `media_liga_per_team = average_goals_per_match / 2`
  - `ataque_relativo = gols_ponderados / media_liga_per_team` (ratio vs liga, não absoluto)
  - `defesa_relativa = gols_sofridos_adversario / media_liga_per_team` (ratio vs liga)
- Isso elimina a dupla contagem: ataque e defesa são expressos como ratios relativos à média da liga

**Camada 2 — Limpeza de spec fictícia "v5.5-ML":**
- Removidas todas as 18+ referências a "v5.5-ML" em docstrings, logs e quadro-resumo
- Referência era nome inventado por sessão anterior, sem existência no REGRAS

**Camada 3 — Grid expandido + 6 temporadas:**
- `DEFLATION_GRID`: [0.75 ... 1.30] (era [0.70 ... 1.10])
- `BTTS_DEFLATION_GRID`: [0.75 ... 1.25]
- `CORNER_DEFLATION_GRID`: [0.70 ... 1.20]
- `SEASON_WEIGHTS`: 6 temporadas [0.50, 0.25, 0.13, 0.07, 0.03, 0.02]
- Default `n_seasons=6` (era 4)

**Camada 4 — API-Football fallback:**
- `fetch_historical_matches_fallback()` usa API-Football quando FootyStats não tem dados
- `calibrate_league()` automaticamente tenta fallback se < 30 matches do FootyStats
- Cobre as 9 ligas que retornavam INSUFFICIENT_DATA

**Camada 5 — Recalibrate-all endpoint com bias detector:**
- `POST /backtesting/recalibrate-all` com opção `clear_previous`
- Detecta viés uniforme: se > 70% das ligas hit o grid boundary, reporta como problema de fórmula

### Lição aprendida

1. **Quando calibração uniforme atinge limites do grid**, o problema está na fórmula base, não nos parâmetros per-league. O grid search é um ajuste fino, não uma correção de viés sistemático.
2. **Dixon-Coles** expressa ataque e defesa como ratios relativos à média da liga, eliminando qualquer dupla contagem.
3. **"v5.5-ML" era um nome fictício** — proibido criar nomes de especificação não documentados no REGRAS.
4. **API-Football como fallback** garante cobertura para ligas sem dados no FootyStats.

---

## 054 — Fix BTTS calibration (deflação separada) + Fix SAFE save + Dual source

**Data:** 2026-03-21
**Arquivos afetados:** `backend/services/league_calibrator.py`, `backend/services/ev_classification.py`, `backend/services/api_football_client.py`, `backend/routes/backtesting.py`
**Severidade:** Alta (calibração incorreta + feature não funcional)
**Status:** Corrigido

### Problema 1: BTTS deflation absurda (1.8-2.0)

A simulação `_simulate_poisson_brier()` aceitava UM ÚNICO `lambda_deflation` aplicado a TODOS os mercados. No grid search de BTTS, passava o fator BTTS como deflação única, boosting lambdas para O/U e BTTS juntos. Em produção, `poisson_matrix.py` aplica deflações SEPARADAS. O resultado: BTTS deflation batia no teto do grid (2.0) porque a simulação não refletia o pipeline real.

**Fix:** `_simulate_poisson_brier()` agora aceita `lambda_deflation_ou` e `lambda_deflation_btts` separadamente. O grid search de BTTS mantém O/U fixo no valor ótimo e varia apenas BTTS. Grid BTTS reduzido para 0.80-1.30.

### Problema 2: safe_enabled nunca gravado no DB

`log_correction()` declara `new_value: float` e formata com `.4f`. `save_calibration()` passava `str(True)` — crash silencioso no format. safe_enabled nunca era gravado.

**Fix:** `save_calibration()` converte booleans para 1.0/0.0 antes de gravar. `_is_safe_enabled()` lê float >= 1.0 como True.

### Evolução: Dual source FootyStats + API-Football

FootyStats não retornava season data para algumas ligas. Sem dados, ficavam com INSUFFICIENT_DATA.

**Fix:** Dual source — FootyStats e API-Football buscados para cada liga. `merge_dual_sources()` seleciona o dataset mais completo. API-Football data agora usa two-pass team average computation (mesmo algoritmo do FootyStats path).

### Lição aprendida

1. **Simulação de calibração deve espelhar produção** — Se produção usa deflações separadas, a simulação de calibração também deve.
2. **Type mismatch silencioso** é fatal para features condicionais — `log_correction(new_value: float)` recebendo string crashava silenciosamente.
3. **Dual source > fallback** — Buscar de ambas as fontes e mergear é mais robusto que fallback sequencial.

---

## 055 — Calibração completa de TODOS os mercados e parâmetros por liga

**Data:** 2026-03-21
**Arquivos afetados:** `backend/services/league_calibrator.py`, `backend/modeling/poisson_matrix.py`, `backend/services/ev_classification.py`, `backend/services/fixtures_service.py`, `backend/main.py`, `backend/ml/predictor.py`, `backend/routes/backtesting.py`
**Severidade:** Alta (assertividade global — cobre tabelas C.1-C.5 do relatório v3)
**Status:** Implementado
**Referência:** Relatório v3, Seção 5.2C (tabelas C.1-C.5)

### Problema identificado

O calibrador (#052-#054) cobria apenas lambda O/U, BTTS deflation, corner ratio e SAFE flag. Mercados e parâmetros não calibrados causavam:
1. **1X2** sem deflation própria — probabilidades potencialmente incorretas
2. **Under** sem validação separada — EV absurdo em mercados Under
3. **Cards** zero calibração — Poisson sem tuning de threshold ou multiplier
4. **Corners** apenas ratio sem Brier — sem validação de melhoria
5. **BTTS fusion weights** (40/30/30) fixos — não otimizados por liga
6. **xG blend** (70/30) fixo — não otimizado por liga
7. **Thresholds** (safe_prob) iguais para todas as ligas — ligas boas penalizadas

### Correções aplicadas — Calibração completa

| Parâmetro | Grid Search | Arquivo que Lê | Antes |
|-----------|------------|----------------|-------|
| lambda O/U | 0.75-1.50 | poisson_matrix.py | existia |
| lambda BTTS | 0.80-1.30 | poisson_matrix.py | existia |
| lambda 1X2 | 0.90-1.10 | poisson_matrix.py | NOVO |
| lambda weights | 0.40-0.70 | lambda_calculator.py | existia |
| corner factor | 0.80-1.20 (Brier) | corners/predictor.py | era ratio |
| cards factor | 0.80-1.20 (Brier) | ml/predictor.py | NOVO |
| xG blend | 0.0-0.50 | main.py | NOVO |
| BTTS weights | heurístico | fixtures_service.py | NOVO |
| safe_prob O/U | heurístico Brier | ev_classification.py | era global |
| safe_prob BTTS | heurístico Brier | ev_classification.py | NOVO |
| safe_prob 1X2 | heurístico Brier | ev_classification.py | NOVO |
| safe_prob DC | heurístico Brier | ev_classification.py | NOVO |
| safe_prob Corners | heurístico Brier | ev_classification.py | NOVO |
| safe_prob Cards | heurístico Brier | ev_classification.py | NOVO |

**Simulação expandida:** `_simulate_all_markets()` computa Brier para 20 mercados: Over 4 linhas, Under 4 linhas, BTTS, 1X2 ×3, DC ×3, Corners ×3, Cards ×3.

**Pipeline reads:** Cada parâmetro calibrado é lido da corrections DB no ponto onde é usado:
- `poisson_matrix.py` → 1X2 deflation (novo `_get_league_deflation` retorna 3 valores)
- `ev_classification.py` → `_get_thresholds(market_cat, league_id)` com priority calibrated > audit DB > defaults
- `fixtures_service.py` → BTTS fusion weights lidos de `get_lambda_corrections()`
- `main.py` → `expected_goals_v2()` recebe `league_id`, lê `xg_blend_weight` calibrado
- `ml/predictor.py` → Cards Poisson aplica `cards_multiplier` calibrado

### Lição aprendida

Calibrar apenas lambda O/U e assumir que outros mercados estão cobertos cria inconsistências. O mapeamento completo de parâmetros calibráveis (tabelas C.1-C.5 do relatório v3) deveria ter sido implementado desde a primeira versão do calibrador.

---

## 056 — Fix extração de cards/corners/BTTS + enriquecimento com league-season stats

**Data:** 2026-03-21
**Arquivos afetados:** `backend/services/league_calibrator.py`, `CLAUDE.md` (estado do pipeline), `docs/REGRAS_CORRECAO_SISTEMA.md` (registro)
**Severidade:** Alta (cards Brier nulo + BTTS no teto 1,30 + season stats)
**Status:** Implementado
**Commits:** `be1328b` (extração + season stats + docs), `c4d54f2` (`fetch_season_stats`: `resolve_season_ids` dinâmico, alinhado a `fetch_historical_matches`)

### Problema identificado (resumo)

1. **Cards Brier null** — uso de campo array (`team_a_cards`) em vez de contagem inteira (`team_a_cards_num` / fallback).
2. **Corners** — sentinel FootyStats `-1` tratado incorretamente com `or`, corrompendo totais.
3. **BTTS** — flag `btts` em `league-matches` não usada; Poisson puro empurrava deflation ao teto do grid (1,30).
4. **Season stats** — `get_league_season_stats` existia mas não alimentava calibração; após deploy, lista vazia porque `season_ids` no config estava vazio — corrigido em **`c4d54f2`** com `client.resolve_season_ids(...)`.

### Lição aprendida

Validar tipos e sentinels da API; reutilizar o mesmo mecanismo de resolução de temporadas que o restante do pipeline (`resolve_season_ids`).

---

## 057 — Correções de governança: testes, documentação, rotas API

**Data:** 2026-03-21
**Arquivos afetados:** `CLAUDE.md`, `docs/REGRAS_CORRECAO_SISTEMA.md`, `.gitignore`, `tests/KNOWN_FAILURES.md` (+ remoção de `.claude/` do versionamento: `settings.local.json`, skills)
**Severidade:** Média (governança e rastreabilidade)
**Status:** Implementado
**Commit:** `8d9b638` — *docs: governance fixes — test baseline, REGRAS sync, API routes, gitignore (#057)*

### Problema identificado

1. Falhas de teste recorrentes sem **baseline** documentado (9 execuções + 1 erro de coleta).
2. Divergência **REGRAS #043** vs **CLAUDE.md** (circuit breaker / deflações vs estado per-league reativado).
3. Rotas API Gateway pouco claras (`/health` vs `/api/health`, parâmetro `league=` vs `league_id=`).
4. Separador Markdown `---` duplicado antes da entrada **#056** (formatação).
5. `.claude/settings.local.json` versionado → avisos CRLF e ruído em commits.

### Correções aplicadas

1. **`tests/KNOWN_FAILURES.md`** — Baseline dos **10** problemas conhecidos no ambiente Windows/local:
   - **1** erro de coleta: `tests/unit/test_util_service.py` — `pandas._libs.pandas_parser` (instalação pandas corrompida no `.venv`; mitigação típica: `pip install --force-reinstall pandas`).
   - **1** falha ML: `tests/test_corner_framework.py::TestMLRegression::test_train_corner_regressor` — dependência **sklearn** / ambiente.
   - **7** falhas **Streamlit** em `tests/test_visual.py` (ex.: `test_app_loads`, `test_title_present`, …) — UI/headless/ambiente.
   - Nota: `tests/unit/test_calibrator.py` **não existe** no repo (comando de verificação retorna file not found).
2. Notas **SUPERADO** em **#042** e **#043** (sincronia com calibração per-league **#054–#056**).
3. **CLAUDE.md** — Seção **API Routes (Lambda / API Gateway)** com URL base, tabela de rotas corretas vs erros comuns, `league=`, timeout API Gateway vs duração da calibração, checklist de deploy Lambda (`State` / `LastUpdateStatus` antes de `update-function-code`).
4. Remoção do **`---`** duplicado imediatamente antes de **## 056**.
5. **`.gitignore`:** `.claude/` (substitui `.claude/worktrees/` apenas); **`git rm --cached .claude/`** para parar de versionar settings locais.

### Lição aprendida

Deploy com testes vermelhos exige **baseline explícito** (`KNOWN_FAILURES.md` ou CI allowlist documentada). Regras históricas **SUPERADAS** devem ser marcadas no próprio REGRAS para não contradizer `CLAUDE.md`. Rotas e parâmetros de API devem estar no guia do repositório para evitar perda de tempo em produção.

---

## 058 — Aplicar deflação per-league no pipeline de produção

**Data:** 2026-03-21
**Arquivos afetados:** `backend/services/fixtures_service.py`, `backend/services/ev_classification.py`, `backend/modeling/corners_engine.py`, `scripts/deploy_lambda.py`, `docs/REGRAS_CORRECAO_SISTEMA.md`
**Severidade:** Crítica (EVs inflados no dashboard — ex.: Under 2.5 com +50% a +70%; escanteios com EV extremo quando o multiplicador era ignorado)
**Status:** Corrigido e deployado (Lambda `sportsbank-pro-backend`)
**Commit:** `2879c71` — *fix(critical): apply per-league deflation in production pipeline (#058)*

### Problema identificado

A calibração **per-league** (**#052–#056**) estava na corrections DB e era usada em `derive_all_markets()` / `poisson_matrix.py`, mas as probabilidades servidas ao cliente seguiam caminhos em que **deflação e multiplicadores não entravam de forma consistente**:

1. **`fixtures_service.py`** — Cálculos Poisson (O/U etc.) com **lambdas em bruto**, sem aplicar deflação O/U / BTTS **antes** dos `poisson_cdf` (ou equivalente na matriz de mercados).
2. **`ev_classification.py`** — `_prob()` priorizava valores em **`stats`** (caminho cru) sobre **`derived`** (após `derive_all_markets` com deflação).
3. **`corners_engine.py`** — `derive_corner_probabilities()` **sem** `corner_multiplier` calibrado por liga.
4. **BTTS** — Risco de **dupla aplicação** de multiplicador; o fix **unifica** via ajuste nas lambdas (uma aplicação coerente com o calibrador).

### Causa raiz

Dois grafos de probabilidade **desalinhados**: o calibrador e `poisson_matrix` usavam deflação; **produção** ainda misturava saídas cruas (`stats`) com classificação baseada em `derived`, e corners sem fator da DB.

### Correções aplicadas

| Componente | Antes #058 | Depois #058 |
|------------|------------|-------------|
| `fixtures_service.py` | Lambdas cruas no Poisson | Deflação O/U aplicada às lambdas; BTTS alinhado (sem multiplicador paralelo incoerente) |
| `ev_classification._prob()` | Prioridade a `stats` (cru) | Prioridade a **`derived`** (deflacionado) |
| `corners_engine.py` | Sem `corner_multiplier` | `corner_multiplier` da DB aplicado ao lambda de corners |
| `deploy_lambda.py` | Sem retry | Retry com espera para **`ResourceConflictException`** no update do Lambda |

### Validação e deploy

- **Lambda:** ZIP → S3 → `update-function-code`; estado **Active**; `GET /health` → `{"status":"ok"}`.
- **Fixtures em produção:** chamadas a `/api/fixtures` (várias ligas e datas) devolveram **0 jogos** ou **503** em alguns parâmetros — atribuído a **disponibilidade FootyStats** / janela sem jogos (ex.: pausa), não a regressão lógica do patch.
- **Sanity check local (ex.: Eliteserien, defl. O/U ≈ 1,20, lambda bruto 1,8):** sem deflação U2.5 ≈ **73,1%**, EV a odd 1,50 ≈ **+9,6%**; com deflação U2.5 ≈ **63,3%**, EV ≈ **−5,0%** (~10 p.p. em U2.5).
- **Windows:** consola **cp1252** pode falhar ao imprimir caractere lambda (`UnicodeEncodeError`) — usar `PYTHONIOENCODING=utf-8` ou evitar símbolos não ASCII em `print` de debug.

### Lição aprendida

1. **Calibrar sem ligar ao mesmo grafo que o dashboard consome não corrige produção** — seguir o dado desde `fixtures_service` até a resposta JSON (investigação obrigatória, **CLAUDE.md**).
2. **`derived` deve vencer `stats`** quando ambos existem após calibração per-league.
3. **Deploy:** `ResourceConflictException` exige retry (coerente com checklist **#057** / `CLAUDE.md`).

---

## 059 — Export/import de calibrações (S3) e investigação «EVs absurdos» pós-#058

**Data:** 2026-03-21
**Arquivos afetados:** `backend/audit.py`, `backend/services/league_calibrator.py`, `docs/REGRAS_CORRECAO_SISTEMA.md`
**Severidade:** Alta (continuidade operacional, diagnóstico de EV e armazenamento de correções)
**Status:** Implementado
**Commit:** `0688909` — *feat: persist calibrations to S3 for Lambda deploy survival (#059)*

### Problema identificado

1. Queixa: após **#058**, os **EVs continuavam absurdos** em produção.
2. Hipótese inicial — **SQLite em `/tmp`** perdido a cada deploy do Lambda — aplica-se a ambientes que **não** usam PostgreSQL. Na investigação, o Lambda tinha **`DATABASE_URL` → PostgreSQL (RDS)** e `_use_postgres() == True`, logo as correções **persistem entre deploys** nesse modo.

### Causa raiz efetiva (linha temporal)

| Quando | O que ocorreu | Efeito |
|--------|---------------|--------|
| **2026-03-19** | Poucas entradas na DB (ex.: `lambda_home_multiplier=0.9` para todas as ligas) | Ajuste limitado |
| **Deploy #058** | Código lê **`lambda_multiplier`** (deflação O/U per-league) na corrections DB | Se o valor **não existir** por liga → default **`1.0`** → **sem** deflação O/U na pipeline |
| **2026-03-21** | Calibração em massa (**~36 ligas**, milhares de correções em PostgreSQL) | `lambda_multiplier` e restantes fatores **gravados**; exemplos observados na sessão: O/U ~**1,0–1,1**, BTTS ~**0,9–1,3**, 1X2 ~**0,9** |

**Conclusão:** **#058** estava alinhado ao desenho, mas existiu **janela** em que o binário já consumia chaves per-league **antes** da DB estar populada → EVs inflados até à recalibração.

### Correções aplicadas (#059 — S3 como rede de segurança)

Objetivo: **export/import de calibrações em S3** para:

- Ambientes **sem** RDS (ex.: SQLite local ou efémero);
- **Recuperação** em cold start / deploy quando o armazenamento primário não está disponível ou está vazio.

Resumo técnico:

1. **`backend/audit.py`** — export das correções de calibração para objeto em S3; import no arranque (`init_db` / lifecycle do container), com guard para não reimportar em loop.
2. **`backend/services/league_calibrator.py`** — após `save_calibration()`, chamada ao export S3.

*(Bucket e key seguem configuração do projeto; não documentar credenciais neste ficheiro.)*

### Estado pós-calibração (referência da investigação)

- **~36 ligas** com multipliers persistidos em PostgreSQL.
- **EV em produção:** verificação **não conclusiva** na sessão (API sem jogos — ex.: pausa internacional).

### Próximos passos (verificação)

1. `GET /api/fixtures?leagues=<liga>&date=...` com jogos reais.
2. Rever EV no array de picks.
3. Se anomalias persistirem, auditar percentagens pré-jogo FootyStats vs prioridade **`derived`** em `_prob()` (**#058**).

### Lição aprendida

1. **Confirmar o backend de persistência** (`DATABASE_URL`, `_use_postgres()`) antes de atribuir falhas a «perda de `/tmp`».
2. **Código que lê novas chaves na DB** deve ir acompanhado de **dados** ou defaults explícitos — senão o utilizador vê deploy novo com comportamento idêntico.
3. **RDS (verdade em produção) + S3 (export)** — redundância útil para degradados e para não depender só do ciclo de vida do container.

---

## Nota — Verificação CI (documentação + suite completa)

**Referência:** [GitHub Actions run 23361270140](https://github.com/wemarques/sportsbankzu-pro/actions/runs/23361270140) — workflow `ci.yml`, commit `d4b31ed`, branch `claude/corner-betting-framework-zh4G1`.

| Job | Duração (aprox.) | Resultado |
|-----|------------------|-----------|
| `backend-tests` | ~57 s | Sucesso |
| `e2e-tests` | ~3 m 16 s | Sucesso |
| **Total pipeline** | ~3 m 20 s | **Success** |

**Avisos (não falha):** deprecação Node.js 20 nos actions `checkout` / `setup-python` / `setup-node` / `upload-artifact` — planejar upgrade para Node 24 conforme [changelog GitHub Actions](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).

**Artefato:** `playwright-report` (~207 KB) gerado no job e2e.

---

## 060 — Live scores resilience: "last known scores" cache

**Data:** 2026-03-21
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Implementado

### Problema identificado

Bragantino vs Botafogo apareceu 0-0 no dashboard quando o placar real era 2-1 (minuto 90).
Ambas fontes externas falharam simultaneamente:
- **API-Football:** Rate limit diário excedido desde ~19:13 UTC
- **FootyStats `todays-matches`:** Retornando vazio

O endpoint `/live-scores` retornou `{"matches":[]}` → frontend não recebeu overlay de placar → score ficou 0-0.

### Causa raiz

**Vulnerabilidade estrutural**: o endpoint `/live-scores` não tinha nenhum mecanismo de fallback quando ambas APIs externas falhavam. O código retornava `{"matches":[]}` imediatamente, sem tentar servir dados recentes da memória.

Confirmado: o código #058 e #059 **NÃO** causaram o problema (health OK, imports OK, nenhum syntax error).

### Correções aplicadas

1. **Cache "last known scores" em memória** (`_last_live_scores` dict): armazena o último resultado bem-sucedido do `/live-scores` com timestamp
2. **TTL de 5 minutos** (`_LIVE_CACHE_TTL = 300`): dados cacheados expiram após 5 min para evitar servir placares muito antigos
3. **3 pontos de fallback**: cache é consultado quando (a) FootyStats falha completamente, (b) ambas APIs retornam vazio, (c) exceção não tratada no handler
4. **2 pontos de cache**: resultados são armazenados quando (a) API-Football primary retorna dados, (b) processamento FootyStats + enrichment completam com sucesso
5. **Flag `stale: true`**: resposta inclui indicador para o frontend saber que dados são do cache
6. **Flag `cacheAge`**: tempo em segundos desde o último fetch bem-sucedido

### Lição aprendida

- Live scores dependem de APIs externas com quotas limitadas. O sistema DEVE ter cache de resiliência para servir dados recentes quando ambas fontes falham
- A API-Football tem limite diário de requisições que pode ser atingido durante rodadas com muitos jogos simultâneos. Considerar upgrade de plano ou implementar budget management para priorizar live scores sobre enrichment

---

## 061 — Fix _prob(): priorizar Poisson deflacionado sobre FootyStats pré-match

**Data:** 2026-03-22
**Arquivos afetados:** `backend/services/ev_classification.py`
**Severidade:** CRÍTICA
**Status:** Corrigido

### Problema identificado

O #058 aplicou deflation nos lambdas Poisson em `fixtures_service.py` e `derive_all_markets()`, mas a função `_prob()` em `ev_classification.py` usava `stats` (FootyStats pre-match %) quando `derived` (Poisson deflacionado) não era encontrado por mismatch de keys.

Evidência: Under 2.5 com probabilidade IDÊNTICA (65-67%) para TODOS os jogos do Brasileirão, independente dos times. Poisson produz valores diferentes por jogo porque depende de ataque x defesa de cada time.

### Causa raiz

1. `_prob()` tentava buscar em `derived` com key exata, mas não tentava variações de key (com/sem sufixo "Prob")
2. Quando a key não era encontrada em `derived`, fallback para `stats["over25Prob"]` que vinha do FootyStats `over_25_percentage_pre_match` — um valor agregado da liga, não específico por jogo
3. Sem logging para diagnosticar qual fonte era usada em runtime

### Correções aplicadas

1. `_prob()` agora tenta key exata E variação sem "Prob" no dict `derived`
2. Logging de diagnóstico: `[ev][prob-source]` mostra `derived[over25Prob]` vs `stats[over25Prob]` para cada jogo
3. Warning quando `derived` está vazio (lambdas indisponíveis)

### Lição aprendida

Seguir Regra de Investigação #2 (trace o fluxo completo) até o VALOR FINAL: não basta verificar que `derive_all_markets()` computa corretamente — é preciso confirmar que o valor chega ao dashboard. Sempre adicionar logging de diagnóstico ao alterar prioridade de fontes de dados.

---

## 062 — Fix: team name mismatch entre league-teams e league-matches (causa raiz dos EVs absurdos)

**Data:** 2026-03-22
**Arquivos afetados:** `backend/services/fixtures_service.py`
**Severidade:** CRITICA
**Status:** Corrigido

### Problema identificado

TODOS os jogos de uma liga tinham lambdas IDENTICOS (ex: Premier League: lamH=1.025, lamA=0.964 para todos os 5 jogos). Isso gerava probabilidades Poisson identicas e EVs absurdos (50-200%+).

### Causa raiz

O FootyStats retorna nomes de times diferentes entre endpoints:
- `league-teams`: "Everton FC", "Chelsea FC", "Liverpool FC", "Cuiaba EC"
- `league-matches`/`todays-matches`: "Everton", "Chelsea", "Liverpool", "Cuiaba"

A funcao `get_team_row()` fazia match EXATO (`teams[name_col] == name`). Como "Everton" != "Everton FC", o lookup falhava silenciosamente para TODOS os times, e os lambdas caiam para defaults da liga (1.025/0.964), resultando em lambdas identicos para todos os jogos.

### Correcoes aplicadas

1. Fuzzy match como fallback: quando match exato falha, tenta `name.lower() in team_val.lower()` (substring match)
2. Logging `[lambda-diag]` em WARNING para monitorar matches fuzzy ativados
3. Se fuzzy tambem falha, loga sample de nomes para debugging

### Resultado

- **Antes:** lamH=1.025 lamA=0.964 para TODOS os 5 jogos da PL
- **Depois:** Everton vs Chelsea (1.086/1.574), Man City vs Palace (1.663/0.640), Fulham vs Burnley (2.455/0.957) — valores unicos por jogo

### Licao aprendida

- NUNCA assumir que nomes de times sao consistentes entre endpoints de uma mesma API. O FootyStats usa "Everton FC" no endpoint `league-teams` mas "Everton" no `todays-matches`. Sempre implementar fuzzy/substring matching para dados de times.
- Quando TODOS os valores de uma metrica sao identicos, a causa mais provavel e fallback para defaults — investigar se o lookup de dados falha silenciosamente.

---

## 063 — EVs absurdos por LAMBDA_MIN=0.2 e falhas residuais de fuzzy match

**Data:** 2026-03-22
**Arquivos afetados:** `backend/services/fixtures_service.py`, `backend/modeling/lambda_calculator.py`, `backend/main.py`, `backend/services/ev_classification.py`
**Severidade:** Critica
**Status:** Corrigido

### Problema identificado

Jogos como Argentinos vs Platense mostravam Draw=68-70% e Under 2.5=97-99%. Em Eliteserien, TODOS os times tinham lambdas identicos (1.053/1.08) — defaulting para media da liga. O fuzzy match simples do #062 (substring) nao resolvia times como PSG, NEC, Inter Milan, Rennes.

### Causa raiz

**Dupla:** (1) `LAMBDA_MIN=0.2` permitia lambdas irrealisticamente baixos (total lambda=0.42 gera P(draw)=68%), e (2) `get_team_row()` falhava para times cujo nome no CSV nao continha substring do nome da API (PSG vs "Paris Saint-Germain", NEC vs "N.E.C.", Inter Milan vs "Internazionale").

### Correcoes aplicadas

**Camada 1 — LAMBDA_MIN elevado (lambda_calculator.py + main.py):**
- `LAMBDA_MIN = 0.2` -> `LAMBDA_MIN = 0.5` — nenhum time real marca menos de 0.5 gols/jogo em media
- Aplicado em `calcular_lambda_dinamico()` e em `expected_goals_v2()` no main.py

**Camada 2 — Fuzzy matching robusto com 6 estrategias (fixtures_service.py):**
1. Exact match (ja existia)
2. Alias lookup: `_TEAM_ALIASES` dict (PSG->paris saint-germain, NEC->n.e.c., Inter Milan->internazionale, Rennes->rennais)
3. Substring match bidirecional (ja existia)
4. Normalized match: `_normalize_team_name()` strip FC/SC/AC/FK, remove dots (N.E.C.->NEC)
5. Token overlap: `_token_match_score()` >= 50% = match
6. Short name prefix match: "AZ" -> "AZ Alkmaar"

**Camada 3 — Diagnostico (ev_classification.py):**
- `[prob-trace]` log mostrando derived vs stats para cada mercado O/U

### Verificacao pos-deploy

- PL: lambdas variam (Newcastle 1.558/0.839, Tottenham 1.316/1.185)
- Brasileirao: todos os times matched (Corinthians->SC Corinthians Paulista, Flamengo->CR Flamengo)
- Bundesliga: Mainz 05->1. FSV Mainz 05 (substring)
- Zero teams "NOT FOUND" em CloudWatch
- Draw probabilities normalizadas (24-28% para PL)
- EVs capped a 40% quando prob/odds mismatch detectado

### Licao aprendida

- `LAMBDA_MIN` deve refletir limites realisticos do futebol (nenhum time marca < 0.5 gols/jogo de media). O floor anterior de 0.2 era matematicamente possivel mas nao realistico.
- Fuzzy matching de nomes de times precisa de multiplas estrategias porque fontes de dados (API-Football, FootyStats, odds providers) usam convencoes diferentes. Substring sozinho nao basta.

---

<!-- Novas correções devem ser adicionadas abaixo, seguindo o mesmo formato -->
