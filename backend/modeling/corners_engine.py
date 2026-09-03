"""
Corners Engine (Layer 2 — Dedicated Corners Motor)

Separate prediction track for corner markets using FootyStats data:
- corners pro/contra
- averages per game
- over corners percentages
- home/away splits
- offensive tempo proxy (shots, possession)
"""

import logging
import math
from typing import Dict, Any, Optional
from backend.utils.valores import primeiro_valido  # #225-c

logger = logging.getLogger("sportsbankzu.corners_engine")

# Poisson PMF for corners (reuse from math_service but inlined for independence)
def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except Exception:
        return 0.0


def estimate_corners_lambda(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
) -> float:
    """Estimate expected total corners for the match.

    Uses weighted combination of:
    - Team corners pro (forced by team)
    - Team corners contra (conceded by opponent)
    - League average as fallback
    """
    # Home team corners (when playing at home)
    # #145: Cap at 12.0 — values above indicate data pollution (match count as average)
    _MAX_CPM = 12.0
    home_corners_for = min(_safe_float(primeiro_valido(home_stats.get("cornersAVG_home"), home_stats.get("homeCornersPerMatch"), home_stats.get("cornersAVG_overall"), padrao=0)), _MAX_CPM)
    # Away team corners (when playing away)
    away_corners_for = min(_safe_float(primeiro_valido(away_stats.get("cornersAVG_away"), away_stats.get("awayCornersPerMatch"), away_stats.get("cornersAVG_overall"), padrao=0)), _MAX_CPM)

    # Corners conceded
    home_corners_against = _safe_float(primeiro_valido(home_stats.get("homeCornersAgainstPerMatch"), home_stats.get("cornersAgainstAVG_home"), padrao=0))
    away_corners_against = _safe_float(primeiro_valido(away_stats.get("awayCornersAgainstPerMatch"), away_stats.get("cornersAgainstAVG_away"), padrao=0))

    # League average
    league_avg = 10.0  # default
    if league_stats:
        league_avg = _safe_float(primeiro_valido(league_stats.get("cornersAVG_overall"), league_stats.get("leagueAvgCorners"), padrao=10.0))

    # #134: Third estimate — cornersTotalAVG (empirical total corners per game)
    home_total_avg = _safe_float(primeiro_valido(home_stats.get("homeCornersTotalAvg"), home_stats.get("corners_total_avg_home"), home_stats.get("cornersTotalAVG_home"), padrao=0))
    away_total_avg = _safe_float(primeiro_valido(away_stats.get("awayCornersTotalAvg"), away_stats.get("corners_total_avg_away"), away_stats.get("cornersTotalAVG_away"), padrao=0))
    total_avg_estimate = None
    if home_total_avg > 0 and away_total_avg > 0:
        total_avg_estimate = (home_total_avg + away_total_avg) / 2

    # Weighted combination of estimates
    if home_corners_for > 0 and away_corners_for > 0:
        direct_estimate = home_corners_for + away_corners_for

        if home_corners_against > 0 and away_corners_against > 0:
            cross_estimate = (home_corners_for + away_corners_against +
                            away_corners_for + home_corners_against) / 2

            if total_avg_estimate is not None:
                # #134: Full scenario — 3 estimates + league
                total_corners = (direct_estimate * 0.35 +
                               cross_estimate * 0.30 +
                               total_avg_estimate * 0.20 +
                               league_avg * 0.15)
            else:
                # Original: 60% direct, 30% cross, 10% league
                total_corners = (direct_estimate * 0.60 +
                               cross_estimate * 0.30 +
                               league_avg * 0.10)
        elif total_avg_estimate is not None:
            # No cross but have total_avg
            total_corners = (direct_estimate * 0.45 +
                           total_avg_estimate * 0.30 +
                           league_avg * 0.25)
        else:
            # Fallback: 75% direct, 25% league
            total_corners = direct_estimate * 0.75 + league_avg * 0.25
    elif league_avg > 0:
        total_corners = league_avg
    else:
        total_corners = 10.0  # absolute fallback

    return max(4.0, min(18.0, total_corners))


def derive_corner_probabilities(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
    footystats_probs: Optional[Dict[str, Any]] = None,
    league_id: Optional[str] = None,
) -> Dict[str, float]:
    """Derive corner market probabilities.

    Uses Poisson model on estimated corners lambda, blended with
    FootyStats pre-match potentials when available.

    Returns probabilities in 0-1 scale.
    """
    total_corners_lambda = estimate_corners_lambda(home_stats, away_stats, league_stats)

    # Apply per-league corner factor from calibration (#058)
    if league_id:
        try:
            from backend.modeling.lambda_calculator import get_lambda_corrections
            _corr = get_lambda_corrections(league_id)
            _corner_mult = float(_corr.get("corner_multiplier", {}).get("value", 1.0))
            total_corners_lambda = total_corners_lambda * _corner_mult
        except Exception:
            pass

    # Poisson-based probabilities
    thresholds = [8.5, 9.5, 10.5, 11.5]
    poisson_probs = {}
    for threshold in thresholds:
        # P(X > threshold) = 1 - P(X <= floor(threshold))
        p_under = sum(_poisson_pmf(k, total_corners_lambda) for k in range(int(threshold) + 1))
        poisson_probs[f"over_{threshold}"] = 1.0 - p_under

    # FootyStats pre-match potentials (if available)
    fs_probs = {}
    if footystats_probs:
        for key, mapped in [
            ("cornerOver85Prob", "over_8.5"),
            ("cornerOver95Prob", "over_9.5"),
            ("cornerOver105Prob", "over_10.5"),
        ]:
            val = footystats_probs.get(key)
            if val is not None:
                v = float(val)
                if v > 1.0:
                    v /= 100.0
                fs_probs[mapped] = v

    # Blend: 40% Poisson + 60% FootyStats (when available), else 100% Poisson
    result = {}
    for threshold in thresholds:
        key = f"over_{threshold}"
        if key in fs_probs and key in poisson_probs:
            result[key] = fs_probs[key] * 0.60 + poisson_probs[key] * 0.40
        elif key in poisson_probs:
            result[key] = poisson_probs[key]
        elif key in fs_probs:
            result[key] = fs_probs[key]

    logger.debug(
        f"Corners engine: λ_total={total_corners_lambda:.1f} | "
        f"O8.5={result.get('over_8.5', 0):.2f} "
        f"O9.5={result.get('over_9.5', 0):.2f} "
        f"O10.5={result.get('over_10.5', 0):.2f}"
    )

    return result


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
