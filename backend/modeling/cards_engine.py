"""Cards projection engine v3 — Dixon-Coles relative strengths (#086).

Fix double-counting from v2 (#085b): homeCardsPerMatch already embeds
league discipline and foul profile. Applying league_discipline_factor
and foul_adjustment on top counted the same effect 2-3x (pattern #053).

Model: lambda = league_avg/2 * home_relative + league_avg/2 * away_relative
where home_relative = homeCardsPerMatch / league_avg (ratio vs league baseline).

Only legitimate external adjustment: referee_factor (not embedded in
team cardsPerMatch stats).

Reference: Titman, Costain, Ridall & Gregory (2015), JRSS-A.
"""

import logging
import math
from typing import Optional, Tuple

logger = logging.getLogger("sportsbankzu.cards_engine")

# Card lines for betting markets
CARD_LINES = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]  # #110: expanded

# Default cards lambda when data is unavailable
DEFAULT_CARDS_LAMBDA = 4.0  # ~4 cards per match is typical
DEFAULT_OVERDISPERSION = 1.3  # literature indicates 1.2-1.5 for cards

# Try scipy for NB2; fall back to pure Poisson if unavailable
try:
    from scipy.stats import nbinom as _nbinom, poisson as _poisson
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


def _poisson_cdf(k: int, lam: float) -> float:
    """Pure-Python Poisson CDF: P(X <= k)."""
    if lam <= 0:
        return 1.0
    total = 0.0
    for i in range(k + 1):
        total += math.exp(-lam) * (lam ** i) / math.factorial(i)
    return min(total, 1.0)


def predict_cards(
    home_stats: dict,
    away_stats: dict,
    league_id: str = "",
    league_stats: Optional[dict] = None,
    referee_avg_cards: Optional[float] = None,
) -> dict:
    """Project total cards with NB2 + Dixon-Coles relative strengths.

    Returns dict with projected_total_cards, lambda components,
    overdispersion, model_source, adjustments, and line probabilities.
    """
    # Step 1: League average as baseline
    league_avg = _get_league_avg_cards(league_stats)

    # Step 2: Relative strengths vs league (Dixon-Coles pattern #053)
    lambda_home, lambda_away = _compute_relative_lambda(
        home_stats, away_stats, league_avg
    )
    lambda_raw = lambda_home + lambda_away

    # #124: Cross-estimate with cardsAgainst (opponent cards drawn)
    home_cards_against = _safe_float(home_stats.get("homeCardsAgainstPerMatch",
                         home_stats.get("cardsAgainstAVG_home",
                         home_stats.get("cards_against_per_match"))))
    away_cards_against = _safe_float(away_stats.get("awayCardsAgainstPerMatch",
                         away_stats.get("cardsAgainstAVG_away",
                         away_stats.get("cards_against_per_match"))))
    if home_cards_against is not None and away_cards_against is not None:
        # Cross: home_for + away_against + away_for + home_against / 2
        home_for = lambda_home
        away_for = lambda_away
        cross = (home_for + away_cards_against / 2 + away_for + home_cards_against / 2) / 2
        lambda_raw = 0.6 * lambda_raw + 0.4 * cross

    # Step 3: Referee factor — ONLY legitimate external adjustment
    # Referee is NOT embedded in cardsPerMatch (which is team average)
    referee_factor = _compute_referee_factor(referee_avg_cards, league_avg)

    # Step 4: Per-league calibrated multiplier (#052-#056)
    cards_multiplier = _get_cards_multiplier(league_id)

    # Final lambda — NO foul_adjustment, NO league_discipline_factor
    # (both already embedded in cardsPerMatch and league_avg)
    lambda_adjusted = lambda_raw * referee_factor * cards_multiplier

    # Step 5: Estimate overdispersion
    overdispersion = _estimate_overdispersion(home_stats, away_stats, league_stats)

    # Step 6: Compute probabilities per line (NB2 or Poisson fallback)
    lines = {}
    model_source = "nb2"

    for line in CARD_LINES:
        k_max = int(line)  # 3.5 -> 3

        if _HAS_SCIPY and overdispersion > 1.01:
            # NB2: n = lambda^2 / (var - lambda), p = lambda / var
            var = lambda_adjusted * overdispersion
            n_param = (lambda_adjusted ** 2) / (var - lambda_adjusted) if var > lambda_adjusted else 100
            p_param = lambda_adjusted / var if var > 0 else 0.5
            n_param = max(n_param, 0.5)  # safety floor

            p_under = float(_nbinom.cdf(k_max, n_param, p_param))
            model_source = "nb2"
        else:
            # Poisson fallback
            if _HAS_SCIPY:
                p_under = float(_poisson.cdf(k_max, lambda_adjusted))
            else:
                p_under = _poisson_cdf(k_max, lambda_adjusted)
            model_source = "poisson_fallback"

        p_over = 1.0 - p_under

        lines[f"over_{line}"] = {
            "prob": round(p_over, 4),
            "prob_pct": round(p_over * 100, 1),
        }
        lines[f"under_{line}"] = {
            "prob": round(p_under, 4),
            "prob_pct": round(p_under * 100, 1),
        }

    return {
        "projected_total_cards": round(lambda_adjusted, 1),
        "cards_lambda": round(lambda_adjusted, 3),
        "cards_lambda_raw": round(lambda_raw, 3),
        "cards_lambda_home": round(lambda_home * referee_factor * cards_multiplier, 3),
        "cards_lambda_away": round(lambda_away * referee_factor * cards_multiplier, 3),
        "cards_multiplier": cards_multiplier,
        "overdispersion": round(overdispersion, 3),
        "model_source": model_source,
        "adjustments": {
            "referee_factor": round(referee_factor, 3),
        },
        "lines": lines,
    }


def _get_league_avg_cards(league_stats: Optional[dict]) -> float:
    """Extract league average cards per match (total, both teams)."""
    if league_stats:
        lg = _safe_float(league_stats.get("cardsAVG_overall",
             league_stats.get("league_cards_avg",
             league_stats.get("avg_cards",
             league_stats.get("average_cards_per_match")))))
        if lg is not None and lg > 0:
            return lg
    return DEFAULT_CARDS_LAMBDA


def _compute_relative_lambda(
    home_stats: dict, away_stats: dict, league_avg: float
) -> Tuple[float, float]:
    """Compute lambda via Dixon-Coles relative strengths.

    Each team's cardsPerMatch is compared to the league average.
    The relative strength (ratio) is applied to half the league baseline.

    This avoids double-counting: cardsPerMatch already embeds league
    discipline and foul profile (#086, pattern #053).
    """
    half_league = league_avg / 2.0

    # Try per-venue stats first (most specific)
    home_cards = _safe_float(home_stats.get("homeCardsPerMatch",
                 home_stats.get("cardsAVG_home",
                 home_stats.get("cardsPerMatch",
                 home_stats.get("cardsAVG_overall")))))

    away_cards = _safe_float(away_stats.get("awayCardsPerMatch",
                 away_stats.get("cardsAVG_away",
                 away_stats.get("cardsPerMatch",
                 away_stats.get("cardsAVG_overall")))))

    # Relative strengths vs league avg per team (half of total)
    if home_cards is not None and half_league > 0:
        home_relative = home_cards / half_league
    else:
        home_relative = 1.0  # no data → assume league average

    if away_cards is not None and half_league > 0:
        away_relative = away_cards / half_league
    else:
        away_relative = 1.0

    lambda_home = half_league * home_relative
    lambda_away = half_league * away_relative
    return lambda_home, lambda_away


def _compute_referee_factor(
    referee_avg_cards: Optional[float], league_avg: float
) -> float:
    """Referee adjustment factor — ONLY legitimate external adjustment.

    Referee is NOT embedded in team cardsPerMatch (which is team average
    across all referees). A strict referee shifts lambda proportionally.
    """
    if referee_avg_cards is None:
        return 1.0

    if league_avg <= 0:
        league_avg = DEFAULT_CARDS_LAMBDA

    # Ratio referee vs league, capped +/-30%
    ratio = referee_avg_cards / league_avg
    return max(0.70, min(1.30, ratio))


def _estimate_overdispersion(
    home_stats: dict, away_stats: dict, league_stats: Optional[dict]
) -> float:
    """Estimate overdispersion (variance/mean) for NB2.

    If variance data available, compute directly.
    Otherwise, use conservative default of 1.3 (literature: 1.2-1.5 for cards).
    """
    # Try to estimate from data variance
    home_var = _safe_float(home_stats.get("cardsVariance",
               home_stats.get("cards_variance")))
    home_mean = _safe_float(home_stats.get("cardsPerMatch",
                home_stats.get("cardsAVG_overall")))

    if home_var is not None and home_mean is not None and home_mean > 0:
        return max(1.0, home_var / home_mean)

    # League level
    if league_stats:
        lg_var = _safe_float(league_stats.get("cardsVariance"))
        lg_mean = _safe_float(league_stats.get("cardsAVG_overall"))
        if lg_var is not None and lg_mean is not None and lg_mean > 0:
            return max(1.0, lg_var / lg_mean)

    return DEFAULT_OVERDISPERSION


def _get_cards_multiplier(league_id: str) -> float:
    """Fetch calibrated cards_multiplier from corrections DB."""
    if not league_id:
        return 1.0
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        val = corrections.get("cards_multiplier", {})
        if isinstance(val, dict):
            return float(val.get("value", 1.0))
        return float(val) if val else 1.0
    except Exception:
        return 1.0


def _safe_float(val) -> Optional[float]:
    """Safely convert to float."""
    if val is None or val == "N/A" or val == -1:
        return None
    try:
        v = float(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None
