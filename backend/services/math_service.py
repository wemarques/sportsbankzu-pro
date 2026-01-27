from typing import Optional, Tuple
import math

def implied_probs(home: Optional[float], draw: Optional[float], away: Optional[float]) -> Tuple[float, float, float]:
    vals = []
    for o in (home, draw, away):
        if o and o > 1:
            vals.append(1.0 / o)
        else:
            vals.append(0.0)
    total = sum(vals)
    if total <= 0:
        return 0.0, 0.0, 0.0
    return (vals[0] / total * 100.0, vals[1] / total * 100.0, vals[2] / total * 100.0)

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except Exception:
        return 0.0

def poisson_cdf(k: int, lam: float) -> float:
    s = 0.0
    for i in range(0, k + 1):
        s += poisson_pmf(i, lam)
    return s
