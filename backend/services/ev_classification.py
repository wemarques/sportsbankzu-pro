"""
EV + Classification Engine (Layer 3)

Centralizes the final decision layer for all markets:
- Computes EV, edge, fair odd from calibrated probabilities + real odds
- Classifies: SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET
- Generates reason codes
- Uses dynamic thresholds per market

This service replaces the inline classification logic and provides
a single entry point for all market evaluation.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.models.market_output import (
    MarketOutput,
    MarketClassification,
    ReasonCode,
    MatchMarketBundle,
)
from backend.modeling.poisson_matrix import derive_all_markets
from backend.modeling.corners_engine import derive_corner_probabilities
from backend.modeling.calibrator import calibrate_prob
from backend.modeling.corners.predictor import predict_corners, get_corner_governance_info
from backend.modeling.corners.operational_states import CornerOperationalState
from backend.services.data_governance import (
    calculate_data_quality_score,
    detect_early_season,
    check_odds_availability,
)

logger = logging.getLogger("sportsbankzu.ev_classification")


# ─── Dynamic Thresholds per Market ───
# Each market has thresholds for SAFE and NEUTRO classification
# These are defaults; can be overridden from audit DB (Gap 4)

DEFAULT_THRESHOLDS = {
    "1X2": {
        "safe_prob": 0.55,    "neutro_prob": 0.42,
        "safe_ev": 0.05,      "neutro_ev": 0.00,
        "safe_edge": 0.04,    "neutro_edge": 0.01,
        "min_quality": 0.3,
    },
    "Over/Under": {
        "safe_prob": 0.68,    "neutro_prob": 0.58,
        "safe_ev": 0.04,      "neutro_ev": 0.00,
        "safe_edge": 0.03,    "neutro_edge": 0.01,
        "min_quality": 0.3,
    },
    "BTTS": {
        "safe_prob": 0.70,    "neutro_prob": 0.60,
        "safe_ev": 0.04,      "neutro_ev": 0.00,
        "safe_edge": 0.03,    "neutro_edge": 0.01,
        "min_quality": 0.3,
    },
    "Double Chance": {
        "safe_prob": 0.75,    "neutro_prob": 0.65,
        "safe_ev": 0.03,      "neutro_ev": 0.00,
        "safe_edge": 0.02,    "neutro_edge": 0.01,
        "min_quality": 0.3,
    },
    "Corners": {
        "safe_prob": 0.65,    "neutro_prob": 0.55,
        "safe_ev": 0.04,      "neutro_ev": 0.00,
        "safe_edge": 0.03,    "neutro_edge": 0.01,
        "min_quality": 0.35,
    },
}

# Minimum thresholds for NEUTRO qualificado (eligible for multiples)
NEUTRO_QUALIFICADO_THRESHOLDS = {
    "min_ev": 0.02,          # EV must be >= 2%
    "min_quality": 0.40,     # data quality >= 0.40
    "min_prob": 0.50,        # calibrated prob >= 50%
    "must_have_odds": True,  # real odds required
}


def _get_thresholds(market_category: str) -> Dict[str, float]:
    """Get thresholds for a market category, with audit DB override."""
    base = DEFAULT_THRESHOLDS.get(market_category, DEFAULT_THRESHOLDS["1X2"])

    # Try to load dynamic thresholds from audit DB
    try:
        from backend.services.market_service import _get_dynamic_thresholds
        db_th = _get_dynamic_thresholds(market_category)
        if db_th:
            # Override prob thresholds if available
            if "SAFE" in db_th:
                base = {**base, "safe_prob": db_th["SAFE"]}
            if "NEUTRO" in db_th:
                base = {**base, "neutro_prob": db_th["NEUTRO"]}
    except Exception:
        pass

    return base


def classify_market(
    output: MarketOutput,
    thresholds: Optional[Dict[str, float]] = None,
) -> MarketOutput:
    """Classify a single market output as SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET.

    Mutates the output in-place and returns it.
    """
    prob = output.calibrated_probability or output.raw_probability or 0.0
    market_cat = _market_category(output.market_type)
    th = thresholds or _get_thresholds(market_cat)

    # Compute EV and display
    output.compute_ev()
    output.compute_display()

    reason_codes: List[ReasonCode] = []

    # ─── Data quality checks ───
    if output.data_quality_score < th.get("min_quality", 0.3):
        reason_codes.append(ReasonCode.LOW_DATA_QUALITY)

    if not output.odds_available:
        reason_codes.append(ReasonCode.NO_ODDS_AVAILABLE)

    # ─── EV checks ───
    if output.ev is not None:
        if output.ev < 0:
            reason_codes.append(ReasonCode.NEGATIVE_EV)
        elif output.ev >= th.get("safe_ev", 0.05):
            reason_codes.append(ReasonCode.POSITIVE_EV)

    if output.edge is not None:
        if output.edge < th.get("neutro_edge", 0.01):
            reason_codes.append(ReasonCode.INSUFFICIENT_EDGE)
        elif output.edge >= th.get("safe_edge", 0.04):
            reason_codes.append(ReasonCode.STRONG_EDGE)

    if prob >= th.get("safe_prob", 0.60):
        reason_codes.append(ReasonCode.HIGH_CALIBRATED_PROB)

    # ─── Classification logic ───
    classification = MarketClassification.NO_BET

    # SAFE: high prob + positive EV + sufficient edge + good data
    if (prob >= th.get("safe_prob", 0.60) and
        output.data_quality_score >= th.get("min_quality", 0.3)):
        if output.odds_available and output.ev is not None and output.ev >= th.get("safe_ev", 0.05):
            classification = MarketClassification.SAFE
        elif output.odds_available and output.ev is not None and output.ev >= 0:
            # Has odds, prob is high, but EV is marginal
            classification = MarketClassification.SAFE
        elif not output.odds_available:
            # High prob but no odds — NEUTRO (can show prob/fair_odd but no stake)
            classification = MarketClassification.NEUTRO

    # NEUTRO: moderate prob
    elif (prob >= th.get("neutro_prob", 0.50) and
          output.data_quality_score >= th.get("min_quality", 0.3) * 0.8):
        if output.odds_available and output.ev is not None and output.ev >= th.get("neutro_ev", 0.0):
            classification = MarketClassification.NEUTRO
        elif output.odds_available and output.ev is not None and output.ev >= -0.03:
            # Slightly negative EV but still usable
            classification = MarketClassification.NEUTRO
        else:
            classification = MarketClassification.NEUTRO

    # NEUTRO qualificado: upgrade NEUTRO if it meets additional criteria
    if classification == MarketClassification.NEUTRO:
        if _is_neutro_qualificado(output, prob):
            classification = MarketClassification.NEUTRO_QUALIFICADO

    # Force NO_BET on negative EV with odds (when prob is too low)
    if (output.odds_available and output.ev is not None and
        output.ev < -0.05 and prob < th.get("neutro_prob", 0.50)):
        classification = MarketClassification.NO_BET
        if ReasonCode.NEGATIVE_EV not in reason_codes:
            reason_codes.append(ReasonCode.NEGATIVE_EV)

    output.classification = classification
    output.reason_codes = reason_codes
    return output


def _is_neutro_qualificado(output: MarketOutput, prob: float) -> bool:
    """Check if a NEUTRO market qualifies for multiples eligibility."""
    th = NEUTRO_QUALIFICADO_THRESHOLDS

    if th["must_have_odds"] and not output.odds_available:
        return False

    if output.ev is None or output.ev < th["min_ev"]:
        return False

    if output.data_quality_score < th["min_quality"]:
        return False

    if prob < th["min_prob"]:
        return False

    return True


def evaluate_match_markets(
    match_data: Dict[str, Any],
    league_id: str = "",
    regime: str = "NORMAL",
) -> MatchMarketBundle:
    """Evaluate all markets for a single match, returning unified output.

    This is the main entry point for Layer 3. It:
    1. Extracts lambdas from match_data
    2. Derives all probabilities from Poisson matrix
    3. Calibrates probabilities
    4. Calculates data quality score
    5. Checks odds availability
    6. Classifies each market
    7. Returns MatchMarketBundle
    """
    stats = match_data.get("stats", {})
    odds = match_data.get("odds", {})
    league_stats = match_data.get("league_stats")
    home_team = match_data.get("homeTeam", "")
    away_team = match_data.get("awayTeam", "")
    match_id = str(match_data.get("id", match_data.get("match_id", "")))

    # ─── Data quality ───
    quality = calculate_data_quality_score(stats, odds, league_stats)
    early_season = detect_early_season(league_stats)

    # ─── Derive probabilities from Poisson matrix when lambdas available ───
    lambda_home = stats.get("lambdaHome")
    lambda_away = stats.get("lambdaAway")

    derived = {}
    if lambda_home and lambda_away and float(lambda_home) > 0 and float(lambda_away) > 0:
        derived = derive_all_markets(float(lambda_home), float(lambda_away))

    # ─── Derive corner probabilities (governed framework) ───
    governed_corners = predict_corners(
        home_stats=stats,
        away_stats=stats,
        league_id=league_id,
        league_stats=league_stats if isinstance(league_stats, dict) else None,
        footystats_probs=stats,
    )

    # Legacy fallback for backward compat
    corner_probs = derive_corner_probabilities(
        home_stats=stats,
        away_stats=stats,
        league_stats=league_stats if isinstance(league_stats, dict) else None,
        footystats_probs=stats,
    )

    # ─── Build market outputs ───
    markets: List[MarketOutput] = []
    source_flags = ["footystats"]

    # Helper to get probability with fallback to derived
    def _prob(stat_key: str, derived_key: str = "") -> Optional[float]:
        val = stats.get(stat_key)
        if val is not None:
            v = float(val)
            return v / 100.0 if v > 1.0 else v
        if derived_key and derived_key in derived:
            return derived[derived_key]
        return None

    # 1X2 markets
    for selection, stat_key, derived_key, odd_key in [
        ("Home", "homeWinProb", "homeWinProb", "home"),
        ("Draw", "drawProb", "drawProb", "draw"),
        ("Away", "awayWinProb", "awayWinProb", "away"),
    ]:
        raw = _prob(stat_key, derived_key)
        if raw is None:
            continue
        calibrated = calibrate_prob(raw, f"1X2_{selection.lower()}", league_id, regime)
        book_odd = odds.get(odd_key)
        if book_odd:
            book_odd = float(book_odd) if float(book_odd) > 1.0 else None
        else:
            book_odd = None

        mo = MarketOutput(
            market_type="1X2",
            selection=selection,
            raw_probability=raw,
            calibrated_probability=calibrated,
            book_odd=book_odd,
            odds_available=book_odd is not None,
            data_quality_score=quality,
            source_flags=source_flags,
            display_label=f"1X2 {selection}",
        )
        markets.append(classify_market(mo))

    # Over/Under markets
    for threshold, stat_over, stat_under, odd_key in [
        ("2.5", "over25Prob", "under25Prob", "over25"),
        ("3.5", "over35Prob", "under35Prob", "over35"),
        ("4.5", "over45Prob", "under45Prob", "over45"),
    ]:
        # Over
        raw_over = _prob(stat_over, f"over{threshold.replace('.', '')}Prob")
        if raw_over is not None:
            calibrated = calibrate_prob(raw_over, f"Over {threshold}", league_id, regime)
            book_odd = odds.get(odd_key)
            book_odd = float(book_odd) if book_odd and float(book_odd) > 1.0 else None
            mo = MarketOutput(
                market_type="Over/Under",
                selection=f"Over {threshold}",
                raw_probability=raw_over,
                calibrated_probability=calibrated,
                book_odd=book_odd,
                odds_available=book_odd is not None,
                data_quality_score=quality,
                source_flags=source_flags,
                display_label=f"Over {threshold} gols",
            )
            markets.append(classify_market(mo))

        # Under
        raw_under = _prob(stat_under, f"under{threshold.replace('.', '')}Prob")
        if raw_under is None and raw_over is not None:
            raw_under = 1.0 - raw_over
        if raw_under is not None:
            calibrated = calibrate_prob(raw_under, f"Under {threshold}", league_id, regime)
            # Derive under odd from over odd
            under_odd = None
            if book_odd and book_odd > 1.0:
                prob_over = 1.0 / book_odd
                prob_under = 1.0 - prob_over
                if prob_under > 0:
                    under_odd = round(1.0 / prob_under, 2)
            mo = MarketOutput(
                market_type="Over/Under",
                selection=f"Under {threshold}",
                raw_probability=raw_under,
                calibrated_probability=calibrated,
                book_odd=under_odd,
                odds_available=under_odd is not None,
                data_quality_score=quality,
                source_flags=source_flags,
                display_label=f"Under {threshold} gols",
            )
            markets.append(classify_market(mo))

    # BTTS
    raw_btts = _prob("bttsProb", "bttsProb")
    if raw_btts is not None:
        calibrated = calibrate_prob(raw_btts, "BTTS", league_id, regime)
        btts_odd = odds.get("bttsYes")
        btts_odd = float(btts_odd) if btts_odd and float(btts_odd) > 1.0 else None
        mo = MarketOutput(
            market_type="BTTS",
            selection="BTTS Yes",
            raw_probability=raw_btts,
            calibrated_probability=calibrated,
            book_odd=btts_odd,
            odds_available=btts_odd is not None,
            data_quality_score=quality,
            source_flags=source_flags,
            display_label="BTTS — SIM",
        )
        markets.append(classify_market(mo))

    # Double Chance (derived from 1X2)
    home_prob = _prob("homeWinProb", "homeWinProb")
    draw_prob = _prob("drawProb", "drawProb")
    away_prob = _prob("awayWinProb", "awayWinProb")

    if home_prob is not None and draw_prob is not None:
        dc_1x = home_prob + draw_prob
        calibrated = calibrate_prob(dc_1x, "Double Chance 1X", league_id, regime)
        # DC odds: derive from 1X2 odds if available
        dc_odd = None
        h_odd = odds.get("home")
        d_odd = odds.get("draw")
        if h_odd and d_odd and float(h_odd) > 1.0 and float(d_odd) > 1.0:
            implied_h = 1.0 / float(h_odd)
            implied_d = 1.0 / float(d_odd)
            dc_implied = implied_h + implied_d
            if dc_implied > 0 and dc_implied < 1.0:
                dc_odd = round(1.0 / dc_implied, 2)

        home_label = str(match_data.get("homeTeam", ""))[:3].upper()
        mo = MarketOutput(
            market_type="Double Chance",
            selection="DC 1X",
            raw_probability=dc_1x,
            calibrated_probability=calibrated,
            book_odd=dc_odd,
            odds_available=dc_odd is not None,
            data_quality_score=quality,
            source_flags=source_flags,
            display_label=f"DC 1X ({home_label}/EMP)",
        )
        markets.append(classify_market(mo))

    # Corner markets (governed framework)
    corner_governance = get_corner_governance_info(league_id)
    for threshold_key, stat_key, odd_key in [
        ("over_8.5", "cornerOver85Prob", "cornersOver85"),
        ("over_9.5", "cornerOver95Prob", "cornersOver95"),
        ("over_10.5", "cornerOver105Prob", "cornersOver105"),
        ("over_11.5", "cornerOver115Prob", "cornersOver115"),
    ]:
        # Use governed corner prediction (champion model)
        gov_line = governed_corners.get("lines", {}).get(threshold_key, {})
        raw = gov_line.get("probability")

        # Fallback to legacy engine / footystats
        if raw is None:
            raw = corner_probs.get(threshold_key)
        if raw is None:
            raw = _prob(stat_key)
        if raw is None:
            continue

        threshold_label = threshold_key.replace("over_", "Over ")
        calibrated = calibrate_prob(raw, f"Escanteios {threshold_label}", league_id, regime)
        corner_odd = odds.get(odd_key)
        corner_odd = float(corner_odd) if corner_odd and float(corner_odd) > 1.0 else None

        # Governance metadata
        gov_line_info = corner_governance.get("lines", {}).get(threshold_key, {})
        operational_state = gov_line_info.get("operationalState", "RESTRICTED")
        champion_model = gov_line_info.get("championModel", gov_line.get("champion_model"))
        fallback_model = gov_line_info.get("fallbackModel", gov_line.get("fallback_model"))
        model_used = gov_line.get("model_used", "legacy_blend")

        mo = MarketOutput(
            market_type="Corners",
            selection=f"Corners {threshold_label}",
            raw_probability=raw,
            calibrated_probability=calibrated,
            book_odd=corner_odd,
            odds_available=corner_odd is not None,
            data_quality_score=quality,
            source_flags=[*source_flags, f"corner_model:{model_used}"],
            display_label=f"Escanteios {threshold_label}",
        )

        classified = classify_market(mo)

        # Attach corner governance metadata
        classified.corner_governance = {
            "marketFamily": "corners",
            "cornerModelStatus": operational_state,
            "championModel": champion_model,
            "fallbackModel": fallback_model,
            "modelUsed": model_used,
            "beatsPoisson": gov_line.get("beats_poisson", False) if isinstance(gov_line, dict) else False,
            "beatsNegativeBinomial": gov_line.get("beats_negative_binomial", False) if isinstance(gov_line, dict) else False,
            "beatsMLRegression": gov_line.get("beats_ml_regression", False) if isinstance(gov_line, dict) else False,
            "cornerCalibrationStatus": gov_line_info.get("cornerCalibrationStatus", "uncalibrated"),
            "cornerSampleAdequacy": gov_line_info.get("cornerSampleAdequacy", "unknown"),
            "cornerValidationVersion": corner_governance.get("cornerValidationVersion", "unknown"),
        }

        markets.append(classified)

    # ─── Apply early season penalty ───
    if early_season:
        for m in markets:
            if ReasonCode.EARLY_SEASON_FALLBACK not in m.reason_codes:
                m.reason_codes.append(ReasonCode.EARLY_SEASON_FALLBACK)
            # Downgrade SAFE to NEUTRO in early season
            if m.classification == MarketClassification.SAFE:
                m.classification = MarketClassification.NEUTRO_QUALIFICADO

    # ─── Filter NO_BET markets that have zero probability ───
    active_markets = [m for m in markets if (m.calibrated_probability or m.raw_probability or 0) > 0.05]

    # ─── Build bundle ───
    bundle = MatchMarketBundle(
        match_id=match_id,
        home_team=str(home_team),
        away_team=str(away_team),
        league_id=league_id,
        data_quality_score=quality,
        markets=active_markets,
    )

    # Check eligibility for multiples
    eligible = [m for m in active_markets
                if m.classification in (MarketClassification.SAFE, MarketClassification.NEUTRO_QUALIFICADO)
                and m.odds_available]
    bundle.eligible_for_multiples = len(eligible) > 0

    if early_season:
        bundle.reason_codes.append(ReasonCode.EARLY_SEASON_FALLBACK)

    return bundle


def _market_category(market_type: str) -> str:
    """Map specific market type to category for threshold lookup."""
    if market_type in ("1X2",):
        return "1X2"
    if market_type in ("Over/Under",):
        return "Over/Under"
    if market_type in ("BTTS",):
        return "BTTS"
    if market_type in ("Double Chance",):
        return "Double Chance"
    if market_type in ("Corners",):
        return "Corners"
    return "1X2"  # fallback
