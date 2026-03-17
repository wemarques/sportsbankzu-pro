"""Feature engineering for ML prediction models.

Transforms raw match data into feature vectors suitable for
Random Forest and XGBoost training. Features include:

- Rolling averages (3, 5, 10 games) for goals, xG, shots, corners
- Elo ratings (dynamically computed per team)
- Home advantage differential
- Rest days between matches
- League DNA features (category, avg_goals, etc.)
- Temporal decay weights from multi-season collection
- Winsorized and Yeo-Johnson transformed continuous features
"""

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Elo system constants
ELO_INITIAL = 1500
ELO_K_FACTOR = 32
ELO_HOME_ADVANTAGE = 65

# Rolling window sizes
ROLLING_WINDOWS = [3, 5, 10]

# Features to exclude in "no-odds" variant (tests if model adds value beyond market)
ODDS_FEATURES = {"implied_odds_ft_1", "implied_odds_ft_x", "implied_odds_ft_2"}

# Features that get Winsorized at 1st/99th percentile
WINSORIZE_FEATURES = [
    "home_goals_scored_avg", "away_goals_scored_avg",
    "home_goals_conceded_avg", "away_goals_conceded_avg",
    "home_xg_avg", "away_xg_avg",
    "home_shots_avg", "away_shots_avg",
]


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert API values to float, handling sentinels (-1, -2, None)."""
    if val is None or val == "" or val == -1 or val == -2:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_date(date_val: Any) -> Optional[datetime]:
    """Parse various date formats from FootyStats API."""
    if isinstance(date_val, (int, float)):
        # Unix timestamp
        try:
            return datetime.fromtimestamp(date_val)
        except (ValueError, OSError):
            return None
    if isinstance(date_val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
    return None


class EloTracker:
    """Compute and track Elo ratings for teams across matches."""

    def __init__(self, k: float = ELO_K_FACTOR, home_advantage: float = ELO_HOME_ADVANTAGE):
        self.k = k
        self.home_advantage = home_advantage
        self.ratings: Dict[str, float] = defaultdict(lambda: ELO_INITIAL)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def update(self, home_team: str, away_team: str, home_goals: int, away_goals: int) -> Tuple[float, float]:
        """Update Elo ratings after a match. Returns (home_elo_before, away_elo_before)."""
        home_elo = self.ratings[home_team]
        away_elo = self.ratings[away_team]

        # Actual score: 1 = win, 0.5 = draw, 0 = loss
        if home_goals > away_goals:
            home_actual, away_actual = 1.0, 0.0
        elif home_goals < away_goals:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual, away_actual = 0.5, 0.5

        # Expected score with home advantage
        home_expected = self.expected_score(home_elo + self.home_advantage, away_elo)
        away_expected = 1.0 - home_expected

        # Goal difference multiplier (capped at 3)
        gd = abs(home_goals - away_goals)
        gd_mult = math.log(max(gd, 1) + 1)

        # Update
        self.ratings[home_team] = home_elo + self.k * gd_mult * (home_actual - home_expected)
        self.ratings[away_team] = away_elo + self.k * gd_mult * (away_actual - away_expected)

        return home_elo, away_elo

    def get_rating(self, team: str) -> float:
        return self.ratings[team]


class RollingStatsTracker:
    """Track rolling statistics per team for feature computation."""

    def __init__(self):
        # team_name -> list of stat dicts (most recent last)
        self.history: Dict[str, List[Dict[str, float]]] = defaultdict(list)

    def add_match(self, team: str, stats: Dict[str, float]):
        """Record a match's stats for a team."""
        self.history[team].append(stats)

    def get_rolling_avg(self, team: str, stat: str, window: int) -> float:
        """Get rolling average of a stat over the last `window` matches."""
        h = self.history.get(team, [])
        if not h:
            return 0.0
        recent = h[-window:]
        vals = [m.get(stat, 0.0) for m in recent]
        return sum(vals) / len(vals) if vals else 0.0

    def get_rolling_std(self, team: str, stat: str, window: int) -> float:
        """Get rolling standard deviation of a stat."""
        h = self.history.get(team, [])
        if len(h) < 2:
            return 0.0
        recent = h[-window:]
        vals = [m.get(stat, 0.0) for m in recent]
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        return math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1))

    def games_played(self, team: str) -> int:
        return len(self.history.get(team, []))


def _extract_match_stats(match: Dict[str, Any], is_home: bool) -> Dict[str, float]:
    """Extract per-team stats from a raw FootyStats match dict.

    FootyStats API uses two naming conventions:
        - league-matches endpoint: team_a_* (home) / team_b_* (away)
        - match detail endpoint:   homeXxx / awayXxx
    We check both to handle data from either endpoint.
    """
    # team_a = home, team_b = away in FootyStats convention
    team_letter = "a" if is_home else "b"
    opp_letter = "b" if is_home else "a"
    prefix = "home" if is_home else "away"
    opp_prefix = "away" if is_home else "home"

    def _get(primary: str, *fallbacks: str) -> float:
        """Try primary key, then fallbacks, return first valid value."""
        for key in (primary, *fallbacks):
            val = match.get(key)
            if val is not None and val != -1 and val != -2 and val != "":
                return _safe_float(val)
        return 0.0

    return {
        "goals_scored": _get(
            f"{prefix}GoalCount",
            f"{prefix}_goals",
            f"home_team_goal_count" if is_home else "away_team_goal_count",
        ),
        "goals_conceded": _get(
            f"{opp_prefix}GoalCount",
            f"{opp_prefix}_goals",
            f"home_team_goal_count" if not is_home else "away_team_goal_count",
        ),
        "xg": _get(
            f"team_{team_letter}_xg",
            f"{prefix}_xg",
            f"home_xg" if is_home else "away_xg",
        ),
        "xg_conceded": _get(
            f"team_{opp_letter}_xg",
            f"{opp_prefix}_xg",
            f"home_xg" if not is_home else "away_xg",
        ),
        "shots": _get(
            f"team_{team_letter}_shots",
            f"{prefix}Shots",
            f"{prefix}_shots",
        ),
        "shots_on_target": _get(
            f"team_{team_letter}_shotsOnTarget",
            f"{prefix}ShotsOnTarget",
            f"{prefix}_shotsOnTarget",
        ),
        "corners": _get(
            f"team_{team_letter}_corners",
            f"{prefix}Corners",
            f"home_team_corner_count" if is_home else "away_team_corner_count",
        ),
        "cards": _get(
            f"team_{team_letter}_cards_num",
            f"team_{team_letter}_yellow_cards",
            f"{prefix}Cards",
        ),
        "possession": _get(
            f"team_{team_letter}_possession",
            f"{prefix}Possession",
            f"{prefix}_possession",
        ),
        "fouls": _get(
            f"team_{team_letter}_fouls",
            f"{prefix}Fouls",
            f"{prefix}_fouls",
        ),
    }


def _get_rest_days(match: Dict[str, Any], team: str, last_match_dates: Dict[str, datetime]) -> float:
    """Calculate rest days since team's last match."""
    match_date = _parse_date(match.get("date_unix", match.get("date")))
    if not match_date:
        return 3.0  # default

    last_date = last_match_dates.get(team)
    if not last_date:
        return 7.0  # first match of season

    rest = (match_date - last_date).days
    return max(0.0, min(rest, 30.0))  # cap at 30 days


def build_features_from_matches(
    matches: List[Dict[str, Any]],
    league_id: str = "",
) -> Tuple[np.ndarray, np.ndarray, List[str], np.ndarray]:
    """Transform raw match dicts into feature matrix and target vector.

    Args:
        matches: List of raw FootyStats match dicts (augmented with _season_weight)
        league_id: League identifier for DNA features

    Returns:
        (X, y, feature_names, timestamps) where:
            X: numpy array of shape (n_samples, n_features)
            y: numpy array of shape (n_samples,) with labels 0=home, 1=draw, 2=away
            feature_names: list of feature column names
            timestamps: numpy array of unix timestamps per sample (for temporal decay)
    """
    # Sort matches chronologically for proper rolling computation
    matches = sorted(
        matches,
        key=lambda m: m.get("date_unix", m.get("date", 0)),
    )

    elo = EloTracker()
    rolling = RollingStatsTracker()
    last_match_dates: Dict[str, datetime] = {}

    # Get league DNA features
    league_dna_features = _get_league_dna_features(league_id)

    feature_rows = []
    targets = []
    sample_weights = []
    match_timestamps = []

    for match in matches:
        home_team = match.get("homeTeam", match.get("home_name", ""))
        away_team = match.get("awayTeam", match.get("away_name", ""))
        home_goals = int(_safe_float(match.get("homeGoalCount", match.get("home_goals", -1)), -1))
        away_goals = int(_safe_float(match.get("awayGoalCount", match.get("away_goals", -1)), -1))

        if not home_team or not away_team or home_goals < 0 or away_goals < 0:
            continue

        # Need at least 3 games per team for rolling features
        if rolling.games_played(home_team) < 3 or rolling.games_played(away_team) < 3:
            # Still record stats for building history
            home_stats = _extract_match_stats(match, is_home=True)
            away_stats = _extract_match_stats(match, is_home=False)
            rolling.add_match(home_team, home_stats)
            rolling.add_match(away_team, away_stats)
            elo.update(home_team, away_team, home_goals, away_goals)
            match_date = _parse_date(match.get("date_unix", match.get("date")))
            if match_date:
                last_match_dates[home_team] = match_date
                last_match_dates[away_team] = match_date
            continue

        # Build feature vector BEFORE updating trackers (prevent lookahead)
        features = {}

        # Elo features
        features["home_elo"] = elo.get_rating(home_team)
        features["away_elo"] = elo.get_rating(away_team)
        features["elo_diff"] = features["home_elo"] - features["away_elo"]

        # Rolling averages for each window
        for w in ROLLING_WINDOWS:
            suffix = f"_r{w}"
            for side, team in [("home", home_team), ("away", away_team)]:
                features[f"{side}_goals_scored_avg{suffix}"] = rolling.get_rolling_avg(team, "goals_scored", w)
                features[f"{side}_goals_conceded_avg{suffix}"] = rolling.get_rolling_avg(team, "goals_conceded", w)
                features[f"{side}_xg_avg{suffix}"] = rolling.get_rolling_avg(team, "xg", w)
                features[f"{side}_xg_conceded_avg{suffix}"] = rolling.get_rolling_avg(team, "xg_conceded", w)
                features[f"{side}_shots_avg{suffix}"] = rolling.get_rolling_avg(team, "shots", w)
                features[f"{side}_corners_avg{suffix}"] = rolling.get_rolling_avg(team, "corners", w)
                features[f"{side}_possession_avg{suffix}"] = rolling.get_rolling_avg(team, "possession", w)

        # Volatility (std of goals over last 5 games)
        features["home_goals_std"] = rolling.get_rolling_std(home_team, "goals_scored", 5)
        features["away_goals_std"] = rolling.get_rolling_std(away_team, "goals_scored", 5)

        # xG luck: goals - xG (overperformance signal)
        features["home_xg_luck"] = (
            rolling.get_rolling_avg(home_team, "goals_scored", 5)
            - rolling.get_rolling_avg(home_team, "xg", 5)
        )
        features["away_xg_luck"] = (
            rolling.get_rolling_avg(away_team, "goals_scored", 5)
            - rolling.get_rolling_avg(away_team, "xg", 5)
        )

        # Rest days
        features["home_rest_days"] = _get_rest_days(match, home_team, last_match_dates)
        features["away_rest_days"] = _get_rest_days(match, away_team, last_match_dates)
        features["rest_diff"] = features["home_rest_days"] - features["away_rest_days"]

        # Games played (proxy for season stage)
        features["home_games_played"] = rolling.games_played(home_team)
        features["away_games_played"] = rolling.games_played(away_team)

        # League DNA features
        features.update(league_dna_features)

        # Interaction features
        features["attack_vs_defense"] = (
            features.get("home_goals_scored_avg_r5", 0) - features.get("away_goals_conceded_avg_r5", 0)
        )
        features["defense_vs_attack"] = (
            features.get("away_goals_scored_avg_r5", 0) - features.get("home_goals_conceded_avg_r5", 0)
        )

        # Odds-derived implied probabilities (if available)
        for key in ("odds_ft_1", "odds_ft_x", "odds_ft_2"):
            odds_val = _safe_float(match.get(key), 0.0)
            features[f"implied_{key}"] = (1.0 / odds_val * 100) if odds_val > 1.0 else 0.0

        feature_rows.append(features)

        # Collect match timestamp for temporal decay
        _match_dt = _parse_date(match.get("date_unix", match.get("date")))
        match_timestamps.append(_match_dt.timestamp() if _match_dt else 0.0)

        # Target: 0 = home win, 1 = draw, 2 = away win
        if home_goals > away_goals:
            targets.append(0)
        elif home_goals == away_goals:
            targets.append(1)
        else:
            targets.append(2)

        # Season weight for sample_weight parameter in training
        sample_weights.append(match.get("_season_weight", 1.0))

        # NOW update trackers with this match's data
        home_stats = _extract_match_stats(match, is_home=True)
        away_stats = _extract_match_stats(match, is_home=False)
        rolling.add_match(home_team, home_stats)
        rolling.add_match(away_team, away_stats)
        elo.update(home_team, away_team, home_goals, away_goals)

        match_date = _parse_date(match.get("date_unix", match.get("date")))
        if match_date:
            last_match_dates[home_team] = match_date
            last_match_dates[away_team] = match_date

    if not feature_rows:
        logger.warning("No feature rows generated from matches")
        return np.array([]), np.array([]), [], np.array([])

    # Convert to numpy arrays
    feature_names = sorted(feature_rows[0].keys())
    X = np.array([[row.get(f, 0.0) for f in feature_names] for row in feature_rows], dtype=np.float64)
    y = np.array(targets, dtype=np.int32)

    # Replace NaN/inf with 0
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    timestamps = np.array(match_timestamps, dtype=np.float64)

    logger.info(f"Built feature matrix: {X.shape[0]} samples, {X.shape[1]} features")
    return X, y, feature_names, timestamps


def _get_league_dna_features(league_id: str) -> Dict[str, float]:
    """Extract numeric features from league DNA profile."""
    try:
        from backend.config.league_dna import get_league_dna
        dna = get_league_dna(league_id)
        if dna:
            return {
                "league_avg_goals": dna.avg_goals,
                "league_avg_corners": dna.avg_corners,
                "league_avg_cards": dna.avg_cards,
                "league_btts_pct": dna.btts_pct,
                "league_is_offensive": 1.0 if dna.category == "OFFENSIVE" else 0.0,
                "league_is_defensive": 1.0 if dna.category == "DEFENSIVE" else 0.0,
                "league_is_aggressive": 1.0 if dna.is_aggressive else 0.0,
            }
    except Exception:
        pass
    return {
        "league_avg_goals": 2.5,
        "league_avg_corners": 10.0,
        "league_avg_cards": 3.5,
        "league_btts_pct": 48.0,
        "league_is_offensive": 0.0,
        "league_is_defensive": 0.0,
        "league_is_aggressive": 0.0,
    }


def winsorize(X: np.ndarray, feature_names: List[str], percentile: float = 1.0) -> np.ndarray:
    """Winsorize features at the given percentile to reduce outlier impact."""
    X_out = X.copy()
    for i, name in enumerate(feature_names):
        if any(wf in name for wf in WINSORIZE_FEATURES):
            lower = np.percentile(X_out[:, i], percentile)
            upper = np.percentile(X_out[:, i], 100 - percentile)
            X_out[:, i] = np.clip(X_out[:, i], lower, upper)
    return X_out
