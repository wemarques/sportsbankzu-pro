"""
#186/#187 — Display-stats invariants for the fixtures payload.

Critérios de aceite (pedido original, Achados 2 e 4):
1. Lambda identity: lambdaTotal == lambdaHome + lambdaAway (tol ≤ 0.001)
2. Complement: over_x + under_x == 100 for every O/U display line
3. Monotonicity: Over 0.5 ≥ Over 1.5 ≥ ... ≥ Over 4.5
4. #187: overXXProb/underXXProb derive from Poisson on lambdaTotalOU and
   bttsProb derives from the payload lambdas — externally verifiable.
"""

import math
import pytest

from backend.services.fixtures_service import (
    compute_btts_from_lambdas,
    compute_ou_stats,
    lambda_stats_block,
)
from backend.services.math_service import poisson_cdf, poisson_pmf


# ──────────────────────────────────────────────
# 1. Lambda identity (Achado 2 do diagnóstico)
# ──────────────────────────────────────────────


class TestLambdaStatsBlock:

    @pytest.mark.parametrize(
        "lam_home, lam_away",
        [
            (0.833, 1.228),   # América Mineiro x Ceará (diagnóstico 2026-07-14)
            (1.3, 1.0),
            (0.0, 0.0),
            (2.789, 0.411),
            (1.23456, 2.34567),
        ],
    )
    def test_identity_holds_within_rounding(self, lam_home, lam_away):
        block = lambda_stats_block(lam_home, lam_away)
        assert block["lambdaHome"] == round(lam_home, 3)
        assert block["lambdaAway"] == round(lam_away, 3)
        deviation = abs(block["lambdaTotal"] - (block["lambdaHome"] + block["lambdaAway"]))
        assert deviation <= 0.01, f"lambdaTotal identity broken: deviation={deviation}"

    def test_exposes_exactly_the_three_lambda_fields(self):
        block = lambda_stats_block(1.1, 0.9)
        assert set(block.keys()) == {"lambdaHome", "lambdaAway", "lambdaTotal"}


# ──────────────────────────────────────────────
# 2/3/4. O/U ladder: Poisson-derived + complement + monotonicity (#187)
# ──────────────────────────────────────────────

_OU_LINES = ("05", "15", "25", "35", "45")


def _assert_complement(fields: dict):
    for line in _OU_LINES:
        total = fields[f"over{line}Prob"] + fields[f"under{line}Prob"]
        assert math.isclose(total, 100.0, abs_tol=0.11), (
            f"over{line}+under{line} = {total} != 100"
        )


def _assert_monotonic(fields: dict):
    ladder = [fields[f"over{line}Prob"] for line in _OU_LINES]
    assert ladder == sorted(ladder, reverse=True), f"O/U ladder not monotonic: {ladder}"


class TestComputeOuStats:

    @pytest.mark.parametrize("lam", [0.8, 1.75, 2.061, 2.5, 3.297, 4.0])
    def test_ladder_is_pure_poisson_on_lambda(self, lam):
        """#187 acceptance: any consumer can recompute the ladder from the
        exposed lambdaTotalOU — no FootyStats potential mixed in."""
        fields, clamped = compute_ou_stats(lam)
        assert clamped is False
        for k, line in enumerate(_OU_LINES):
            expected = round((1.0 - poisson_cdf(k, lam)) * 100.0, 1)
            assert fields[f"over{line}Prob"] == expected
        _assert_complement(fields)
        _assert_monotonic(fields)

    def test_diagnostic_case_criciuma(self):
        # Criciúma x Vila Nova (diagnóstico): lambdas 2.061 → Poisson over 2.5 ≈ 34%
        fields, _ = compute_ou_stats(2.061)
        expected_over25 = round((1.0 - poisson_cdf(2, 2.061)) * 100.0, 1)
        assert fields["over25Prob"] == expected_over25
        assert 30.0 < fields["over25Prob"] < 40.0

    def test_values_bounded_0_100(self):
        for lam in (0.0, 10.0):
            fields, _ = compute_ou_stats(lam)
            for key, value in fields.items():
                assert 0.0 <= value <= 100.0, f"{key}={value} out of [0, 100]"

    def test_exposes_all_ten_fields(self):
        fields, _ = compute_ou_stats(2.0)
        expected_keys = {f"over{line}Prob" for line in _OU_LINES} | {
            f"under{line}Prob" for line in _OU_LINES
        }
        assert set(fields.keys()) == expected_keys


class TestComputeBttsFromLambdas:

    @pytest.mark.parametrize(
        "lam_home, lam_away",
        [(0.833, 1.228), (1.706, 1.59), (1.0, 1.0), (0.5, 2.5)],
    )
    def test_btts_is_verifiable_from_payload_lambdas(self, lam_home, lam_away):
        """#187 acceptance: bttsProb == (1-P0(λh))(1-P0(λa)) on the displayed lambdas."""
        got = compute_btts_from_lambdas(lam_home, lam_away)
        expected = round(
            (1.0 - poisson_pmf(0, lam_home)) * (1.0 - poisson_pmf(0, lam_away)) * 100.0, 1
        )
        assert got == expected
        assert 0.0 <= got <= 100.0

    def test_zero_lambda_means_no_btts(self):
        assert compute_btts_from_lambdas(0.0, 2.0) == 0.0

    def test_plausible_range_for_typical_lambdas(self):
        # Achado 4: bttsProb do payload deve ser o valor Poisson dos lambdas,
        # não a fusão 40/30/30 (preservada em bttsFusionProb)
        got = compute_btts_from_lambdas(1.1, 1.35)
        assert 45.0 < got < 55.0
