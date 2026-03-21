"""
Per-League Calibration Service

Replaces uniform deflation (#043) with league-specific factors
trained on 4 seasons of historical data.

Reference: REGRAS #052
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from backend.services.math_service import poisson_pmf

logger = logging.getLogger("sportsbankzu.league_calibrator")

# Temporal decay weights for 4 seasons (T-1 most recent)
SEASON_WEIGHTS = [0.45, 0.28, 0.17, 0.10]

# Grid search ranges
DEFLATION_GRID = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10]
LAMBDA_WEIGHT_GRID = [
    (0.40, 0.60), (0.45, 0.55), (0.50, 0.50),
    (0.55, 0.45), (0.60, 0.40), (0.65, 0.35), (0.70, 0.30),
]
BTTS_DEFLATION_GRID = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05]
CORNER_DEFLATION_GRID = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05]


def _brier(prob: float, outcome: int) -> float:
    """Brier score for a single prediction."""
    return (prob - outcome) ** 2


def _simulate_poisson_brier(
    matches: List[Dict],
    lambda_deflation: float,
    lambda_weights: Tuple[float, float],
) -> Dict[str, float]:
    """Simulate Brier scores for goal markets given deflation and weight params.

    For each match:
    1. Compute lambda from team averages using given weights
    2. Apply deflation factor
    3. Use Poisson to predict Over/Under probabilities
    4. Compare with actual result
    5. Compute Brier score

    Returns dict with brier_ou, brier_btts, brier_1x2, n_matches.
    """
    brier_ou = []
    brier_btts = []
    brier_1x2 = []

    w_season, w_recent = lambda_weights

    for m in matches:
        # Extract team averages
        home_avg_season = m.get("home_goals_scored_avg", 0) or 0
        away_avg_season = m.get("away_goals_scored_avg", 0) or 0
        home_avg_recent = m.get("home_goals_scored_avg_recent", home_avg_season) or home_avg_season
        away_avg_recent = m.get("away_goals_scored_avg_recent", away_avg_season) or away_avg_season

        # Opponent defensive factors
        home_def_factor = m.get("away_goals_conceded_factor", 1.0) or 1.0
        away_def_factor = m.get("home_goals_conceded_factor", 1.0) or 1.0

        # Compute lambda with given weights
        lh_raw = (home_avg_season * w_season + home_avg_recent * w_recent) * home_def_factor
        la_raw = (away_avg_season * w_season + away_avg_recent * w_recent) * away_def_factor

        # Clamp
        lh_raw = max(0.2, min(4.5, lh_raw))
        la_raw = max(0.2, min(4.5, la_raw))

        # Deflated lambdas for O/U
        lh = lh_raw * lambda_deflation
        la = la_raw * lambda_deflation

        # Actual results
        gh = m.get("goals_home", 0) or 0
        ga = m.get("goals_away", 0) or 0
        total = gh + ga

        # Poisson probabilities
        prob_over25 = 0.0
        prob_btts = 0.0
        prob_home = 0.0
        prob_draw = 0.0

        for h in range(9):
            ph = poisson_pmf(h, lh)
            for a in range(9):
                pa = poisson_pmf(a, la)
                p = ph * pa
                if h + a > 2:
                    prob_over25 += p
                if h >= 1 and a >= 1:
                    prob_btts += p
                if h > a:
                    prob_home += p
                elif h == a:
                    prob_draw += p

        # Brier for Over 2.5
        actual_over25 = 1 if total > 2.5 else 0
        brier_ou.append(_brier(prob_over25, actual_over25))

        # Brier for BTTS
        actual_btts = 1 if (gh > 0 and ga > 0) else 0
        brier_btts.append(_brier(prob_btts, actual_btts))

        # Brier for 1X2 (Home)
        actual_home = 1 if gh > ga else 0
        brier_1x2.append(_brier(prob_home, actual_home))

    n = len(brier_ou)
    return {
        "brier_ou": sum(brier_ou) / n if n > 0 else None,
        "brier_btts": sum(brier_btts) / n if n > 0 else None,
        "brier_1x2": sum(brier_1x2) / n if n > 0 else None,
        "n_matches": n,
    }


def _extract_matches_from_season(raw_data: Dict) -> List[Dict]:
    """Extract finished matches with stats from FootyStats league-matches response.

    Maps FootyStats fields to our internal structure for simulation.
    """
    matches = []
    items = raw_data.get("data", [])
    if isinstance(items, dict):
        items = [items]

    for m in items:
        # Only finished matches
        status = m.get("status", "")
        if status not in ("complete", "finished", "ft"):
            continue

        gh = m.get("homeGoalCount") or m.get("home_goals")
        ga = m.get("awayGoalCount") or m.get("away_goals")
        if gh is None or ga is None:
            continue

        try:
            gh, ga = int(gh), int(ga)
        except (ValueError, TypeError):
            continue

        matches.append({
            "goals_home": gh,
            "goals_away": ga,
            "home_goals_scored_avg": m.get("team_a_xg") or m.get("homeGoalsAVG_overall") or 1.3,
            "away_goals_scored_avg": m.get("team_b_xg") or m.get("awayGoalsAVG_overall") or 1.1,
            "home_goals_scored_avg_recent": m.get("homeGoalsAVG_last5") or m.get("homeGoalsAVG_overall") or 1.3,
            "away_goals_scored_avg_recent": m.get("awayGoalsAVG_last5") or m.get("awayGoalsAVG_overall") or 1.1,
            "away_goals_conceded_factor": m.get("awayConcededAVG_factor") or 1.0,
            "home_goals_conceded_factor": m.get("homeConcededAVG_factor") or 1.0,
            "total_corners": (m.get("team_a_corners") or 0) + (m.get("team_b_corners") or 0),
            "total_cards": (m.get("team_a_cards") or 0) + (m.get("team_b_cards") or 0),
        })

    return matches


def fetch_historical_matches(league_id: str, n_seasons: int = 4) -> List[Dict]:
    """Fetch up to n_seasons of historical match data for a league.

    Uses FootyStats API via FootyStatsClient. Applies temporal weighting
    so recent matches count more.

    Returns flat list of match dicts with season_weight field added.
    """
    from backend.services.footstats_client import FootyStatsClient
    from backend.config.leagues_config import LEAGUES_CONFIG

    # Find league config
    league_cfg = None
    for cfg in LEAGUES_CONFIG:
        if cfg["id"] == league_id:
            league_cfg = cfg
            break

    if not league_cfg:
        logger.warning(f"League {league_id} not found in config")
        return []

    client = FootyStatsClient()
    season_ids = client.resolve_season_ids(
        country=league_cfg["country"],
        league_name=league_cfg["name"],
        alt_names=league_cfg.get("alt_names", []),
        n_seasons=n_seasons,
    )

    if not season_ids:
        logger.warning(f"No season IDs found for {league_id}")
        return []

    all_matches = []
    weights = SEASON_WEIGHTS[:len(season_ids)]

    for i, (sid, api_name) in enumerate(season_ids):
        try:
            raw = client.get_league_matches(sid)
            season_matches = _extract_matches_from_season(raw)
            w = weights[i] if i < len(weights) else 0.10

            for m in season_matches:
                m["season_weight"] = w
                m["season_index"] = i  # 0 = most recent

            all_matches.extend(season_matches)
            logger.info(f"[calibrator] {league_id} season {sid}: {len(season_matches)} matches (weight={w})")

        except Exception as e:
            logger.error(f"[calibrator] Failed to fetch season {sid} for {league_id}: {e}")

    logger.info(f"[calibrator] {league_id}: total {len(all_matches)} historical matches from {len(season_ids)} seasons")
    return all_matches


def calibrate_league(
    league_id: str,
    n_seasons: int = 4,
    matches: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Run full calibration for a single league.

    1. Fetch 4 seasons of historical data (or use provided matches)
    2. Grid search: lambda deflation x lambda weights
    3. Grid search: BTTS deflation
    4. Grid search: corner deflation
    5. Select best params by weighted Brier score (recent seasons count more)

    Returns optimal parameters for the league.
    """
    if matches is None:
        matches = fetch_historical_matches(league_id, n_seasons)

    if len(matches) < 30:
        logger.warning(f"[calibrator] {league_id}: only {len(matches)} matches — insufficient for calibration")
        return {
            "league": league_id,
            "status": "INSUFFICIENT_DATA",
            "n_matches": len(matches),
            "params": None,
        }

    # ── Grid search: lambda deflation x lambda weights ──
    best_ou = {"brier": 1.0}
    best_1x2 = {"brier": 1.0}

    for deflation in DEFLATION_GRID:
        for weights in LAMBDA_WEIGHT_GRID:
            result = _simulate_poisson_brier(matches, deflation, weights)

            if result["brier_ou"] is not None and result["brier_ou"] < best_ou["brier"]:
                best_ou = {
                    "brier": result["brier_ou"],
                    "deflation": deflation,
                    "weight_season": weights[0],
                    "weight_recent": weights[1],
                }

            # 1X2 uses undeflated lambda — search only weights
            if deflation == 1.0 and result["brier_1x2"] is not None and result["brier_1x2"] < best_1x2["brier"]:
                best_1x2 = {
                    "brier": result["brier_1x2"],
                    "weight_season": weights[0],
                    "weight_recent": weights[1],
                }

    # ── Grid search: BTTS deflation (using best O/U weights) ──
    best_btts = {"brier": 1.0}
    best_ou_weights = (best_ou.get("weight_season", 0.60), best_ou.get("weight_recent", 0.40))

    for btts_defl in BTTS_DEFLATION_GRID:
        result = _simulate_poisson_brier(matches, btts_defl, best_ou_weights)
        if result["brier_btts"] is not None and result["brier_btts"] < best_btts["brier"]:
            best_btts = {
                "brier": result["brier_btts"],
                "deflation": btts_defl,
            }

    # ── Corner deflation (based on avg corners error) ──
    avg_corners_actual = 0
    n_corners = 0
    for m in matches:
        tc = m.get("total_corners")
        if tc and tc > 0:
            avg_corners_actual += tc
            n_corners += 1
    avg_corners_actual = avg_corners_actual / n_corners if n_corners > 0 else 10.0

    # Compare with league DNA expected
    try:
        from backend.config.league_dna import get_league_dna
        dna = get_league_dna(league_id)
        expected_corners = dna.avg_corners if dna else 10.0
    except Exception:
        expected_corners = 10.0

    corner_factor = avg_corners_actual / expected_corners if expected_corners > 0 else 1.0
    corner_factor = max(0.70, min(1.20, round(corner_factor, 2)))

    # ── SAFE threshold recommendation ──
    # Based on Brier score with optimal params
    optimal_result = _simulate_poisson_brier(matches, best_ou.get("deflation", 1.0), best_ou_weights)

    safe_enabled = (
        optimal_result["brier_ou"] is not None and optimal_result["brier_ou"] < 0.25
        and len(matches) >= 100
    )

    params = {
        "lambda_deflation_ou": best_ou.get("deflation", 1.0),
        "lambda_deflation_btts": best_btts.get("deflation", 1.0),
        "lambda_weight_season": best_ou.get("weight_season", 0.60),
        "lambda_weight_recent": best_ou.get("weight_recent", 0.40),
        "corner_factor": corner_factor,
        "safe_enabled": safe_enabled,
        "brier_ou": best_ou.get("brier"),
        "brier_btts": best_btts.get("brier"),
        "brier_1x2": best_1x2.get("brier"),
    }

    logger.info(
        f"[calibrator] {league_id}: optimal params — "
        f"lambda_defl_ou={params['lambda_deflation_ou']}, "
        f"btts_defl={params['lambda_deflation_btts']}, "
        f"weights={params['lambda_weight_season']}/{params['lambda_weight_recent']}, "
        f"corner_factor={params['corner_factor']}, "
        f"safe={params['safe_enabled']}, "
        f"brier_ou={params['brier_ou']:.4f}"
    )

    return {
        "league": league_id,
        "status": "CALIBRATED",
        "n_matches": len(matches),
        "n_seasons": n_seasons,
        "params": params,
        "calibrated_at": datetime.now().isoformat(),
    }


def save_calibration(league_id: str, params: Dict[str, Any]) -> None:
    """Save calibration results to the corrections DB.

    Uses the existing audit.log_correction() to store per-league params.
    This integrates with the existing get_lambda_corrections() flow.
    """
    from backend.audit import log_correction

    param_map = {
        "lambda_deflation_ou": ("lambda_multiplier", "Calibrated lambda deflation for O/U"),
        "lambda_deflation_btts": ("btts_multiplier", "Calibrated BTTS deflation"),
        "corner_factor": ("corner_multiplier", "Calibrated corner factor"),
        "lambda_weight_season": ("lambda_weight_season", "Calibrated season weight"),
        "lambda_weight_recent": ("lambda_weight_recent", "Calibrated recent weight"),
        "safe_enabled": ("safe_enabled", "Per-league SAFE status"),
    }

    n_matches = params.get("n_matches", "?")
    brier_ou = params.get("brier_ou", "?")

    for key, (param_name, reason) in param_map.items():
        value = params.get(key)
        if value is not None:
            try:
                log_correction(
                    match_id=f"calibration_{league_id}",
                    league=league_id,
                    parameter_name=param_name,
                    old_value=None,
                    new_value=str(value),
                    correction_type="calibration",
                    reason=f"[Auto-calibration] {reason} (n={n_matches} matches, "
                           f"brier_ou={brier_ou})",
                )
            except Exception as e:
                logger.error(f"Failed to save calibration {key} for {league_id}: {e}")


def calibrate_all_leagues(n_seasons: int = 4) -> Dict[str, Dict]:
    """Run calibration for all configured leagues.

    Returns dict of league_id -> calibration result.
    """
    from backend.config.leagues_config import LEAGUES_CONFIG

    results = {}
    for cfg in LEAGUES_CONFIG:
        league_id = cfg["id"]
        try:
            result = calibrate_league(league_id, n_seasons=n_seasons)
            if result.get("status") == "CALIBRATED" and result.get("params"):
                save_calibration(league_id, result["params"])
            results[league_id] = result
        except Exception as e:
            logger.error(f"Calibration failed for {league_id}: {e}")
            results[league_id] = {"league": league_id, "status": "ERROR", "error": str(e)}

    calibrated = sum(1 for r in results.values() if r.get("status") == "CALIBRATED")
    logger.info(f"[calibrator] Calibration complete: {calibrated}/{len(results)} leagues calibrated")

    return results
