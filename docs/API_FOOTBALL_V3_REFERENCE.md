# API-Football v3 — Referência do projeto

> **Documentação oficial (interativa):** [https://www.api-football.com/documentation-v3](https://www.api-football.com/documentation-v3)  
> **Base URL da API (REST):** `https://v3.football.api-sports.io`  
> **Dashboard / chave / Live Tester:** [dashboard.api-football.com](https://dashboard.api-football.com)

## Acesso à documentação web

A página **documentation-v3** é tipicamente uma aplicação carregada no browser; pedidos HTTP simples ou ferramentas automatizadas podem **expirar ou receber HTML mínimo**. Para explorar parâmetros e exemplos de resposta, use:

1. O **Live API Tester** no dashboard (recomendado).  
2. O browser em [documentation-v3](https://www.api-football.com/documentation-v3).  
3. O guia narrativo no monorepo: [`../../docs/api-football.md`](../../docs/api-football.md) (tutorial completo + walkthrough de endpoints).

---

## Contrato v3 (resumo)

| Item | Detalhe |
|------|---------|
| **Método** | Apenas **GET** (sem POST/PUT/DELETE nos dados). |
| **Auth** | Header `x-apisports-key: <sua_chave>`. Variável no projeto: `API_FOOTBALL_KEY`. |
| **Resposta** | Envelope comum: `get`, `parameters`, `errors`, `results`, `paging`, `response`. Validar `errors` antes de usar `response`. |
| **Paginação** | Se `paging.total > 1`, usar `page=2`, … — ex.: **`/odds`** costuma paginar a **10** resultados por página (o cliente do projeto percorre páginas). |
| **Rate limit** | Headers como `x-ratelimit-requests-remaining` (dia) e limites por minuto; ver guia em `../../docs/api-football.md`. |
| **Coverage** | Em **`/leagues`**, por época: objeto `coverage` (ex.: `injuries`, `fixtures.statistics`) — evitar chamadas inúteis se a liga não cobre o dado. |

---

## Endpoints usados neste projeto

Implementação principal: `backend/services/api_football_client.py` (`APIFootballClient`).

| Endpoint API-Football | Uso no projeto (resumo) |
|------------------------|-------------------------|
| `fixtures` | Jogos por data/liga, `live=all` ou IDs, enrich / fallback de records. |
| `standings` | Classificação por liga/temporada. |
| `teams/statistics` | Estatísticas agregadas da equipa na competição. |
| `fixtures/statistics` | Stats por jogo (cantos, posse, cartões, etc.) — parsing dedicado. |
| `fixtures/events` | Timeline (golos, cartões, substituições) — parsing dedicado. |
| `fixtures/lineups` | Onzes e bancos. |
| `odds` | Odds pré-jogo (com **paginação completa** no client). |
| `predictions` | Previsões API-Sports quando usadas. |
| `fixtures/headtohead` | H2H entre duas equipas (`h2h=id-id`). |
| `injuries` | Lesões / indisponíveis por fixture (com verificação de **coverage** de lesões). |
| `leagues` | Metadados e **coverage** por temporada (ex.: `has_injury_coverage`). |

Modos **sync** (`requests`) e **async** (`httpx`) existem para vários fluxos; respostas frequentemente passam por **cache SQLite** com TTL configurável por chamada.

---

## Onde a API entra na arquitetura

- **Complementar** à FootyStats: livescore, lesões, enrichment de fixtures, matching por nomes de equipas (ver `docs/REGRAS_CORRECAO_SISTEMA.md`, integração #003 e seguintes).  
- **Mistral / análise:** contexto ao vivo (stats, eventos, cantos) quando ligado ao pipeline (`mistral_analysis`, rotas em `fixtures.py` / `ai_analysis.py`).

---

## Ficheiros relacionados no repo

| Ficheiro | Conteúdo |
|----------|----------|
| [`../../docs/api-football.md`](../../docs/api-football.md) | Guia longo (endpoints, exemplos cURL/JS/Python, paginação, timezones). |
| `backend/services/api_football_client.py` | Cliente e parsers. |
| `backend/config/leagues_config.py` | Mapeamento `API_FOOTBALL_LEAGUE_IDS` (liga interna → ID numérico v3). |

---

## Changelog deste ficheiro

- **2026-03-24:** Criado como referência local (documentação oficial consultada via browser; mirror estrutural + endpoints usados no código).
