# Analise: Como a API FootyStats Retorna Dados de Placar em Tempo Real

## Resumo Executivo

A API FootyStats (football-data-api.com) retorna dados de jogos ao vivo atraves do endpoint `/todays-matches`. O comportamento observado com `homeGoalCount: -1` nao e especifico de jogos ao vivo, mas sim um padrao de valores padrao usado pela API para indicar "dados nao disponiveis" em diferentes campos.

## Endpoint Principal

**URL:** `GET https://api.football-data-api.com/todays-matches?key=YOURKEY`

### Parametros de Query

| Parametro | Tipo   | Descricao                                                              |
|-----------|--------|------------------------------------------------------------------------|
| key*      | string | Sua chave de API (obrigatorio)                                         |
| date      | string | Formato: YYYY-MM-DD (ex: 2020-07-30). Padrao: data atual em UTC       |
| timezone  | string | Timezone (ex: Europe/London). Padrao: Etc/UTC                          |

### Limitacoes

- Retorna maximo de 200 matches por pagina
- Paginacao habilitada por padrao (adicionar `&page=2` para proxima pagina)
- Voce deve escolher as ligas em suas configuracoes para que os matches aparecam

## Padrao de Valores Padrao

A API FootyStats utiliza um sistema de valores padrao consistente para indicar "dados nao disponiveis":

| Valor | Significado                      | Campos Afetados                                              |
|-------|----------------------------------|--------------------------------------------------------------|
| -1    | Dados nao disponiveis            | corners, shots on target, fouls, possession, IDs             |
| -2    | Dados nao disponiveis (variante) | total shots                                                  |
| 0     | Sem dados ou zero ocorrencias    | goal counts, offsides, cards, corner count                   |
| ""    | String vazia                     | stadium name, stadium location                               |
| "[]"  | Array JSON vazio                 | goal timings                                                 |

## Campos de Placar

| Campo          | Tipo    | Descricao                        | Valor Padrao |
|----------------|---------|----------------------------------|--------------|
| homeGoalCount  | integer | Gols marcados pelo time da casa  | 0 ou -1      |
| awayGoalCount  | integer | Gols marcados pelo visitante     | 0 ou -1      |
| totalGoalCount | integer | Total de gols no jogo            | 0            |
| homeGoals      | string  | Timings dos gols (array JSON)    | "[]"         |
| awayGoals      | string  | Timings dos gols (array JSON)    | "[]"         |

## Campos de Estatisticas

| Campo                | Descricao                          | Valor Padrao |
|----------------------|------------------------------------|--------------|
| team_a_corners       | Escanteios do time da casa         | -1           |
| team_b_corners       | Escanteios do visitante            | -1           |
| team_a_possession    | Posse de bola da casa (%)          | -1           |
| team_b_possession    | Posse de bola do visitante (%)     | -1           |
| team_a_shotsOnTarget | Chutes no alvo da casa             | -1           |
| team_b_shotsOnTarget | Chutes no alvo do visitante        | -1           |
| team_a_shots         | Total de chutes da casa            | -2           |
| team_b_shots         | Total de chutes do visitante       | -2           |
| team_a_fouls         | Faltas da casa                     | -1           |
| team_b_fouls         | Faltas do visitante                | -1           |

## Status do Jogo

| Status       | Significado                                    |
|--------------|------------------------------------------------|
| "incomplete" | Jogo ainda nao iniciou ou esta em andamento    |
| "complete"   | Jogo finalizado                                |

## Comportamento em Tempo Real

Durante jogos ao vivo:

1. **Placar (homeGoalCount, awayGoalCount):** Atualizado em tempo real conforme gols sao marcados
2. **Estatisticas (corners, shots, etc.):** Podem retornar -1 se o provedor nao tiver acesso em tempo real
3. **Cartoes e impedimentos:** Geralmente atualizados em tempo real

## Endpoint Adicional: Match Details

**URL:** `GET https://api.football-data-api.com/match?key=YOURKEY&match_id=1`

Para detalhes completos de um jogo especifico, incluindo estatisticas completas, H2H, trends e odds.

## Recomendacao de Polling

| Contexto                   | Intervalo         |
|----------------------------|-------------------|
| Lista de jogos (live)      | 30 segundos       |
| Lista de jogos (sem live)  | 120 segundos      |
| Detalhes do jogo           | 30-60 segundos    |
| Jogos finalizados          | 5 minutos         |

## Tratamento no Projeto

O backend SportsBankZU trata estes valores em:

- `backend/services/data_mapper.py` — `sanitize_api_value()` normaliza -1/-2 para None/0
- `backend/services/fixtures_service.py` — `_safe_int()` e `_valid_goal_count()` filtram valores negativos
- `backend/routes/fixtures.py` — `/live-scores` valida goals antes de retornar
- `frontend/next/src/lib/matchStats.ts` — `sanitizeStatValue()` filtra valores negativos no frontend
