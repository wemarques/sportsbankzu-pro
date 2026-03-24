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

# Default Dixon-Coles rho (negative = draws more likely than independent Poisson)
_DEFAULT_RHO = -0.10


def dixon_coles_tau(x: int, y: int, lambda_: float, mu: float, rho: float) -> float:
    """Dixon-Coles τ correction for low-scoring results (1997, section 3).

    Adjusts P(0-0), P(1-0), P(0-1), P(1-1) to account for correlation
    between home and away goals that independent Poisson ignores.

    Args:
        x: home goals
        y: away goals
        lambda_: expected home goals (λ)
        mu: expected away goals (μ)
        rho: dependence parameter (typically -0.15 to 0)

    Returns:
        Multiplicative correction factor τ(x, y, λ, μ, ρ).
        For scorelines other than (0,0), (1,0), (0,1), (1,1) returns 1.0.
    """
    if x == 0 and y == 0:
        return 1 - lambda_ * mu * rho
    elif x == 0 and y == 1:
        return 1 + lambda_ * rho
    elif x == 1 and y == 0:
        return 1 + mu * rho
    elif x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _get_rho(league_id: str | None) -> float:
    """Get calibrated ρ for a league from the corrections DB.

    Falls back to _DEFAULT_RHO if no calibration exists.
    """
    if not league_id:
        return _DEFAULT_RHO
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        rho_corr = corrections.get("rho")
        if rho_corr:
            return float(rho_corr.get("value", _DEFAULT_RHO))
    except Exception:
        pass
    return _DEFAULT_RHO


# ─── Lambda Deflation — Per-League from Calibration DB (#052) ───
# Uniform deflation (#043) replaced by per-league factors from calibration.
# Default: 1.0 (no deflation) when no calibration exists for a league.
_DEFAULT_OU_DEFLATION = 1.0
_DEFAULT_BTTS_DEFLATION = 1.0
_DEFAULT_1X2_DEFLATION = 1.0


def _get_league_deflation(league_id: str | None) -> tuple[float, float, float]:
    """Get per-league deflation factors from calibration DB.

    Returns (ou_deflation, btts_deflation, x1x2_deflation).
    Falls back to 1.0 (no deflation) if no calibration exists.
    """
    if not league_id:
        return (_DEFAULT_OU_DEFLATION, _DEFAULT_BTTS_DEFLATION, _DEFAULT_1X2_DEFLATION)
    try:
        from backend.modeling.lambda_calculator import get_lambda_corrections
        corrections = get_lambda_corrections(league_id)
        ou = float(corrections.get("lambda_multiplier", {}).get("value", _DEFAULT_OU_DEFLATION))
        btts = float(corrections.get("btts_multiplier", {}).get("value", _DEFAULT_BTTS_DEFLATION))
        x1x2 = float(corrections.get("1x2_multiplier", {}).get("value", _DEFAULT_1X2_DEFLATION))
        return (ou, btts, x1x2)
    except Exception:
        return (_DEFAULT_OU_DEFLATION, _DEFAULT_BTTS_DEFLATION, _DEFAULT_1X2_DEFLATION)


def build_scoreline_matrix(
    lambda_home: float,
    lambda_away: float,
    rho: float = 0.0,
) -> Dict[Tuple[int, int], float]:
    """Build a full scoreline probability matrix.

    When rho != 0, applies Dixon-Coles τ correction to low-scoring results.
    With rho=0.0 (default), τ=1.0 for all scorelines → identical to pure
    independent Poisson (backward compatible).

    Args:
        lambda_home: expected home goals
        lambda_away: expected away goals
        rho: Dixon-Coles dependence parameter (typically -0.15 to 0)

    Returns dict mapping (home_goals, away_goals) -> probability.
    """
    matrix: Dict[Tuple[int, int], float] = {}
    total = 0.0

    for h in range(MAX_GOALS + 1):
        ph = poisson_pmf(h, lambda_home)
        for a in range(MAX_GOALS + 1):
            pa = poisson_pmf(a, lambda_away)
            tau = dixon_coles_tau(h, a, lambda_home, lambda_away, rho)
            prob = tau * ph * pa
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
    league_id: str = "",
) -> Dict[str, float]:
    """Derive all goal-based market probabilities from lambdas.

    Returns a flat dict with all derived probabilities (0-1 scale).

    Uses per-league deflated lambdas for Over/Under and BTTS (#052).
    1X2 and Double Chance use original lambdas.
    """
    ou_defl, btts_defl, x1x2_defl = _get_league_deflation(league_id)
    rho = _get_rho(league_id)

    # 1X2 / Double Chance: per-league 1X2 deflation (#055) + Dixon-Coles τ (#078)
    lh_1x2 = lambda_home * x1x2_defl
    la_1x2 = lambda_away * x1x2_defl
    matrix_1x2 = build_scoreline_matrix(lh_1x2, la_1x2, rho=rho)
    x1x2 = derive_1x2(matrix_1x2)
    dc = derive_double_chance(x1x2)

    # Over/Under: per-league deflated lambdas + Dixon-Coles τ (#078)
    lh_ou = lambda_home * ou_defl
    la_ou = lambda_away * ou_defl
    matrix_ou = build_scoreline_matrix(lh_ou, la_ou, rho=rho)
    ou = derive_over_under(matrix_ou)

    # BTTS: per-league deflation + Dixon-Coles τ (#078)
    lh_btts = lambda_home * btts_defl
    la_btts = lambda_away * btts_defl
    matrix_btts = build_scoreline_matrix(lh_btts, la_btts, rho=rho)
    btts = derive_btts(matrix_btts)

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
        f"Poisson matrix derived: λH={lambda_home:.2f} λA={lambda_away:.2f} "
        f"(O/U={lh_ou:.2f}/{la_ou:.2f}, BTTS={lh_btts:.2f}/{la_btts:.2f}, "
        f"1X2={lh_1x2:.2f}/{la_1x2:.2f}, ρ={rho:.3f}) → "
        f"1X2=({x1x2['home']:.2f}/{x1x2['draw']:.2f}/{x1x2['away']:.2f}) "
        f"O2.5={ou['over_2.5']:.2f} BTTS={btts['btts_yes']:.2f}"
    )

    return result
