"""Dynamic League DNA — Multi-season weighted classification.

Replaces static league_dna.py profiles with dynamically computed values
from 3 seasons of historical data. Falls back to static DNA if API data
is unavailable.

Temporal Decay Weights:
    T-1: 0.50, T-2: 0.33, T-3: 0.17
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.config.league_dna import (
    LeagueDNA,
    LEAGUE_DNA_MATRIX,
    classify_league_dna,
    get_league_dna,
)

logger = logging.getLogger(__name__)

# Season weights for 3-season decay
_WEIGHTS = [0.50, 0.33, 0.17]

# Markets enabled per category
_CATEGORY_MARKETS = {
    "DEFENSIVE": ["UNDER_35", "BTTS_NO"],
    "BALANCED": ["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
    "OFFENSIVE": ["SAFE_CORNERS", "TIMING_2H"],
}


def compute_dynamic_dna(
    league_id: str,
    season_stats: List[Dict[str, Any]],
) -> Optional[LeagueDNA]:
    """Compute dynamic DNA from multi-season API statistics.

    Args:
        league_id: League identifier
        season_stats: List of season stat dicts, most recent first.
            Each dict should have:
                - average_goals_per_match (float)
                - average_corners_per_match (float)
                - average_cards_per_match (float)
                - btts_percentage (float)

    Returns:
        LeagueDNA with weighted averages, or None if insufficient data
    """
    if not season_stats:
        return None

    n = min(len(season_stats), len(_WEIGHTS))
    weights = _WEIGHTS[:n]
    total_w = sum(weights)

    def weighted_avg(key: str, default: float) -> float:
        total = 0.0
        for i in range(n):
            val = season_stats[i].get(key)
            if val is not None:
                try:
                    total += float(val) * weights[i]
                except (ValueError, TypeError):
                    total += default * weights[i]
            else:
                total += default * weights[i]
        return round(total / total_w, 2) if total_w > 0 else default

    avg_goals = weighted_avg("average_goals_per_match", 2.5)
    avg_corners = weighted_avg("average_corners_per_match", 10.0)
    avg_cards = weighted_avg("average_cards_per_match", 3.5)
    btts_pct = weighted_avg("btts_percentage", 48.0)

    category, is_aggressive = classify_league_dna(avg_goals, avg_cards)

    # Determine markets from category + aggressive axis
    markets = list(_CATEGORY_MARKETS.get(category, _CATEGORY_MARKETS["BALANCED"]))
    if is_aggressive and "TIMING_2H" not in markets:
        markets.append("TIMING_2H")

    dna = LeagueDNA(
        league_id=league_id,
        category=category,
        is_aggressive=is_aggressive,
        markets_enabled=markets,
        avg_goals=avg_goals,
        avg_corners=avg_corners,
        avg_cards=avg_cards,
        btts_pct=btts_pct,
    )

    logger.info(
        f"Dynamic DNA for {league_id}: {category} "
        f"(goals={avg_goals}, corners={avg_corners}, cards={avg_cards}, "
        f"btts={btts_pct}%, aggressive={is_aggressive})"
    )
    return dna


def get_dynamic_league_dna(
    league_id: str,
    season_stats: Optional[List[Dict[str, Any]]] = None,
) -> LeagueDNA:
    """Get league DNA with dynamic override.

    If multi-season stats are provided, computes dynamic DNA.
    Otherwise falls back to static LEAGUE_DNA_MATRIX.

    Args:
        league_id: League identifier
        season_stats: Optional list of season stat dicts (most recent first)
    """
    if season_stats:
        dynamic = compute_dynamic_dna(league_id, season_stats)
        if dynamic:
            return dynamic

    # Fallback to static DNA
    static = get_league_dna(league_id)
    if static:
        return static

    # Ultimate fallback: generic balanced profile
    return LeagueDNA(
        league_id=league_id,
        category="BALANCED",
        is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.5,
        avg_corners=10.0,
        avg_cards=3.5,
        btts_pct=48.0,
    )


def refresh_all_dynamic_dna(client) -> Dict[str, LeagueDNA]:
    """Refresh dynamic DNA profiles for all configured leagues using API data.

    Fetches season stats for the last 3 seasons per league and computes
    weighted averages. Results can be used to update the ML pipeline features.

    Args:
        client: FootyStatsClient instance

    Returns:
        Dict of league_id -> LeagueDNA
    """
    from backend.config.leagues_config import LEAGUES_CONFIG

    results = {}
    for cfg in LEAGUES_CONFIG:
        league_id = cfg["id"]
        country = cfg["country"]
        name = cfg["name"]
        alt_names = cfg.get("alt_names", [])

        try:
            season_ids = client.resolve_season_ids(
                country, name, alt_names=alt_names, n_seasons=3
            )
            if not season_ids:
                results[league_id] = get_dynamic_league_dna(league_id)
                continue

            season_stats = []
            for sid, api_name in season_ids:
                stats = client.get_league_season_stats(sid)
                if stats.get("success") and stats.get("data"):
                    data = stats["data"]
                    # league-season returns a single object or list
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    season_stats.append(data)

            dna = get_dynamic_league_dna(league_id, season_stats)
            results[league_id] = dna

        except Exception as e:
            logger.error(f"Failed to refresh DNA for {league_id}: {e}")
            results[league_id] = get_dynamic_league_dna(league_id)

    logger.info(f"Dynamic DNA refreshed for {len(results)} leagues")
    return results
