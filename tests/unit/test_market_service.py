from backend.services.market_service import normalize_prob, calcular_odd_under, selecionar_mercados_jogo

def test_normalize_prob():
    assert normalize_prob(0.75) == 0.75
    assert normalize_prob(75.0) == 0.75
    assert normalize_prob(-1) is None

def test_calcular_odd_under():
    assert round(calcular_odd_under(3.5), 2) == 1.4
    assert calcular_odd_under(0.5) is None

def test_selecionar_mercados_under35_safe():
    jogo = {
        "homeTeam": "X",
        "awayTeam": "Y",
        "stats": {
            "over25Prob": 0.50,
            "bttsProb": 0.55,
            "under35Prob": 0.66,
            "under45Prob": 0.80,
            "leagueAvgGoals": 2.6
        },
        "odds": {
            "over35": 3.5,
            "over45": 7.0,
            "over25": 1.85,
            "bttsYes": 1.80
        }
    }
    mercados = selecionar_mercados_jogo(jogo, regime="NORMAL", volatilidade="BAIXA")
    assert any(m["mercado"].startswith("Under 3.5") for m in mercados)
