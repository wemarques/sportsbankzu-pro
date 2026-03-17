"""
Poisson Scoreline Matrix (Layer 2 — Predictive Engine)

Generates a full scoreline probability matrix from lambda_home / lambda_away,
then derives all goal-based markets from the matrix:
- 1X2
- Over/Under (1.5, 2.5, 3.5, 4.5)
- BTTS
- Double Chance (1X, 12, X2)

This ensures all markets are mathematically consistent and derived from the
same underlying model, rather than computed independently.
"""

import logging
from typing import Dict, Tuple
from backend.services.math_service import poisson_pmf

logger = logging.getLogger("sportsbankzu.poisson_matrix")

# Maximum scoreline to consider (0..MAX_GOALS for each team)
MAX_GOALS = 8


def build_scoreline_matrix(
    lambda_home: float,
    lambda_away: float,
) -> Dict[Tuple[int, int], float]:
    """Build a full scoreline probability matrix.

    Returns dict mapping (home_goals, away_goals) -> probability.
    """
    matrix: Dict[Tuple[int, int], float] = {}
    total = 0.0

    for h in range(MAX_GOALS + 1):
        ph = poisson_pmf(h, lambda_home)
        for a in range(MAX_GOALS + 1):
            pa = poisson_pmf(a, lambda_away)
            prob = ph * pa
            matrix[(h, a)] = prob
            total += prob

    # Normalize to ensure sum = 1.0
    if total > 0 and abs(total - 1.0) > 0.001:
        for key in matrix:
            matrix[key] /= total

    return matrix


def derive_1x2(matrix: Dict[Tuple[int, int], float]) -> Dict[str, float]:
    """Derive 1X2 probabilities from scoreline matrix.

    Returns {"home": p, "draw": p, "away": p} in 0-1 scale.
    """
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for (h, a), prob in matrix.items():
        if h > a:
            home_win += prob
        elif h == a:
            draw += prob
        else:
            away_win += prob

    return {"home": home_win, "draw": draw, "away": away_win}


def derive_over_under(matrix: Dict[Tuple[int, int], float]) -> Dict[str, float]:
    """Derive Over/Under probabilities from scoreline matrix.

    Returns {"over_1.5": p, "under_1.5": p, "over_2.5": p, ...} in 0-1 scale.
    """
    thresholds = [0.5, 1.5, 2.5, 3.5, 4.5]
    result = {}

    for threshold in thresholds:
        over = 0.0
        for (h, a), prob in matrix.items():
            if h + a > threshold:
                over += prob
        under = 1.0 - over
        result[f"over_{threshold}"] = over
        result[f"under_{threshold}"] = under

    return result


def derive_btts(matrix: Dict[Tuple[int, int], float]) -> Dict[str, float]:
    """Derive BTTS probabilities from scoreline matrix.

    Returns {"btts_yes": p, "btts_no": p} in 0-1 scale.
    """
    btts_yes = 0.0
    for (h, a), prob in matrix.items():
        if h >= 1 and a >= 1:
            btts_yes += prob

    return {"btts_yes": btts_yes, "btts_no": 1.0 - btts_yes}


def derive_double_chance(x1x2: Dict[str, float]) -> Dict[str, float]:
    """Derive Double Chance from 1X2 probabilities.

    Returns {"dc_1x": p, "dc_12": p, "dc_x2": p} in 0-1 scale.
    """
    return {
        "dc_1x": x1x2["home"] + x1x2["draw"],
        "dc_12": x1x2["home"] + x1x2["away"],
        "dc_x2": x1x2["draw"] + x1x2["away"],
    }


def derive_all_markets(
    lambda_home: float,
    lambda_away: float,
) -> Dict[str, float]:
    """Derive all goal-based market probabilities from lambdas.

    Returns a flat dict with all derived probabilities (0-1 scale).
    """
    matrix = build_scoreline_matrix(lambda_home, lambda_away)
    x1x2 = derive_1x2(matrix)
    ou = derive_over_under(matrix)
    btts = derive_btts(matrix)
    dc = derive_double_chance(x1x2)

    result = {
        # 1X2
        "homeWinProb": x1x2["home"],
        "drawProb": x1x2["draw"],
        "awayWinProb": x1x2["away"],
        # Over/Under
        "over05Prob": ou["over_0.5"],
        "over15Prob": ou["over_1.5"],
        "over25Prob": ou["over_2.5"],
        "over35Prob": ou["over_3.5"],
        "over45Prob": ou["over_4.5"],
        "under15Prob": ou["under_1.5"],
        "under25Prob": ou["under_2.5"],
        "under35Prob": ou["under_3.5"],
        "under45Prob": ou["under_4.5"],
        # BTTS
        "bttsProb": btts["btts_yes"],
        "bttsNoProb": btts["btts_no"],
        # Double Chance
        "dc1xProb": dc["dc_1x"],
        "dc12Prob": dc["dc_12"],
        "dcx2Prob": dc["dc_x2"],
        # Expected goals
        "expectedGoals": lambda_home + lambda_away,
    }

    logger.debug(
        f"Poisson matrix derived: λH={lambda_home:.2f} λA={lambda_away:.2f} → "
        f"1X2=({x1x2['home']:.2f}/{x1x2['draw']:.2f}/{x1x2['away']:.2f}) "
        f"O2.5={ou['over_2.5']:.2f} BTTS={btts['btts_yes']:.2f}"
    )

    return result
