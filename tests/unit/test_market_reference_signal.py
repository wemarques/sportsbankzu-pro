"""
Tests for the market_reference_signal governance layer.

Covers:
1. Signal computation per market type
2. Pick capping logic
3. Audit compatibility (finalClassification used for accuracy)
4. Correction system blocking
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.market_reference_signal import (
    get_market_reference_signal,
    apply_signal_capping,
    _detect_market_category,
    _normalize_market_category,
    SAFE,
    NEUTRO,
    RESTRITO,
)


# ──────────────────────────────────────────────
# 1. Signal computation tests
# ──────────────────────────────────────────────


class TestGetMarketReferenceSignal:
    """Test signal computation per league + market type."""

    @patch("backend.ml.predictor.is_ml_available", return_value=True)
    @patch("backend.ml.predictor._load_models")
    def test_1x2_ml_active_returns_safe(self, mock_load, mock_ml):
        result = get_market_reference_signal("1625", "1X2")
        assert result["signal"] == SAFE
        assert result["source"] == "league_classification"

    @patch("backend.ml.predictor.is_ml_available", return_value=False)
    @patch("backend.ml.predictor._load_models")
    def test_1x2_poisson_returns_neutro(self, mock_load, mock_ml):
        mock_load.return_value = {
            "metadata": {"validation_brier": 0.62, "ml_deactivated": False}
        }
        result = get_market_reference_signal("1625", "1X2")
        assert result["signal"] == NEUTRO

    @patch("backend.ml.predictor.is_ml_available", return_value=False)
    @patch("backend.ml.predictor._load_models")
    def test_1x2_deactivated_returns_restrito(self, mock_load, mock_ml):
        mock_load.return_value = {
            "metadata": {"ml_deactivated": True}
        }
        result = get_market_reference_signal("1625", "1X2")
        assert result["signal"] == RESTRITO

    @patch("backend.ml.predictor.is_ml_available", return_value=False)
    @patch("backend.ml.predictor._load_models", return_value=None)
    def test_1x2_no_model_returns_restrito(self, mock_load, mock_ml):
        result = get_market_reference_signal("9999", "1X2")
        assert result["signal"] == RESTRITO

    @patch("backend.services.market_reference_signal._get_1x2_signal")
    def test_double_chance_inherits_from_1x2(self, mock_1x2):
        mock_1x2.return_value = {"signal": SAFE, "reason": "ML active", "source": "league_classification"}
        result = get_market_reference_signal("1625", "Double Chance")
        assert result["signal"] == SAFE
        assert "Herda do 1X2" in result["reason"]

    def test_corners_uses_v2_governance(self):
        result = get_market_reference_signal("1625", "Corners")
        assert result["signal"] in (SAFE, NEUTRO, RESTRITO)
        # #187: "fallback_default" eliminado das fontes exibidas (Achado 5)
        assert result["source"] in ("corners_v2_governance", "indeterminate")

    @patch("backend.services.market_reference_signal._get_market_model_signal")
    def test_over_under_delegates_to_market_model(self, mock_mkt):
        mock_mkt.return_value = {"signal": SAFE, "reason": "beats Poisson", "source": "market_model"}
        result = get_market_reference_signal("1625", "Over/Under")
        mock_mkt.assert_called_once_with("1625", "over25")
        assert result["signal"] == SAFE

    @patch("backend.services.market_reference_signal._get_market_model_signal")
    def test_btts_delegates_to_market_model(self, mock_mkt):
        mock_mkt.return_value = {"signal": NEUTRO, "reason": "fallback", "source": "fallback_default"}
        result = get_market_reference_signal("1625", "BTTS")
        mock_mkt.assert_called_once_with("1625", "btts")
        assert result["signal"] == NEUTRO


# ──────────────────────────────────────────────
# 2. Pick capping tests
# ──────────────────────────────────────────────


class TestApplySignalCapping:
    """Test that market_reference_signal correctly caps pick classification."""

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_safe_signal_no_capping(self, mock_signal):
        mock_signal.return_value = {"signal": SAFE, "reason": "ML active", "source": "league_classification"}
        mercados = [{"mercado": "Over 2.5 gols", "status": "SAFE"}]
        result = apply_signal_capping(mercados, "1625")
        assert result[0]["status"] == "SAFE"
        assert result[0]["finalClassification"] == "SAFE"
        assert result[0]["wasCappedByMarketSignal"] is False
        assert result[0]["rawClassification"] == "SAFE"

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_neutro_signal_caps_safe_to_neutro(self, mock_signal):
        mock_signal.return_value = {"signal": NEUTRO, "reason": "Poisson fallback", "source": "league_classification"}
        mercados = [{"mercado": "Over 2.5 gols", "status": "SAFE"}]
        result = apply_signal_capping(mercados, "1625")
        assert result[0]["status"] == "NEUTRO"
        assert result[0]["finalClassification"] == "NEUTRO"
        assert result[0]["wasCappedByMarketSignal"] is True
        assert result[0]["rawClassification"] == "SAFE"

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_restrito_signal_blocks_safe(self, mock_signal):
        mock_signal.return_value = {"signal": RESTRITO, "reason": "deactivated", "source": "league_classification"}
        mercados = [{"mercado": "Over 2.5 gols", "status": "SAFE"}]
        result = apply_signal_capping(mercados, "1625")
        assert result[0]["status"] == "NEUTRO"
        assert result[0]["finalClassification"] == "NEUTRO"
        assert result[0]["wasCappedByMarketSignal"] is True

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_neutro_pick_not_capped_by_neutro_signal(self, mock_signal):
        mock_signal.return_value = {"signal": NEUTRO, "reason": "Poisson", "source": "league_classification"}
        mercados = [{"mercado": "BTTS — SIM", "status": "NEUTRO"}]
        result = apply_signal_capping(mercados, "1625")
        assert result[0]["status"] == "NEUTRO"
        assert result[0]["wasCappedByMarketSignal"] is False

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_safe_star_is_treated_as_safe(self, mock_signal):
        """SAFE* (with alert) should still be capped if signal is NEUTRO."""
        mock_signal.return_value = {"signal": NEUTRO, "reason": "Poisson", "source": "league_classification"}
        mercados = [{"mercado": "Under 3.5 gols", "status": "SAFE*"}]
        result = apply_signal_capping(mercados, "1625")
        assert result[0]["status"] == "NEUTRO"
        assert result[0]["wasCappedByMarketSignal"] is True
        assert result[0]["rawClassification"] == "SAFE*"

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_multiple_mercados_with_different_categories(self, mock_signal):
        """Different market types get independent signals."""
        call_count = {"n": 0}
        def side_effect(league_id, market_type):
            call_count["n"] += 1
            if market_type == "Over/Under":
                return {"signal": SAFE, "reason": "ML", "source": "market_model"}
            return {"signal": NEUTRO, "reason": "Poisson", "source": "league_classification"}

        mock_signal.side_effect = side_effect
        mercados = [
            {"mercado": "Over 2.5 gols", "status": "SAFE"},
            {"mercado": "BTTS — SIM", "status": "SAFE"},
        ]
        result = apply_signal_capping(mercados, "1625")
        # Over/Under SAFE signal → no capping
        assert result[0]["wasCappedByMarketSignal"] is False
        # BTTS NEUTRO signal → SAFE capped to NEUTRO
        assert result[1]["wasCappedByMarketSignal"] is True
        assert result[1]["finalClassification"] == "NEUTRO"


# ──────────────────────────────────────────────
# 3. Audit compatibility tests
# ──────────────────────────────────────────────


class TestAuditCompatibility:
    """Ensure market_reference_signal doesn't break audit accuracy."""

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_final_classification_preserved_for_audit(self, mock_signal):
        """finalClassification should be what the audit system uses."""
        mock_signal.return_value = {"signal": NEUTRO, "reason": "Poisson", "source": "league_classification"}
        mercados = [{"mercado": "Over 2.5 gols", "status": "SAFE"}]
        result = apply_signal_capping(mercados, "1625")

        # Audit should use finalClassification (NEUTRO), not rawClassification (SAFE)
        assert result[0]["finalClassification"] == "NEUTRO"
        assert result[0]["rawClassification"] == "SAFE"
        # The actual status field is also updated
        assert result[0]["status"] == "NEUTRO"

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_market_reference_fields_all_present(self, mock_signal):
        mock_signal.return_value = {"signal": SAFE, "reason": "ML active", "source": "league_classification"}
        mercados = [{"mercado": "DC 1X (FLA/EMP)", "status": "SAFE"}]
        result = apply_signal_capping(mercados, "1625")
        m = result[0]
        assert "marketReferenceSignal" in m
        assert "marketReferenceReason" in m
        assert "marketReferenceSource" in m
        assert "rawClassification" in m
        assert "finalClassification" in m
        assert "wasCappedByMarketSignal" in m


# ──────────────────────────────────────────────
# 4. Correction system blocking
# ──────────────────────────────────────────────


class TestCorrectionBlocking:
    """Ensure market_reference_signal cannot be changed by automatic corrections."""

    def test_validate_adjustment_blocks_market_reference_signal_type(self):
        from backend.audit import validate_adjustment
        is_valid, reason = validate_adjustment(
            "MARKET_REFERENCE_SIGNAL", "market_ref_1x2", 1.0, 0.5
        )
        assert is_valid is False
        assert "market_reference_signal" in reason.lower()

    def test_validate_adjustment_blocks_market_reference_parameter(self):
        from backend.audit import validate_adjustment
        is_valid, reason = validate_adjustment(
            "THRESHOLD", "market_reference_override", 0.6, 0.7
        )
        assert is_valid is False
        assert "market_reference_signal" in reason.lower()

    def test_validate_adjustment_allows_normal_corrections(self):
        from backend.audit import validate_adjustment
        is_valid, reason = validate_adjustment(
            "THRESHOLD", "safe_threshold_1x2", 0.60, 0.65
        )
        assert is_valid is True


# ──────────────────────────────────────────────
# 5. Market category detection
# ──────────────────────────────────────────────


class TestMarketCategoryDetection:

    def test_detect_over_under(self):
        assert _detect_market_category("Over 2.5 gols") == "Over/Under"
        assert _detect_market_category("Under 3.5 gols") == "Over/Under"

    def test_detect_btts(self):
        assert _detect_market_category("BTTS — SIM") == "BTTS"

    def test_detect_double_chance(self):
        assert _detect_market_category("DC 1X (FLA/EMP)") == "Double Chance"

    def test_detect_corners(self):
        assert _detect_market_category("Escanteios Over 9.5") == "Corners"

    def test_detect_cards(self):
        # #186: cards contain "over"/"under" and must NOT fall into goals Over/Under
        assert _detect_market_category("Cartoes Over 3.5") == "Cards"
        assert _detect_market_category("Cartões Under 4.5") == "Cards"
        assert _detect_market_category("Cards Over 2.5") == "Cards"

    def test_normalize_market_category(self):
        assert _normalize_market_category("1X2") == "1X2"
        assert _normalize_market_category("Over/Under") == "Over/Under"
        assert _normalize_market_category("something with over") == "Over/Under"
        assert _normalize_market_category("btts yes") == "BTTS"
        assert _normalize_market_category("corner over 9.5") == "Corners"
        assert _normalize_market_category("Cards") == "Cards"
        assert _normalize_market_category("cartoes over 3.5") == "Cards"


# ──────────────────────────────────────────────
# 6. Cards signal (#186)
# ──────────────────────────────────────────────


class TestCardsSignal:

    @patch("backend.services.market_reference_signal._get_market_model_signal")
    def test_cards_without_ml_model_uses_engine_default(self, mock_mkt):
        mock_mkt.return_value = {
            "signal": NEUTRO,
            "reason": "No dedicated market model — Poisson fallback (cards)",
            "source": "fallback_default",
        }
        result = get_market_reference_signal("1625", "Cards")
        mock_mkt.assert_called_once_with("1625", "cards")
        assert result["signal"] == NEUTRO
        assert result["source"] == "cards_engine_default"
        # Reason must name cards, never the goals over25 model (pre-#186 bug)
        assert "over25" not in result["reason"]
        assert "cards" in result["reason"].lower()

    @patch("backend.services.market_reference_signal._get_market_model_signal")
    def test_cards_with_dedicated_ml_model_is_honored(self, mock_mkt):
        mock_mkt.return_value = {
            "signal": SAFE,
            "reason": "Dedicated ML model beats Poisson (cards)",
            "source": "market_model",
        }
        result = get_market_reference_signal("1625", "Cards")
        assert result["signal"] == SAFE
        assert result["source"] == "market_model"

    @patch("backend.services.market_reference_signal.get_market_reference_signal")
    def test_cards_mercado_gets_cards_category_in_capping(self, mock_signal):
        seen_categories = []

        def side_effect(league_id, market_type):
            seen_categories.append(market_type)
            return {"signal": NEUTRO, "reason": "x", "source": "cards_engine_default"}

        mock_signal.side_effect = side_effect
        mercados = [{"mercado": "Cartoes Over 3.5", "status": "NEUTRO"}]
        apply_signal_capping(mercados, "1625")
        assert seen_categories == ["Cards"]
