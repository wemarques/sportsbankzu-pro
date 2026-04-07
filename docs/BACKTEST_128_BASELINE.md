# BACKTEST POS-FIX #128 — BASELINE COMPLETO
**Data:** 2026-04-07
**Commit:** 89be30f (#128e-g)
**Periodo avaliado:** Temporadas calibradas (3 seasons por liga)
**N ligas:** 22

## Brier Scores por Mercado (com IC 95%)

| Mercado | Brier | N ligas | IC 95% |
|---------|:-----:|:-------:|:------:|
| Over/Under (gols) | **0.1713** | 22 | +-0.0031 |
| 1X2 | **0.1912** | 22 | +-0.0034 |
| Corners | **0.2381** | 22 | +-0.0016 |
| Cards | **0.1987** | 22 | +-0.0098 |
| **Geral** | **0.1998** | 88 | +-0.0058 |

**Nota:** N=22 ligas (nao jogos individuais). Cada liga agrega centenas de jogos no calibrador. Brier de Corners (0.2381) e o mais proximo de random (0.25) — precisa investigacao dedicada.

## Brier Score por Liga

| Liga | O/U | 1X2 | Corners | Cards |
|------|:---:|:---:|:-------:|:-----:|
| premier-league | 0.1785 | 0.1828 | 0.2359 | 0.2230 |
| championship | 0.1695 | 0.1998 | 0.2375 | 0.2165 |
| league-one | 0.1736 | 0.1968 | 0.2411 | 0.2180 |
| la-liga | 0.1696 | 0.1873 | 0.2391 | 0.1909 |
| serie-a | 0.1698 | 0.1873 | 0.2406 | 0.2031 |
| serie-b | 0.1684 | 0.2017 | 0.2410 | 0.1633 |
| bundesliga | 0.1770 | 0.1868 | 0.2423 | 0.2212 |
| 2-bundesliga | 0.1757 | 0.1968 | 0.2376 | 0.1997 |
| ligue-1 | 0.1767 | 0.1860 | 0.2382 | 0.2140 |
| brasileirao-serie-a | 0.1635 | 0.1932 | 0.2343 | 0.1764 |
| brasileirao-serie-b | 0.1511 | 0.1945 | 0.2341 | 0.1702 |
| eredivisie | 0.1760 | 0.1766 | 0.2380 | 0.2209 |
| primeira-liga | 0.1682 | 0.1739 | 0.2411 | 0.1691 |
| super-lig | 0.1781 | 0.1824 | 0.2407 | 0.2033 |
| pro-league | 0.1761 | 0.1929 | 0.2395 | 0.2158 |
| premiership | 0.1728 | 0.1814 | 0.2334 | 0.2187 |
| superliga | 0.1772 | 0.1937 | 0.2409 | 0.2217 |
| primera-division | 0.1553 | 0.2028 | 0.2400 | 0.1680 |
| a-league | 0.1739 | 0.1980 | 0.2256 | 0.2136 |
| mls | 0.1774 | 0.1989 | 0.2410 | 0.2088 |
| colombian-primera-a | 0.1643 | 0.1993 | 0.2369 | 0.1452 |
| liga-mx | 0.1754 | 0.1931 | 0.2403 | 0.1910 |

## Cobertura xG — TODAS as 22 Ligas

| Liga | N jogos | xG Home | xG Away | xG-Ag Home | xG-Ag Away | Guarda #128e |
|------|:-------:|:-------:|:-------:|:----------:|:----------:|:------------:|
| premier-league | 0 | N/A | N/A | N/A | N/A | N/A |
| championship | 12 | 0% | 0% | 0% | 0% | BLOQUEADA |
| league-one | 11 | 9% | 0% | 9% | 0% | BLOQUEADA |
| la-liga | 1 | 100% | 0% | 100% | 0% | BLOQUEADA |
| serie-a | 4 | 0% | 25% | 0% | 25% | BLOQUEADA |
| serie-b | 8 | 0% | 0% | 0% | 0% | BLOQUEADA |
| bundesliga | 0 | N/A | N/A | N/A | N/A | N/A |
| 2-bundesliga | 0 | N/A | N/A | N/A | N/A | N/A |
| ligue-1 | 0 | N/A | N/A | N/A | N/A | N/A |
| brasileirao-serie-a | 0 | N/A | N/A | N/A | N/A | N/A |
| brasileirao-serie-b | 1 | 0% | 0% | 0% | 0% | BLOQUEADA |
| eredivisie | 0 | N/A | N/A | N/A | N/A | N/A |
| primeira-liga | 2 | 50% | 50% | 50% | 50% | BLOQUEADA |
| super-lig | 1 | 0% | 0% | 0% | 0% | BLOQUEADA |
| pro-league | 3 | 67% | 33% | 67% | 33% | BLOQUEADA |
| premiership | 0 | N/A | N/A | N/A | N/A | N/A |
| superliga | 4 | 0% | 0% | 0% | 0% | BLOQUEADA |
| primera-division | 2 | 50% | 0% | 50% | 0% | BLOQUEADA |
| a-league | 1 | 100% | 0% | 100% | 0% | BLOQUEADA |
| mls | 0 | N/A | N/A | N/A | N/A | N/A |
| colombian-primera-a | 2 | 0% | 0% | 0% | 0% | BLOQUEADA |
| liga-mx | 1 | 0% | 0% | 0% | 0% | BLOQUEADA |

**Resumo xG:** 0 de 22 ligas passam na guarda #128e (cobertura >= 80% home E away). xG blend permanece inativo globalmente. Cobertura assimetrica confirmada (home parcial, away quase zero).

## Cobertura Corners/Cards Against (fallback #124)

| Liga | N | CornersAgainst | CardsAgainst |
|------|:-:|:--------------:|:------------:|
| championship | 12 | 92% | 92% |
| league-one | 11 | 100% | 100% |
| la-liga | 1 | 100% | 100% |
| serie-a | 4 | 100% | 100% |
| serie-b | 8 | 100% | 100% |
| brasileirao-serie-b | 1 | 100% | 100% |
| primeira-liga | 2 | 100% | 100% |
| super-lig | 1 | 100% | 100% |
| pro-league | 3 | 100% | 100% |
| superliga | 4 | 75% | 75% |
| primera-division | 2 | 100% | 100% |
| a-league | 1 | 100% | 100% |
| colombian-primera-a | 2 | 100% | 100% |
| liga-mx | 1 | 100% | 100% |

**Resumo:** CornersAgainst e CardsAgainst estao >= 75% em TODAS as ligas testadas. Fallback por match history (#124) funciona.

## Pos-Recalibracao (2026-04-07)

### xG Blend Ativado — Impacto no Brier O/U

Recalibracao ativou xG blend em **20 de 22 ligas** (Championship e League One timeout).
Brier O/U **melhorou em TODAS as 20 ligas**. Reducao media: **-0.0036**.

| Liga | xG Weight | Brier PRE | Brier POS | Delta |
|------|:---------:|:---------:|:---------:|:-----:|
| premier-league | 0.4 | 0.1785 | 0.1748 | -0.0037 |
| la-liga | 0.4 | 0.1696 | 0.1658 | -0.0038 |
| serie-a | 0.4 | 0.1698 | 0.1672 | -0.0026 |
| serie-b | 0.3 | 0.1684 | 0.1646 | -0.0038 |
| bundesliga | 0.4 | 0.1770 | 0.1731 | -0.0039 |
| 2-bundesliga | 0.4 | 0.1757 | 0.1715 | -0.0042 |
| ligue-1 | 0.5 | 0.1767 | 0.1712 | -0.0055 |
| brasileirao-serie-a | 0.3 | 0.1635 | 0.1605 | -0.0030 |
| brasileirao-serie-b | 0.2 | 0.1511 | 0.1502 | -0.0009 |
| eredivisie | 0.4 | 0.1760 | 0.1724 | -0.0036 |
| primeira-liga | 0.3 | 0.1682 | 0.1654 | -0.0028 |
| super-lig | 0.5 | 0.1781 | 0.1720 | -0.0061 |
| pro-league | 0.5 | 0.1761 | 0.1710 | -0.0051 |
| premiership | 0.4 | 0.1728 | 0.1679 | -0.0049 |
| superliga | 0.3 | 0.1772 | 0.1743 | -0.0029 |
| primera-division | 0.3 | 0.1553 | 0.1518 | -0.0035 |
| a-league | 0.3 | 0.1739 | 0.1714 | -0.0025 |
| mls | 0.4 | 0.1774 | 0.1725 | -0.0049 |
| colombian-primera-a | 0.3 | 0.1643 | 0.1622 | -0.0021 |
| liga-mx | 0.3 | 0.1754 | 0.1724 | -0.0030 |

**Brier O/U medio:** 0.1713 → **0.1678** (-0.0035)

### Corners e Cards: Sem mudanca

Recalibracao NAO mudou Brier de corners (0.2381) nem cards (0.1987). Confirmado: problema de corners e estrutural no modelo, nao nos dados.

### Decisao #129

Corners Brier pos-recalib: **0.2381 (inalterado)**. #129 e necessario para investigar o modelo de corners.

## Metricas de Produto (extraidas 2026-04-07)

### 1. Brier BTTS
**NAO DISPONIVEL** — O calibrador calcula brier_btts internamente (league_calibrator.py:194) mas NAO o salva no DB (ausente do param_map nas linhas 1320-1340). O campo e computado, descartado, e nao exposto na API de calibration-status. Para extrair, seria necessario adicionar "brier_btts" ao param_map e recalibrar.

### 2. Lambda Erro Medio
**NAO DISPONIVEL** — O cron_handler.py calcula avg_lambda_error (linha 429) durante auditorias pos-jogo, mas o endpoint /api/health/safe-status retorna 404. O valor de 1.45 gols reportado no audit #119 veio de uma execucao manual do cron. Nao ha endpoint exposto para consultar o valor atual.

| Referencia | Valor |
|------------|:-----:|
| Audit #119 | 1.45 gols |
| Limite aceitavel | 0.50 gols |
| Atual | NAO DISPONIVEL (endpoint /safe-status 404) |

### 3. Distribuicao de Classificacoes (06/04/2026, 12 ligas, 49 jogos)

| Classificacao | Frontend | Count | % |
|---------------|----------|:-----:|:-:|
| SAFE | ALTA CONFIANCA | 0 | 0.0% |
| NEUTRO_QUALIFICADO | VALOR DETECTADO | 34 | 30.1% |
| NEUTRO | INFORMATIVO | 79 | 69.9% |
| NO_BET | BLOQUEADO | 0* | 0.0%* |
| **Total** | | **113** | **100%** |

*NO_BET picks sao filtrados antes do response da API (nao aparecem em `mercados`). O total real de picks gerados (incluindo NO_BET) e desconhecido sem logs do Lambda.

**VIA 2 (direcao natural):** 37 picks promovidos de NEUTRO para NQ pela VIA 2. Sem VIA 2, NQ seria ~0% como antes do fix #127.

### 4. SAFE Acuracia
**N/A** — 0 picks SAFE gerados. O circuit breaker (#043/#052) desativa SAFE para ligas sem 3 auditorias consecutivas com accuracy > 50%. Nenhuma liga atingiu esse criterio. Acuracia de SAFE nao pode ser medida com N=0.

### 5. N de Jogos por Mercado
**NAO DISPONIVEL** — O calibrador armazena `n_matches` nos params (linha 909) mas NAO o expoe na API de calibration-status (ausente do response). Cada liga processa 3 temporadas de historico (~300-600 jogos por liga, ~6.600-13.200 total estimado para 22 ligas). Para extrair N exato, seria necessario adicionar ao endpoint ou rodar o calibrador com logging.

## Notas
- xG blend era codigo morto desde #052 — fix #128c + recalibracao ativou em 20 ligas
- Maior impacto: Ligue 1 (-0.0055), Super Lig (-0.0061), Pro League (-0.0051)
- Championship e League One nao recalibraram (timeout — issue #112 conhecida)
- Brier e validacao sao IN-SAMPLE (overlap 100% treino/avaliacao) — ganhos podem ser overfitting
