# backend/routes/live.py
"""
Endpoints for real-time match data via API-Football v3.

Provides:
  GET /live              — All currently live fixtures (optionally filtered by league)
  GET /live/fixture/{id} — Detailed live data for a single fixture (stats, events, lineups)
  GET /live/standings    — League standings from API-Football
"""
from fastapi import APIRouter, Query, Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone, timedelta

from backend.services.api_football_client import APIFootballClient
from backend.config.leagues_config import get_api_football_league_id, get_season_for_league

logger = logging.getLogger("sportsbankzu.live")
router = APIRouter(prefix="/live", tags=["live"])

_afc = APIFootballClient()


def _current_season() -> int:
    """Infer the current football season year.

    For European leagues the season usually starts mid-year,
    so after July we use the current year, before July we use the previous year.
    """
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


@router.get("")
def live_fixtures(league: str = Query("", description="Internal league ID (optional)")) -> Dict[str, Any]:
    """Fetch all currently live fixtures from API-Football.

    Optionally filter by internal league ID (e.g., 'premier-league').
    Returns enriched records with score, minute, period, and events.
    """
    if not _afc.is_configured:
        return {"matches": [], "source": "api-football", "error": "API_FOOTBALL_KEY not configured"}

    af_league_id = None
    if league:
        af_league_id = get_api_football_league_id(league)
        if af_league_id is None:
            return {"matches": [], "source": "api-football", "error": f"League '{league}' not mapped to API-Football"}

    try:
        raw_fixtures = _afc.get_live_fixtures(league_id=af_league_id)
    except Exception as e:
        logger.error(f"[live] Error fetching live fixtures: {e}")
        return {"matches": [], "source": "api-football", "error": str(e)}

    if not raw_fixtures:
        return {"matches": [], "source": "api-football", "nextUpdate": 60}

    records = []
    for fx in raw_fixtures:
        live_data = _afc.extract_live_data(fx)
        teams = fx.get("teams", {})
        league_info = fx.get("league", {})

        record = {
            "id": f"af-{live_data['fixture_id']}",
            "apiFootballFixtureId": live_data["fixture_id"],
            "homeTeam": teams.get("home", {}).get("name", ""),
            "awayTeam": teams.get("away", {}).get("name", ""),
            "homeTeamLogo": teams.get("home", {}).get("logo", ""),
            "awayTeamLogo": teams.get("away", {}).get("logo", ""),
            "leagueName": league_info.get("name", ""),
            "country": league_info.get("country", ""),
            "leagueLogo": league_info.get("logo", ""),
            "status": "live" if live_data["is_live"] else ("finished" if live_data["is_finished"] else "scheduled"),
            "apiFootballStatus": live_data["status"],
            "score": {
                "home": live_data["goals_home"],
                "away": live_data["goals_away"],
                "halftime": {
                    "home": live_data.get("halftime_home"),
                    "away": live_data.get("halftime_away"),
                },
            },
            "minute": live_data["minute"],
            "period": live_data["status"],
            "datetime": fx.get("fixture", {}).get("date", ""),
        }
        records.append(record)

    logger.info(f"[live] Returned {len(records)} live fixtures")
    return {"matches": records, "source": "api-football", "nextUpdate": 30}


@router.get("/fixture/{fixture_id}")
def live_fixture_detail(fixture_id: int = Path(..., description="API-Football fixture ID")) -> Dict[str, Any]:
    """Fetch detailed live data for a single fixture.

    Includes: match statistics, events (goals, cards, subs), and lineups.
    """
    if not _afc.is_configured:
        return {"error": "API_FOOTBALL_KEY not configured"}

    result: Dict[str, Any] = {"fixtureId": fixture_id}

    # Fetch statistics, events, and lineups in sequence (sync calls with cache)
    try:
        stats_raw = _afc.get_fixture_statistics(fixture_id, ttl_minutes=5)
        if stats_raw:
            parsed_stats: Dict[str, Dict[str, Any]] = {}
            for team_stats in stats_raw:
                team_name = team_stats.get("team", {}).get("name", "Unknown")
                stat_map: Dict[str, Any] = {}
                for s in team_stats.get("statistics", []):
                    stat_map[s.get("type", "")] = s.get("value")
                parsed_stats[team_name] = stat_map
            result["statistics"] = parsed_stats
    except Exception as e:
        logger.warning(f"[live] Stats fetch failed for fixture {fixture_id}: {e}")

    try:
        events = _afc.get_fixture_events(fixture_id, ttl_minutes=2)
        result["events"] = [
            {
                "time": ev.get("time", {}).get("elapsed"),
                "extra": ev.get("time", {}).get("extra"),
                "team": ev.get("team", {}).get("name", ""),
                "player": ev.get("player", {}).get("name", ""),
                "assist": ev.get("assist", {}).get("name"),
                "type": ev.get("type", ""),
                "detail": ev.get("detail", ""),
            }
            for ev in events
        ]
    except Exception as e:
        logger.warning(f"[live] Events fetch failed for fixture {fixture_id}: {e}")

    try:
        lineups = _afc.get_fixture_lineups(fixture_id, ttl_minutes=60)
        result["lineups"] = [
            {
                "team": lu.get("team", {}).get("name", ""),
                "formation": lu.get("formation", ""),
                "startXI": [
                    p.get("player", {}).get("name", "")
                    for p in lu.get("startXI", [])
                ],
                "substitutes": [
                    p.get("player", {}).get("name", "")
                    for p in lu.get("substitutes", [])
                ],
            }
            for lu in lineups
        ]
    except Exception as e:
        logger.warning(f"[live] Lineups fetch failed for fixture {fixture_id}: {e}")

    try:
        injuries = _afc.get_injuries_sync(fixture_id, ttl_minutes=30)
        result["injuries"] = injuries
    except Exception as e:
        logger.warning(f"[live] Injuries fetch failed for fixture {fixture_id}: {e}")

    return result


@router.get("/standings")
def live_standings(
    league: str = Query(..., description="Internal league ID"),
    season: Optional[int] = Query(None, description="Season year"),
) -> Dict[str, Any]:
    """Fetch league standings from API-Football."""
    if not _afc.is_configured:
        return {"standings": [], "error": "API_FOOTBALL_KEY not configured"}

    af_league_id = get_api_football_league_id(league)
    if af_league_id is None:
        return {"standings": [], "error": f"League '{league}' not mapped to API-Football"}

    season_year = season or get_season_for_league(league)

    try:
        raw = _afc.get_standings(af_league_id, season_year)
    except Exception as e:
        logger.error(f"[live/standings] Error: {e}")
        return {"standings": [], "error": str(e)}

    standings = []
    for entry in raw:
        team = entry.get("team", {})
        all_stats = entry.get("all", {})
        standings.append({
            "rank": entry.get("rank"),
            "teamId": team.get("id"),
            "teamName": team.get("name", ""),
            "teamLogo": team.get("logo", ""),
            "points": entry.get("points", 0),
            "goalsDiff": entry.get("goalsDiff", 0),
            "form": entry.get("form", ""),
            "played": all_stats.get("played", 0),
            "won": all_stats.get("win", 0),
            "drawn": all_stats.get("draw", 0),
            "lost": all_stats.get("lose", 0),
            "goalsFor": all_stats.get("goals", {}).get("for", 0),
            "goalsAgainst": all_stats.get("goals", {}).get("against", 0),
        })

    return {"standings": standings, "league": league, "season": season_year, "source": "api-football"}
