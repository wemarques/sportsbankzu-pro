#!/usr/bin/env python3
"""Full ML retrain pipeline with auditable artifact generation.

Called by the ml-retrain-validate GitHub Actions workflow.
Produces all required artifacts for human audit before promotion.

Artifacts saved to --output-dir:
  - training_summary.json         Full training results with per-league metrics
  - league_classifications.json   ML_ACTIVE / POISSON / DEACTIVATED per league
  - market_models_summary.json    Aggregated market model gate results
  - retrain.log                   Complete training log
  - per_league_metadata/          Individual metadata.json per league (from .ml_models)

Usage:
  python scripts/retrain_validate.py --leagues "" --n-seasons 3 --include-markets --output-dir /tmp/artifacts
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Setup logging to both console and file
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(output_dir: Path):
    log_path = output_dir / "retrain.log"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_path), mode="w"),
    ]
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers)
    return log_path


def main():
    parser = argparse.ArgumentParser(description="ML Retrain Validation Pipeline")
    parser.add_argument("--leagues", default="", help="Comma-separated league IDs (empty = all)")
    parser.add_argument("--n-seasons", default="3", help="Number of historical seasons")
    parser.add_argument("--include-markets", action="store_true", help="Train Over/Under + BTTS")
    parser.add_argument("--output-dir", default="/tmp/ml_pipeline/artifacts", help="Artifact output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_path = setup_logging(output_dir)
    logger = logging.getLogger("retrain_validate")

    n_seasons = int(args.n_seasons)
    league_filter = [lid.strip() for lid in args.leagues.split(",") if lid.strip()] if args.leagues else None

    logger.info("=" * 70)
    logger.info("ML RETRAIN VALIDATION PIPELINE")
    logger.info(f"  Timestamp:       {datetime.utcnow().isoformat()}Z")
    logger.info(f"  Leagues:         {league_filter or 'ALL'}")
    logger.info(f"  Seasons:         {n_seasons}")
    logger.info(f"  Include markets: {args.include_markets}")
    logger.info(f"  Output dir:      {output_dir}")
    logger.info(f"  DATA_ROOT:       {os.environ.get('DATA_ROOT', 'NOT SET')}")
    logger.info("=" * 70)

    # Import pipeline modules
    import numpy as np
    from backend.services.footstats_client import FootyStatsClient
    from backend.ml.historical_data import (
        collect_all_leagues_history,
        collect_league_history,
        save_training_data,
    )
    from backend.ml.train_model import train_all_leagues, BRIER_DEACTIVATION_THRESHOLD
    from backend.config.leagues_config import LEAGUES_CONFIG

    # ──────────────────────────────────────────────────────────
    # 1. Collect historical data from FootyStats API
    # ──────────────────────────────────────────────────────────
    logger.info("Phase 1: Collecting historical data from API...")
    client = FootyStatsClient()

    if league_filter:
        all_data = {}
        for lid in league_filter:
            cfg = next((c for c in LEAGUES_CONFIG if c["id"] == lid), None)
            if cfg:
                matches = collect_league_history(
                    client, cfg["country"], cfg["name"],
                    alt_names=cfg.get("alt_names"), n_seasons=n_seasons,
                )
                if matches:
                    all_data[lid] = matches
                    logger.info(f"  {lid}: {len(matches)} matches")
                else:
                    logger.warning(f"  {lid}: no matches collected")
            else:
                logger.error(f"  {lid}: not found in LEAGUES_CONFIG")
    else:
        all_data = collect_all_leagues_history(client, n_seasons=n_seasons)

    if not all_data:
        logger.error("No training data collected. Check FOOTYSTATS_API_KEY and connectivity.")
        sys.exit(1)

    # Save raw data
    raw_path = save_training_data(all_data)
    logger.info(f"Raw training data saved: {raw_path}")

    total_matches = sum(len(m) for m in all_data.values())
    logger.info(f"Total: {len(all_data)} leagues, {total_matches} matches")

    # ──────────────────────────────────────────────────────────
    # 2. Train 1X2 models (RF + XGBoost ensemble)
    # ──────────────────────────────────────────────────────────
    logger.info("")
    logger.info("Phase 2: Training 1X2 models...")
    results_1x2 = train_all_leagues(all_data, validate=True)

    # ──────────────────────────────────────────────────────────
    # 3. Train market models (Over/Under + BTTS)
    # ──────────────────────────────────────────────────────────
    market_results_all = {}
    if args.include_markets:
        logger.info("")
        logger.info("Phase 3: Training Over/Under + BTTS market models...")
        from backend.ml.feature_engineering import build_features_from_matches
        from backend.ml.market_models import train_all_markets

        for league_id, matches in all_data.items():
            try:
                X, y, feature_names, _ts = build_features_from_matches(matches, league_id)
                if len(y) > 0:
                    weights = np.ones(len(y), dtype=np.float64)
                    market_res = train_all_markets(X, matches, weights, feature_names, league_id)
                    market_results_all[league_id] = market_res
            except Exception as e:
                logger.error(f"Market training failed for {league_id}: {e}")

    # ──────────────────────────────────────────────────────────
    # 4. Build audit artifacts
    # ──────────────────────────────────────────────────────────
    logger.info("")
    logger.info("Phase 4: Generating audit artifacts...")

    # 4a. Classify leagues
    classifications = []
    for r in results_1x2:
        lid = r.get("league_id", "?")
        status = r.get("status", "unknown")
        val = r.get("validation", {})
        brier = val.get("avg_brier")

        if status != "success":
            classification = "FAILED"
        elif r.get("ml_deactivated"):
            classification = "DEACTIVATED"
        elif isinstance(brier, float) and brier < 0.60:
            classification = "ML_ACTIVE"
        else:
            classification = "POISSON"

        entry = {
            "league_id": lid,
            "classification": classification,
            "status": status,
            "brier": round(brier, 4) if isinstance(brier, float) else None,
            "ece": round(val.get("avg_ece"), 4) if isinstance(val.get("avg_ece"), (int, float)) else None,
            "accuracy": round(val.get("avg_accuracy"), 4) if isinstance(val.get("avg_accuracy"), (int, float)) else None,
            "odds_value_added": r.get("odds_value_added"),
            "market_efficiency_r2": r.get("market_efficiency_r2"),
            "n_samples": r.get("n_samples"),
            "chronological_sorted": r.get("chronological_check", {}).get("sorted"),
        }
        classifications.append(entry)

    # Sort by brier (best first)
    classifications.sort(key=lambda x: x.get("brier") or 99)

    # 4b. Classification counts
    counts = {
        "ML_ACTIVE": sum(1 for c in classifications if c["classification"] == "ML_ACTIVE"),
        "POISSON": sum(1 for c in classifications if c["classification"] == "POISSON"),
        "DEACTIVATED": sum(1 for c in classifications if c["classification"] == "DEACTIVATED"),
        "FAILED": sum(1 for c in classifications if c["classification"] == "FAILED"),
    }

    # 4c. Chronological sort check
    all_sorted = all(
        c.get("chronological_sorted", False)
        for c in classifications
        if c.get("chronological_sorted") is not None
    )

    # 4d. Aggregated market models summary
    market_summary_agg = {}
    models_dir = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"
    for league_id in sorted(all_data.keys()):
        summary_path = models_dir / league_id / "market_models_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                league_market_summary = json.load(f)
            market_summary_agg[league_id] = league_market_summary

    market_totals = {"active": 0, "inactive": 0, "error": 0, "insufficient": 0}
    for lid, markets in market_summary_agg.items():
        for market, info in markets.items():
            st = info.get("status", "")
            if st == "success":
                if info.get("beats_poisson"):
                    market_totals["active"] += 1
                else:
                    market_totals["inactive"] += 1
            elif st == "error":
                market_totals["error"] += 1
            elif st == "insufficient_data":
                market_totals["insufficient"] += 1

    # ──────────────────────────────────────────────────────────
    # 5. Write artifact files
    # ──────────────────────────────────────────────────────────

    # training_summary.json — main artifact
    training_summary = {
        "pipeline_version": "v3.5",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "n_seasons": n_seasons,
        "include_markets": args.include_markets,
        "leagues_requested": league_filter or "ALL",
        "total_leagues_trained": len(results_1x2),
        "total_matches": total_matches,
        "classification_counts": counts,
        "chronological_all_sorted": all_sorted,
        "brier_deactivation_threshold": BRIER_DEACTIVATION_THRESHOLD,
        "market_totals": market_totals,
        "leagues": [],
    }

    for r in results_1x2:
        league_entry = {
            "league_id": r.get("league_id"),
            "status": r.get("status"),
            "n_samples": r.get("n_samples"),
            "n_features": r.get("n_features"),
            "validation": r.get("validation", {}),
            "odds_value_added": r.get("odds_value_added"),
            "market_efficiency_r2": r.get("market_efficiency_r2"),
            "ml_deactivated": r.get("ml_deactivated", False),
            "deactivation_reason": r.get("deactivation_reason"),
            "chronological_check": r.get("chronological_check"),
            "no_odds_variant": r.get("no_odds_variant"),
            "rf_importance_top5": r.get("rf_importance_top5"),
        }

        # Add classification
        cls_entry = next((c for c in classifications if c["league_id"] == r.get("league_id")), {})
        league_entry["classification"] = cls_entry.get("classification", "UNKNOWN")

        training_summary["leagues"].append(league_entry)

    # Write all artifacts
    with open(output_dir / "training_summary.json", "w") as f:
        json.dump(training_summary, f, indent=2, default=str)
    logger.info(f"Saved: training_summary.json")

    with open(output_dir / "league_classifications.json", "w") as f:
        json.dump(classifications, f, indent=2, default=str)
    logger.info(f"Saved: league_classifications.json")

    with open(output_dir / "market_models_summary.json", "w") as f:
        json.dump({
            "totals": market_totals,
            "per_league": market_summary_agg,
        }, f, indent=2, default=str)
    logger.info(f"Saved: market_models_summary.json")

    # Copy per-league metadata from .ml_models into artifacts
    meta_dir = output_dir / "per_league_metadata"
    meta_dir.mkdir(exist_ok=True)
    for league_id in sorted(all_data.keys()):
        src = models_dir / league_id / "metadata.json"
        if src.exists():
            shutil.copy2(src, meta_dir / f"{league_id}_metadata.json")
        # Also copy market summary per league
        src_mkt = models_dir / league_id / "market_models_summary.json"
        if src_mkt.exists():
            shutil.copy2(src_mkt, meta_dir / f"{league_id}_market_summary.json")

    logger.info(f"Saved: per_league_metadata/ ({len(list(meta_dir.iterdir()))} files)")

    # ──────────────────────────────────────────────────────────
    # 6. Print final summary to stdout (for GitHub Actions logs)
    # ──────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 70)
    logger.info("RETRAIN VALIDATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Total leagues:       {len(results_1x2)}")
    logger.info(f"  ML_ACTIVE:           {counts['ML_ACTIVE']}")
    logger.info(f"  POISSON:             {counts['POISSON']}")
    logger.info(f"  DEACTIVATED:         {counts['DEACTIVATED']}")
    logger.info(f"  FAILED:              {counts['FAILED']}")
    logger.info(f"  Chronological:       {'ALL OK' if all_sorted else 'SOME FAILED'}")
    if args.include_markets:
        logger.info(f"  Market models:       {market_totals['active']} active, "
                     f"{market_totals['inactive']} inactive, {market_totals['error']} errors")
    logger.info("")

    header = f"  {'Liga':<22} {'Brier':>7} {'ECE':>7} {'Acc':>6} {'OddsVal':>8} {'MktEff':>7} {'Class':>12}"
    logger.info(header)
    logger.info("  " + "-" * 72)
    for c in classifications:
        b = f"{c['brier']:.4f}" if c['brier'] is not None else "—"
        e = f"{c['ece']:.4f}" if c['ece'] is not None else "—"
        a = f"{c['accuracy']:.4f}" if c['accuracy'] is not None else "—"
        ov = f"{c['odds_value_added']:.4f}" if isinstance(c.get('odds_value_added'), float) else "—"
        me = f"{c['market_efficiency_r2']:.4f}" if isinstance(c.get('market_efficiency_r2'), float) else "—"
        logger.info(f"  {c['league_id']:<22} {b:>7} {e:>7} {a:>6} {ov:>8} {me:>7} {c['classification']:>12}")

    logger.info("")
    logger.info(f"Artifacts saved to: {output_dir}")
    logger.info(f"Log saved to: {log_path}")
    logger.info("Next step: review artifacts, then run ml-retrain-promote workflow.")


if __name__ == "__main__":
    main()
