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


# ── Probability deflation by band + per-league (#105) ──────────────────
# Based on Brier #104 (379 picks): model overconfident at 70%+ bands.
# Replaces uniform 15% concept (#043) with progressive deflation.

_LEAGUE_DEFLATION = {
    "brasileirao-serie-a": 0.90,  # Δ=-0.075, Acc=46% (N=24)
    "league-two": 0.95,           # Δ=-0.013, Acc=48% (N=23)
}


def _band_deflation(prob: float) -> float:
    """Progressive deflation by probability band."""
    if prob >= 0.80:
        return 0.25
    if prob >= 0.70:
        return 0.20
    if prob >= 0.60:
        return 0.15
    if prob >= 0.50:
        return 0.12
    return 0.10


def apply_probability_deflation(prob: float, league_id: str = "") -> float:
    """Apply progressive band deflation + per-league factor (#105).

    Args:
        prob: Model probability (0-1)
        league_id: League slug for per-league adjustment

    Returns:
        Deflated probability, floored at 0.05.
    """
    deflation = _band_deflation(prob)
    deflated = prob * (1.0 - deflation)

    # Per-league factor (never below 0.85)
    if league_id:
        factor = _LEAGUE_DEFLATION.get(league_id, 1.0)
        deflated *= max(factor, 0.85)

    return max(deflated, 0.05)


def _calibrate_and_deflate(raw: float, market: str, league_id: str, regime: str) -> float:
    """Calibrate via Isotonic model then apply band+league deflation (#105, #113, #152)."""
    calibrated = calibrate_prob(raw, market, league_id, regime)
    # BTTS: lambda already deflated per-league in poisson_matrix (btts_multiplier).
    # Applying full band deflation on top causes double-penalty (~64% → ~44%).
    # #152: halve band deflation for BTTS to prevent excessive cumulative deflation.
    if market.upper() == "BTTS":
        deflation = _band_deflation(calibrated)
        half_deflation = deflation / 2.0
        result = calibrated * (1.0 - half_deflation)
        # Per-league factor still applies
        if league_id:
            factor = _LEAGUE_DEFLATION.get(league_id, 1.0)
            result *= max(factor, 0.85)
        result = max(result, 0.05)
    else:
        result = apply_probability_deflation(calibrated, league_id)
    # Under 2.5 extra deflation — worst market in Brier #104 (Δ=-0.03, acc=57%) (#113)
    if "under" in market.lower() and "2.5" in market:
        result *= 0.90
    return result
from backend.modeling.corners.predictor import predict_corners, get_corner_governance_info
from backend.modeling.corners.operational_states import CornerOperationalState
from backend.services.data_governance import (
    calculate_data_quality_score,
    detect_early_season,
    check_odds_availability,
)

logger = logging.getLogger("sportsbankzu.ev_classification")

# ─── SAFE Circuit Breaker ───
# Global override: True = force-disable SAFE for ALL leagues (emergency)
# When False, per-league SAFE status from calibration DB is used (#052)
SAFE_CIRCUIT_BREAKER_ENABLED = False

# ─── Shadow Mode (#129c) ───
# When True: SAFE is computed internally but displayed as NQ.
# Shadow picks are logged for accuracy measurement.
# When accuracy > 50% (N >= 50), set to False to show SAFE to users.
import os
SAFE_SHADOW_MODE = os.getenv("SAFE_SHADOW_MODE", "true").lower() == "true"
_shadow_logger = logging.getLogger("sportsbankzu.safe_shadow")


def _is_safe_enabled(league_id: str | None) -> bool:
    """Check if SAFE classification is enabled for this league.

    Per-league SAFE status from calibration DB (#052).
    Default: disabled (conservative — requires calibration to enable).
    Global override: SAFE_CIRCUIT_BREAKER_ENABLED=True forces all disabled.
    """
    if SAFE_CIRCUIT_BREAKER_ENABLED:
        return False  # Global emergency override
    if not league_id:
        return False
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        safe_val = corrections.get("safe_enabled", {}).get("value", "0")
        try:
            return float(safe_val) >= 1.0
        except (ValueError, TypeError):
            return str(safe_val).lower() in ("true", "1", "yes", "1.0")
    except Exception:
        return False  # Default: disabled

# ─── Dynamic Thresholds per Market ───
# Each market has thresholds for SAFE and NEUTRO classification
# These are defaults; can be overridden from audit DB (Gap 4)

DEFAULT_THRESHOLDS = {
    "1X2": {
        "safe_prob": 0.62,    "neutro_prob": 0.45,
        "safe_ev": 0.08,      "neutro_ev": 0.00,
        "safe_edge": 0.06,    "neutro_edge": 0.02,
        "min_quality": 0.40,
    },
    "Over/Under": {
        "safe_prob": 0.75,    "neutro_prob": 0.60,
        "safe_ev": 0.06,      "neutro_ev": 0.00,
        "safe_edge": 0.05,    "neutro_edge": 0.02,
        "min_quality": 0.40,
    },
    "BTTS": {
        "safe_prob": 0.75,    "neutro_prob": 0.62,
        "safe_ev": 0.06,      "neutro_ev": 0.00,
        "safe_edge": 0.05,    "neutro_edge": 0.02,
        "min_quality": 0.40,
    },
    "Double Chance": {
        "safe_prob": 0.82,    "neutro_prob": 0.68,
        "safe_ev": 0.04,      "neutro_ev": 0.00,
        "safe_edge": 0.03,    "neutro_edge": 0.01,
        "min_quality": 0.40,
    },
    "Corners": {
        "safe_prob": 0.72,    "neutro_prob": 0.58,
        "safe_ev": 0.08,      "neutro_ev": 0.02,
        "safe_edge": 0.06,    "neutro_edge": 0.02,
        "min_quality": 0.45,
    },
    "Cards": {
        "safe_prob": 0.78,    "neutro_prob": 0.60,  # Conservative until NB2 validated (#085b)
        "safe_ev": 0.08,      "neutro_ev": 0.02,
        "safe_edge": 0.06,    "neutro_edge": 0.02,
        "min_quality": 0.45,
    },
}

# Minimum thresholds for NEUTRO qualificado (eligible for multiples)
NEUTRO_QUALIFICADO_THRESHOLDS = {
    "min_ev": 0.05,          # EV must be >= 5% (was 2%)
    "min_edge": 0.03,        # edge must be >= 3%
    "min_quality": 0.45,     # data quality >= 0.45 (was 0.40)
    "min_prob": 0.52,        # calibrated prob >= 52% (was 50%)
    "must_have_odds": True,  # real odds required
}


def _get_calibrated_threshold(league_id: str | None, market_category: str) -> Dict[str, float] | None:
    """Get per-league calibrated threshold from corrections DB (#055)."""
    if not league_id:
        return None
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)

        param_map = {
            "Over/Under": "safe_prob_ou",
            "BTTS": "safe_prob_btts",
            "1X2": "safe_prob_1x2",
            "Double Chance": "safe_prob_dc",
            "Corners": "safe_prob_corners",
            "Cards": "safe_prob_cards",
        }

        param_name = param_map.get(market_category)
        if param_name:
            val = corrections.get(param_name, {}).get("value")
            if val is not None:
                return {"safe_prob": float(val)}
        return None
    except Exception:
        return None


def _get_thresholds(market_category: str, league_id: str | None = None) -> Dict[str, float]:
    """Get thresholds with priority: calibrated per-league > audit DB > defaults."""
    base = dict(DEFAULT_THRESHOLDS.get(market_category, DEFAULT_THRESHOLDS["1X2"]))

    # 1. Check per-league calibration (#055)
    calibrated = _get_calibrated_threshold(league_id, market_category)
    if calibrated:
        base.update(calibrated)
        return base

    # 2. Check audit DB dynamic thresholds
    try:
        from backend.services.market_service import _get_dynamic_thresholds
        db_th = _get_dynamic_thresholds(market_category)
        if db_th:
            if "SAFE" in db_th:
                base["safe_prob"] = db_th["SAFE"]
            if "NEUTRO" in db_th:
                base["neutro_prob"] = db_th["NEUTRO"]
    except Exception:
        pass

    return base


def classify_market(
    output: MarketOutput,
    thresholds: Optional[Dict[str, float]] = None,
    league_id: str = "",
    projection: Optional[float] = None,  # #126: model projection for direction-based classification
) -> MarketOutput:
    """Classify a single market output as SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET.

    Mutates the output in-place and returns it.

    Classification uses raw_probability (pre-deflation) for threshold comparison (#106).
    EV uses calibrated_probability (post-deflation) for realistic bet sizing (#105).
    VIA 2 (#126): picks in the model's natural direction promoted to NEUTRO_QUALIFICADO.
    """
    # prob_for_class: raw model confidence (before deflation) — for SAFE/NEUTRO thresholds
    # prob_for_ev: deflated probability — for EV calculation (already in calibrated_probability)
    prob_for_class = calibrate_prob(
        output.raw_probability or 0.0,
        _market_category(output.market_type),
        league_id, "",
    ) if output.raw_probability else (output.calibrated_probability or 0.0)
    prob = output.calibrated_probability or output.raw_probability or 0.0
    market_cat = _market_category(output.market_type)
    th = thresholds or _get_thresholds(market_cat, league_id=league_id)

    # Compute EV and display
    output.compute_ev()
    output.compute_display()

    reason_codes: List[ReasonCode] = []

    # ─── Data quality checks ───
    if output.data_quality_score < th.get("min_quality", 0.3):
        reason_codes.append(ReasonCode.LOW_DATA_QUALITY)

    if not output.odds_available:
        reason_codes.append(ReasonCode.NO_ODDS_AVAILABLE)

    # ─── EV sanity cap (#064, #116) ───
    # EV > 40% is almost certainly a data issue (prob/odds mismatch).
    # #116: Instead of capping to exactly 40% (which shows misleading "+40.0%"),
    # null out EV/edge so the market is treated as informational only.
    MAX_CREDIBLE_EV = 0.40
    if output.ev is not None and output.ev > MAX_CREDIBLE_EV and output.book_odd and output.book_odd > 1.0:
        original_prob = prob
        original_ev = output.ev
        reason_codes.append(ReasonCode.SUSPICIOUS_EV)
        # Null out EV — don't show a misleading capped value (#116)
        output.ev = None
        output.edge = None
        logger.warning(
            f"[EV Cap] {output.display_label}: EV={original_ev:.1%} > {MAX_CREDIBLE_EV:.0%} "
            f"(suspicious). EV nulled. prob={original_prob:.1%}, odd={output.book_odd}."
        )

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

    if prob_for_class >= th.get("safe_prob", 0.60):
        reason_codes.append(ReasonCode.HIGH_CALIBRATED_PROB)

    # ─── Classification logic (#106: use prob_for_class for thresholds) ───
    classification = MarketClassification.NO_BET

    # #127: Pre-compute direction info for VIA 2 (used throughout classification)
    _DIRECTION_MIN_ODD = 1.50
    _DIRECTION_RESCUE_PROB = 0.50  # #127: floor for direction rescue
    _dir_natural = False
    _dir_against = False
    _dir_nz = 0.5
    _dir_diff = 0.0

    if projection is not None and projection > 0:
        import re as _re
        _lm = _re.search(r"(\d+\.?\d*)", output.selection or "")
        if _lm:
            _dir_line = float(_lm.group(1))
            _dir_diff = projection - _dir_line
            _dir_nz = _get_direction_neutral_zone(output.market_type)  # #127: proportional
            _is_over = "over" in (output.selection or "").lower()
            _is_under = "under" in (output.selection or "").lower()
            _dir_odd_ok = output.book_odd is not None and output.book_odd >= _DIRECTION_MIN_ODD

            if abs(_dir_diff) > _dir_nz and (_is_over or _is_under) and _dir_odd_ok:
                _dir_natural = (_dir_diff > 0 and _is_over) or (_dir_diff < 0 and _is_under)
                _dir_against = (_dir_diff > 0 and _is_under) or (_dir_diff < 0 and _is_over)

    # SAFE: high prob + positive EV + sufficient edge + good data
    if (prob_for_class >= th.get("safe_prob", 0.60) and
        output.data_quality_score >= th.get("min_quality", 0.3)):
        if ReasonCode.SUSPICIOUS_EV in reason_codes:
            classification = MarketClassification.NEUTRO
        elif (output.odds_available and
              output.ev is not None and output.ev >= th.get("safe_ev", 0.05) and
              output.edge is not None and output.edge >= th.get("safe_edge", 0.04)):
            classification = MarketClassification.SAFE
        elif output.odds_available and output.ev is not None and output.ev >= 0:
            classification = MarketClassification.NEUTRO
        elif not output.odds_available:
            classification = MarketClassification.NEUTRO

    # NEUTRO: moderate prob
    elif (prob_for_class >= th.get("neutro_prob", 0.50) and
          output.data_quality_score >= th.get("min_quality", 0.3) * 0.8):
        if output.odds_available and output.ev is not None and output.ev >= th.get("neutro_ev", 0.0):
            classification = MarketClassification.NEUTRO
        elif not output.odds_available:
            classification = MarketClassification.NEUTRO
        # #127: VIA 2 rescue — NEUTRO even with negative EV if direction confirms
        elif _dir_natural and output.odds_available:
            classification = MarketClassification.NEUTRO
            reason_codes.append(ReasonCode.DIRECTION_NATURAL_MATCH)
            logger.info(
                f"[direction-rescue] {output.display_label}: rescued to NEUTRO "
                f"(ev={output.ev}, but dir confirms, proj diff={_dir_diff:+.1f})"
            )

    # #127: VIA 2 rescue for prob below neutro_prob (0.50-0.59 range)
    elif (prob_for_class >= _DIRECTION_RESCUE_PROB and _dir_natural and
          output.data_quality_score >= th.get("min_quality", 0.3) * 0.8):
        classification = MarketClassification.NEUTRO
        reason_codes.append(ReasonCode.DIRECTION_NATURAL_MATCH)
        logger.info(
            f"[direction-rescue] {output.display_label}: NO_BET->NEUTRO "
            f"(raw={prob_for_class:.3f} < neutro but > rescue {_DIRECTION_RESCUE_PROB}, "
            f"proj diff={_dir_diff:+.1f})"
        )

    # NEUTRO qualificado: upgrade if meets criteria (VIA 1 — EV based)
    if classification == MarketClassification.NEUTRO:
        if _is_neutro_qualificado(output, prob_for_class) and ReasonCode.SUSPICIOUS_EV not in reason_codes:
            classification = MarketClassification.NEUTRO_QUALIFICADO
        # #126/#127: VIA 2 — direction-based upgrade to NQ
        # #130: REQUIRE EV >= 0 — VIA 2 cannot promote with negative EV
        elif (_dir_natural and prob_for_class >= th.get("neutro_prob", 0.50)
              and ReasonCode.SUSPICIOUS_EV not in reason_codes):
            if output.ev is not None and output.ev >= 0:
                classification = MarketClassification.NEUTRO_QUALIFICADO
                if ReasonCode.DIRECTION_NATURAL_MATCH not in reason_codes:
                    reason_codes.append(ReasonCode.DIRECTION_NATURAL_MATCH)
                logger.info(
                    f"[direction-via2] {output.display_label}: NEUTRO->NQ "
                    f"(proj diff={_dir_diff:+.1f}, ev={output.ev:+.1%})"
                )
            else:
                # #130: Direction natural OK but EV < 0 → keep NEUTRO with informative reason
                if ReasonCode.DIRECTION_NATURAL_NO_EV not in reason_codes:
                    reason_codes.append(ReasonCode.DIRECTION_NATURAL_NO_EV)
                logger.info(
                    f"[via2-blocked] {output.display_label}: direction OK but EV={output.ev} < 0. "
                    f"Kept NEUTRO (not promoted to NQ)."
                )

    # #126: Direction AGAINST → force NO_BET
    if _dir_against and classification in (
        MarketClassification.NEUTRO, MarketClassification.NEUTRO_QUALIFICADO
    ):
        classification = MarketClassification.NO_BET
        reason_codes.append(ReasonCode.DIRECTION_AGAINST_PROJFT)
        logger.info(
            f"[direction-via2] {output.display_label}: ->NO_BET "
            f"(against direction, proj diff={_dir_diff:+.1f})"
        )

    # Force NO_BET on negative EV with very low prob (below rescue threshold)
    if (output.odds_available and output.ev is not None and
        output.ev < -0.05 and prob_for_class < _DIRECTION_RESCUE_PROB):
        classification = MarketClassification.NO_BET
        if ReasonCode.NEGATIVE_EV not in reason_codes:
            reason_codes.append(ReasonCode.NEGATIVE_EV)

    # ─── Force NO_BET on absurdly high EV (#064) ───
    if (ReasonCode.SUSPICIOUS_EV in reason_codes and
            output.ev is not None and output.ev > 1.0):
        classification = MarketClassification.NO_BET
        logger.warning(
            f"[EV Force NO_BET] {output.display_label}: EV={output.ev:.1%} still >100% after cap, "
            f"forcing NO_BET"
        )

    # ─── SAFE Circuit Breaker — per-league (#052) + Shadow Mode (#129c) ───
    if classification == MarketClassification.SAFE and not _is_safe_enabled(league_id):
        # #129c: Log shadow SAFE for accuracy tracking
        if SAFE_SHADOW_MODE:
            _shadow_logger.info(
                f"SHADOW_SAFE|{output.display_label}|league={league_id}|"
                f"raw={output.raw_probability}|calib={output.calibrated_probability}|"
                f"odd={output.book_odd}|ev={output.ev}"
            )
        classification = MarketClassification.NEUTRO_QUALIFICADO
        reason_codes.append(ReasonCode.SAFE_CIRCUIT_BREAKER)
        logger.info(
            f"[Circuit Breaker] {output.display_label}: SAFE → NEUTRO_QUALIFICADO "
            f"(SAFE not enabled for league '{league_id}'"
            f"{', shadow=ON' if SAFE_SHADOW_MODE else ''})"
        )

    output.classification = classification
    output.reason_codes = reason_codes
    # #129c: mark shadow SAFE picks for audit tracking
    if ReasonCode.SAFE_CIRCUIT_BREAKER in reason_codes and SAFE_SHADOW_MODE:
        output.source_flags = list(output.source_flags or []) + ["shadow_safe"]
    return output


def _is_neutro_qualificado(output: MarketOutput, prob: float) -> bool:
    """Check if a NEUTRO market qualifies for multiples eligibility."""
    th = NEUTRO_QUALIFICADO_THRESHOLDS

    if th["must_have_odds"] and not output.odds_available:
        return False

    if output.ev is None or output.ev < th["min_ev"]:
        return False

    # Require minimum edge
    if output.edge is None or output.edge < th.get("min_edge", 0.03):
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
    # Normalize team names — handle both string and dict formats
    _raw_home = match_data.get("homeTeam", match_data.get("home_team", ""))
    _raw_away = match_data.get("awayTeam", match_data.get("away_team", ""))
    home_team = _raw_home.get("name", _raw_home.get("team_name", str(_raw_home))) if isinstance(_raw_home, dict) else str(_raw_home)
    away_team = _raw_away.get("name", _raw_away.get("team_name", str(_raw_away))) if isinstance(_raw_away, dict) else str(_raw_away)
    match_id = str(match_data.get("id", match_data.get("match_id", "")))

    # ─── Data quality ───
    quality = calculate_data_quality_score(stats, odds, league_stats)
    early_season = detect_early_season(league_stats)

    # ─── Derive probabilities from Poisson matrix when lambdas available ───
    lambda_home = stats.get("lambdaHome")
    lambda_away = stats.get("lambdaAway")

    derived = {}
    _goals_projection = None  # #126: total goals projection for direction classification
    if lambda_home and lambda_away and float(lambda_home) > 0 and float(lambda_away) > 0:
        derived = derive_all_markets(float(lambda_home), float(lambda_away), league_id=league_id)
        _goals_projection = float(lambda_home) + float(lambda_away)

    # Lambda floor detection (#064): when both lambdas are clamped to LAMBDA_MIN,
    # it means team lookup failed — Poisson output is pure noise from league averages.
    # Discard derived to fall through to FootyStats/odds-implied.
    from backend.modeling.lambda_calculator import LAMBDA_MIN
    _FLOOR_TOLERANCE = 0.02
    _lambda_at_floor = (
        lambda_home is not None and lambda_away is not None
        and float(lambda_home) <= LAMBDA_MIN + _FLOOR_TOLERANCE
        and float(lambda_away) <= LAMBDA_MIN + _FLOOR_TOLERANCE
    )
    if _lambda_at_floor and derived:
        logger.warning(
            f"[lambda-floor] {home_team} vs {away_team}: both lambdas at floor "
            f"({lambda_home}/{lambda_away}), discarding Poisson-derived probs"
        )
        derived = {}
        # Reduce quality score — model has no real data for these teams
        quality = max(0.0, quality - 0.20)

    if not derived:
        logger.warning(
            f"[ev] No Poisson-derived probs: λH={lambda_home} λA={lambda_away} "
            f"match={home_team} vs {away_team}"
        )

    # ─── Derive corner probabilities (governed framework v2) ───
    governed_corners = predict_corners(
        home_stats=stats,
        away_stats=stats,
        league_id=league_id,
        league_stats=league_stats if isinstance(league_stats, dict) else None,
        footystats_probs=stats,
        odds=odds,
    )

    # Legacy fallback for backward compat
    corner_probs = derive_corner_probabilities(
        home_stats=stats,
        away_stats=stats,
        league_stats=league_stats if isinstance(league_stats, dict) else None,
        footystats_probs=stats,
        league_id=league_id,
    )

    # ─── Build market outputs ───
    markets: List[MarketOutput] = []
    source_flags = ["footystats"]

    # Helper: get probability — PRIORITY depends on market type (#061)
    # For O/U and BTTS: prefer Poisson-derived (deflated) over FootyStats
    # For 1X2: prefer stats (odds-implied) over Poisson
    def _prob(stat_key: str, derived_key: str = "") -> Optional[float]:
        # Priority 1: derived probabilities (with per-league deflation)
        if derived_key:
            # Try exact key
            d_val = derived.get(derived_key)
            # Try without "Prob" suffix (handle key format variations)
            if d_val is None:
                alt_key = derived_key.replace("Prob", "")
                d_val = derived.get(alt_key)
            if d_val is not None:
                v = float(d_val)
                if 0 < v <= 1.0:
                    return v
                elif v > 1.0:
                    return v / 100.0
        # Priority 2: stats (FootyStats pre-match %, may be league aggregate)
        val = stats.get(stat_key)
        if val is not None:
            try:
                v = float(val)
                if v > 1.0:
                    return v / 100.0
                if v > 0:
                    return v
            except (ValueError, TypeError):
                pass
        return None

    # 1X2 markets — prefer odds-implied (stats) when odds available (#064)
    # Poisson 1X2 diverges 20-30pp from market (e.g. Paris Home=80% vs odd=2.00=50%),
    # creating fake EV. Use odds-implied as primary; Poisson only as fallback.
    _1x2_has_odds = (
        odds.get("home") and odds.get("draw") and odds.get("away")
        and float(odds.get("home", 0)) > 1.0
    )
    # Diagnostic: trace 1X2 source (#064)
    logger.debug(
        f"[prob-trace][1X2] {home_team} vs {away_team} | "
        f"has_odds={_1x2_has_odds} "
        f"stats[homeWinProb]={stats.get('homeWinProb')} "
        f"derived[homeWinProb]={derived.get('homeWinProb')} "
        f"odds={{h={odds.get('home')},d={odds.get('draw')},a={odds.get('away')}}}"
    )
    for selection, stat_key, derived_key, odd_key in [
        ("Home", "homeWinProb", "homeWinProb", "home"),
        ("Draw", "drawProb", "drawProb", "draw"),
        ("Away", "awayWinProb", "awayWinProb", "away"),
    ]:
        # When odds available: skip derived_key so _prob uses stats (odds-implied)
        # When no odds: use Poisson-derived as fallback
        raw = _prob(stat_key) if _1x2_has_odds else _prob(stat_key, derived_key)
        if raw is None:
            continue
        calibrated = _calibrate_and_deflate(raw, f"1X2_{selection.lower()}", league_id, regime)
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
        markets.append(classify_market(mo, league_id=league_id))

    # Over/Under markets — diagnostic: trace Poisson vs FootyStats source (#061)
    _d_val = derived.get("over25Prob")
    _s_val = stats.get("over25Prob")
    logger.debug(
        f"[ev][prob-source] {home_team} vs {away_team} | "
        f"derived[over25Prob]={_d_val} stats[over25Prob]={_s_val} "
        f"derived_keys={len(derived)} lamH={lambda_home} lamA={lambda_away}"
    )

    for threshold, stat_over, stat_under, odd_key in [
        ("0.5", "over05Prob", "under05Prob", "over05"),
        ("1.5", "over15Prob", "under15Prob", "over15"),
        ("2.5", "over25Prob", "under25Prob", "over25"),
        ("3.5", "over35Prob", "under35Prob", "over35"),
        ("4.5", "over45Prob", "under45Prob", "over45"),
        ("5.5", "over55Prob", "under55Prob", "over55"),
    ]:
        # Diagnostic: trace which source _prob() uses (#063)
        _dk = f"over{threshold.replace('.', '')}Prob"
        _dk_alt = _dk.replace("Prob", "")
        logger.debug(
            f"[prob-trace] {home_team} vs {away_team} | {stat_over}: "
            f"stats={stats.get(stat_over)} derived={derived.get(_dk)} "
            f"derived_alt={derived.get(_dk_alt)} lamH={lambda_home} lamA={lambda_away}"
        )
        # Over
        raw_over = _prob(stat_over, f"over{threshold.replace('.', '')}Prob")
        if raw_over is not None:
            calibrated = _calibrate_and_deflate(raw_over, f"Over {threshold}", league_id, regime)
            book_odd = odds.get(odd_key)
            book_odd = float(book_odd) if book_odd and float(book_odd) > 1.0 else None
            # #127: skip Over 0.5 without odds or with very low odds (noise)
            if threshold == "0.5" and (book_odd is None or book_odd < 1.30):
                continue
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
            markets.append(classify_market(mo, league_id=league_id, projection=_goals_projection))

        # Under
        raw_under = _prob(stat_under, f"under{threshold.replace('.', '')}Prob")
        if raw_under is None and raw_over is not None:
            raw_under = 1.0 - raw_over
        if raw_under is not None:
            calibrated = _calibrate_and_deflate(raw_under, f"Under {threshold}", league_id, regime)
            # Under odds: prefer real odds, fallback to derived with overround discount
            under_key = f"under{threshold.replace('.', '')}"  # "under25", "under35", "under45"
            under_odd = odds.get(under_key)
            if under_odd:
                under_odd = float(under_odd) if float(under_odd) > 1.0 else None

            if under_odd is None and book_odd and book_odd > 1.0:
                # Derive from Over: implied_under = OVERROUND - implied_over
                OVERROUND = 1.05
                implied_over = 1.0 / book_odd
                implied_under = OVERROUND - implied_over
                under_odd = round(1.0 / implied_under, 2) if implied_under > 0.01 else None
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
            markets.append(classify_market(mo, league_id=league_id, projection=_goals_projection))

    # BTTS
    raw_btts = _prob("bttsProb", "bttsProb")
    if raw_btts is not None:
        calibrated = _calibrate_and_deflate(raw_btts, "BTTS", league_id, regime)
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
        markets.append(classify_market(mo, league_id=league_id))

    # Double Chance (derived from 1X2 — use same source priority as 1X2 #064)
    if _1x2_has_odds:
        home_prob = _prob("homeWinProb")
        draw_prob = _prob("drawProb")
        away_prob = _prob("awayWinProb")
    else:
        home_prob = _prob("homeWinProb", "homeWinProb")
        draw_prob = _prob("drawProb", "drawProb")
        away_prob = _prob("awayWinProb", "awayWinProb")

    if home_prob is not None and draw_prob is not None:
        dc_1x = home_prob + draw_prob
        calibrated = _calibrate_and_deflate(dc_1x, "Double Chance 1X", league_id, regime)
        # DC odds: prefer real from API-Football (#111), fallback to derived
        dc_odd = None
        _real_dc = odds.get("dc_1x")
        if _real_dc and float(_real_dc) > 1.0:
            dc_odd = float(_real_dc)
        else:
            h_odd = odds.get("home")
            d_odd = odds.get("draw")
            if h_odd and d_odd and float(h_odd) > 1.0 and float(d_odd) > 1.0:
                implied_h = 1.0 / float(h_odd)
                implied_d = 1.0 / float(d_odd)
                dc_implied = implied_h + implied_d
                if dc_implied > 0 and dc_implied < 1.0:
                    dc_odd = round(1.0 / dc_implied, 2)

        home_label = home_team[:3].upper() if home_team else "CAS"
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
        markets.append(classify_market(mo, league_id=league_id))

    # DC 12 (Home or Away = 1 - Draw) (#111)
    if home_prob is not None and away_prob is not None:
        dc_12 = home_prob + away_prob
        cal_12 = _calibrate_and_deflate(dc_12, "Double Chance 12", league_id, regime)
        dc_12_odd = None
        _real_12 = odds.get("dc_12")
        if _real_12 and float(_real_12) > 1.0:
            dc_12_odd = float(_real_12)
        elif odds.get("home") and odds.get("away"):
            imp_h = 1.0 / float(odds["home"])
            imp_a = 1.0 / float(odds["away"])
            imp_12 = imp_h + imp_a
            if 0 < imp_12 < 1.0:
                dc_12_odd = round(1.0 / imp_12, 2)
        mo = MarketOutput(
            market_type="Double Chance", selection="DC 12",
            raw_probability=dc_12, calibrated_probability=cal_12,
            book_odd=dc_12_odd, odds_available=dc_12_odd is not None,
            data_quality_score=quality, source_flags=source_flags,
            display_label=f"DC 12 ({home_team[:3].upper() if home_team else 'CAS'}/{away_team[:3].upper() if away_team else 'FOR'})",
        )
        markets.append(classify_market(mo, league_id=league_id))

    # DC X2 (Draw or Away) (#111)
    if draw_prob is not None and away_prob is not None:
        dc_x2 = draw_prob + away_prob
        cal_x2 = _calibrate_and_deflate(dc_x2, "Double Chance X2", league_id, regime)
        dc_x2_odd = None
        _real_x2 = odds.get("dc_x2")
        if _real_x2 and float(_real_x2) > 1.0:
            dc_x2_odd = float(_real_x2)
        elif odds.get("draw") and odds.get("away"):
            imp_d = 1.0 / float(odds["draw"])
            imp_a = 1.0 / float(odds["away"])
            imp_x2 = imp_d + imp_a
            if 0 < imp_x2 < 1.0:
                dc_x2_odd = round(1.0 / imp_x2, 2)
        mo = MarketOutput(
            market_type="Double Chance", selection="DC X2",
            raw_probability=dc_x2, calibrated_probability=cal_x2,
            book_odd=dc_x2_odd, odds_available=dc_x2_odd is not None,
            data_quality_score=quality, source_flags=source_flags,
            display_label=f"DC X2 (EMP/{away_team[:3].upper() if away_team else 'FOR'})",
        )
        markets.append(classify_market(mo, league_id=league_id))

    # Corner markets (governed framework v2 — bidirectional Over + Under)
    corner_governance = get_corner_governance_info(league_id)
    v2_projection = governed_corners.get("projection", {})
    _corners_projection = v2_projection.get("expected_total_corners_ft") if v2_projection else None  # #126
    v2_engine_version = governed_corners.get("engine_version", governed_corners.get("engineVersion", "1.0.0"))
    v2_lines = governed_corners.get("lines", {})

    # FootyStats stat keys and odds keys for legacy lines (used as fallback)
    _FOOTYSTATS_STAT_MAP = {
        8.5: "cornerOver85Prob", 9.5: "cornerOver95Prob",
        10.5: "cornerOver105Prob", 11.5: "cornerOver115Prob",
    }
    _FOOTYSTATS_ODD_MAP = {
        8.5: "cornersOver85", 9.5: "cornersOver95",
        10.5: "cornersOver105", 11.5: "cornersOver115",
    }

    # Iterate ALL v2 lines (4.5-12.5) for Over markets
    from backend.modeling.corners import CORNER_LINES

    # Pass 1: collect raw probs per line from waterfall sources
    _corner_raw: Dict[float, Tuple[float, str, dict]] = {}  # line_val → (raw, source, gov_line)
    for line_val in CORNER_LINES:
        line_key = f"over_{line_val}"
        gov_line = v2_lines.get(line_key, {})
        raw = gov_line.get("probability")
        _corner_source = "v2_governed" if raw is not None else None
        if raw is None:
            raw = corner_probs.get(line_key)
            if raw is not None:
                _corner_source = "legacy_engine"
        if raw is None:
            stat_key = _FOOTYSTATS_STAT_MAP.get(line_val)
            if stat_key:
                raw = _prob(stat_key)
                if raw is not None:
                    _corner_source = "footystats_raw"
        if raw is not None:
            _corner_raw[line_val] = (raw, _corner_source or "", gov_line)

    # Enforce monotonicity (#121): P(Over N+1) <= P(Over N)
    sorted_corner_lines = sorted(_corner_raw.keys())
    for i in range(1, len(sorted_corner_lines)):
        prev_line = sorted_corner_lines[i - 1]
        curr_line = sorted_corner_lines[i]
        prev_raw = _corner_raw[prev_line][0]
        curr_raw, curr_src, curr_gov = _corner_raw[curr_line]
        if curr_raw > prev_raw:
            logger.info(
                f"[monotonicity-corners] {home_team} vs {away_team}: "
                f"Over {curr_line} capped {curr_raw:.4f} -> {prev_raw:.4f} "
                f"(was > Over {prev_line}={prev_raw:.4f}, source={curr_src})"
            )
            _corner_raw[curr_line] = (prev_raw, curr_src, curr_gov)

    # Pass 2: build MarketOutputs with corrected probs
    for line_val in CORNER_LINES:
        if line_val not in _corner_raw:
            continue
        raw, _corner_source, gov_line = _corner_raw[line_val]
        line_key = f"over_{line_val}"
        threshold_label = f"Over {line_val}"

        logger.debug(
            f"[prob-trace][corners] {home_team} vs {away_team} | "
            f"line={line_val} source={_corner_source} raw={raw:.3f} "
            f"v2={gov_line.get('probability')} legacy={corner_probs.get(line_key)}"
        )

        calibrated = _calibrate_and_deflate(raw, f"Escanteios {threshold_label}", league_id, regime)

        # Odds: try v2 book_odd_over, then FootyStats odds key
        corner_odd = gov_line.get("book_odd_over")
        if corner_odd is None:
            odd_key = _FOOTYSTATS_ODD_MAP.get(line_val)
            if odd_key:
                corner_odd = odds.get(odd_key)
        corner_odd = float(corner_odd) if corner_odd and float(corner_odd) > 1.0 else None

        gov_line_info = corner_governance.get("lines", {}).get(line_key, {})
        operational_state = gov_line_info.get("operationalState", gov_line.get("operational_state", "RESTRICTED"))
        champion_model = gov_line_info.get("championModel", gov_line.get("champion_model"))
        fallback_model = gov_line_info.get("fallbackModel", gov_line.get("fallback_model"))
        model_used = gov_line.get("model_used", "corners_engine_v2")

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

        classified = classify_market(mo, league_id=league_id, projection=_corners_projection)
        classified.corner_governance = {
            "marketFamily": "corners",
            "engineVersion": v2_engine_version,
            "cornerModelStatus": operational_state,
            "side": "OVER",
            "championModel": champion_model,
            "fallbackModel": fallback_model,
            "modelUsed": model_used,
            "projectedTotalCornersFT": v2_projection.get("expected_total_corners_ft"),
            "projectedTotalCorners1H": v2_projection.get("expected_total_corners_1h"),
            "projectedTotalCorners2H": v2_projection.get("expected_total_corners_2h"),
            "beatsPoisson": gov_line.get("beats_poisson", False) if isinstance(gov_line, dict) else False,
            "beatsNegativeBinomial": gov_line.get("beats_negative_binomial", False) if isinstance(gov_line, dict) else False,
            "beatsMLRegression": gov_line.get("beats_ml_regression", False) if isinstance(gov_line, dict) else False,
            "cornerCalibrationStatus": gov_line_info.get("cornerCalibrationStatus", "uncalibrated"),
            "cornerSampleAdequacy": gov_line_info.get("cornerSampleAdequacy", "unknown"),
            "cornerValidationVersion": corner_governance.get("cornerValidationVersion", v2_engine_version),
        }
        markets.append(classified)

    # Under lines (v2 — bidirectional, all lines from CORNER_LINES)
    for line_val in CORNER_LINES:
        line_key = f"over_{line_val}"
        gov_line = v2_lines.get(line_key, {})
        p_under = gov_line.get("probability_under")

        if p_under is None:
            # Derive from Over probability
            p_over = gov_line.get("probability")
            if p_over is not None:
                p_under = 1.0 - p_over
            else:
                continue

        threshold_label = f"Under {line_val}"
        calibrated = _calibrate_and_deflate(p_under, f"Escanteios {threshold_label}", league_id, regime)

        # Under odds: try v2 book_odd_under, then explicit key, else derive from Over
        under_odd = gov_line.get("book_odd_under")
        line_tag = str(line_val).replace(".", "")
        if under_odd is None:
            under_odd = odds.get(f"cornersUnder{line_tag}")
        if under_odd:
            under_odd = float(under_odd) if float(under_odd) > 1.0 else None
        else:
            over_odd_key = _FOOTYSTATS_ODD_MAP.get(line_val)
            over_odd = odds.get(over_odd_key) if over_odd_key else None
            if over_odd and float(over_odd) > 1.0:
                # Derive from Over: implied_under = OVERROUND - implied_over
                OVERROUND = 1.06
                implied_over = 1.0 / float(over_odd)
                implied_under = OVERROUND - implied_over
                under_odd = round(1.0 / implied_under, 2) if implied_under > 0.01 else None
            else:
                under_odd = None

        mo = MarketOutput(
            market_type="Corners",
            selection=f"Corners {threshold_label}",
            raw_probability=p_under,
            calibrated_probability=calibrated,
            book_odd=under_odd,
            odds_available=under_odd is not None,
            data_quality_score=quality,
            source_flags=[*source_flags, f"corner_model:{gov_line.get('model_used', 'corners_engine_v2')}", "under"],
            display_label=f"Escanteios {threshold_label}",
        )

        classified = classify_market(mo, league_id=league_id, projection=_corners_projection)
        classified.corner_governance = {
            "marketFamily": "corners",
            "engineVersion": v2_engine_version,
            "cornerModelStatus": gov_line.get("operational_state", "NEUTRAL"),
            "side": "UNDER",
            "projectedTotalCornersFT": v2_projection.get("expected_total_corners_ft"),
            "projectedTotalCorners1H": v2_projection.get("expected_total_corners_1h"),
            "projectedTotalCorners2H": v2_projection.get("expected_total_corners_2h"),
            "cornerValidationVersion": corner_governance.get("cornerValidationVersion", v2_engine_version),
        }
        markets.append(classified)

    # ── Cards Markets (#085, #085b) — NB2 + covariates Over/Under 2.5-5.5 ──
    try:
        from backend.modeling.cards_engine import predict_cards, CARD_LINES

        cards_result = predict_cards(
            home_stats=stats,
            away_stats=stats,
            league_id=league_id,
            league_stats=league_stats if isinstance(league_stats, dict) else None,
        )

        # Adaptive data_quality_score based on model source (#085b)
        if cards_result.get("model_source") == "nb2":
            _cards_quality = quality * 0.75  # NB2 present: better than Poisson
        else:
            _cards_quality = quality * 0.65  # Poisson fallback: conservative

        _cards_projection = cards_result.get("cards_lambda")  # #126
        _cards_flags = [*source_flags, f"cards_{cards_result.get('model_source', 'unknown')}"]
        if cards_result.get("adjustments", {}).get("referee_factor", 1.0) != 1.0:
            _cards_flags.append("referee_adjusted")

        for line in CARD_LINES:
            over_prob = cards_result["lines"].get(f"over_{line}", {}).get("prob", 0)
            under_prob = cards_result["lines"].get(f"under_{line}", {}).get("prob", 0)

            # Over cards
            if over_prob > 0.10:
                calibrated_over = _calibrate_and_deflate(over_prob, f"Cartoes Over {line}", league_id, regime)
                over_odd = odds.get(f"cards_over_{line}") or odds.get(f"over{str(line).replace('.', '')}Cards")
                over_odd = float(over_odd) if over_odd and float(over_odd) > 1.0 else None
                # Cards Over <=2.5: skip low odds (easy line, no value) (#113)
                if line <= 2.5 and over_odd and over_odd < 1.50:
                    over_odd = None  # force NO_BET by removing odd

                mo = MarketOutput(
                    market_type="Cards",
                    selection=f"Over {line}",
                    raw_probability=over_prob,
                    calibrated_probability=calibrated_over,
                    book_odd=over_odd,
                    odds_available=over_odd is not None,
                    data_quality_score=_cards_quality,
                    source_flags=_cards_flags,
                    display_label=f"Cartoes Over {line}",
                )
                markets.append(classify_market(mo, league_id=league_id, projection=_cards_projection))

            # Under cards
            if under_prob > 0.10:
                calibrated_under = _calibrate_and_deflate(under_prob, f"Cartoes Under {line}", league_id, regime)
                under_odd = odds.get(f"cards_under_{line}") or odds.get(f"under{str(line).replace('.', '')}Cards")
                under_odd = float(under_odd) if under_odd and float(under_odd) > 1.0 else None

                mo = MarketOutput(
                    market_type="Cards",
                    selection=f"Under {line}",
                    raw_probability=under_prob,
                    calibrated_probability=calibrated_under,
                    book_odd=under_odd,
                    odds_available=under_odd is not None,
                    data_quality_score=_cards_quality,
                    source_flags=_cards_flags,
                    display_label=f"Cartoes Under {line}",
                )
                markets.append(classify_market(mo, league_id=league_id, projection=_cards_projection))

    except Exception as e:
        logger.debug(f"[cards] Card market evaluation failed: {e}")

    # ─── Apply early season penalty ───
    if early_season:
        for m in markets:
            if ReasonCode.EARLY_SEASON_FALLBACK not in m.reason_codes:
                m.reason_codes.append(ReasonCode.EARLY_SEASON_FALLBACK)
            # Downgrade SAFE to NEUTRO in early season
            if m.classification == MarketClassification.SAFE:
                m.classification = MarketClassification.NEUTRO_QUALIFICADO

    # ─── Apply chaos detector gate — chaotic matches cannot be SAFE ───
    chaos_detected = stats.get("chaosDetected", False)
    if chaos_detected:
        for m in markets:
            if m.classification == MarketClassification.SAFE:
                m.classification = MarketClassification.NEUTRO
                if ReasonCode.HIGH_PREDICTION_RISK not in m.reason_codes:
                    m.reason_codes.append(ReasonCode.HIGH_PREDICTION_RISK)
        logger.info("[Chaos] Capped all SAFE → NEUTRO for chaotic match")

    # ─── Filter NO_BET markets that have zero probability ───
    active_markets = [m for m in markets if (m.calibrated_probability or m.raw_probability or 0) > 0.05]

    # ─── Filter redundant 1X2 ↔ Double Chance ───
    active_markets = _filter_1x2_dc_redundancy(active_markets)

    # ─── Filter corridor bets (Over X.5 + Under (X+1).5) ───
    active_markets = _filter_corridor_bets(active_markets)

    # ─── Line safety margin (#120) — downgrade borderline Over lines ───
    _apply_line_safety_margin(active_markets)

    # ─── Corner direction filter (#123) — downgrade picks against projFT direction ───
    proj_ft = v2_projection.get("expected_total_corners_ft") if v2_projection else None
    if proj_ft and proj_ft > 0:
        _apply_corner_direction_filter(active_markets, proj_ft)

    # ─── Collect rejected insights (#152) ───
    # Notable markets classified NO_BET with raw_prob ≥ 55% — explain why
    _rejected_insights = []
    for m in markets:
        if m.classification != MarketClassification.NO_BET:
            continue
        raw_p = m.raw_probability or 0
        if raw_p < 0.55:
            continue
        cal_p = m.calibrated_probability or 0
        ev_val = m.ev
        reason = "EV negativo após deflação" if (ev_val is not None and ev_val < 0) else "prob insuficiente"
        if not m.odds_available:
            reason = "sem odds disponíveis"
        _rejected_insights.append({
            "market": m.display_label or m.selection,
            "raw_prob": round(raw_p * 100, 1),
            "deflated_prob": round(cal_p * 100, 1),
            "ev": round(ev_val * 100, 1) if ev_val is not None else None,
            "reason": reason,
            "reason_codes": [rc.value for rc in m.reason_codes],
        })

    # ─── Build bundle ───
    bundle = MatchMarketBundle(
        match_id=match_id,
        home_team=str(home_team),
        away_team=str(away_team),
        league_id=league_id,
        data_quality_score=quality,
        markets=active_markets,
        rejected_insights=_rejected_insights,
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
    if market_type in ("Cards",):
        return "Cards"
    return "1X2"  # fallback


def _filter_1x2_dc_redundancy(markets: List[MarketOutput]) -> List[MarketOutput]:
    """Remove redundant 1X2/DC pairs — keep only the more appropriate one.

    Rules:
    - 1X2 Home + DC 1X → keep 1X2 Home if prob >= 50%, else keep DC 1X
    - 1X2 Away + DC X2 → keep 1X2 Away if prob >= 50%, else keep DC X2
    """
    remove_set = set()

    # Check Home + DC 1X
    home_markets = [m for m in markets if m.selection == "Home" and m.market_type == "1X2"]
    dc1x_markets = [m for m in markets if m.selection == "DC 1X" and m.market_type == "Double Chance"]

    if home_markets and dc1x_markets:
        home_m = home_markets[0]
        dc1x_m = dc1x_markets[0]
        home_prob = home_m.calibrated_probability or home_m.raw_probability or 0
        if home_prob >= 0.50:
            remove_set.add(id(dc1x_m))
            logger.debug(f"[Redundancy] Removed DC 1X (Home prob={home_prob:.1%} >= 50%)")
        else:
            remove_set.add(id(home_m))
            logger.debug(f"[Redundancy] Removed 1X2 Home (prob={home_prob:.1%} < 50%), keeping DC 1X")

    # Check Away + DC X2
    away_markets = [m for m in markets if m.selection == "Away" and m.market_type == "1X2"]
    dcx2_markets = [m for m in markets if m.selection == "DC X2" and m.market_type == "Double Chance"]

    if away_markets and dcx2_markets:
        away_m = away_markets[0]
        dcx2_m = dcx2_markets[0]
        away_prob = away_m.calibrated_probability or away_m.raw_probability or 0
        if away_prob >= 0.50:
            remove_set.add(id(dcx2_m))
            logger.debug(f"[Redundancy] Removed DC X2 (Away prob={away_prob:.1%} >= 50%)")
        else:
            remove_set.add(id(away_m))
            logger.debug(f"[Redundancy] Removed 1X2 Away (prob={away_prob:.1%} < 50%), keeping DC X2")

    return [m for m in markets if id(m) not in remove_set]


def _filter_corridor_bets(markets: List[MarketOutput]) -> List[MarketOutput]:
    """When Over X.5 and Under (X+1).5 both appear, keep only the higher probability one.

    Corridors detected:
    - Over 1.5 + Under 2.5 → corridor of exactly 2 goals
    - Over 2.5 + Under 3.5 → corridor of exactly 3 goals
    - Over 3.5 + Under 4.5 → corridor of exactly 4 goals
    """
    # Corridor pairs for goals, corners, and cards (#113 expanded from #037)
    CORRIDOR_PAIRS = []
    # Goals
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        CORRIDOR_PAIRS.append(("Over/Under", f"Over {line}", f"Under {line + 1.0}"))
    # Corners
    for line in [4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]:
        CORRIDOR_PAIRS.append(("Corners", f"Corners Over {line}", f"Corners Under {line + 1.0}"))
    # Cards
    for line in [1.5, 2.5, 3.5, 4.5, 5.5]:
        CORRIDOR_PAIRS.append(("Cards", f"Over {line}", f"Under {line + 1.0}"))

    remove_set = set()

    for mtype, over_sel, under_sel in CORRIDOR_PAIRS:
        over_markets = [m for m in markets if m.selection == over_sel and (m.market_type == mtype or mtype in (m.market_type or ""))]
        under_markets = [m for m in markets if m.selection == under_sel and (m.market_type == mtype or mtype in (m.market_type or ""))]

        if over_markets and under_markets:
            over_m = over_markets[0]
            under_m = under_markets[0]
            over_prob = over_m.calibrated_probability or over_m.raw_probability or 0
            under_prob = under_m.calibrated_probability or under_m.raw_probability or 0

            if over_prob >= under_prob:
                remove_set.add(id(under_m))
                logger.debug(
                    f"[Corridor] {over_sel} ({over_prob:.1%}) + {under_sel} ({under_prob:.1%}) "
                    f"-> kept {over_sel} (higher prob)"
                )
            else:
                remove_set.add(id(over_m))
                logger.debug(
                    f"[Corridor] {over_sel} ({over_prob:.1%}) + {under_sel} ({under_prob:.1%}) "
                    f"-> kept {under_sel} (higher prob)"
                )

    return [m for m in markets if id(m) not in remove_set]


# ── Line safety margin (#120) ─────────────────────────────────────
LINE_SAFETY_MARGIN = 0.05  # 5% — corners, goals, and cards (#152)


def _apply_line_safety_margin(markets: List[MarketOutput]) -> List[MarketOutput]:
    """Downgrade borderline Over lines to NEUTRO (#120).

    When a high Over line has probability barely above the NEUTRO threshold,
    downgrade it if a lower line also qualifies. Prevents consistently
    selecting 1 line above the correct one.

    Affects Over lines for Corners, Over/Under (goals), and Cards (#152).
    """
    import re
    _line_re = re.compile(r"(\d+\.?\d*)")

    families: Dict[str, List[MarketOutput]] = {}
    for m in markets:
        if "over" not in (m.selection or "").lower():
            continue
        if m.market_type == "Corners":
            families.setdefault("Corners", []).append(m)
        elif m.market_type == "Over/Under":
            families.setdefault("Goals", []).append(m)
        elif m.market_type == "Cards":
            families.setdefault("Cards", []).append(m)

    for family, over_list in families.items():
        if len(over_list) <= 1:
            continue

        def _line_val(mo: MarketOutput) -> float:
            match = _line_re.search(mo.selection or "")
            return float(match.group(1)) if match else 0

        over_list.sort(key=_line_val)

        cat = {"Corners": "Corners", "Goals": "Over/Under", "Cards": "Cards"}.get(family, "Over/Under")
        th = _get_thresholds(cat)
        neutro_prob = th.get("neutro_prob", 0.50)

        for i, mo in enumerate(over_list):
            if mo.classification not in (MarketClassification.SAFE, MarketClassification.NEUTRO_QUALIFICADO):
                continue
            prob = mo.calibrated_probability or mo.raw_probability or 0
            if prob <= 0:
                continue
            gap = prob - neutro_prob
            if gap >= LINE_SAFETY_MARGIN:
                continue
            lower_exists = any(
                (prev.calibrated_probability or prev.raw_probability or 0) > neutro_prob
                for prev in over_list[:i]
            )
            if not lower_exists:
                continue
            old_cls = mo.classification
            mo.classification = MarketClassification.NEUTRO
            mo.reason_codes.append(ReasonCode.BORDERLINE_LINE_MARGIN)
            logger.info(
                f"[line-margin] {mo.display_label}: {old_cls.value}->NEUTRO "
                f"(prob {prob:.3f}, gap {gap:.3f} < margin {LINE_SAFETY_MARGIN})"
            )


# ── Direction neutral zones (#127) ──────────────────────────────────
def _get_direction_neutral_zone(market_type: str) -> float:
    """Proportional neutral zone by market scale (#127).

    Goals: avg ~2.5/game → zone 0.3 (~12%)
    Corners: avg ~10/game → zone 0.5 (~5%)
    Cards: avg ~4/game → zone 0.3 (~7.5%)
    """
    if market_type == "Corners":
        return 0.5
    return 0.3  # Goals (Over/Under) and Cards


# ── Corner direction filter (#123) ─────────────────────────────────
CORNER_DIRECTION_NEUTRAL_ZONE = 0.5  # |projFT - line| < 0.5 → both sides OK


def _apply_corner_direction_filter(markets: List[MarketOutput], proj_ft: float) -> None:
    """Downgrade corner picks that go against the projFT direction (#123).

    If projFT > line + 0.5, the natural direction is Over → Under is downgraded.
    If projFT < line - 0.5, the natural direction is Under → Over is downgraded.
    Within the neutral zone (|diff| < 0.5), both sides are allowed.
    """
    import re
    _line_re = re.compile(r"(\d+\.?\d*)")

    for m in markets:
        if m.market_type != "Corners":
            continue
        sel = (m.selection or "").lower()
        is_over = "over" in sel
        is_under = "under" in sel
        if not is_over and not is_under:
            continue

        match = _line_re.search(m.selection or "")
        if not match:
            continue
        line = float(match.group(1))

        diff = proj_ft - line  # positive = projFT above line

        if is_under and diff > CORNER_DIRECTION_NEUTRAL_ZONE:
            # projFT ABOVE line → Under goes against direction
            old_cls = m.classification
            if old_cls in (MarketClassification.SAFE, MarketClassification.NEUTRO_QUALIFICADO):
                m.classification = MarketClassification.NEUTRO
                m.reason_codes.append(ReasonCode.DIRECTION_AGAINST_PROJFT)
                logger.info(
                    f"[corner-direction] {m.display_label}: {old_cls.value}->NEUTRO "
                    f"(projFT={proj_ft:.1f} > line {line}, diff={diff:+.1f})"
                )

        elif is_over and diff < -CORNER_DIRECTION_NEUTRAL_ZONE:
            # projFT BELOW line → Over goes against direction
            old_cls = m.classification
            if old_cls in (MarketClassification.SAFE, MarketClassification.NEUTRO_QUALIFICADO):
                m.classification = MarketClassification.NEUTRO
                m.reason_codes.append(ReasonCode.DIRECTION_AGAINST_PROJFT)
                logger.info(
                    f"[corner-direction] {m.display_label}: {old_cls.value}->NEUTRO "
                    f"(projFT={proj_ft:.1f} < line {line}, diff={diff:+.1f})"
                )
