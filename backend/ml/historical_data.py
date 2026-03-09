"""Multi-season historical data collection for ML training.

Fetches match data for the last N seasons (default 3) from FootyStats API,
applies exponential decay weights, and stores in a unified training dataset.

Temporal Decay Weights (3 seasons):
    T-1 (most recent): 0.50
    T-2:               0.33
    T-3 (oldest):      0.17
"""

import logging
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Exponential decay weights for 3-season window
SEASON_WEIGHTS = {0: 0.50, 1: 0.33, 2: 0.17}  # index 0 = most recent

# Minimum games played in current season before blending with historical
CURRENT_SEASON_BLEND_THRESHOLD = 15
CURRENT_SEASON_MIN_GAMES = 3

# Storage path for historical training data
_DATA_DIR = Path(os.getenv("DATA_ROOT", ".")) / ".ml_data"


def get_season_weight(season_index: int, n_seasons: int = 3) -> float:
    """Return the exponential decay weight for a season by recency index.

    Args:
        season_index: 0 = most recent, 1 = T-2, 2 = T-3, etc.
        n_seasons: Total seasons in window
    """
    if n_seasons <= 1:
        return 1.0
    return SEASON_WEIGHTS.get(season_index, 0.0)


def blend_current_with_historical(
    current_value: float,
    historical_value: float,
    games_played: int,
) -> float:
    """Dynamically blend current season data with historical multi-season data.

    Blending logic:
        games_played >= 15  -> 100% current season
        games_played < 3    -> 100% historical
        3 <= games < 15     -> linear interpolation
    """
    if games_played >= CURRENT_SEASON_BLEND_THRESHOLD:
        return current_value
    if games_played < CURRENT_SEASON_MIN_GAMES:
        return historical_value

    alpha = (games_played - CURRENT_SEASON_MIN_GAMES) / (
        CURRENT_SEASON_BLEND_THRESHOLD - CURRENT_SEASON_MIN_GAMES
    )
    return current_value * alpha + historical_value * (1 - alpha)


def collect_league_history(
    client,
    country: str,
    league_name: str,
    alt_names: Optional[List[str]] = None,
    n_seasons: int = 3,
) -> List[Dict[str, Any]]:
    """Collect match data for the last n_seasons from FootyStats API.

    Returns a list of match dicts, each augmented with:
        - season_index (0 = most recent)
        - season_weight (exponential decay)
        - season_id

    Args:
        client: FootyStatsClient instance
        country: Country name
        league_name: League name
        alt_names: Alternative league names
        n_seasons: Number of seasons to fetch (default 3)
    """
    season_ids = client.resolve_season_ids(
        country, league_name, alt_names=alt_names, n_seasons=n_seasons
    )

    if not season_ids:
        logger.warning(f"No seasons found for {country}/{league_name}")
        return []

    all_matches = []

    for idx, (season_id, api_name) in enumerate(season_ids):
        weight = get_season_weight(idx, n_seasons)
        logger.info(
            f"Fetching season {idx + 1}/{len(season_ids)}: "
            f"id={season_id} weight={weight:.2f} ({api_name})"
        )

        # Fetch all pages of matches for this season
        page = 1
        season_matches = []
        while True:
            data = client.get_league_matches(season_id, page=page)
            if not data.get("success"):
                break
            matches = data.get("data", [])
            if not matches:
                break
            season_matches.extend(matches)
            # FootyStats paginates; if fewer than expected, we're done
            if len(matches) < 50:
                break
            page += 1

        # Augment each match with season metadata
        for match in season_matches:
            # Only include completed matches (status = "complete")
            status = str(match.get("status", "")).lower()
            if status not in ("complete", "finished", "ft"):
                continue

            match["_season_index"] = idx
            match["_season_weight"] = weight
            match["_season_id"] = season_id
            all_matches.append(match)

        logger.info(
            f"Season {season_id}: {len(season_matches)} total, "
            f"{sum(1 for m in season_matches if m.get('_season_index') is not None)} completed"
        )

    logger.info(
        f"Collected {len(all_matches)} completed matches across "
        f"{len(season_ids)} seasons for {country}/{league_name}"
    )
    return all_matches


def collect_all_leagues_history(
    client,
    n_seasons: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """Collect historical data for all configured leagues.

    Returns a dict keyed by league_id with lists of augmented match dicts.
    """
    from backend.config.leagues_config import LEAGUES_CONFIG

    all_data = {}
    for league_cfg in LEAGUES_CONFIG:
        league_id = league_cfg["id"]
        country = league_cfg["country"]
        name = league_cfg["name"]
        alt_names = league_cfg.get("alt_names", [])

        logger.info(f"Collecting history for {league_id} ({country}/{name})")
        try:
            matches = collect_league_history(
                client, country, name, alt_names=alt_names, n_seasons=n_seasons
            )
            if matches:
                all_data[league_id] = matches
                logger.info(f"{league_id}: {len(matches)} matches collected")
            else:
                logger.warning(f"{league_id}: no matches found")
        except Exception as e:
            logger.error(f"{league_id}: collection failed: {e}")

    return all_data


def save_training_data(data: Dict[str, List[Dict[str, Any]]], filename: str = "training_data.json"):
    """Persist collected training data to disk."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, default=str)
    logger.info(f"Training data saved to {path} ({os.path.getsize(path) / 1024:.0f} KB)")
    return path


def load_training_data(filename: str = "training_data.json") -> Dict[str, List[Dict[str, Any]]]:
    """Load previously collected training data from disk."""
    path = _DATA_DIR / filename
    if not path.exists():
        logger.warning(f"Training data not found at {path}")
        return {}
    with open(path, "r") as f:
        return json.load(f)
