#!/usr/bin/env python3
"""Run ML retrain pipeline with realistic synthetic match data.

Generates ~400-1200 matches per league across 3 synthetic seasons,
with realistic goal distributions, odds, and timestamps.
Used for offline pipeline validation when FootyStats API is unavailable.
"""

import json
import logging
import math
import random
import time
from datetime import datetime, timedelta

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# League profiles: (avg_goals_per_match, home_advantage_factor, n_matches_per_season)
LEAGUE_PROFILES = {
    "premier-league":       (2.8, 1.35, 380),
    "championship":         (2.6, 1.25, 552),
    "league-one":           (2.5, 1.20, 552),
    "league-two":           (2.4, 1.20, 552),
    "la-liga":              (2.6, 1.30, 380),
    "segunda-division":     (2.3, 1.20, 462),
    "serie-a":              (2.7, 1.30, 380),
    "serie-b":              (2.4, 1.20, 380),
    "bundesliga":           (3.0, 1.35, 306),
    "2-bundesliga":         (2.7, 1.25, 306),
    "ligue-1":              (2.6, 1.30, 380),
    "ligue-2":              (2.3, 1.20, 380),
    "brasileirao-serie-a":  (2.4, 1.25, 380),
    "brasileirao-serie-b":  (2.2, 1.20, 380),
    "eredivisie":           (3.0, 1.35, 306),
    "primeira-liga":        (2.5, 1.30, 306),
    "super-lig":            (2.7, 1.30, 306),
    "pro-league":           (2.8, 1.25, 240),
    "premiership":          (2.6, 1.30, 228),
    "austrian-bundesliga":  (2.8, 1.25, 182),
    "superliga":            (2.7, 1.25, 182),
    "super-league":         (2.6, 1.25, 180),
    "primera-division":     (2.3, 1.20, 380),
    "a-league":             (2.8, 1.20, 156),
    "professional-league":  (2.7, 1.25, 182),
    "j-league":             (2.6, 1.25, 306),
    "k-league":             (2.5, 1.20, 228),
    "eliteserien":          (2.8, 1.25, 182),
    "allsvenskan":          (2.7, 1.25, 182),
    "uae-pro-league":       (2.6, 1.20, 182),
    "eerste-divisie":       (2.9, 1.20, 342),
    "super-league-greece":  (2.4, 1.30, 240),
    "czech-first-league":   (2.6, 1.30, 240),
    "mls":                  (2.8, 1.20, 374),
    "colombian-primera-a":  (2.2, 1.20, 288),
    "liga-mx":              (2.6, 1.25, 306),
}

TEAM_POOLS = {}
for lid in LEAGUE_PROFILES:
    n_teams = 20
    profile = LEAGUE_PROFILES[lid]
    if profile[2] <= 200:
        n_teams = 12
    elif profile[2] <= 310:
        n_teams = 18
    elif profile[2] <= 400:
        n_teams = 20
    else:
        n_teams = 24
    TEAM_POOLS[lid] = [f"Team_{lid[:3].upper()}_{i+1:02d}" for i in range(n_teams)]


def _poisson_sample(lam):
    """Sample from Poisson distribution."""
    return np.random.poisson(max(lam, 0.1))


def generate_odds(home_prob, draw_prob, away_prob, margin=0.06):
    """Generate realistic decimal odds from true probabilities with bookmaker margin."""
    # Add margin
    total = home_prob + draw_prob + away_prob
    h = home_prob / total * (1 + margin)
    d = draw_prob / total * (1 + margin)
    a = away_prob / total * (1 + margin)

    odds_h = round(1 / h, 2) if h > 0.02 else 50.0
    odds_d = round(1 / d, 2) if d > 0.02 else 50.0
    odds_a = round(1 / a, 2) if a > 0.02 else 50.0
    return odds_h, odds_d, odds_a


def generate_league_matches(league_id, n_seasons=3):
    """Generate synthetic match data for a league."""
    profile = LEAGUE_PROFILES.get(league_id, (2.6, 1.25, 300))
    avg_goals, home_adv, matches_per_season = profile
    teams = TEAM_POOLS[league_id]

    # Team strengths (attack + defense ratings)
    n_teams = len(teams)
    attack_strength = {t: max(0.3, np.random.normal(1.0, 0.25)) for t in teams}
    defense_strength = {t: max(0.3, np.random.normal(1.0, 0.25)) for t in teams}

    all_matches = []
    season_weights = {0: 0.50, 1: 0.33, 2: 0.17}

    for season_idx in range(n_seasons):
        # Season dates: most recent season first in index
        # season_idx 0 = most recent = 2025-26
        # season_idx 1 = 2024-25
        # season_idx 2 = 2023-24
        base_year = 2026 - season_idx
        season_start = datetime(base_year - 1, 8, 15)  # Aug 15

        # Generate round-robin fixtures
        fixtures = []
        for i in range(n_teams):
            for j in range(n_teams):
                if i != j:
                    fixtures.append((teams[i], teams[j]))

        # Limit to matches_per_season
        random.shuffle(fixtures)
        fixtures = fixtures[:matches_per_season]

        for match_idx, (home, away) in enumerate(fixtures):
            # Match date: spread across season (~38 weeks)
            days_offset = int(match_idx / len(fixtures) * 280)
            match_date = season_start + timedelta(days=days_offset)
            date_unix = int(match_date.timestamp())

            # Expected goals based on team strengths
            lambda_home = (avg_goals / 2) * attack_strength[home] / defense_strength[away] * home_adv
            lambda_away = (avg_goals / 2) * attack_strength[away] / defense_strength[home]

            # Clamp
            lambda_home = max(0.3, min(lambda_home, 4.5))
            lambda_away = max(0.2, min(lambda_away, 4.0))

            home_goals = _poisson_sample(lambda_home)
            away_goals = _poisson_sample(lambda_away)
            total_goals = home_goals + away_goals

            # Generate realistic pre-match probabilities (with noise)
            home_prob = 1.0 / (1.0 + 10 ** ((0 - (lambda_home - lambda_away) * 100) / 400))
            away_prob = 1.0 / (1.0 + 10 ** ((0 - (lambda_away - lambda_home) * 100) / 400))
            draw_prob = max(0.15, 1.0 - home_prob - away_prob)
            total_p = home_prob + draw_prob + away_prob
            home_prob /= total_p
            draw_prob /= total_p
            away_prob /= total_p

            odds_h, odds_d, odds_a = generate_odds(home_prob, draw_prob, away_prob)

            # xG with noise
            xg_home = max(0, lambda_home + np.random.normal(0, 0.3))
            xg_away = max(0, lambda_away + np.random.normal(0, 0.3))

            match = {
                "id": f"{league_id}-{season_idx}-{match_idx}",
                "status": "complete",
                "date_unix": date_unix,
                "date": match_date.strftime("%Y-%m-%d %H:%M:%S"),
                "homeTeam": home,
                "awayTeam": away,
                "homeGoalCount": home_goals,
                "awayGoalCount": away_goals,
                "totalGoalCount": total_goals,
                "team_a_xg": round(xg_home, 2),
                "team_b_xg": round(xg_away, 2),
                "team_a_shots": max(1, int(xg_home * 4 + np.random.normal(3, 2))),
                "team_b_shots": max(1, int(xg_away * 4 + np.random.normal(3, 2))),
                "team_a_shotsOnTarget": max(0, int(xg_home * 2 + np.random.normal(1, 1))),
                "team_b_shotsOnTarget": max(0, int(xg_away * 2 + np.random.normal(1, 1))),
                "team_a_corners": max(0, int(np.random.normal(5, 2))),
                "team_b_corners": max(0, int(np.random.normal(4.5, 2))),
                "team_a_possession": round(max(25, min(75, 50 + np.random.normal(0, 8))), 1),
                "team_b_possession": 0,  # will be 100 - home
                "team_a_cards_num": max(0, int(np.random.normal(1.8, 1))),
                "team_b_cards_num": max(0, int(np.random.normal(2.0, 1))),
                "team_a_fouls": max(0, int(np.random.normal(12, 3))),
                "team_b_fouls": max(0, int(np.random.normal(12, 3))),
                "odds_ft_1": odds_h,
                "odds_ft_x": odds_d,
                "odds_ft_2": odds_a,
                "_season_index": season_idx,
                "_season_weight": season_weights.get(season_idx, 0.17),
                "_season_id": f"synth_{league_id}_{base_year}",
            }
            match["team_b_possession"] = round(100 - match["team_a_possession"], 1)
            all_matches.append(match)

        # Drift team strengths slightly between seasons
        for t in teams:
            attack_strength[t] *= np.random.uniform(0.9, 1.1)
            defense_strength[t] *= np.random.uniform(0.9, 1.1)

    return all_matches


def main():
    from backend.ml.train_model import train_all_leagues
    from backend.ml.feature_engineering import build_features_from_matches
    from backend.ml.market_models import train_all_markets
    from backend.ml.historical_data import save_training_data

    logger.info("=" * 70)
    logger.info("RETRAIN PIPELINE — Synthetic Data Mode")
    logger.info("=" * 70)

    # 1. Generate data
    np.random.seed(42)
    random.seed(42)
    all_data = {}
    for league_id in LEAGUE_PROFILES:
        matches = generate_league_matches(league_id, n_seasons=3)
        all_data[league_id] = matches
        logger.info(f"Generated {len(matches)} matches for {league_id}")

    # 2. Save raw data
    path = save_training_data(all_data, filename="training_data_synthetic.json")
    logger.info(f"Saved synthetic data to {path}")

    # 3. Train 1X2 models
    logger.info("=" * 70)
    logger.info("Training 1X2 models...")
    logger.info("=" * 70)
    results = train_all_leagues(all_data, validate=True)

    # 4. Train market models
    logger.info("=" * 70)
    logger.info("Training Over/Under + BTTS models...")
    logger.info("=" * 70)
    market_count = 0
    for league_id, matches in all_data.items():
        try:
            X, y, feature_names, _ts = build_features_from_matches(matches, league_id)
            if len(y) > 0:
                weights = np.ones(len(y), dtype=np.float64)
                train_all_markets(X, matches, weights, feature_names, league_id)
                market_count += 1
        except Exception as e:
            logger.warning(f"Market model training failed for {league_id}: {e}")
    logger.info(f"Market models trained for {market_count} leagues")

    # 5. Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("RETRAIN SUMMARY")
    logger.info("=" * 70)

    success = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") != "success"]

    header = (
        f"{'League':<22} {'Brier':>7} {'ECE':>7} {'Acc%':>6} "
        f"{'OddsVal':>8} {'MktEff':>7} {'Sorted':>6} {'Status':>12}"
    )
    logger.info(header)
    logger.info("-" * 80)

    for r in sorted(success, key=lambda x: x.get("validation", {}).get("avg_brier", 99)):
        val = r.get("validation", {})
        brier = val.get("avg_brier", "?")
        ece = val.get("avg_ece", "?")
        acc = val.get("avg_accuracy", "?")
        odds_v = r.get("odds_value_added", "-")
        mkt_eff = r.get("market_efficiency_r2", "-")
        chrono = r.get("chronological_check", {})
        sorted_ok = chrono.get("sorted", "?")
        deact = r.get("ml_deactivated", False)

        if deact:
            status = "DEACTIVATED"
        elif isinstance(brier, float) and brier < 0.60:
            status = "ML_ACTIVE"
        else:
            status = "POISSON"

        brier_s = f"{brier:.4f}" if isinstance(brier, float) else str(brier)
        ece_s = f"{ece:.4f}" if isinstance(ece, float) else str(ece)
        acc_s = f"{acc:.4f}" if isinstance(acc, float) else str(acc)
        odds_s = f"{odds_v:.4f}" if isinstance(odds_v, float) else str(odds_v)
        mkt_s = f"{mkt_eff:.4f}" if isinstance(mkt_eff, float) else str(mkt_eff)

        logger.info(
            f"  {r['league_id']:<20} {brier_s:>7} {ece_s:>7} "
            f"{acc_s:>6} {odds_s:>8} {mkt_s:>7} {str(sorted_ok):>6} {status:>12}"
        )

    for r in failed:
        logger.info(
            f"  {r.get('league_id', '?'):<20} {'—':>7} {'—':>7} "
            f"{'—':>6} {'—':>8} {'—':>7} {'—':>6} {r.get('status', '?'):>12}"
        )

    # Counts
    n_active = sum(1 for r in success
                   if not r.get("ml_deactivated") and
                   isinstance(r.get("validation", {}).get("avg_brier"), float) and
                   r["validation"]["avg_brier"] < 0.60)
    n_deact = sum(1 for r in success if r.get("ml_deactivated"))
    n_poisson = len(success) - n_active - n_deact

    logger.info("")
    logger.info(f"Total: {len(success)} trained, {len(failed)} failed/skipped")
    logger.info(f"  ML_ACTIVE: {n_active}")
    logger.info(f"  POISSON:   {n_poisson}")
    logger.info(f"  DEACTIVATED: {n_deact}")

    # Check chronological sort
    all_sorted = all(
        r.get("chronological_check", {}).get("sorted", False)
        for r in success if r.get("chronological_check")
    )
    logger.info(f"  Chronological sorted: {'ALL OK' if all_sorted else 'SOME FAILED'}")

    # Market models summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("MARKET MODELS SUMMARY")
    logger.info("=" * 70)
    logger.info(
        f"{'League':<22} {'Market':<10} {'Brier_ML':>9} {'Brier_P':>9} {'Gate':>18}"
    )
    logger.info("-" * 72)

    import os
    from pathlib import Path
    models_dir = Path(os.getenv("DATA_ROOT", ".")) / ".ml_models"
    for league_id in sorted(LEAGUE_PROFILES.keys()):
        summary_path = models_dir / league_id / "market_models_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
            for market, info in sorted(summary.items()):
                if info.get("status") != "success":
                    continue
                bml = info.get("brier_ml", "?")
                bp = info.get("brier_poisson", "?")
                beats = info.get("beats_poisson", False)
                gate = "BEATS_POISSON" if beats else "WORSE_THAN_POISSON"
                if bp is None:
                    gate = "NO_BENCHMARK"
                bml_s = f"{bml:.4f}" if isinstance(bml, (int, float)) else str(bml)
                bp_s = f"{bp:.4f}" if isinstance(bp, (int, float)) and bp is not None else str(bp)
                logger.info(
                    f"  {league_id:<20} {market:<10} {bml_s:>9} {bp_s:>9} {gate:>18}"
                )


if __name__ == "__main__":
    main()
