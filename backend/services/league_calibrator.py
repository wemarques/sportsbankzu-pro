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

# Temporal decay weights for 6 seasons (T-1 most recent)
SEASON_WEIGHTS = [0.50, 0.25, 0.13, 0.07, 0.03, 0.02]

# Grid search ranges — expanded after all 28 leagues hit 1.10 ceiling (#053)
DEFLATION_GRID = [
    0.75, 0.80, 0.85, 0.90, 0.92, 0.95, 0.97,
    1.00, 1.03, 1.05, 1.08, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50,
]
LAMBDA_WEIGHT_GRID = [
    (0.40, 0.60), (0.45, 0.55), (0.50, 0.50),
    (0.55, 0.45), (0.60, 0.40), (0.65, 0.35), (0.70, 0.30),
]
BTTS_DEFLATION_GRID = [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]
CORNER_DEFLATION_GRID = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]


def _brier(prob: float, outcome: int) -> float:
    """Brier score for a single prediction."""
    return (prob - outcome) ** 2


def _simulate_poisson_brier(
    matches: List[Dict],
    lambda_deflation_ou: float,
    lambda_weights: Tuple[float, float],
    lambda_deflation_btts: float | None = None,
) -> Dict[str, float]:
    """Simulate Brier scores with SEPARATE deflation for O/U and BTTS.

    Args:
        lambda_deflation_ou: Deflation factor for Over/Under markets
        lambda_weights: (weight_season, weight_recent)
        lambda_deflation_btts: Deflation for BTTS. If None, uses same as O/U.

    Returns dict with brier_ou, brier_btts, brier_1x2, n_matches.
    """
    btts_defl = lambda_deflation_btts if lambda_deflation_btts is not None else lambda_deflation_ou

    brier_ou = []
    brier_btts = []
    brier_1x2 = []

    w_season, w_recent = lambda_weights

    for m in matches:
        home_avg_season = m.get("home_goals_scored_avg", 0) or 0
        away_avg_season = m.get("away_goals_scored_avg", 0) or 0
        home_avg_recent = m.get("home_goals_scored_avg_recent", home_avg_season) or home_avg_season
        away_avg_recent = m.get("away_goals_scored_avg_recent", away_avg_season) or away_avg_season

        home_def_factor = m.get("away_goals_conceded_factor", 1.0) or 1.0
        away_def_factor = m.get("home_goals_conceded_factor", 1.0) or 1.0

        lh_raw = (home_avg_season * w_season + home_avg_recent * w_recent) * home_def_factor
        la_raw = (away_avg_season * w_season + away_avg_recent * w_recent) * away_def_factor

        lh_raw = max(0.2, min(4.5, lh_raw))
        la_raw = max(0.2, min(4.5, la_raw))

        # SEPARATE deflations: O/U uses one, BTTS uses another
        lh_ou = lh_raw * lambda_deflation_ou
        la_ou = la_raw * lambda_deflation_ou
        lh_btts = lh_raw * btts_defl
        la_btts = la_raw * btts_defl

        gh = m.get("goals_home", 0) or 0
        ga = m.get("goals_away", 0) or 0
        total = gh + ga

        # O/U and 1X2 — with O/U deflation
        prob_over25 = 0.0
        prob_home = 0.0
        prob_draw = 0.0
        for h in range(9):
            ph = poisson_pmf(h, lh_ou)
            for a in range(9):
                pa = poisson_pmf(a, la_ou)
                p = ph * pa
                if h + a > 2:
                    prob_over25 += p
                if h > a:
                    prob_home += p
                elif h == a:
                    prob_draw += p

        # BTTS — with BTTS-specific deflation
        prob_btts = 0.0
        for h in range(9):
            ph = poisson_pmf(h, lh_btts)
            for a in range(9):
                pa = poisson_pmf(a, la_btts)
                if h >= 1 and a >= 1:
                    prob_btts += ph * pa

        actual_over25 = 1 if total > 2.5 else 0
        brier_ou.append(_brier(prob_over25, actual_over25))

        actual_btts = 1 if (gh > 0 and ga > 0) else 0
        brier_btts.append(_brier(prob_btts, actual_btts))

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
    """Extract finished matches from FootyStats league-matches response.

    Two-pass approach:
    1. Extract all finished matches with their raw goals
    2. Compute per-team averages from actual results (not unreliable per-match fields)

    This ensures the calibrator uses real data rather than xG or missing averages.
    """
    # Pass 1: extract raw match results
    raw_matches = []
    items = raw_data.get("data", [])
    if isinstance(items, dict):
        items = [items]

    for m in items:
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

        home_name = m.get("home_name") or m.get("homeTeam") or "unknown_home"
        away_name = m.get("away_name") or m.get("awayTeam") or "unknown_away"

        raw_matches.append({
            "goals_home": gh,
            "goals_away": ga,
            "home_name": home_name,
            "away_name": away_name,
            "total_corners": (m.get("team_a_corners") or 0) + (m.get("team_b_corners") or 0),
            "total_cards": (m.get("team_a_cards") or 0) + (m.get("team_b_cards") or 0),
        })

    if not raw_matches:
        return []

    # Pass 2: compute per-team averages from actual results
    from collections import defaultdict
    team_home_goals = defaultdict(list)  # goals scored at home
    team_away_goals = defaultdict(list)  # goals scored away
    team_home_conceded = defaultdict(list)  # goals conceded at home
    team_away_conceded = defaultdict(list)  # goals conceded away

    for rm in raw_matches:
        h, a = rm["home_name"], rm["away_name"]
        team_home_goals[h].append(rm["goals_home"])
        team_away_goals[a].append(rm["goals_away"])
        team_home_conceded[h].append(rm["goals_away"])
        team_away_conceded[a].append(rm["goals_home"])

    def _avg(lst):
        return sum(lst) / len(lst) if lst else 1.25

    # League average goals per team
    all_goals = [rm["goals_home"] + rm["goals_away"] for rm in raw_matches]
    league_avg_per_team = sum(all_goals) / len(all_goals) / 2.0 if all_goals else 1.25

    # Pass 3: enrich each match with team averages (Dixon-Coles inputs)
    matches = []
    for rm in raw_matches:
        h, a = rm["home_name"], rm["away_name"]

        home_scored_avg = _avg(team_home_goals[h])
        away_scored_avg = _avg(team_away_goals[a])

        # Recent form: last 5 matches for each team at their respective venue
        home_recent = team_home_goals[h][-5:] if len(team_home_goals[h]) >= 5 else team_home_goals[h]
        away_recent = team_away_goals[a][-5:] if len(team_away_goals[a]) >= 5 else team_away_goals[a]

        # Opponent defensive factor (Dixon-Coles relative strength)
        away_conceded_avg = _avg(team_away_conceded[a])  # how many goals away team concedes away
        home_conceded_avg = _avg(team_home_conceded[h])   # how many goals home team concedes at home

        away_def_rel = away_conceded_avg / league_avg_per_team if league_avg_per_team > 0 else 1.0
        home_def_rel = home_conceded_avg / league_avg_per_team if league_avg_per_team > 0 else 1.0

        matches.append({
            "goals_home": rm["goals_home"],
            "goals_away": rm["goals_away"],
            "home_goals_scored_avg": home_scored_avg,
            "away_goals_scored_avg": away_scored_avg,
            "home_goals_scored_avg_recent": _avg(home_recent),
            "away_goals_scored_avg_recent": _avg(away_recent),
            "away_goals_conceded_factor": away_def_rel,
            "home_goals_conceded_factor": home_def_rel,
            "total_corners": rm["total_corners"],
            "total_cards": rm["total_cards"],
        })

    return matches


def fetch_historical_matches(league_id: str, n_seasons: int = 6) -> List[Dict]:
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


def fetch_from_api_football(league_id: str, n_seasons: int = 6) -> List[Dict]:
    """Fetch historical matches from API-Football for calibration.

    Uses get_season_fixtures() to get full seasons. Applies two-pass
    team average computation (same as FootyStats path) for consistency.

    Reference: REGRAS #054 — dual source.
    """
    try:
        from backend.services.api_football_client import APIFootballClient
        from backend.config.leagues_config import (
            get_api_football_league_id, get_season_for_league, CALENDAR_YEAR_LEAGUES,
            LEAGUE_ID_ALIASES,
        )

        af_league_id = get_api_football_league_id(league_id)
        if not af_league_id:
            logger.info(f"[calibrator] No API-Football ID for {league_id}")
            return []

        current_season = get_season_for_league(league_id)
        resolved_id = LEAGUE_ID_ALIASES.get(league_id, league_id)
        is_calendar = resolved_id in CALENDAR_YEAR_LEAGUES

        client = APIFootballClient()
        all_matches = []
        weights = SEASON_WEIGHTS[:n_seasons]

        for i in range(n_seasons):
            season = current_season - i
            if not is_calendar and season < 2018:
                break
            if is_calendar and season < 2019:
                break

            try:
                fixtures = client.get_season_fixtures(
                    league_id=af_league_id,
                    season=season,
                )
                if not fixtures:
                    continue

                # Extract raw match data
                raw_season = []
                for fx in fixtures:
                    goals = fx.get("goals", {})
                    teams = fx.get("teams", {})
                    gh, ga = goals.get("home"), goals.get("away")
                    if gh is None or ga is None:
                        continue
                    try:
                        gh, ga = int(gh), int(ga)
                    except (ValueError, TypeError):
                        continue
                    raw_season.append({
                        "goals_home": gh,
                        "goals_away": ga,
                        "home_name": teams.get("home", {}).get("name", f"home_{i}"),
                        "away_name": teams.get("away", {}).get("name", f"away_{i}"),
                        "total_corners": 0,
                        "total_cards": 0,
                    })

                if not raw_season:
                    continue

                # Compute per-team averages (same two-pass as FootyStats)
                from collections import defaultdict
                team_hg = defaultdict(list)
                team_ag = defaultdict(list)
                team_hc = defaultdict(list)
                team_ac = defaultdict(list)

                for rm in raw_season:
                    h, a = rm["home_name"], rm["away_name"]
                    team_hg[h].append(rm["goals_home"])
                    team_ag[a].append(rm["goals_away"])
                    team_hc[h].append(rm["goals_away"])
                    team_ac[a].append(rm["goals_home"])

                def _avg(lst):
                    return sum(lst) / len(lst) if lst else 1.25

                all_g = [rm["goals_home"] + rm["goals_away"] for rm in raw_season]
                league_avg_pt = sum(all_g) / len(all_g) / 2.0 if all_g else 1.25

                w = weights[i] if i < len(weights) else 0.02

                for rm in raw_season:
                    h, a = rm["home_name"], rm["away_name"]
                    away_c_avg = _avg(team_ac[a])
                    home_c_avg = _avg(team_hc[h])

                    all_matches.append({
                        "goals_home": rm["goals_home"],
                        "goals_away": rm["goals_away"],
                        "home_goals_scored_avg": _avg(team_hg[h]),
                        "away_goals_scored_avg": _avg(team_ag[a]),
                        "home_goals_scored_avg_recent": _avg(team_hg[h][-5:]),
                        "away_goals_scored_avg_recent": _avg(team_ag[a][-5:]),
                        "away_goals_conceded_factor": away_c_avg / league_avg_pt if league_avg_pt > 0 else 1.0,
                        "home_goals_conceded_factor": home_c_avg / league_avg_pt if league_avg_pt > 0 else 1.0,
                        "total_corners": 0,
                        "total_cards": 0,
                        "season_weight": w,
                        "season_index": i,
                        "source": "api_football",
                    })

                logger.info(
                    f"[calibrator] API-Football: {league_id} season {season}: "
                    f"{len(raw_season)} matches (weight={w})"
                )
            except Exception as e:
                logger.warning(f"[calibrator] API-Football season {season} failed for {league_id}: {e}")

        return all_matches
    except Exception as e:
        logger.error(f"[calibrator] API-Football fetch error for {league_id}: {e}")
        return []


def merge_dual_sources(
    fs_matches: List[Dict],
    af_matches: List[Dict],
    league_id: str,
) -> List[Dict]:
    """Merge FootyStats + API-Football, picking most complete dataset per league.

    Strategy:
    - If one has >50% more matches -> use that one entirely
    - If similar -> use FootyStats as base (has better team stats),
      fill gaps from API-Football for seasons FootyStats doesn't cover
    - Deduplicate by season_index to avoid double-counting
    """
    n_fs = len(fs_matches)
    n_af = len(af_matches)

    logger.info(f"[calibrator] {league_id}: FootyStats={n_fs}, API-Football={n_af}")

    if n_fs == 0 and n_af == 0:
        return []
    if n_fs == 0:
        logger.info(f"[calibrator] {league_id}: FootyStats empty — using API-Football ({n_af})")
        return af_matches
    if n_af == 0:
        logger.info(f"[calibrator] {league_id}: API-Football empty — using FootyStats ({n_fs})")
        return fs_matches

    # API-Football has >50% more -> use as primary
    if n_af > n_fs * 1.5:
        logger.info(f"[calibrator] {league_id}: API-Football has {n_af} vs FootyStats {n_fs} — using API-Football")
        return af_matches

    # FootyStats as base, fill missing seasons from API-Football
    fs_seasons = {m.get("season_index", 0) for m in fs_matches}
    af_unique = [m for m in af_matches if m.get("season_index", 0) not in fs_seasons]

    merged = fs_matches + af_unique
    logger.info(f"[calibrator] {league_id}: merged FS({n_fs}) + AF unique({len(af_unique)}) = {len(merged)}")
    return merged


def calibrate_league(
    league_id: str,
    n_seasons: int = 6,
    matches: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Run full calibration for a single league.

    1. Fetch 6 seasons of historical data (or use provided matches)
    2. Grid search: lambda deflation x lambda weights
    3. Grid search: BTTS deflation
    4. Grid search: corner deflation
    5. Select best params by weighted Brier score (recent seasons count more)

    Returns optimal parameters for the league.
    """
    if matches is None:
        # Dual source: fetch from both FootyStats and API-Football (#054)
        fs_matches = fetch_historical_matches(league_id, n_seasons)
        af_matches = fetch_from_api_football(league_id, n_seasons)
        matches = merge_dual_sources(fs_matches, af_matches, league_id)

        if len(fs_matches) > 0 and len(af_matches) > 0:
            data_source = "footystats+api_football"
        elif len(fs_matches) > 0:
            data_source = "footystats"
        elif len(af_matches) > 0:
            data_source = "api_football"
        else:
            data_source = "none"

    if len(matches) < 30:
        logger.warning(f"[calibrator] {league_id}: only {len(matches)} matches — insufficient")
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
            result = _simulate_poisson_brier(
                matches, lambda_deflation_ou=deflation, lambda_weights=weights,
            )

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

    # ── Grid search: BTTS deflation (O/U fixed at optimal, BTTS varies independently) ──
    best_btts = {"brier": 1.0}
    best_ou_weights = (best_ou.get("weight_season", 0.60), best_ou.get("weight_recent", 0.40))
    best_ou_defl = best_ou.get("deflation", 1.0)

    for btts_defl in BTTS_DEFLATION_GRID:
        result = _simulate_poisson_brier(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=btts_defl,
        )
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
    optimal_result = _simulate_poisson_brier(
        matches,
        lambda_deflation_ou=best_ou_defl,
        lambda_weights=best_ou_weights,
        lambda_deflation_btts=best_btts.get("deflation", 1.0),
    )

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
        "data_source": data_source,
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
                # log_correction expects float — convert booleans to 1.0/0.0
                if isinstance(value, bool):
                    numeric_value = 1.0 if value else 0.0
                else:
                    numeric_value = float(value)

                log_correction(
                    match_id=f"calibration_{league_id}",
                    league=league_id,
                    parameter_name=param_name,
                    old_value=0.0,
                    new_value=numeric_value,
                    correction_type="calibration",
                    reason=f"[Auto-calibration] {reason} (n={n_matches} matches, "
                           f"brier_ou={brier_ou})",
                )
            except Exception as e:
                logger.error(f"Failed to save calibration {key}={value} for {league_id}: {e}")


def calibrate_all_leagues(n_seasons: int = 6) -> Dict[str, Dict]:
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
