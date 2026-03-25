# PROMPT — Enriquecer Prompt da Mistral com Cartões, Escanteios Completos e Stats de Liga

## PROBLEMA

A Mistral não recebe dados de cartões, faltas, clean sheets, percentuais por time (Over 25%, BTTS%, FTS%) nem médias da liga. Esses dados EXISTEM no `stats` dict que chega na função `analyze_match()` — simplesmente não são incluídos no prompt.

Dados disponíveis no `stats` mas NÃO enviados à Mistral:

| Campo | Descrição | Impacto |
|-------|-----------|---------|
| `homeCardsPerMatch` / `awayCardsPerMatch` | Cartões por jogo | Mercado de cartões + indicador de agressividade |
| `homeFoulsPerMatch` / `awayFoulsPerMatch` | Faltas por jogo | Correlação com cartões e escanteios |
| `leagueAvgCorners` | Média de escanteios da liga | Contexto para corners |
| `leagueAvgCards` | Média de cartões da liga | Contexto para cards |
| `leagueAvgFouls` | Média de faltas da liga | Contexto geral |
| `homeCleanSheetPct` / `awayCleanSheetPct` | % Clean Sheet | BTTS e Under analysis |
| `homeFtsPercentage` / `awayFtsPercentage` | % Failed To Score | BTTS NO e Under |
| `homeBttsPercentage` / `awayBttsPercentage` | % BTTS do time | BTTS direto |
| `homeOver25Percentage` / `awayOver25Percentage` | % Over 2.5 do time | Over/Under |
| `homeWinPercentage` / `awayWinPercentage` | % Vitória do time | 1X2 context |
| `homeXgAgainstAvg` / `awayXgAgainstAvg` | xG sofrido | Força defensiva |
| `homeLeaguePosition` / `awayLeaguePosition` | Posição na liga | Contexto |
| `cornerOver85Prob` / `cornerOver95Prob` / `cornerOver105Prob` | Potenciais corners FootyStats | Projeção de corners |
| `leagueCleanSheetsPct` / `leagueOver25Pct` | Médias da liga | Contexto |
| `homeAvgTotalGoals` / `awayAvgTotalGoals` | Média total gols/jogo do time | Gols |

## ARQUIVO A MODIFICAR

`backend/ai/match_analysis_service.py`

---

## CORREÇÃO — Expandir prompt com todos os dados disponíveis

Na função `analyze_match()`, substituir o bloco "DADOS AVANCADOS DO SISTEMA:" (~linhas 72-86) por um bloco mais completo.

Substituir as linhas 72-86 (de `DADOS AVANCADOS DO SISTEMA:` até o fechamento das aspas `"""`) por:

```python
DADOS AVANCADOS DO SISTEMA:

OFENSIVOS:
- xG Casa: {stats.get('homeXgForAvg', 'N/A')}
- xG Fora: {stats.get('awayXgForAvg', 'N/A')}
- xG Sofrido Casa: {stats.get('homeXgAgainstAvg', 'N/A')}
- xG Sofrido Fora: {stats.get('awayXgAgainstAvg', 'N/A')}
- Chutes/Jogo Casa: {stats.get('homeShotsPerMatch', 'N/A')}
- Chutes/Jogo Fora: {stats.get('awayShotsPerMatch', 'N/A')}
- Chutes no Alvo Casa: {stats.get('homeShotsOnTarget', 'N/A')}
- Chutes no Alvo Fora: {stats.get('awayShotsOnTarget', 'N/A')}
- Media Total Gols/Jogo Casa: {stats.get('homeAvgTotalGoals', 'N/A')}
- Media Total Gols/Jogo Fora: {stats.get('awayAvgTotalGoals', 'N/A')}

DEFENSIVOS:
- Clean Sheet Casa: {stats.get('homeCleanSheetPct', 'N/A')}%
- Clean Sheet Fora: {stats.get('awayCleanSheetPct', 'N/A')}%
- Failed To Score Casa: {stats.get('homeFtsPercentage', 'N/A')}%
- Failed To Score Fora: {stats.get('awayFtsPercentage', 'N/A')}%

PERCENTUAIS POR TIME:
- Vitoria Casa: {stats.get('homeWinPercentage', 'N/A')}%
- Vitoria Fora: {stats.get('awayWinPercentage', 'N/A')}%
- Over 2.5 Casa: {stats.get('homeOver25Percentage', 'N/A')}%
- Over 2.5 Fora: {stats.get('awayOver25Percentage', 'N/A')}%
- BTTS Casa: {stats.get('homeBttsPercentage', 'N/A')}%
- BTTS Fora: {stats.get('awayBttsPercentage', 'N/A')}%

ESCANTEIOS:
- Escanteios/Jogo Casa: {stats.get('homeCornersPerMatch', 'N/A')}
- Escanteios/Jogo Fora: {stats.get('awayCornersPerMatch', 'N/A')}
- Escanteios Contra Casa: {stats.get('homeCornersAgainstPerMatch', 'N/A')}
- Escanteios Contra Fora: {stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Potencial Over 8.5 Corners: {stats.get('cornerOver85Prob', 'N/A')}%
- Potencial Over 9.5 Corners: {stats.get('cornerOver95Prob', 'N/A')}%
- Potencial Over 10.5 Corners: {stats.get('cornerOver105Prob', 'N/A')}%

CARTOES E FALTAS:
- Cartoes/Jogo Casa: {stats.get('homeCardsPerMatch', 'N/A')}
- Cartoes/Jogo Fora: {stats.get('awayCardsPerMatch', 'N/A')}
- Faltas/Jogo Casa: {stats.get('homeFoulsPerMatch', 'N/A')}
- Faltas/Jogo Fora: {stats.get('awayFoulsPerMatch', 'N/A')}

POSSE E CONTROLE:
- Posse Casa: {stats.get('homePossession', 'N/A')}%
- Posse Fora: {stats.get('awayPossession', 'N/A')}%

MEDIAS DA LIGA:
- Media Gols Liga: {stats.get('leagueAvgGoals', 'N/A')}
- Media Escanteios Liga: {stats.get('leagueAvgCorners', 'N/A')}
- Media Cartoes Liga: {stats.get('leagueAvgCards', 'N/A')}
- Media Faltas Liga: {stats.get('leagueAvgFouls', 'N/A')}
- Clean Sheets Liga: {stats.get('leagueCleanSheetsPct', 'N/A')}%
- Over 2.5 Liga: {stats.get('leagueOver25Pct', 'N/A')}%
- xG Medio Liga: {stats.get('leagueXgAvg', 'N/A')}
- Vantagem Casa Liga: {stats.get('leagueHomeAdvantage', 'N/A')}%

POSICAO NA LIGA:
- Posicao Casa: {stats.get('homeLeaguePosition', 'N/A')}
- Posicao Fora: {stats.get('awayLeaguePosition', 'N/A')}

INDICADORES DO SISTEMA:
- Chaos Detectado: {stats.get('chaosDetected', False)}
- Regime da Liga: {stats.get('leagueRegime', 'N/A')}
- Volatilidade: {stats.get('leagueVolatility', 'N/A')}
```

---

## ATUALIZAR INSTRUÇÃO FINAL DO PROMPT

Substituir o bloco de instruções finais (~linhas 139-161) para que a Mistral considere os novos dados:

```python
    prompt += """
Com base nesses dados, forneca uma analise OBJETIVA no seguinte formato JSON:

{
  "summary": "Resumo de 2-3 frases cobrindo: resultado provavel, tendencia de gols, e destaque de escanteios ou cartoes se relevante",
  "key_points": [
    "Ponto sobre resultado 1X2 (usar win%, posicao na liga, forma)",
    "Ponto sobre gols Over/Under (usar lambda, Over 2.5%, media total gols)",
    "Ponto sobre BTTS (usar BTTS%, clean sheet%, FTS%)",
    "Ponto sobre escanteios (usar corners/jogo, corners contra, potenciais, media liga)",
    "Ponto sobre cartoes e disciplina (usar cards/jogo, fouls/jogo, media liga) OU valor nas odds"
  ],
  "recommendation": "Recomendacao com mercado e odd REAL. Pode ser gols, BTTS, escanteios ou cartoes. NUNCA invente odds. Use APENAS as odds fornecidas nos dados.",
  "confidence": 75
}

REGRAS:
- Use APENAS odds fornecidas nos dados acima. NUNCA invente odds.
- Se dados de escanteios estiverem disponiveis (nao N/A), INCLUA analise de corners nos pontos-chave.
- Se dados de cartoes estiverem disponiveis (nao N/A), INCLUA analise de disciplina.
- Compare os dados do time com as medias da liga para contextualizar.
- Se o sistema detectou chaos, mencione como fator de risco.
- Se houver lesoes de jogadores-chave, avalie o impacto.
- Se Clean Sheet% for alto para algum time, destaque no contexto de BTTS.
- Se Failed To Score% for alto, destaque no contexto de Under.
- Retorne APENAS o JSON, sem texto adicional.
"""
```

---

## VALIDAÇÃO

```bash
pytest -q
cd frontend/next && npm run build
```

Verificar na análise Mistral de um jogo:
1. Resumo deve mencionar escanteios e/ou cartões quando dados existem
2. Pontos-chave devem ter ponto sobre corners (ex: "Corners/jogo do Kayserispor: 5.2 vs média da liga 10.0")
3. Pontos-chave devem ter ponto sobre disciplina (ex: "Cartões/jogo do Grêmio: 2.8 acima da média da liga 4.0")
4. Recomendação pode incluir mercado de escanteios se tiver EV positivo

Commit:
```
feat: enrich Mistral prompt with cards, fouls, clean sheets, league averages, team percentages

- Add: cards/match, fouls/match for both teams
- Add: clean sheet %, FTS %, BTTS %, Over 2.5 %, win % per team
- Add: xG against avg, shots on target, avg total goals per team
- Add: league averages (corners, cards, fouls, clean sheets, Over 2.5, xG)
- Add: league position, corner potentials (O8.5/9.5/10.5)
- Add: home advantage %, league goals home/away split
- Update: prompt instructions to require corners and cards analysis
- Total: ~40 new data fields sent to Mistral (were available but unused)
```

Push:
```bash
git push origin main
```

---

## REGRAS

- Modificar APENAS `backend/ai/match_analysis_service.py`
- NÃO alterar os dados que o backend calcula (fixtures_service.py)
- NÃO alterar o formato de resposta da Mistral (summary, key_points, recommendation, confidence)
- Todos os novos campos usam `stats.get('campo', 'N/A')` — se o dado não existir, mostra N/A
- Se `pytest -q` falhar, corrigir antes de commitar
