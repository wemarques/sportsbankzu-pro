# FootyStats (Football Data API) — Endpoints Reference

> Base URL: `https://api.football-data-api.com/`
> Autenticação: query parameter `key` (obrigatório em todos os endpoints)
> Formato de resposta: JSON
> Timestamps: UNIX (segundos)

---

## Índice

1. [League List](#1-league-list)
2. [League Teams](#2-league-teams)
3. [League Matches](#3-league-matches)
4. [League Players](#4-league-players)
5. [League Referees](#5-league-referees)
6. [League Season (Stats)](#6-league-season)
7. [League Tables](#7-league-tables)
8. [Team](#8-team)
9. [Team Last X](#9-team-last-x)
10. [Match](#10-match)
11. [Player Stats](#11-player-stats)
12. [Referee](#12-referee)
13. [Country List](#13-country-list)
14. [Today's Matches](#14-todays-matches)
15. [Stats Data BTTS](#15-stats-data-btts)
16. [Stats Data Over 2.5](#16-stats-data-over-25)

---

## 1. League List

Lista todas as ligas disponíveis na API.

**Endpoint:** `GET /league-list`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `chosen_leagues_only` | boolean | ❌ | Retorna apenas ligas selecionadas na conta |
| `country` | string | ❌ | Código ISO do país (ex: `41` para Brasil) |

### Resposta

```json
{
  "success": true,
  "pager": { "current_page": 1, "max_page": 1, "results_per_page": 1000 },
  "data": [
    {
      "name": "Premier League",
      "country": "England",
      "season": [
        { "id": 2012, "year": "2023/2024" },
        { "id": 1625, "year": "2022/2023" }
      ]
    }
  ]
}
```

### Campos Principais

- `name` — Nome da liga
- `country` — País da liga
- `season[].id` — `season_id` utilizado nos demais endpoints
- `season[].year` — Período da temporada

---

## 2. League Teams

Retorna os times de uma temporada com estatísticas completas.

**Endpoint:** `GET /league-teams`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `include` | string | ❌ | `stats` para estatísticas detalhadas |
| `page` | int | ❌ | Página de resultados |
| `max_time` | int | ❌ | Timestamp UNIX máximo (filtro temporal) |

### Resposta (com `include=stats`)

Retorna array de objetos `team` com schema idêntico ao endpoint `/team`. Cada time inclui:

- Estatísticas gerais: `seasonMatchesPlayed_overall`, `seasonWinsNum_overall`, `seasonDrawsNum_overall`, `seasonLossesNum_overall`
- Gols: `seasonGoals_overall`, `seasonConceded_overall`, `seasonGoalDifference_overall`
- Clean sheets: `seasonCSPercentage_overall`, `seasonCSNum_overall`
- BTTS: `seasonBTTSPercentage_overall`, `seasonBTTSNum_overall`
- Over/Under (0.5 a 5.5): `seasonOver05Percentage_overall` ... `seasonOver55Percentage_overall`
- Corners: `seasonCornersTotal_overall`, `seasonCornersAvg_overall`
- Cards: `seasonCardsTotal_overall`, `seasonCardsAvg_overall`
- xG: `seasonxGTotal_overall`, `seasonxGAvg_overall`
- Todas as métricas com variantes `_home` e `_away`

---

## 3. League Matches

Retorna o calendário completo de jogos de uma temporada.

**Endpoint:** `GET /league-matches`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `page` | int | ❌ | Página de resultados |
| `max_per_page` | int | ❌ | Resultados por página (máx 1000) |
| `max_time` | int | ❌ | Timestamp UNIX máximo |

### Resposta

```json
{
  "success": true,
  "pager": { "current_page": 1, "max_page": 3, "results_per_page": 200 },
  "data": [
    {
      "id": 123456,
      "homeID": 100,
      "awayID": 200,
      "home_name": "Team A",
      "away_name": "Team B",
      "status": "complete",
      "date_unix": 1700000000,
      "homeGoalCount": 2,
      "awayGoalCount": 1,
      "totalGoalCount": 3,
      "team_a_corners": 5,
      "team_b_corners": 3,
      "totalCornerCount": 8,
      "team_a_yellow_cards": 2,
      "team_b_yellow_cards": 3,
      "team_a_red_cards": 0,
      "team_b_red_cards": 0,
      "team_a_shots": 15,
      "team_b_shots": 10,
      "team_a_shotsOnTarget": 7,
      "team_b_shotsOnTarget": 4,
      "team_a_possession": 55,
      "team_b_possession": 45,
      "team_a_offsides": 2,
      "team_b_offsides": 1,
      "refereeID": 500,
      "stadium_name": "Arena X",
      "attendance": 45000,
      "odds_ft_1": 1.85,
      "odds_ft_x": 3.40,
      "odds_ft_2": 4.20,
      "odds_ft_over25": 1.90,
      "odds_ft_under25": 1.95,
      "odds_btts_yes": 1.80,
      "odds_btts_no": 2.00,
      "o05_potential": 85,
      "o15_potential": 70,
      "o25_potential": 55,
      "o35_potential": 35,
      "o45_potential": 15,
      "btts_potential": 60,
      "home_ppg": 2.1,
      "away_ppg": 1.3,
      "ht_goals_team_a": 1,
      "ht_goals_team_b": 0,
      "competition_id": 999,
      "round_id": 10,
      "game_week": 10,
      "pre_match_teamA_overall_ppg": 2.1,
      "pre_match_teamB_overall_ppg": 1.3,
      "pre_match_home_ppg": 2.4,
      "pre_match_away_ppg": 1.1
    }
  ]
}
```

### Campos Principais

**Identificação:**
- `id` — ID único do jogo (usado em `/match`)
- `homeID`, `awayID` — IDs dos times
- `home_name`, `away_name` — Nomes dos times
- `status` — `complete`, `incomplete`, `live`, `suspended`, `cancelled`
- `date_unix` — Timestamp UNIX do jogo

**Placar:**
- `homeGoalCount`, `awayGoalCount`, `totalGoalCount`
- `ht_goals_team_a`, `ht_goals_team_b` — Gols no 1º tempo

**Estatísticas de Jogo:**
- `team_a_corners`, `team_b_corners`, `totalCornerCount`
- `team_a_yellow_cards`, `team_b_yellow_cards`
- `team_a_red_cards`, `team_b_red_cards`
- `team_a_shots`, `team_b_shots`
- `team_a_shotsOnTarget`, `team_b_shotsOnTarget`
- `team_a_possession`, `team_b_possession`
- `team_a_offsides`, `team_b_offsides`

**Odds:**
- `odds_ft_1`, `odds_ft_x`, `odds_ft_2` — 1X2
- `odds_ft_over25`, `odds_ft_under25` — Over/Under 2.5
- `odds_btts_yes`, `odds_btts_no` — BTTS

**Potenciais (pré-jogo):**
- `o05_potential` a `o45_potential` — Potencial de Over 0.5 a 4.5
- `btts_potential` — Potencial BTTS

**Performance:**
- `home_ppg`, `away_ppg` — Pontos por jogo
- `pre_match_teamA_overall_ppg`, `pre_match_teamB_overall_ppg`
- `pre_match_home_ppg`, `pre_match_away_ppg`

---

## 4. League Players

Retorna jogadores que participaram em uma temporada.

**Endpoint:** `GET /league-players`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `page` | int | ❌ | Página |
| `max_time` | int | ❌ | Timestamp UNIX máximo |
| `include` | string | ❌ | `stats` para estatísticas detalhadas |

### Resposta

```json
{
  "data": [
    {
      "id": 50000,
      "full_name": "John Doe",
      "known_as": "J. Doe",
      "team_id": 100,
      "position": "Forward",
      "nationality": "Brazil",
      "age": 25,
      "appearances_overall": 30,
      "goals_overall": 12,
      "assists_overall": 5,
      "minutes_played_overall": 2400,
      "yellow_cards_overall": 3,
      "red_cards_overall": 0,
      "clean_sheets_overall": 0,
      "rating": "7.2"
    }
  ]
}
```

### Campos Principais

- `id` — ID do jogador (usado em `/player-stats`)
- `full_name`, `known_as` — Nome
- `team_id` — ID do time atual na temporada
- `position` — Posição (Forward, Midfielder, Defender, Goalkeeper)
- `appearances_overall` — Jogos disputados
- `goals_overall`, `assists_overall` — Gols e assistências
- `minutes_played_overall` — Minutos jogados
- `yellow_cards_overall`, `red_cards_overall` — Cartões
- `clean_sheets_overall` — Clean sheets (goleiros/defensores)
- `rating` — Nota média

---

## 5. League Referees

Retorna árbitros de uma temporada com estatísticas.

**Endpoint:** `GET /league-referees`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `max_time` | int | ❌ | Timestamp UNIX máximo |

### Resposta

```json
{
  "data": [
    {
      "id": 800,
      "name": "Referee Name",
      "matches_officiated": 15,
      "yellow_cards_avg": 4.2,
      "red_cards_avg": 0.3,
      "penalties_avg": 0.2,
      "goals_avg": 2.8,
      "btts_percentage": 55,
      "over25_percentage": 60,
      "over35_percentage": 30
    }
  ]
}
```

### Campos Principais

- `id` — ID do árbitro (usado em `/referee`)
- `matches_officiated` — Jogos apitados
- `yellow_cards_avg`, `red_cards_avg` — Média de cartões
- `penalties_avg` — Média de pênaltis
- `goals_avg` — Média de gols nos jogos
- `btts_percentage` — % de jogos com BTTS
- `over25_percentage`, `over35_percentage` — % de jogos Over 2.5/3.5

---

## 6. League Season

Estatísticas agregadas de uma temporada/liga.

**Endpoint:** `GET /league-season`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `max_time` | int | ❌ | Timestamp UNIX máximo |

### Resposta

```json
{
  "data": {
    "id": 2012,
    "name": "Premier League",
    "country": "England",
    "matchesPlayed": 250,
    "numberOfTeams": 20,
    "totalGoals": 650,
    "avgGoals": 2.6,
    "bttsPercentage": 52,
    "over25Percentage": 55,
    "over15Percentage": 72,
    "over35Percentage": 30,
    "cleanSheetPercentage": 25,
    "avgCorners": 10.5,
    "avgCards": 3.8,
    "avgFouls": 22.1,
    "avgShots": 25.3,
    "avgShotsOnTarget": 9.1,
    "avgPossessionHome": 53,
    "avgPossessionAway": 47,
    "homeWinPercentage": 45,
    "drawPercentage": 25,
    "awayWinPercentage": 30,
    "homeGoalsAvg": 1.5,
    "awayGoalsAvg": 1.1,
    "homeGoalsTotal": 375,
    "awayGoalsTotal": 275,
    "cornersAvg_home": 5.5,
    "cornersAvg_away": 5.0,
    "cardsAvg_home": 1.8,
    "cardsAvg_away": 2.0
  }
}
```

### Campos Principais

**Geral:**
- `matchesPlayed`, `numberOfTeams`, `totalGoals`, `avgGoals`

**Over/Under & BTTS:**
- `over15Percentage`, `over25Percentage`, `over35Percentage`
- `bttsPercentage`, `cleanSheetPercentage`

**Média por jogo:**
- `avgCorners`, `avgCards`, `avgFouls`, `avgShots`, `avgShotsOnTarget`

**Home/Away advantage:**
- `homeWinPercentage`, `drawPercentage`, `awayWinPercentage`
- `homeGoalsAvg`, `awayGoalsAvg`
- `avgPossessionHome`, `avgPossessionAway`
- `cornersAvg_home`, `cornersAvg_away`
- `cardsAvg_home`, `cardsAvg_away`

---

## 7. League Tables

Tabela de classificação da liga.

**Endpoint:** `GET /league-tables`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `season_id` | int | ✅ | ID da temporada |
| `max_time` | int | ❌ | Timestamp UNIX máximo |

### Resposta

```json
{
  "data": {
    "league_table": [
      {
        "position": 1,
        "team_id": 100,
        "team_name": "Team A",
        "played": 20,
        "wins": 14,
        "draws": 4,
        "losses": 2,
        "goals_for": 40,
        "goals_against": 15,
        "goal_difference": 25,
        "points": 46,
        "form": "WWDWW"
      }
    ],
    "home_table": [],
    "away_table": [],
    "round_tables": {},
    "group_tables": {}
  }
}
```

### Campos Principais

- `league_table` — Classificação geral
- `home_table` — Classificação como mandante
- `away_table` — Classificação como visitante
- `round_tables` — Tabelas por rodada (quando aplicável)
- `group_tables` — Tabelas por grupo (copas/torneios)
- Cada entry: `position`, `team_id`, `team_name`, `played`, `wins`, `draws`, `losses`, `goals_for`, `goals_against`, `goal_difference`, `points`, `form`

---

## 8. Team

Estatísticas detalhadas de um time em uma temporada.

**Endpoint:** `GET /team`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `team_id` | int | ✅ | ID do time |
| `include` | string | ❌ | `stats` para estatísticas detalhadas |

### Resposta (campos principais)

O endpoint retorna centenas de métricas. As principais categorias:

**Identificação:**
- `id`, `name`, `full_name`, `country`, `image`

**Resultados (overall/home/away):**
- `seasonMatchesPlayed_overall`, `seasonWinsNum_overall`, `seasonDrawsNum_overall`, `seasonLossesNum_overall`
- `seasonPPG_overall` — Pontos por jogo
- `seasonGoals_overall`, `seasonConceded_overall`, `seasonGoalDifference_overall`

**Over/Under (0.5 a 5.5, overall/home/away):**
- `seasonOver05Percentage_overall` ... `seasonOver55Percentage_overall`
- `seasonOver05Num_overall` ... `seasonOver55Num_overall`

**BTTS:**
- `seasonBTTSPercentage_overall`, `seasonBTTSNum_overall`

**Clean Sheets:**
- `seasonCSPercentage_overall`, `seasonCSNum_overall`
- `seasonFTSPercentage_overall` — Failed to score %
- `seasonFTSNum_overall`

**Corners:**
- `seasonCornersTotal_overall`, `seasonCornersAvg_overall`
- `seasonCornersFor_overall`, `seasonCornersAgainst_overall`
- `seasonCornersOver85_overall` ... `seasonCornersOver135_overall` (%)

**Cards:**
- `seasonCardsTotal_overall`, `seasonCardsAvg_overall`
- `seasonCardsFor_overall`, `seasonCardsAgainst_overall`
- `seasonCardsOver15_overall` ... `seasonCardsOver65_overall` (%)

**xG (Expected Goals):**
- `seasonxGTotal_overall`, `seasonxGAvg_overall`
- `seasonxGFor_overall`, `seasonxGAgainst_overall`

**Posse de Bola:**
- `seasonPossessionAvg_overall`

**Gols por Intervalo de Tempo (10 min):**
- `goals_scored_min_0_to_10`, `goals_scored_min_11_to_20` ... `goals_scored_min_81_to_90`
- `goals_conceded_min_0_to_10` ... `goals_conceded_min_81_to_90`

**Gols por Intervalo de Tempo (15 min):**
- `goals_scored_min_0_to_15`, `goals_scored_min_16_to_30` ... `goals_scored_min_76_to_90`
- `goals_conceded_min_0_to_15` ... `goals_conceded_min_76_to_90`

**2º Tempo:**
- `seasonScoredFirst2HPercentage_overall`, `seasonConcededFirst2HPercentage_overall`
- `seasonOver05_2h_overall` ... `seasonOver25_2h_overall`

**Outros:**
- `attendance_average`, `attendance_highest`, `attendance_lowest`
- `seasonThrowInsFor_overall`, `seasonThrowInsAgainst_overall`
- `seasonFreeKicksFor_overall`, `seasonFreeKicksAgainst_overall`
- `seasonGoalKicksFor_overall`, `seasonGoalKicksAgainst_overall`
- `seasonPenaltiesScored_overall`, `seasonPenaltiesMissed_overall`

> Nota: Todas as métricas possuem variantes `_home` e `_away` além de `_overall`.

---

## 9. Team Last X

Estatísticas dos últimos 5, 6 e 10 jogos de um time.

**Endpoint:** `GET /lastx`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `team_id` | int | ✅ | ID do time |

### Resposta

```json
{
  "data": {
    "last_5": { /* mesmo schema do Team endpoint + formRun */ },
    "last_6": { /* mesmo schema do Team endpoint + formRun */ },
    "last_10": { /* mesmo schema do Team endpoint + formRun */ }
  }
}
```

### Campos Adicionais

- `formRun` — String de forma recente (ex: `"WWDLW"`)
- Todas as métricas do endpoint `/team` aplicadas ao período (5/6/10 jogos)

---

## 10. Match

Detalhes completos de um jogo individual, incluindo H2H, escalações e odds.

**Endpoint:** `GET /match`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `match_id` | int | ✅ | ID do jogo |

### Resposta

Além dos campos do league-matches, inclui:

**Escalações:**
```json
{
  "lineup": {
    "home": [
      { "player_id": 50000, "name": "J. Doe", "position": "Forward", "number": 9 }
    ],
    "away": []
  },
  "bench": {
    "home": [],
    "away": []
  }
}
```

**Detalhes de Gols e Cartões:**
```json
{
  "goalDetails": [
    {
      "player_id": 50000,
      "player_name": "J. Doe",
      "team": "home",
      "minute": 35,
      "type": "goal"
    }
  ],
  "cardDetails": [
    {
      "player_id": 60000,
      "player_name": "A. Smith",
      "team": "away",
      "minute": 67,
      "type": "yellow"
    }
  ]
}
```

**Head-to-Head (H2H):**
```json
{
  "h2h": [
    {
      "id": 100000,
      "date_unix": 1690000000,
      "homeID": 100,
      "awayID": 200,
      "homeGoalCount": 1,
      "awayGoalCount": 1,
      "status": "complete"
    }
  ]
}
```

**Tendências (trends):**
```json
{
  "trends": [
    "Team A has scored in 8 of their last 10 home matches",
    "Over 2.5 goals in 6 of Team B's last 10 away matches"
  ]
}
```

**Odds Comparison:**
```json
{
  "odds_comparison": {
    "1x2": [
      { "bookmaker": "Bet365", "home": 1.85, "draw": 3.40, "away": 4.20 },
      { "bookmaker": "Pinnacle", "home": 1.90, "draw": 3.35, "away": 4.10 }
    ],
    "over_under_25": [
      { "bookmaker": "Bet365", "over": 1.90, "under": 1.95 }
    ],
    "btts": [
      { "bookmaker": "Bet365", "yes": 1.80, "no": 2.00 }
    ]
  }
}
```

**Outros:**
- `weather` — Condições meteorológicas
- `stadium_name`, `attendance`

---

## 11. Player Stats

Estatísticas individuais de um jogador em todas as temporadas/ligas.

**Endpoint:** `GET /player-stats`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `player_id` | int | ✅ | ID do jogador |

### Resposta

```json
{
  "data": [
    {
      "season_id": 2012,
      "league_name": "Premier League",
      "team_name": "Team A",
      "appearances": 30,
      "goals": 12,
      "assists": 5,
      "minutes_played": 2400,
      "yellow_cards": 3,
      "red_cards": 0,
      "xG": 10.5,
      "xA": 4.2,
      "npxG": 9.8,
      "passes_completed": 1200,
      "passes_attempted": 1500,
      "tackles_won": 45,
      "dribbles_completed": 60,
      "saves": 0,
      "aerial_duels_won": 30,
      "shot_conversion_rate": 18.5,
      "salary": "£100,000/week",
      "percentile_rank": {
        "goals": 92,
        "assists": 78,
        "xG": 88,
        "passes": 65,
        "tackles": 45
      }
    }
  ]
}
```

### Campos Principais

**Performance:**
- `appearances`, `goals`, `assists`, `minutes_played`
- `shot_conversion_rate`

**Expected Metrics:**
- `xG` — Expected Goals
- `xA` — Expected Assists
- `npxG` — Non-Penalty Expected Goals

**Técnicos:**
- `passes_completed`, `passes_attempted`
- `tackles_won`, `dribbles_completed`
- `aerial_duels_won`, `saves`

**Classificação:**
- `percentile_rank` — Ranking percentil comparado a jogadores da mesma posição
- `salary` — Salário (quando disponível)

---

## 12. Referee

Estatísticas individuais de um árbitro em todas as competições.

**Endpoint:** `GET /referee`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `referee_id` | int | ✅ | ID do árbitro |

### Resposta

```json
{
  "data": [
    {
      "season_id": 2012,
      "competition_name": "Premier League",
      "matches_officiated": 15,
      "yellow_cards_avg": 4.2,
      "red_cards_avg": 0.3,
      "penalties_avg": 0.2,
      "goals_avg": 2.8,
      "btts_percentage": 55,
      "over25_percentage": 60
    }
  ]
}
```

### Campos Principais

- Estatísticas por temporada/competição
- Mesmo schema do `/league-referees`, mas agregado por competição

---

## 13. Country List

Lista de países com códigos ISO.

**Endpoint:** `GET /country-list`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |

### Resposta

```json
{
  "data": [
    { "id": 41, "name": "Brazil" },
    { "id": 62, "name": "England" },
    { "id": 76, "name": "Germany" }
  ]
}
```

### Uso

- `id` — Código ISO utilizado no parâmetro `country` do `/league-list`

---

## 14. Today's Matches

Jogos por data específica.

**Endpoint:** `GET /todays-matches`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |
| `date` | string | ❌ | Data no formato `YYYY-MM-DD` (default: hoje) |
| `timezone` | string | ❌ | Timezone (ex: `America/Sao_Paulo`, `Europe/London`) |

### Resposta

Retorna máximo de 200 jogos por página com dados básicos de cada jogo:

```json
{
  "data": [
    {
      "id": 123456,
      "homeID": 100,
      "awayID": 200,
      "home_name": "Team A",
      "away_name": "Team B",
      "status": "incomplete",
      "date_unix": 1700000000,
      "competition_id": 999,
      "competition_name": "Premier League",
      "odds_ft_1": 1.85,
      "odds_ft_x": 3.40,
      "odds_ft_2": 4.20,
      "odds_ft_over25": 1.90,
      "odds_ft_under25": 1.95,
      "odds_btts_yes": 1.80,
      "odds_btts_no": 2.00
    }
  ]
}
```

### Notas

- Máximo 200 jogos por página
- Inclui odds básicas (1X2, Over/Under 2.5, BTTS)
- Use o `id` retornado para buscar detalhes completos via `/match`

---

## 15. Stats Data BTTS

Top times, jogos e ligas para BTTS (Both Teams To Score).

**Endpoint:** `GET /stats-data-btts`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |

### Resposta

```json
{
  "data": {
    "top_teams": [
      { "team_id": 100, "team_name": "Team A", "btts_percentage": 80, "season_id": 2012 }
    ],
    "top_fixtures": [
      { "match_id": 123456, "home_name": "Team A", "away_name": "Team B", "btts_potential": 85 }
    ],
    "top_leagues": [
      { "season_id": 2012, "league_name": "Eredivisie", "btts_percentage": 62 }
    ]
  }
}
```

### Uso

- Rankings globais de BTTS
- Útil para identificar oportunidades de apostas BTTS

---

## 16. Stats Data Over 2.5

Top times, jogos e ligas para Over 2.5 gols.

**Endpoint:** `GET /stats-data-over25`

### Parâmetros

| Param | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `key` | string | ✅ | API key |

### Resposta

```json
{
  "data": {
    "top_teams": [
      { "team_id": 100, "team_name": "Team A", "over25_percentage": 75, "season_id": 2012 }
    ],
    "top_fixtures": [
      { "match_id": 123456, "home_name": "Team A", "away_name": "Team B", "o25_potential": 80 }
    ],
    "top_leagues": [
      { "season_id": 2012, "league_name": "Bundesliga", "over25_percentage": 58 }
    ]
  }
}
```

### Uso

- Rankings globais de Over 2.5
- Útil para identificar ligas e times com alto volume de gols

---

## Notas Gerais

### Paginação

Endpoints que suportam paginação retornam um objeto `pager`:
```json
{
  "pager": {
    "current_page": 1,
    "max_page": 3,
    "results_per_page": 200
  }
}
```

### Filtro Temporal (`max_time`)

- Aceita timestamp UNIX (segundos)
- Filtra resultados até aquele momento
- Útil para simulações históricas e backtesting

### Status de Jogos

| Status | Descrição |
|--------|-----------|
| `complete` | Jogo finalizado |
| `incomplete` | Jogo ainda não realizado |
| `live` | Jogo em andamento |
| `suspended` | Jogo suspenso |
| `cancelled` | Jogo cancelado |

### Endpoints Usados no SportsBankZU Pro

Mapeamento dos endpoints mais utilizados pelo sistema:

| Endpoint | Uso no Sistema |
|----------|---------------|
| `/league-list` | Carregamento de ligas disponíveis |
| `/league-matches` | Calendário de jogos e dados pré-jogo |
| `/league-teams` | Estatísticas de times por temporada |
| `/team` | Análise detalhada de time individual |
| `/lastx` | Forma recente (últimos 5/6/10 jogos) |
| `/match` | Detalhes completos de jogo, H2H, odds |
| `/todays-matches` | Jogos do dia para painel em tempo real |
| `/league-season` | Métricas agregadas da liga |
| `/league-tables` | Classificação atualizada |
