"""
Corner Feature Engineering Pipeline

Builds feature vectors specifically for corner prediction models.
Reuses the existing RollingStatsTracker pattern from ml/feature_engineering.py
but focuses on corner-specific signals.

Features include:
- corners for average (rolling 5, 10)
- corners against average (rolling 5, 10)
- home/away splits
- standard deviation / stability
- historical line hit frequency
- offensive proxies (shots, possession, xG)
- matchup features (attack corners vs defense corners conceded)
- league: average, dispersion, corner environment
- drift: current season vs historical
"""

import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("sportsbankzu.corners.features")

from backend.modeling.corners import CORNER_LINES_LEGACY

ROLLING_WINDOWS = [5, 10]


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "" or val == -1 or val == -2:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class CornerStatsTracker:
    """Track rolling corner statistics per team."""

    def __init__(self):
        self.history: Dict[str, List[Dict[str, float]]] = defaultdict(list)

    def add_match(self, team: str, stats: Dict[str, float]):
        self.history[team].append(stats)

    def rolling_avg(self, team: str, stat: str, window: int) -> float:
        h = self.history.get(team, [])
        if not h:
            return 0.0
        recent = h[-window:]
        vals = [m.get(stat, 0.0) for m in recent]
        return sum(vals) / len(vals) if vals else 0.0

    def rolling_std(self, team: str, stat: str, window: int) -> float:
        h = self.history.get(team, [])
        if len(h) < 2:
            return 0.0
        recent = h[-window:]
        vals = [m.get(stat, 0.0) for m in recent]
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))

    def line_hit_rate(self, team: str, stat: str, threshold: float, window: int) -> float:
        """Fraction of recent matches where stat > threshold."""
        h = self.history.get(team, [])
        if not h:
            return 0.0
        recent = h[-window:]
        hits = sum(1 for m in recent if m.get(stat, 0.0) > threshold)
        return hits / len(recent)

    def games_played(self, team: str) -> int:
        return len(self.history.get(team, []))


def _extract_corner_stats(match: Dict[str, Any], is_home: bool) -> Dict[str, float]:
    """Extract corner-specific stats from a match dict."""
    prefix = "home" if is_home else "away"
    opp_prefix = "away" if is_home else "home"
    team_letter = "a" if is_home else "b"
    opp_letter = "b" if is_home else "a"

    def _get(*keys: str) -> float:
        for key in keys:
            val = match.get(key)
            if val is not None and val != -1 and val != "":
                return _safe_float(val)
        return 0.0

    return {
        "corners_for": _get(
            f"team_{team_letter}_corners",
            f"{prefix}Corners",
            f"home_team_corner_count" if is_home else "away_team_corner_count",
        ),
        "corners_against": _get(
            f"team_{opp_letter}_corners",
            f"{opp_prefix}Corners",
            f"home_team_corner_count" if not is_home else "away_team_corner_count",
        ),
        "total_corners": _get(
            "totalCorners",
            "total_corners",
        ) or (
            _get(f"team_{team_letter}_corners", f"{prefix}Corners")
            + _get(f"team_{opp_letter}_corners", f"{opp_prefix}Corners")
        ),
        "shots": _get(
            f"team_{team_letter}_shots",
            f"{prefix}Shots",
        ),
        "shots_on_target": _get(
            f"team_{team_letter}_shotsOnTarget",
            f"{prefix}ShotsOnTarget",
        ),
        "possession": _get(
            f"team_{team_letter}_possession",
            f"{prefix}Possession",
        ),
        "xg": _get(
            f"team_{team_letter}_xg",
            f"{prefix}_xg",
        ),
        "goals": _get(
            f"{prefix}GoalCount",
            f"{prefix}_goals",
        ),
    }


def build_corner_features(
    matches: List[Dict[str, Any]],
    league_id: str = "",
    league_stats: Optional[Dict[str, Any]] = None,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Transform match data into corner-specific feature matrix.

    Args:
        matches: List of raw match dicts (chronologically sorted)
        league_id: League identifier
        league_stats: League-level averages

    Returns:
        (X, y, feature_names) where:
            X: feature matrix (n_samples, n_features)
            y: target (total corners per match)
            feature_names: column names
    """
    matches = sorted(matches, key=lambda m: m.get("date_unix", m.get("date", 0)))

    tracker = CornerStatsTracker()
    feature_rows = []
    targets = []

    # League-level stats
    league_avg_corners = _safe_float(
        (league_stats or {}).get("cornersAVG_overall",
        (league_stats or {}).get("leagueAvgCorners", 10.0)),
        10.0,
    )

    for match in matches:
        home_team = match.get("homeTeam", match.get("home_name", ""))
        away_team = match.get("awayTeam", match.get("away_name", ""))

        home_stats = _extract_corner_stats(match, is_home=True)
        away_stats = _extract_corner_stats(match, is_home=False)

        total_corners = home_stats["total_corners"]
        if total_corners <= 0:
            # Try to compute from individual
            total_corners = home_stats["corners_for"] + away_stats["corners_for"]
        if total_corners <= 0:
            continue

        # Need at least 3 games for rolling features
        if tracker.games_played(home_team) < 3 or tracker.games_played(away_team) < 3:
            tracker.add_match(home_team, home_stats)
            tracker.add_match(away_team, away_stats)
            continue

        # Build features BEFORE updating tracker (prevent lookahead)
        features = {}

        for w in ROLLING_WINDOWS:
            suffix = f"_r{w}"
            # Home team
            features[f"home_corners_for_avg{suffix}"] = tracker.rolling_avg(home_team, "corners_for", w)
            features[f"home_corners_against_avg{suffix}"] = tracker.rolling_avg(home_team, "corners_against", w)
            features[f"home_corners_for_std{suffix}"] = tracker.rolling_std(home_team, "corners_for", w)
            features[f"home_shots_avg{suffix}"] = tracker.rolling_avg(home_team, "shots", w)
            features[f"home_possession_avg{suffix}"] = tracker.rolling_avg(home_team, "possession", w)
            features[f"home_xg_avg{suffix}"] = tracker.rolling_avg(home_team, "xg", w)

            # Away team
            features[f"away_corners_for_avg{suffix}"] = tracker.rolling_avg(away_team, "corners_for", w)
            features[f"away_corners_against_avg{suffix}"] = tracker.rolling_avg(away_team, "corners_against", w)
            features[f"away_corners_for_std{suffix}"] = tracker.rolling_std(away_team, "corners_for", w)
            features[f"away_shots_avg{suffix}"] = tracker.rolling_avg(away_team, "shots", w)
            features[f"away_possession_avg{suffix}"] = tracker.rolling_avg(away_team, "possession", w)
            features[f"away_xg_avg{suffix}"] = tracker.rolling_avg(away_team, "xg", w)

        # Total corners rolling avg (sum of both teams' corners for)
        features["combined_corners_avg_r5"] = (
            features["home_corners_for_avg_r5"] + features["away_corners_for_avg_r5"]
        )
        features["combined_corners_avg_r10"] = (
            features["home_corners_for_avg_r10"] + features["away_corners_for_avg_r10"]
        )

        # Stability metric (lower = more predictable)
        home_cv = (
            features["home_corners_for_std_r10"] / features["home_corners_for_avg_r10"]
            if features["home_corners_for_avg_r10"] > 0 else 1.0
        )
        away_cv = (
            features["away_corners_for_std_r10"] / features["away_corners_for_avg_r10"]
            if features["away_corners_for_avg_r10"] > 0 else 1.0
        )
        features["home_corner_cv"] = home_cv
        features["away_corner_cv"] = away_cv

        # Historical line hit frequency
        for line in CORNER_LINES_LEGACY:
            features[f"home_total_over_{line}_rate_r10"] = tracker.line_hit_rate(
                home_team, "total_corners", line, 10
            )
            features[f"away_total_over_{line}_rate_r10"] = tracker.line_hit_rate(
                away_team, "total_corners", line, 10
            )

        # Matchup features
        features["attack_corners_vs_defense"] = (
            features["home_corners_for_avg_r5"] - features["away_corners_against_avg_r5"]
        )
        features["defense_corners_vs_attack"] = (
            features["away_corners_for_avg_r5"] - features["home_corners_against_avg_r5"]
        )

        # Offensive proxy differential
        features["shots_diff_r5"] = features["home_shots_avg_r5"] - features["away_shots_avg_r5"]
        features["possession_diff_r5"] = features["home_possession_avg_r5"] - features["away_possession_avg_r5"]

        # League environment
        features["league_avg_corners"] = league_avg_corners
        features["combined_vs_league"] = features["combined_corners_avg_r5"] - league_avg_corners

        # Drift: recent form vs longer-term
        if features["combined_corners_avg_r10"] > 0:
            features["corner_drift"] = (
                features["combined_corners_avg_r5"] - features["combined_corners_avg_r10"]
            )
        else:
            features["corner_drift"] = 0.0

        # Games played (season stage proxy)
        features["home_games_played"] = tracker.games_played(home_team)
        features["away_games_played"] = tracker.games_played(away_team)

        feature_rows.append(features)
        targets.append(total_corners)

        # NOW update tracker
        tracker.add_match(home_team, home_stats)
        tracker.add_match(away_team, away_stats)

    if not feature_rows:
        return np.array([]), np.array([]), []

    feature_names = sorted(feature_rows[0].keys())
    X = np.array([[row.get(f, 0.0) for f in feature_names] for row in feature_rows], dtype=np.float64)
    y = np.array(targets, dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    logger.info(f"Corner features: {X.shape[0]} samples, {X.shape[1]} features")
    return X, y, feature_names


def build_match_corner_features(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Build corner features for a single match prediction (runtime).

    Uses pre-computed stats (rolling averages already in the API data)
    rather than building from match history.
    """
    features = {}

    # Direct corner averages from API data
    # #145: Cap at 12.0 — values above indicate data pollution (match count as average)
    _MAX_V1 = 12.0
    home_corners_for = min(_safe_float(home_stats.get("cornersAVG_home",
                        home_stats.get("homeCornersPerMatch",
                        home_stats.get("cornersAVG_overall", 0)))), _MAX_V1)
    away_corners_for = min(_safe_float(away_stats.get("cornersAVG_away",
                        away_stats.get("awayCornersPerMatch",
                        away_stats.get("cornersAVG_overall", 0)))), _MAX_V1)
    home_corners_against = _safe_float(home_stats.get("homeCornersAgainstPerMatch",
                            home_stats.get("cornersAgainstAVG_home", 0)))
    away_corners_against = _safe_float(away_stats.get("awayCornersAgainstPerMatch",
                            away_stats.get("cornersAgainstAVG_away", 0)))

    # Use same keys for both r5 and r10 (API doesn't distinguish windows)
    for suffix in ["_r5", "_r10"]:
        features[f"home_corners_for_avg{suffix}"] = home_corners_for
        features[f"home_corners_against_avg{suffix}"] = home_corners_against
        features[f"home_corners_for_std{suffix}"] = 0.0  # not available at runtime
        features[f"away_corners_for_avg{suffix}"] = away_corners_for
        features[f"away_corners_against_avg{suffix}"] = away_corners_against
        features[f"away_corners_for_std{suffix}"] = 0.0

        features[f"home_shots_avg{suffix}"] = _safe_float(home_stats.get("shotsAVG_home",
                                                home_stats.get("shotsPerMatch", 0)))
        features[f"away_shots_avg{suffix}"] = _safe_float(away_stats.get("shotsAVG_away",
                                                away_stats.get("shotsPerMatch", 0)))
        features[f"home_possession_avg{suffix}"] = _safe_float(home_stats.get("possessionAVG_home",
                                                    home_stats.get("possessionAVG_overall", 50)))
        features[f"away_possession_avg{suffix}"] = _safe_float(away_stats.get("possessionAVG_away",
                                                    away_stats.get("possessionAVG_overall", 50)))
        features[f"home_xg_avg{suffix}"] = _safe_float(home_stats.get("xgAVG_home",
                                            home_stats.get("xgAVG_overall", 0)))
        features[f"away_xg_avg{suffix}"] = _safe_float(away_stats.get("xgAVG_away",
                                            away_stats.get("xgAVG_overall", 0)))

    combined = home_corners_for + away_corners_for
    features["combined_corners_avg_r5"] = combined
    features["combined_corners_avg_r10"] = combined

    features["home_corner_cv"] = 0.3  # default estimate
    features["away_corner_cv"] = 0.3

    for line in [8.5, 9.5, 10.5, 11.5]:
        features[f"home_total_over_{line}_rate_r10"] = 0.5  # default
        features[f"away_total_over_{line}_rate_r10"] = 0.5

    features["attack_corners_vs_defense"] = home_corners_for - away_corners_against
    features["defense_corners_vs_attack"] = away_corners_for - home_corners_against

    features["shots_diff_r5"] = features["home_shots_avg_r5"] - features["away_shots_avg_r5"]
    features["possession_diff_r5"] = features["home_possession_avg_r5"] - features["away_possession_avg_r5"]

    league_avg = _safe_float(
        (league_stats or {}).get("cornersAVG_overall",
        (league_stats or {}).get("leagueAvgCorners", 10.0)),
        10.0,
    )
    features["league_avg_corners"] = league_avg
    features["combined_vs_league"] = combined - league_avg
    features["corner_drift"] = 0.0  # not computable at runtime without history

    features["home_games_played"] = _safe_float(home_stats.get("matchesPlayed_home",
                                     home_stats.get("matchesPlayed_overall", 15)))
    features["away_games_played"] = _safe_float(away_stats.get("matchesPlayed_away",
                                     away_stats.get("matchesPlayed_overall", 15)))

    return features


# ─── v2: Extended features for projection engine ───


def _get_split_or_fallback(
    stats: Dict[str, Any],
    key: str,
    split: str,
    fallback_key: str = "",
) -> float:
    """Get a stat with home/away split preference, falling back to overall."""
    # Try split-specific key first (e.g., "corners_total_per_match" with split="home")
    split_key = f"{key}_{split}" if split else key
    for k in [split_key, f"{split}_{key}", key, fallback_key]:
        if k:
            val = stats.get(k)
            if val is not None and val != "" and val != -1:
                return _safe_float(val)
    return 0.0


def build_v2_match_features(
    home_stats: Dict[str, Any],
    away_stats: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build expanded feature set for Corners Engine v2 runtime.

    Includes:
    - League priors
    - Team corner attack/defense
    - FH/2H decomposition
    - Pressure index (shots, possession, xG)
    - Over-percentage features
    - Stability proxies
    """
    f: Dict[str, Any] = {}
    ls = league_stats or {}

    # ── League priors ──
    f["league_corner_mean_ft"] = _safe_float(
        ls.get("average_corners_per_match",
        ls.get("cornersAVG_overall",
        ls.get("leagueAvgCorners", 10.0))),
        10.0,
    )
    f["league_corner_mean_home"] = _safe_float(
        ls.get("average_corners_per_match_home_team",
        ls.get("cornersAVG_home", f["league_corner_mean_ft"] * 0.55)),
    )
    f["league_prediction_risk"] = _safe_float(ls.get("prediction_risk", 50))
    f["league_home_advantage"] = _safe_float(ls.get("home_advantage_percentage", 45))
    f["league_progress"] = _safe_float(ls.get("progress", 50))
    f["league_matches_completed"] = _safe_float(ls.get("matches_completed", 0))

    # ── Home team corner stats ──
    # #145: Cap per-team corners at 12.0 — no team averages more than ~8 corners/match.
    # Values above 12 indicate data pollution (e.g. match count mapped as average).
    _MAX_TEAM_CORNERS_PM = 12.0
    _raw_home_for = _safe_float(
        home_stats.get("corners_total_per_match",
        home_stats.get("cornersAVG_home",
        home_stats.get("homeCornersPerMatch",
        home_stats.get("corners_per_match", 0))))
    )
    f["home_corners_for_pm"] = min(_raw_home_for, _MAX_TEAM_CORNERS_PM) if _raw_home_for > 0 else 0
    f["home_corners_against_pm"] = _safe_float(
        home_stats.get("corners_against_per_match",
        home_stats.get("cornersAgainstAVG_home",
        home_stats.get("homeCornersAgainstPerMatch", 0)))
    )
    f["home_corner_sample"] = _safe_float(
        home_stats.get("corners_recorded_matches_num",
        home_stats.get("matchesPlayed_home", 0))
    )

    # ── Away team corner stats ──
    _raw_away_for = _safe_float(
        away_stats.get("corners_total_per_match",
        away_stats.get("cornersAVG_away",
        away_stats.get("awayCornersPerMatch",
        away_stats.get("corners_per_match", 0))))
    )
    f["away_corners_for_pm"] = min(_raw_away_for, _MAX_TEAM_CORNERS_PM) if _raw_away_for > 0 else 0
    f["away_corners_against_pm"] = _safe_float(
        away_stats.get("corners_against_per_match",
        away_stats.get("cornersAgainstAVG_away",
        away_stats.get("awayCornersAgainstPerMatch", 0)))
    )
    f["away_corner_sample"] = _safe_float(
        away_stats.get("corners_recorded_matches_num",
        away_stats.get("matchesPlayed_away", 0))
    )

    # ── FH/2H timing ──
    f["home_corners_fh_pm"] = _safe_float(
        home_stats.get("corners_total_per_match_fh",
        home_stats.get("corners_total_fh", 0))
    )
    f["home_corners_2h_pm"] = _safe_float(
        home_stats.get("corners_total_per_match_2h",
        home_stats.get("corners_total_2h_overall", 0))
    )
    f["away_corners_fh_pm"] = _safe_float(
        away_stats.get("corners_total_per_match_fh",
        away_stats.get("corners_total_fh", 0))
    )
    f["away_corners_2h_pm"] = _safe_float(
        away_stats.get("corners_total_per_match_2h",
        away_stats.get("corners_total_2h_overall", 0))
    )
    f["home_timing_sample"] = _safe_float(
        home_stats.get("cornerTimingRecorded_matches", 0)
    )
    f["away_timing_sample"] = _safe_float(
        away_stats.get("cornerTimingRecorded_matches", 0)
    )

    # ── Pressure features ──
    f["home_shots_pm"] = _safe_float(
        home_stats.get("shots_per_match",
        home_stats.get("shotsAVG_home",
        home_stats.get("homeShotsPerMatch", 0)))
    )
    f["away_shots_pm"] = _safe_float(
        away_stats.get("shots_per_match",
        away_stats.get("shotsAVG_away",
        away_stats.get("awayShotsPerMatch", 0)))
    )
    f["home_sot_pm"] = _safe_float(
        home_stats.get("shots_on_target_per_match",
        home_stats.get("shotsOnTargetAVG_home",
        home_stats.get("homeShotsOnTarget", 0)))
    )
    f["away_sot_pm"] = _safe_float(
        away_stats.get("shots_on_target_per_match",
        away_stats.get("shotsOnTargetAVG_away",
        away_stats.get("awayShotsOnTarget", 0)))
    )
    f["home_possession"] = _safe_float(
        home_stats.get("average_possession",
        home_stats.get("possessionAVG_home",
        home_stats.get("homePossession", 50)))
    )
    f["away_possession"] = _safe_float(
        away_stats.get("average_possession",
        away_stats.get("possessionAVG_away",
        away_stats.get("awayPossession", 50)))
    )
    f["home_xg_for"] = _safe_float(
        home_stats.get("xg_for_avg",
        home_stats.get("xgAVG_home",
        home_stats.get("homeXG",
        home_stats.get("team_a_xg", 0))))
    )
    f["away_xg_for"] = _safe_float(
        away_stats.get("xg_for_avg",
        away_stats.get("xgAVG_away",
        away_stats.get("awayXG",
        away_stats.get("team_b_xg", 0))))
    )
    f["home_xg_against"] = _safe_float(
        home_stats.get("xg_against_avg",
        home_stats.get("xgAgainstAVG_home", 0))
    )
    f["away_xg_against"] = _safe_float(
        away_stats.get("xg_against_avg",
        away_stats.get("xgAgainstAVG_away", 0))
    )

    # ── Over-percentage features (#129: prefixed keys for home/away) ──
    for threshold in ["65", "85", "95", "105", "115", "145"]:
        f[f"home_over{threshold}_corners_pct"] = _safe_float(
            home_stats.get(f"over{threshold}_corners_percentage",
            home_stats.get(f"home_over{threshold}_corners_pct", 0))
        ) / 100.0
        f[f"away_over{threshold}_corners_pct"] = _safe_float(
            away_stats.get(f"away_over{threshold}_corners_percentage",
            away_stats.get(f"away_over{threshold}_corners_pct", 0))
        ) / 100.0

    # ── PPG (form proxy) ──
    f["home_ppg"] = _safe_float(
        home_stats.get("home_ppg",
        home_stats.get("Pre-Match PPG (Home)", 0))
    )
    f["away_ppg"] = _safe_float(
        away_stats.get("away_ppg",
        away_stats.get("Pre-Match PPG (Away)", 0))
    )

    # ── Derived / composite features ──
    f["direct_estimate_ft"] = f["home_corners_for_pm"] + f["away_corners_for_pm"]

    # #123: Proxy cornersAgainst when NULL — estimate from league avg
    league_avg = f.get("league_corner_mean_ft", 10.0)
    home_against = f["home_corners_against_pm"]
    away_against = f["away_corners_against_pm"]
    _against_estimated = False

    if home_against <= 0 and f["home_corners_for_pm"] > 0 and league_avg > 0:
        home_against = max(2.0, league_avg - f["home_corners_for_pm"])
        _against_estimated = True
    if away_against <= 0 and f["away_corners_for_pm"] > 0 and league_avg > 0:
        away_against = max(2.0, league_avg - f["away_corners_for_pm"])
        _against_estimated = True

    f["cross_estimate_ft"] = 0.0
    if home_against > 0 and away_against > 0:
        f["cross_estimate_ft"] = (
            f["home_corners_for_pm"] + away_against
            + f["away_corners_for_pm"] + home_against
        ) / 2.0

    # #123: FootyStats cornersPotential as independent projection anchor
    f["footystats_corners_potential"] = _safe_float(
        home_stats.get("cornersPotential",
        home_stats.get("corners_potential", 0))
    )

    # #131: Total game corners avg (third independent estimate)
    _home_total = _safe_float(home_stats.get("homeCornersTotalAvg", 0))
    _away_total = _safe_float(away_stats.get("awayCornersTotalAvg", 0))
    if _home_total > 0 and _away_total > 0:
        f["total_game_avg"] = (_home_total + _away_total) / 2.0
    else:
        f["total_game_avg"] = 0

    f["combined_fh"] = f["home_corners_fh_pm"] + f["away_corners_fh_pm"]
    f["combined_2h"] = f["home_corners_2h_pm"] + f["away_corners_2h_pm"]

    # ── Feature availability flags ──
    f["_has_timing"] = f["combined_fh"] > 0 and f["combined_2h"] > 0
    f["_has_against"] = f["home_corners_against_pm"] > 0 and f["away_corners_against_pm"] > 0 and not _against_estimated
    f["_has_against_estimated"] = _against_estimated  # #123: proxy active
    f["_has_pressure"] = f["home_shots_pm"] > 0 and f["away_shots_pm"] > 0
    f["_has_xg"] = f["home_xg_for"] > 0 and f["away_xg_for"] > 0

    return f


def compute_matchup_pressure_index(features: Dict[str, Any]) -> float:
    """Compute standardized matchup pressure index.

    Combines shots, shots on target, possession dominance, xG,
    and corner synergy into a single score normalized around 0.

    Positive = more pressure (more corners expected).
    Negative = less pressure.
    """
    components = []
    weights = []

    # Shots
    total_shots = features.get("home_shots_pm", 0) + features.get("away_shots_pm", 0)
    if total_shots > 0:
        # Normalize: typical match ~24 total shots
        components.append((total_shots - 24.0) / 8.0)
        weights.append(0.20)

    # Shots on target
    total_sot = features.get("home_sot_pm", 0) + features.get("away_sot_pm", 0)
    if total_sot > 0:
        components.append((total_sot - 8.0) / 3.0)
        weights.append(0.15)

    # Possession dominance (extreme possession → more corners for dominant side)
    home_poss = features.get("home_possession", 50)
    poss_dominance = abs(home_poss - 50) / 20.0  # higher = more one-sided
    components.append(poss_dominance)
    weights.append(0.10)

    # xG total
    total_xg = features.get("home_xg_for", 0) + features.get("away_xg_for", 0)
    if total_xg > 0:
        components.append((total_xg - 2.5) / 1.0)
        weights.append(0.15)

    # Corner for/against synergy
    direct = features.get("direct_estimate_ft", 0)
    league_avg = features.get("league_corner_mean_ft", 10.0)
    if direct > 0:
        components.append((direct - league_avg) / 3.0)
        weights.append(0.25)

    # Cross estimate synergy
    cross = features.get("cross_estimate_ft", 0)
    if cross > 0:
        components.append((cross - league_avg) / 3.0)
        weights.append(0.15)

    if not components:
        return 0.0

    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    index = sum(c * w for c, w in zip(components, weights)) / total_weight
    return round(max(-2.0, min(2.0, index)), 4)
