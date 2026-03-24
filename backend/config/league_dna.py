"""
League DNA — Consolidated Profile Matrix (Layer 1)

Static categorization of all 22 monitored leagues based on historical averages.
Reduced from 34 to 22 in #078r — removed 15 with insufficient data.

Categories:
  - DEFENSIVE: seasonAVG < 2.2 — enables Under goals, BTTS No
  - BALANCED:  2.2 <= seasonAVG <= 2.8 — standard markets
  - OFFENSIVE: seasonAVG > 2.8 — enables Over Corners, 2nd Half Goals
  - AGGRESSIVE: cardsAVG > 3.5 — card-focused markets (independent axis)

The `markets_enabled` list controls which Safe Bet strategies can fire.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class LeagueDNA:
    """Static league profile for Safe Bets filtering."""
    league_id: str
    category: str                   # DEFENSIVE | BALANCED | OFFENSIVE
    is_aggressive: bool             # Independent card axis (cardsAVG > 3.5)
    markets_enabled: List[str]      # Allowed safe bet strategies
    avg_goals: float                # Expected seasonAVG_overall
    avg_corners: float = 0.0        # Expected cornersAVG_overall
    avg_cards: float = 0.0          # Expected cardsAVG_overall
    btts_pct: float = 0.0           # Expected seasonBTTSPercentage
    goal_timing_disabled: bool = False
    corners_disabled: bool = False


# Static DNA matrix for all 22 leagues
LEAGUE_DNA_MATRIX: Dict[str, LeagueDNA] = {
    # === DEFENSIVE LEAGUES (< 2.2 goals) — Under / BTTS No ===
    "serie-b": LeagueDNA(
        league_id="serie-b", category="DEFENSIVE", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO", "UNDER_25"],
        avg_goals=2.12, avg_corners=9.0, avg_cards=4.2, btts_pct=40.0,
    ),
    "league-one": LeagueDNA(
        league_id="league-one", category="DEFENSIVE", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "UNDER_25"],
        avg_goals=2.18, avg_corners=9.2, avg_cards=3.0, btts_pct=44.0,
    ),

    # === BALANCED LEAGUES (2.2 — 2.8 goals) ===
    "la-liga": LeagueDNA(
        league_id="la-liga", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.55, avg_corners=10.0, avg_cards=4.5, btts_pct=48.0,
    ),
    "serie-a": LeagueDNA(
        league_id="serie-a", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.65, avg_corners=10.5, avg_cards=4.0, btts_pct=50.0,
    ),
    "ligue-1": LeagueDNA(
        league_id="ligue-1", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.50, avg_corners=10.2, avg_cards=3.4, btts_pct=46.0,
    ),
    "eredivisie": LeagueDNA(
        league_id="eredivisie", category="BALANCED", is_aggressive=False,
        markets_enabled=["SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.78, avg_corners=10.8, avg_cards=3.2, btts_pct=52.0,
    ),
    "championship": LeagueDNA(
        league_id="championship", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.40, avg_corners=10.0, avg_cards=3.0, btts_pct=47.0,
    ),
    "2-bundesliga": LeagueDNA(
        league_id="2-bundesliga", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.70, avg_corners=10.0, avg_cards=3.2, btts_pct=50.0,
    ),
    "primeira-liga": LeagueDNA(
        league_id="primeira-liga", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.40, avg_corners=9.8, avg_cards=4.0, btts_pct=45.0,
    ),
    "pro-league": LeagueDNA(
        league_id="pro-league", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.60, avg_corners=10.2, avg_cards=3.5, btts_pct=50.0,
    ),
    "premiership": LeagueDNA(
        league_id="premiership", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.50, avg_corners=10.0, avg_cards=3.0, btts_pct=47.0,
    ),
    "superliga": LeagueDNA(
        league_id="superliga", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.60, avg_corners=10.2, avg_cards=3.1, btts_pct=48.0,
    ),
    "a-league": LeagueDNA(
        league_id="a-league", category="BALANCED", is_aggressive=False,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.65, avg_corners=10.0, avg_cards=3.0, btts_pct=50.0,
    ),
    "mls": LeagueDNA(
        league_id="mls", category="BALANCED", is_aggressive=False,
        markets_enabled=["SAFE_CORNERS", "TIMING_2H"],
        avg_goals=2.75, avg_corners=10.5, avg_cards=3.2, btts_pct=52.0,
    ),
    "colombian-primera-a": LeagueDNA(
        league_id="colombian-primera-a", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO"],
        avg_goals=2.25, avg_corners=9.0, avg_cards=4.5, btts_pct=42.0,
    ),
    "liga-mx": LeagueDNA(
        league_id="liga-mx", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO", "SAFE_CORNERS"],
        avg_goals=2.45, avg_corners=9.8, avg_cards=4.3, btts_pct=46.0,
    ),
    "brasileirao-serie-b": LeagueDNA(
        league_id="brasileirao-serie-b", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO"],
        avg_goals=2.30, avg_corners=9.0, avg_cards=4.0, btts_pct=43.0,
    ),

    # === OFFENSIVE LEAGUES (> 2.8 goals) — Over Corners / 2nd Half Goals ===
    "premier-league": LeagueDNA(
        league_id="premier-league", category="OFFENSIVE", is_aggressive=False,
        markets_enabled=["SAFE_CORNERS", "TIMING_2H", "BTTS_YES", "OVER_25"],
        avg_goals=2.85, avg_corners=10.8, avg_cards=3.0, btts_pct=54.0,
    ),
    "bundesliga": LeagueDNA(
        league_id="bundesliga", category="OFFENSIVE", is_aggressive=False,
        markets_enabled=["SAFE_CORNERS", "TIMING_2H", "BTTS_YES", "OVER_25"],
        avg_goals=3.10, avg_corners=10.5, avg_cards=3.2, btts_pct=56.0,
    ),
    "brasileirao-serie-a": LeagueDNA(
        league_id="brasileirao-serie-a", category="OFFENSIVE", is_aggressive=True,
        markets_enabled=["SAFE_CORNERS", "TIMING_2H", "BTTS_YES", "OVER_25"],
        avg_goals=2.82, avg_corners=9.5, avg_cards=4.2, btts_pct=51.0,
    ),

    # === AGGRESSIVE LEAGUES (cardsAVG > 3.5) ===
    "primera-division": LeagueDNA(
        league_id="primera-division", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO"],
        avg_goals=2.35, avg_corners=9.2, avg_cards=5.0, btts_pct=44.0,
    ),
    "super-lig": LeagueDNA(
        league_id="super-lig", category="BALANCED", is_aggressive=True,
        markets_enabled=["UNDER_35", "BTTS_NO"],
        avg_goals=2.55, avg_corners=10.0, avg_cards=4.8, btts_pct=47.0,
    ),
}


def get_league_dna(league_id: str) -> Optional[LeagueDNA]:
    """Get the static DNA profile for a league."""
    return LEAGUE_DNA_MATRIX.get(league_id)


def classify_league_dna(
    season_avg_goals: float,
    cards_avg: float = 0.0,
) -> tuple:
    """Dynamically classify a league based on live season stats.
    Returns (category: str, is_aggressive: bool)."""
    if season_avg_goals < 2.2:
        category = "DEFENSIVE"
    elif season_avg_goals > 2.8:
        category = "OFFENSIVE"
    else:
        category = "BALANCED"

    is_aggressive = cards_avg > 3.5
    return category, is_aggressive


def get_enabled_markets(league_id: str) -> List[str]:
    """Get the list of enabled safe bet strategies for a league."""
    dna = get_league_dna(league_id)
    if dna:
        return dna.markets_enabled
    return ["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"]
