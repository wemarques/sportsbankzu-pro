"""Exponential Moving Average weighting for lambda calculation (#108).

Replaces hardcoded 60% season / 40% last-5 with exponential decay.
Half-life of 5 matches: after 5 games, weight drops to 50%.
"""

import math
from typing import List, Tuple

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


def ema_lambda(
    match_goals: List[float],
    season_avg: float,
    league_avg: float,
    half_life: float = DEFAULT_HALF_LIFE,
    min_matches: int = 3,
) -> float:
    """Lambda via EMA with fallbacks for few matches."""
    n = len(match_goals)
    if n == 0:
        return league_avg
    if n < min_matches:
        ema_weight = n / min_matches
        ema_val = weighted_average(match_goals, half_life)
        return ema_val * ema_weight + league_avg * (1 - ema_weight)
    return weighted_average(match_goals, half_life)


def ema_from_averages(
    season_avg: float,
    last_n_avg: float,
    n_recent: int = 5,
    n_season: int = 15,
    half_life: float = DEFAULT_HALF_LIFE,
) -> float:
    """Approximate EMA using only averages (no per-match data).

    Creates synthetic per-match list and applies EMA.
    This is the bridge between the current 60/40 system and full EMA.
    """
    synthetic = [last_n_avg] * n_recent + [season_avg] * max(0, n_season - n_recent)
    return weighted_average(synthetic, half_life)


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
