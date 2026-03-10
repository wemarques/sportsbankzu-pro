# Análise: Como a API FootyStats Retorna Dados de Placar em Tempo Real

## Resumo Executivo

A API FootyStats (football-data-api.com) retorna dados de jogos ao vivo através do endpoint `/todays-matches`. O comportamento observado com `homeGoalCount: -1` **não é específico de jogos ao vivo**, mas sim um **padrão de valores padrão** usado pela API para indicar "dados não disponíveis" em diferentes campos.

---

## Endpoint Principal

**URL:** `GET https://api.football-data-api.com/todays-matches?key=YOURKEY`

### Parâmetros de Query

| Parâmetro | Tipo   | Descrição |
|-----------|--------|-----------|
| `key`*    | string | Sua chave de API (obrigatório) |
| `date`    | string | Formato: YYYY-MM-DD (ex: 2020-07-30). Padrão: data atual em UTC |
| `timezone`| string | Timezone (ex: Europe/London). Padrão: Etc/UTC |

### Limitações

- Retorna **máximo de 200 matches por página**
- Paginação habilitada por padrão (adicionar `&page=2` para próxima página)
- Você deve escolher as ligas em suas configurações para que os matches apareçam

---

## Estrutura de Resposta

### Exemplo de Resposta Completa

```json
{
    "success": true,
    "pager": {
        "current_page": 1,
        "max_page": 1,
        "results_per_page": 200,
        "total_results": 2
    },
    "data": [
        {
            "id": 579362,
            "homeID": 155,
            "awayID": 93,
            "season": "2019/2020",
            "status": "incomplete",
            "roundID": 50055,
            "game_week": 37,
            "revised_game_week": -1,
            "homeGoals": "[]",
            "awayGoals": "[]",
            "homeGoalCount": 0,
            "awayGoalCount": 0,
            "totalGoalCount": 0,
            "team_a_corners": -1,
            "team_b_corners": -1,
            "totalCornerCount": 0,
            "team_a_offsides": 0,
            "team_b_offsides": 0,
            "team_a_yellow_cards": 0,
            "team_b_yellow_cards": 0,
            "team_a_red_cards": 0,
            "team_b_red_cards": 0,
            "team_a_shotsOnTarget": -1,
            "team_b_shotsOnTarget": -1,
            "team_a_shotsOffTarget": -1,
            "team_b_shotsOffTarget": -1,
            "team_a_shots": -2,
            "team_b_shots": -2,
            "team_a_fouls": -1,
            "team_b_fouls": -1,
            "team_a_possession": -1,
            "team_b_possession": -1,
            "refereeID": -1,
            "coach_a_ID": -1,
            "coach_b_ID": -1,
            "stadium_name": "",
            "stadium_location": "",
            "team_a_cards_num": 0,
            "team_b_cards_num": 0,
            "odds_ft_1": 8.75,
            "odds_ft_x": 5.8,
            "odds_ft_2": 1.33
        }
    ]
}
```

---

## Campos de Dados e Valores Padrão

### Campos de Placar

| Campo | Tipo | Descrição | Valor Padrão |
|-------|------|-----------|--------------|
| `homeGoalCount` | integer | Gols marcados pelo time da casa | 0 ou -1 |
| `awayGoalCount` | integer | Gols marcados pelo time visitante | 0 ou -1 |
| `totalGoalCount` | integer | Total de gols no jogo | 0 |
| `homeGoals` | string | Timings dos gols do time da casa (array JSON) | "[]" |
| `awayGoals` | string | Timings dos gols do time visitante (array JSON) | "[]" |

### Campos de Estatísticas

| Campo | Descrição | Valor Padrão |
|-------|-----------|--------------|
| `team_a_corners` | Escanteios do time da casa | **-1** |
| `team_b_corners` | Escanteios do time visitante | **-1** |
| `team_a_offsides` | Impedimentos do time da casa | 0 |
| `team_b_offsides` | Impedimentos do time visitante | 0 |
| `team_a_yellow_cards` | Cartões amarelos do time da casa | 0 |
| `team_b_yellow_cards` | Cartões amarelos do time visitante | 0 |
| `team_a_red_cards` | Cartões vermelhos do time da casa | 0 |
| `team_b_red_cards` | Cartões vermelhos do time visitante | 0 |
| `team_a_shotsOnTarget` | Chutes no alvo do time da casa | **-1** |
| `team_b_shotsOnTarget` | Chutes no alvo do time visitante | **-1** |
| `team_a_shotsOffTarget` | Chutes fora do alvo do time da casa | **-1** |
| `team_b_shotsOffTarget` | Chutes fora do alvo do time visitante | **-1** |
| `team_a_shots` | Total de chutes do time da casa | **-2** |
| `team_b_shots` | Total de chutes do time visitante | **-2** |
| `team_a_fouls` | Faltas do time da casa | **-1** |
| `team_b_fouls` | Faltas do time visitante | **-1** |
| `team_a_possession` | Posse de bola do time da casa (%) | **-1** |
| `team_b_possession` | Posse de bola do time visitante (%) | **-1** |

### Campos de Metadados

| Campo | Descrição | Valor Padrão |
|-------|-----------|--------------|
| `revised_game_week` | Rodada revisada | **-1** |
| `refereeID` | ID do árbitro | **-1** |
| `coach_a_ID` | ID do técnico do time da casa | **-1** |
| `coach_b_ID` | ID do técnico do time visitante | **-1** |
| `stadium_name` | Nome do estádio | "" (string vazia) |
| `stadium_location` | Localização do estádio | "" (string vazia) |

---

## Padrão de Valores Padrão

A API FootyStats utiliza um **sistema de valores padrão consistente** para indicar "dados não disponíveis":

### Valores Padrão Utilizados

| Valor | Significado | Campos Afetados |
|-------|-------------|-----------------|
| **-1** | Dados não disponíveis | Corners, shots on target, fouls, possession, IDs, revised_game_week |
| **-2** | Dados não disponíveis (variante) | Total shots |
| **0** | Sem dados ou zero ocorrências | Goal counts, offsides, cards, corner count |
| **""** | String vazia | Stadium name, stadium location |
| **"[]"** | Array JSON vazio | Goal timings |

---

## Comportamento em Tempo Real

### Status do Jogo

O campo `status` indica o estado atual do jogo:

- `"incomplete"` - Jogo ainda não iniciou ou está em andamento
- `"complete"` - Jogo finalizado
- Outros valores possíveis dependem da fonte de dados

### Quando os Dados são Atualizados

**Durante jogos ao vivo:**

1. **Placar (homeGoalCount, awayGoalCount)**: Atualizado em tempo real conforme gols são marcados
2. **Estatísticas (corners, shots, etc.)**: Podem retornar `-1` se o provedor de dados não tiver acesso em tempo real
3. **Cartões e Impedimentos**: Geralmente atualizados em tempo real

### Dados Indisponíveis em Tempo Real

Alguns campos frequentemente retornam valores padrão durante jogos ao vivo:

- `team_a_possession` / `team_b_possession`: Podem retornar `-1` se não disponível
- `team_a_shotsOnTarget` / `team_b_shotsOnTarget`: Podem retornar `-1` se não disponível
- `team_a_shots` / `team_b_shots`: Podem retornar `-2` se não disponível
- `team_a_corners` / `team_b_corners`: Podem retornar `-1` se não disponível

---

## Interpretação do Campo `homeGoalCount: -1`

### Contexto Original

Você mencionou que a API retorna `homeGoalCount: -1` para jogos ao vivo, significando "sem dados". 

**Análise:**

1. **Não é o padrão documentado**: Na documentação oficial, `homeGoalCount` retorna `0` quando não há gols (veja exemplo acima)
2. **Possíveis cenários**:
   - Jogo não iniciou ainda (status: "incomplete")
   - Dados não sincronizados com o provedor
   - Jogo em estado de transição (pré-jogo para ao vivo)
   - Provedor de dados não tem acesso ao placar em tempo real

3. **Recomendação de tratamento**:
   ```javascript
   // Tratamento recomendado
   const homeGoals = (match.homeGoalCount === -1 || match.homeGoalCount === null) 
       ? 0 
       : match.homeGoalCount;
   ```

---

## Recomendações para Exibição em Tempo Real

### 1. Tratamento de Valores Padrão

```javascript
function parseMatchData(match) {
    return {
        homeGoals: match.homeGoalCount >= 0 ? match.homeGoalCount : 'N/A',
        awayGoals: match.awayGoalCount >= 0 ? match.awayGoalCount : 'N/A',
        corners: {
            home: match.team_a_corners >= 0 ? match.team_a_corners : 'N/A',
            away: match.team_b_corners >= 0 ? match.team_b_corners : 'N/A'
        },
        possession: {
            home: match.team_a_possession >= 0 ? match.team_a_possession + '%' : 'N/A',
            away: match.team_b_possession >= 0 ? match.team_b_possession + '%' : 'N/A'
        },
        shots: {
            home: match.team_a_shots > -2 ? match.team_a_shots : 'N/A',
            away: match.team_b_shots > -2 ? match.team_b_shots : 'N/A'
        }
    };
}
```

### 2. Indicador de Dados Disponíveis

```javascript
function isDataAvailable(match) {
    return {
        liveScore: match.homeGoalCount >= 0 && match.awayGoalCount >= 0,
        corners: match.team_a_corners >= 0 && match.team_b_corners >= 0,
        possession: match.team_a_possession >= 0 && match.team_b_possession >= 0,
        shots: match.team_a_shots > -2 && match.team_b_shots > -2
    };
}
```

### 3. Polling para Atualização

```javascript
async function fetchLiveMatches(interval = 5000) {
    setInterval(async () => {
        const response = await fetch(
            'https://api.football-data-api.com/todays-matches?key=YOUR_KEY'
        );
        const data = await response.json();
        
        // Atualizar UI com novos dados
        updateMatchDisplay(data.data);
    }, interval);
}
```

---

## Conclusão

A API FootyStats retorna dados de placar em tempo real através do endpoint `/todays-matches`, com o seguinte comportamento:

1. **Placar (goals)**: Atualizado em tempo real, retorna `0` ou `-1` se não disponível
2. **Estatísticas**: Frequentemente retornam valores padrão (`-1`, `-2`) durante jogos ao vivo
3. **Padrão consistente**: A API usa valores negativos para indicar "dados não disponíveis"
4. **Recomendação**: Sempre validar valores antes de exibir, tratando `-1` e `-2` como "N/A" ou "Indisponível"

Para exibição em tempo real, recomenda-se fazer polling a cada 5-10 segundos e tratar valores padrão apropriadamente.


---

## Endpoint Adicional: Match Details

Para obter informações mais detalhadas sobre um jogo específico, incluindo estatísticas completas, existe o endpoint `/match`:

**URL:** `GET https://api.football-data-api.com/match?key=YOURKEY&match_id=1`

### Parâmetros

| Parâmetro | Tipo    | Descrição |
|-----------|---------|-----------|
| `key`*    | string  | Sua chave de API (obrigatório) |
| `match_id`*| integer | ID do jogo (obrigatório) |

### Diferenças entre Endpoints

| Aspecto | Today's Matches | Match Details |
|--------|-----------------|---------------|
| **Dados retornados** | Múltiplos jogos do dia | Um jogo específico |
| **Estatísticas** | Básicas | Completas (H2H, Trends, Odds) |
| **Timings de gols** | Array simples | Array com minutos exatos |
| **Dados adicionais** | Mínimos | Presença, lineups, XG, etc. |

### Exemplo de Resposta - Match Details (Jogo Completo)

```json
{
    "id": 579101,
    "homeID": 251,
    "awayID": 145,
    "season": "2019/2020",
    "status": "complete",
    "homeGoals": ["17", "43", "44"],
    "awayGoals": [],
    "homeGoalCount": 3,
    "awayGoalCount": 0,
    "totalGoalCount": 3,
    "team_a_corners": 7,
    "team_b_corners": 6,
    "team_a_shotsOnTarget": 7,
    "team_b_shotsOnTarget": 0,
    "team_a_possession": 45,
    "team_b_possession": 55,
    "attendance": 31131,
    "team_a_xg": 1.72,
    "team_b_xg": 0.77
}
```

**Observação importante:** Neste exemplo de jogo completo, todos os campos têm valores reais (sem -1 ou -2), indicando que os dados estão completos.

---

## Comparação: Today's Matches vs Match Details

### Today's Matches (Exemplo de Jogo Incompleto)

```json
{
    "homeGoalCount": 0,
    "awayGoalCount": 0,
    "team_a_corners": -1,
    "team_b_corners": -1,
    "team_a_possession": -1,
    "team_b_possession": -1,
    "team_a_shots": -2,
    "team_b_shots": -2
}
```

**Interpretação:** Jogo ainda não iniciou ou dados não sincronizados.

### Match Details (Jogo Completo)

```json
{
    "homeGoalCount": 3,
    "awayGoalCount": 0,
    "team_a_corners": 7,
    "team_b_corners": 6,
    "team_a_possession": 45,
    "team_b_possession": 55,
    "team_a_shots": 14,
    "team_b_shots": 6
}
```

**Interpretação:** Jogo finalizado com dados completos.

---

## Recomendação Final para Exibição em Tempo Real

Para uma aplicação que exibe placar em tempo real, recomenda-se:

### 1. **Usar Today's Matches para lista de jogos**
   - Mais leve e rápido
   - Ideal para dashboard com múltiplos jogos
   - Atualizar a cada 5-10 segundos

### 2. **Usar Match Details para detalhes completos**
   - Quando usuário clica em um jogo específico
   - Para exibir estatísticas detalhadas
   - Menos frequente (a cada 30-60 segundos)

### 3. **Tratamento de Valores Padrão**

```javascript
function formatLiveScore(match) {
    return {
        // Placar sempre disponível
        score: `${match.homeGoalCount >= 0 ? match.homeGoalCount : 0} - ${match.awayGoalCount >= 0 ? match.awayGoalCount : 0}`,
        
        // Estatísticas com fallback
        stats: {
            corners: match.team_a_corners >= 0 
                ? `${match.team_a_corners} - ${match.team_b_corners}` 
                : 'N/A',
            
            possession: match.team_a_possession >= 0 
                ? `${match.team_a_possession}% - ${match.team_b_possession}%` 
                : 'N/A',
            
            shots: match.team_a_shots > -2 
                ? `${match.team_a_shots} - ${match.team_b_shots}` 
                : 'N/A'
        },
        
        // Indicador de dados disponíveis
        dataQuality: {
            hasCorners: match.team_a_corners >= 0,
            hasPossession: match.team_a_possession >= 0,
            hasShots: match.team_a_shots > -2
        }
    };
}
```

### 4. **Polling Recomendado**

```javascript
// Para Today's Matches (lista)
const LIVE_POLL_INTERVAL = 5000; // 5 segundos

// Para Match Details (detalhes)
const DETAIL_POLL_INTERVAL = 30000; // 30 segundos

// Para jogos finalizados
const FINISHED_POLL_INTERVAL = 300000; // 5 minutos
```

---

## Conclusão Atualizada

A API FootyStats oferece dois endpoints principais para dados de jogos:

1. **`/todays-matches`**: Ideal para listas em tempo real, com valores padrão (-1, -2) indicando dados não disponíveis
2. **`/match`**: Ideal para detalhes completos de um jogo específico, com dados mais ricos

O comportamento de `homeGoalCount: -1` é **não é padrão** para este campo especificamente, mas faz parte do **padrão geral de valores padrão** da API para indicar "dados não disponíveis" em diversos campos de estatísticas.

Para uma aplicação de exibição de placar em tempo real, recomenda-se:
- Usar `/todays-matches` com polling a cada 5-10 segundos
- Validar e tratar valores padrão (-1, -2) apropriadamente
- Exibir "N/A" ou "Indisponível" para dados não disponíveis
- Usar `/match` para detalhes quando necessário
