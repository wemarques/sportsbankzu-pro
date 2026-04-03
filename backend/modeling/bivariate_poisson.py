"""Bivariate Poisson model (Karlis & Ntzoufras, 2003) — #107c.

Feature flag OFF — not integrated in pipeline yet.
Provides bivariate_poisson_pmf() for future use when Dixon-Coles rho
is validated in production.

When lambda3=0, reduces to independent double Poisson (current model).
"""

from math import exp, factorial, comb
from typing import List

# Feature flag — set True to activate in pipeline
USE_BIVARIATE_POISSON = False


def bivariate_poisson_pmf(
    x: int, y: int, lambda1: float, lambda2: float, lambda3: float = 0.0
) -> float:
    """Bivariate Poisson PMF.

    Args:
        x: home goals
        y: away goals
        lambda1: home attack rate (marginal - lambda3)
        lambda2: away attack rate (marginal - lambda3)
        lambda3: covariance parameter (>=0). When 0, independent Poisson.

    Returns:
        P(X=x, Y=y)
    """
    if lambda3 == 0 or lambda3 < 0:
        from scipy.stats import poisson
        return float(poisson.pmf(x, lambda1) * poisson.pmf(y, lambda2))

    mu1 = lambda1 - lambda3
    mu2 = lambda2 - lambda3
    if mu1 <= 0 or mu2 <= 0:
        from scipy.stats import poisson
        return float(poisson.pmf(x, lambda1) * poisson.pmf(y, lambda2))

    total = 0.0
    for k in range(min(x, y) + 1):
        total += comb(x, k) * comb(y, k) * factorial(k) * (lambda3 ** k) / (mu1 ** k * mu2 ** k)

    from scipy.stats import poisson
    return float(exp(-lambda3) * poisson.pmf(x, mu1) * poisson.pmf(y, mu2) * total)


def build_bivariate_matrix(
    lambda1: float, lambda2: float, lambda3: float = 0.0, max_goals: int = 8
) -> List[List[float]]:
    """Build scoreline probability matrix using bivariate Poisson."""
    matrix = []
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            row.append(bivariate_poisson_pmf(i, j, lambda1, lambda2, lambda3))
        matrix.append(row)

    # Renormalize
    total = sum(sum(row) for row in matrix)
    if total > 0 and abs(total - 1.0) > 0.001:
        matrix = [[cell / total for cell in row] for row in matrix]

    return matrix
