# BACKTEST POS-FIX #128 — BASELINE
**Data:** 2026-04-07
**Commit:** 81b1b7a (dados) + d9c3f56 (#127 VIA2) + 385f652 (#126 direcao)
**Periodo avaliado:** Temporadas calibradas (3 seasons por liga)
**N ligas:** 22

## Brier Scores Medios (menor = melhor, random = 0.25)

| Mercado | Brier Medio | N ligas |
|---------|:-----------:|:-------:|
| Over/Under (gols) | **0.1713** | 22 |
| 1X2 | **0.1912** | 22 |
| Corners | **0.2381** | 22 |
| Cards | **0.1987** | 22 |
| **Geral** | **0.1998** | 22 |

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

## Cobertura de Campos Novos (#128) — Validacao Multi-Liga

| Liga | Corners For | Corners Against | Cards For | Cards Against | xG Home | xG Away |
|------|:-----------:|:---------------:|:---------:|:-------------:|:-------:|:-------:|
| Championship (12j) | 92% | 92% | 92% | 92% | **0%** | **0%** |
| La Liga (1j) | 100% | 100% | 100% | 100% | 100% | **0%** |
| A-League (1j) | 100% | 100% | 100% | 100% | 100% | **0%** |

### xG: Padrao assimetrico confirmado
- Home xG disponivel em La Liga e A-League (100%)
- Away xG **sempre NULL** em todas as ligas testadas
- Championship: 0% para ambos os lados
- **Guarda #128e implementada:** xG blend so ativa com cobertura >= 80% home E away

## Notas
- Este baseline NAO tem pre-128 para comparacao (deploy foi feito sem baseline)
- Serve como referencia para fixes futuros a partir de agora
- Brier de Corners (0.2381) e o mais alto — mais proximo do random (0.25)
- Brier de O/U (0.1713) e o melhor — modelo tem boa calibracao para gols
