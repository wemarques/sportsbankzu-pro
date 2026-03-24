"""Tests for Dixon-Coles extensions (#078).

Covers:
- τ(ρ) correction function
- Scoreline matrix with ρ
- Backward compatibility (ρ=0)
- Gamma home advantage helper
- Decay utility functions
"""

import pytest
import math
from unittest.mock import patch

from backend.modeling.poisson_matrix import (
    dixon_coles_tau,
    build_scoreline_matrix,
)
from backend.modeling.lambda_calculator import (
    _get_home_advantage_gamma,
    weighted_average_with_decay,
    half_life_to_weights,
)


class TestDixonColesTau:
    """Tests for the τ(ρ) correction factor."""

    def test_tau_rho_zero_equals_one(self):
        """When ρ=0, τ=1.0 for ALL scorelines (no correction)."""
        lam, mu, rho = 1.5, 1.2, 0.0
        for x in range(5):
            for y in range(5):
                assert dixon_coles_tau(x, y, lam, mu, rho) == 1.0

    def test_tau_negative_rho_increases_draws(self):
        """ρ<0 should increase P(0-0) and P(1-1)."""
        lam, mu = 1.5, 1.2
        rho = -0.10

        # τ(0,0) = 1 - λ*μ*ρ = 1 - 1.5*1.2*(-0.10) = 1 + 0.18 = 1.18
        tau_00 = dixon_coles_tau(0, 0, lam, mu, rho)
        assert tau_00 > 1.0
        assert abs(tau_00 - 1.18) < 0.001

        # τ(1,1) = 1 - ρ = 1 - (-0.10) = 1.10
        tau_11 = dixon_coles_tau(1, 1, lam, mu, rho)
        assert tau_11 > 1.0
        assert abs(tau_11 - 1.10) < 0.001

    def test_tau_only_affects_low_scores(self):
        """τ should only modify scorelines (0,0), (1,0), (0,1), (1,1)."""
        lam, mu, rho = 1.5, 1.2, -0.10

        # High scorelines should return exactly 1.0
        assert dixon_coles_tau(2, 0, lam, mu, rho) == 1.0
        assert dixon_coles_tau(0, 2, lam, mu, rho) == 1.0
        assert dixon_coles_tau(2, 2, lam, mu, rho) == 1.0
        assert dixon_coles_tau(3, 1, lam, mu, rho) == 1.0


class TestScorelineMatrixWithRho:
    """Tests for build_scoreline_matrix with Dixon-Coles ρ."""

    def test_matrix_sums_to_one(self):
        """Matrix should normalize to ~1.0 for all ρ values."""
        for rho in [-0.15, -0.10, -0.05, 0.0]:
            matrix = build_scoreline_matrix(1.5, 1.2, rho=rho)
            total = sum(matrix.values())
            assert abs(total - 1.0) < 0.01, f"ρ={rho}: sum={total}"

    def test_backward_compat_rho_zero(self):
        """Matrix with ρ=0 should be identical to pure independent Poisson."""
        matrix_with_rho = build_scoreline_matrix(1.5, 1.2, rho=0.0)
        matrix_without_rho = build_scoreline_matrix(1.5, 1.2)

        for key in matrix_without_rho:
            assert abs(matrix_with_rho[key] - matrix_without_rho[key]) < 1e-10, (
                f"Scoreline {key}: with_rho={matrix_with_rho[key]}, "
                f"without_rho={matrix_without_rho[key]}"
            )

    def test_negative_rho_boosts_draws(self):
        """ρ<0 should increase draw probabilities relative to ρ=0."""
        matrix_base = build_scoreline_matrix(1.5, 1.2, rho=0.0)
        matrix_dc = build_scoreline_matrix(1.5, 1.2, rho=-0.10)

        # P(0-0) should increase with negative rho
        assert matrix_dc[(0, 0)] > matrix_base[(0, 0)]
        # P(1-1) should increase with negative rho
        assert matrix_dc[(1, 1)] > matrix_base[(1, 1)]


class TestGammaHomeAdvantage:
    """Tests for the _get_home_advantage_gamma helper."""

    def test_gamma_default(self):
        """Unknown league should return 1.0 (no adjustment)."""
        with patch("backend.modeling.lambda_calculator.get_lambda_corrections", return_value={}):
            gamma = _get_home_advantage_gamma("unknown-league-xyz")
            assert gamma == 1.0

    def test_gamma_from_corrections(self):
        """Should read γ from corrections DB."""
        mock_corrections = {
            "home_advantage_gamma": {"value": 1.05}
        }
        with patch("backend.modeling.lambda_calculator.get_lambda_corrections", return_value=mock_corrections):
            gamma = _get_home_advantage_gamma("premier-league")
            assert abs(gamma - 1.05) < 0.001


class TestDecayUtilities:
    """Tests for decay utility functions."""

    def test_decay_infinite_halflife_equals_simple(self):
        """Very large half-life should approximate simple mean."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        simple_mean = sum(values) / len(values)
        decay_mean = weighted_average_with_decay(values, half_life_games=1e7)
        assert abs(decay_mean - simple_mean) < 0.01

    def test_decay_weights_recent_more(self):
        """Recent values should have more weight with finite half-life."""
        # All old values are 1.0, most recent is 10.0
        values = [1.0, 1.0, 1.0, 1.0, 10.0]
        simple_mean = sum(values) / len(values)  # 2.8
        decay_mean = weighted_average_with_decay(values, half_life_games=2.0)

        # Decay mean should be closer to 10.0 (recent) than simple mean
        assert decay_mean > simple_mean

    def test_decay_empty_values(self):
        """Empty values should return 0.0."""
        assert weighted_average_with_decay([]) == 0.0

    def test_half_life_to_weights_range(self):
        """Output weights should be in valid range and sum to 1.0."""
        for hl in [5, 10, 20, 50, 100]:
            for mp in [10, 20, 38]:
                sw, rw = half_life_to_weights(hl, mp)
                assert 0.0 <= sw <= 1.0
                assert 0.0 <= rw <= 1.0
                assert abs(sw + rw - 1.0) < 0.01
