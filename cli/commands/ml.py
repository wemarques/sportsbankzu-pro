"""ML Pipeline CLI commands for training, evaluation, and status."""

import json
import logging

import click

logger = logging.getLogger(__name__)


@click.group()
def ml():
    """ML pipeline: train, evaluate, and manage prediction models."""
    pass


@ml.command()
@click.option("--leagues", "-l", default="", help="Comma-separated league IDs (empty = all)")
@click.option("--n-seasons", "-n", default=3, help="Number of historical seasons")
@click.option("--no-validate", is_flag=True, help="Skip walk-forward validation")
@click.option("--include-markets", is_flag=True, help="Also train Over/Under and BTTS models")
def train(leagues, n_seasons, no_validate, include_markets):
    """Train ML models from historical data.

    Collects match data for the last N seasons, builds features,
    and trains RF + XGBoost ensemble models per league.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from backend.services.footstats_client import FootyStatsClient
    from backend.ml.historical_data import (
        collect_all_leagues_history,
        collect_league_history,
        save_training_data,
    )
    from backend.ml.train_model import train_all_leagues
    from backend.config.leagues_config import LEAGUES_CONFIG

    client = FootyStatsClient()
    league_ids = [lid.strip() for lid in leagues.split(",") if lid.strip()] if leagues else None

    click.echo(f"Starting ML training pipeline (n_seasons={n_seasons})")

    # Collect data
    if league_ids:
        click.echo(f"Collecting data for: {', '.join(league_ids)}")
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
                    click.echo(f"  {lid}: {len(matches)} matches")
            else:
                click.echo(f"  {lid}: not found in config", err=True)
    else:
        click.echo(f"Collecting data for all {len(LEAGUES_CONFIG)} leagues...")
        all_data = collect_all_leagues_history(client, n_seasons=n_seasons)

    if not all_data:
        click.echo("No data collected. Check API key and league configs.", err=True)
        return

    # Save raw data
    path = save_training_data(all_data)
    click.echo(f"Training data saved: {path}")

    # Train 1X2 models
    click.echo("Training 1X2 models...")
    results = train_all_leagues(all_data, validate=not no_validate)

    # Train market models if requested
    if include_markets:
        click.echo("Training Over/Under + BTTS models...")
        from backend.ml.feature_engineering import build_features_from_matches
        from backend.ml.market_models import train_all_markets
        import numpy as np

        for league_id, matches in all_data.items():
            X, y, feature_names = build_features_from_matches(matches, league_id)
            if len(y) > 0:
                weights = np.ones(len(y), dtype=np.float64)
                train_all_markets(X, matches, weights, feature_names, league_id)

    # Summary
    success = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") != "success"]

    click.echo(f"\n{'='*50}")
    click.echo(f"Training complete: {len(success)} OK, {len(failed)} failed/skipped")
    for r in success:
        brier = r.get("validation", {}).get("avg_brier", "?")
        click.echo(f"  ✓ {r['league_id']}: Brier={brier}, n={r.get('n_samples', 0)}")
    for r in failed:
        click.echo(f"  ✗ {r.get('league_id', '?')}: {r.get('status', '?')}")


@ml.command()
@click.option("--league", "-l", default="global", help="League ID to check")
def status(league):
    """Check ML model status for a league."""
    from backend.ml.predictor import get_model_info, is_ml_available

    info = get_model_info(league)
    if info:
        click.echo(f"League: {league}")
        click.echo(f"  Available: {is_ml_available(league)}")
        click.echo(f"  Trained at: {info.get('trained_at', '?')}")
        click.echo(f"  Samples: {info.get('n_samples', '?')}")
        click.echo(f"  Features: {info.get('n_features', '?')}")
        click.echo(f"  Brier Score: {info.get('validation_brier', '?')}")
        click.echo(f"  Accuracy: {info.get('validation_accuracy', '?')}")
        click.echo(f"  Top features: {', '.join(info.get('top_features', [])[:5])}")
    else:
        click.echo(f"No model found for {league}")


@ml.command("status-all")
def status_all():
    """Check ML model status for all leagues."""
    from backend.config.leagues_config import LEAGUES_CONFIG
    from backend.ml.predictor import get_model_info, is_ml_available

    click.echo(f"{'League':<25} {'Available':>9} {'Brier':>7} {'Samples':>8} {'Trained':>12}")
    click.echo("-" * 65)

    for cfg in LEAGUES_CONFIG:
        lid = cfg["id"]
        info = get_model_info(lid)
        avail = is_ml_available(lid)
        if info:
            brier = info.get("validation_brier", "?")
            n = info.get("n_samples", "?")
            trained = (info.get("trained_at", "?") or "?")[:10]
            click.echo(f"{lid:<25} {'✓' if avail else '✗':>9} {str(brier):>7} {str(n):>8} {trained:>12}")
        else:
            click.echo(f"{lid:<25} {'✗':>9} {'—':>7} {'—':>8} {'—':>12}")


@ml.command("refresh-dna")
def refresh_dna():
    """Refresh dynamic league DNA profiles from API data."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from backend.services.footstats_client import FootyStatsClient
    from backend.config.league_dna_dynamic import refresh_all_dynamic_dna

    client = FootyStatsClient()
    click.echo("Refreshing dynamic DNA profiles...")
    results = refresh_all_dynamic_dna(client)

    click.echo(f"\n{'League':<25} {'Category':>10} {'Goals':>6} {'Corners':>8} {'Cards':>6} {'BTTS%':>6}")
    click.echo("-" * 65)
    for lid, dna in sorted(results.items()):
        click.echo(
            f"{lid:<25} {dna.category:>10} {dna.avg_goals:>6.2f} "
            f"{dna.avg_corners:>8.1f} {dna.avg_cards:>6.1f} {dna.btts_pct:>6.1f}"
        )
