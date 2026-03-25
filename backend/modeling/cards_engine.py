"""Cards projection engine v2 — NB2 + covariates (#085b).

Upgrade from Poisson (#085) to Negative Binomial (NB2) with:
- Lambda split home/away (visitor asymmetry — away team receives more cards)
- Foul/match adjustment (covariate with high card correlation)
- League discipline profile (league avg cards as baseline)
- Referee factor (when available via API-Football)
- Overdispersion via NB2 (variance > mean, documented in Titman 2015)

Reference: Titman, Costain, Ridall & Gregory (2015), JRSS-A.
"""

import logging
import math
from typing import Optional, Tuple

logger = logging.getLogger("sportsbankzu.cards_engine")

# Card lines for betting markets
CARD_LINES = [2.5, 3.5, 4.5, 5.5]

# Default cards lambda when data is unavailable
DEFAULT_CARDS_LAMBDA = 4.0  # ~4 cards per match is typical
DEFAULT_OVERDISPERSION = 1.3  # literature indicates 1.2-1.5 for cards

# Home/away card share asymmetry: visitors receive ~10-15% more cards
HOME_CARD_SHARE = 0.45
AWAY_CARD_SHARE = 0.55

# Foul elasticity: each foul/match above league average adjusts lambda
FOUL_CARD_ELASTICITY = 0.06  # +6% lambda per foul/match above average

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
    """Project total cards with NB2 + covariates.

    Returns dict with projected_total_cards, lambda components,
    overdispersion, model_source, adjustments, and line probabilities.
    """
    # Step 1: Estimate split lambda (home/away)
    lambda_home, lambda_away = _estimate_split_lambda(
        home_stats, away_stats, league_stats
    )
    lambda_raw = lambda_home + lambda_away

    # Step 2: Foul adjustment (covariate)
    foul_adj = _compute_foul_adjustment(home_stats, away_stats, league_stats)

    # Step 3: Referee factor
    referee_factor = _compute_referee_factor(referee_avg_cards, league_stats)

    # Step 4: League discipline profile
    league_disc = _compute_league_discipline_factor(league_stats)

    # Step 5: Per-league calibrated multiplier (#052-#056)
    cards_multiplier = _get_cards_multiplier(league_id)

    # Final composed lambda
    lambda_adjusted = lambda_raw * foul_adj * referee_factor * league_disc * cards_multiplier

    # Step 6: Estimate overdispersion
    overdispersion = _estimate_overdispersion(home_stats, away_stats, league_stats)

    # Step 7: Compute probabilities per line (NB2 or Poisson fallback)
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
        "cards_lambda_home": round(
            lambda_home * foul_adj * referee_factor * league_disc * cards_multiplier, 3
        ),
        "cards_lambda_away": round(
            lambda_away * foul_adj * referee_factor * league_disc * cards_multiplier, 3
        ),
        "cards_multiplier": cards_multiplier,
        "overdispersion": round(overdispersion, 3),
        "model_source": model_source,
        "adjustments": {
            "foul_adjustment": round(foul_adj, 3),
            "referee_factor": round(referee_factor, 3),
            "league_discipline_factor": round(league_disc, 3),
        },
        "lines": lines,
    }


def _estimate_split_lambda(
    home_stats: dict, away_stats: dict, league_stats: Optional[dict]
) -> Tuple[float, float]:
    """Estimate cards lambda SPLIT for home and away.

    Visitors receive ~10-15% more cards (documented asymmetry).
    Uses same 3-layer strategy as v1 but with split.
    """
    # Try per-venue stats (best)
    home_cards_home = _safe_float(home_stats.get("homeCardsPerMatch",
                      home_stats.get("cardsAVG_home")))
    away_cards_away = _safe_float(away_stats.get("awayCardsPerMatch",
                      away_stats.get("cardsAVG_away")))

    if home_cards_home is not None and away_cards_away is not None:
        return home_cards_home, away_cards_away

    # Fallback: use overall and apply split
    total_lambda = _estimate_total_lambda(home_stats, away_stats, league_stats)
    return total_lambda * HOME_CARD_SHARE, total_lambda * AWAY_CARD_SHARE


def _estimate_total_lambda(
    home_stats: dict, away_stats: dict, league_stats: Optional[dict]
) -> float:
    """Fallback: estimate total lambda (same logic as v1)."""
    home_overall = _safe_float(home_stats.get("cardsPerMatch",
                   home_stats.get("cardsAVG_overall")))
    away_overall = _safe_float(away_stats.get("cardsPerMatch",
                   away_stats.get("cardsAVG_overall")))

    if home_overall is not None and away_overall is not None:
        return (home_overall + away_overall) / 2
    if home_overall is not None:
        return home_overall
    if away_overall is not None:
        return away_overall

    # League fallback
    if league_stats:
        lg = _safe_float(league_stats.get("cardsAVG_overall",
             league_stats.get("league_cards_avg",
             league_stats.get("avg_cards",
             league_stats.get("average_cards_per_match")))))
        if lg is not None and lg > 0:
            return lg

    return DEFAULT_CARDS_LAMBDA


def _compute_foul_adjustment(
    home_stats: dict, away_stats: dict, league_stats: Optional[dict]
) -> float:
    """Adjustment based on fouls/match above league average.

    Foul-card correlation is strong (~0.6-0.7 in literature).
    """
    league_fouls = 22.0  # default ~22 fouls/match (global average)
    if league_stats:
        lf = _safe_float(league_stats.get("foulsAVG_overall",
             league_stats.get("league_fouls_avg")))
        if lf is not None and lf > 0:
            league_fouls = lf

    home_fouls = _safe_float(home_stats.get("homeTeamFoulsPerMatch",
                 home_stats.get("homeFoulsPerMatch",
                 home_stats.get("foulsPerMatch"))))
    away_fouls = _safe_float(away_stats.get("awayTeamFoulsPerMatch",
                 away_stats.get("awayFoulsPerMatch",
                 away_stats.get("foulsPerMatch"))))

    if home_fouls is None and away_fouls is None:
        return 1.0  # no data, no adjustment

    match_fouls = (home_fouls or league_fouls / 2) + (away_fouls or league_fouls / 2)
    deviation = (match_fouls - league_fouls) / league_fouls if league_fouls > 0 else 0

    # Cap: max +/-25% adjustment from fouls
    adjustment = 1.0 + (deviation * FOUL_CARD_ELASTICITY * 10)
    return max(0.75, min(1.25, adjustment))


def _compute_referee_factor(
    referee_avg_cards: Optional[float], league_stats: Optional[dict]
) -> float:
    """Referee adjustment factor.

    If designated referee has known card average,
    adjusts lambda proportionally vs league average.
    """
    if referee_avg_cards is None:
        return 1.0

    league_avg = DEFAULT_CARDS_LAMBDA
    if league_stats:
        la = _safe_float(league_stats.get("cardsAVG_overall"))
        if la is not None and la > 0:
            league_avg = la

    # Ratio referee vs league, capped +/-30%
    ratio = referee_avg_cards / league_avg if league_avg > 0 else 1.0
    return max(0.70, min(1.30, ratio))


def _compute_league_discipline_factor(league_stats: Optional[dict]) -> float:
    """League discipline profile vs global average.

    More disciplined leagues (e.g. J-League) have fewer cards.
    More aggressive leagues (e.g. Argentina, Turkey) have more.
    """
    if not league_stats:
        return 1.0

    league_cards = _safe_float(league_stats.get("cardsAVG_overall",
                   league_stats.get("league_cards_avg",
                   league_stats.get("avg_cards"))))
    if league_cards is None or league_cards <= 0:
        return 1.0

    # Ratio vs global average (~4.0 cards/match), cap +/-20%
    ratio = league_cards / DEFAULT_CARDS_LAMBDA
    return max(0.80, min(1.20, ratio))


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
    """Fetch calibrated cards_multiplier from corrections DB (kept from v1)."""
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
