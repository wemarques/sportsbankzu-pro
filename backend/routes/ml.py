"""ML Pipeline API endpoints — training, status, and retraining."""

from fastapi import APIRouter, Query, BackgroundTasks
from typing import Dict, Any, List
import logging

logger = logging.getLogger("sportsbankzu.ml")
router = APIRouter(tags=["ml"])


@router.get("/ml/status")
def ml_status(league: str = Query("global")) -> Dict[str, Any]:
    """Check ML model status and metadata for a league."""
    try:
        from backend.ml.predictor import get_model_info, is_ml_available
        info = get_model_info(league)
        if info:
            return {
                "available": is_ml_available(league),
                **info,
            }
        return {"available": False, "league_id": league, "message": "No trained model found"}
    except Exception as e:
        logger.error(f"ML status check failed: {e}")
        return {"available": False, "error": str(e)}


@router.get("/ml/status/all")
def ml_status_all() -> Dict[str, Any]:
    """Check ML model status for all configured leagues."""
    try:
        from backend.config.leagues_config import LEAGUES_CONFIG
        from backend.ml.predictor import get_model_info, is_ml_available

        results = {}
        for cfg in LEAGUES_CONFIG:
            lid = cfg["id"]
            info = get_model_info(lid)
            results[lid] = {
                "available": is_ml_available(lid),
                "trained_at": info.get("trained_at") if info else None,
                "validation_brier": info.get("validation_brier") if info else None,
                "n_samples": info.get("n_samples") if info else None,
            }
        return {"leagues": results}
    except Exception as e:
        logger.error(f"ML status-all failed: {e}")
        return {"error": str(e)}


@router.post("/ml/retrain")
def ml_retrain(
    background_tasks: BackgroundTasks,
    leagues: str = Query("", description="Comma-separated league IDs, empty = all"),
    n_seasons: int = Query(3, description="Number of historical seasons"),
    include_markets: bool = Query(True, description="Also train O/U and BTTS models"),
) -> Dict[str, Any]:
    """Trigger ML model retraining (runs in background).

    This endpoint collects historical data and retrains RF + XGBoost models.
    Now includes market models (O/U, BTTS) by default (improvement #8).
    """
    league_ids = [lid.strip() for lid in leagues.split(",") if lid.strip()] if leagues else None

    def _run_retrain():
        try:
            import numpy as _np
            from backend.services.footstats_client import FootyStatsClient
            from backend.ml.historical_data import collect_all_leagues_history, collect_league_history, save_training_data
            from backend.ml.train_model import train_all_leagues
            from backend.ml.predictor import clear_model_cache
            from backend.config.leagues_config import LEAGUES_CONFIG

            client = FootyStatsClient()

            if league_ids:
                all_data = {}
                for lid in league_ids:
                    cfg = next((c for c in LEAGUES_CONFIG if c["id"] == lid), None)
                    if cfg:
                        matches = collect_league_history(
                            client, cfg["country"], cfg["name"],
                            alt_names=cfg.get("alt_names"), n_seasons=n_seasons,
                        )
                        if matches:
                            all_data[lid] = matches
            else:
                all_data = collect_all_leagues_history(client, n_seasons=n_seasons)

            if all_data:
                save_training_data(all_data)
                results = train_all_leagues(all_data, validate=True)

                # Improvement #8: also train O/U and BTTS market models
                if include_markets:
                    from backend.ml.feature_engineering import build_features_from_matches
                    from backend.ml.market_models import train_all_markets

                    market_count = 0
                    for league_id, matches in all_data.items():
                        try:
                            X, y, feature_names, _ts = build_features_from_matches(matches, league_id)
                            if len(y) > 0:
                                weights = _np.ones(len(y), dtype=_np.float64)
                                train_all_markets(X, matches, weights, feature_names, league_id)
                                market_count += 1
                        except Exception as e:
                            logger.warning(f"Market model training failed for {league_id}: {e}")
                    logger.info(f"Market models trained for {market_count} leagues")

                clear_model_cache()
                logger.info(f"ML retrain complete: {len(results)} leagues processed")
            else:
                logger.warning("ML retrain: no training data collected")
        except Exception as e:
            logger.error(f"ML retrain failed: {e}", exc_info=True)

    background_tasks.add_task(_run_retrain)
    return {
        "status": "started",
        "message": "Retraining started in background (1X2 + market models)",
        "leagues": league_ids or "all",
        "n_seasons": n_seasons,
        "include_markets": include_markets,
    }
