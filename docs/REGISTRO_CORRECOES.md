# Registro de Correções de Regras do Sistema

> **Objetivo:** Este arquivo documenta correções aplicadas ao sistema que devem ser consultadas quando erros semelhantes ocorrerem. Cada entrada descreve o problema, a causa raiz e as camadas de correção implementadas.

---

> Historico completo de todos os fixes e correcoes do sistema.
> Para regras ativas e permanentes, consultar `docs/REGRAS_ATIVAS.md`.
> Indice rapido em `docs/INDICE_REGRAS.md`.


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

**Commit:** `5c751a0` — *fix(critical): raise LAMBDA_MIN to 0.5 and add 6-strategy fuzzy team matching (#063)*

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
- Zero teams "NOT FOUND" em CloudWatch (nas ligas amostradas)
- Draw probabilities normalizadas (24-28% para PL; antes ~68% em cenários com λ no chão)
- Pipeline aplica **cap de EV** quando há mismatch prob/odd (ver **Cuidado — cap de EV** abaixo)

### Nota pos-deploy — Eliteserien, Argentina e MLS

Após **`5c751a0`**, testes em **produção** ainda mostraram padrões compatíveis com **cobertura de dados**, não só com falha de fuzzy:

- **Argentina (primera-division):** vários jogos com **ambos os λ no floor (0,5)** quando stats por clube / `league-teams` **faltam ou vêm vazios** no path FootyStats — o match de nomes pode estar correto e ainda assim **não haver linha utilizável**.
- **Eliteserien:** parte dos jogos manteve **λ idênticos (ex.: 1,053 / 1,08)** — típico de **média da liga** quando stats por equipa não entram (época a iniciar, cobertura).
- **MLS:** **misto** (alguns clubes com λ realistas; outros no **floor**) — esperável com **disponibilidade desigual** por equipa.

**Interpretação:** λ no **LAMBDA_MIN** ou **iguais em demasia** entre jogos = priorizar **governação de dados** (pré-carga `league-teams`, cache, época anterior — ver **#064**), não assumir só “bug de código”.

### Cuidado — cap de EV (~40%)

O **cap de EV** (e flags associadas) **atenua valores extremos na API/UI** mas **não corrige** sozinho probabilidade mal calibrada: o modelo pode continuar errado com EV “apresentável”. Acompanhar **Brier**, distribuição de EV, **% de mercados tocados pelo cap** e logs **`[prob-trace]`** — **não** concluir saúde do sistema só porque `abs(EV)` raramente passa de ~40%.

### Licao aprendida

- `LAMBDA_MIN` deve refletir limites realisticos do futebol (nenhum time marca < 0.5 gols/jogo de media). O floor anterior de 0.2 era matematicamente possivel mas nao realistico.
- Fuzzy matching de nomes de times precisa de multiplas estrategias porque fontes de dados (API-Football, FootyStats, odds providers) usam convencoes diferentes. Substring sozinho nao basta.

---

## 064 — Fallback de temporada anterior para ligas com dados insuficientes

**Data:** 2026-03-22
**Arquivos afetados:** `backend/routes/fixtures.py`, `backend/services/fixtures_service.py`, `backend/modeling/lambda_calculator.py`
**Severidade:** Alta
**Status:** Implementado

**Complemento:** encadeia **#063** (*commit* `5c751a0`): mantém-se `LAMBDA_MIN=0.5` e o **Cuidado — cap de EV (~40%)** em **#063**; **#064** reduz casos em que a época corrente tem **poucos ou zero jogos** e stats quase vazios — **não** substitui o cap nem elimina por si só lacunas de `league-teams` (ver **Nota pos-deploy — Eliteserien, Argentina e MLS** em **#063**).

### Problema identificado

Ligas com temporada recem-iniciada (Argentina, Eliteserien, MLS) tinham times com 0-4 jogos na temporada atual. Os stats (gols/jogo, gols sofridos/jogo) eram proximos de zero, resultando em lambdas calculados abaixo de 0.5 e sendo "floored" pelo LAMBDA_MIN. Isso gerava probabilidades Poisson incorretas para todos os mercados.

Exemplos reais (CloudWatch, **antes** do blend completo operacional):
- Argentina: Argentinos Juniors, Platense, River Plate — muitos com lambda=0.5 (floor)
- Eliteserien: varios jogos defaultando para media da liga (1.053/1.08)
- MLS: Montreal, Seattle — casos no floor

Complementa **#063**: o floor evita λ impossíveis; **#064** reduz a **frequência** em que o modelo precisa dele ao **enriquecer** stats no início de época.

### Causa raiz

`_process_single_league()` so carregava a temporada atual via `resolve_season_id()` (singular). Para temporadas recem-iniciadas, `matches_played` era 0-4, gerando stats insuficientes para o modelo Dixon-Coles.

### Correcoes aplicadas

**Camada 1 — Regressao Bayesiana (lambda_calculator.py):**
- Quando `games_played < 5`, regride `ataque_ponderado` em direcao a media da liga
- Formula: `weight = games_played / 5.0`, `ataque = ataque * weight + media_liga * (1 - weight)`
- Defesa em profundidade: funciona mesmo sem dados de temporada anterior

**Camada 2 — Blending de temporada anterior (fixtures_service.py):**
- `_find_team_in_df()`: matching de 6 estrategias reutilizavel para qualquer DataFrame
- `_blend_row()`: combina stats da temporada atual com anterior, peso proporcional a `matches_played / 5`
- Aplicado no ponto de extracao de `home_row`/`away_row` em `build_records_from_matches()`
- Se `matches_played < 5` e `teams2` disponivel, busca time na temporada anterior e faz blend

**Camada 3 — Carga de temporada anterior (fixtures.py):**
- `resolve_season_id()` substituido por `resolve_season_ids(n_seasons=2)`
- Se >30% dos times tem `matches_played < 5`, carrega `get_league_teams(prev_season_id)` (gate com `pd.to_numeric(..., errors="coerce")` para evitar `FutureWarning` pandas em `.fillna`/downcasting)
- Passa `teams2=prev_teams_df` para `build_records_from_matches()` (parametro ja existia mas era sempre `None`)

### Verificacao

CloudWatch confirmou:
- `[fixtures] primera-division: loaded 30 prev-season teams as fallback (prev_sid=15746)`
- `[fixtures] eliteserien: loaded 16 prev-season teams as fallback (prev_sid=16260)`
- `[fixtures] mls: loaded 30 prev-season teams as fallback (prev_sid=13973)`
- `[lambda-diag] Blended Argentinos Juniors: mp=0, prev-season data available, weight=0.00`
- `[lambda-diag] Blended Bodo/Glimt: mp=0, prev-season data available, weight=0.00`

**Semântica do log:** `weight=0.00` com `mp=0` indica **0% época atual / 100% época anterior** no blend (esperado para equipas sem jogos contabilizados na época).

**Pendente:** validar **λ e EV finais** em `GET /api/fixtures?...` quando houver jogos e quotas API OK (smoke com `/fixtures` sem prefixo `/api/` pode não refletir o API Gateway documentado em **#057**).

### Licao aprendida

- Temporadas nao comecam todas em agosto/setembro. Ligas de calendario-ano (Argentina, Noruega, MLS, J-League) comecam em fev-mar. O sistema precisa lidar com early-season gracefully.
- O parametro `teams2` em `build_records_from_matches()` existia desde a criacao da funcao mas nunca foi utilizado — era dead code. Agora esta ativo.
- Defesa em profundidade: 3 camadas independentes (regressao no lambda, blending no service, carga no route) garantem que mesmo se uma falhar, as outras compensam.

---

## 065 — EVs absurdos residuais: 1X2 Poisson inflado, lambda floor e cap real de EV

**Data:** 2026-03-22
**Arquivos afetados:** `backend/services/ev_classification.py`
**Severidade:** Critica
**Status:** Corrigido

### Problema identificado

Apos **#063** (e com early-season ainda sensível antes de **#064**), tres categorias de EVs absurdos persistiam:
1. **Cat 1 — Lambda floor:** Argentinos vs Platense Under 2.5=89-91%. Ambos lambdas batendo em LAMBDA_MIN=0.5, Poisson gera probabilidades extremas para Under.
2. **Cat 2 — 1X2 inflado:** Paris Home=80-82% (Poisson) mas odd=2.00 (implied 50%). EV=+60% falso. O `_prob()` usava Poisson-derived para 1X2 apesar do comentario dizer "prefer stats (odds-implied)".
3. **Cat 3 — Over extremos:** Portland vs LA Galaxy Over 4.5=76-78% EV +195%. Poisson com lambda=3.0 da ~18%, nao 76%. FootyStats pre-match % vazando quando derived vazio.

### Causa raiz

**Tripla:**
1. `_prob()` sempre verificava `derived` (Poisson) primeiro para TODOS os mercados, incluindo 1X2. O comentario na linha 370 dizia "For 1X2: prefer stats (odds-implied)" mas **nunca foi implementado**. Poisson 1X2 diverge 20-30pp do mercado.
2. Quando ambos lambdas = LAMBDA_MIN (team lookup falhou), `derive_all_markets()` gerava probabilidades de puro ruido (Under 2.5=92% com lambda_total=1.0). Sem deteccao de lambda floor.
3. `MAX_CREDIBLE_EV=0.40` apenas adicionava flag `SUSPICIOUS_EV` e downgradeava SAFE→NEUTRO, mas **nao capava a probabilidade**. Mercados com EV +195% continuavam mostrando como NEUTRO.

### Correcoes aplicadas

**Camada 1 — 1X2 usa odds-implied quando odds disponiveis (ev_classification.py):**
- Quando odds 1X2 existem, `_prob()` e chamado sem `derived_key` → usa stats (odds-implied de `implied_probs()`)
- Quando odds nao existem, Poisson-derived serve como fallback
- Resultado: 1X2 EV fica proximo de 0 (correto para mercado eficiente), eliminando falsos +60%

**Camada 2 — Lambda floor detection (ev_classification.py):**
- Detecta quando ambos lambdas <= LAMBDA_MIN + 0.02 (team lookup falhou)
- Descarta dict `derived` inteiro → _prob cai para FootyStats/odds-implied (mais realista)
- Reduz quality score em -0.20 (modelo sem dados reais para esses times)

**Camada 3 — EV cap com recompute de probabilidade (ev_classification.py):**
- Quando EV > 40%: calcula `max_prob = (1 + 0.40) / book_odd`
- Capa `calibrated_probability` e `raw_probability` para max_prob
- Recomputa `compute_ev()` e `compute_display()` com prob capada
- Resultado: probabilidade e EV exibidos sao consistentes e capados a 40%

**Camada 4 — Force NO_BET para EV > 100% (ev_classification.py):**
- Apos todas as camadas, se EV ainda > 100% com SUSPICIOUS_EV flag, forca NO_BET
- Captura edge cases onde cap nao aplicou completamente (ex: book_odd missing)

### Verificacao pos-deploy

Cenarios esperados:
- Paris Home: EV ~0% (odds-implied = Poisson nao mais usado para 1X2)
- Argentinos vs Platense Under 2.5: derived descartado (lambda floor), FootyStats/odds usados
- Portland Over 4.5: se EV > 40%, prob capada; se > 100%, NO_BET

### Licao aprendida

- Comentarios de intencao ("prefer stats for 1X2") devem ser implementados no codigo, nao apenas documentados. O gap entre comentario e implementacao persistiu por multiplas sessoes.
- Flag de EV suspeito sem cap real e inutil — o mercado ainda mostra na UI como NEUTRO com +195%. O cap deve atuar na probabilidade e recomputar todos os valores derivados.
- Quando lambdas batem no floor, o output Poisson e ruido — deve ser descartado, nao usado. Defesa em profundidade: detectar na entrada (lambda floor), capar na saida (EV cap), e bloquear extremos (NO_BET).
- **Relação com #063:** o cap ~40% altera **prob/EV exibidos**; a advertência em **#063 — Cuidado — cap de EV** mantém-se — continuar a monitorizar Brier e % de mercados capados.

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

## 066 — Ligas desaparecendo do dashboard por timeout silencioso no fan-out batching

**Data:** 2026-03-22
**Arquivos afetados:** `frontend/next/src/lib/api.ts`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Ligas como brazil-serie-a, brazil-serie-b, england-league-one e england-league-two pararam de aparecer no dashboard. Backend responde normalmente quando chamado diretamente. Logs do Vercel mostram zero chamadas para essas ligas nas ultimas 6h. Erros 504 esporadicos persistem.

### Causa raiz

O fan-out batching agrupava 5 ligas por batch. Com a ordem do `AVAILABLE_LEAGUES`, as ligas pesadas (Premier League, Championship, League One, League Two) ficavam no batch 1, e as brasileiras (Serie A, Serie B) no batch 2. Com Lambda cold start (~10-20s) + 5 ligas em paralelo (~8-15s), o tempo total (~18-35s) excedia o hard limit de 30s do API Gateway, causando 504.

O retry automatico no route.ts (2x 35s = 70s) excedia o maxDuration de 60s do Vercel. Como mais de 50% dos batches (3-8) succedem, o erro era suprimido silenciosamente pelo merge de resultados — o dashboard mostrava jogos das ligas que respondiam mas omitia as que falhavam sem nenhum indicador visual.

### Correcoes aplicadas (3 camadas)

**Camada 1 — Reducao do batch size (api.ts):**
- `LEAGUES_PER_BATCH`: 5 → 3 (cada batch processa menos ligas, fica bem abaixo do limite de 30s do API Gateway)
- `MAX_CONCURRENT`: 3 → 4 (compensa o aumento de batches mantendo throughput)

**Camada 2 — Retry individual de batches falhados (api.ts):**
- Apos o fan-out inicial, identifica batches que falharam (rejected ou erro retryable com 0 matches)
- Retenta as ligas desses batches individualmente (1 liga por chamada) com o mesmo MAX_CONCURRENT
- Substitui o resultado do batch falhado pelo merge dos retries individuais
- Resultado: mesmo que o batch com 3 ligas falhe, cada liga e retentada sozinha (~5-10s, bem dentro do timeout)

**Camada 3 — Logging detalhado por batch (api.ts):**
- Log de composicao de cada batch antes do fetch
- Log de resultado (OK/FAIL) de cada batch com count de matches e erro
- Log de retries individuais com resultado por liga
- Log final com total de matches e count de batches falhados
- Permite diagnostico rapido via logs do Vercel

### Licao aprendida

- Fan-out batching com suppression de erro parcial pode esconder falhas silenciosamente. Quando >50% dos batches succedem, o dashboard parece funcional mas esta incompleto. O retry individual de batches falhados e essencial para garantir que timeouts intermitentes nao causem perda permanente de ligas.
- O batch size deve considerar o elo mais fraco da timeout chain (API Gateway 30s), nao apenas o timeout do fetch client (35s).
- Logging por batch e critico para diagnosticar falhas parciais em producao — sem ele, a unica evidencia e a ausencia de dados no dashboard.

---

## 067 — Live-score swap matching, proxy timeout, Unicode, FT odds, goals-null log

**Data:** 2026-03-22
**Commit:** `f33262d`
**Nota (historico):** O commit `f33262d` pode citar **(#069)** na mensagem Git; **neste documento** esse pacote (live-scores/proxy/Unicode) esta como **#067**. A secao **#069** abaixo e **outra** correcao (auditoria Brier/SAFE/lambda, commit `832c0a8`).
**Arquivos afetados:** `backend/routes/fixtures.py`, `frontend/next/src/app/api/matches/live/route.ts`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Critica (Fix 1), Alta (Fix 2), Media (Fix 3), Baixa (Fix 4), Diagnostico (Fix 5)
**Status:** Implementado

### Correcoes aplicadas

**Fix 1 — Swap home/away no AF matching do /live-scores (gap do #005):**
- `find_fixture` em `api_football_client.py` ja fazia 2 passagens (normal + swap) desde #005
- `/live-scores` so fazia 1 passagem → jogos com convencao invertida nao matchavam
- Adicionada segunda passagem com flag `af_swapped`; quando True, inverte `af_home_g`/`af_away_g` no overlay

**Fix 2 — Timeout proxy live 10s→20s (cadeia Vercel→Lambda; ver tambem **#066** fan-out / timeouts):**
- Pipeline live-scores chama FootyStats + API-Football + matching + fallback
- Com cold start Lambda, >10s e plausivel; Fluid Compute permite ate 300s
- `timeoutMs` aumentado para 20_000 em ambos os calls (live-scores e fixtures fallback)

**Fix 3 — Unicode literal em JSX:**
- `m\u00EDn` em texto JSX renderizava literalmente "m\u00EDn" em vez de "mín"
- Substituido por UTF-8 direto (`mín`) em todas as 3 ocorrencias

**Fix 4 — Odds 0.00 em jogos finalizados:**
- Odds removidas pos-jogo chegam como 0; `.toFixed(2)` mostrava "0.00"
- Agora exibe em-dash quando `odd <= 0`

**Fix 5 — Log diagnostico para goals=null (gap do #008):**
- Quando AF match encontrado mas `goals_home` is None, o `continue` era silencioso
- Adicionado `logger.warning` com `fixture_id` antes do `continue`

### Licao aprendida

- Ao adicionar matching robusto em um endpoint (find_fixture), verificar se TODOS os endpoints que fazem matching similar foram atualizados. O /live-scores foi esquecido no #005.
- Timeouts devem considerar o pipeline completo (cold start + N API calls + processing), nao apenas um unico call.

---

## 068 — Fix CornerProgressBar invisivel em jogos ao vivo

**Data:** 2026-03-22
**Commit:** `441c531`
**Arquivos afetados:** `backend/services/api_football_client.py`, `frontend/next/src/components/CornerProgressBar.tsx`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Media
**Status:** Implementado

### Problema identificado

CornerProgressBar nunca aparecia em jogos ao vivo apesar do codigo estar presente. Tres gaps:
1. `enrich_fixture_record()` descartava corners do `extract_live_data()` — `currentCorners` nunca era populado na carga inicial via `/fixtures`
2. `extractTargetCorners()` so reconhecia "Over", ignorando picks "Escanteios Under X.5"
3. Sem suporte visual para Under (barra deveria indicar perigo ao ultrapassar limite)

### Causa raiz

`extract_live_data()` retorna `home_corners` e `away_corners` (linhas 618-619 em api_football_client.py), mas `enrich_fixture_record()` nunca copiava esses valores para o record. O frontend so recebia corners via `/live-scores` (polling separado) — se o polling falhasse (rate limit, ambas APIs vazias), corners nunca chegavam.

### Correcoes aplicadas

**Camada 1 — Backend: popular currentCorners em enrich_fixture_record() (api_football_client.py):**
- Apos overlay de status/score/minute/venue, copia `home_corners + away_corners` para `record["currentCorners"]`
- Se so `home_corners` disponivel, usa esse valor parcial
- Corners agora chegam na carga inicial via `/fixtures`, nao dependendo exclusivamente do polling `/live-scores`

**Camada 2 — Frontend: extractTargetCorners reconhece Over e Under (CornerProgressBar.tsx):**
- Retorno mudou de `number | null` para `{ target: number; direction: "over" | "under" } | null`
- Regex separado para Over (Math.ceil) e Under (Math.floor)

**Camada 3 — Frontend: CornerProgressBar com prop direction (CornerProgressBar.tsx):**
- Over: barra verde quando atinge meta (comportamento existente)
- Under: barra vermelha quando ultrapassa limite (novo)
- `isGood = direction === "over" ? hit : !hit` — logica invertida para Under

**Camada 4 — Frontend: MatchDetailCard passa direction (MatchDetailCard.tsx):**
- `extractTargetCorners` retorna objeto; desestrutura `target` e `direction`
- Passa `direction` ao `CornerProgressBar` e ao placeholder
- Placeholder mostra "Meta" (Over) ou "Limite" (Under)

**Camada 5 — CSS: classes danger para Under (match-detail-card.css):**
- `.cpb-fill--danger`: gradiente vermelho (substitui verde)
- `.cpb-badge--danger`: badge vermelho com glow

### Licao aprendida

- Funcao que extrai dados (`extract_live_data`) e funcao que aplica dados (`enrich_fixture_record`) sao separadas. Se a segunda nao consome um campo da primeira, o dado e silenciosamente descartado. Verificar que TODOS os campos extraidos sao usados downstream.
- Mercados bidirecionais (Over/Under) exigem que a UI represente ambas direcoes — uma regex so para "Over" ignora metade dos picks possiveis.

---

## 069 — Fix auditoria: Brier/SAFE/lambda per-league + CSS placeholder + lambda formula

**Data:** 2026-03-23
**Commit:** `832c0a8`
**Arquivos afetados:** `backend/cron_handler.py`, `backend/ai/prompt_templates.py`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Alta
**Status:** Implementado

### Problema identificado

Tres bugs na auditoria batch e um bug visual no frontend:

1. **Brier identico para todas as ligas:** `avg_brier` era calculado como media global unica (cron_handler.py:348) e passado ao prompt Mistral como valor singular. Mistral repetia o valor global em cada linha da tabela per-league.
2. **SAFE global = 0.0% mas ligas mostram 50-100%:** `safe_total` so conta picks com `status == "SAFE"` (cron_handler.py:187). Com circuit breaker #043 ativo, nenhum pick tem status SAFE → `safe_accuracy_pct = 0.0`. Mistral gerava valores per-league inventados a partir de `matches_summary_text`.
3. **Lambda erro 1.42 com formula imprecisa:** Usava `|lambda_total - total_goals|` (uma comparacao por jogo). A formula correta e `|lambda_home - goals_home| + |lambda_away - goals_away|` (per-team, conforme backtesting.py:138).
4. **Placeholder CornerProgressBar sem espacamento:** `.cpb-root` tinha `display: block !important` que sobrescrevia o `display: flex` do `.cpb-placeholder`, resultando em texto colado "ESCANTEIOSLimite: 9Aguardando dados...".

### Causa raiz

`_run_batch_audit()` acumulava metricas apenas em listas globais (`brier_scores`, `lambda_errors`, `safe_total/safe_correct`). Nao havia `league_metrics` dict para acumular per-league. O prompt template so recebia `avg_brier_score` como numero unico.

### Correcoes aplicadas

**BUG 1 — Brier per-league (cron_handler.py + prompt_templates.py):**
- Adicionado `league_metrics` dict que acumula `brier_scores`, `lambda_errors`, `correct/total`, `safe_correct/safe_total` por liga
- Gerado `league_accuracy_text` com Brier, lambda error e SAFE per-league
- Adicionado ao `batch_summary` e ao prompt template como secao "ACURACIA POR LIGA"

**BUG 2 — SAFE per-league (cron_handler.py):**
- Per-league SAFE accuracy agora e acumulada em `league_metrics[league]["safe_correct/safe_total"]`
- Inclusa no `league_accuracy_text` quando `safe_total > 0`
- O global `safe_accuracy_pct` continua correto (0.0% quando circuit breaker ativo)

**BUG 3 — Lambda formula (cron_handler.py):**
- Substituido `abs(lambda_total - total_goals)` por `abs(lambda_home - goals_home) + abs(lambda_away - goals_away)`
- Consistente com `compute_lambda_error()` em backtesting.py:138

**BUG 4 — CSS placeholder (match-detail-card.css):**
- `.cpb-root.cpb-placeholder` agora tem `display: flex !important` para sobrescrever o `!important` de `.cpb-root`

### Licao aprendida

- Quando o prompt para a AI so contem metricas globais, a AI inventa valores per-league. Fornecer dados reais per-league no prompt e essencial para relatorios corretos.
- Formulas de erro devem ser consistentes entre modulos (cron vs backtesting). A formula per-team (`|λh-gh| + |λa-ga|`) captura desvios que a formula total (`|λt-gt|`) mascara por cancelamento.
- CSS `!important` em seletores base (`.cpb-root`) impede que modificadores (`.cpb-placeholder`) funcionem sem seu proprio `!important`.

**Registo documentacao:** commit `4b41af5` — acrescentados SHAs **#068** (`441c531`) e **#069** (`832c0a8`) aos cabecalhos das respetivas seccoes (repo `sportsbankzu-pro`; copia na raiz do monorepo alinhada).

---

## 070 — /live-scores não lia corners do FootyStats (currentCorners sempre null)

**Data:** 2026-03-23
**Commit:** `799675a`
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

CornerProgressBar mostrava "Aguardando dados..." para TODOS os jogos ao vivo, mesmo quando FootyStats retornava dados de corners (`team_a_corners`, `team_b_corners`). O campo `currentCorners` era sempre `null` no endpoint `/live-scores`.

### Causa raiz

Investigação de 7 passos (PROMPT_INVESTIGATE_CORNERS.md) revelou que o `/live-scores` Path A (FootyStats primary) construía os registros de match sem NUNCA ler os campos `team_a_corners` / `team_b_corners` do FootyStats `todays-matches`. Os corners só apareciam se:
- API-Football enrichment (Path B) encontrasse o match E tivesse dados de corners
- Isso falhava quando AF não encontrava match (nome diferente) ou corners eram null no AF

O fix #068 (enrich_fixture_record) cobria apenas o endpoint `/fixtures`, não o `/live-scores` que é usado pelo polling do frontend.

### Correções aplicadas

**Camada 1 — FootyStats corners no /live-scores (fixtures.py:1315-1341):**
- Ler `m.get("team_a_corners")` e `m.get("team_b_corners")` antes de `result.append()`
- Validar: int, >= 0, try/except para ValueError/TypeError
- Setar `_rec["currentCorners"] = _fhc + _fac` quando ambos disponíveis
- AF overlay (linhas 1461-1495) sobrescreve se tiver dados mais recentes

**Camada 2 — Diagnostic WARNING (fixtures.py:1496-1500):**
- Log `[live-scores][corners] No corner data for live match` quando nenhuma fonte (FS nem AF) fornece corners
- Permite monitorar via CloudWatch quais jogos ficam sem dados

### Lição aprendida

- O endpoint `/live-scores` tem seu PRÓPRIO código de construção de records, separado do `enrich_fixture_record()` usado por `/fixtures`. Fixes em um não se propagam ao outro automaticamente.
- Ao corrigir um campo (como `currentCorners`), é preciso verificar TODOS os pontos de construção de records: `/fixtures` (via enrich), `/live-scores` Path A (FootyStats), `/live-scores` Path B (AF overlay), e `/live-scores` Path C (AF primary).
- A investigação de 7 passos confirmou que frontend (route.ts, dashboard merge, MatchDetailCard) repassa `currentCorners` corretamente — o problema era exclusivamente backend.

---

## 071 — Jogos ficam "VIVO 2T 90'" indefinidamente — nunca transitam para FT

**Data:** 2026-03-23
**Commit:** `d665249`
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Jogos ao vivo ficavam travados em "VIVO 2T 90'" indefinidamente no dashboard — nunca transitavam para "FT" (finished). O status permanecia "live" mesmo horas após o término real do jogo.

### Causa raiz (3 pontos de falha no frontend)

1. **`fetchLiveScores` retornava cedo em liveList vazio (linha 764):** Quando `/live-scores` retornava `matches: []` (jogo acabou e saiu da lista de live), o `return` impedia qualquer atualização de status. Jogos com `status === "live"` no state nunca eram marcados como "finished".

2. **`catch {}` silenciava erros 503 (linha 839):** Quando o backend retornava 503 (Lambda cold start, API Gateway timeout), o catch vazio engolia o erro sem retry. O status ficava congelado.

3. **Sem timeout de segurança:** Não havia mecanismo baseado em tempo decorrido para forçar transição de live → finished quando nenhuma fonte de dados confirmava o status.

### Correções aplicadas (3 camadas — defesa em profundidade)

**Camada 1 — Safety timeout (`useEffect` com `setInterval` 60s):**
- Se `match.status === "live"` E `elapsedMinutes(match.datetime) > 120` → marca como `"finished"` localmente
- Helper `elapsedMinutes()` adicionado como utility (baseado em `Date.now() - kickoff`)
- 120min = tempo máximo razoável para qualquer jogo de futebol (90min + intervalo + acréscimos)

**Camada 2 — Empty liveList handler (dentro de `fetchLiveScores`):**
- Quando `liveList.length === 0` mas existem matches com `status === "live"` no state, verifica `elapsedMinutes > 100`
- Se sim, marca como `"finished"` (o jogo provavelmente acabou e saiu da lista de live do FootyStats)
- 100min = threshold mais agressivo que Camada 1 porque temos confirmação (liveList vazio)

**Camada 3 — Retry com backoff no 503 + log de erros:**
- Em vez de silenciar o catch, faz 1 retry com delay progressivo (`3s * failCount`, max 15s)
- `liveScoreFailCountRef` rastreia falhas consecutivas
- Erros logados com `console.warn` em vez de engolidos silenciosamente

**Refatoração auxiliar:**
- Lógica de merge extraída para função `mergeLiveOverlay()` para reutilização no retry path e no path normal
- `elapsedMinutes(datetime)` helper adicionado junto com `computeLiveInfo` e `minutesToKickoff`

### Lição aprendida

- Um `return` silencioso quando `liveList.length === 0` é perigoso: ignora a informação de que o jogo NÃO está mais na lista de live. A ausência de dados É um dado relevante.
- `catch {}` vazio em polling é anti-pattern: erros transientes (503) devem ter retry, e erros persistentes devem ser logados para diagnóstico.
- Timeout de segurança baseado em elapsed time é a última linha de defesa contra estado stale. Ver também #021b (computeLiveInfo) e #032 (live score merge).

---

## 072 — Router AI Mistral v3.0 usava mock: análise real falhava para qualquer `match_id` válido

**Data:** 2026-03-23  
**Commit:** `2d26513`  
**Arquivos afetados:** `backend/routes/ai_analysis.py`  
**Severidade:** Alta (análise por jogo inutilizável em produção)  
**Status:** Corrigido  
**Relacionado:** `dc9dd31` (prompt v3.0 — 24 mercados), `b097961` (frontend `/analysis/legacy`)

### Problema identificado

O router `GET /api/ai/match/{match_id}/analysis` (v3.0) dependia de `_get_match_data()` e `_get_matches_by_league_and_date()` **mockados**, com um único registo falso (`id == '1'`). Para qualquer `match_id` real do pipeline (`fixtures`), o mock levantava `ValueError` → o utilizador via **serviço indisponível** / erro 400 apesar do prompt Mistral v3.0 e do frontend estarem corretos.

### Causa raiz

1. **Dados não ligados ao pipeline** — Nenhuma chamada a `fixtures_service` / `_process_single_league`; só dicionário estático.  
2. **Incompatibilidade de nomes de campos** — `mistral_analysis._build_prompt()` espera chaves **snake_case** (`lambda_home`, `prob_over_25`, `over_25`, `btts_yes`), enquanto os records do pipeline expõem **camelCase** (`lambdaHome`, `over25Prob`, `over25`, `bttsYes`). Sem mapeamento, mesmo com dados reais o prompt ficaria inconsistente.  
3. **Contexto Mistral** — `_mistral_context` (forma, H2H, lesões) precisava ser convertido para as strings que o v3.0 espera (`home_injuries_starters`, `h2h` legível, posições na tabela).

### Correções aplicadas

**Camada 1 — Fetch real assíncrono (`ai_analysis.py`):**
- `_get_match_data(match_id)` passa a ser `async`: `asyncio.to_thread(_process_single_league, league_id, date_str, base)` com `get_data_dir()` e procura do record por `r["id"] == match_id`.
- `_get_matches_by_league_and_date(league, date, limit)` idem, retornando lista mapeada com `[:limit]`.
- Callers `get_match_analysis` / `get_batch_analysis` usam `await`.

**Camada 2 — Resolução de `league_id` e data a partir do `match_id`:**
- `_extract_league_id()`: prefix-match do `match_id` contra `LEAGUES_CONFIG` (lista de slugs), **mais longo primeiro** para evitar colisão (ex.: `brasileirao-serie-a` vs `serie-a`).
- `_extract_date_from_id()`: segmento final do ID como timestamp Unix → `YYYY-MM-DD`; fallback `"today"` se parse falhar.

**Camada 3 — `_map_record_to_v3(record)`:**
- **stats:** cópia do dict do pipeline + aliases `lambda_home`/`lambda_away`, `prob_home`/`prob_draw`/`prob_away`, `prob_over_05`…`prob_over_45`, `prob_btts`, `homeXg`/`awayXg` (a partir de `homeXgForAvg`/`awayXgForAvg` quando existir).
- **odds:** aliases `over_05`…`over_45`, `under_25`/`under_35`/`under_45`, `btts_yes`/`btts_no` a partir de `over05`, `under35`, etc. Odds **Double Chance** (`dc_*`) continuam **N/A** se o pipeline não as expuser (aceite no desenho).
- **context:** `home_form`/`away_form`, `h2h` via `_format_h2h_str()`, lesões via `_format_injuries_str()` sobre `injuries.home`/`injuries.away`, posições a partir de `homeLeaguePosition`/`awayLeaguePosition`.
- **Equipas / meta:** `home_team`/`away_team` a partir de `homeTeam`/`awayTeam`, `league`, `start_time` ← `datetime`.

**Camada 4 — Correção de import:** uso de `LEAGUES_CONFIG` (nome real em `leagues_config.py`), não `SUPPORTED_LEAGUES` (inexistente).

**Sem alteração** em `backend/services/mistral_analysis.py` (regra do projeto: não mexer no prompt sem processo explícito — ver CLAUDE.md).

### Verificação sugerida

- `python -c "import py_compile; py_compile.compile('backend/routes/ai_analysis.py', doraise=True)"`  
- `python -c "from backend.routes.ai_analysis import router; ..."`  
- Chamada real: `/api/ai/match/{id_real_de_/fixtures}/analysis/legacy` após deploy Lambda.

### Lição aprendida

- **Mock com um único ID** dá falsa sensação de integração: E2E e UI podem parecer OK enquanto produção quebra para todos os jogos reais.  
- **Contrato de nomes** entre pipeline e consumidor LLM deve ser documentado ou centralizado (mapper único como `_map_record_to_v3`) para não divergir camelCase vs snake_case.  
- **Lesões e H2H** em formato bruto (dict/list API-Football) precisam de formatação explícita antes do prompt, senão o modelo ignora ou interpreta mal.

---

## 073 — Migração Mistral v3.7 → v3.0: prompt 24 mercados, remoção de rota orphan, ponte de formato legado

**Data:** 2026-03-23
**Commits:** `dc9dd31` (prompt v3.0), `2a8c896` (remoção orphan), `b097961` (ponte legado)
**Arquivos afetados:** `backend/services/mistral_analysis.py` (novo), `backend/routes/ai_analysis.py` (novo), `backend/main.py`, `frontend/next/src/app/api/ai/match/[id]/analysis/route.ts`
**Severidade:** Alta
**Status:** Implementado

### Problema identificado

O sistema usava o prompt Mistral v3.7 (`backend/ai/match_analysis_service.py`) com apenas 6 mercados. Havia 3 problemas simultâneos:

1. **Prompt limitado:** v3.7 cobria apenas 1X2, Over/Under 2.5, BTTS. Faltavam Over/Under 0.5-4.5, Double Chance, Escanteios 8.5-11.5, impacto de lesões de titulares.
2. **Rota orphan:** `POST /ai/match-analysis` no `main.py:1268` chamava `match_analysis_service.py` (v3.7), mas o frontend já usava `GET /api/ai/match/{id}/analysis` via `routes/ai_analysis.py` (v3.0). A rota orphan nunca era chamada.
3. **Mismatch de formato:** O frontend (`MatchDetailCard.tsx`) espera `{summary, key_points, recommendation, confidence}` (legado), mas o v3.0 retorna `{resumo_analitico, key_points, recomendacao_principal, confidence}`. Além disso, `to_legacy_format()` usava `keyPoints` (camelCase) e `lastUpdated` em vez de `key_points` e `last_updated`.

### Correções aplicadas

**Passo 1 — Upgrade do prompt para v3.0 (`dc9dd31`):**
- Novos ficheiros: `backend/services/mistral_analysis.py` (MistralAnalysisService v3.0) e `backend/routes/ai_analysis.py` (router com 4 endpoints).
- Output expandido: 24 mercados (1X2, Double Chance, Over/Under 0.5-4.5, BTTS, Escanteios Over/Under 8.5-11.5).
- Lesões filtradas apenas para titulares ([FORA]/[DÚVIDA]).
- Input enriquecido: +40 campos (xG, cartões/jogo, faltas, clean sheet %, médias da liga).
- 4 camadas de defesa anti-alucinação mantidas (CLAUDE.md proibição #6).

**Passo 2 — Remoção da rota orphan v3.7 (`2a8c896`):**
- Removida `POST /ai/match-analysis` (~25 linhas) e modelo `MatchAnalysisRequest` de `main.py`.
- `backend/ai/match_analysis_service.py` NÃO foi deletado (pode servir de referência futura).

**Passo 3 — Ponte de formato legado (`b097961`):**
- Frontend Next.js route alterada para chamar `/analysis/legacy` em vez de `/analysis`.
- `to_legacy_format()` corrigido: `keyPoints` → `key_points`, `lastUpdated` → `last_updated` para corresponder à interface `AIAnalysis` do frontend.

### Lição aprendida

- **Contrato frontend/backend** deve ser validado ANTES de deploy: nomes de campos (camelCase vs snake_case) entre Pydantic models, `to_legacy_format()`, e interfaces TypeScript devem ser explicitamente verificados.
- **Rotas orphan** acumulam-se silenciosamente quando endpoints são substituídos. Após migrar, sempre verificar todas as rotas que chamam o serviço antigo e eliminar as que não são mais usadas.

---

## 074 — Vercel Fluid Compute + maxDuration para plano Pro

**Data:** 2026-03-23
**Commit:** `e3ac3a6`
**Arquivos afetados:** `vercel.json`
**Severidade:** Média (infraestrutura)
**Status:** Implementado

### Problema identificado

O `vercel.json` tinha apenas `{"framework": "nextjs"}` sem configuração de Fluid Compute nem `maxDuration`. Funções serverless no Vercel tinham o timeout default (10s no plano Hobby), insuficiente para:
- `/api/matches/fetch` (busca fixtures de múltiplas ligas — até 30s)
- `/api/matches/live` (proxy para live scores — até 20s)
- `/api/ai/*/analysis` (chamada à API Mistral — até 55s)

### Correções aplicadas

- **Fluid Compute:** `"fluid": true` para reutilizar instâncias entre invocações.
- **maxDuration por rota:**
  - `app/api/matches/fetch/route.ts`: 60s, 1024MB
  - `app/api/matches/live/route.ts`: 60s, 1024MB
  - `app/api/ai/*/route.ts`: 30s, 1024MB
  - `app/api/**/*.ts`: 30s (fallback)
- Nota: path correto é `app/api/matches/live/route.ts` (não `app/api/live-scores/route.ts` que não existe).

### Lição aprendida

- Confirmar sempre o path real da rota antes de configurar `vercel.json` — o path no config deve corresponder ao filesystem relativo à raiz do Next.js, sem `src/`.

---

## 075 — Endpoints de auditoria por jogo retornam HTTP 404

**Data:** 2026-03-23
**Commit:** `2ec107a`
**Arquivos afetados:** `backend/routes/ai_analysis.py`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Ao clicar "Auditar" no painel de um jogo, a seção "Resultado da Auditoria" mostrava:

```
Confiança: 0%
Validação:
  Probabilidades  → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
  Lambdas         → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
  Expected Value  → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
```

A Análise AI funcionava normalmente (75% confiança, resumo, pontos-chave). Apenas a auditoria/validação por jogo estava quebrada com HTTP 404.

### Investigação detalhada

**1. Fluxo completo rastreado (frontend → backend):**

```
Botão "Auditar" (MatchDetailCard.tsx)
  → postMatchAudit() (lib/api.ts:279-306)
    → POST /api/ai/match/{id}/audit  (body: {predictions, ai_summary})
      → Next.js proxy (api/ai/match/[id]/audit/route.ts)
        → fetchBackend(`/api/ai/match/${id}/audit`)
          → Backend Lambda: /api/ai/match/{id}/audit  ← NÃO EXISTIA (404)
```

**2. Rotas existentes no backend:**

| Path | Onde | Status |
|------|------|--------|
| `POST /ai/audit-match` | `main.py:1256` | Rota antiga, path INCOMPATÍVEL |
| `GET /api/ai/match/{id}/analysis` | `ai_analysis.py` | OK |
| `GET /api/ai/match/{id}/analysis/legacy` | `ai_analysis.py` | OK |
| `POST /api/ai/match/{id}/analysis/regenerate` | `ai_analysis.py` | OK |
| `GET /api/ai/batch-analysis` | `ai_analysis.py` | OK |
| **`POST /api/ai/match/{id}/audit`** | **NENHUM** | **← 404** |
| **`POST /api/ai/match/{id}/audit/apply`** | **NENHUM** | **← 404** |

**3. Interfaces TypeScript esperadas pelo frontend:**

```typescript
// MatchDetailCard.tsx
interface AuditResult {
  validation: { probabilities, lambdas, ev }
  audit_confidence: number
  corrections?: AuditCorrection[]
}
interface AuditCorrection {
  type: string; parameter: string
  current_value: number; suggested_value: number
  reason: string; confidence: number; impact: string
}
```

**4. Backend audit disponível:**
- `MistralAuditor.audit_match_calculation(match_data)` em `backend/ai/mistral_auditor.py` — aceita dict com `id`, `homeTeam`/`home_team`, `stats`, `odds`
- `log_correction()` em `backend/audit.py` — persiste correções

### Causa raiz

Durante a migração Mistral v3.0 (#072, #073):
1. A rota orphan `POST /ai/audit-match` existia em `main.py:1256` com path `/ai/audit-match` (sem prefixo `/api/`)
2. O novo router `ai_analysis.py` (prefixo `/api/ai`) foi criado com 4 endpoints (analysis, legacy, regenerate, batch) mas **nenhum endpoint de auditoria**
3. O frontend chama `POST /api/ai/match/{id}/audit` que passa pelo Next.js proxy (`api/ai/match/[id]/audit/route.ts`) e chega ao backend como `/api/ai/match/{id}/audit`
4. **Path mismatch**: frontend espera `/api/ai/match/{id}/audit`, backend só tinha `/ai/audit-match` → HTTP 404

### Correções aplicadas

**Camada 1 — Novos endpoints no router v3.0 (`backend/routes/ai_analysis.py`):**

```python
# Pydantic models para request bodies
class _AuditRequest(BaseModel):
    predictions: Optional[list] = None
    ai_summary: Optional[dict] = None

class _CorrectionRequest(BaseModel):
    correction_type: str
    parameter_name: str
    old_value: float
    new_value: float
    reason: str
    audit_confidence: int = 0

@router.post("/match/{match_id}/audit")
async def audit_match(match_id: str, body: _AuditRequest = _AuditRequest()):
    # 1. Busca dados reais do pipeline via _get_match_data()
    # 2. Constrói auditor_input com ambos formatos de nome (home_team + homeTeam)
    # 3. Chama MistralAuditor.audit_match_calculation() via asyncio.to_thread
    # 4. Retorna {"status": "success", "audit": result}

@router.post("/match/{match_id}/audit/apply")
async def apply_audit_correction(match_id: str, body: _CorrectionRequest):
    # 1. Busca match_data para identificar liga
    # 2. Chama log_correction() com todos os campos
    # 3. Retorna {"status": "success", "message": "Correcao aplicada para {match_id}"}
```

**Camada 2 — Compatibilidade de nomes:**
- O dict `auditor_input` inclui ambos formatos (`home_team`/`homeTeam`, `away_team`/`awayTeam`) porque `MistralAuditor` e `PromptTemplates.audit_calculation_prompt()` aceitam ambos formatos em pontos diferentes do código

**Camada 3 — Validação e error handling:**
- `ValueError` (match não encontrado via `_get_match_data`, liga inválida via `_extract_league_id`) → HTTP 400
- Erros gerais (Mistral API down, timeout, etc.) → HTTP 500 com log detalhado

### Verificação

```bash
# Antes do fix:
curl -X POST .../api/ai/match/test-id/audit → HTTP 404 {"detail":"Not Found"}

# Depois do fix:
curl -X POST .../api/ai/match/test-id/audit → HTTP 400 {"detail":"Liga nao identificada..."}
curl -X POST .../api/ai/match/{real-id}/audit → HTTP 200 {"status":"success","audit":{...}}
```

- Total de rotas no router: 6 (era 4, +audit, +audit/apply)
- Imports verificados: `from backend.ai.mistral_auditor import MistralAuditor` e `from backend.audit import log_correction` (deferred imports para evitar circular)

### Lição aprendida

Ao migrar routers, verificar não apenas os endpoints de CRUD principal (analysis, regenerate, batch) mas **também endpoints auxiliares** (audit, validate, export) que dependem do mesmo serviço. O path do frontend proxy deve corresponder **exatamente** ao prefix+path do router backend. Manter uma tabela de endpoints (path, método, origem, destino) durante migrações para não perder rotas.

---

## 076 — /live-scores retorna 0 jogos quando FootyStats tem dados mas todos filtrados

**Data:** 2026-03-24
**Commit:** `e1858d5`
**Arquivos afetados:** `backend/routes/fixtures.py` (linhas 1343-1410 aprox.)
**Severidade:** Crítica — bug silencioso, sem erro HTTP, dados simplesmente desaparecem
**Status:** Corrigido

### Problema identificado

O endpoint `/live-scores` retornava `{"matches": [], "nextUpdate": 60}` com HTTP 200 (sem erro!) mesmo com 9 jogos ao vivo globalmente. O jogo Huracán vs Barracas Central (Argentina Primera División, 78', 0-0) era invisível no dashboard.

**Sintomas enganosos que dificultaram a localização:**
- HTTP 200 (não 404 nem 500) — parecia funcionar
- Nenhum log de warning no CloudWatch — o código não logava nada quando retornava vazio
- A duração do request era 5ms (cache hit do FootyStats) — parecia saudável
- O endpoint `/live` (API-Football direto) retornava 9 jogos corretamente
- O endpoint `/fixtures` processava o Huracán normalmente nos logs

### Investigação detalhada — por que foi difícil localizar

**Passo 1 — Verificação inicial:**
```bash
curl .../live-scores → {"matches":[],"nextUpdate":60}  # HTTP 200, sem erro
```
Sem erro HTTP, sem mensagem de erro. O endpoint simplesmente retorna lista vazia.

**Passo 2 — Logs do CloudWatch:**
```
REQUEST 17f5e5e1 Duration: 4.87ms  # Nenhum log interno!
```
A request completou em 5ms sem gerar nenhum warning. Isso indicou cache hit do FootyStats — a chamada `footstats.get_live_scores()` retornou do cache SQLite instantaneamente.

**Passo 3 — Verificação cruzada:**
```bash
curl .../live → 9 matches (Huracán, Aucas, etc.)  # API-Football direto funciona!
```
O `/live` endpoint (usa API-Football via `live.py`) retornava todos os jogos. O problema era exclusivo do `/live-scores` (em `fixtures.py`).

**Passo 4 — Trace do fluxo no código:**

```
/live-scores (fixtures.py:976)
│
├─ footstats.get_live_scores() → success:true, data:[...5 items...]
│   └─ FootyStats todays-matches retorna jogos de OUTRAS ligas
│       (Costa Rica, México, etc.) com status="incomplete" ou "scheduled"
│
├─ raw_list = data["data"] → NÃO vazio (5 items)
│
├─ if not raw_list: ← FALSO! raw_list tem items
│   └─ Fallback API-Football: NUNCA ATIVADO  ← BUG AQUI
│
├─ Loop raw_list (linha 1105):
│   ├─ status_map("incomplete") → "scheduled"
│   ├─ "scheduled" not in ("live", "finished") → SKIP
│   ├─ status_map("scheduled") → "scheduled" → SKIP
│   └─ ... todos os 5 items são SKIP
│
├─ result = []  ← VAZIO após filtragem
│
├─ API-Football enrichment (linha 1346):
│   └─ for rec in result: ← result vazio, loop não executa
│
└─ return {"matches": [], "nextUpdate": 60}  ← RETORNA VAZIO
```

**O bug estava na condição da linha 1005:**
```python
if not raw_list and _afc.is_configured:  # Só ativa quando raw_list é COMPLETAMENTE vazio
```

Cenários reais não cobertos:
- FootyStats retorna 5 jogos de ligas menores (scheduled/incomplete) → raw_list=[5 items]
- Todos são filtrados → result=[]
- API-Football tem 9 jogos ao vivo → NUNCA consultado
- Dashboard mostra 0 jogos

### Causa raiz

A arquitetura de fallback do `/live-scores` tinha **3 pontos onde API-Football é usado**:

| Ponto | Condição | O que faz | Cobria o bug? |
|-------|----------|-----------|---------------|
| **Linha 1005** | `raw_list` vazio | API-Football como fonte primária | **NÃO** — raw_list não estava vazio |
| **Linha 1086** | `raw_list` vazio (2a checagem) | Serve cache ou retorna vazio | **NÃO** — mesmo motivo |
| **Linha 1346** | Enrich items em `result` | Overlay scores nos items do FootyStats | **NÃO** — result estava vazio, nada a enricher |

**Nenhum dos 3 pontos cobria o cenário: "FootyStats retorna dados, mas nenhum é live/finished".**

Isso acontece frequentemente para ligas sul-americanas (Argentina, Colômbia, Equador) porque:
1. FootyStats `todays-matches` é um endpoint global que retorna jogos de TODAS as ligas
2. Jogos de ligas sem season_id ativo podem aparecer como "incomplete" ou "scheduled"
3. API-Football `fixtures?live=all` retorna corretamente os jogos ao vivo de TODAS as ligas
4. Mas o fallback só era acionado quando FootyStats retornava **zero** items

### Correções aplicadas

**Camada 1 — Fallback API-Football pós-filtragem (`fixtures.py`, após linha 1344):**

Adicionado novo bloco entre a filtragem do FootyStats e o enrichment do API-Football:

```python
# ── API-Football as PRIMARY when FootyStats had data but all filtered (#075) ──
# FootyStats may return matches from other leagues (all "scheduled") while
# the Argentine/Colombian league matches are only in API-Football.
# In this case raw_list is non-empty but result is empty after filtering.
if not result and _afc.is_configured:
    try:
        af_live = _afc.get_live_fixtures()
        if af_live:
            af_result = []
            period_map = {"1H": "1T", "HT": "HT", "2H": "2T", "ET": "ET", "BT": "HT", "P": "PEN"}
            for fx in af_live:
                ld = _afc.extract_live_data(fx)
                # ... extrai teams, status, score, corners
                # Corner extraction: inline data → fallback get_fixture_statistics()
                entry = {
                    "id": ld["fixture_id"],
                    "homeTeam": home_name,
                    "awayTeam": away_name,
                    "status": _af_status,
                    "score": score_entry,
                    "period": period_map.get(fx_status),
                    "minute": ld["minute"],
                    "dateUnix": fx.get("fixture", {}).get("timestamp"),
                }
                if current_corners is not None:
                    entry["currentCorners"] = current_corners
                af_result.append(entry)
            if af_result:
                logger.info(
                    f"[live-scores] FootyStats filtered to 0 → API-Football primary: "
                    f"{len(af_result)} matches"
                )
                result = af_result
    except Exception as _af_err:
        logger.warning(f"[live-scores] API-Football post-filter fallback failed: {_af_err}")
```

**Lógica de extração de corners (3 camadas dentro do bloco):**
1. Inline: `extract_live_data()` → `home_corners` + `away_corners` do `fixtures?live=all`
2. Stats API: se inline é None → `get_fixture_statistics(fixture_id)` → `_extract_corners_from_stats()`
3. Parsed: se extraction falha → `parse_fixture_statistics()` → `corner_kicks` key

**Onde o novo bloco se encaixa no fluxo:**

```
/live-scores
├─ FootyStats todays-matches → raw_list (pode ter items)
├─ if not raw_list → API-Football primary (bloco existente, linha 1005)
├─ Loop raw_list → filter live/finished → result
├─ if not result → API-Football primary (NOVO BLOCO #076) ← AQUI
├─ API-Football enrichment → overlay nos items de result (existente, linha 1346)
└─ return result
```

### Verificação em produção

```bash
# ANTES do fix:
curl .../live-scores
→ {"matches":[],"nextUpdate":60}

# DEPOIS do fix:
curl .../live-scores
→ 9 matches:
  Antigua GFC vs Marquense [live 1T 45'] corners=MISS
  UMECIT vs Herrera [live 1T 25'] corners=MISS
  Huracan vs Barracas Central [live 2T 82'] 0-0 corners=9   ← CORNERS FUNCIONANDO
  Aucas vs Orense SC [live 2T 85'] 3-0 corners=4            ← CORNERS FUNCIONANDO
  Corinthians W vs America Mineiro W [live 2T 90'] 4-0
  Mount Pleasant Academy vs Portmore United [live 2T 62'] 2-0
  Pitbulls Santa Barbara FC vs Escorpiones Belén [live HT 45'] 1-0
  León W vs Atlas W [live HT 45'] 1-0
  Lobos Upnfm vs Olancho [live HT 45'] 2-1
```

Corners=9 para Huracán confirma que a extração de corners via API-Football funciona no novo bloco.

### Por que este bug era difícil de localizar

1. **HTTP 200 sem erro** — não aparece em monitoramento de erros
2. **Nenhum log de warning** — o código simplesmente retornava vazio sem alertar
3. **Cache de 30s mascara** — duração de 5ms sugere "tudo OK"
4. **Funciona para algumas ligas** — quando FootyStats cobre a liga (ex: Premier League), jogos aparecem normalmente
5. **Endpoints vizinhos funcionam** — `/live` (API-Football direto) e `/fixtures` retornam dados
6. **Condição sutil** — a diferença entre `raw_list` vazio e `result` vazio após filtragem é fácil de confundir
7. **Intermitente** — só ocorre quando FootyStats retorna items de outras ligas (depende do horário e ligas ativas)

### Ligas afetadas (não cobertas pelo FootyStats todays-matches)

Baseado na observação, as seguintes ligas podem ser afetadas:
- Argentina Primera División
- Campeonato Colombiano
- Liga Pro Ecuador
- Liga Nacional Guatemala/Honduras
- Liga Panameña
- Cualquer liga não-europeia quando FootyStats retorna dados de ligas europeias primeiro

### Lição aprendida

1. **Fallbacks devem cobrir "sem dados úteis", não apenas "sem dados brutos"** — um `raw_list` com 5 items scheduled é funcionalmente equivalente a vazio para o propósito de live scores
2. **Sempre logar quando retorna vazio em endpoints críticos** — se `/live-scores` retorna 0 matches, deveria logar warning com: `"[live-scores] 0 matches after filtering {len(raw_list)} raw items (statuses: {skipped_statuses})"`
3. **Testar com ligas sul-americanas** — FootyStats tem cobertura inconsistente para ligas fora da Europa. Testes end-to-end devem incluir ao menos 1 liga SA
4. **Validar consistência entre endpoints** — se `/live` retorna N jogos e `/live-scores` retorna 0, há um bug em uma das camadas

**Registo documentação:** entrada **#076** alargada (diagramas de fluxo, investigação em 5 passos, tabela dos 3 pontos API-Football, 7 razões de dificuldade, ligas SA, lições); entrada **#075** alargada (tabela de rotas, fluxo frontend→Lambda, snippets Pydantic). Commit docs: `e0ea953`. *Nota:* a mensagem Git do fix em `fixtures.py` pode citar “(#075)”; neste documento a correção live-scores está numerada como **#076** para não colidir com **#075** (auditoria 404).

---

## 077 — Refinamento visual CornerProgressBar + Brier per-league persistente

**Data:** 2026-03-24
**Commit:** `5fb001c`
**Arquivos afetados:** `frontend/next/src/styles/match-detail-card.css`, `frontend/next/src/lib/api.ts`, `frontend/next/src/lib/localAudit.ts`, `frontend/next/src/components/AuditReportCard.tsx`
**Severidade:** Baixa (visual), Alta (Brier)
**Status:** Corrigido

### Problema identificado

1. **CornerProgressBar** mais larga que a barra de confiança — desproporcional no painel lateral. Track 18px era maior que os 6-8px da barra de confiança.
2. **Brier Score idêntico** para todas as ligas no relatório de auditoria. O fix #069 adicionou `league_metrics` no backend `cron_handler.py`, mas a auditoria agora roda localmente no frontend (`localAudit.ts`) que NÃO tinha acumulação per-league de Brier.
3. **Label "SAFE"** per-league contava todos os picks (SAFE + NEUTRO) mas mostrava o rótulo "SAFE", criando confusão quando circuit breaker #043 ativo (0 picks SAFE global, mas 80% "SAFE" per-league).

### Causa raiz

**Bug A (Brier idêntico):** O fluxo completo é:

```
localAudit.ts:runLocalAudit()
  → calcula brierScores[] GLOBAL (linha 680-685)
  → leagueMap NÃO acumulava Brier per-league (linhas 748-769)
  → LeagueAuditStats NÃO tinha campo brier_score (api.ts:413-419)
  → AuditReportCard.tsx linha 86: brierScore = r.avg_brier_score (GLOBAL para TODAS as ligas)
```

O fix #069 no backend (`cron_handler.py`) estava correto: `lg_brier = sum(lm["brier_scores"]) / len(lm["brier_scores"])`. Porém, a auditoria migrou para rodar localmente no browser via `localAudit.ts`, e esta migração NÃO portou a lógica per-league de Brier.

**Bug B (label SAFE):** `lg.safeHits`/`lg.safeTotal` no AuditReportCard mapeavam `picks_correct`/`picks_total` (TODOS os picks), mas o label dizia "SAFE". Quando circuit breaker #043 ativo, global SAFE=0% mas per-league mostrava 80% "SAFE".

**Visual:** `.cpb-track` tinha `height: 18px` e `.cpb-root` tinha `width: 100%` sem margens, dominando visualmente sobre a barra de confiança.

### Correções aplicadas

**Camada 1 — Frontend visual (CSS):**
- `.cpb-root`: `margin: 0 8px` (recuada das bordas), `border-radius: 6px`
- `.cpb-track`: `height: 4px` (vs 6-8px da confiança), `overflow: visible`, `border: 1px solid #222`
- `.cpb-badge`: 20px circular com `border: 2px solid #141414` (recorte visual), `transform: translate(50%, -50%)`
- `.cpb-fill`: cor normal via `:not(.cpb-fill--hit):not(.cpb-fill--danger)`, danger agora `#dc2626→#ef4444`
- `.cpb-placeholder`: `border: 1px dashed #2a2a2a`, animação `cpb-pulse` sutil

**Camada 2 — Per-league Brier (frontend):**
- `api.ts`: adicionado `brier_score?: number` a `LeagueAuditStats` e `BatchAuditMatchResult`
- `localAudit.ts`: captura `matchBrier` por jogo (linha 680), adiciona a `matchResults`, acumula `brierScores[]` no `leagueMap`, calcula média per-league no output
- `AuditReportCard.tsx:86`: `brierScore: lg.brier_score ?? r.avg_brier_score` (usa per-league quando disponível, fallback global)

**Camada 3 — Label SAFE→Acurácia:**
- `AuditReportCard.tsx`: label per-league alterado de "SAFE" para "Acurácia" (reflete que conta TODOS os picks, não apenas SAFE)
- Aplicado tanto no `formatReport()` (clipboard) quanto no render JSX

### Lição aprendida

1. O fix #069 corrigiu o backend (`cron_handler.py`), mas a auditoria migrou para rodar localmente no frontend (`localAudit.ts`) — e o frontend nunca implementou a mesma lógica per-league. Ao migrar funcionalidade entre camadas (backend→frontend), verificar que TODAS as sub-features são portadas.
2. Labels devem refletir o que os dados realmente medem. "SAFE" per-league contava todos os picks → deveria ser "Acurácia".
3. Elementos visuais complementares devem ser SUBORDINADOS ao principal. Track height, margin e tipografia menores comunicam hierarquia visual.

---

## 078 — Dixon-Coles Complete Model (τ, γ, ρ calibration)

**Data:** 2026-03-24
**Arquivos afetados:** `backend/modeling/poisson_matrix.py`, `backend/modeling/lambda_calculator.py`, `backend/services/league_calibrator.py`, `tests/unit/test_dixon_coles.py`
**Severidade:** Alta
**Status:** Implementado
**Relacionado:** #053 (forças relativas λ), #078v (MLE para ρ, bug de extração de gols, validação em 6 ligas)

### Problema identificado

O motor Poisson usado desde #028 assume independência completa entre gols marcados pelo mandante e visitante. O paper original de Dixon & Coles (1997) identifica 3 extensões fundamentais que melhoram a calibração:

1. **τ(ρ) correction** — os resultados de baixa pontuação (0-0, 1-0, 0-1, 1-1) têm probabilidade diferente da prevista por Poisson independente, devido à correlação entre gols
2. **Temporal decay** — jogos recentes devem ter mais peso que jogos antigos na estimativa de parâmetros
3. **Home advantage γ** — fator explícito de vantagem de mando de campo sobre λ_home

### Causa raiz

REGRAS #053 implementou forças relativas Dixon-Coles (`λ = media_liga × ataque_rel × defesa_rel`), mas manteve a multiplicação independente P(h,a) = P(h) × P(a) na matriz de scorelines. Isso sistematicamente subestima empates e resultados de 0-0/1-1, prejudicando especialmente a calibração de 1X2 e Draw.

### Correções aplicadas

**Camada 1 — τ(ρ) em `poisson_matrix.py`:**
- Nova função `dixon_coles_tau(x, y, λ, μ, ρ)` implementa a correção multiplicativa dos 4 scorelines baixos
- `build_scoreline_matrix()` recebe parâmetro `rho=0.0` (backward compatible)
- `_get_rho()` lê ρ calibrado da corrections DB (default -0.10)
- `derive_all_markets()` passa ρ para todas as 3 matrizes (1X2, O/U, BTTS)

**Camada 2 — γ em `lambda_calculator.py`:**
- `_get_home_advantage_gamma()` lê fator γ da corrections DB (default 1.0 = sem ajuste extra)
- Aplicado em `calcular_lambda_jogo()` após cálculo de ambos lambdas, antes das correções de auditoria
- Home advantage implícito (stats home-specific) mantido — γ é fator ADICIONAL

**Camada 3 — Decay utilities em `lambda_calculator.py`:**
- `weighted_average_with_decay(values, half_life_games)` — média ponderada com decaimento exponencial
- `half_life_to_weights(half_life_games, matches_played)` — bridge entre half-life e season/recent weights
- Funções utilitárias para uso futuro quando dados per-game estiverem disponíveis (Bloco 2)

**Camada 4 — ρ calibration em `league_calibrator.py`:**
- `RHO_GRID = [round(-0.25 + i * 0.01, 2) for i in range(31)]` — grid expandido [-0.25, 0.05]
- `_simulate_all_markets()` recebe `rho` e aplica τ em todos os loops internos (O/U, BTTS, 1X2)
- Grid search #4 otimiza ρ por **MLE (log-likelihood)** — Brier é insensível a ρ (#078v)
- Sanity guard: cap ρ em -0.15 se grid retornar ≤ -0.20
- ρ salvo na corrections DB via `save_calibration()`

**Camada 5 — Tests em `tests/unit/test_dixon_coles.py`:**
- 12 testes: τ (ρ=0, ρ<0, scorelines altos), matriz (soma≈1, backward compat, draw boost), γ (default e corrections), decay (half-life, peso recente, lista vazia), `half_life_to_weights`
- Verifica backward compatibility (ρ=0 ≡ Poisson independente)

### Lição aprendida

1. Extensões de modelo estatístico devem ser implementadas com backward compatibility (parâmetro default que reproduz o comportamento anterior). Isso permite deploy seguro sem recalibração imediata.
2. ρ é calibrado por liga — ligas diferentes têm correlações diferentes entre gols de mandante e visitante.
3. O grid search de ρ deve otimizar por **MLE** (log-likelihood), não Brier — ver #078v para detalhes.

---

## 078v — Validação do parâmetro ρ (rho) de Dixon-Coles

**Data:** 2026-03-24
**Commits:** `d401ab4` (fix extração `homeGoalCount`/`awayGoalCount` em `_extract_matches_from_season`), `ab451c4` (documentação REGRAS #078v + ajustes no texto do #078)
**Arquivos afetados:** `backend/services/league_calibrator.py`, `docs/REGRAS_CORRECAO_SISTEMA.md`
**Severidade:** Crítica (bug afetava TODA a calibração, não só ρ)
**Status:** Corrigido + Validado

### Problema investigado

Calibração da Premier League escolheu ρ = -0.15, que era o boundary do grid
original [-0.15, 0.05]. Anti-pattern documentado no #053 (28 ligas no teto).
Grid expandido para [-0.25, 0.05] — todas 6 ligas AINDA retornavam ρ = -0.15
(ou -0.25 com MLE). Investigação revelou 2 bugs fundamentais.

### Causa raiz

**Bug 1 — Brier insensível a ρ:**
O grid search #4 de ρ usava Brier score como objetivo. Análise sintética mostrou
que o Brier varia apenas ~0.002 no 6º decimal ao longo de todo o range de ρ — essencialmente
flat. O Brier mede a qualidade das probabilidades finais (que são uma mistura de muitos
scorelines), não é sensível à redistribuição de probabilidade entre os 4 scorelines baixos
que τ(ρ) afeta.

**Correção:** Substituído por MLE (Maximum Likelihood Estimation):
`LL(ρ) = Σ log[τ(x_i, y_i, λ_h_i, λ_a_i, ρ)]`, conforme Dixon & Coles (1997).

**Bug 2 — Matches com 0 gols silenciosamente excluídos (CRÍTICO):**
```python
# ANTES (bugado):
gh = m.get("homeGoalCount") or m.get("home_goals")
```
Python `or` trata `0` como falsy. Para um jogo 0-0: `homeGoalCount = 0` →
`0 or m.get("home_goals")` → se `home_goals` não existe → `0 or None = None` →
match dropped pelo `if gh is None: continue`.

**Impacto:** TODA partida onde pelo menos um time marcou 0 gols era excluída
do dataset de calibração. Diagnóstico mostrou `scores={0-0:0, 0-1:0, 1-0:0, 1-1:240}`
para 1196 partidas da PL — ~50% dos jogos perdidos.

Isso afetava não apenas ρ, mas TODA calibração (O/U, BTTS, 1X2, λ deflation)
desde a implementação original de `_extract_matches_from_season`.

**Correção:** o mesmo padrão aplica-se a **visitante** (`awayGoalCount` / `away_goals`).

```python
# DEPOIS (correto):
gh = m.get("homeGoalCount")
if gh is None:
    gh = m.get("home_goals")
ga = m.get("awayGoalCount")
if ga is None:
    ga = m.get("away_goals")
```

### Resultados da validação

| Liga | N matches | ρ calibrado | Boundary? | LL curve |
|------|-----------|-------------|-----------|----------|
| Premier League | ~2000 | -0.06 | Não | Concava, pico claro |
| La Liga | 2190 | -0.07 | Não | Concava |
| Bundesliga | 1773 | -0.17 | Não | Concava, explicável por λ alto |
| Brasileirão Serie A | 1976 | -0.04 | Não | Concava |
| Primera División (Arg) | 2715 | -0.13 | Não | Concava, liga defensiva |
| Serie A (Italy) | 2201 | -0.06 | Não | Concava |

Score counts agora realistas (exemplo PL):
- Antes: `{0-0:0, 0-1:0, 1-0:0, 1-1:240, other:956}` (bug)
- Depois: `{0-0:~150, 0-1:~160, 1-0:~250, 1-1:~280, other:~1160}` (correto)

### Lição aprendida

1. **Python `or` com valores numéricos é perigoso** — `0 or fallback` retorna o fallback
   porque 0 é falsy. Usar `if x is None: x = fallback` explícito para campos numéricos.
2. **Brier score é insensível a redistribuições internas** — quando τ(ρ) redistribui
   probabilidade entre scorelines baixos mas o total para Over/Under/Draw não muda muito,
   Brier não detecta a diferença. MLE é o objetivo correto para calibrar ρ.
3. **Diagnóstico detalhado é essencial** — sem o logging de score_counts, o bug teria
   permanecido invisível. O anti-pattern "todas as ligas no mesmo valor" foi o primeiro
   sintoma que levou à investigação.
4. **Bug de extração de dados afeta TODA calibração** — não apenas o parâmetro sendo
   investigado. Todas as ligas previamente calibradas (#052-#056) foram treinadas com
   ~50% dos jogos faltando (todos os jogos com pelo menos um 0-0, 0-X, X-0).

### Infra (conhecido em produção)

Em ambiente Lambda, se `PutObject` no bucket S3 de calibrações estiver negado (IAM), os parâmetros calibrados (incluindo ρ) podem **não persistir** entre cold starts — a validação via CloudWatch (logs `rho-data`, `rho-LL`, `optimal rho`) confirma o comportamento do código; corrigir a política do role (`s3:PutObject` no prefixo de calibrações) para persistência durável.

**Registo documentação:** entrada **#078v** (commits `d401ab4`, `ab451c4`, correção `ga`, nota S3); refinamentos no **#078** (relacionados, contagem de testes).

---

## 078r — Limpeza de ligas (37→22) + Recalibração completa

**Data:** 2026-03-24
**Arquivos afetados:** `backend/config/leagues_config.py`, `backend/config/league_dna.py`, `backend/main.py`, `backend/modeling/calibrator.py`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/hooks/useLeagueClassifications.ts`, `frontend/next/src/lib/mockMatches.ts`
**Severidade:** Alta
**Status:** Implementado

### Problema identificado

1. 15 ligas com dados insuficientes na FootyStats (< 100 jogos/temporada ou sem dados)
   geravam calibrações instáveis ou INSUFFICIENT_DATA. Estas ligas inflavam o config
   sem contribuir valor real ao sistema.

2. S3 `AccessDenied` impedia persistência de calibrações — o IAM role do Lambda
   (`sportsbank-pro-lambda-role`) tinha apenas `AmazonS3ReadOnlyAccess`, sem `s3:PutObject`.

3. Todas as 22 ligas remanescentes precisavam recalibração limpa (dataset corrigido
   pelo fix de 0-goal do #078v + grid expandido de ρ).

### Causa raiz

- **Config inflado**: Adição progressiva de ligas sem verificação de cobertura de dados.
- **IAM incompleto**: Deploy inicial só configurou `S3ReadOnlyAccess` no role.
- **Calibrações stale**: Bugs anteriores (#078v) invalidaram calibrações existentes.

### Correções aplicadas

**Camada 1 — Remoção de 15 ligas (37→22):**

Removidas de TODOS os config files (backend + frontend):
- j-league, k-league, eliteserien, allsvenskan (0 matches na FootyStats)
- ligue-2, league-two, serie-b-czech, eerste-divisie, segunda-division (2ª divisão redundante)
- copa-do-brasil (formato mata-mata, incompatível com calibração)
- austrian-bundesliga, super-league, professional-league, super-league-greece, uae-pro-league (dados insuficientes)

Arquivos editados:
- `leagues_config.py`: LEAGUE_ID_ALIASES, LEAGUES_CONFIG, API_FOOTBALL_LEAGUE_IDS, CALENDAR_YEAR_LEAGUES
- `league_dna.py`: LEAGUE_DNA_MATRIX (22 entradas)
- `main.py`: mock teams, league_names, offensive_leagues, aliases_map
- `leagues.ts`: AVAILABLE_LEAGUES (22 entries)
- `useLeagueClassifications.ts`: RETRAIN_TO_FRONTEND_ID
- `mockMatches.ts`: removed mock data for 4 deleted leagues
- `calibrator.py`: _SEASON_STARTS (removed 3 deleted leagues)

**Camada 2 — Fix IAM S3:**

Adicionada inline policy `S3CalibrationWrite` ao role `sportsbank-pro-lambda-role`:
```json
{"Effect":"Allow","Action":["s3:PutObject","s3:DeleteObject"],"Resource":"arn:aws:s3:::meu-bucket-sportsbank/calibrations/*"}
```

**Camada 3 — Recalibração completa (22/22):**

Resultados (ρ por liga via MLE com dataset corrigido):

| Liga | ρ | defl_ou | defl_1x2 |
|------|-----|---------|----------|
| premier-league | -0.06 | 1.0 | 0.9 |
| championship | -0.04 | 1.0 | 0.9 |
| league-one | 0.0 | 1.0 | 0.9 |
| la-liga | -0.07 | 1.0 | 0.9 |
| serie-a | -0.06 | 1.0 | 0.9 |
| serie-b | -0.14 | 1.0 | 0.9 |
| bundesliga | -0.17 | 1.0 | 0.9 |
| 2-bundesliga | -0.10 | 1.0 | 0.9 |
| ligue-1 | -0.07 | 1.0 | 0.9 |
| brasileirao-serie-a | -0.04 | 0.95 | 0.9 |
| brasileirao-serie-b | -0.06 | 0.95 | 0.9 |
| eredivisie | -0.09 | 1.0 | 0.9 |
| primeira-liga | +0.01 | 1.0 | 0.97 |
| super-lig | -0.12 | 0.95 | 0.9 |
| pro-league | -0.06 | 1.0 | 0.9 |
| premiership | -0.02 | 1.0 | 0.9 |
| superliga | -0.11 | 1.0 | 0.9 |
| primera-division | -0.13 | 0.95 | 0.9 |
| a-league | +0.03 | 1.0 | 0.9 |
| mls | -0.09 | 1.0 | 0.9 |
| colombian-primera-a | -0.10 | 1.0 | 0.9 |
| liga-mx | -0.09 | 1.0 | 0.9 |

Distribuição ρ saudável: range [-0.17, +0.03], mediana ≈-0.07, sem hits de boundary.

### Lição aprendida

1. **Manter config enxuto** — ligas sem dados suficientes geram ruído de calibração.
   Manter apenas ligas com 100+ jogos/temporada e cobertura estável na API.
2. **IAM deve ser verificado no deploy** — policies de escrita (PutObject) são tão
   críticas quanto as de leitura para persistência de estado em Lambda.
3. **Calibrações concorrentes no Lambda geram race condition** — cada invocação Lambda
   tem seu próprio /tmp e SQLite. `export_corrections_to_s3()` sobrescreve o arquivo
   inteiro. Calibrar sequencialmente ou em invocação única.

---

## 079 — BLOCO 2: Métricas determinísticas e audit sem LLM

**Data:** 2026-03-24
**Arquivos afetados:** `backend/services/backtesting.py`, `backend/services/deterministic_audit.py` (novo), `backend/cron_handler.py`, `backend/routes/ai_analysis.py`, `tests/unit/test_metrics_079.py` (novo)
**Severidade:** Alta
**Status:** Implementado
**Relacionado:** #069 / #077 (Brier e métricas per-league no audit), #043 (circuit breaker SAFE), #075 (rotas de auditoria)

### Problema identificado

1. Batch audit usava `MistralAuditor.evaluate_model_from_batch()` — não-determinístico, custo de API, risco de alucinação em `recommended_corrections`.
2. Audit por jogo usava `MistralAuditor.audit_match_calculation()` — mesmos problemas.
3. Faltavam métricas **Sharpe** (retornos por pick) e **hit rate por banda de EV** no pacote de backtesting.
4. `compute_log_loss` e `compute_calibration_bins` já existiam em `backtesting.py` mas o loop do **cron** não alimentava Log-Loss de forma explícita nem consolidava notas per-league no relatório.

### Causa raiz

Uso de LLM onde o produto precisa de **reprodutibilidade**, testes unitários e custo previsível (zero chamadas Mistral nestes dois fluxos quando os flags estão ativos).

### Correções aplicadas

**Camada 1 — Novas métricas (`backtesting.py`):**

- Constantes: `MIN_N_BRIER=20`, `MIN_N_SHARPE=50`, `MIN_N_RELIABILITY=30`, `MIN_N_LOG_LOSS=20`.
- `compute_sharpe_ratio(picks)`: retorno por unidade apostada — vitória `odd - 1`, derrota `-1`; `sharpe = mean/std` só se `n >= MIN_N_SHARPE` e `std > 0`.
- `compute_hit_rate_by_ev_band(picks, bands)`: usa **`|ev_pct|`**; bandas default `[(0,5), (5,10), (10,20), (20,100)]` em %.

**Camada 2 — Relatório batch (`deterministic_audit.py`):**

- `generate_deterministic_audit_report(batch_summary, league_metrics)` devolve dict alinhado a **`BatchAuditModelEvaluation`** (Next: `api.ts`), incluindo `ai_self_evaluation` estático (“deterministico — sem LLM”) para não quebrar o painel.
- **`overall_assessment`:** `CRITICO` se `avg_brier > 0.28` ou `safe_acc < 40` ou `avg_lambda_err > 1.5`; senão `NECESSITA_AJUSTE` se `avg_brier > 0.24` ou `safe_acc < 50` ou `avg_lambda_err > 1.0` ou `overall_acc < 45`; senão `SATISFATORIO`.
- **`lambda_evaluation`:** status OK / ALTO / CRITICO por faixas de `avg_lambda_err`; `direction` OVER/UNDER só quando `league_metrics[*].lambda_errors_detail` existir (estrutura consumida por `deterministic_audit`; o cron atual popula `lambda_errors` escalar — até estender o payload, `direction` pode ficar `UNKNOWN`).
- **`threshold_evaluation`:** SAFE OK se `>= 55%`, NEUTRO OK se `>= 45%`.
- **`market_biases`:** parse de `market_accuracy_text` (linhas `- MERCADO: x/y (z%)`); bias se `N >= 5` e acurácia `< 40%`.
- **`recommended_corrections` / `model_update_recommendation`:** regras determinísticas + confiança por tamanho de amostra (`overall_total`).
- **Per-league em `overall_notes`:** Brier médio por liga; Log-Loss por liga com `ou_predictions` e `len >= MIN_N_LOG_LOSS`.

**Camada 3 — Flag cron (`cron_handler.py`):**

- `USE_DETERMINISTIC_AUDIT = True` → chama `generate_deterministic_audit_report`; `False` mantém Mistral.
- Lista `ou_predictions` no loop (`prob` O/U 2.5, `outcome` 0/1); espelho em `league_metrics[][ou_predictions]`.
- `batch_summary["log_loss"] = compute_log_loss(ou_predictions)` antes do relatório.

**Camada 4 — Audit por jogo (`ai_analysis.py`):**

- `USE_DETERMINISTIC_MATCH_AUDIT = True` → `_validate_match_deterministic(match_data)` sem Mistral.
- **1X2:** soma prob ~100 — `WARN` se desvio `> 3`, `FAIL` se `> 5`.
- **λ:** `FAIL` fora `[0.3, 4.5]`, `WARN` fora `[0.5, 4.0]`.
- **Over 2.5 / BTTS:** `WARN` se fora `[5, 95]` (percentagem).
- Resposta: `status` PASS/WARN/FAIL, `checks`, `corrections` (lista, pode vazia), `audit_confidence` fixo 90, `audit_type` deterministic.

**Camada 5 — Testes (`tests/unit/test_metrics_079.py`):**

- 7 testes: Sharpe (positivo com mix win/loss; insuficiente N), bandas EV, log loss, forma do relatório determinístico, caso CRITICO, validação prob sum.
- Suíte unitária: 80 passando com `--ignore=tests/unit/test_util_service.py` (falha pré-existente de import pandas no ambiente).

### Verificação pós-implantação

- `python -m pytest tests/unit/test_metrics_079.py -v -o addopts=` (pytest.ini pode injetar `--cov` sem plugin instalado).
- Build Next.js (`frontend/next`) sem alterações de contrato — mesmo shape do relatório.
- Deploy Lambda `sportsbank-pro-backend` + `GET /health` → `{"status":"ok"}`.

### Lição aprendida

1. LLM não deve substituir validações numéricas reprodutíveis — regras + testes cobrem regressões e eliminam custo de API nestes caminhos.
2. Flags `USE_DETERMINISTIC_AUDIT` e `USE_DETERMINISTIC_MATCH_AUDIT` permitem rollback imediato para Mistral.
3. Antes de duplicar métricas, reutilizar `backtesting.py` (`compute_log_loss`, `compute_calibration_bins`, constantes MIN_N).

---

## 080 — Rename Classifications + Tooltips + Glossary (frontend-only)

**Data:** 2026-03-24
**Commit:** `fc9f00c`
**Arquivos afetados:** `frontend/next/src/lib/classifications.ts` (NEW), `frontend/next/src/lib/glossary.ts` (NEW), `frontend/next/src/components/ClassificationBadge.tsx` (NEW), `frontend/next/src/components/Glossary.tsx` (NEW), `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`, `frontend/next/src/app/dashboard/page.tsx`, `backend/services/deterministic_audit.py`, `tests/unit/test_classifications_080.py` (NEW)
**Severidade:** Média
**Status:** Implementado
**Relacionado:** #079 (textos amigáveis no `deterministic_audit` alinhados ao mapeamento de UI)
**Roadmap:** **BLOCO 3** — rótulos de classificação para o utilizador, tooltips e glossário; consolidado no commit `fc9f00c` (nomenclatura interna do roadmap; o **BLOCO 2** de métricas/audit determinístico corresponde à REGRAS **#079**).

### Problema identificado

Classification badges (SAFE, NEUTRO_QUALIFICADO, NEUTRO, NO_BET) usavam nomes técnicos internos que não comunicam valor ao utilizador final.

### Causa raiz

Os nomes de classificação foram criados como enum técnico do backend e propagados diretamente para o frontend sem tradução para linguagem amigável.

### Correções aplicadas

**Camada 1 — Mapeamento de display (`classifications.ts`):**
- `CLASSIFICATION_DISPLAY`: SAFE → ALTA CONFIANÇA, NEUTRO_QUALIFICADO → VALOR DETECTADO, NEUTRO → INFORMATIVO, NO_BET → BLOQUEADO
- `getClassificationDisplay()` com fallback para NEUTRO
- Cores: VALOR DETECTADO gold (#ffd700), INFORMATIVO cinza (#9ca3af)

**Camada 2 — Badge com tooltip (`ClassificationBadge.tsx`):**
- Componente reutilizável; tooltip ao hover (delay 300 ms)
- Tooltip com rótulo + descrição da classificação
- CSS: `.classification-badge`, `.classification-tooltip`, animação fade-in

**Camada 3 — `MatchDetailCard.tsx`:**
- Badge de classificação via `<ClassificationBadge>`
- Sinal de referência de mercado com `getClassificationDisplay()` no texto
- Glossário inline atualizado (ALTA CONFIANÇA, VALOR DETECTADO, INFORMATIVO)

**Camada 4 — Glossário (`glossary.ts` + `Glossary.tsx`):**
- 20+ termos em 4 categorias (classificações, métricas, mercados, modelo)
- Filtro por categoria e busca textual
- Acesso: Ferramentas → Glossário no dashboard

**Camada 5 — Nomes amigáveis no audit (`deterministic_audit.py`):**
- `DISPLAY_NAMES` + `_display_name()` para strings de notas (ex.: accuracy)
- Campos estruturais (`safe_status`, parâmetros de threshold) mantêm nomes internos

**Sem alteração:** enum do backend, parâmetros de calibração na DB, `cron_handler`, testes existentes (nomes internos preservados).

### Verificação


- `pytest tests/unit/test_classifications_080.py -v -o addopts=` — 4 testes OK (sessão referida)
- `npm run build` em `frontend/next` — build OK

### Lição aprendida

1. Renomear UI deve ser **frontend-only** — enum e DB intactos evitam quebrar dezenas de testes e logs.
2. Mapeamento centralizado (`classifications.ts`) permite ajustar rótulos num único sítio.
3. Tooltips explicam jargão sem poluir o layout.

**Registo documentação:** entrada **#080** (**BLOCO 3**); commit **`fc9f00c`** em `main`.

---

## 081 — Corners Engine v2: melhorias cirúrgicas (NB2, barra 3 zonas, API)

**Data:** 2026-03-24
**Commit:** `8104d99`
**Arquivos afetados:** `backend/modeling/corners/champion_selector.py`, `backend/services/fixtures_service.py`, `frontend/next/src/components/CornerProgressBar.tsx`, `frontend/next/src/styles/match-detail-card.css`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/components/MatchDetailCard.tsx`, `tests/unit/test_corners_081.py` (novo)
**Severidade:** Média
**Status:** Implementado
**Relacionado:** #033 (Corners Engine v2 bidirecional); o motor v2 já estava ativo — #081 não “ativa” o framework, apenas refina selector, UI e payload da API.

### Problema identificado

1. O champion selector não privilegiava o **Negative Binomial (NB2)** quando adequado estatisticamente (escanteios com overdispersion: variância > média).
2. A **CornerProgressBar** era binária (verde/vermelho), sem zona intermédia de proximidade à meta.
3. Projeções do motor v2 (total FT, 1H, 2H, modelo, qualidade, governança, recomendação) eram calculadas internamente mas **não serializadas** na resposta da API de fixtures.

### Causa raiz

1. Tiebreaker do selector baseado só em composite score, sem preferência explícita a NB2 quando quase empatado com o melhor modelo.
2. Lógica `isGood` binária no componente React da barra de escanteios.
3. `predict_corners()` integrado no fluxo de mercados (`ev_classification` / pipeline) sem campo dedicado no `record` exposto ao cliente.

### Correções aplicadas

**Camada 1 — NB2 preference (`champion_selector.py`):**
- Constante `NB2_PREFERENCE_THRESHOLD = 0.02`.
- Após ordenar modelos elegíveis: se o campeão não é `negative_binomial`, NB2 é elegível e `(nb2_score - champion_score) / champion_score <= 0.02`, troca para NB2 e `selection_method = "composite_score_nb2_preference"`.

**Camada 2 — Barra 3 zonas (`CornerProgressBar.tsx` + `match-detail-card.css`):**
- `getBarState(direction, ratio)` → estados `hit` | `warning` | `normal` | `danger` (Over: ratio ≥1 hit, ≥0.85 warning; Under: ratio >1 danger, ≥0.85 warning).
- Classes `.cpb-fill--normal` (teal), `.cpb-fill--warning` (amber), badges espelhados.

**Camada 3 — API `cornerPredictions` (`fixtures_service.py`):**
- Após `record["mercados"]`, `try/except` chama `predict_corners(...)` com os mesmos insumos do pipeline e preenche `record["cornerPredictions"]` com FT/1H/2H, `modelSource`, `dataQualityTier`, `governanceState`, linha/side/edge recomendados, `noBet`, `engineVersion`.

**Camada 4 — Frontend (`leagues.ts` + `MatchDetailCard.tsx`):**
- Tipo `CornerPredictions` e `cornerPredictions?` em `Match`.
- Card “Motor v2 Escanteios” no separador escanteios (projeção FT em destaque, badge de tier, recomendação com edge quando aplicável).

**Camada 5 — Testes (`test_corners_081.py`):**
- 4 testes: NB2 preferido dentro do limiar; sem swap com gap grande; NB2 já campeão; NB2 inelegível (ex.: ECE alto).

### Verificação

- `pytest tests/unit/test_corners_081.py -v -o addopts=` — 4/4 OK.
- `npm run build` em `frontend/next` — OK.

### Lição aprendida

O framework corners v2 já estava operacional; a evolução correta foi **cirúrgica** (tiebreaker, visual, exposição de dados), não assumir componentes “dormentes”. Investigar o código e o fluxo antes de reescrever.

**Registo documentação:** entrada **#081**; commit **`8104d99`** em `main`.

---

## 082 — Mistral redefinida: papel exclusivamente narrativo

**Data:** 2026-03-24
**Commit:** `83365e0`
**Arquivos afetados:** `backend/ai/mistral_auditor.py` (removido), `backend/ai/prompt_templates.py`, `backend/cron_handler.py`, `backend/routes/ai_analysis.py`, `backend/main.py`, `backend/services/fixtures_service.py`, `CLAUDE.md` (raiz + `sportsbankzu-pro/`), `tests/unit/test_mistral_contract_082.py` (novo)
**Severidade:** Alta
**Status:** Implementado
**Relacionado:** #079 (audit batch/jogo determinístico), #001–#002 (defesas anti-alucinação na análise narrativa), #052–#078 (calibração per-league e pipeline numérico)

### Problema identificado

Depois do #079, as auditorias passaram a ser determinísticas, mas **código morto** da Mistral (flags `USE_DETERMINISTIC_AUDIT` / `USE_DETERMINISTIC_MATCH_AUDIT` e ramos `else`) mantinha caminhos legados. Além disso, `_apply_confidence_adjustment()` em `fixtures_service.py` permitia **alterar probabilidades 1X2** com base em `ContextAnalyzer` / Mistral — violação da separação **cálculo vs narrativa**; o pipeline Dixon-Coles + calibração (#052–#078) é a fonte única de probabilidades.

### Causa raiz

Migração #079 incompleta: flags como ponte sem remoção do legado. O “Gap 3” (`confidence_adjustment`) era tratado como enriquecimento de contexto, mas na prática era **mutação numérica** de `stats`.

### Correções aplicadas

**Camada 1 — Remoção de código morto:**
- Removido `backend/ai/mistral_auditor.py` (~280 linhas).
- `cron_handler.py`: removidos import `MistralAuditor`, flag `USE_DETERMINISTIC_AUDIT` e ramo Mistral; avaliação do modelo é **sempre** `generate_deterministic_audit_report(...)`.
- `ai_analysis.py`: removidos `USE_DETERMINISTIC_MATCH_AUDIT` e ramo Mistral; `POST .../audit` usa **sempre** `_validate_match_deterministic`.
- `main.py`: removidos import/instância `MistralAuditor`, modelo `MatchAuditRequest` e rota `POST /ai/audit-match`.

**Camada 2 — Fim de cálculo via Mistral no pipeline de fixtures:**
- Removida `_apply_confidence_adjustment()` e o bloco que chamava `ContextAnalyzer().analyze_match_context` para aplicar ajuste às probs 1X2 (apenas em jogos não finalizados).

**Camada 3 — Prompts mortos (`prompt_templates.py`):**
- Ficheiro reduzido a `PromptTemplates.report_generation_prompt()` (relatório narrativo).
- Removidos prompts de contexto, auditoria de cálculo, auditoria pós-jogo, batch evaluation, mercados 1X2/O-U/BTTS/corners, `_build_feedback_block`, `_format_market_reference_stats`.

**Camada 4 — Contrato em documentação:**
- Secção **CONTRATO DA MISTRAL AI (#082)** nos dois `CLAUDE.md`: Mistral só narrativa (`mistral_analysis.py` v3.0); não calcula, não audita, não corrige λ/thresholds; fallback sem API não altera o pipeline.

**Camada 5 — Testes (`test_mistral_contract_082.py`):**
- 5 testes de contrato (ausência de `MistralAuditor`, imports limpos, `prompt_templates` só com relatório, etc., conforme implementação).

### Verificação

- `pytest tests/unit/test_mistral_contract_082.py -v -o addopts=` — 5/5 OK.
- Regressão rápida: `pytest tests/ -k "classifications or metrics_079 or corners_081" -o addopts= --ignore=tests/unit/test_util_service.py` — 15/15 OK (ambiente com falha pré-existente em `test_util_service` / pandas pode ignorar esse módulo).
- `npm run build` em `frontend/next` — OK.
- Imports: `backend.routes.ai_analysis`, `cron_handler` carregam sem erro.

### Lição aprendida

Feature flags servem para **transição**, não como destino final: após decidir determinístico para auditoria, remover legado Mistral. Qualquer função que **renormalize ou desvie probabilidades** conta como camada de cálculo — não como “só contexto LLM”.

**Registo documentação:** entrada **#082**; commit **`83365e0`** em `main`.

---

## 083 — Post-Match Diagnostic Engine + version bump V3.7 → V4.0

**Data:** 2026-03-24
**Commit:** `48e10d9`
**Arquivos afetados:** `backend/services/post_match_diagnostic.py` (novo), `backend/config/version.py` (novo), `backend/cron_handler.py`, `backend/routes/ai_analysis.py`, `backend/main.py`, `backend/audit.py`, `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/styles/match-detail-card.css`, `frontend/next/package.json`, `tests/unit/test_diagnostic_083.py` (novo)
**Severidade:** Alta
**Status:** Implementado
**Relacionado:** #079 (audit batch), #082 (Mistral só narrativa), #080 (rótulos de classificação), #081 (escanteios API/UI)
**Roadmap:** **BLOCO 6** — motor de diagnóstico pós-jogo + alinhamento de versão e UX; commit `48e10d9`.

### Problema identificado

1. O sistema media acerto/Brier/erro de λ, mas **não decompunha** a causa dos erros nem agregava **padrões** (λ alto/baixo, ρ, overconfidence, cantos, etc.).
2. A versão exposta continuava **V3.7** apesar da evolução acumulada (Dixon-Coles, calibração per-league, audit determinístico, corners v2, UI #080, contrato Mistral #082).
3. **UI:** lateral e lista ainda mostravam `SAFE` em texto cru; barra de escanteios não ocupava a largura útil; tooltip podia ser cortado; ausência de mensagem clara quando a análise narrativa falha; tab de versão não refletia jogo ao vivo.

### Causa raiz

Faltava uma camada **analítica** entre métricas agregadas e ação humana; a versão e os rótulos estavam **dispersos** em ficheiros sem fonte única; alguns componentes não tinham sido atualizados no mesmo passo que o mapeamento `#080`.

### Correções aplicadas

**Camada 1 — `post_match_diagnostic.py` (Python, contrato #082):**
- `decompose_error()` — causas prováveis por pick (ex.: LAMBDA_OVER/UNDER, RHO_INSUFFICIENT, ODDS_VALUE_TRAP, CALIBRATION_DRIFT, CORNER_MODEL_ERROR, EARLY_SEASON, LOW_SAMPLE, MARKET_MISMATCH, UNKNOWN).
- `detect_patterns()` — padrões agregados (ex.: SYSTEMATIC_LAMBDA_OVER/UNDER, DRAW_UNDERESTIMATION, OVERCONFIDENCE, CORNER_SYSTEMATIC_ERROR, HIGH_ODDS_VALUE_TRAP).
- `generate_diagnostic_narrative()` — base determinística; enriquecimento Mistral **opcional** e só como texto.
- `run_post_match_diagnostic()` — orquestra os três blocos.

**Camada 2 — `cron_handler.py`:**
- Acumula `all_evaluated_picks` no loop de mercados (match, liga, mercado, acerto, prob, ev, odd, λ, cantos projetados, etc.).
- Após `model_evaluation`, chama `run_post_match_diagnostic(..., use_mistral_narrative=bool(MISTRAL_API_KEY))`.
- Inclui `diagnostic` no dict guardado via `log_audit_result` / resultado do cron.

**Camada 3 — API `GET /api/ai/diagnostic/latest` (`ai_analysis.py`):**
- Lê o audit recente (ex.: 7 dias, limite 1) e devolve o campo `diagnostic` quando existir.

**Camada 4 — Versão V4.0:**
- `backend/config/version.py`: `APP_VERSION = "pro V4.0"`.
- `audit.py`: default de versão a partir de `version.py` (continua override por `SPORTSBANK_VERSION`).
- `main.py`: `FastAPI(..., version="4.0.0")`.
- Frontend: `VERSION_FALLBACK`, default do `MatchDetailCard`, `package.json` → `4.0.0`.

**Camada 5 — Ajustes visuais / UX:**
- `dashboard/page.tsx`: badges da lista e da lateral com `getClassificationDisplay()` (cor + rótulo amigável).
- `match-detail-card.css`: `.cpb-root` largura total; `overflow: visible` na lista de prognósticos (tooltips).
- `MatchDetailCard.tsx`: aviso quando análise narrativa indisponível (`confidence === 0` + resumo com “indispon”); tab com indicador **Ao vivo** para `match.status === "live"` (em jogos não live mantém badge de versão).

**Camada 6 — Testes `test_diagnostic_083.py`:**
- 7 testes (decomposição, padrões, narrativa, orquestração, conforme implementação).

### Verificação

- `pytest tests/unit/test_diagnostic_083.py -v -o addopts=` — 7/7 OK.
- Regressão: `pytest tests/ -k "diagnostic or metrics_079 or classifications or corners_081 or mistral_contract" -o addopts= --ignore=tests/unit/test_util_service.py` — 29/29 OK (sessão referida; ignorar módulo com pandas quebrado).
- `npm run build` em `frontend/next` — OK.
- Imports: `ai_analysis`, `cron_handler`; `APP_VERSION` → `pro V4.0`.

### Lição aprendida

1. Métricas sem **causa** não orientam calibração; padrões exigem **N mínimo** para não confundir ruído com regime.
2. Após #082, LLM no diagnóstico só como **reformulador narrativo**, nunca como fonte de conclusões numéricas.
3. **Uma constante** de versão evita drift backend/frontend.

**Registo documentação:** entrada **#083** (**BLOCO 6**); commit **`48e10d9`** em `main`.

---

## 084 — Integrar métricas pendentes no cron loop + baseline de odds

**Data:** 2026-03-25
**Commit:** `614fcc9`
**Arquivos afetados:** `backend/services/backtesting.py`, `backend/cron_handler.py`, `backend/services/deterministic_audit.py`, `backend/services/post_match_diagnostic.py`, `tests/unit/test_metrics_integration_084.py` (novo)
**Severidade:** Alta (sem integração, métricas derivadas do #079 não saem do `backtesting.py` para o audit em produção)
**Status:** Implementado
**Relacionado:** #079 (funções de métricas no `backtesting.py`), #083 (`batch_summary` → diagnóstico; passagem explícita para `run_post_match_diagnostic`)
**Roadmap / prompt:** hotfix métricas no cron — integração pós-Blocos 1–6; mensagem de commit: `feat: integrate all metrics into cron loop + odds baseline comparison (#084)`.

### Problema identificado

1. Quatro funções já existentes no #079 (`compute_sharpe_ratio`, `compute_hit_rate_by_ev_band`, `compute_calibration_bins`, `compute_roi`) **não eram chamadas** no loop de audit do `cron_handler`: o batch acumulava picks mas **não** materializava Sharpe, faixas de EV, calibração agregada nem ROI no `batch_summary`.
2. Faltava **baseline** explícito: Brier do modelo vs probabilidade implícita da casa (`1/odd`, sem normalização de overround na comparação implementada), para saber se o modelo **melhora** a casa em precisão probabilística.
3. O diagnóstico (#083) precisava usar o mesmo `batch_summary` para sinalizar quando o modelo perde para a casa (padrão agregado, não só erro por pick).

### Causa raiz

Implementação #079 ficou em biblioteca isolada; o cron só computava métricas já ligadas ao fluxo (ex.: log-loss em O/U) e **não** encadeava o restante. Não havia contrato de “métricas do batch” unificado até o relatório determinístico e o motor de padrões.

### Correções aplicadas

**Camada 1 — `compute_implied_odds_brier()` (`backtesting.py`):**
- Entrada: lista de `{"odd", "prob" (0–1 ou % tratado no cron), "outcome": bool}`.
- Saída: `brier_implied`, `brier_model`, `model_vs_house` (positivo = modelo pior que implícita), `model_beats_house`, `n`.

**Camada 2 — `cron_handler.py` (após `batch_summary["log_loss"]`):**
- **Sharpe:** `all_evaluated_picks` → `{"odd", "outcome", "stake": 1.0}`.
- **Hit rate por banda de EV:** `ev` + `acertou`.
- **Calibração / ECE:** `compute_calibration_bins` recebe `list[dict]` com chaves `prob` e `outcome` (assinatura real do módulo — **não** duas listas paralelas). ECE derivado dos bins: média ponderada de `|predicted_avg - actual_avg|`. Se `n < 30`, `ece: null` e nota de amostra insuficiente.
- **ROI:** `compute_roi` — usar **`roi_pct`** no relatório (o retorno não expõe campo `roi` simples).
- **Baseline:** `odds_baseline` = `compute_implied_odds_brier(baseline_picks)` a partir de `all_evaluated_picks`.
- `run_post_match_diagnostic(..., batch_summary=batch_summary)` para alimentar padrões agregados.

**Camada 3 — `deterministic_audit.py`:**
- `overall_notes` passa a incluir Sharpe (com `n_bets`), ROI (`roi_pct`), ECE + rótulo “bem calibrado / recalibrar”, linha modelo vs casa (Brier + diff), resumo de hit rate por EV (só bandas com `total >= 5`).

**Camada 4 — `post_match_diagnostic.py`:**
- `detect_patterns(..., batch_summary=...)` e `run_post_match_diagnostic(..., batch_summary=...)`.
- Padrão **`MODEL_WORSE_THAN_HOUSE`**: `model_vs_house > 0.01`, severidade HIGH.
- **Correção de fluxo:** nos early returns (`diagnostics` vazio ou **zero erros por pick**), o código **ainda** avalia `batch_summary.odds_baseline` — antes o padrão contra a casa nunca aparecia quando não havia decomposições de erro.

**Camada 5 — Testes `test_metrics_integration_084.py`:**
- 6 testes (baseline, sharpe, calibração, ROI, padrão `MODEL_WORSE_THAN_HOUSE` com `batch_summary`, etc.).

### Verificação

- `pytest tests/unit/test_metrics_integration_084.py -v -o addopts=` — **6/6** OK.
- Regressão: `pytest tests/ -k "diagnostic or metrics_079 or metrics_integration or mistral_contract" -v -o addopts=` — **27/27** OK (sessão referida).
- Imports: `cron_handler`, `backtesting`, `deterministic_audit`, diagnóstico — OK.

### Lição aprendida

1. Funções em `services/` sem chamada no **caminho feliz** do cron/deploy = métricas “fantasma”.
2. Ao integrar, validar **assinaturas reais** (`compute_calibration_bins`, `compute_roi`) em vez de suposições do prompt.
3. Padrões agregados (baseline) são **independentes** da lista de erros por pick: early return não pode saltar essa lógica.

**Registo documentação:** entrada **#084**; commit **`614fcc9`** em `main` (`48e10d9..614fcc9`).

---

## 085 — Ativação de cartões como mercado de picks + correção de divergência de classificação

**Data:** 2026-03-25
**Commit:** `fe553b1`
**Arquivos afetados:** `backend/modeling/cards_engine.py` (novo), `backend/services/ev_classification.py`, `backend/services/fixtures_service.py`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/app/dashboard/page.tsx`, `tests/unit/test_cards_085.py` (novo)
**Severidade:** Média (novo mercado, isolado dos demais) + Alta (bug de UI: mesmo pick com rótulos diferentes)
**Status:** Implementado
**Relacionado:** #080 (campo `classification` vs `status` legacy / rótulos amigáveis), #056 (calibração de cartões per-league no `league_calibrator`), #084 (métricas no cron — picks de cartões passam a entrar no batch quando elegíveis)
**Roadmap / prompt:** `PROMPT-ATIVAR-CARTOES-085.md` — ativar picks + alinhar consumo de `classification`; mensagem de commit: `feat: activate cards as pick market + fix classification divergence (#085)`.

### Problema identificado

1. **Cartões:** havia `cardsAVG` (FootyStats), `cards_multiplier` calibrado e separador **Cartões** no detalhe do jogo, mas **não** havia geração de mercados de cartão em `ev_classification` nem `cardsPredictions` na resposta da API — calibração e UI órfãs do pipeline de picks.
2. **Classificação:** o mesmo pick mostrava rótulos distintos na lista lateral vs `MatchDetailCard` (ex.: INFORMATIVO vs VALOR DETECTADO). `_legacy_status()` rebaixa `NEUTRO_QUALIFICADO` → `NEUTRO` em `pred.status`; `pred.classification` conserva o valor canónico. O dashboard usava só `pred.status` em três pontos; o card de detalhe já usava `pred.classification || pred.status`.

### Causa raiz

1. Motor Poisson de cartões e ligação a `classify_market` / odds nunca tinham sido implementados apesar da calibradora.
2. Migração **parcial** de `status` → `classification`: `MatchDetailCard` atualizado, `dashboard/page.tsx` não.

### Correções aplicadas

**Camada 1 — `backend/modeling/cards_engine.py`:**
- `predict_cards()`, `CARD_LINES` (2.5, 3.5, 4.5, 5.5), `DEFAULT_CARDS_LAMBDA`.
- λ em cascata: média equipas → média liga → default (~4.0); `cards_multiplier` por liga aplicado ao λ.
- Probabilidades Over/Under complementares por linha (Poisson).

**Camada 2 — `ev_classification.py` (após bloco de cantos):**
- Para cada linha: se `over_prob` / `under_prob` > 0.10, `calibrate_prob(...)` + `MarketOutput` (`market_type="Cards"`, `classify_market`).
- Odds: `cards_over_{line}` / `cards_under_{line}` com fallback `over{X}Cards` / `under{X}Cards` (X sem ponto decimal).
- `data_quality_score` ligeiramente reduzido (×0.85); `source_flags` inclui `cards_poisson`.
- Falhas isoladas em `try/except` com log debug.

**Camada 3 — `fixtures_service.py`:**
- Enriquecimento `record["cardsPredictions"]`: `projectedTotalCards`, `cardsLambda`, `cardsMultiplier`, `modelSource`, `lines` com `prob_pct` exposto como `prob` no JSON.

**Camada 4 — Frontend:**
- `CardsPredictions` em `leagues.ts` e no tipo local **`MatchDetailData`** em `MatchDetailCard.tsx` (o build falhou até o segundo existir — o card não usa só o tipo `Match` de `leagues.ts`).
- Tab Cartões: bloco laranja `#ff6b35` com total projetado e Over 2.5–5.5 com cores por faixa de probabilidade.

**Camada 5 — `dashboard/page.tsx` (três alinhamentos):**
- `safePicks`: `(p.classification || p.status) === "SAFE"`.
- Badges da sidebar: `getClassificationDisplay(p.classification || p.status)`.
- Lista de prognósticos: classe CSS e rótulo a partir de `pred.classification || pred.status`.

**Camada 6 — `tests/unit/test_cards_085.py`:**
- 7 testes (básico, complementaridade, fallback, multiplier, linhas, λ alto/baixo, etc., conforme ficheiro).

### Verificação

- `pytest tests/unit/test_cards_085.py -v -o addopts=` — **7/7** OK.
- Regressão: `pytest tests/ -k "cards or diagnostic or metrics or mistral_contract or classifications" -v -o addopts=` — **39/39** OK (sessão referida).
- `npm run build` em `frontend/next` — OK (após tipo local em `MatchDetailCard`).
- Imports: `cards_engine`, `ev_classification` — OK.

### Lição aprendida

1. Poisson é base razoável para cartões; o mesmo padrão (motor + `ev_classification` + API + tab) escala para novos mercados discretos.
2. **`classification` e `status` legacy** devem ser consumidos com a **mesma regra** em todos os componentes: `classification || status`, senão a UI contradiz o pipeline.
3. Tipos duplicados (`Match` global vs `MatchDetailData` local) exigem atualização **nos dois** quando novos campos chegam ao card.
4. Calibração sem chamada no motor de mercados é infraestrutura morta até ser ligada.

**Registo documentação:** entrada **#085**; commit **`fe553b1`** em `main` (`614fcc9..fe553b1`).

---

## 085b — Avaliação pós-jogo de cartões + motor NB2 (v2) + verificação de deploy

**Data:** 2026-03-25
**Commit:** `2674c8e`
**Arquivos afetados:** `backend/modeling/cards_engine.py`, `backend/routes/ai_analysis.py`, `backend/cron_handler.py`, `backend/services/ev_classification.py`, `backend/services/fixtures_service.py`, `frontend/next/src/lib/localAudit.ts`, `frontend/next/src/lib/leagues.ts`, `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/components/MatchDetailCard.tsx`, `CLAUDE.md` (cópia em `sportsbankzu-pro/`)
**Severidade:** Crítica (padrão #006: picks de cartão sem ramo de avaliação → feedback de auditoria destrutivo; cron com ImportError)
**Status:** Implementado
**Relacionado:** #006 (escanteios “ERROU” por falta de avaliação), #020 (`normalizeMatch` omitiu stats), #085 (cartões como mercado v1 Poisson)
**Roadmap / prompt:** `PROMPT-DEPLOY-085B.md`; mensagem de commit: `feat: NB2 cards engine v2 + post-match eval + deploy hotfix (#085b)` (12 ficheiros no push referido).

### Problema identificado

1. **#085** ativou cartões como picks mas faltava **avaliação pós-jogo** em backend e frontend (equivalente ao que #006 documentou para cantos).
2. `cron_handler` importava `_evaluate_pick_deterministic` e `_get_all_finished_matches` de `ai_analysis.py`, mas as funções **não existiam** → **ImportError** no audit por cron (só manifesto no EventBridge/Lambda).
3. `normalizeMatch` não copiava amarelos/vermelhos reais para `stats` → audit local e UI sem `totalCards` fiável (eco do #020 para cantos).
4. Quarto ponto de UI: `getHighlightReason` ainda filtrava `p.status === "SAFE"` em vez de `p.classification || p.status`.

### Causa raiz

Mercado novo sem checklist de “ponta a ponta”: engine + classificação + API + `evaluatePick` (TS) + avaliador determinístico (Python) + `normalizeMatch` + tipos. Imports do cron **não** são validados no CI se o módulo não for importado nos testes.

### Correções aplicadas (estado no commit `2674c8e`)

**Camada 1 — `cards_engine.py` NB2 (v2, pré-#086):**
- Evolução Poisson (#085) → **NB2** (`scipy.stats.nbinom`) com sobredispersão quando há variância.
- Split λ casa/fora, ajuste por faltas vs média da liga, fator de árbitro, fator de perfil disciplinar da liga; fallback Poisson se scipy indisponível.
- **Nota:** em **#086** removeram-se `foul_adjustment` e `league_discipline_factor` do motor (dupla contagem com `cardsPerMatch`); ver entrada **#086** para o modelo v3 e Layer scipy.

**Camada 2 — `ai_analysis.py`:**
- `_evaluate_pick_deterministic(pick, actual_result)` — 1X2, O/U golos, BTTS, DC, escanteios, **cartões** (threshold no texto do mercado).
- `_get_all_finished_matches(date_filter, before_time_brt)` — jogos finalizados por liga.

**Camada 3 — `cron_handler.py`:**
- `total_cards` = amarelos + vermelhos (stats ou aliases `home_team_yellow_cards`, etc.).
- `actual_result["total_cards"]`; log `[audit] ... cards hy=...` quando existem mercados com `CART`/`CARD`.

**Camada 4 — `localAudit.ts`:**
- `evaluatePick(..., totalCards?)`; ramo CART/CARD (Over `total > threshold`, Under `total < threshold`).
- `MatchActualResult.totalCards`; duplas e `runLocalAudit` passam `totalCards`.

**Camada 5 — `dashboard/page.tsx`:**
- `normalizeMatch`: `homeYellowCards`, `awayYellowCards`, `homeRedCards`, `awayRedCards` (API/stats + aliases Footy).
- **Highlight / SAFE:** `safePreds` com `(p.classification || p.status) === "SAFE"` (alinhado ao #085).

**Camada 6 — Tipos (`leagues.ts`, `MatchDetailCard.tsx`):**
- Stats reais de cartões; `CardsPredictions` com campos NB2 (`cardsLambdaHome/Away`, `overdispersion`, `adjustments`, …).

**Camada 7 — `ev_classification.py`:**
- `data_quality_score` adaptativo: NB2 ×0.75, fallback Poisson ×0.65; `source_flags` com `cards_{model_source}` e (até #086) flags de ajuste.

**Camada 8 — `fixtures_service.py`:**
- `cardsPredictions` com campos NB2 adicionais.

**Camada 9 — `CLAUDE.md`:**
- Mercados: "Cards (0.5-5.5)" → **"Cards Over/Under (2.5-5.5)"**.

### Verificação (sessão pós-implementação #085b, antes de #086)

- `pytest tests/unit/test_cards_085b.py -v -o addopts=` — **10/10** OK.
- `pytest tests/unit/test_cards_085.py` + `test_metrics_integration_084.py` — OK.
- `pytest tests/ -k "classifications or corners_081" -o addopts=` — **8/8** OK (`--ignore` em módulos quebrados se necessário).
- `npm run build` em `frontend/next` — OK.
- Deploy checklist referido: bug “or com 0” nos quatro campos de cartões, `safe_prob` cartões, Lambda **Active** / **Successful**, `GET /health` → `{"status":"ok"}`.

### Lição aprendida

1. Checklist #006 alargado: **backend determinístico + cron + normalizeMatch + localAudit + tipos** para cada mercado novo.
2. Imports usados só no **cron/Lambda** devem ser cobertos por teste de import ou job de smoke.
3. Covariáveis que duplicam sinal já presente em `cardsPerMatch` inflacionam λ — corrigido formalmente em **#086** (mesmo princípio do #053).

**Registo documentação:** entrada **#085b**; commit **`2674c8e`** (`fe553b1..2674c8e`).

---

## 086 — Dupla contagem no λ de cartões (Dixon-Coles relativo) + Lambda Layer scipy

**Data:** 2026-03-25
**Commit:** `a111c7f`
**Arquivos afetados:** `backend/modeling/cards_engine.py`, `backend/services/ev_classification.py`, `CLAUDE.md` (`sportsbankzu-pro/` e, quando sincronizado, raiz do monorepo), `tests/unit/test_cards_085b.py`
**Severidade:** Crítica (λ de cartões inflado ~+22% a +114% em produção; NB2 inoperante sem scipy no runtime)
**Status:** Implementado
**Relacionado:** #053 (double-counting em λ de golos), #085b (NB2 v2 que introduziu multiplicadores redundantes), #078v (bug `or` com zero nos contadores de cartões no audit — corrigido no âmbito do deploy #085b)

### Problema identificado

1. **Dupla contagem:** `homeCardsPerMatch` / médias observadas já embutem contexto de liga e ritmo; `foul_adjustment` e `league_discipline_factor` em cima multiplicavam o efeito. Ex.: Argentina λ **11.4** vs média de liga **5.33** (~+114%).
2. **scipy ausente no pacote Lambda** → NB2 caía em `poisson_fallback` (`modelSource` não nb2).

### Causa raiz

Mesmo padrão do #053: usar multiplicadores “explicativos” em cima de estatísticas que **já** condicionam o mesmo sinal.

### Correções aplicadas

**Camada 1 — `cards_engine.py` v3 (força relativa estilo Dixon-Coles):**
- λ agregado a partir de `league_avg/2 × home_relative + league_avg/2 × away_relative` com `home_relative = homeCardsPerMatch / leagueAvgCards` (e análogo visitante).
- Removidos: `_compute_foul_adjustment`, `_compute_league_discipline_factor`, `HOME_CARD_SHARE`, `AWAY_CARD_SHARE`, `FOUL_CARD_ELASTICITY`.
- **Mantido:** `referee_factor` como único ajuste externo explícito legítimo.

**Camada 2 — Lambda Layer (scipy):**
- Layer publicada (ex.: `scipy-numpy-layer:2`, scipy para Python 3.11), anexada a `sportsbank-pro-backend`.
- **numpy** fora da Layer quando já vai no ZIP de deploy (evitar duplicação e limite de 250 MB descomprimido).
- Produção: `modelSource=nb2` com Layer ativa.

**Camada 3 — `ev_classification.py`:**
- Remoção do `source_flags` `foul_adjusted` (ajuste de faltas deixou de existir no motor).

**Camada 4 — Testes `test_cards_085b.py`:**
- Novos: `test_relative_strength_lambda`, `test_league_avg_bounds_lambda`, `test_no_foul_or_league_adjustment`, `test_referee_is_only_external_adjustment`, `test_average_team_produces_league_avg_lambda`.
- Removidos/substituídos testes que dependiam de foul/split antigo ou de `adjustments` completos obsoletos.

**Camada 5 — Documentação `CLAUDE.md`:**
- Secção da Layer scipy: ARN, recriação e notas de deploy.

### Verificação

- `pytest tests/unit/test_cards_085b.py -v -o addopts=` — **11/11** OK.
- Regressão: `pytest tests/ -k "cards or diagnostic or metrics or classifications" -v -o addopts=` — **45/45** OK (sessão referida; ignorar módulos quebrados se aplicável).
- `npm run build` em `frontend/next` — OK.
- `scripts/deploy_lambda.py` — deploy OK; `aws lambda get-function-configuration` → **State=Active**, **LastUpdateStatus=Successful**.
- `GET https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/health` → `{"status":"ok"}`.

### Validação em produção (amostra)

- **Argentina** (Riestra vs San Lorenzo): λ **11.4 → 3.8** (≈0,71× média liga 5.33); `modelSource=nb2`.
- **Colômbia** (América de Cali vs Llaneros): λ **7,454 → 2,9** (≈0,47× média); `modelSource=nb2`.
- `adjustments` sem `foul_adjustment` / `league_discipline_factor`; apenas `referee_factor` quando aplicável.

### Lição aprendida

1. Dados observacionais por jogo (`cardsPerMatch`, golos, etc.) já “preçam” o ambiente; multiplicadores paralelos geram **inflação de λ** se não forem independentes.
2. **Lambda Layers** para dependências pesadas (scipy ~tens MB) — separação do ZIP de aplicação e reutilização.
3. Não duplicar **numpy** na Layer se já está no artefacto de deploy.

**Registo documentação:** entrada **#086**; commit **`a111c7f`** (`2674c8e..a111c7f`).

---

## 087 — Standings indisponivel para ligas calendario-ano (Colombia, Argentina)

**Data:** 2026-03-25
**Arquivos afetados:** `backend/routes/live.py`, `backend/routes/fixtures.py`, `frontend/next/src/app/api/standings/route.ts`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

"Ver classificacao" mostrava "Classificacao indisponivel" para Campeonato Colombiano e Argentina Primera Division.

### Causa raiz

Duas falhas independentes:

1. **Season errado no `/live/standings`**: `_current_season()` retornava `2025` para todas as ligas (regra europeia: mes < 7 → ano anterior). Ligas calendario-ano (Argentina, Colombia, Brasil) precisam de `2026` em marco 2026. A funcao `get_season_for_league()` em `leagues_config.py` ja tratava isso corretamente mas nao era usada.

2. **Null safety no `/standings` (FootyStats)**: `data.get("league_table", [])` retornava `None` quando a API FootyStats retornava `league_table: null` (valor explicito), causando `'NoneType' object is not iterable`.

3. **Frontend proxy errado**: `/api/standings/route.ts` chamava `/standings` (FootyStats, quebrado) em vez de `/live/standings` (API-Football, funcional).

### Correções aplicadas

1. **live.py** — `season_year = season or get_season_for_league(league)` em vez de `_current_season()`. Agora usa CALENDAR_YEAR_LEAGUES para resolver a season correta.
2. **fixtures.py** — `table = (raw.get("league_table") or [])` — guard contra `null` explicito da API.
3. **standings/route.ts** — Proxy agora chama `/live/standings` como fonte primaria com normalizacao de campos (`rank→position`, `teamName→name`). Fallback para FootyStats `/standings`.

### Lição aprendida

Funcoes de resolucao de season devem ser centralizadas (`get_season_for_league`) e nao reimplementadas em cada modulo. Ligas calendario-ano devem SEMPRE ser testadas separadamente de ligas europeias.

---

## 088 — Highlight de odds vinculado ao prognostico do pipeline

**Data:** 2026-03-25
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/styles/scoretabs-dashboard.css`
**Severidade:** Media
**Status:** Implementado

### Problema identificado

Na aba esquerda do dashboard, o highlight verde nas odds estava incorreto:
- **1X2**: destacava a menor odd (favorito matematico), nao o prognostico do pipeline.
- **Dupla Chance, BTTS, Gols**: nenhum highlight.
- **Gols**: Over 2.5 hardcoded como highlight em todos os jogos.

### Causa raiz

Funcao `getLowestOddIndex()` usava logica de menor odd (favorito implicito), ignorando completamente os prognosticos do pipeline (`match.predictions`).

### Correções aplicadas

1. **Removida** `getLowestOddIndex()` e substituida por `getHighlightedOddPositions()` — retorna `Set<string>` com as posicoes a destacar baseadas em `match.predictions[].mercado`.
2. **1X2**: highlight so quando predictions contem "1X2 Home/Draw/Away" ou "1"/"X"/"2".
3. **Dupla Chance**: highlight em "1X"/"12"/"X2" quando predictions contem "DC 1X/12/X2".
4. **BTTS**: highlight em "Sim"/"Nao" quando predictions contem "BTTS Sim/Nao".
5. **Gols**: removido hardcoded Over 2.5; agora highlight so na linha do prediction (ex: "O 2.5" para "Over 2.5 gols").
6. **Cards/Corners**: sem alteracao (mostram stats, nao odds).
7. **CSS**: adicionado indicador verde (`::after` dot) na odd com prognostico.

### Lição aprendida

Highlight visual deve refletir a saida do pipeline, nao heuristicas simples (menor odd). Jogos sem prediction para o mercado ativo nao devem ter nenhuma odd destacada.

---

## 089 — Cron auditava jogos da data errada + cartões rejeitados pelo validador

**Data:** 2026-03-26
**Arquivos afetados:** `backend/main.py`, `backend/routes/ai_analysis.py`, `backend/modeling/market_validator.py`, `tests/unit/test_cron_date_range_089.py` (novo)
**Severidade:** Crítica (cron produzia diagnósticos sobre jogos errados — TODAS as ligas afetadas)
**Status:** Corrigido
**Relacionado:** #083 (diagnostic engine), #084 (métricas no cron), #085/#085b (cartões)

### Problema identificado

1. **Cron de diagnóstico pós-jogo auditava jogos da data errada.** Evidência do CloudWatch (2026-03-25T23:00 UTC): `audited_matches: 4`, `overall_accuracy: 0.0`, `model_assessment: "CRITICO"` — mas 0 erros no diagnóstico. Ligas Premier League e Championship retornavam `0 records for date '2026-03-24'`.
2. **Mercados de cartões rejeitados como inválidos** por `MERCADOS_VALIDOS` em toda execução do cron: `Prognóstico INVÁLIDO: ['Cartoes Under 2.5', 'Cartoes Under 3.5', ...]`.
3. **Regra EventBridge `today_audit` não criada** — handler em `cron_handler.py:42-44` suportava a ação mas nenhuma regra EventBridge existia para dispará-la. Jogos terminados 21:00-23:59 BRT nunca eram auditados.

### Causa raiz

**Bug 1 — `date_range()` não parseava datas ISO:**
- `_get_all_finished_matches("yesterday")` computava `dates = ["2026-03-24"]` (data UTC)
- Passava `"2026-03-24"` para `_process_single_league` → `build_records_from_matches(date_filter="2026-03-24")`
- `date_range("2026-03-24")` NÃO reconhecia datas ISO → caía no default (janela 7 dias a partir de hoje)
- Jogos de ontem ficavam FORA dessa janela → filtrados → 0 records para maioria das ligas
- Ligas que retornavam records tinham jogos de temporadas novas caindo acidentalmente na janela errada

**Bug 2 — `_get_all_finished_matches` usava UTC em vez de BRT:**
- `_dt.utcnow() - 1 day` pode divergir do "ontem BRT" entre 21:00-23:59 BRT (00:00-02:59 UTC)
- Exemplo: às 23:00 UTC March 25, `utcnow - 1 day` = March 24 UTC, mas "ontem BRT" = March 24 BRT (correto neste caso, mas diverge em edge cases perto da meia-noite UTC)

**Bug 3 — Cartões não adicionados ao `MERCADOS_VALIDOS`:**
- #085 ativou cartões em `ev_classification.py` gerando mercados `"Cartoes Over/Under X.5"`
- Mas `market_validator.py:MERCADOS_VALIDOS` não foi atualizado → todos rejeitados pelo validador

### Correções aplicadas

**Camada 1 — `date_range()` em `main.py`:**
- Adicionado parsing de datas ISO (`%Y-%m-%d`) antes do fallback 7-day
- A data é interpretada como dia calendário BRT (00:00-23:59 BRT) convertido para UTC
- Keywords "today", "yesterday", "tomorrow" continuam funcionando normalmente

**Camada 2 — `_get_all_finished_matches()` em `ai_analysis.py`:**
- Trocou `_dt.utcnow()` por `_dt.now(BRT)` para computar datas no calendário BRT
- Garante que "yesterday" = ontem BRT, não ontem UTC

**Camada 3 — `MERCADOS_VALIDOS` em `market_validator.py`:**
- Adicionados 8 mercados de cartões: `Cartoes Over/Under 2.5/3.5/4.5/5.5`

**Camada 4 — Regra EventBridge `today_audit`:**
- Documentada a criação necessária: `cron(45 2 * * ? *)` = 02:45 UTC = 23:45 BRT
- Input: `{"source": "eventbridge", "action": "today_audit"}`
- Captura jogos que terminam 20:00-23:45 BRT no mesmo dia

**Camada 5 — Testes (`test_cron_date_range_089.py`):**
- 7 testes: parsing ISO, regressão "yesterday"/"today", fallback default, inclusão de jogo 22:00 BRT, exclusão de jogo 00:30 BRT (dia seguinte), cartões no validador

### Verificação

- `pytest tests/unit/test_cron_date_range_089.py -v` — 7/7 OK
- Regressão: `pytest tests/ -k "diagnostic or metrics or cards or classifications or mistral_contract"` — 50/50 OK
- CloudWatch: próxima execução do cron (23:00 UTC) deve retornar jogos corretos para o dia

### Lição aprendida

1. `date_range()` era usado em dois contextos com expectativas diferentes: frontend (keywords "today"/"yesterday") e cron (datas ISO computadas). O gap entre os dois nunca foi testado.
2. Checklist #085 faltou atualizar `MERCADOS_VALIDOS` — mesmo padrão do #006 (mercado ativado sem checklist completo).
3. Regras EventBridge documentadas em comentários de código (`cron(45 2 * * ? *)`) mas nunca criadas → precisam de checklist de infra separado.

---

## 089b — Dedup de linhas de cartões (4 linhas → 1 melhor)

**Data:** 2026-03-26
**Arquivos afetados:** `backend/services/market_service.py`, `backend/services/correlation_matrix.py`
**Severidade:** Média (UI poluída com 4 linhas redundantes de cartões INFORMATIVO)
**Status:** Corrigido
**Relacionado:** #089 (cartões adicionados ao validador), #085 (cartões como mercado)

### Problema identificado

Após #089 adicionar cartões ao `MERCADOS_VALIDOS`, a UI passou a mostrar 4 linhas de cartões por jogo (Cartoes Under 2.5, 3.5, 4.5, 5.5 todas como INFORMATIVO), poluindo a lista de picks. Antes do #089, eram rejeitadas pelo validador e não apareciam.

### Causa raiz

`_dedup_market_groups()` em `market_service.py` deduplicava Over/Under gols (1 melhor) e Escanteios (1 melhor), mas **não incluía cartões** — caiam no bucket `others` sem dedup. Igualmente, `correlation_matrix.py` não tinha correlações para linhas aninhadas de cartões.

### Correções aplicadas

**Camada 1 — `_dedup_market_groups()` (`market_service.py`):**
- Adicionados buckets `cards_over` e `cards_under`
- Detecção: `"Cartoes Over"` e `"Cartoes Under"` no nome do mercado
- `_pick_best()` seleciona 1 melhor por direção (mesma lógica de Escanteios e gols)

**Camada 2 — `correlation_matrix.py`:**
- Correlações altas (0.85-0.92) para linhas aninhadas de cartões Over e Under
- Pares redundantes adicionados ao `REDUNDANT_PAIRS`

### Verificação

- Teste local: 5 picks (4 cartões + 1 Under gols) → 2 picks (1 cartão melhor + 1 Under gols)
- Regressão: 51/51 testes OK
- Deploy Lambda OK

### Lição aprendida

Checklist para mercado novo: engine + classificação + validador + **dedup** + correlações + avaliação + tipos frontend. #085 faltou validador (#089), e #089 faltou dedup (#089b).

---

## 090 — Fallback Mistral retornava HTTP 400 + standings highlight quebrado

**Data:** 2026-03-26
**Arquivos afetados:** `backend/routes/ai_analysis.py`, `backend/services/mistral_analysis.py`, `frontend/next/src/components/MatchDetailCard.tsx`
**Severidade:** Média
**Status:** Corrigido
**Relacionado:** #082 (contrato Mistral narrativa-only), #083 (aviso "indispon" no frontend), #087 (standings revert)

### Problema identificado

1. **Aba Análise AI (Mistral)** mostrava erro na montagem do texto. Quando `MISTRAL_API_KEY` ausente no Lambda, `MistralAnalysisService.__init__` lançava `ValueError` → rota retornava HTTP 400 → frontend recebia erro → aba ficava vazia (nem fallback, nem conteúdo).
2. **Standings "Ver Classificação"**: times do jogo não eram destacados. Comparação de nomes era case-sensitive (`===`) e falhava quando FootyStats/API-Football retornava nome com capitalização diferente (ex: "argentinos juniors" vs "Argentinos Juniors"). Além disso, cor era laranja em vez de cinza claro.

### Causa raiz

1. O endpoint `GET /api/ai/match/{id}/analysis` capturava `ValueError` como HTTP 400 (erro do cliente), mas a ausência de API key é um problema de infraestrutura — deveria retornar um fallback gracioso, não um erro.
2. `_get_fallback_analysis()` era método de instância, mas sem instância disponível quando `__init__` falha. Não havia caminho para gerar fallback sem API key.
3. Comparação de nomes no standings usava `===` (case-sensitive, sem fuzzy matching).

### Correções aplicadas

**Camada 1 — `ai_analysis.py`:**
- `ValueError` e `Exception` agora retornam `_get_fallback_static()` em vez de HTTP 400/500.
- Log: `logger.warning` para fallback, `logger.error` para exceções gerais.

**Camada 2 — `mistral_analysis.py`:**
- Novo `@staticmethod _get_fallback_static()` + `_build_fallback()` — gera AIAnalysisResponse com `confidence=0`, `resumo_analitico` contendo "indisponível" (para que frontend detecte corretamente), e 5 `key_points` informativos.
- Fallback funciona sem instanciar o service (sem depender de API key).

**Camada 3 — `MatchDetailCard.tsx` (standings):**
- Comparação de nomes agora case-insensitive + fuzzy (`.toLowerCase()` + `.includes()` bidirecional).
- Cor de highlight: `rgba(200,200,200,0.18)` (cinza claro) em vez de `rgba(255,165,0,0.15)` (laranja).

### Verificação

- Backend: `GET /api/ai/match/test-123/analysis/legacy` → `confidence=0, summary="Análise indisponível..."`, 5 key_points — OK
- Frontend build: `npm run build` OK
- Regressão: 51/51 testes OK

### Lição aprendida

1. Endpoints que dependem de serviços externos (API key, rede) devem SEMPRE retornar fallback, nunca HTTP 4xx/5xx para o frontend. O contrato #082 (Mistral só narrativa) implica que ausência de Mistral NÃO pode quebrar a UI.
2. Comparação de nomes entre fontes diferentes (FootyStats, API-Football, frontend) deve ser case-insensitive + fuzzy, não exata.

---

## 090b — Análise AI Mistral não carregava automaticamente ao selecionar jogo

**Data:** 2026-03-27
**Arquivos afetados:** `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Média (funcionalidade existia mas exigia clique manual em "Regenerar")
**Status:** Corrigido
**Relacionado:** #082 (contrato Mistral narrativa-only), #083 (aviso indisponível), #090 (fallback gracioso)

### Problema identificado

Ao selecionar um jogo no dashboard, a aba "Análise AI" mostrava "Nenhuma análise AI gerada" ou "⚠ Analise narrativa temporariamente indisponivel." O backend Mistral funcionava corretamente (confirmado via curl: `confidence: 72` com análise completa), mas o frontend NÃO buscava automaticamente.

### Causa raiz

O `useEffect` que observa `selectedMatch` apenas resetava `aiAnalysis = null` ao trocar de jogo, mas NÃO disparava o fetch. O `handleGenerateAiAnalysis` só era chamado via clique manual no botão "Regenerar".

### Correções aplicadas

- `dashboard/page.tsx`: adicionado auto-fetch de `getAiMatchAnalysis()` no `useEffect` quando `selectedMatch` muda. A análise é buscada em background com `setAiLoading(true)` e trata erros silenciosamente (AI é opcional).

### Verificação

- `npm run build` OK
- Endpoint real testado: `colombian-primera-a-Rionegro Águilas-Alianza Petrolera-1774645200.0` → confidence=72, 5 key_points, summary e recommendation corretos

### Lição aprendida

Funcionalidades on-demand (clique manual) degradam a experiência. Auto-fetch com fallback gracioso é preferível.

---

## 091 — Match ID com alias não-canônico impedia análise Mistral para 17 ligas

**Data:** 2026-03-27
**Arquivos afetados:** `backend/routes/fixtures.py`
**Severidade:** Crítica (análise AI falhava silenciosamente para TODAS as ligas com alias frontend ≠ backend)
**Status:** Corrigido
**Relacionado:** #082 (contrato Mistral), #090 (fallback gracioso mascarou o erro real)

### Problema identificado

Análise AI Mistral retornava "indisponível" para o jogo Rionegro Águilas vs Alianza Petrolera (liga colombiana). Investigação revelou que o backend Lambda retorna `confidence=75` com análise completa — o proxy Vercel também funciona. O erro estava nos match IDs gerados com o league ID do frontend (`colombia-primera-a`) em vez do ID canônico do backend (`colombian-primera-a`).

### Causa raiz

**`_process_single_league()` em `fixtures.py`** resolvia o alias via `get_league_config(lid)` para buscar dados, mas passava o `lid` **original** (do frontend) para `build_records_from_matches(league_id=lid)`. O match ID gerado ficava `colombia-primera-a-Rionegro...` em vez de `colombian-primera-a-Rionegro...`.

Quando o frontend chamava `/api/ai/match/{matchId}/analysis`, `_extract_league_id()` procurava o prefixo em `LEAGUES_CONFIG` — não encontrava `colombia-primera-a` (só `colombian-primera-a`) → ValueError → fallback `confidence=0`.

**17 ligas afetadas** (todas com alias frontend ≠ backend): La Liga, Serie A/B, Bundesliga/2.Bundesliga, Ligue 1, Brasileirão A/B, Eredivisie, Primeira Liga, Premiership, Superliga, Super Lig, League One, MLS, Colombiana, Liga MX.

### Evidência

Logs Vercel: `/api/ai/match/colombia-primera-a-Rion...` (frontend) vs `/api/ai/match/colombian-primera-a-Rio...` (curl direto). Ambos retornavam 200 mas o primeiro com `confidence=0` (fallback) e o segundo com `confidence=75` (análise real).

### Correções aplicadas

**`fixtures.py` (`_process_single_league`):** resolve `LEAGUE_ID_ALIASES` ANTES de gerar match IDs. `lid = LEAGUE_ID_ALIASES.get(lid, lid)` logo após `get_league_config()`.

### Verificação

- `GET /fixtures?leagues=colombia-primera-a` → match ID agora `colombian-primera-a-Rionegro...`
- `GET /api/ai/match/colombian-primera-a-Rionegro.../analysis` via proxy → `confidence=75`
- Regressão: 51/51 testes OK
- Deploy Lambda OK

### Lição aprendida

1. **#090 mascarou este bug:** ao trocar HTTP 400 por fallback gracioso, o match ID errado parou de gerar erro visível — passou a retornar `confidence=0` silenciosamente. Defesa em profundidade é necessária, mas NÃO como substituto de resolver a causa raiz.
2. IDs gerados em caminhos com aliases devem SEMPRE usar o ID canônico. A resolução de alias deve ser o PRIMEIRO passo, não apenas no `get_league_config`.
3. O padrão se repetia para 17 ligas — não testar apenas o caso reportado.

---

## 092 — _extract_date_from_id usava UTC em vez de BRT (mesma classe de bug #089)

**Data:** 2026-03-27
**Arquivos afetados:** `backend/routes/ai_analysis.py`
**Severidade:** Alta (jogos 21:00-23:59 BRT sem análise Mistral — timestamp cai no dia UTC seguinte)
**Status:** Corrigido
**Relacionado:** #089 (date_range UTC→BRT), #091 (alias no match ID)

### Problema identificado

Atlético Bucaramanga vs Santa Fe (22:10 BRT / 01:10 UTC) retornava fallback `confidence=0`. Rionegro Águilas (18:00 BRT / 21:00 UTC) funcionava normalmente com `confidence=75`.

### Causa raiz

`_extract_date_from_id()` usava `datetime.fromtimestamp(ts)` que no Lambda (UTC) retornava a data UTC. Um jogo às 22:10 BRT = 01:10 UTC dia seguinte → `date_str = "2026-03-28"`. Mas `date_range("2026-03-28")` espera calendário BRT (03:00 UTC - 02:59 UTC+1). O jogo às 01:10 UTC ficava ANTES do range → match not found → fallback.

Mesma classe de bug do #089 (`_get_all_finished_matches` usava UTC em vez de BRT).

### Correções aplicadas

`_extract_date_from_id()`: `datetime.fromtimestamp(ts, tz=BRT)` em vez de `datetime.fromtimestamp(ts)`. A data extraída é agora o dia BRT, alinhado com `date_range()`.

### Verificação

- Backend `/analysis`: `confidence=75` para Bucaramanga (antes: fallback)
- Proxy Vercel: `confidence=75`, `summary_len=269`
- Deploy Lambda OK

### Lição aprendida

Terceira ocorrência do bug UTC→BRT (#089, #091 parcial, #092). Toda conversão `timestamp → date string` no backend deve usar BRT. Adicionar checklist: grep por `fromtimestamp` sem `tz=BRT` e `utcnow()` antes de cada deploy.

---

## 093 — Mistral recomendava mercados sem odd disponível

**Data:** 2026-03-28
**Arquivos afetados:** `backend/services/mistral_analysis.py`
**Severidade:** Média (recomendação confusa para o usuário, não afeta pipeline de cálculo)
**Status:** Corrigido
**Relacionado:** #001, #002 (defesas anti-alucinação), #082 (contrato narrativo)

### Problema identificado

Mistral recomendou "Double Chance 1X (odd não disponível, mas probabilidade de 77.7%)" para Bucaramanga vs Santa Fe. Sem odd, não há como calcular EV. A recomendação contradiz o pipeline que selecionou Under 2.5 (EV +8.4%) como pick de valor.

### Causa raiz

Prompt v3.0 não restringia recomendação a mercados com odd real. A instrução dizia "Mercado com maior EV+" mas não proibia mercados sem odd. Sem validação pós-processamento para detectar "odd não disponível".

### Correções aplicadas

**Camada 1 — Instrução no prompt (preventiva):**
- Adicionada REGRA DE RECOMENDAÇÃO: "DEVE ser de um mercado com odd REAL (NÃO N/A)"
- "NUNCA diga 'odd não disponível mas probabilidade de X%'"
- "Se nenhum mercado tem odd, escreva 'Sem recomendação — odds indisponíveis'"

**Camada 2 — `_validate_recommendation()` (pós-processamento corretivo):**
- Detecta padrões: "odd não disponível", "sem odd", "odd n/a", etc.
- Substitui por mensagem que redireciona ao pipeline Dixon-Coles

**Camada 3 — 4 camadas de defesa anti-alucinação mantidas (#001, #002):**
- Prompt expandido com 12+ mercados (intacto)
- Instrução "NAO invente odds" (intacto)
- Validação de recomendação (NOVA — camada 5)
- Sanitização de key_points (intacto)

### Verificação

- `pytest tests/unit/test_mistral_contract_082.py` — 5/5 OK
- `_validate_recommendation("DC 1X (odd não disponível...")` → "Sem recomendação adicional..."
- Deploy Lambda OK, `/health` → ok

### Lição aprendida

Alta probabilidade sem odd NÃO indica valor. Recomendações narrativas devem ser restritas a mercados com odd real para não confundir o usuário que segue o pipeline de valor.

---

## 094 — Bankroll editável + Stake sugerido Quarter Kelly no dashboard

**Data:** 2026-03-28
**Arquivos afetados:** `frontend/next/src/components/BankrollCard.tsx` (novo), `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/app/dashboard/page.tsx`, `frontend/next/src/styles/match-detail-card.css`
**Severidade:** Baixa (feature nova, não altera pipeline de cálculo)
**Status:** Implementado
**Relacionado:** #028 (bankroll_engine Quarter Kelly original)

### Funcionalidade adicionada

1. **BankrollCard** acima do MatchDetailCard: campo R$ editável, presets (50/100/250/500/1000), resumo (stake total, EV médio, % comprometido), disclaimer.
2. **Stake sugerido por pick**: bloco abaixo de cada prediction mostrando "Quarter Kelly • X.XX% do bankroll → R$ Y.YY". Picks sem EV positivo: "Sem EV positivo — stake não recomendado".
3. **Persistência**: bankroll salvo em `localStorage` entre sessões.
4. **Cálculo 100% client-side**: `calcQuarterKelly(prob, odd, bankroll)` usando `calibrated_probability` e `book_odd` que já vêm da API. Cap 5% por pick.

### Implementação

- `BankrollCard.tsx`: componente + função exportada `calcQuarterKelly`
- `dashboard/page.tsx`: state `bankroll`, `handleBankrollChange` com localStorage, BankrollCard renderizado acima do MatchDetailCard, prop `bankroll` passada ao card
- `MatchDetailCard.tsx`: prop `bankroll`, bloco de stake dentro do loop de predictions
- `match-detail-card.css`: classes `.bkr-*` e `.stake-*`

### Lição aprendida

O pipeline v2 já retornava `ev`, `calibrated_probability`, `book_odd` por pick — o cálculo de stake não precisou de alteração no backend. Features de apresentação devem consumir dados existentes sempre que possível.

---

## 095 — Integração de odds reais de cartões (API-Football v3)

**Data:** 2026-03-29
**Arquivos afetados:** `backend/services/api_football_client.py`, `backend/services/fixtures_service.py`
**Severidade:** Média (cartões passam a ter EV real quando odd disponível)
**Status:** Implementado
**Relacionado:** #056 (cards per-league), #085 (cards as pick market), #028 (ev_classification)

### Funcionalidade adicionada

1. `extract_best_odds()` agora extrai odds de cartões (Total Bookings Over/Under 2.5-5.5) com prioridade Bet365 > Pinnacle > 1xBet
2. `fixtures_service.py` enriquece `odds_dict` com `cards_over_2.5`, `cards_under_2.5`, etc.
3. `ev_classification` já buscava `cards_over_{line}` — agora encontra odds reais quando disponíveis
4. Picks de cartões com odd real são classificados normalmente (VALOR_DETECTADO se EV > threshold)
5. Sem odd real: mantém INFORMATIVO com Fair value (fallback intacto)

### Lição aprendida

Pick sem odd real do bookmaker NÃO deveria parecer apostável. Integrar odds reais de TODOS os mercados que o pipeline gera é pré-requisito para classificação correta.

---

## 096 — Mistral recomendava mercado OPOSTO ao pick VALOR DETECTADO do pipeline

**Data:** 2026-03-29
**Arquivos afetados:** `backend/services/mistral_analysis.py`, `backend/routes/ai_analysis.py`
**Severidade:** Crítica (recomendação contradiz pipeline — usuário pode apostar no mercado errado)
**Status:** Corrigido
**Relacionado:** #082 (contrato narrativo), #093 (recomendação sem odd), #001-#002 (anti-alucinação)

### Problema identificado

Millonarios vs Fortaleza CEIF: pipeline selecionou Under 2.5 (prob 66%, EV +17.4%), Mistral recomendou Over 2.5 (prob 58%, fonte FootyStats). Probabilidades somam 124% — impossível para mercados complementares.

### Causa raiz

1. **Mistral não recebia os picks do pipeline** — não sabia que Under 2.5 era VALOR DETECTADO
2. **`prob_over_25` no prompt vinha do FootyStats** (`over_25_percentage_pre_match`, m��dia da liga) quando disponível, não do Poisson/Dixon-Coles específico do jogo
3. Sem picks de referência, a Mistral calculava sua própria recomendação com dados de fonte diferente
4. **Bug adicional (fix 2):** `_map_record_to_v3()` buscava `record.get("predictions")` mas os picks v2 estão em `record["mercados"]` — `pipeline_picks` era sempre lista vazia

### Correções aplicadas

**Camada 1 — Picks do pipeline passados ao prompt (`ai_analysis.py`):**
- `_map_record_to_v3()` extrai picks de `record["mercados"]` (não `predictions`) com EV+ e inclui em `pipeline_picks`
- `analyze_match()` recebe e propaga `pipeline_picks`

**Camada 2 — Seção PICKS + REGRA DE ALINHAMENTO no prompt (`mistral_analysis.py`):**
- Bloco "PICKS SELECIONADOS PELO PIPELINE (Dixon-Coles)" listando mercado, prob, odd, EV, classificação
- Instrução: "Sua recomendação DEVE ser UM DOS picks acima. NUNCA contradiga a direção Over/Under."

**Camada 3 — `_validate_recommendation_vs_pipeline()` pós-processamento:**
- Detecta se a recomendação contém a direção OPOSTA de um pick (Under→Over, Over→Under) com a mesma linha
- Se contradiz, substitui por "Recomendação alinhada ao pipeline: {pick} (odd X, EV Y%)"

### Verificação

- Anti-contradição: Under 2.5 no pipeline + Over 2.5 na Mistral → BLOQUEADO
- Mesmo sentido: Under 2.5 no pipeline + Under 2.5 na Mistral → MANTIDO
- Escanteios: Under 8.5 no pipeline + Over 8.5 na Mistral → BLOQUEADO
- Testes: 5/5 contrato Mistral + 18/18 regressão OK
- Deploy Lambda OK, health OK

### Lição aprendida

1. A Mistral NUNCA deve usar probabilidades de fonte diferente do pipeline. O contrato #082 (narrativa-only) exige que as probabilidades venham do Dixon-Coles.
2. Sem acesso aos picks, a Mistral não tem como saber o que o pipeline selecionou — fornecer os picks no prompt é a defesa primária.
3. Validação pós-processamento é a defesa secundária — mesmo com instrução no prompt, LLMs podem ignorá-la.
4. Agora são 6 camadas de defesa: #001 (prompt expandido), #002 (instrução anti-invenção), #093 (sem odd → bloqueado), #096 camada prompt (picks no prompt), #096 camada validação (anti-contradição).

---

## 097 — Standings highlight falhava para times com nome abreviado

**Data:** 2026-03-29
**Arquivos afetados:** `frontend/next/src/components/MatchDetailCard.tsx`
**Severidade:** Média (UX — time não destacado na classificação)
**Status:** Corrigido
**Relacionado:** #090 (highlight case-insensitive + cinza), #087 (standings revert)

### Problema identificado

Atlético PR vs Botafogo: tabela "Ver Classificação" destacava apenas Botafogo. "Atlético PR" (nome do jogo) não casava com "Atletico Paranaense" (nome na tabela).

### Causa raiz

O fix #090 usava `.toLowerCase()` + `.includes()` bidirecional, que funciona para diferenças de capitalização mas NÃO para abreviações ("PR" vs "Paranaense"), hifens, acentos ou sufixos de estado/tipo.

### Correções aplicadas

`_normalizeTeamName()` + `_teamsMatch()`: remove acentos (NFD), hifens, sufixos de estado (PR, RJ, SP, MG...), sufixos de tipo (FC, SC, EC...), normaliza "Red Bull"→"RB", compara primeira palavra significativa (≥3 chars) como fallback.

### Verificação

8/8 testes: Atlético PR↔Atletico Paranaense, Chapecoense-sc↔Chapecoense, RB Bragantino↔Red Bull Bragantino, Atletico-MG↔Atlético Mineiro, Vasco DA Gama↔Vasco da Gama, Botafogo↔Botafogo — todos match. Santos↔Internacional, Flamengo↔Fluminense — corretamente não match.

### Lição aprendida

Nomes de times brasileiros são particularmente problemáticos — abreviações por estado, variações com/sem acento, hifens. Normalização robusta (accents + suffixes + first-word fallback) é essencial para qualquer comparação entre fontes diferentes.

---

## 098 — Safety: validação de mercados complementares (hard constraint)

**Data:** 2026-03-30
**Arquivos afetados:** `backend/services/safety_validation.py` (novo), `backend/services/fixtures_service.py`
**Severidade:** Crítica (previne exibição de probabilidades impossíveis)
**Status:** Implementado
**Relacionado:** #096 (Mistral contradiz pipeline)

### Funcionalidade adicionada

`validar_mercados_complementares()` em `safety_validation.py` — detecta pares complementares (Under/Over gols, escanteios, cartões + BTTS Sim/Não) com probabilidades somando >105% e bloqueia o pick com menor EV. Integrado em `fixtures_service.py` após `selecionar_mercados_v2()` e antes de `record["mercados"]`.

### Detecção

`_sao_complementares()` usa regex para detectar pares Over/Under na mesma linha (2.5, 3.5, etc.) e BTTS Sim/Não. Tolerância de 5% para arredondamentos (105% → OK, 106% → bloqueio).

### Verificação

5/5 testes: complementares 124% → bloqueado, complementares 100% → mantidos, tolerância 105% → mantidos, não-complementares → mantidos, detecção de pares → OK. 42/42 regressão OK.

### Lição aprendida

Validação de integridade matemática deve existir INDEPENDENTE de defesas no prompt da Mistral. É a última linha de defesa — mesmo que todas as 6 camadas anti-alucinação falhem, esta validação impede que dados impossíveis cheguem ao usuário.

---

## 099 — Safety: filtro de ações de auditoria por regras operacionais

**Data:** 2026-03-30
**Arquivos afetados:** `backend/services/safety_validation.py`, `backend/services/deterministic_audit.py`
**Severidade:** Alta (previne recomendações que violam regras operacionais)
**Status:** Implementado
**Relacionado:** #082 (contrato Mistral), #079 (amostras mínimas), #042 (backtesting), #043 (circuit breaker)

### Funcionalidade adicionada

1. `filtrar_acoes_por_regras()` — filtra `recommended_actions` (strings) contra padrões proibidos
2. `filtrar_corrections_por_regras()` — filtra `recommended_corrections` (objetos com parameter/reason)
3. Integrado em `deterministic_audit.py` após `_compute_corrections()` e `_compute_model_recommendation()`
4. Ações bloqueadas retornadas em `blocked_corrections` para transparência

### Regras implementadas

| Padrão | Regra | Motivo |
|--------|-------|--------|
| `lambda.*multiplier` | #082 | Mistral não ajusta parâmetros |
| `calibration.*retrain` (N<20) | #079 | MIN_N_BRIER=20 jogos |
| `ajustar.*threshold` | #042 | Requer backtesting |
| `safe.*recalibr` | #043 | Circuit breaker ativo |

### Verificação

6/6 testes: lambda bloqueado, calibration N=6 bloqueado, calibration N=25 permitido, threshold bloqueado, ação genérica permitida, correction object bloqueado. 32/32 regressão OK.

### Lição aprendida

O sistema de auditoria deve respeitar suas próprias regras. Recomendar ações proibidas é violação de compliance — o filtro é a última camada de defesa entre o gerador de ações e o usuário.

---

## 100 — Predictability: ECE (Expected Calibration Error) por faixa de probabilidade

**Data:** 2026-03-30
**Arquivos afetados:** `backend/services/backtesting.py`, `backend/cron_handler.py`
**Severidade:** Baixa (feature informativa, não altera pipeline)
**Status:** Implementado
**Relacionado:** #079 (amostras mínimas), #084 (métricas no cron)

### Funcionalidade adicionada

`compute_ece()` em `backtesting.py` — divide picks em 5 faixas de probabilidade e compara prob prevista vs acurácia real. Retorna `ece_global` (0=perfeito), `faixas` com status (calibrado/overconfident/underconfident), `aviso` quando N<20.

Integrado no `cron_handler.py` como `batch_summary["calibration"]["ece_faixas"]`, substituindo o cálculo inline anterior.

### Verificação

- Modelo calibrado (pred 65%, real 67%) → ECE 0.017, status "calibrado"
- Modelo overconfident (pred 80%, real 33%) → ECE 0.467, status "overconfident"
- 47/47 regressão OK

### Lição aprendida

Brier Score global é insuficiente para diagnosticar calibração. ECE por faixa revela se o modelo é overconfident em certas faixas e underconfident em outras.

---

## 101 — Dashboard de Confiabilidade (Admin) — 4 dimensoes Princeton

**Data:** 2026-03-30
**Arquivos afetados:** `backend/routes/health.py`, `backend/services/reliability_tracker.py` (novo), `backend/services/safety_validation.py`, `frontend/next/src/app/admin/reliability/page.tsx` (novo), `frontend/next/src/app/api/admin/reliability/route.ts` (novo)
**Severidade:** Baixa (feature informativa, diferencial competitivo)
**Status:** Implementado
**Relacionado:** #098 (safety complementares), #099 (filtro auditoria), #100 (ECE calibracao)

### Funcionalidade adicionada

1. **ReliabilityTracker** — singleton que conta eventos de safety/robustness em tempo real (reset no cold start)
2. **`GET /health/reliability`** — endpoint que agrega metricas das 4 dimensoes Princeton
3. **Pagina `/admin/reliability`** — dashboard visual com Previsibilidade, Seguranca, Robustez, Consistencia e Defesas Ativas
4. Integracao com safety_validation.py para contar bloqueios (#098, #099)

### Verificacao

- Endpoint retorna JSON com 4 dimensoes + defesas_ativas
- Frontend build OK com rota /admin/reliability
- 28/28 regressao OK

### Licao aprendida

Metricas de confiabilidade devem ser visiveis e permanentes. Um dashboard dedicado incentiva monitoramento continuo.

---

## 102 — Persistir ReliabilityTracker no PostgreSQL + integrar API clients

**Data:** 2026-03-30
**Arquivos afetados:** `backend/services/reliability_tracker.py` (reescrito), `backend/services/api_football_client.py`, `backend/services/footstats_client.py`, `backend/services/mistral_analysis.py`, `backend/services/safety_validation.py`, `backend/routes/health.py`, `backend/cron_handler.py`, `backend/main.py`
**Severidade:** Baixa (monitoramento, nao altera pipeline)
**Status:** Implementado
**Relacionado:** #101 (dashboard confiabilidade), #098 (safety), #099 (filtro auditoria)

### Funcionalidade adicionada

1. Tabela `reliability_events` no PostgreSQL (auto-criada via `_ensure_table`)
2. `track_api_call()` integrado em API-Football (`_get_sync`), FootyStats (`_request`), Mistral (`_call_mistral_api`)
3. `track_duration()` no handler Lambda principal (`main.py:handler`)
4. `track_safety()` atualizado em `safety_validation.py`
5. `get_stats(days=30)` le agregados do PostgreSQL (AVG, PERCENTILE_CONT, STDDEV)
6. `cleanup_old_events(90d)` no cron diario
7. Fallback: in-memory counters quando PostgreSQL indisponivel

### Regra critica

Monitoramento NUNCA bloqueia producao. Todo INSERT e leitura em try/except silencioso.

### Verificacao

47/47 testes regressao OK. Deploy Lambda OK. Endpoint retorna dados (acumulam com uso).

---

## 103 — Fix: barra escanteios null + stake em picks sem odd + visual INFORMATIVO

**Data:** 2026-04-01
**Arquivos afetados:** `frontend/next/src/components/MatchDetailCard.tsx`, `frontend/next/src/app/dashboard/page.tsx`
**Severidade:** Media (UX — stake falso pode induzir aposta errada)
**Status:** Corrigido
**Relacionado:** #094 (bankroll/stake), #095 (cards real odds), #068 (corners)

### Correcoes

1. **CornerProgressBar**: `currentCorners ?? 0` em vez de fallback "Aguardando dados" — mostra 0/9 no inicio do jogo live
2. **Stake**: so calcula com `book_odd` real (>1). NÃO usa `odd_minima` (fair value) como fallback. Sem odd real → "Sem odd real — stake nao calculavel"
3. **Visual**: picks sem `book_odd` com `opacity: 0.55` — visualmente subordinados aos VALOR DETECTADO
4. **BankrollCard summary**: filtra picks sem `book_odd` do calculo de stake total

### Licao aprendida

Fair value (`odd_minima`) nunca deve substituir odd real (`book_odd`) no calculo de stake. Sao metricas diferentes: fair value e informativo, odd real e apostavel.

---

## 104 — Lambdas de escanteios subestimadas (V2 misturava escala per-team com per-match)

**Data:** 2026-04-01
**Arquivos afetados:** `backend/modeling/corners/predictor.py`
**Severidade:** Critica (picks VALOR DETECTADO gerando prejuizo real — R$ 117,74)
**Status:** Corrigido
**Relacionado:** #033 (Corners Engine v2), #081 (NB2 preference)

### Problema identificado

Under escanteios >=10.5 classificados como VALOR DETECTADO com 68-70% prob, mas acumulado historico de 33% (Under 11.5) e 50% (Under 10.5). Millonarios vs Fortaleza CEIF: modelo previa lambda ~5.75 quando media real da liga era 8.93.

### Causa raiz

`_project_expected_corners()` no motor V2 misturava valores **per-team** (~4.5 corners por equipe) com valores **per-match total** (~9.0 corners por jogo) nos mesmos pesos:

```
OLD: raw = 0.10*9.0 + 0.20*4.5 + 0.15*4.3 + 0.20*4.3 + 0.15*4.5 + 0.10*9.0 + 0.10*8.8 = 5.75
```

Componentes `home_attack` (4.5) e `away_attack` (4.3) sao per-team, mas recebiam 20% de peso cada. Isso arrastava o `raw` 3+ escanteios abaixo da media real.

### Correcao

Substituidos os pesos per-team por componentes **total-scale** (`direct_estimate` = home_for + away_for, `cross_estimate`):

```
NEW: raw = 0.15*9.0 + 0.35*8.8 + 0.25*8.8 + 0.10*9.0 + 0.15*9.0 = 8.85
```

Diferenca: OLD 5.75 (3.18 abaixo) → NEW 8.85 (0.08 abaixo). Under 10.5 cai de 96.7% (falso) para 72.3% (realista).

### Verificacao

- 64/64 testes regressao OK (corners + classifications + metrics)
- Deploy Lambda OK, health OK
- Calculo simulado: lambda OLD 5.75 → NEW 8.85 ≈ league avg 8.93

### Licao aprendida

Quando um modelo usa weighted components, TODOS os componentes devem estar na mesma escala. Misturar per-team (~4.5) com per-match (~9.0) gera subestimacao sistematica.

---

## 102b — Configurar DATABASE_URL + PGHOST no Lambda (infraestrutura)

**Data:** 2026-04-02
**Arquivos afetados:** Configuracao Lambda (variaveis de ambiente)
**Severidade:** Critica (sem DATABASE_URL, #102 e #101 ficam inoperantes)
**Status:** Configurado
**Relacionado:** #102 (tracker PostgreSQL), #101 (dashboard confiabilidade)

### Problema identificado

O #102 implementou persistencia no PostgreSQL, mas DATABASE_URL nunca foi adicionada ao Lambda. Codigo caia no fallback silencioso (SQLite /tmp), perdendo dados no cold start.

### Correcao

- Senha do RDS resetada (caracteres especiais `@` nao sao permitidos pelo RDS)
- Variaveis configuradas: `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT`, `DATABASE_URL` (com `?sslmode=require`)
- Conectividade confirmada: `health/db` → `status: ok, backend: postgresql`
- Tracker funcionando: AF=100%, FS=100%, Lambda avg=4733ms

### Regra permanente

Toda nova variavel de ambiente adicionada ao codigo DEVE ser verificada no Lambda ANTES de considerar deploy concluido. Deploy de codigo sem deploy de infra e deploy incompleto.

---

<!-- Novas correções devem ser adicionadas abaixo, seguindo o mesmo formato -->

## 105 — Deflacao progressiva por banda + per-league

**Data:** 2026-04-02
**Arquivos afetados:** `backend/services/ev_classification.py`
**Severidade:** Alta (calibracao baseada em 379 picks reais)
**Status:** Implementado
**Relacionado:** #042, #043, #079, Brier #104

### Problema

Deflacao uniforme 15% (#043) insuficiente para probs altas (70-80%: gap +0.058, 80%+: gap +0.081). Brasil Serie A com Delta Brier = -0.075 (modelo pior que casa).

### Correcoes

1. `apply_probability_deflation()`: <50%->10%, 50-60%->12%, 60-70%->15%, 70-80%->20%, 80%+->25%
2. `_LEAGUE_DEFLATION`: brasileirao-serie-a=0.90, league-two=0.95
3. `_calibrate_and_deflate()` substitui `calibrate_prob()` em todos os mercados
4. Floor 5%, fator per-league minimo 0.85

### Verificacao

5/5 testes deflacao OK. 91/91 regressao OK. Deploy Lambda OK.

### Licao aprendida

Calibracao baseada em dados reais (379 picks) > heuristicas uniformes (#043).

---

