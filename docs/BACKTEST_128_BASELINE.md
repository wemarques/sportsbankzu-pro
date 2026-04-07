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

## Notas
- Baseline NAO tem pre-128 para comparacao
- Brier de Corners (0.2381) e o mais alto — perto de random (0.25)
- Melhor Brier de O/U: brasileirao-serie-b (0.1511) e primera-division (0.1553)
- Pior Brier de Cards: premier-league (0.2230) e superliga (0.2217)
- Campos novos #128a/#128b (corner 65/115/145, card 25/35/45 percentages) nao puderam ser verificados via API — precisam de recalibracao para popular
