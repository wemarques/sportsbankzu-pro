"""#189-f — cobertura de odds de escanteios + árbitro nos picks.

Gargalos encontrados na auditoria de 31/08/2026:
1. `extract_best_odds` devolve corners_over/under_45..125 desde o #144,
   mas `_enrich_odds_from_api_football` copiava gols/1X2/BTTS/DC/cartões
   e DESCARTAVA escanteios — todo pick de Escanteios nascia "sem odd".
2. `_FOOTYSTATS_ODD_MAP` só cobria as linhas Over 8.5–11.5.
3. O fator de árbitro (#141) alimentava apenas o display
   (cardsPredictions); os picks chamavam predict_cards sem
   referee_avg_cards — e o lookup rodava DEPOIS da seleção de mercados.
"""
import pytest

from backend.routes.fixtures import _enrich_odds_from_api_football
import backend.routes.fixtures as fixtures_mod
from backend.modeling.cards_engine import predict_cards


# ── 1. odds de escanteios copiadas no enrichment ─────────────────────

class _FakeAFC:
    is_configured = True

    def get_odds(self, fixture_id, ttl_minutes=180):
        return {"fake": True}

    def extract_best_odds(self, af_odds, league_id=""):
        return {
            "corners_over_85": 1.85, "corners_under_85": 1.95,
            "corners_over_105": 2.40, "corners_under_95": 1.72,
            "cards_over_25": 1.60,
            "over_25": 1.80,
        }


def test_enrichment_copia_odds_de_escanteios(monkeypatch):
    monkeypatch.setattr(fixtures_mod, "_afc", _FakeAFC())
    rec = {
        "apiFootballFixtureId": 123,
        "leagueId": "brasileirao-serie-a",
        "odds": {},
        "homeTeam": {"name": "Time A"},
    }
    enriched = _enrich_odds_from_api_football([rec])
    assert enriched, "record deveria ter sido enriquecido"
    odds = rec["odds"]
    assert odds["cornersOver85"] == 1.85
    assert odds["cornersUnder85"] == 1.95
    assert odds["cornersOver105"] == 2.40
    assert odds["cornersUnder95"] == 1.72
    # familias anteriores continuam funcionando
    assert odds["cards_over_2.5"] == 1.60
    assert odds["over25"] == 1.80


def test_enrichment_nao_sobrescreve_odd_existente(monkeypatch):
    monkeypatch.setattr(fixtures_mod, "_afc", _FakeAFC())
    rec = {
        "apiFootballFixtureId": 123,
        "leagueId": "x",
        "odds": {"cornersOver85": 2.10},
        "homeTeam": {"name": "Time A"},
    }
    _enrich_odds_from_api_football([rec])
    assert rec["odds"]["cornersOver85"] == 2.10  # FootyStats vence


# ── 2. mapa de odds cobre todas as linhas 4.5–12.5 ───────────────────

def test_mapa_de_odds_completo():
    import inspect
    from backend.services import ev_classification
    src = inspect.getsource(ev_classification.evaluate_match_markets)
    for key in ("cornersOver45", "cornersOver75", "cornersOver125"):
        assert key in src, f"{key} ausente do _FOOTYSTATS_ODD_MAP"


# ── 3. árbitro muda a probabilidade dos picks de cartões ─────────────

def test_referee_factor_desloca_probabilidade():
    base = predict_cards(
        home_stats={"homeCardsPerMatch": 2.0},
        away_stats={"awayCardsPerMatch": 2.0},
        league_id="",
        league_stats={"cardsAVG_overall": 4.0},
        referee_avg_cards=None,
    )
    strict = predict_cards(
        home_stats={"homeCardsPerMatch": 2.0},
        away_stats={"awayCardsPerMatch": 2.0},
        league_id="",
        league_stats={"cardsAVG_overall": 4.0},
        referee_avg_cards=5.2,  # arbitro rigoroso: 5.2 vs media 4.0
    )
    assert strict["adjustments"]["referee_factor"] == pytest.approx(1.30, abs=0.01)
    p_base = base["lines"]["over_3.5"]["prob"]
    p_strict = strict["lines"]["over_3.5"]["prob"]
    assert p_strict > p_base + 0.05  # Over sobe com arbitro rigoroso


def test_picks_recebem_referee_do_record():
    """evaluate_match_markets deve repassar refereeAvgCards ao predict_cards."""
    import inspect
    from backend.services import ev_classification
    src = inspect.getsource(ev_classification.evaluate_match_markets)
    assert 'referee_avg_cards=match_data.get("refereeAvgCards")' in src


def test_lookup_de_arbitro_roda_antes_da_selecao():
    """Em fixtures_service, o refereeAvgCards deve existir ANTES do
    selecionar_mercados_v2 (senão os picks nunca veem o árbitro)."""
    import inspect
    from backend.services import fixtures_service
    src = inspect.getsource(fixtures_service)
    pos_ref = src.find('record["refereeAvgCards"] = round(_ref_avg_pre, 2)')
    pos_sel = src.find("mercados = selecionar_mercados_v2(")
    assert pos_ref != -1 and pos_sel != -1
    assert pos_ref < pos_sel, "lookup do árbitro deve preceder a seleção de mercados"
