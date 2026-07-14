"""
#187 — Cards/corners odds: single-bet family capture + ladder coherence,
e critério de aceite do Achado 5: nenhum sinal exibido com fonte
"fallback_default".

Contexto: pré-#187, extract_best_odds preenchia cada linha de cartões com o
primeiro valor de QUALQUER bet contendo "card"/"booking", misturando mercado
total com mercados por time/tempo/handicap entre bookmakers — produzindo
escadas impossíveis (Over 5.5 pagando menos que Over 3.5 no mesmo payload,
observado em produção no CRB x Náutico, 2026-07-14).
"""

import pytest

from backend.services.api_football_client import (
    APIFootballClient,
    _extract_line_family,
)
from backend.services.market_reference_signal import get_market_reference_signal


def _bet(name, values):
    return {
        "id": 999,
        "name": name,
        "values": [{"value": v, "odd": str(o)} for v, o in values],
    }


def _odds_response(bookmakers):
    return [{"bookmakers": bookmakers}]


# ──────────────────────────────────────────────
# 1. _extract_line_family
# ──────────────────────────────────────────────


class TestExtractLineFamily:

    CARD_LINES = ("1.5", "2.5", "3.5", "4.5", "5.5", "6.5")

    def test_coherent_total_market_is_captured(self):
        values = [
            {"value": "Over 2.5", "odd": "1.20"},
            {"value": "Over 3.5", "odd": "1.60"},
            {"value": "Over 4.5", "odd": "2.40"},
            {"value": "Under 3.5", "odd": "2.30"},
            {"value": "Under 4.5", "odd": "1.55"},
        ]
        fam = _extract_line_family("Cards Over/Under", values, "cards", self.CARD_LINES)
        assert fam["cards_over_25"] == 1.20
        assert fam["cards_over_35"] == 1.60
        assert fam["cards_over_45"] == 2.40
        assert fam["cards_under_35"] == 2.30

    @pytest.mark.parametrize(
        "bet_name",
        [
            "Home Team Total Cards",
            "Away Team Total Cards",
            "Cards European Handicap",
            "Cards Over/Under 1st Half",
            "Asian Total Cards",
            "Player Cards",
        ],
    )
    def test_non_total_variants_are_rejected(self, bet_name):
        values = [{"value": "Over 2.5", "odd": "1.80"}]
        assert _extract_line_family(bet_name, values, "cards", self.CARD_LINES) == {}

    def test_incoherent_over_ladder_is_discarded(self):
        # Over 5.5 pagando MENOS que Over 3.5 = semântica de mercado misturada
        values = [
            {"value": "Over 3.5", "odd": "2.27"},
            {"value": "Over 5.5", "odd": "1.75"},
        ]
        assert _extract_line_family("Cards Over/Under", values, "cards", self.CARD_LINES) == {}

    def test_incoherent_under_ladder_is_discarded(self):
        # P(under) cresce com a linha → odd de under deve CAIR com a linha
        values = [
            {"value": "Under 2.5", "odd": "1.50"},
            {"value": "Under 4.5", "odd": "2.80"},
        ]
        assert _extract_line_family("Cards Over/Under", values, "cards", self.CARD_LINES) == {}

    def test_invalid_odds_are_skipped(self):
        values = [
            {"value": "Over 2.5", "odd": "0"},
            {"value": "Over 3.5", "odd": "1.0"},
            {"value": "Over 4.5", "odd": "abc"},
        ]
        assert _extract_line_family("Cards Over/Under", values, "cards", self.CARD_LINES) == {}


# ──────────────────────────────────────────────
# 2. extract_best_odds — no cross-bet mixing
# ──────────────────────────────────────────────


class TestExtractBestOddsCards:

    def test_team_cards_market_does_not_pollute_total(self):
        """Reprodução do caso CRB x Náutico: bet de cartões por time vinha
        primeiro e contaminava as linhas do mercado total."""
        client = APIFootballClient()
        response = _odds_response([
            {
                "name": "Bet365",
                "bets": [
                    _bet("Home Team Total Cards", [("Over 2.5", 1.78), ("Over 3.5", 3.2)]),
                    _bet("Cards Over/Under", [
                        ("Over 2.5", 1.25), ("Over 3.5", 2.27), ("Over 5.5", 6.0),
                    ]),
                ],
            },
        ])
        result = client.extract_best_odds(response)
        assert result.get("cards_over_35") == 2.27
        assert result.get("cards_over_25") == 1.25
        assert result.get("cards_over_55") == 6.0

    def test_incoherent_mix_never_reaches_result(self):
        """Um único bet com escada impossível é descartado inteiro (#103:
        nenhuma odd é melhor que uma odd errada)."""
        client = APIFootballClient()
        response = _odds_response([
            {
                "name": "Bet365",
                "bets": [
                    _bet("Cards Over/Under", [("Over 3.5", 2.27), ("Over 5.5", 1.75)]),
                ],
            },
        ])
        result = client.extract_best_odds(response)
        assert not any(k.startswith("cards_") for k in result)

    def test_corners_family_from_single_bet(self):
        client = APIFootballClient()
        response = _odds_response([
            {
                "name": "Bet365",
                "bets": [
                    _bet("Corners Over Under", [
                        ("Over 8.5", 1.30), ("Over 9.5", 1.55), ("Over 10.5", 1.95),
                        ("Under 10.5", 1.80),
                    ]),
                    _bet("Home Team Corners", [("Over 4.5", 1.60)]),
                ],
            },
        ])
        result = client.extract_best_odds(response)
        assert result.get("corners_over_85") == 1.30
        assert result.get("corners_over_105") == 1.95
        assert result.get("corners_under_105") == 1.80


# ──────────────────────────────────────────────
# 3. Achado 5 — nenhum sinal com fonte fallback_default
# ──────────────────────────────────────────────


class TestNoFallbackDefaultDisplayed:

    @pytest.mark.parametrize(
        "market_type",
        ["1X2", "Double Chance", "Over/Under", "BTTS", "Corners", "Cards", "???"],
    )
    def test_signal_source_is_never_fallback_default(self, market_type):
        result = get_market_reference_signal("liga-inexistente-xyz", market_type)
        assert result["source"] != "fallback_default", (
            f"{market_type}: critério de aceite do Achado 5 violado "
            f"(source={result['source']})"
        )

    def test_no_model_over_under_declares_poisson_pipeline(self):
        result = get_market_reference_signal("liga-inexistente-xyz", "Over/Under")
        assert result["source"] in ("poisson_pipeline", "indeterminate")
        if result["source"] == "poisson_pipeline":
            assert "Poisson" in result["reason"]
