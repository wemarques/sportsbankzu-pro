import math
from backend.services.math_service import implied_probs, poisson_pmf, poisson_cdf

def test_implied_probs_basic():
    h, d, a = implied_probs(2.0, 3.0, 4.0)
    assert round(h, 3) == round(1/2 / (1/2+1/3+1/4) * 100, 3)
    assert round(d, 3) == round(1/3 / (1/2+1/3+1/4) * 100, 3)
    assert round(a, 3) == round(1/4 / (1/2+1/3+1/4) * 100, 3)

def test_poisson_pmf_cdf():
    pmf0 = poisson_pmf(0, 2.5)
    assert pmf0 > 0 and pmf0 < 1
    cdf2 = poisson_cdf(2, 2.5)
    # sanity: cdf should be between 0 and 1 and > pmf0
    assert 0 < cdf2 < 1
    assert cdf2 > pmf0
