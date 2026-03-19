# Regras de Correção do Sistema — Placares ao Vivo

## Problema Original
Jogos ao vivo mostravam placar **0 - 0** mesmo quando o placar real era diferente (ex: Preston 1-3 Oxford United exibido como 0-0 aos 90').

## Causa Raiz
Três falhas em cadeia:
1. **FootyStats `todays-matches`** retorna `homeGoalCount: -1` para jogos ao vivo (dados indisponíveis)
2. **Frontend `normalizeMatch`** forçava `{home: 0, away: 0}` como default para qualquer jogo ao vivo sem score
3. **Overlay `/live-scores`** recebia `score: null` e não sobrescrevia o 0-0 fake do frontend

## Correções Aplicadas

### 1. Backend — Fallback via endpoint `match` (defesa em profundidade)
**Arquivo:** `backend/routes/fixtures.py`
- Quando `todays-matches` não tem dados de gol para um jogo ao vivo, o sistema agora faz fallback para o endpoint `match` (detalhes individuais) que retorna dados mais atualizados.
- Cache de 30s garante dados frescos sem sobrecarregar a API.

### 2. Backend — Cache reduzido para 30s
**Arquivo:** `backend/services/footstats_client.py`
- `get_live_scores()`: cache de 1 min → **30s**
- `get_match_live_details()`: cache de 1 min → **30s**

### 3. Frontend — Não defaultar 0-0 para jogos ao vivo
**Arquivo:** `frontend/next/src/app/dashboard/page.tsx`
- `normalizeMatch()`: default `{home: 0, away: 0}` agora só para jogos **finalizados** (não mais para "live")
- Jogos ao vivo sem score mostram `- : -` com animação pulsante (indicando carregamento)

### 4. Frontend — Polling mais rápido
**Arquivo:** `frontend/next/src/hooks/useLivePolling.ts`
- Polling com jogos ao vivo: 30s → **15s**
- Polling sem jogos ao vivo: 120s (mantido)

### 5. Backend — Janela de inferência de status
**Arquivo:** `backend/routes/fixtures.py`
- Janela de inferência "scheduled → live" via kickoff: 150 min → **120 min**
- Evita promover jogos já finalizados que a API reporta como "incomplete"

## Performance Resultante
| Métrica | Antes | Depois |
|---------|-------|--------|
| Cache do servidor | 60s | 30s |
| Polling do dashboard | 30s | 15s |
| Delay máximo estimado | ~90s | ~45s |
| Fallback para gols | Nenhum | endpoint `match` |
| Default de score vivo | 0-0 (fake) | `- : -` (loading) |

## Regras para Futuras Correções

1. **Nunca inventar score** — se a API não retorna gol, mostrar indicador de carregamento, não 0-0
2. **Defesa em profundidade** — usar fallback em cadeia: `todays-matches` → `match` → manter último score válido
3. **Validar com dados reais** — sempre confirmar o score real antes de declarar bug resolvido (ex: consultar foxsports.com, sofascore.com)
4. **Testar com nomes variantes** — times como Vasco (Club de Regatas Vasco da Gama vs Vasco) devem casar corretamente no normalizeTeamName
5. **Cuidado com status "incomplete"** — FootyStats usa "incomplete" para jogos não finalizados, tratar como "scheduled" e deixar o heurístico de kickoff decidir

---

## #25 — Correção: Barra de Escanteios Não Aparecia

### Problema
A barra de progresso de escanteios (CornerProgressBar) não era exibida em jogos ao vivo, mesmo quando a API-Football retornava os dados corretamente.

### Causa Raiz
Três falhas em camadas diferentes:
1. **Backend `extract_live_data()`** usava match exato `== "Corner Kicks"` para extrair escanteios inline — se a API retornasse outro casing (ex: `"corner kicks"`, `"Corner kicks"`), o dado era perdido e `currentCorners` ficava `None`
2. **Frontend `normalizeTeamName()`** removia apenas 8 prefixos (`sc|ec|fc|cr|se|aa|ce|gr`) e somente no início da string — times como "Atlético Mineiro" vs "Atletico-MG" ou "AC Milan" vs "Milan" não casavam no merge do live-scores
3. **CSS `.cpb-root`** podia ser escondido por estilos pai que sobrescrevessem `display` ou `opacity`

### Correções Aplicadas

#### 1. Backend — Extração case-insensitive de escanteios inline
**Arquivo:** `backend/services/api_football_client.py` (linha 476)
- **Antes:** `if s.get("type") == "Corner Kicks":`
- **Depois:** `if "corner" in str(s.get("type", "")).lower():`
- Consistente com `_extract_corners_from_stats()` que já usava `.lower()`

#### 2. Frontend — Normalização de nomes mais abrangente
**Arquivo:** `frontend/next/src/app/dashboard/page.tsx` (linha 158)
- **Antes:** `s.replace(/^\b(sc|ec|fc|cr|se|aa|ce|gr)\s+/i, "")`
- **Depois:** `s.replace(/\b(sc|ec|fc|cr|se|aa|ce|gr|ac|cf|as|rc|cd|ca|ss|afc|atletico)\b\s*/gi, "").trim()`
- Match global (não só início), inclui "atletico", "ac", "cf", "afc" etc., alinhado com o backend `_normalize_team_name()`

#### 3. Frontend — CSS defensivo
**Arquivo:** `frontend/next/src/styles/match-detail-card.css`
- Adicionado `display: block !important`, `opacity: 1 !important`, `min-height: 20px`, `width: 100%` ao `.cpb-root`

### Fluxo de Dados dos Escanteios
```
API-Football /fixtures?live=all
  → extract_live_data() extrai home_corners/away_corners (inline stats)
  → Se inline vazio: fallback para /fixtures/statistics via _extract_corners_from_stats()
  → Se ainda vazio: fallback para parse_fixture_statistics() → corner_kicks
  → Soma home + away → currentCorners
  → /live-scores retorna { currentCorners: N }
  → Frontend fetchLiveScores() casa por ID ou normalizeTeamName()
  → MatchDetailCard verifica: mercado contém "Escanteios Over X.X"?
  → CornerProgressBar renderiza barra com progresso atual vs meta
```

### Regras para Futuras Correções de Escanteios
1. **Sempre case-insensitive** — qualquer extração de stat type da API-Football deve usar `.lower()` ou `in`, nunca `==` com string literal
2. **Manter frontend alinhado com backend** — se o backend `_normalize_team_name()` ganhar novos prefixos, atualizar `normalizeTeamName()` no frontend também
3. **Validar com 0 escanteios** — 0 é um valor válido (jogo recém iniciado), não confundir com `None` (dado indisponível)
4. **Testar ligas problemáticas** — Brasileirão Serie A e ligas árabes frequentemente não incluem stats inline no `/fixtures?live=all`, dependendo do fallback explícito via `/fixtures/statistics`

---

## Filtros de Status, Ordenação Prioritária e Separador Visual

**Data:** 2026-03-16
**Arquivo:** `frontend/next/src/app/dashboard/page.tsx`

### O que foi feito

1. **Filtro de Status** — Botão "Filtros em breve" substituído por dropdown funcional (Todos, Ao Vivo, Finalizados, Não Iniciados)
2. **Ordenação Prioritária** — Brasil Serie A e B sempre no topo, demais ligas em ordem alfabética, jogos por horário dentro de cada liga
3. **Separador Visual** — Linha divisória com label "Ligas Internacionais" entre ligas brasileiras e demais

### Regras
1. **Usar IDs estáveis** — Prioridade usa `brazil-serie-a` / `brazil-serie-b` (não string matching)
2. **Filtro integrado ao displayMatches** — Estado `statusFilter` filtra antes do agrupamento por liga
3. **Separador condicional** — Só aparece quando há ligas brasileiras E internacionais na mesma visualização

---

## Dropdown Ilegível + Premier League como "unknown"

**Data:** 2026-03-16
**Arquivos:** `page.tsx`, `api_football_client.py`

### Correções
1. **Backend** — `api_football_client.py`: campo `"league"` renomeado para `"leagueId"` em `fixtures_to_records()`
2. **Frontend (defesa)** — Normalização usa `item.leagueId ?? item.league ?? "unknown"` para compatibilidade
3. **Frontend (dropdown)** — Cores fixas do tema escuro (`#1a1a2e` bg, `#e0e0e0` text) em `<select>` e `<option>`

### Regras
1. **Campos backend→frontend devem bater com o tipo TS** — `"leagueId"` não `"league"`
2. **Dropdowns nativos** — Sempre usar cores inline fixas nas `<option>`, browser ignora CSS variables

---

## Corners Engine v2 — Motor Bidirecional de Projeção de Escanteios

**Data:** 2026-03-18
**Branch:** `claude/corner-betting-framework-zh4G1`

### Problema Original
O motor v1 de escanteios era enviesado para Over: começava ancorado em Over 8.5 e só avaliava 4 linhas `[8.5, 9.5, 10.5, 11.5]`, todas Over. Linhas Under nunca eram candidatas. Além disso, o `ev_classification.py` tinha as linhas hardcoded em tuples fixos, descartando qualquer projeção do motor v2 fora dessas 4 linhas.

### Causa Raiz (3 camadas)
1. **`ev_classification.py`** — Loop de montagem de `MarketOutput` usava 4 tuples hardcoded `[(over_8.5, cornerOver85Prob, cornersOver85), ...]` para Over e `[8.5, 9.5, 10.5, 11.5]` para Under. O motor v2 projetava 9 linhas [4.5-12.5] mas só 4 apareciam.
2. **`calibrator.py` / `market_validator.py`** — Só 8 mercados de escanteio registrados (4 Over + 4 Under para 8.5-11.5). Linhas v2 fora desse range eram rejeitadas como inválidas.
3. **`safe_bets_service.py`** — Strategy C fixada em `market_label="Over 9.5 Escanteios"`, ignorando o motor v2.
4. **`market_reference_signal.py`** — Corners retornava "NEUTRO by default" sem consultar governance do v2.

### Arquitetura do Corners Engine v2 (5 camadas)

```
Layer A: Data Quality Assessment
  → coverage_score, feature_completeness, sample_adequacy
  → Tiers: HIGH / MEDIUM / LOW / INSUFFICIENT

Layer B: Baseline Priors (Negative Binomial + Poisson)
  → NB2 parameterization para overdispersão
  → Method of moments para fitting de r, p

Layer C: Projection (FT / 1H / 2H)
  → Weighted projection com dynamic shrinkage
  → Matchup pressure index (shots, SoT, possession, xG, corners)
  → FH/2H decomposition (timing data ou default 45%/55%)

Layer D: Bidirectional Price Ladder
  → 9 linhas: [4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]
  → Over AND Under para cada linha
  → Fair odds, edge, quality-adjusted edge
  → select_best_market() trata Over e Under como candidatos iguais

Layer E: Decision Engine + Mistral Review
  → Mistral como reviewer contextual (não pode promover)
  → Ações: maintain, lower_confidence, force_no_bet
```

### Correções Aplicadas

#### 1. Corners Engine v2 — Motor completo
**Arquivos novos:**
- `backend/modeling/corners/data_quality.py` — Layer A, avaliação de qualidade de dados
- `backend/modeling/corners/price_ladder.py` — Layer D, pricing bidirecional Over+Under
- `backend/modeling/corners/mistral_review.py` — Layer E, review contextual Mistral AI

**Arquivos reescritos:**
- `backend/modeling/corners/predictor.py` — Orquestrador v2, projeção com shrinkage dinâmico
- `backend/modeling/corners/features.py` — 40+ features v2 + pressure index

**Arquivos atualizados:**
- `backend/modeling/corners/negative_binomial.py` — Emite Over + Under para todas as linhas
- `backend/modeling/corners/poisson_model.py` — Idem, bidirecional
- `backend/modeling/corners/ml_regression.py` — Idem, bidirecional
- `backend/modeling/corners/__init__.py` — `CORNER_LINES = [4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]`

#### 2. Integração — Ladder completo no output
**Arquivo:** `backend/services/ev_classification.py`
- **Antes:** 4 tuples hardcoded para Over, 4 valores fixos para Under
- **Depois:** Itera `CORNER_LINES` (9 linhas) dinamicamente, Over + Under, com fallback para FootyStats stats/odds quando v2 não tem dados

#### 3. Calibrador e Validador expandidos
**Arquivos:** `backend/modeling/calibrator.py`, `backend/modeling/market_validator.py`
- **Antes:** 8 mercados de escanteio (4 Over + 4 Under, só 8.5-11.5)
- **Depois:** 18 mercados (9 Over + 9 Under, 4.5-12.5)

#### 4. Strategy C — Consulta motor v2
**Arquivo:** `backend/services/safe_bets_service.py`
- **Antes:** `market_label="Over 9.5 Escanteios"` hardcoded
- **Depois:** `_try_corners_v2()` consulta `predict_corners()` para melhor linha/lado; fallback `_corners_fallback_heuristic()` escolhe lado/linha dinamicamente baseado na média combinada

#### 5. Market Reference Signal — Governance v2
**Arquivo:** `backend/services/market_reference_signal.py`
- **Antes:** `"Corners sem pipeline de validacao dedicado (v1)"` → sempre NEUTRO
- **Depois:** `_get_corners_signal()` consulta `get_corner_governance_info()`:
  - `ACTIVE / ACTIVE_GUARDED` → SAFE
  - `NEUTRAL` → NEUTRO
  - `RESTRICTED` → RESTRITO

#### 6. Fixes CI/CD
**Arquivo:** `backend/models/market_output.py`
- Pydantic v2: `_corner_governance` (underscore proibido) → `corner_governance` com `AliasChoices`

**Arquivo:** `frontend/next/src/lib/leagues.ts`
- TypeScript: `marketReferenceSignal?: string` → `"SAFE" | "NEUTRO" | "RESTRITO"`

### Testes
- `tests/test_corners_v2.py` — 35 testes cobrindo todas as 5 camadas
- `tests/test_corner_framework.py` — Testes de regressão atualizados
- Total: 241 testes passando

### Regras para Futuras Correções de Escanteios

1. **Nunca hardcodar linhas** — Sempre usar `CORNER_LINES` de `backend/modeling/corners/__init__.py`. Se precisar expandir ou reduzir, alterar apenas a constante.
2. **Under é candidato igual a Over** — O motor v2 trata ambos os lados como first-class. Nunca filtrar Under no pipeline de output.
3. **Motor projeta primeiro, preços depois** — A projeção de expected corners FT vem antes de qualquer avaliação de linha. Não ancorar em Over 8.5.
4. **Shrinkage dinâmico** — Adapta-se à qualidade dos dados. Não usar reducers fixos.
5. **Mistral é reviewer, não decisor** — Pode rebaixar confiança ou forçar NO_BET, mas nunca promover um mercado fraco ou inventar probabilidades.
6. **Governance > Mistral > Nada** — Hierarquia estrita: motor estatístico > governance de dados > review Mistral.
7. **Fallback gracioso** — Se dados INSUFFICIENT, usar legacy engine (4 linhas) em vez de não mostrar nada.
8. **Calibrador e validador devem estar sincronizados** — Se adicionar nova linha em `CORNER_LINES`, adicionar nos dois arquivos também.

---

## Estádio Não Exibido na Análise Mistral — "Estadio nao informado"

**Data:** 2026-03-19
**Branch:** `claude/corner-betting-framework-zh4G1`

### Problema
O campo de estádio exibia "Estadio nao informado" no MatchDetailCard e na análise Mistral, mesmo para jogos onde o API-Football possuía o dado de venue.

### Causa Raiz (3 camadas)
1. **FootyStats `stadium_name` vazio** — A API FootyStats frequentemente não retorna `stadium_name` para partidas brasileiras (Serie A, Copa do Brasil), resultando em string vazia no `DataMapper.map_match_to_internal()`
2. **`enrich_fixture_record()` não copiava venue** — O método que faz overlay de dados API-Football sobre os records do FootyStats atualizava score, status e minute, mas ignorava completamente o campo `venue` da fixture, mesmo quando disponível em `fixture.venue.name`
3. **`_match_to_ai_input()` não incluía stadium** — A função que converte dados de fixture para input da análise Mistral omitia o campo `stadium` do retorno, então mesmo quando o dado existia, não chegava ao frontend

### Fluxo do Dado (antes da correção)
```
FootyStats API → stadium_name: "" (vazio para ligas brasileiras)
  → DataMapper → stadium: ""
  → fixtures_service → stadium: ""
  → fixtures route → { venue: "", stadium: "" }
  → Frontend → match.venue || "Estadio nao informado" ← exibido

API-Football → fixture.venue.name: "Arena MRV" (disponível!)
  → enrich_fixture_record() → NÃO copiava venue ← BUG
  → fixtures_to_records() → venue: "Arena MRV" mas sem campo stadium ← BUG
```

### Correções Aplicadas

#### 1. API-Football — Overlay de venue na enrichment
**Arquivo:** `backend/services/api_football_client.py` (`enrich_fixture_record`)
- **Adicionado:** Quando `record["stadium"]` está vazio, copia `fixture.venue.name` do API-Football
- Só sobrescreve se o venue do API-Football não for vazio (defesa contra dados nulos)

#### 2. API-Football — Campo `stadium` em records de fallback
**Arquivo:** `backend/services/api_football_client.py` (`fixtures_to_records`)
- **Antes:** Só incluía `"venue": venue_name`
- **Depois:** Inclui `"venue": venue_name` E `"stadium": venue_name`
- O `fixtures_service.py` lê `r.get("stadium")`, então o campo precisa existir

#### 3. AI Analysis — Captura e retorno do estádio
**Arquivo:** `backend/routes/ai_analysis.py` (`_match_to_ai_input`)
- **Adicionado:** `footystats_stadium` extraído de `detail_data.get("stadium_name")` dos match details
- **Prioridade:** FootyStats match details → fixtures record `stadium` → fixtures record `venue` → vazio
- **Retorno:** Campo `"stadium"` agora incluído no dict retornado para a análise Mistral

### Regras para Futuras Correções de Estádio
1. **Não confiar em uma única fonte** — FootyStats pode ter `stadium_name` vazio; usar API-Football como fallback
2. **Manter `stadium` e `venue` sincronizados** — O backend usa `stadium`, o frontend lê ambos (`item.venue ?? item.stadium`). Ao adicionar dados, popular ambos os campos
3. **`enrich_fixture_record` deve ser completo** — Qualquer novo campo do API-Football que tenha equivalente no FootyStats deve ser overlayed quando o original estiver vazio
4. **`_match_to_ai_input` deve passar todos os metadados relevantes** — Stadium, venue, e outros campos contextuais devem estar no dict retornado para a análise Mistral funcionar corretamente
