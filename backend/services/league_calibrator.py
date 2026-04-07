"""
Per-League Calibration Service

Replaces uniform deflation (#043) with league-specific factors
trained on 4 seasons of historical data.

Reference: REGRAS #052
"""

import logging
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from backend.services.math_service import poisson_pmf
from backend.modeling.poisson_matrix import dixon_coles_tau

logger = logging.getLogger("sportsbankzu.league_calibrator")
logger.setLevel(logging.INFO)

# ── NB2 for cards calibration (#122) ──────────────────────────────
# Must match the model used by cards_engine.py (NB2 with overdispersion).
# Default overdispersion from cards_engine: 1.3 (literature: 1.2-1.5).
_CARDS_DEFAULT_OVERDISPERSION = 1.3

try:
    from scipy.stats import nbinom as _nbinom_cal
    _CAL_HAS_SCIPY = True
except ImportError:
    _CAL_HAS_SCIPY = False


def _nb2_cdf(k: int, lam: float, overdispersion: float = _CARDS_DEFAULT_OVERDISPERSION) -> float:
    """NB2 CDF: P(X <= k). Mirrors cards_engine.py NB2 parametrization.

    NB2: var = lam * overdispersion
    scipy nbinom: n = lam^2 / (var - lam), p = lam / var
    Falls back to Poisson if scipy unavailable or overdispersion <= 1.01.
    """
    if overdispersion <= 1.01 or not _CAL_HAS_SCIPY:
        # Poisson fallback (same as cards_engine when overdispersion ~ 1)
        return sum(poisson_pmf(i, lam) for i in range(k + 1))
    var = lam * overdispersion
    if var <= lam:
        return sum(poisson_pmf(i, lam) for i in range(k + 1))
    n_param = (lam ** 2) / (var - lam)
    p_param = lam / var
    n_param = max(n_param, 0.5)
    return float(_nbinom_cal.cdf(k, n_param, p_param))


def _nb2_prob_over(lam: float, line: float, overdispersion: float = _CARDS_DEFAULT_OVERDISPERSION) -> float:
    """P(X > line) using NB2. Used for cards calibration (#122)."""
    return 1.0 - _nb2_cdf(int(line), lam, overdispersion)

# Temporal decay weights for 6 seasons (T-1 most recent)
SEASON_WEIGHTS = [0.50, 0.25, 0.13, 0.07, 0.03, 0.02]

# Grid search ranges — expanded after all 28 leagues hit 1.10 ceiling (#053)
DEFLATION_GRID = [
    0.80, 0.90, 0.95, 1.00, 1.03, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.50,
]
LAMBDA_WEIGHT_GRID = [
    (0.40, 0.60), (0.50, 0.50), (0.60, 0.40), (0.70, 0.30),
]
BTTS_DEFLATION_GRID = [0.80, 0.90, 1.00, 1.10, 1.20, 1.30]
CORNER_DEFLATION_GRID = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
ONE_X_TWO_DEFLATION_GRID = [0.90, 0.95, 0.97, 1.00, 1.03, 1.05, 1.10]
CORNER_BRIER_GRID = [0.75, 0.80, 0.83, 0.85, 0.88, 0.90, 0.92, 0.95, 0.97, 1.00, 1.03, 1.05, 1.10]  # #119a finer granularity
CARDS_DEFLATION_GRID = [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30]  # #119b includes inflation >1.0
XG_BLEND_GRID = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
RHO_GRID = [round(-0.25 + i * 0.01, 2) for i in range(31)]  # -0.25 to 0.05


def _brier(prob: float, outcome: int) -> float:
    """Brier score for a single prediction."""
    return (prob - outcome) ** 2


def _simulate_all_markets(
    matches: List[Dict],
    lambda_deflation_ou: float,
    lambda_weights: Tuple[float, float],
    lambda_deflation_btts: float | None = None,
    lambda_deflation_1x2: float | None = None,
    corner_deflation: float = 1.0,
    cards_deflation: float = 1.0,
    xg_blend_weight: float = 0.0,
    compute_only: str | None = None,
    rho: float = 0.0,
) -> Dict[str, float]:
    """Simulate Brier scores for markets with per-market deflation.

    Args:
        compute_only: If set, only compute this market group for performance.
            Options: "ou", "btts", "1x2", "corners", "cards", None (all).
    """
    defl_btts = lambda_deflation_btts if lambda_deflation_btts is not None else lambda_deflation_ou
    defl_1x2 = lambda_deflation_1x2 if lambda_deflation_1x2 is not None else 1.0

    w_season, w_recent = lambda_weights

    # Compute flags for performance — skip unnecessary loops in grid search
    do_ou = compute_only is None or compute_only == "ou"
    do_btts = compute_only is None or compute_only == "btts"
    do_1x2 = compute_only is None or compute_only in ("1x2", "ou")
    do_corners = compute_only is None or compute_only == "corners"
    do_cards = compute_only is None or compute_only == "cards"

    # Accumulators per market
    brier = {
        "over_15": [], "over_25": [], "over_35": [], "over_45": [],
        "under_15": [], "under_25": [], "under_35": [], "under_45": [],
        "btts": [],
        "1x2_home": [], "1x2_draw": [], "1x2_away": [],
        "dc_1x": [], "dc_12": [], "dc_x2": [],
        "corners_o85": [], "corners_o95": [], "corners_o105": [],
        "cards_o25": [], "cards_o35": [], "cards_o45": [],
    }

    # Pre-compute league averages for cards and corners
    _cards_vals = [m.get("total_cards", 0) for m in matches if m.get("total_cards", 0) > 0]
    avg_cards_league = sum(_cards_vals) / len(_cards_vals) if _cards_vals else 4.0

    _corners_vals = [m.get("total_corners", 0) for m in matches if m.get("total_corners", 0) > 0]
    avg_corners_league = sum(_corners_vals) / len(_corners_vals) if _corners_vals else 10.0

    for m in matches:
        home_avg_season = m.get("home_goals_scored_avg", 0) or 0
        away_avg_season = m.get("away_goals_scored_avg", 0) or 0
        home_avg_recent = m.get("home_goals_scored_avg_recent", home_avg_season) or home_avg_season
        away_avg_recent = m.get("away_goals_scored_avg_recent", away_avg_season) or away_avg_season
        home_def_factor = m.get("away_goals_conceded_factor", 1.0) or 1.0
        away_def_factor = m.get("home_goals_conceded_factor", 1.0) or 1.0

        lh_raw = (home_avg_season * w_season + home_avg_recent * w_recent) * home_def_factor
        la_raw = (away_avg_season * w_season + away_avg_recent * w_recent) * away_def_factor

        # xG blend
        if xg_blend_weight > 0:
            home_xg = m.get("home_xg")
            away_xg = m.get("away_xg")
            if home_xg is not None and home_xg > 0:
                lh_raw = (1.0 - xg_blend_weight) * lh_raw + xg_blend_weight * home_xg
            if away_xg is not None and away_xg > 0:
                la_raw = (1.0 - xg_blend_weight) * la_raw + xg_blend_weight * away_xg

        lh_raw = max(0.2, min(4.5, lh_raw))
        la_raw = max(0.2, min(4.5, la_raw))

        # Per-market lambdas
        lh_ou = lh_raw * lambda_deflation_ou
        la_ou = la_raw * lambda_deflation_ou

        gh = m.get("goals_home", 0) or 0
        ga = m.get("goals_away", 0) or 0
        total = gh + ga

        # ── O/U matrix (all lines) — with Dixon-Coles τ (#078) ──
        if do_ou:
            prob_over = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0, 4.5: 0.0}
            for h in range(9):
                ph = poisson_pmf(h, lh_ou)
                for a in range(9):
                    pa = poisson_pmf(a, la_ou)
                    tau = dixon_coles_tau(h, a, lh_ou, la_ou, rho)
                    p = tau * ph * pa
                    t = h + a
                    for line in prob_over:
                        if t > line:
                            prob_over[line] += p

            for line, prob in prob_over.items():
                actual = 1 if total > line else 0
                key_suffix = f"{int(line)}5"
                brier[f"over_{key_suffix}"].append(_brier(prob, actual))
                brier[f"under_{key_suffix}"].append(_brier(1.0 - prob, 1 - actual))

        # ── BTTS (use real btts boolean when available) — with τ (#078) ──
        if do_btts:
            lh_btts = lh_raw * defl_btts
            la_btts = la_raw * defl_btts
            prob_btts = 0.0
            for h in range(9):
                ph = poisson_pmf(h, lh_btts)
                for a in range(9):
                    pa = poisson_pmf(a, la_btts)
                    tau = dixon_coles_tau(h, a, lh_btts, la_btts, rho)
                    if h >= 1 and a >= 1:
                        prob_btts += tau * ph * pa
            btts_real = m.get("btts")
            actual_btts = (1 if btts_real else 0) if btts_real is not None else (1 if (gh > 0 and ga > 0) else 0)
            brier["btts"].append(_brier(prob_btts, actual_btts))

        # ── 1X2 — with Dixon-Coles τ (#078) ──
        if do_1x2:
            lh_1x2 = lh_raw * defl_1x2
            la_1x2 = la_raw * defl_1x2
            prob_home = 0.0
            prob_draw = 0.0
            for h in range(9):
                ph = poisson_pmf(h, lh_1x2)
                for a in range(9):
                    pa = poisson_pmf(a, la_1x2)
                    tau = dixon_coles_tau(h, a, lh_1x2, la_1x2, rho)
                    p = tau * ph * pa
                    if h > a:
                        prob_home += p
                    elif h == a:
                        prob_draw += p
            prob_away = max(0, 1.0 - prob_home - prob_draw)

            brier["1x2_home"].append(_brier(prob_home, 1 if gh > ga else 0))
            brier["1x2_draw"].append(_brier(prob_draw, 1 if gh == ga else 0))
            brier["1x2_away"].append(_brier(prob_away, 1 if gh < ga else 0))

            # ── Double Chance (derived from 1X2) ──
            brier["dc_1x"].append(_brier(prob_home + prob_draw, 1 if gh >= ga else 0))
            brier["dc_12"].append(_brier(prob_home + prob_away, 1 if gh != ga else 0))
            brier["dc_x2"].append(_brier(prob_draw + prob_away, 1 if gh <= ga else 0))

        # ── Corners (use league average as lambda, real total as outcome) ──
        if do_corners:
            tc = m.get("total_corners")
            if tc is not None and tc > 0:
                corner_lambda = avg_corners_league * corner_deflation
                corner_lambda = max(3.0, min(20.0, corner_lambda))
                for line, key in [(8.5, "corners_o85"), (9.5, "corners_o95"), (10.5, "corners_o105")]:
                    prob_over_c = sum(poisson_pmf(k, corner_lambda) for k in range(int(line) + 1, 25))
                    brier[key].append(_brier(prob_over_c, 1 if tc > line else 0))

        # ── Cards (NB2 — same model as cards_engine.py) (#122) ──
        if do_cards:
            total_cards = m.get("total_cards")
            if total_cards is not None and total_cards > 0:
                cards_lambda = avg_cards_league * cards_deflation
                cards_lambda = max(1.0, min(12.0, cards_lambda))
                for line, key in [(2.5, "cards_o25"), (3.5, "cards_o35"), (4.5, "cards_o45")]:
                    prob_over_cards = _nb2_prob_over(cards_lambda, line)
                    brier[key].append(_brier(prob_over_cards, 1 if total_cards > line else 0))

    # Aggregate
    def avg(lst):
        return sum(lst) / len(lst) if lst else None

    result = {}
    for k, v in brier.items():
        result[f"brier_{k}"] = avg(v)

    # Grouped averages
    result["brier_over_avg"] = avg(brier["over_15"] + brier["over_25"] + brier["over_35"] + brier["over_45"])
    result["brier_under_avg"] = avg(brier["under_15"] + brier["under_25"] + brier["under_35"] + brier["under_45"])
    result["brier_1x2_avg"] = avg(brier["1x2_home"] + brier["1x2_draw"] + brier["1x2_away"])
    result["brier_dc_avg"] = avg(brier["dc_1x"] + brier["dc_12"] + brier["dc_x2"])
    result["brier_corners_avg"] = avg(brier["corners_o85"] + brier["corners_o95"] + brier["corners_o105"])
    result["brier_cards_avg"] = avg(brier["cards_o25"] + brier["cards_o35"] + brier["cards_o45"])
    result["n_matches"] = len(brier["over_25"])
    result["n_corners_matches"] = len(brier["corners_o85"])
    result["n_cards_matches"] = len(brier["cards_o25"])

    # Backward-compatible aliases
    result["brier_ou"] = result.get("brier_over_25")
    result["brier_btts"] = result.get("brier_btts")
    result["brier_1x2"] = result.get("brier_1x2_home")

    return result


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

        gh = m.get("homeGoalCount")
        if gh is None:
            gh = m.get("home_goals")
        ga = m.get("awayGoalCount")
        if ga is None:
            ga = m.get("away_goals")
        if gh is None or ga is None:
            continue

        try:
            gh, ga = int(gh), int(ga)
        except (ValueError, TypeError):
            continue

        home_name = m.get("home_name") or m.get("homeTeam") or "unknown_home"
        away_name = m.get("away_name") or m.get("awayTeam") or "unknown_away"

        # Sanitize sentinel values: FootyStats uses -1 for "not available"
        def _sanitize(val, default=0):
            if val is None:
                return default
            try:
                v = int(val)
                return v if v >= 0 else default
            except (ValueError, TypeError):
                if isinstance(val, list):
                    return len(val)
                return default

        # Cards: use team_a_cards_num (integer), NOT team_a_cards (array of timings)
        home_cards = _sanitize(m.get("team_a_cards_num") or m.get("team_a_yellow_cards"))
        away_cards = _sanitize(m.get("team_b_cards_num") or m.get("team_b_yellow_cards"))

        # Corners: sanitize -1 sentinel
        home_corners = _sanitize(m.get("team_a_corners"))
        away_corners = _sanitize(m.get("team_b_corners"))

        # BTTS: boolean field from league-matches
        btts_actual = m.get("btts")
        if btts_actual is None:
            btts_actual = (gh > 0 and ga > 0)

        # #128c: Extract xG for xG blend grid search
        _home_xg_raw = m.get("team_a_xg")
        _away_xg_raw = m.get("team_b_xg")
        _home_xg = float(_home_xg_raw) if _home_xg_raw and float(_home_xg_raw) > 0 else None
        _away_xg = float(_away_xg_raw) if _away_xg_raw and float(_away_xg_raw) > 0 else None

        raw_matches.append({
            "goals_home": gh,
            "goals_away": ga,
            "home_name": home_name,
            "away_name": away_name,
            "total_corners": home_corners + away_corners,
            "home_corners": home_corners,
            "away_corners": away_corners,
            "total_cards": home_cards + away_cards,
            "home_cards": home_cards,
            "away_cards": away_cards,
            "btts": bool(btts_actual),
            "cards_potential": _sanitize(m.get("cards_potential")),
            "corners_potential": _sanitize(m.get("corners_potential")),
            "home_xg": _home_xg,   # #128c
            "away_xg": _away_xg,   # #128c
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

    # League average corners and cards (for Poisson baselines)
    corners_with_data = [rm["total_corners"] for rm in raw_matches if rm["total_corners"] > 0]
    avg_corners = sum(corners_with_data) / len(corners_with_data) if corners_with_data else 0
    cards_with_data = [rm["total_cards"] for rm in raw_matches if rm["total_cards"] > 0]
    avg_cards = sum(cards_with_data) / len(cards_with_data) if cards_with_data else 0

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
            "avg_corners_total": avg_corners,
            "avg_cards_total": avg_cards,
            "home_corners": rm.get("home_corners", 0),
            "away_corners": rm.get("away_corners", 0),
            "home_cards": rm.get("home_cards", 0),
            "away_cards": rm.get("away_cards", 0),
            "btts": rm.get("btts", False),
            "cards_potential": rm.get("cards_potential", 0),
            "corners_potential": rm.get("corners_potential", 0),
            "home_xg": rm.get("home_xg"),   # #128c: pass through for xG blend
            "away_xg": rm.get("away_xg"),   # #128c
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


def _safe_float(val):
    if val is None:
        return None
    try:
        v = float(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    if val is None:
        return None
    try:
        v = int(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def fetch_season_stats(league_id: str, n_seasons: int = 6) -> List[Dict]:
    """Fetch league-season aggregate stats from FootyStats.

    Returns 1 dict per season with real percentages for cards, corners, BTTS, O/U.
    Uses get_league_season_stats() — 1 API call per season, cached 6h.
    Reference: REGRAS #056
    """
    try:
        from backend.services.footstats_client import FootyStatsClient
        from backend.config.leagues_config import LEAGUES_CONFIG

        client = FootyStatsClient()
        all_stats = []

        league_cfg = next((c for c in LEAGUES_CONFIG if c["id"] == league_id), None)
        if not league_cfg:
            return []

        # Resolve season IDs dynamically (same as fetch_historical_matches)
        resolved = client.resolve_season_ids(
            country=league_cfg["country"],
            league_name=league_cfg["name"],
            alt_names=league_cfg.get("alt_names", []),
            n_seasons=n_seasons,
        )
        if not resolved:
            logger.warning(f"[calibrator] No season IDs resolved for {league_id} season stats")
            return []

        for i, (season_id, _api_name) in enumerate(resolved[:n_seasons]):
            try:
                data = client.get_league_season_stats(season_id)
                items = data.get("data", [])
                stats = items[0] if isinstance(items, list) and items else (items if isinstance(items, dict) else {})

                if not stats:
                    continue

                weight = SEASON_WEIGHTS[i] if i < len(SEASON_WEIGHTS) else 0.02

                all_stats.append({
                    "season_index": i,
                    "season_weight": weight,
                    "avg_goals_overall": _safe_float(stats.get("seasonAVG_overall")),
                    "avg_goals_home": _safe_float(stats.get("seasonAVG_home")),
                    "avg_goals_away": _safe_float(stats.get("seasonAVG_away")),
                    "total_matches": _safe_int(stats.get("matchesCompleted")),
                    "btts_pct": _safe_float(stats.get("seasonBTTSPercentage")),
                    "over15_pct": _safe_float(stats.get("seasonOver15Percentage_overall")),
                    "over25_pct": _safe_float(stats.get("seasonOver25Percentage_overall")),
                    "over35_pct": _safe_float(stats.get("seasonOver35Percentage_overall")),
                    "cards_avg": _safe_float(stats.get("cardsAVG_overall")),
                    "over25_cards_pct": _safe_float(stats.get("over25CardsPercentage_overall")),
                    "over35_cards_pct": _safe_float(stats.get("over35CardsPercentage_overall")),
                    "over45_cards_pct": _safe_float(stats.get("over45CardsPercentage_overall")),
                    "over55_cards_pct": _safe_float(stats.get("over55CardsPercentage_overall")),
                    "corners_avg": _safe_float(stats.get("cornersAVG_overall")),
                    "over85_corners_pct": _safe_float(stats.get("over85CornersPercentage_overall")),
                    "over95_corners_pct": _safe_float(stats.get("over95CornersPercentage_overall")),
                    "over105_corners_pct": _safe_float(stats.get("over105CornersPercentage_overall")),
                    "home_win_pct": _safe_float(stats.get("homeWinPercentage")),
                    "draw_pct": _safe_float(stats.get("drawPercentage")),
                    "away_win_pct": _safe_float(stats.get("awayWinPercentage")),
                })

                logger.info(f"[calibrator] league-season {league_id} s={season_id}: "
                            f"btts={stats.get('seasonBTTSPercentage')}%, cards_avg={stats.get('cardsAVG_overall')}")

            except Exception as e:
                logger.warning(f"[calibrator] league-season {league_id} s={season_id} failed: {e}")

        return all_stats
    except Exception as e:
        logger.error(f"[calibrator] league-season fetch error for {league_id}: {e}")
        return []


def _calibrate_btts_from_season(season_stats: List[Dict], lambda_weights) -> Dict:
    """Calibrate BTTS deflation against real seasonBTTSPercentage."""
    best = {"brier": 1.0, "deflation": 1.0}
    w_season, w_recent = lambda_weights

    for defl in BTTS_DEFLATION_GRID:
        total_brier = 0.0
        n = 0.0
        for ss in season_stats:
            btts_real = ss.get("btts_pct")
            avg_home = ss.get("avg_goals_home")
            avg_away = ss.get("avg_goals_away")
            if btts_real is None or avg_home is None or avg_away is None:
                continue
            if avg_home <= 0 or avg_away <= 0:
                continue

            weight = ss.get("season_weight", 1.0)
            lh = avg_home * defl
            la = avg_away * defl

            prob_btts = 0.0
            for h in range(9):
                ph = poisson_pmf(h, lh)
                for a in range(9):
                    if h >= 1 and a >= 1:
                        prob_btts += ph * poisson_pmf(a, la)

            actual = btts_real / 100.0
            total_brier += ((prob_btts - actual) ** 2) * weight
            n += weight

        if n > 0 and (total_brier / n) < best["brier"]:
            best = {"brier": total_brier / n, "deflation": defl}

    return best


def _calibrate_cards_from_season(season_stats: List[Dict]) -> Dict:
    """Calibrate cards deflation against real Over X Cards percentages.

    #122 fixes:
    - Uses NB2 (same model as cards_engine.py) instead of Poisson
    - Bilateral Brier: evaluates both Over AND Under per line
    - Expanded lines: 2.5, 3.5, 4.5, 5.5 (all available from FootyStats)
    """
    lines = [
        ("over25_cards_pct", 2.5),
        ("over35_cards_pct", 3.5),
        ("over45_cards_pct", 4.5),
        ("over55_cards_pct", 5.5),  # #122 Fix 4: expanded
    ]
    best = {"brier": 1.0, "deflation": 1.0}

    for defl in CARDS_DEFLATION_GRID:
        total_brier = 0.0
        n = 0.0
        for ss in season_stats:
            cards_avg = ss.get("cards_avg")
            if cards_avg is None or cards_avg <= 0:
                continue
            weight = ss.get("season_weight", 1.0)
            cards_lambda = cards_avg * defl

            for pct_key, line in lines:
                actual_pct = ss.get(pct_key)
                if actual_pct is None:
                    continue
                # #122 Fix 1: NB2 instead of Poisson
                prob_over = _nb2_prob_over(cards_lambda, line)
                prob_under = 1.0 - prob_over
                actual_over = actual_pct / 100.0
                actual_under = 1.0 - actual_over

                # #122 Fix 3: Bilateral Brier (Over + Under)
                brier_over = (prob_over - actual_over) ** 2
                brier_under = (prob_under - actual_under) ** 2
                brier_bilateral = (brier_over + brier_under) / 2.0

                total_brier += brier_bilateral * weight
                n += weight

        if n > 0 and (total_brier / n) < best["brier"]:
            best = {"brier": total_brier / n, "deflation": defl}

    return best


def _calibrate_corners_from_season(season_stats: List[Dict]) -> Dict:
    """Calibrate corners deflation against real Over X Corners percentages."""
    lines = [("over85_corners_pct", 8.5), ("over95_corners_pct", 9.5), ("over105_corners_pct", 10.5)]
    best = {"brier": 1.0, "deflation": 1.0}

    for defl in CORNER_BRIER_GRID:
        total_brier = 0.0
        n = 0.0
        for ss in season_stats:
            corners_avg = ss.get("corners_avg")
            if corners_avg is None or corners_avg <= 0:
                continue
            weight = ss.get("season_weight", 1.0)
            corners_lambda = corners_avg * defl

            for pct_key, line in lines:
                actual_pct = ss.get(pct_key)
                if actual_pct is None:
                    continue
                prob = sum(poisson_pmf(k, corners_lambda) for k in range(int(line) + 1, 25))
                total_brier += ((prob - actual_pct / 100.0) ** 2) * weight
                n += weight

        if n > 0 and (total_brier / n) < best["brier"]:
            best = {"brier": total_brier / n, "deflation": defl}

    return best


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
        # Dual source: FootyStats first, API-Football only if needed (#054)
        fs_matches = fetch_historical_matches(league_id, n_seasons)

        # Only fetch API-Football if FootyStats has insufficient data
        if len(fs_matches) >= 100:
            # FootyStats has enough — skip API-Football to save time
            matches = fs_matches
            data_source = "footystats"
        else:
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

    # ── Grid search 1: O/U deflation × lambda weights ──
    best_ou = {"brier": 1.0}

    for deflation in DEFLATION_GRID:
        for weights in LAMBDA_WEIGHT_GRID:
            result = _simulate_all_markets(
                matches, lambda_deflation_ou=deflation, lambda_weights=weights,
                compute_only="ou",
            )

            b = result.get("brier_over_avg")
            if b is not None and b < best_ou["brier"]:
                best_ou = {
                    "brier": b,
                    "deflation": deflation,
                    "weight_season": weights[0],
                    "weight_recent": weights[1],
                }

    best_ou_weights = (best_ou.get("weight_season", 0.60), best_ou.get("weight_recent", 0.40))
    best_ou_defl = best_ou.get("deflation", 1.0)

    # ── Grid search 2: BTTS deflation (O/U fixed) ──
    best_btts = {"brier": 1.0}

    for btts_defl in BTTS_DEFLATION_GRID:
        result = _simulate_all_markets(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=btts_defl,
            compute_only="btts",
        )
        b = result.get("brier_btts")
        if b is not None and b < best_btts["brier"]:
            best_btts = {"brier": b, "deflation": btts_defl}

    # ── Grid search 3: 1X2 deflation ──
    best_1x2_defl = {"brier": 1.0}

    for defl_1x2 in ONE_X_TWO_DEFLATION_GRID:
        result = _simulate_all_markets(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=best_btts.get("deflation", 1.0),
            lambda_deflation_1x2=defl_1x2,
            compute_only="1x2",
        )
        b = result.get("brier_1x2_avg")
        if b is not None and b < best_1x2_defl["brier"]:
            best_1x2_defl = {"brier": b, "deflation": defl_1x2}

    # ── Grid search 4: Dixon-Coles ρ via MLE (#078-v2) ──
    # Brier is ~flat over ρ (range ~0.002) — useless for calibrating ρ.
    # MLE (log-likelihood of observed scorelines) is the correct objective
    # per Dixon & Coles (1997). Since τ only affects (0,0),(0,1),(1,0),(1,1),
    # LL(ρ) = Σ log[τ(x_i, y_i, λ_h_i, λ_a_i, ρ)] + const w.r.t. ρ.
    # We only need τ at the observed score — no 9x9 matrix loop needed.
    defl_1x2_for_rho = best_1x2_defl.get("deflation", 1.0)
    w_s, w_r = best_ou_weights

    # Pre-compute per-match lambdas and count scoreline types (once)
    match_lambdas = []
    score_counts = {"00": 0, "01": 0, "10": 0, "11": 0, "other": 0}
    sum_lh = sum_la = 0.0

    for m in matches:
        home_s = m.get("home_goals_scored_avg", 0) or 0
        away_s = m.get("away_goals_scored_avg", 0) or 0
        home_r = m.get("home_goals_scored_avg_recent", home_s) or home_s
        away_r = m.get("away_goals_scored_avg_recent", away_s) or away_s
        h_def = m.get("away_goals_conceded_factor", 1.0) or 1.0
        a_def = m.get("home_goals_conceded_factor", 1.0) or 1.0

        lh = max(0.2, min(4.5, (home_s * w_s + home_r * w_r) * h_def)) * defl_1x2_for_rho
        la = max(0.2, min(4.5, (away_s * w_s + away_r * w_r) * a_def)) * defl_1x2_for_rho

        gh = m.get("goals_home", 0) or 0
        ga = m.get("goals_away", 0) or 0

        match_lambdas.append((gh, ga, lh, la))
        sum_lh += lh
        sum_la += la

        if gh <= 1 and ga <= 1:
            score_counts[f"{gh}{ga}"] += 1
        else:
            score_counts["other"] += 1

    n_total = len(match_lambdas)
    avg_lh = sum_lh / n_total if n_total else 0
    avg_la = sum_la / n_total if n_total else 0

    logger.info(
        f"[rho-data] {league_id}: N={n_total} "
        f"scores={{0-0:{score_counts['00']}, 0-1:{score_counts['01']}, "
        f"1-0:{score_counts['10']}, 1-1:{score_counts['11']}, other:{score_counts['other']}}} "
        f"avg_lh={avg_lh:.3f} avg_la={avg_la:.3f} defl_1x2={defl_1x2_for_rho}"
    )

    best_rho = {"ll": -1e18, "rho": 0.0}
    ll_curve = {}

    for rho_val in RHO_GRID:
        log_lik = 0.0

        for gh, ga, lh, la in match_lambdas:
            tau = dixon_coles_tau(gh, ga, lh, la, rho_val)
            if tau > 0:
                log_lik += math.log(tau)
            else:
                log_lik += -50  # heavy penalty for invalid tau

        ll_curve[rho_val] = log_lik
        if log_lik > best_rho["ll"]:
            best_rho = {"ll": log_lik, "rho": rho_val}

    # Log LL curve at key points for diagnostics
    diag_rhos = [-0.25, -0.20, -0.15, -0.10, -0.05, 0.0, 0.05]
    ll_str = " | ".join(f"{r:+.2f}:{ll_curve.get(r, 0):.3f}" for r in diag_rhos if r in ll_curve)
    logger.info(f"[rho-LL] {league_id}: {ll_str}")

    optimal_rho = best_rho.get("rho", 0.0)

    # Sanity guard: cap extreme rho values (#078-validation)
    if optimal_rho <= -0.20:
        logger.warning(
            f"[calibrator] {league_id}: rho={optimal_rho} is extreme (< -0.20). "
            f"Possible data/formula issue. Capping at -0.15."
        )
        optimal_rho = -0.15
    if optimal_rho >= 0.03:
        logger.warning(
            f"[calibrator] {league_id}: rho={optimal_rho} is positive (> 0.03). "
            f"Unusual for football — check draw data for this league."
        )

    logger.info(
        f"[calibrator] {league_id}: optimal rho={optimal_rho} "
        f"(raw_best={best_rho['rho']}, LL={best_rho['ll']:.2f})"
    )

    # ── Grid search 5: Corners deflation (Brier-based) ──
    best_corner = {"brier": 1.0}

    for c_defl in CORNER_BRIER_GRID:
        result = _simulate_all_markets(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=best_btts.get("deflation", 1.0),
            lambda_deflation_1x2=best_1x2_defl.get("deflation", 1.0),
            corner_deflation=c_defl,
            compute_only="corners",
            rho=optimal_rho,
        )
        b = result.get("brier_corners_avg")
        if b is not None and b < best_corner["brier"]:
            best_corner = {"brier": b, "deflation": c_defl}

    # Fallback: ratio-based if no corner Brier matches
    if best_corner["brier"] >= 1.0:
        avg_corners_actual = 0
        n_corners = 0
        for m in matches:
            tc = m.get("total_corners")
            if tc and tc > 0:
                avg_corners_actual += tc
                n_corners += 1
        avg_corners_actual = avg_corners_actual / n_corners if n_corners > 0 else 10.0
        try:
            from backend.config.league_dna import get_league_dna
            dna = get_league_dna(league_id)
            expected_corners = dna.avg_corners if dna else 10.0
        except Exception:
            expected_corners = 10.0
        corner_factor = avg_corners_actual / expected_corners if expected_corners > 0 else 1.0
        corner_factor = max(0.70, min(1.20, round(corner_factor, 2)))
    else:
        corner_factor = best_corner.get("deflation", 1.0)

    # ── Grid search 6: Cards deflation ──
    best_cards = {"brier": 1.0}

    for c_defl in CARDS_DEFLATION_GRID:
        result = _simulate_all_markets(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=best_btts.get("deflation", 1.0),
            lambda_deflation_1x2=best_1x2_defl.get("deflation", 1.0),
            corner_deflation=corner_factor,
            cards_deflation=c_defl,
            compute_only="cards",
            rho=optimal_rho,
        )
        b = result.get("brier_cards_avg")
        if b is not None and b < best_cards["brier"]:
            best_cards = {"brier": b, "deflation": c_defl}

    cards_factor = best_cards.get("deflation", 1.0)

    # ── Grid search 7: xG blend weight ──
    best_xg = {"brier": 1.0, "weight": 0.0}

    for xg_w in XG_BLEND_GRID:
        result = _simulate_all_markets(
            matches,
            lambda_deflation_ou=best_ou_defl,
            lambda_weights=best_ou_weights,
            lambda_deflation_btts=best_btts.get("deflation", 1.0),
            lambda_deflation_1x2=best_1x2_defl.get("deflation", 1.0),
            corner_deflation=corner_factor,
            cards_deflation=cards_factor,
            xg_blend_weight=xg_w,
            compute_only="ou",
            rho=optimal_rho,
        )
        b = result.get("brier_over_avg")
        if b is not None and b < best_xg["brier"]:
            best_xg = {"brier": b, "weight": xg_w}

    # ── Enrich with season stats (resolves BTTS ceiling + cards null) (#056) ──
    season_stats = fetch_season_stats(league_id, n_seasons)

    if season_stats:
        # BTTS: calibrate against real seasonBTTSPercentage
        btts_season = _calibrate_btts_from_season(season_stats, best_ou_weights)
        if btts_season.get("brier") is not None:
            btts_match_brier = best_btts.get("brier", 1.0)
            # Prefer season-based if better or if match-based hit ceiling
            if btts_season["brier"] < btts_match_brier or best_btts.get("deflation") == BTTS_DEFLATION_GRID[-1]:
                best_btts = btts_season
                logger.info(f"[calibrator] {league_id}: BTTS from season stats = {best_btts['deflation']} "
                           f"(brier {best_btts['brier']:.4f})")

        # Cards: calibrate against real cardsAVG + over% (#122: conditional override)
        cards_season = _calibrate_cards_from_season(season_stats)
        if cards_season.get("brier") is not None:
            cards_match_brier = best_cards.get("brier", 1.0)
            if cards_season["brier"] < cards_match_brier:
                cards_factor = cards_season["deflation"]
                logger.info(f"[calibrator] {league_id}: cards from season stats = {cards_factor} "
                           f"(season brier {cards_season['brier']:.4f} < match {cards_match_brier:.4f})")
            else:
                logger.info(f"[calibrator] {league_id}: cards keeping match-based = {cards_factor} "
                           f"(match brier {cards_match_brier:.4f} <= season {cards_season['brier']:.4f})")

        # Corners: compare with season stats
        corners_season = _calibrate_corners_from_season(season_stats)
        if corners_season.get("brier") is not None:
            if corners_season["brier"] < best_corner.get("brier", 1.0):
                corner_factor = corners_season["deflation"]
                logger.info(f"[calibrator] {league_id}: corners from season stats = {corner_factor}")

    # ── BTTS fusion weights suggestion (heuristic from BTTS deflation) ──
    btts_defl_val = best_btts.get("deflation", 1.0)
    if btts_defl_val > 1.10:
        suggested_btts_weights = {"footystats": 0.50, "poisson": 0.20, "team_avg": 0.30}
    elif btts_defl_val < 0.90:
        suggested_btts_weights = {"footystats": 0.30, "poisson": 0.40, "team_avg": 0.30}
    else:
        suggested_btts_weights = {"footystats": 0.40, "poisson": 0.30, "team_avg": 0.30}

    # ── Final optimal simulation with all best params ──
    optimal = _simulate_all_markets(
        matches,
        lambda_deflation_ou=best_ou_defl,
        lambda_weights=best_ou_weights,
        lambda_deflation_btts=best_btts.get("deflation", 1.0),
        lambda_deflation_1x2=best_1x2_defl.get("deflation", 1.0),
        corner_deflation=corner_factor,
        cards_deflation=cards_factor,
        xg_blend_weight=best_xg.get("weight", 0.0),
        rho=optimal_rho,
    )

    # ── Threshold suggestions per market (Brier heuristic) ──
    def _threshold_from_brier(brier_val, tight=0.62, loose=0.78):
        if brier_val is None:
            return loose
        if brier_val < 0.20:
            return tight
        elif brier_val < 0.23:
            return tight + 0.05
        elif brier_val < 0.25:
            return tight + 0.10
        else:
            return loose

    suggested_safe_prob = {
        "over_under": _threshold_from_brier(optimal.get("brier_over_avg"), 0.65, 0.78),
        "btts": _threshold_from_brier(optimal.get("brier_btts"), 0.65, 0.78),
        "1x2": _threshold_from_brier(optimal.get("brier_1x2_avg"), 0.55, 0.68),
        "dc": _threshold_from_brier(optimal.get("brier_dc_avg"), 0.72, 0.85),
        "corners": _threshold_from_brier(optimal.get("brier_corners_avg"), 0.62, 0.75),
        "cards": _threshold_from_brier(optimal.get("brier_cards_avg"), 0.65, 0.78),
    }

    # ── SAFE determination ──
    safe_enabled = (
        optimal.get("brier_over_avg") is not None
        and optimal["brier_over_avg"] < 0.25
        and len(matches) >= 100
    )

    params = {
        # Existing
        "lambda_deflation_ou": best_ou_defl,
        "lambda_deflation_btts": best_btts.get("deflation", 1.0),
        "lambda_weight_season": best_ou.get("weight_season", 0.60),
        "lambda_weight_recent": best_ou.get("weight_recent", 0.40),
        "corner_factor": corner_factor,
        "safe_enabled": safe_enabled,
        # Per-market deflation
        "lambda_deflation_1x2": best_1x2_defl.get("deflation", 1.0),
        "cards_factor": cards_factor,
        "xg_blend_weight": best_xg.get("weight", 0.0),
        # Dixon-Coles ρ (#078)
        "rho": optimal_rho,
        # New — BTTS fusion weights
        "btts_weight_footystats": suggested_btts_weights["footystats"],
        "btts_weight_poisson": suggested_btts_weights["poisson"],
        "btts_weight_team_avg": suggested_btts_weights["team_avg"],
        # New — thresholds per market
        "safe_prob_ou": suggested_safe_prob["over_under"],
        "safe_prob_btts": suggested_safe_prob["btts"],
        "safe_prob_1x2": suggested_safe_prob["1x2"],
        "safe_prob_dc": suggested_safe_prob["dc"],
        "safe_prob_corners": suggested_safe_prob["corners"],
        "safe_prob_cards": suggested_safe_prob["cards"],
        # Brier diagnostics
        "brier_over_avg": optimal.get("brier_over_avg"),
        "brier_under_avg": optimal.get("brier_under_avg"),
        "brier_ou": optimal.get("brier_over_25"),
        "brier_btts": optimal.get("brier_btts"),
        "brier_1x2": optimal.get("brier_1x2_avg"),
        "brier_dc_avg": optimal.get("brier_dc_avg"),
        "brier_corners_avg": optimal.get("brier_corners_avg"),
        "brier_cards_avg": optimal.get("brier_cards_avg"),
    }

    logger.info(
        f"[calibrator] {league_id}: optimal — "
        f"ou={best_ou_defl}, btts={best_btts.get('deflation', 1.0)}, "
        f"1x2={best_1x2_defl.get('deflation', 1.0)}, "
        f"corners={corner_factor}, cards={cards_factor}, "
        f"xg_w={best_xg.get('weight', 0.0)}, ρ={optimal_rho}, "
        f"safe={safe_enabled}, brier_ou={optimal.get('brier_over_avg', '?')}"
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
        # Existing
        "lambda_deflation_ou": ("lambda_multiplier", "Calibrated lambda deflation for O/U"),
        "lambda_deflation_btts": ("btts_multiplier", "Calibrated BTTS deflation"),
        "corner_factor": ("corner_multiplier", "Calibrated corner factor (Brier-based)"),
        "lambda_weight_season": ("lambda_weight_season", "Calibrated season weight"),
        "lambda_weight_recent": ("lambda_weight_recent", "Calibrated recent weight"),
        "safe_enabled": ("safe_enabled", "Per-league SAFE status"),
        # New — per-market deflation
        "lambda_deflation_1x2": ("1x2_multiplier", "Calibrated 1X2 deflation"),
        "cards_factor": ("cards_multiplier", "Calibrated cards factor (Brier-based)"),
        "xg_blend_weight": ("xg_blend_weight", "Calibrated xG blend weight"),
        # Dixon-Coles rho (#078)
        "rho": ("rho", "Calibrated Dixon-Coles rho (goal correlation)"),
        # BTTS fusion weights
        "btts_weight_footystats": ("btts_weight_footystats", "Calibrated BTTS FootyStats weight"),
        "btts_weight_poisson": ("btts_weight_poisson", "Calibrated BTTS Poisson weight"),
        "btts_weight_team_avg": ("btts_weight_team_avg", "Calibrated BTTS team_avg weight"),
        # New — thresholds per market
        "safe_prob_ou": ("safe_prob_ou", "Calibrated SAFE threshold for O/U"),
        "safe_prob_btts": ("safe_prob_btts", "Calibrated SAFE threshold for BTTS"),
        "safe_prob_1x2": ("safe_prob_1x2", "Calibrated SAFE threshold for 1X2"),
        "safe_prob_dc": ("safe_prob_dc", "Calibrated SAFE threshold for DC"),
        "safe_prob_corners": ("safe_prob_corners", "Calibrated SAFE threshold for Corners"),
        "safe_prob_cards": ("safe_prob_cards", "Calibrated SAFE threshold for Cards"),
        # Diagnostic Brier scores
        "brier_over_avg": ("brier_over_avg", "Diagnostic: Brier Over all lines"),
        "brier_under_avg": ("brier_under_avg", "Diagnostic: Brier Under all lines"),
        "brier_1x2": ("brier_1x2_avg", "Diagnostic: Brier 1X2 averaged"),
        "brier_dc_avg": ("brier_dc_avg", "Diagnostic: Brier Double Chance averaged"),
        "brier_corners_avg": ("brier_corners_avg", "Diagnostic: Brier Corners averaged"),
        "brier_cards_avg": ("brier_cards_avg", "Diagnostic: Brier Cards averaged"),
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

    # Persist calibrations to S3 for Lambda deploy survival (#059)
    try:
        from backend.audit import export_corrections_to_s3
        export_corrections_to_s3()
    except Exception as e:
        logger.warning(f"S3 export after calibration failed: {e}")


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
