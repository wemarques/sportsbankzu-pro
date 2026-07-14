"""
#186 — Display-stats invariants for the fixtures payload.

Guards the three contracts the production payload must always satisfy
(verified against the 2026-07-14 Série B diagnostic):

1. Lambda identity: lambdaTotal == lambdaHome + lambdaAway (tol ≤ 0.001)
2. Complement: over_x + under_x == 100 for every O/U display line
3. Monotonicity: Over 0.5 ≥ Over 1.5 ≥ ... ≥ Over 4.5 even when FootyStats
   pre-match potentials and Poisson fallbacks are mixed in the same ladder
"""

import math
import pytest

from backend.services.fixtures_service import compute_ou_stats, lambda_stats_block
from backend.services.math_service import poisson_cdf


# ──────────────────────────────────────────────
# 1. Lambda identity (Finding 2 do diagnóstico)
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
# 2/3. O/U ladder: complement + monotonicity
# ──────────────────────────────────────────────

_OU_LINES = ("15", "25", "35", "45")


def _assert_complement(fields: dict):
    for line in _OU_LINES:
        total = fields[f"over{line}Prob"] + fields[f"under{line}Prob"]
        assert math.isclose(total, 100.0, abs_tol=0.11), (
            f"over{line}+under{line} = {total} != 100"
        )


def _assert_monotonic(fields: dict):
    ladder = [fields[f"over{line}Prob"] for line in ("05", "15", "25", "35", "45")]
    assert ladder == sorted(ladder, reverse=True), f"O/U ladder not monotonic: {ladder}"


class TestComputeOuStats:

    def test_pure_poisson_fallback(self):
        lam = 2.0
        fields, clamped = compute_ou_stats(lam)
        assert clamped is False
        expected_over25 = round((1.0 - poisson_cdf(2, lam)) * 100.0, 1)
        assert fields["over25Prob"] == expected_over25
        _assert_complement(fields)
        _assert_monotonic(fields)

    def test_footystats_potentials_take_precedence(self):
        fields, clamped = compute_ou_stats(
            2.0, over15_pct=68.0, over25_pct=46.0, over35_pct=25.0, over45_pct=11.0
        )
        assert clamped is False
        assert fields["over25Prob"] == 46.0
        assert fields["under25Prob"] == 54.0
        _assert_complement(fields)
        _assert_monotonic(fields)

    def test_incoherent_potentials_are_clamped(self):
        # over35 potential absurdly above over25 → must clamp to keep the ladder coherent
        fields, clamped = compute_ou_stats(2.0, over25_pct=40.0, over35_pct=80.0)
        assert clamped is True
        assert fields["over35Prob"] <= fields["over25Prob"]
        _assert_complement(fields)
        _assert_monotonic(fields)

    def test_mixed_sources_stay_monotonic(self):
        # Potentials for 1.5/2.5/3.5, Poisson for 0.5/4.5 (the common production mix)
        lam_deflated = 1.75
        fields, _ = compute_ou_stats(
            lam_deflated, over15_pct=70.0, over25_pct=45.0, over35_pct=22.0
        )
        _assert_complement(fields)
        _assert_monotonic(fields)

    def test_poisson_over45_cannot_exceed_potential_over35(self):
        # High lambda + low FootyStats over35 potential: Poisson over45 would cross it
        fields, clamped = compute_ou_stats(4.0, over35_pct=20.0)
        assert fields["over45Prob"] <= fields["over35Prob"]
        assert clamped is True
        _assert_complement(fields)

    def test_values_bounded_0_100(self):
        fields, _ = compute_ou_stats(0.0)
        for key, value in fields.items():
            assert 0.0 <= value <= 100.0, f"{key}={value} out of [0, 100]"
