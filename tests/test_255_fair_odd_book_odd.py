# -*- coding: utf-8 -*-
"""#255 — contrato `fair_odd`/`book_odd` (spec §6.3): "sempre presentes e
distintos no payload de /fixtures".

Achado da Etapa 1 (Validacao de Contrato): o contrato JA EXISTE em
`backend/models/market_output.py` — `fair_odd` (:64, calculado em
`compute_display`, :147) e `book_odd` (:65) sao campos do proprio
`MarketOutput`, e `to_legacy_mercado()` (:176-177) sempre inclui os dois. A
spec listava isto como "falta implementar"; nao falta — falta a prova, que e
este arquivo. Payload no mesmo formato de
`tests/test_251_calibrated_prob_e_o_modelo.py`.

Achado da Etapa 4 (Prova Empirica): teste #3 era order-dependent (falhava na
suite completa, passava sozinho). `fair_odd` e calculado em `compute_display`
a partir da probabilidade SEM arredondar, enquanto `to_legacy_mercado`
arredonda a 4 casas. Em fronteira de arredondamento (ex.: 0,56983 -> 0,5698)
os resultados diferem por 0,01. A prova foi redesenhada para comparar contra
o objeto nao-arredondado, eliminando a dependencia de estado global (se o
modelo ML de escanteios e carregavel ou nao determina quais mercados caem na
fronteira).
"""
import copy

from backend.services.ev_classification import evaluate_match_markets

_ODDS = {
    "home": 1.95, "draw": 3.60, "away": 3.70,
    "over25": 1.80, "under25": 1.90, "over15": 1.22, "under15": 3.54,
    "bttsYes": 1.75, "bttsNo": 2.00,
    "cornersOver95": 1.77, "cornersUnder95": 1.95, "cornersOver115": 2.63,
}
_MATCH = {
    "id": "999250", "homeTeam": "Casa FC", "awayTeam": "Fora FC",
    "stats": {"lambdaHome": 1.55, "lambdaAway": 1.15, "lambdaTotal": 2.70,
              "homeWinProb": 47.0, "drawProb": 26.0, "awayWinProb": 27.0,
              "homeCornersPerMatch": 5.6, "awayCornersPerMatch": 4.9,
              "leagueAvgCorners": 10.2,
              "homeCardsPerMatch": 2.1, "awayCardsPerMatch": 2.4,
              "leagueAvgCards": 4.6,
              "matchesPlayed_home": 18, "matchesPlayed_away": 18},
    "league_stats": {"matches_completed": 200, "average_goals_per_match": 2.65,
                     "average_corners_per_match": 10.2,
                     "average_cards_per_match": 4.6},
    "odds": {**_ODDS, "over05": 1.03, "under05": 9.50, "over35": 2.99,
             "under35": 1.30, "over45": 5.85, "under45": 1.10,
             "dc_1x": 1.25, "dc_12": 1.28, "dc_x2": 1.83,
             "cornersOver75": 1.24, "cornersUnder75": 3.55,
             "cornersUnder115": 1.41},
}


def _mercados():
    bundle = evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    return [m.to_legacy_mercado() for m in bundle.markets]


def test_fair_odd_e_book_odd_sempre_presentes():
    mercados = _mercados()
    assert mercados, "bundle sem mercados — payload de teste desatualizado"
    for m in mercados:
        assert "fair_odd" in m
        assert "book_odd" in m


def test_fair_odd_e_book_odd_distintos_quando_ha_preco_de_casa():
    mercados = _mercados()
    com_book = [m for m in mercados if m["book_odd"] is not None]
    assert com_book, "nenhum mercado com book_odd — payload de teste sem odds reais"
    distintos = [m for m in com_book if m["fair_odd"] != m["book_odd"]]
    assert distintos, "fair_odd == book_odd em todo mercado com preco de casa"


def test_fair_odd_e_o_inverso_da_probabilidade_calibrada():
    # A prob do dict legado e arredondada a 4 casas (`to_legacy_mercado`); `fair_odd`
    # e calculada em `compute_display` a partir da prob SEM arredondar. Comparar
    # contra a prob arredondada falha em fronteira de arredondamento (ex.: 0,56983
    # -> 0,5698 -> 1/p = 1,755 -> 1,76, enquanto 1/0,56983 = 1,7549 -> 1,75), e o
    # conjunto de mercados que cai na fronteira depende de estado global (modelo ML
    # de escanteios carregavel ou nao). Por isso a prova usa o objeto.
    bundle = evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    assert bundle.markets
    for m in bundle.markets:
        legado = m.to_legacy_mercado()
        assert legado["fair_odd"] == m.fair_odd
        if m.fair_odd is not None and m.calibrated_probability:
            assert m.fair_odd == round(1.0 / m.calibrated_probability, 2)
