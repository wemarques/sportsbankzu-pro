# FootyStats API — Data Points and Stats Identifiers

## Referência Completa de Variáveis e Identificadores de Estatísticas

**Fonte:** [https://footystats.org/api/](https://footystats.org/api/)
**Data de extração:** 24 de fevereiro de 2026

---

## Sumário

1. [Visão Geral da API](#visão-geral-da-api)
2. [Especificações da API](#especificações-da-api)
3. [Endpoints Disponíveis](#endpoints-disponíveis)
4. [LEAGUES — Data Points (170+)](#leagues--data-points)
5. [TEAMS — Data Points (710+)](#teams--data-points)
6. [PLAYERS — Data Points (65+)](#players--data-points)
7. [Planos e Preços](#planos-e-preços)

---

## Visão Geral da API

A FootyStats API é uma API de estatísticas de futebol (soccer) que fornece dados em formato JSON, projetada para websites, Machine Learning, Python e uso acadêmico. Cobre mais de 1.500 ligas e competições em todo o mundo.

---

## Especificações da API

| Especificação | Detalhe |
|---|---|
| Esporte | Futebol (Soccer) |
| Formato de Dados | JSON |
| Projetada Para | Websites, Machine Learning, Python, Academia |
| Ligas e Competições Incluídas | 1.500+ |
| Rate Limiting | 60 – 90 Requisições / Min |
| Frequência de Atualização de Resultados | A cada 20 minutos |
| Data Points por Liga | 170+ |
| Data Points por Time | 710+ |
| Data Points por Jogador | 65+ |

---

## Endpoints Disponíveis

| Endpoint | URL Base | Descrição |
|---|---|---|
| League List | `/league-list` | Lista de todas as ligas disponíveis |
| Country List | `/country-list` | Lista de todos os países |
| Today's Matches | `/todays-matches` | Partidas do dia (por data) |
| League Stats | `/league-season` | Estatísticas da liga e times da temporada |
| League Matches | `/league-matches` | Partidas de uma liga |
| League Teams | `/league-teams` | Times de uma liga |
| League Players | `/league-players` | Jogadores de uma liga |
| League Referees | `/league-referees` | Árbitros de uma liga |
| Team | `/team` | Dados individuais de um time |
| Team Last 5/6/10 | `/team-lastx` | Estatísticas dos últimos 5, 6 ou 10 jogos |
| Match Details | `/match` | Detalhes da partida (Stats, H2H, Odds) |
| League Table | `/league-table` | Tabela de classificação |
| Player Individual | `/player` | Dados individuais de um jogador |
| Referee Individual | `/referee` | Dados individuais de um árbitro |
| BTTS Stats | `/btts-stats` | Estatísticas de Both Teams To Score |
| Over 2.5 Stats | `/over25-stats` | Estatísticas de Over 2.5 gols |

**URL Base da API:** `https://api.football-data-api.com/`

---

## LEAGUES — Data Points

### Parâmetros de Consulta (Query Parameters)

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| key | string | Sim | Sua chave de API |
| season_id | integer | Sim | ID da temporada da liga que deseja consultar |
| max_time | integer | Não | UNIX Timestamp. Retorna as estatísticas da liga e dos times até um determinado momento |

### Identificação e Metadados da Liga

| Variável | Descrição |
|---|---|
| id | ID da temporada |
| tsapi_id | ID alternativo da temporada |
| name | Nome da liga |
| english_name | Nome da liga sem acentos e diacríticos |
| name_jp / name_tr / name_kr / name_pt / name_ru / name_es / name_se / name_de / name_zht / name_nl / name_it / name_fr / name_id / name_pl / name_gr / name_dk / name_th / name_hr / name_ro / name_in / name_no / name_hu / name_cz / name_cn / name_ara / name_si / name_vn / name_my / name_sk / name_rs / name_ua / name_bg / name_lv / name_ge / name_swa / name_kur / name_ee / name_lt / name_ba / name_by / name_fi | Nome da liga em diversos idiomas |
| country | Nome do país |
| year | Ano da temporada |
| short_hand | Abreviação da liga |
| domestic_scale | Importância da liga dentro do próprio país (usado para ranquear ligas em feeds) |
| international_scale | Importância das ligas do país globalmente (usado para ranquear ligas em feeds) |
| tie_break | Critério de desempate da liga |
| status | Status da temporada |
| format | Formato da liga |
| division | Divisão da liga |
| no_home_away | 1 se a liga não tem distinção casa/fora |
| starting_year | Ano de início da temporada (ex: 2017 para temporada 17-18) |
| ending_year | Ano de término da temporada (ex: 2018 para temporada 17-18) |
| premium | Indicador de liga premium |
| women | 1 ou true se é liga feminina |
| uefa_coefficient | Coeficiente UEFA |
| continent | Continente da liga |
| image | URL da imagem da liga |
| image_thumb | URL do thumbnail da imagem da liga |
| url | URL da liga no FootyStats |
| parent_url | URL pai da liga |
| iso | Código ISO do país |
| flag_element | Elemento de bandeira |
| flag_element_11 | Elemento de bandeira (variante) |
| countryURL | URL do país |
| source | Fonte dos dados |
| verified | Se os dados são verificados |
| comp_master_id | ID mestre da competição |
| sm_children_ids | IDs de competições filhas |

### Configuração e Status da Liga

| Variável | Descrição |
|---|---|
| total_matches | Total de partidas na temporada |
| goal_timing_disabled | 1 se os tempos de gol não estão disponíveis |
| schedule_change_freq | Frequência de alteração do calendário |
| final_espresso | Último processamento espresso |
| last_espresso_timestamp | Timestamp do último processamento espresso |
| last_db_update_timestamp | Timestamp da última atualização do banco de dados |
| corner_disabled | 1 se escanteios não estão disponíveis |
| cards_disabled | 1 se cartões não estão disponíveis |
| players | Indicador de dados de jogadores disponíveis |
| table_corrections | Correções na tabela de classificação |
| zone_descriptions_element | Descrições das zonas da tabela |
| round_dates | Datas das rodadas |

### Progresso e Resumo da Temporada

| Variável | Descrição |
|---|---|
| clubNum | Número de clubes na liga |
| season | Descrição completa da temporada |
| goalTimingDisabled | 1 se os tempos de gol não estão disponíveis |
| latest | Indicador de temporada mais recente |
| totalMatches | Total de partidas na temporada |
| matchesCompleted | Número de partidas completadas |
| canceledMatchesNum | Número de partidas canceladas |
| game_week | Rodada atual da liga |
| total_game_week | Total de rodadas |
| round | ID da rodada atual (corresponde à rodada das tabelas) |
| round_format | Formato da rodada (0 = Liga, 1 = Fase de Grupos, 2 = Eliminatórias) |
| progress | Progresso da temporada em % |
| player_count | Número de jogadores que participaram da liga |
| averageAttendance | Público médio por partida |

### Gols — Estatísticas Gerais

| Variável | Descrição |
|---|---|
| total_goals | Total de gols na temporada |
| home_teams_goals | Gols marcados pelos times da casa |
| home_teams_conceded | Gols sofridos pelos times da casa |
| away_teams_goals | Gols marcados pelos times visitantes |
| away_teams_conceded | Gols sofridos pelos times visitantes |
| seasonAVG_overall | Média de gols totais por partida |
| seasonAVG_home | Média de gols dos times da casa por partida |
| seasonAVG_away | Média de gols dos times visitantes por partida |

### BTTS (Both Teams To Score) e Clean Sheets

| Variável | Descrição |
|---|---|
| btts_matches | Número de partidas que terminaram com BTTS |
| seasonBTTSPercentage | % de partidas que terminaram com BTTS |
| seasonCSPercentage | % de partidas que terminaram com Clean Sheet para algum time |
| home_teams_clean_sheets | Número de clean sheets dos times da casa |
| away_teams_clean_sheets | Número de clean sheets dos times visitantes |
| home_teams_failed_to_score | Número de vezes que o time da casa não marcou |
| away_teams_failed_to_score | Número de vezes que o time visitante não marcou |
| failed_to_score_total | Total de vezes que times não marcaram |
| clean_sheets_total | Total de clean sheets |

### Previsão e Risco

| Variável | Descrição |
|---|---|
| riskNum | Risco de Previsão FootyStats |

### Vantagem Casa/Fora

| Variável | Descrição |
|---|---|
| homeAttackAdvantagePercentage | Vantagem da casa no ataque (% a mais de gols que os times da casa marcam vs visitantes) |
| homeDefenceAdvantagePercentage | Vantagem da casa na defesa (% a menos de gols que os times da casa sofrem vs visitantes) |
| homeOverallAdvantage | Vantagem geral entre ataque e defesa |

### Resultados (Vitórias, Empates, Derrotas)

| Variável | Descrição |
|---|---|
| homeWins | Número de vitórias em casa |
| draws | Número de empates |
| awayWins | Número de vitórias fora |
| homeWinPercentage | % de vitórias em casa |
| drawPercentage | % de empates |
| awayWinPercentage | % de vitórias fora |

### Escanteios (Corners)

| Variável | Descrição |
|---|---|
| cornersAVG_overall | Média de escanteios por partida na liga |
| cornersAVG_home | Média de escanteios por partida do time da casa |
| cornersAVG_away | Média de escanteios por partida do time visitante |
| cornersTotal_overall | Total de escanteios na temporada |
| cornersTotal_home | Total de escanteios dos times da casa |
| cornersTotal_away | Total de escanteios dos times visitantes |
| cornersRecorded_matches | Número de partidas com escanteios registrados |
| over65Corners_overall — over145Corners_overall | Número de partidas com Over 6.5 a 14.5 escanteios |
| over65CornersPercentage_overall — over145CornersPercentage_overall | % de partidas com Over 6.5 a 14.5 escanteios |
| cornerTimingRecorded_matches | Partidas com timing de escanteios registrado |
| corners_fh_num | Total de escanteios no 1º tempo |
| corners_2h_num | Total de escanteios no 2º tempo |
| corners_fh_avg | Média de escanteios no 1º tempo |
| corners_2h_avg | Média de escanteios no 2º tempo |
| corners_fh_over4_num — corners_fh_over6_num | Partidas com Over 4-6 escanteios no 1º tempo |
| corners_2h_over4_num — corners_2h_over6_num | Partidas com Over 4-6 escanteios no 2º tempo |
| corners_fh_over4_percentage — corners_fh_over6_percentage | % de partidas com Over 4-6 escanteios no 1º tempo |
| corners_2h_over4_percentage — corners_2h_over6_percentage | % de partidas com Over 4-6 escanteios no 2º tempo |

### Cartões (Cards)

| Variável | Descrição |
|---|---|
| cardsAVG_overall | Média de cartões por partida na temporada |
| cardsAVG_home | Média de cartões por partida do time da casa |
| cardsAVG_away | Média de cartões por partida do time visitante |
| cardsTotal_overall | Total de cartões na temporada |
| cardsTotal_home | Total de cartões dos times da casa |
| cardsTotal_away | Total de cartões dos times visitantes |
| cardsRecorded_matches | Número de partidas com cartões registrados |
| over05Cards_overall — over75Cards_overall | Número de partidas com Over 0.5 a 7.5 cartões |
| over05CardsPercentage_overall — over75CardsPercentage_overall | % de partidas com Over 0.5 a 7.5 cartões |

### Faltas (Fouls)

| Variável | Descrição |
|---|---|
| foulsTotal_overall | Total de faltas na temporada |
| foulsTotal_home | Total de faltas dos times da casa |
| foulsTotal_away | Total de faltas dos times visitantes |
| foulsAVG_overall | Média de faltas por partida |
| foulsAVG_home | Média de faltas por partida do time da casa |
| foulsAVG_away | Média de faltas por partida do time visitante |
| foulsRecorded_matches | Partidas com faltas registradas |

### Chutes (Shots)

| Variável | Descrição |
|---|---|
| shotsTotal_overall | Total de chutes na temporada |
| shotsTotal_home | Total de chutes dos times da casa |
| shotsTotal_away | Total de chutes dos times visitantes |
| shotsAVG_overall | Média de chutes por partida |
| shotsAVG_home | Média de chutes por partida do time da casa |
| shotsAVG_away | Média de chutes por partida do time visitante |
| shotsRecorded_matches | Partidas com chutes registrados |

### Impedimentos (Offsides)

| Variável | Descrição |
|---|---|
| offsidesTotal_overall | Total de impedimentos na temporada |
| offsidesTotal_home | Total de impedimentos dos times da casa |
| offsidesTotal_away | Total de impedimentos dos times visitantes |
| offsidesAVG_overall | Média de impedimentos por partida |
| offsidesAVG_home | Média de impedimentos por partida do time da casa |
| offsidesAVG_away | Média de impedimentos por partida do time visitante |
| offsidesRecorded_matches | Partidas com impedimentos registrados |
| offsidesOver05_overall — offsidesOver65_overall | Partidas com Over 0.5 a 6.5 impedimentos |
| over05OffsidesPercentage_overall — over65OffsidesPercentage_overall | % de partidas com Over 0.5 a 6.5 impedimentos |

### Posse de Bola (Possession)

| Variável | Descrição |
|---|---|
| possession_overall | Posse de bola média geral |
| possession_home | Posse de bola média do time da casa |
| possession_away | Posse de bola média do time visitante |
| possessions_recorded_matches | Partidas com posse registrada |

### Over/Under Gols

| Variável | Descrição |
|---|---|
| seasonOver05Percentage_overall — seasonOver55Percentage_overall | % de partidas com Over 0.5 a 5.5 gols |
| seasonUnder05Percentage_overall — seasonUnder55Percentage_overall | % de partidas com Under 0.5 a 5.5 gols |
| seasonOver05_num — seasonOver55_num | Número de partidas com Over 0.5 a 5.5 gols |
| seasonUnder05_num — seasonUnder55_num | Número de partidas com Under 0.5 a 5.5 gols |

### Gols por Tempo (First Half / Second Half)

| Variável | Descrição |
|---|---|
| over05_fhg_num — over35_fhg_num | Partidas com Over 0.5 a 3.5 gols no 1º tempo |
| over05_fhg_percentage — over35_fhg_percentage | % de partidas com Over 0.5 a 3.5 gols no 1º tempo |
| over05_2hg_num — over35_2hg_num | Partidas com Over 0.5 a 3.5 gols no 2º tempo |
| over05_2hg_percentage — over35_2hg_percentage | % de partidas com Over 0.5 a 3.5 gols no 2º tempo |

### Gols por Intervalo de Tempo (Goal Timing)

| Variável | Descrição |
|---|---|
| goals_min_0_to_10 — goals_min_81_to_90 | Gols marcados em intervalos de 10 minutos |
| goals_min_0_to_15 — goals_min_76_to_90 | Gols marcados em intervalos de 15 minutos |
| goalTimingsRecorded_num | Número de partidas com tempos de gol registrados |

### Ataques e xG

| Variável | Descrição |
|---|---|
| attack_num_recoded_matches | Partidas com ataques registrados |
| dangerous_attacks_num | Total de ataques perigosos |
| attacks_num | Total de ataques |
| dangerous_attacks_avg | Média de ataques perigosos por partida |
| attacks_avg | Média de ataques por partida |
| xg_avg | Média de Expected Goals (xG) por partida |

### Dados Adicionais da Liga

| Variável | Descrição |
|---|---|
| seasonGoals_home | Timing de gols marcados pelo time da casa (Array) |
| seasonConceded_home | Timing de gols sofridos pelo time da casa (Array) |
| seasonGoals_away | Timing de gols marcados pelo time visitante |
| seasonConceded_away | Timing de gols sofridos pelo time visitante |
| round_obj | Objeto da rodada |
| type | Tipo da competição |
| matches | Array de partidas |
| clubs | Array de clubes |
| table_away | Tabela de classificação fora de casa |
| table_home | Tabela de classificação em casa |
| table | Tabela de classificação geral |
| footystats_url | URL da liga no FootyStats |

---

## TEAMS — Data Points

### Parâmetros de Consulta (Query Parameters)

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| key | string | Sim | Sua chave de API |
| team_id | integer | Sim | ID do time que deseja consultar |
| include | string | Não | Adicione `stats` para obter as estatísticas do time |

### Identificação e Metadados do Time

| Variável | Descrição |
|---|---|
| id | ID do time |
| original_id | ID original do time |
| name | Nome do time |
| cleanName | Nome limpo do time |
| full_name | Nome completo do time |
| english_name | Nome em inglês do time |
| alt_name1 / alt_name2 / alt_name3 | Nomes alternativos |
| shortHand | Abreviação do time |
| country | País do time |
| continent | Continente do time |
| founded | Ano de fundação |
| image | URL da imagem do time |
| image_thumb | URL do thumbnail da imagem |
| flag_element | Elemento de bandeira |
| season | Temporada mais recente |
| seasonClean | Temporada formatada |
| url | URL do time no FootyStats |
| seasonURL_overall / seasonURL_home / seasonURL_away | URLs da temporada (geral/casa/fora) |
| stadium_name | Nome do estádio |
| stadium_address | Endereço do estádio |
| previous_seasons | Temporadas anteriores |
| competition_id | ID da competição |
| season_format | Formato da temporada |
| dsg_id / tsapi_id / eo_id | IDs alternativos |
| verified | Se os dados são verificados |
| women | 1 = Time feminino, Null = Time masculino |
| home_venue_id | ID do local de jogos em casa |
| fansite_link1 / fansite_link2 / fansite_link3 | Links de fansites |
| officialsite_link1 / officialsite_link2 / officialsite_link3 | Links do site oficial |
| related_team_ids | IDs de times relacionados |
| parent_url | URL pai |
| additional_team_info | Informações adicionais do time |
| name_pt — name_fi | Nome do time em diversos idiomas |

### Vantagem Casa/Fora do Time

| Variável | Descrição |
|---|---|
| homeAttackAdvantage | Vantagem do time no ataque jogando em casa |
| homeDefenceAdvantage | Vantagem do time na defesa jogando em casa |
| homeOverallAdvantage | Vantagem geral do time jogando em casa |
| homeAttackAdvantageText | Texto descritivo da vantagem no ataque |
| homeDefenceAdvantageText | Texto descritivo da vantagem na defesa |
| homeOverallAdvantageText | Texto descritivo da vantagem geral |

### Forma Recente (Form)

| Variável | Descrição |
|---|---|
| formRun_overall / formRun_home / formRun_away | Sequência de resultados recentes (geral/casa/fora) |
| formRun_ht_overall / formRun_ht_home / formRun_ht_away | Sequência de resultados no intervalo |
| formRun_2hg_overall / formRun_2hg_home / formRun_2hg_away | Sequência de resultados no 2º tempo |
| currentFormHome / currentFormAway | Forma atual casa/fora |
| trueFormHome / trueFormAway | Forma verdadeira casa/fora |

### Gols — Estatísticas do Time

| Variável | Descrição |
|---|---|
| seasonGoals_overall / home / away | Gols marcados na temporada (geral/casa/fora) |
| seasonConceded_overall / home / away | Gols sofridos na temporada |
| seasonGoalsTotal_overall / home / away | Total de eventos de gol registrados |
| seasonScoredNum_overall / home / away | Número de gols marcados |
| seasonConcededNum_overall / home / away | Número de gols sofridos |
| seasonGoalsMin_overall / home / away | Média de gols por minuto |
| seasonScoredMin_overall / home / away | Média de gols marcados por minuto |
| seasonConcededMin_overall / home / away | Média de gols sofridos por minuto |
| seasonGoalDifference_overall / home / away | Saldo de gols |
| seasonGoalDifferenceText_overall / home / away | Texto do saldo de gols |
| seasonHighestScored_home / away | Maior número de gols marcados (casa/fora) |
| seasonHighestConceded_home / away | Maior número de gols sofridos (casa/fora) |

### Resultados do Time (Vitórias, Empates, Derrotas)

| Variável | Descrição |
|---|---|
| seasonWins_overall / home / away | Vitórias na temporada (texto) |
| seasonDraws_overall / home / away | Empates na temporada (texto) |
| seasonLosses_overall / home / away | Derrotas na temporada (texto) |
| seasonWinsNum_overall / home / away | Número de vitórias |
| seasonDrawsNum_overall / home / away | Número de empates |
| seasonLossesNum_overall / home / away | Número de derrotas |
| seasonMatchesPlayed_overall / home / away | Partidas jogadas |
| seasonAllMatches | Todas as partidas da temporada |
| seasonMatchObjects_overall / home / away | Objetos de partida |
| winPercentage_overall / home / away | % de vitórias |
| drawPercentage_overall / home / away | % de empates |
| losePercentage_overall / home / away | % de derrotas |

### Clean Sheets e Failed To Score

| Variável | Descrição |
|---|---|
| seasonCS_overall / home / away | Clean sheets na temporada |
| seasonCSPercentage_overall / home / away | % de clean sheets |
| seasonCSHT_overall / home / away | Clean sheets no intervalo |
| seasonCSPercentageHT_overall / home / away | % de clean sheets no intervalo |
| seasonFTS_overall / home / away | Failed To Score (não marcou) |
| seasonFTSPercentage_overall / home / away | % de Failed To Score |
| seasonFTSHT_overall / home / away | Failed To Score no intervalo |
| seasonFTSPercentageHT_overall / home / away | % de Failed To Score no intervalo |

### BTTS (Both Teams To Score) do Time

| Variável | Descrição |
|---|---|
| seasonBTTS_overall / home / away | BTTS na temporada |
| seasonBTTSPercentage_overall / home / away | % de BTTS |
| seasonBTTSHT_overall / home / away | BTTS no intervalo |
| seasonBTTSPercentageHT_overall / home / away | % de BTTS no intervalo |
| BTTS_and_win_overall / home / away | BTTS e vitória |
| BTTS_and_win_percentage_overall / home / away | % de BTTS e vitória |
| BTTS_and_draw_overall / home / away | BTTS e empate |
| BTTS_and_draw_percentage_overall / home / away | % de BTTS e empate |
| BTTS_and_lose_overall / home / away | BTTS e derrota |
| BTTS_and_lose_percentage_overall / home / away | % de BTTS e derrota |
| BTTS_both_halves_overall / home / away | BTTS em ambos os tempos |
| BTTS_both_halves_percentage_overall / home / away | % de BTTS em ambos os tempos |
| btts_2hg_overall / home / away | BTTS no 2º tempo |
| btts_2hg_percentage_overall / home / away | % de BTTS no 2º tempo |
| btts_fhg_overall / home / away | BTTS no 1º tempo |
| btts_fhg_percentage_overall / home / away | % de BTTS no 1º tempo |
| btts_1h2h_yes_yes_num_overall / home / away | BTTS 1º tempo sim & 2º tempo sim |
| btts_1h2h_yes_no_num_overall / home / away | BTTS 1º tempo sim & 2º tempo não |
| btts_1h2h_no_no_num_overall / home / away | BTTS 1º tempo não & 2º tempo não |
| btts_1h2h_no_yes_num_overall / home / away | BTTS 1º tempo não & 2º tempo sim |
| btts_1h2h_yes_yes_percentage_overall / home / away | % BTTS 1º tempo sim & 2º tempo sim |
| btts_1h2h_yes_no_percentage_overall / home / away | % BTTS 1º tempo sim & 2º tempo não |
| btts_1h2h_no_no_percentage_overall / home / away | % BTTS 1º tempo não & 2º tempo não |
| btts_1h2h_no_yes_percentage_overall / home / away | % BTTS 1º tempo não & 2º tempo sim |
| over25_and_btts_num_overall / home / away | Over 2.5 e BTTS |
| over25_and_btts_percentage_overall / home / away | % de Over 2.5 e BTTS |
| over25_and_no_btts_num_overall / home / away | Over 2.5 e sem BTTS |
| over25_and_no_btts_percentage_overall / home / away | % de Over 2.5 e sem BTTS |

### Pontos por Jogo (PPG)

| Variável | Descrição |
|---|---|
| seasonPPG_overall / home / away | Pontos por jogo (V=3, E=1) |
| seasonRecentPPG | PPG recente |
| seasonPPGProcessed_overall / home / away | PPG processado |

### Médias de Gols

| Variável | Descrição |
|---|---|
| seasonAVG_overall / home / away | Média de gols (marcados + sofridos) por jogo |
| seasonScoredAVG_overall / home / away | Média de gols marcados por jogo |
| seasonConcededAVG_overall / home / away | Média de gols sofridos por jogo |
| seasonAVGFormatted_overall / home / away | Média formatada |
| seasonScoredAVGFormatted_overall / home / away | Média de gols marcados formatada |
| seasonConcededAVGFormatted_overall / home / away | Média de gols sofridos formatada |

### Situação no Intervalo (Half-Time)

| Variável | Descrição |
|---|---|
| leadingAtHT_overall / home / away | Vezes vencendo no intervalo |
| leadingAtHTPercentage_overall / home / away | % vencendo no intervalo |
| drawingAtHT_overall / home / away | Vezes empatando no intervalo |
| drawingAtHTPercentage_overall / home / away | % empatando no intervalo |
| trailingAtHT_overall / home / away | Vezes perdendo no intervalo |
| trailingAtHTPercentage_overall / home / away | % perdendo no intervalo |
| HTPoints_overall / home / away | Pontos no intervalo |
| HTPPG_overall / home / away | Pontos por jogo no intervalo |
| HTPPGProcessed_overall / home / away | PPG no intervalo processado |

### Gols no Intervalo (Half-Time Goals)

| Variável | Descrição |
|---|---|
| scoredAVGHT_overall / home / away | Média de gols marcados no intervalo |
| concededAVGHT_overall / home / away | Média de gols sofridos no intervalo |
| AVGHT_overall / home / away | Média de gols totais no intervalo |
| scoredGoalsHT_overall / home / away | Total de gols marcados no intervalo |
| concededGoalsHT_overall / home / away | Total de gols sofridos no intervalo |
| GoalsHT_overall / home / away | Total de gols no intervalo |
| GoalDifferenceHT_overall / home / away | Saldo de gols no intervalo |
| GoalDifferenceTextHT_overall / home / away | Texto do saldo de gols no intervalo |

### Over/Under Gols do Time

| Variável | Descrição |
|---|---|
| seasonOver05_overall — seasonOver55_overall / home / away | Over 0.5 a 5.5 gols (texto) |
| seasonOver05Num_overall — seasonOver55Num_overall / home / away | Número de partidas com Over 0.5 a 5.5 gols |
| seasonOver05Percentage_overall — seasonOver55Percentage_overall / home / away | % de partidas com Over 0.5 a 5.5 gols |
| seasonUnder05_overall — seasonUnder55_overall / home / away | Under 0.5 a 5.5 gols (texto) |
| seasonUnder05Num_overall — seasonUnder55Num_overall / home / away | Número de partidas com Under 0.5 a 5.5 gols |
| seasonUnder05Percentage_overall — seasonUnder55Percentage_overall / home / away | % de partidas com Under 0.5 a 5.5 gols |
| seasonOver05PercentageHT_overall — seasonOver25PercentageHT_overall / home / away | % de Over 0.5 a 2.5 gols no intervalo |
| seasonOver05NumHT_overall — seasonOver25NumHT_overall / home / away | Número de Over 0.5 a 2.5 gols no intervalo |

### Gols Marcados/Sofridos Over

| Variável | Descrição |
|---|---|
| seasonScoredOver05Num_overall — seasonScoredOver35Num_overall / home / away | Partidas com Over 0.5 a 3.5 gols marcados |
| seasonScoredOver05PercentageNum_overall — seasonScoredOver35PercentageNum_overall / home / away | % de partidas com Over 0.5 a 3.5 gols marcados |
| seasonConcededOver05Num_overall — seasonConcededOver35Num_overall / home / away | Partidas com Over 0.5 a 3.5 gols sofridos |
| seasonConcededOver05PercentageNum_overall — seasonConcededOver35PercentageNum_overall / home / away | % de partidas com Over 0.5 a 3.5 gols sofridos |

### Escanteios do Time (Corners)

| Variável | Descrição |
|---|---|
| cornersRecorded_matches_overall / home / away | Partidas com escanteios registrados |
| cornersTotal_overall / home / away | Total de escanteios |
| cornersTotalAVG_overall / home / away | Média de escanteios totais por partida |
| cornersAVG_overall / home / away | Média de escanteios do time |
| cornersAgainst_overall / home / away | Escanteios contra |
| cornersAgainstAVG_overall / home / away | Média de escanteios contra |
| cornersHighest_overall | Maior número de escanteios |
| cornersLowest_overall | Menor número de escanteios |
| over65Corners_overall — over145Corners_overall / home / away | Partidas com Over 6.5 a 14.5 escanteios |
| over65CornersPercentage_overall — over145CornersPercentage_overall / home / away | % de partidas com Over 6.5 a 14.5 escanteios |
| over25CornersFor_overall — over85CornersFor_overall / home / away | Over 2.5 a 8.5 escanteios a favor |
| over25CornersForPercentage_overall — over85CornersForPercentage_overall / home / away | % de Over 2.5 a 8.5 escanteios a favor |
| over25CornersAgainst_overall — over85CornersAgainst_overall / home / away | Over 2.5 a 8.5 escanteios contra |
| over25CornersAgainstPercentage_overall — over85CornersAgainstPercentage_overall / home / away | % de Over 2.5 a 8.5 escanteios contra |
| cornerTimingRecorded_matches_overall / home / away | Partidas com timing de escanteios |
| corners_fh_overall / home / away | Escanteios no 1º tempo |
| corners_2h_overall / home / away | Escanteios no 2º tempo |
| corners_fh_avg_overall / home / away | Média de escanteios no 1º tempo |
| corners_2h_avg_overall / home / away | Média de escanteios no 2º tempo |
| corners_fh_over4_overall — corners_fh_over6_overall / home / away | Over 4-6 escanteios no 1º tempo |
| corners_2h_over4_overall — corners_2h_over6_overall / home / away | Over 4-6 escanteios no 2º tempo |
| corners_fh_over4_percentage_overall — corners_fh_over6_percentage_overall / home / away | % de Over 4-6 escanteios no 1º tempo |
| corners_2h_over4_percentage_overall — corners_2h_over6_percentage_overall / home / away | % de Over 4-6 escanteios no 2º tempo |
| corners_earned_1h_num_overall / home / away | Total de escanteios ganhos no 1º tempo |
| corners_earned_2h_num_overall / home / away | Total de escanteios ganhos no 2º tempo |
| corners_earned_1h_avg_overall / home / away | Média de escanteios ganhos no 1º tempo |
| corners_earned_2h_avg_overall / home / away | Média de escanteios ganhos no 2º tempo |
| corners_earned_1h_over2_num_overall / home / away | Over 2 escanteios ganhos no 1º tempo |
| corners_earned_2h_over2_num_overall / home / away | Over 2 escanteios ganhos no 2º tempo |
| corners_earned_1h_over3_num_overall / home / away | Over 3 escanteios ganhos no 1º tempo |
| corners_earned_2h_over3_num_overall / home / away | Over 3 escanteios ganhos no 2º tempo |
| corners_earned_1h_2_to_3_num_overall / home / away | 2 a 3 escanteios ganhos no 1º tempo |
| corners_earned_2h_2_to_3_num_overall / home / away | 2 a 3 escanteios ganhos no 2º tempo |
| team_with_most_corners_win_num_overall / home / away | Vezes com mais escanteios na partida |
| team_with_most_corners_win_1h_num_overall / home / away | Vezes com mais escanteios no 1º tempo |
| team_with_most_corners_win_2h_num_overall / home / away | Vezes com mais escanteios no 2º tempo |
| team_with_most_corners_win_percentage_overall / home / away | % com mais escanteios na partida |

### Cartões do Time (Cards)

| Variável | Descrição |
|---|---|
| cardsTotal_overall / home / away | Total de cartões |
| cardsAVG_overall / home / away | Média de cartões |
| cardsHighest_overall | Maior número de cartões |
| cardsLowest_overall | Menor número de cartões |
| over05Cards_overall — over85Cards_overall / home / away | Over 0.5 a 8.5 cartões |
| over05CardsPercentage_overall — over85CardsPercentage_overall / home / away | % de Over 0.5 a 8.5 cartões |
| over05CardsFor_overall — over65CardsFor_overall / home / away | Over 0.5 a 6.5 cartões a favor |
| over05CardsForPercentage_overall — over65CardsForPercentage_overall / home / away | % de Over 0.5 a 6.5 cartões a favor |
| over05CardsAgainst_overall — over65CardsAgainst_overall / home / away | Over 0.5 a 6.5 cartões contra |
| over05CardsAgainstPercentage_overall — over65CardsAgainstPercentage_overall / home / away | % de Over 0.5 a 6.5 cartões contra |
| cards_for_overall / home / away | Cartões a favor |
| cards_against_overall / home / away | Cartões contra |
| cards_for_avg_overall / home / away | Média de cartões a favor |
| cards_against_avg_overall / home / away | Média de cartões contra |
| cards_total_overall / home / away | Total de cartões |
| cards_total_avg_overall / home / away | Média total de cartões |
| cardsRecorded_matches_overall / home / away | Partidas com cartões registrados |
| cardTimingRecorded_matches_overall / home / away | Partidas com timing de cartões |
| fh_cards_total_overall / home / away | Total de cartões no 1º tempo |
| 2h_cards_total_overall / home / away | Total de cartões no 2º tempo |
| fh_cards_for_total_overall / home / away | Cartões a favor no 1º tempo |
| 2h_cards_for_total_overall / home / away | Cartões a favor no 2º tempo |
| fh_cards_against_total_overall / home / away | Cartões contra no 1º tempo |
| 2h_cards_against_total_overall / home / away | Cartões contra no 2º tempo |
| fh_total_cards_under2_percentage_overall / home / away | % Under 2 cartões no 1º tempo |
| 2h_total_cards_under2_percentage_overall / home / away | % Under 2 cartões no 2º tempo |
| fh_total_cards_2to3_percentage_overall / home / away | % 2 a 3 cartões no 1º tempo |
| 2h_total_cards_2to3_percentage_overall / home / away | % 2 a 3 cartões no 2º tempo |
| fh_total_cards_over3_percentage_overall / home / away | % Over 3 cartões no 1º tempo |
| 2h_total_cards_over3_percentage_overall / home / away | % Over 3 cartões no 2º tempo |
| fh_half_with_most_cards_total_percentage_overall / home / away | % 1º tempo com mais cartões |
| 2h_half_with_most_cards_total_percentage_overall / home / away | % 2º tempo com mais cartões |
| fh_cards_for_over05_percentage_overall / home / away | % Over 0.5 cartões a favor no 1º tempo |
| 2h_cards_for_over05_percentage_overall / home / away | % Over 0.5 cartões a favor no 2º tempo |

### Chutes do Time (Shots)

| Variável | Descrição |
|---|---|
| shotsTotal_overall / home / away | Total de chutes |
| shotsAVG_overall / home / away | Média de chutes |
| shotsOnTargetTotal_overall / home / away | Total de chutes no alvo |
| shotsOffTargetTotal_overall / home / away | Total de chutes para fora |
| shotsOnTargetAVG_overall / home / away | Média de chutes no alvo |
| shotsOffTargetAVG_overall / home / away | Média de chutes para fora |
| shots_recorded_matches_num_overall / home / away | Partidas com chutes registrados |
| shot_conversion_rate_overall / home / away | Taxa de conversão de chutes |
| match_shots_over225_num_overall — match_shots_over265_num_overall / home / away | Over 22.5 a 26.5 chutes na partida |
| match_shots_over225_percentage_overall — match_shots_over265_percentage_overall / home / away | % de Over 22.5 a 26.5 chutes |
| match_shots_on_target_over75_num_overall — match_shots_on_target_over95_num_overall / home / away | Over 7.5 a 9.5 chutes no alvo |
| match_shots_on_target_over75_percentage_overall — match_shots_on_target_over95_percentage_overall / home / away | % de Over 7.5 a 9.5 chutes no alvo |
| team_shots_over105_num_overall — team_shots_over155_num_overall / home / away | Over 10.5 a 15.5 chutes do time |
| team_shots_over105_percentage_overall — team_shots_over155_percentage_overall / home / away | % de Over 10.5 a 15.5 chutes do time |
| team_shots_on_target_over35_num_overall — team_shots_on_target_over65_num_overall / home / away | Over 3.5 a 6.5 chutes no alvo do time |
| team_shots_on_target_over35_percentage_overall — team_shots_on_target_over65_percentage_overall / home / away | % de Over 3.5 a 6.5 chutes no alvo do time |

### Posse de Bola e Faltas do Time

| Variável | Descrição |
|---|---|
| possessionAVG_overall / home / away | Média de posse de bola |
| foulsAVG_overall / home / away | Média de faltas |
| foulsTotal_overall / home / away | Total de faltas |
| fouls_recorded_overall / home / away | Faltas registradas |
| fouls_against_num_overall / home / away | Faltas sofridas |
| fouls_against_avg_overall / home / away | Média de faltas sofridas |

### Impedimentos do Time (Offsides)

| Variável | Descrição |
|---|---|
| offsidesTotal_overall / home / away | Total de impedimentos (ambos os times) |
| offsidesTeamTotal_overall / home / away | Total de impedimentos do time |
| offsidesRecorded_matches_overall / home / away | Partidas com impedimentos registrados |
| offsidesAVG_overall / home / away | Média de impedimentos |
| offsidesTeamAVG_overall / home / away | Média de impedimentos do time |
| offsidesOver05_overall — offsidesOver65_overall / home / away | Over 0.5 a 6.5 impedimentos |
| over05OffsidesPercentage_overall — over65OffsidesPercentage_overall / home / away | % de Over 0.5 a 6.5 impedimentos |
| offsidesTeamOver05_overall — offsidesTeamOver65_overall / home / away | Over 0.5 a 6.5 impedimentos do time |
| over05OffsidesTeamPercentage_overall — over65OffsidesTeamPercentage_overall / home / away | % de Over 0.5 a 6.5 impedimentos do time |

### Gols Marcados em Ambos os Tempos

| Variável | Descrição |
|---|---|
| scoredBothHalves_overall / home / away | Marcou em ambos os tempos |
| scoredBothHalvesPercentage_overall / home / away | % de marcou em ambos os tempos |

### Primeiro Gol

| Variável | Descrição |
|---|---|
| firstGoalScored_overall / home / away | Vezes que marcou o primeiro gol |
| firstGoalScoredPercentage_overall / home / away | % de vezes que marcou o primeiro gol |

### Estatísticas do 2º Tempo

| Variável | Descrição |
|---|---|
| AVG_2hg_overall / home / away | Média de gols totais no 2º tempo |
| scored_2hg_avg_overall / home / away | Média de gols marcados no 2º tempo |
| conceded_2hg_avg_overall / home / away | Média de gols sofridos no 2º tempo |
| total_2hg_overall / home / away | Total de gols no 2º tempo |
| conceded_2hg_overall / home / away | Total de gols sofridos no 2º tempo |
| scored_2hg_overall / home / away | Total de gols marcados no 2º tempo |
| over05_2hg_num_overall — over25_2hg_num_overall / home / away | Over 0.5 a 2.5 gols no 2º tempo |
| over05_2hg_percentage_overall — over25_2hg_percentage_overall / home / away | % de Over 0.5 a 2.5 gols no 2º tempo |
| points_2hg_overall / home / away | Pontos ganhos no 2º tempo |
| ppg_2hg_overall / home / away | Pontos por jogo no 2º tempo |
| ppg_2hg_processed_overall / home / away | PPG no 2º tempo processado |
| wins_2hg_overall / home / away | Vitórias no 2º tempo |
| wins_2hg_percentage_overall / home / away | % de vitórias no 2º tempo |
| draws_2hg_overall / home / away | Empates no 2º tempo |
| draws_2hg_percentage_overall / home / away | % de empates no 2º tempo |
| losses_2hg_overall / home / away | Derrotas no 2º tempo |
| losses_2hg_percentage_overall / home / away | % de derrotas no 2º tempo |
| gd_2hg_overall / home / away | Saldo de gols no 2º tempo |
| gd_text_2hg_overall / home / away | Texto do saldo de gols no 2º tempo |
| cs_2hg_overall / home / away | Clean sheets no 2º tempo |
| cs_2hg_percentage_overall / home / away | % de clean sheets no 2º tempo |
| fts_2hg_overall / home / away | Failed to score no 2º tempo |
| fts_2hg_percentage_overall / home / away | % de failed to score no 2º tempo |

### Metade com Mais Gols

| Variável | Descrição |
|---|---|
| half_with_most_goals_is_1h_num_overall / home / away | Vezes que o 1º tempo teve mais gols |
| half_with_most_goals_is_tie_num_overall / home / away | Vezes que houve empate entre tempos |
| half_with_most_goals_is_2h_num_overall / home / away | Vezes que o 2º tempo teve mais gols |
| half_with_most_goals_is_1h_percentage_overall / home / away | % 1º tempo com mais gols |
| half_with_most_goals_is_tie_percentage_overall / home / away | % empate entre tempos |
| half_with_most_goals_is_2h_percentage_overall / home / away | % 2º tempo com mais gols |

### Ataques e xG do Time

| Variável | Descrição |
|---|---|
| attack_num_recoded_matches_overall | Partidas com ataques registrados |
| dangerous_attacks_num_overall | Total de ataques perigosos |
| attacks_num_overall | Total de ataques |
| dangerous_attacks_avg_overall / home / away | Média de ataques perigosos |
| attacks_avg_overall / home / away | Média de ataques |
| xg_for_avg_overall / home / away | Média de xG a favor |
| xg_against_avg_overall / home / away | Média de xG contra |

### Pênaltis

| Variável | Descrição |
|---|---|
| penalties_won_overall / home / away | Pênaltis ganhos |
| penalties_scored_overall / home / away | Pênaltis convertidos |
| penalties_missed_overall / home / away | Pênaltis perdidos |
| penalties_won_per_match_overall / home / away | Pênaltis ganhos por partida |
| penalties_recorded_matches_overall / home / away | Partidas com pênaltis registrados |
| penalties_conceded_overall / home / away | Pênaltis concedidos |
| penalty_in_a_match_overall / home / away | Partidas com pelo menos 1 pênalti |
| penalty_in_a_match_percentage_overall / home / away | % de partidas com pênalti |

### Gols Exatos

| Variável | Descrição |
|---|---|
| exact_team_goals_0_ft_overall — exact_team_goals_3_ft_overall / home / away | Vezes que o time marcou exatamente 0 a 3 gols |
| exact_team_goals_0_ft_percentage_overall — exact_team_goals_3_ft_percentage_overall / home / away | % de 0 a 3 gols exatos |
| exact_total_goals_0_ft_overall — exact_total_goals_7_ft_overall / home / away | % de 0 a 7 gols totais exatos |

### Resultados por Intervalo de Tempo (10 min)

| Variável | Descrição |
|---|---|
| win_0_10_num_overall / home / away | Vitórias entre minuto 0 e 10 (foco apenas nos primeiros 10 min) |
| draw_0_10_num_overall / home / away | Empates entre minuto 0 e 10 |
| loss_0_10_num_overall / home / away | Derrotas entre minuto 0 e 10 |
| win_0_10_percentage_overall / home / away | % de vitórias entre minuto 0 e 10 |
| draw_0_10_percentage_overall / home / away | % de empates entre minuto 0 e 10 |
| loss_0_10_percentage_overall / home / away | % de derrotas entre minuto 0 e 10 |
| total_goal_over05_0_10_num_overall / home / away | Over 0.5 gols entre minuto 0 e 10 |
| total_corner_over05_0_10_num_overall / home / away | Over 0.5 escanteios entre minuto 0 e 10 |
| total_goal_over05_0_10_percentage_overall / home / away | % de Over 0.5 gols entre minuto 0 e 10 |
| total_corner_over05_0_10_percentage_overall / home / away | % de Over 0.5 escanteios entre minuto 0 e 10 |

### Gols por Intervalo de Tempo do Time

| Variável | Descrição |
|---|---|
| goals_scored_min_0_to_10 — goals_scored_min_81_to_90 | Gols marcados em intervalos de 10 min |
| goals_conceded_min_0_to_10 — goals_conceded_min_81_to_90 | Gols sofridos em intervalos de 10 min |
| goals_all_min_0_to_10 — goals_all_min_81_to_90 | Gols totais em intervalos de 10 min |
| goals_all_min_0_to_15 — goals_all_min_76_to_90 | Gols totais em intervalos de 15 min |
| goals_scored_min_0_to_15 — goals_scored_min_76_to_90 | Gols marcados em intervalos de 15 min |
| goals_conceded_min_0_to_15 — goals_conceded_min_76_to_90 | Gols sofridos em intervalos de 15 min |
| (Todas as variáveis acima também disponíveis com sufixo _home e _away) | Casa e fora separadamente |

### Tiros de Meta (Goal Kicks)

| Variável | Descrição |
|---|---|
| goal_kicks_recorded_matches_overall / home / away | Partidas com tiros de meta registrados |
| goal_kicks_team_num_overall / home / away | Tiros de meta do time |
| goal_kicks_total_num_overall / home / away | Total de tiros de meta (ambos os times) |
| goal_kicks_team_avg_overall / home / away | Média de tiros de meta do time |
| goal_kicks_total_avg_overall / home / away | Média total de tiros de meta |
| goal_kicks_team_over35_overall — goal_kicks_team_over115_overall / home / away | Over 3.5 a 11.5 tiros de meta do time |
| goal_kicks_total_over85_overall — goal_kicks_total_over185_overall / home / away | Over 8.5 a 18.5 tiros de meta totais |

### Arremessos Laterais (Throw-ins)

| Variável | Descrição |
|---|---|
| throwins_recorded_matches_overall / home / away | Partidas com arremessos laterais registrados |
| throwins_team_num_overall / home / away | Arremessos laterais do time |
| throwins_total_num_overall / home / away | Total de arremessos laterais |
| throwins_team_avg_overall / home / away | Média de arremessos laterais do time |
| throwins_total_avg_overall / home / away | Média total de arremessos laterais |
| throwins_team_over155_overall — throwins_team_over245_overall / home / away | Over 15.5 a 24.5 arremessos laterais do time |

### Risco e Previsão

| Variável | Descrição |
|---|---|
| risk | Risco de previsão (frequência com que o time marca ou sofre gols em proximidade) |
| prediction_risk | Risco de Previsão detalhado — representa a frequência com que um time marca ou sofre gols em proximidade temporal. Ex: se o time marca aos 55' e sofre aos 58', aumenta o risco. Quanto mais vezes isso acontece, maior o risco de gols inesperados |
| riskArray | Array de risco |
| riskTextProcessed | Texto de risco processado |
| riskNumProcessed | Número de risco processado |
| riskTableTextProcessed | Texto de risco da tabela processado |

### Posição e Performance

| Variável | Descrição |
|---|---|
| leaguePosition_overall / home / away | Posição na liga (geral/tabela casa/tabela fora) |
| table_position | Posição na tabela |
| performance_rank | Ranking de performance (PPG) na liga |
| additional_info | Informações adicionais |
| next_match | Próxima partida |
| suspended_matches | Partidas suspensas |
| average_attendance_overall / home / away | Público médio (geral/casa/fora) |

---

## PLAYERS — Data Points

### Parâmetros de Consulta

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| key | string | Sim | Sua chave de API |
| player_id | integer | Sim | ID do jogador que deseja consultar |

### Identificação do Jogador

| Variável | Descrição |
|---|---|
| id | ID do jogador |
| competition_id | ID da competição |
| full_name | Nome completo |
| first_name | Primeiro nome |
| last_name | Sobrenome |
| known_as | Nome conhecido |
| shorthand | Abreviação |
| age | Idade |
| height | Altura |
| weight | Peso |
| birthday | Data de nascimento |
| nationality | Nacionalidade |
| continent | Continente |

### Competição e Time

| Variável | Descrição |
|---|---|
| league | Liga |
| league_type | Tipo da liga |
| season | Temporada |
| starting_year | Ano de início |
| ending_year | Ano de término |
| url | URL do jogador no FootyStats |
| club_team_id | ID do time do clube |
| club_team_2_id | ID do segundo time do clube |
| national_team_id | ID da seleção nacional |
| position | Posição |

### Minutos Jogados

| Variável | Descrição |
|---|---|
| minutes_played_overall | Minutos jogados (geral) |
| minutes_played_home | Minutos jogados (casa) |
| minutes_played_away | Minutos jogados (fora) |

### Aparições

| Variável | Descrição |
|---|---|
| appearances_overall | Aparições (geral) |
| appearances_home | Aparições (casa) |
| appearances_away | Aparições (fora) |

### Gols e Assistências

| Variável | Descrição |
|---|---|
| goals_overall | Gols (geral) |
| goals_home | Gols (casa) |
| goals_away | Gols (fora) |
| assists_overall | Assistências (geral) |
| assists_home | Assistências (casa) |
| assists_away | Assistências (fora) |
| goals_involved_per_90_overall | Participações em gol por 90 min |
| assists_per_90_overall | Assistências por 90 min |
| goals_per_90_overall | Gols por 90 min |
| goals_per_90_home | Gols por 90 min (casa) |
| goals_per_90_away | Gols por 90 min (fora) |
| min_per_goal_overall | Minutos por gol |
| min_per_assist_overall | Minutos por assistência |

### Pênaltis

| Variável | Descrição |
|---|---|
| penalty_goals | Gols de pênalti |
| penalty_misses | Pênaltis perdidos |
| penalty_success | Taxa de sucesso em pênaltis |

### Defesa (Goleiros/Defensores)

| Variável | Descrição |
|---|---|
| clean_sheets_overall | Clean sheets (geral) |
| clean_sheets_home | Clean sheets (casa) |
| clean_sheets_away | Clean sheets (fora) |
| clean_sheets_per_overall | Clean sheets por partida |
| conceded_overall | Gols sofridos (geral) |
| conceded_home | Gols sofridos (casa) |
| conceded_away | Gols sofridos (fora) |
| conceded_per_90_overall | Gols sofridos por 90 min |
| min_per_conceded_overall | Minutos por gol sofrido |

### Cartões

| Variável | Descrição |
|---|---|
| cards_overall | Total de cartões |
| yellow_cards_overall | Cartões amarelos |
| red_cards_overall | Cartões vermelhos |
| min_per_card_overall | Minutos por cartão |
| cards_per_90_overall | Cartões por 90 min |
| min_per_match | Minutos por partida |

### Rankings

| Variável | Descrição |
|---|---|
| rank_in_league_top_attackers | Ranking entre os melhores atacantes da liga |
| rank_in_league_top_midfielders | Ranking entre os melhores meio-campistas da liga |
| rank_in_league_top_defenders | Ranking entre os melhores defensores da liga |
| rank_in_club_top_scorer | Ranking de artilheiro do clube |

### Outros

| Variável | Descrição |
|---|---|
| last_match_timestamp | Timestamp da última partida |

---

## Planos e Preços

| Plano | Preço | Ligas | Requisições |
|---|---|---|---|
| Free | Gratuito | Apenas Premier League | 180 / Hora |
| Hobby | £29,99 / Mês | 50 ligas à escolha | 1.800 / Hora |
| Serious | £69,99 / Mês | 150 ligas à escolha | 3.600 / Hora |
| Everything | £389,99 / Mês | Todas as 1.500+ ligas | 4.500 / Hora |

---

## Notas Importantes para Prognósticos Esportivos

### Convenção de Sufixos

Muitas variáveis seguem o padrão de sufixos para indicar o contexto:

| Sufixo | Significado |
|---|---|
| `_overall` | Todos os jogos (casa + fora) |
| `_home` | Apenas jogos em casa |
| `_away` | Apenas jogos fora de casa |

### Variáveis Mais Relevantes para Modelos de Prognóstico

As seguintes categorias de dados são especialmente úteis para modelos de previsão de futebol:

1. **Over/Under Goals:** `seasonOver25Percentage_overall`, `seasonAVG_overall`
2. **BTTS:** `seasonBTTSPercentage_overall`, `BTTS_and_win_percentage_overall`
3. **Resultado:** `winPercentage_overall`, `homeWinPercentage`, `awayWinPercentage`
4. **PPG:** `seasonPPG_overall`, `seasonRecentPPG`
5. **xG:** `xg_for_avg_overall`, `xg_against_avg_overall`
6. **Forma:** `formRun_overall`, `currentFormHome`, `currentFormAway`
7. **Escanteios:** `cornersAVG_overall`, `over95CornersPercentage_overall`
8. **Cartões:** `cardsAVG_overall`, `over35CardsPercentage_overall`
9. **Risco:** `prediction_risk`, `riskNum`
10. **Vantagem Casa:** `homeOverallAdvantage`, `homeAttackAdvantagePercentage`

---

> **Documento gerado em 24/02/2026 a partir da documentação oficial da FootyStats API.**
> **Fonte:** [https://footystats.org/api/](https://footystats.org/api/)
