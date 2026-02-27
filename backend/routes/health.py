from fastapi import APIRouter, Query
import os

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/health/diag")
async def diagnostics(league: str = Query("premier-league")):
    """Diagnostic endpoint to debug FootyStats API integration."""
    from backend.config.leagues_config import get_league_config
    from backend.services.footstats_client import FootyStatsClient

    result: dict = {
        "league_input": league,
        "api_key_set": bool(os.getenv("FOOTYSTATS_API_KEY")),
        "api_key_preview": (os.getenv("FOOTYSTATS_API_KEY", ""))[:6] + "...",
    }

    config = get_league_config(league)
    result["league_config"] = config

    if not config:
        result["error"] = "League config not found"
        return result

    try:
        fs = FootyStatsClient()
        # Step 1: resolve season
        season_id = fs.resolve_season_id(config["country"], config["name"], alt_names=config.get("alt_names"))
        result["season_id"] = season_id

        if not season_id:
            # Debug: check league list
            leagues_data = fs.get_league_list(chosen_only=False)
            result["league_list_success"] = leagues_data.get("success")
            result["league_list_count"] = len(leagues_data.get("data", []))
            result["error"] = "Could not resolve season_id"
            return result

        # Step 2: get matches
        matches_data = fs.get_league_matches(season_id)
        result["matches_success"] = matches_data.get("success")
        result["matches_count"] = len(matches_data.get("data", []))

        if matches_data.get("data"):
            m = matches_data["data"][0]
            result["sample_match"] = {
                "home_name": m.get("home_name"),
                "away_name": m.get("away_name"),
                "date_unix": m.get("date_unix"),
                "status": m.get("status"),
            }
    except Exception as e:
        result["exception"] = f"{type(e).__name__}: {e}"

    return result
