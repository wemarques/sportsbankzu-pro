"""
Corners Engine v2 — Layer A: Data Quality & Coverage Assessment

Evaluates the quality and completeness of corner-related data for a match,
producing a structured quality report that feeds into shrinkage and governance.

Quality Tiers:
  HIGH         — Robust corner, timing, pressure, and xG data
  MEDIUM       — Functional coverage, some gaps
  LOW          — Limited data, no timing or unreliable pressure
  INSUFFICIENT — Cannot produce reliable corner projections
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("sportsbankzu.corners.data_quality")

# Minimum thresholds
MIN_CORNER_SAMPLE = 5        # minimum matches with corners recorded
MIN_CORNER_SAMPLE_GOOD = 15  # sample considered adequate
MIN_TIMING_SAMPLE = 5        # matches with FH/2H timing
PREDICTION_RISK_HIGH = 75    # league prediction_risk above this is risky


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "" or val == -1 or val == -2:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def compute_corners_data_quality(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute data quality assessment for corner prediction.

    Returns:
        Dict with coverage_score, feature_completeness_score,
        sample_adequacy_score, corner_timing_available,
        data_quality_tier, and component details.
    """
    components: Dict[str, float] = {}
    details: Dict[str, Any] = {}
    ls = league_stats or {}

    # ── 1. Corner coverage per team ──
    # #225-b: `d.get(k, alternativa)` so usa a alternativa quando a chave esta
    # AUSENTE. Quando ela existe valendo None — que e o caso aqui, porque
    # fixtures_service.py:1950 SEMPRE cria `corners_recorded_matches_num`,
    # preenchida ou nao — o get devolve None e a cadeia inteira de fallback
    # morre. `_safe_float(None)` da 0.0, entao `min_sample` vai a zero,
    # `sample_adequacy` vai a zero e o tier despenca para INSUFFICIENT mesmo com
    # a temporada inteira jogada. Verificado: com a chave presente e nula, o
    # fallback de 24 jogos nunca e alcancado.
    #
    # E o mesmo defeito que o #201 corrigiu no lambda com `_num()`, e a mesma
    # forma do #208 e do #217: ausencia de informacao tratada como informacao de
    # ausencia. `_primeiro_valido` pula None em vez de parar nele.
    def _primeiro_valido(*valores):
        for v in valores:
            if v is not None:
                return v
        return 0

    home_sample = _safe_float(_primeiro_valido(
        home_stats.get("corners_recorded_matches_num"),
        home_stats.get("matchesPlayed_home"),
        home_stats.get("matchesPlayed_overall"),
    ))
    away_sample = _safe_float(_primeiro_valido(
        away_stats.get("corners_recorded_matches_num"),
        away_stats.get("matchesPlayed_away"),
        away_stats.get("matchesPlayed_overall"),
    ))

    home_has_corners = _safe_float(_primeiro_valido(
        home_stats.get("corners_total_per_match"),
        home_stats.get("cornersAVG_home"),
        home_stats.get("homeCornersPerMatch"),
    )) > 0
    away_has_corners = _safe_float(_primeiro_valido(
        away_stats.get("corners_total_per_match"),
        away_stats.get("cornersAVG_away"),
        away_stats.get("awayCornersPerMatch"),
    )) > 0

    min_sample = min(home_sample, away_sample)
    details["home_corner_sample"] = home_sample
    details["away_corner_sample"] = away_sample

    if min_sample >= MIN_CORNER_SAMPLE_GOOD and home_has_corners and away_has_corners:
        components["coverage"] = 1.0
    elif min_sample >= MIN_CORNER_SAMPLE and home_has_corners and away_has_corners:
        components["coverage"] = 0.7
    elif min_sample >= 3 and (home_has_corners or away_has_corners):
        components["coverage"] = 0.4
    else:
        components["coverage"] = 0.1

    # ── 2. Corner timing (FH / 2H) availability ──
    home_timing_sample = _safe_float(home_stats.get(
        "cornerTimingRecorded_matches",
        home_stats.get("corners_total_fh", -1)  # proxy: if FH exists, timing recorded
    ))
    away_timing_sample = _safe_float(away_stats.get(
        "cornerTimingRecorded_matches",
        away_stats.get("corners_total_fh", -1)
    ))

    home_fh = _safe_float(home_stats.get("corners_total_per_match_fh",
                  home_stats.get("corners_total_fh", 0)))
    away_fh = _safe_float(away_stats.get("corners_total_per_match_fh",
                  away_stats.get("corners_total_fh", 0)))
    home_2h = _safe_float(home_stats.get("corners_total_per_match_2h",
                  home_stats.get("corners_total_2h_overall", 0)))
    away_2h = _safe_float(away_stats.get("corners_total_per_match_2h",
                  away_stats.get("corners_total_2h_overall", 0)))

    timing_available = (home_fh > 0 or away_fh > 0) and (home_2h > 0 or away_2h > 0)
    details["corner_timing_available"] = timing_available
    details["home_fh_corners"] = home_fh
    details["away_fh_corners"] = away_fh

    if timing_available and min(home_timing_sample, away_timing_sample) >= MIN_TIMING_SAMPLE:
        components["timing"] = 1.0
    elif timing_available:
        components["timing"] = 0.6
    else:
        components["timing"] = 0.0

    # ── 3. Pressure features (shots, possession, xG) ──
    has_shots = (
        _safe_float(home_stats.get("shots_per_match",
                    home_stats.get("shotsAVG_home", 0))) > 0
        and _safe_float(away_stats.get("shots_per_match",
                        away_stats.get("shotsAVG_away", 0))) > 0
    )
    has_possession = (
        _safe_float(home_stats.get("average_possession",
                    home_stats.get("possessionAVG_home", 0))) > 0
        and _safe_float(away_stats.get("average_possession",
                        away_stats.get("possessionAVG_away", 0))) > 0
    )
    has_xg = (
        _safe_float(home_stats.get("xg_for_avg",
                    home_stats.get("xgAVG_home", 0))) > 0
        and _safe_float(away_stats.get("xg_for_avg",
                        away_stats.get("xgAVG_away", 0))) > 0
    )

    pressure_count = sum([has_shots, has_possession, has_xg])
    details["has_shots"] = has_shots
    details["has_possession"] = has_possession
    details["has_xg"] = has_xg

    if pressure_count >= 3:
        components["pressure"] = 1.0
    elif pressure_count >= 2:
        components["pressure"] = 0.7
    elif pressure_count >= 1:
        components["pressure"] = 0.4
    else:
        components["pressure"] = 0.0

    # ── 4. League prediction risk ──
    league_risk = _safe_float(ls.get("prediction_risk", 50))
    details["league_prediction_risk"] = league_risk

    if league_risk <= 40:
        components["league_risk"] = 1.0
    elif league_risk <= 60:
        components["league_risk"] = 0.7
    elif league_risk <= PREDICTION_RISK_HIGH:
        components["league_risk"] = 0.4
    else:
        components["league_risk"] = 0.1

    # ── 5. Corners-against data ──
    home_against = _safe_float(home_stats.get("corners_against_per_match",
                      home_stats.get("cornersAgainstAVG_home",
                      home_stats.get("homeCornersAgainstPerMatch", 0))))
    away_against = _safe_float(away_stats.get("corners_against_per_match",
                      away_stats.get("cornersAgainstAVG_away",
                      away_stats.get("awayCornersAgainstPerMatch", 0))))
    has_against = home_against > 0 and away_against > 0
    details["has_corners_against"] = has_against
    components["against_data"] = 1.0 if has_against else 0.3

    # ── Aggregate scores ──
    weights = {
        "coverage": 0.30,
        "timing": 0.15,
        "pressure": 0.20,
        "league_risk": 0.15,
        "against_data": 0.20,
    }
    coverage_score = sum(components[k] * weights[k] for k in weights)
    feature_completeness = sum(1 for v in components.values() if v >= 0.6) / len(components)
    sample_adequacy = min(min_sample / MIN_CORNER_SAMPLE_GOOD, 1.0)

    # Determine tier
    if coverage_score >= 0.75 and sample_adequacy >= 0.8 and feature_completeness >= 0.7:
        tier = "HIGH"
    elif coverage_score >= 0.50 and sample_adequacy >= 0.5:
        tier = "MEDIUM"
    elif coverage_score >= 0.25 and sample_adequacy >= 0.2:
        tier = "LOW"
    else:
        tier = "INSUFFICIENT"

    return {
        "coverage_score": round(coverage_score, 4),
        "feature_completeness_score": round(feature_completeness, 4),
        "sample_adequacy_score": round(sample_adequacy, 4),
        "corner_timing_available": timing_available,
        "data_quality_tier": tier,
        "components": {k: round(v, 4) for k, v in components.items()},
        "details": details,
    }
