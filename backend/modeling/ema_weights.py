"""Exponential Moving Average weighting for lambda calculation (#108, #108c).

Half-life of 5 matches: after 5 games, weight drops to 50%.
#108c adds: extract_team_goals (real data), clamp_to_season (safety net).
"""

import math
from typing import List, Optional, Tuple

DEFAULT_HALF_LIFE = 5


def ema_weights(n_matches: int, half_life: float = DEFAULT_HALF_LIFE) -> List[float]:
    """Normalized exponential decay weights. Index 0 = most recent."""
    if n_matches <= 0:
        return []
    if n_matches == 1:
        return [1.0]
    decay = math.log(2) / half_life
    raw = [math.exp(-decay * i) for i in range(n_matches)]
    total = sum(raw)
    return [w / total for w in raw]


def weighted_average(values: List[float], half_life: float = DEFAULT_HALF_LIFE) -> float:
    """EMA-weighted average. values[0] = most recent."""
    if not values:
        return 0.0
    weights = ema_weights(len(values), half_life)
    return sum(v * w for v, w in zip(values, weights))


# ── Clamp (#108c) ────────────────────────────────────────────────────

def clamp_to_season(value: float, season_avg: float,
                    floor_pct: float = 0.70, cap_pct: float = 1.30) -> float:
    """Clamp EMA result to ±30% of season average. Prevents overcorrection."""
    if season_avg <= 0:
        return value
    return max(season_avg * floor_pct, min(value, season_avg * cap_pct))


# ── EMA Lambda (#108 + #108c) ───────��────────────────────────────────

def ema_lambda(
    match_goals: List[float],
    season_avg: float,
    league_avg: float,
    half_life: float = DEFAULT_HALF_LIFE,
    min_matches: int = 3,
    clamp: bool = True,
) -> float:
    """Lambda via EMA with fallbacks and safety clamp."""
    n = len(match_goals)
    if n == 0:
        return league_avg
    if n < min_matches:
        ema_weight = n / min_matches
        ema_val = weighted_average(match_goals, half_life)
        result = ema_val * ema_weight + league_avg * (1 - ema_weight)
    else:
        result = weighted_average(match_goals, half_life)
    if clamp and season_avg > 0:
        result = clamp_to_season(result, season_avg)
    return result


def ema_from_averages(
    season_avg: float,
    last_n_avg: float,
    n_recent: int = 5,
    n_season: int = 15,
    half_life: float = DEFAULT_HALF_LIFE,
    clamp: bool = True,
) -> float:
    """Approximate EMA from averages only (fallback when no per-match data)."""
    synthetic = [last_n_avg] * n_recent + [season_avg] * max(0, n_season - n_recent)
    result = weighted_average(synthetic, half_life)
    if clamp and season_avg > 0:
        result = clamp_to_season(result, season_avg)
    return result


# ── Cached team goals extraction (#112 — replaces O(N×M) iterrows) ───

def build_team_goals_cache(matches_df, max_matches: int = 20) -> Dict[str, List[Tuple[int, float, bool]]]:
    """Build cache of per-team goals from DataFrame in ONE pass. O(N)."""
    if matches_df is None or len(matches_df) == 0:
        return {}
    cache: Dict[str, list] = {}
    for _, row in matches_df.iterrows():
        status = str(row.get("status", "")).lower()
        if status in ("scheduled", "incomplete", "live", "postponed", "cancelled"):
            continue
        hg = row.get("homeGoalCount") or row.get("home_goals") or row.get("homeGoals")
        ag = row.get("awayGoalCount") or row.get("away_goals") or row.get("awayGoals")
        if hg is None or ag is None:
            continue
        try:
            hg, ag = int(hg), int(ag)
        except (ValueError, TypeError):
            continue
        date_val = int(row.get("date_unix", 0) or 0)
        home = str(row.get("home_team") or row.get("home_team_name") or row.get("homeTeam") or row.get("home_name") or "").lower().strip()
        away = str(row.get("away_team") or row.get("away_team_name") or row.get("awayTeam") or row.get("away_name") or "").lower().strip()
        if home:
            cache.setdefault(home, []).append((date_val, float(hg), True))
        if away:
            cache.setdefault(away, []).append((date_val, float(ag), False))
    for team in cache:
        cache[team].sort(key=lambda x: x[0], reverse=True)
        cache[team] = cache[team][:max_matches]
    return cache


def get_team_goals_from_cache(cache: dict, team_name: str, is_home: Optional[bool] = None) -> List[float]:
    """O(1) lookup from pre-built cache. Fallback: substring match (#062)."""
    if not cache or not team_name:
        return []
    key = team_name.lower().strip()
    entries = cache.get(key)
    if not entries:
        for k in cache:
            if key in k or k in key:
                entries = cache[k]
                break
    if not entries:
        return []
    if is_home is None:
        return [g for _, g, _ in entries]
    return [g for _, g, h in entries if h == is_home]


# ── Extract team goals from matches (#108c — kept for backward compat) ──

def extract_team_goals(
    matches_df,
    team_name: str,
    is_home: Optional[bool] = None,
    max_matches: int = 20,
) -> List[float]:
    """Extract per-match goals for a team from the season matches DataFrame.

    Args:
        matches_df: pandas DataFrame with columns like homeGoalCount, awayGoalCount,
                    home_team/away_team (or similar), date_unix, status.
        team_name: Team name to search for.
        is_home: True=home only, False=away only, None=all.
        max_matches: Max matches to return (most recent first).

    Returns:
        List of goals scored per match, most-recent-first. Empty if not found.
    """
    if matches_df is None or len(matches_df) == 0:
        return []

    team_lower = team_name.lower().strip()
    results = []

    for _, row in matches_df.iterrows():
        # Get team names (try multiple column names)
        home_name = str(
            row.get("home_team") or row.get("home_team_name") or
            row.get("homeTeam") or row.get("home_name") or ""
        ).lower().strip()
        away_name = str(
            row.get("away_team") or row.get("away_team_name") or
            row.get("awayTeam") or row.get("away_name") or ""
        ).lower().strip()

        # Skip incomplete/scheduled
        status = str(row.get("status", "")).lower()
        if status in ("scheduled", "incomplete", "live", "postponed", "cancelled"):
            continue

        # Get goals
        hg = row.get("homeGoalCount") or row.get("home_goals") or row.get("homeGoals")
        ag = row.get("awayGoalCount") or row.get("away_goals") or row.get("awayGoals")
        if hg is None or ag is None:
            continue
        try:
            hg = int(hg)
            ag = int(ag)
        except (ValueError, TypeError):
            continue

        date_val = row.get("date_unix") or row.get("timestamp") or 0
        try:
            date_val = int(date_val)
        except (ValueError, TypeError):
            date_val = 0

        # Match team (substring for fuzzy match, per #062)
        is_team_home = team_lower in home_name or home_name in team_lower
        is_team_away = team_lower in away_name or away_name in team_lower

        if not is_team_home and not is_team_away:
            continue
        if is_home is True and not is_team_home:
            continue
        if is_home is False and not is_team_away:
            continue

        goals = hg if is_team_home else ag
        results.append((date_val, float(goals)))

    # Sort by date descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [g for _, g in results[:max_matches]]


def compare_with_fixed_weights(
    match_goals: List[float], season_avg: float
) -> Tuple[float, float, float]:
    """Compare EMA vs fixed 60/40 for diagnostics."""
    if len(match_goals) < 5:
        return (0.0, 0.0, 0.0)
    ema_val = weighted_average(match_goals)
    last_5_avg = sum(match_goals[:5]) / 5
    fixed_val = season_avg * 0.6 + last_5_avg * 0.4
    diff_pct = ((ema_val - fixed_val) / fixed_val * 100) if fixed_val > 0 else 0
    return (ema_val, fixed_val, diff_pct)
