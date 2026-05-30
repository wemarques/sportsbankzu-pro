"""Test #185 — canonical league_id before corrections lookup + observable
silent misses in the SAFE gate and per-league threshold loader.

Bug: _is_safe_enabled / _get_calibrated_threshold looked up the corrections DB
with the RAW league_id. A frontend alias (e.g. 'brazil-serie-a') or mixed case
never matched the canonical calibration key ('brasileirao-serie-a'), so the
lookup silently fell back to defaults — invisibly disabling SAFE and per-league
thresholds for that league.
"""

import logging

from backend.services.ev_classification import (
    _canonical_league,
    _is_safe_enabled,
    _get_calibrated_threshold,
)


# ── _canonical_league ──────────────────────────────────────────────────

def test_canonical_resolves_frontend_alias():
    assert _canonical_league("brazil-serie-a") == "brasileirao-serie-a"


def test_canonical_passes_through_already_canonical():
    assert _canonical_league("brasileirao-serie-a") == "brasileirao-serie-a"


def test_canonical_is_case_and_whitespace_insensitive():
    assert _canonical_league("  Brazil-Serie-A  ") == "brasileirao-serie-a"


def test_canonical_handles_none_and_empty():
    assert _canonical_league(None) is None
    assert _canonical_league("") is None


# ── _is_safe_enabled ───────────────────────────────────────────────────

def test_safe_gate_resolves_alias_before_lookup(monkeypatch):
    """Passing the frontend alias must hit the canonical calibration key."""
    seen = {}

    def fake_corrections(league):
        seen["league"] = league
        return {"safe_enabled": {"value": "1.0"}}

    monkeypatch.setattr(
        "backend.modeling.lambda_calculator.get_lambda_corrections",
        fake_corrections,
    )
    # Without #185 this passed 'brazil-serie-a' and missed the calibration row.
    assert _is_safe_enabled("brazil-serie-a") is True
    assert seen["league"] == "brasileirao-serie-a"


def test_safe_gate_logs_warning_on_missing_corrections(monkeypatch, caplog):
    """Empty corrections (uncalibrated / key mismatch) must be visible, not silent."""
    monkeypatch.setattr(
        "backend.modeling.lambda_calculator.get_lambda_corrections",
        lambda league: {},
    )
    with caplog.at_level(logging.WARNING, logger="sportsbankzu.ev_classification"):
        assert _is_safe_enabled("brasileirao-serie-a") is False
    assert any("no corrections for league" in r.message for r in caplog.records)


def test_safe_gate_warns_on_empty_league_id(caplog):
    with caplog.at_level(logging.WARNING, logger="sportsbankzu.ev_classification"):
        assert _is_safe_enabled(None) is False
    assert any("empty league_id" in r.message for r in caplog.records)


def test_safe_gate_disabled_when_calibrated_but_flag_off(monkeypatch):
    monkeypatch.setattr(
        "backend.modeling.lambda_calculator.get_lambda_corrections",
        lambda league: {"safe_enabled": {"value": "0"}, "lambda_deflation_ou": {"value": "0.9"}},
    )
    assert _is_safe_enabled("brasileirao-serie-a") is False


# ── _get_calibrated_threshold ──────────────────────────────────────────

def test_threshold_resolves_alias_before_lookup(monkeypatch):
    seen = {}

    def fake_corrections(league):
        seen["league"] = league
        return {"safe_prob_ou": {"value": "0.71"}}

    monkeypatch.setattr(
        "backend.modeling.lambda_calculator.get_lambda_corrections",
        fake_corrections,
    )
    th = _get_calibrated_threshold("brazil-serie-a", "Over/Under")
    assert th == {"safe_prob": 0.71}
    assert seen["league"] == "brasileirao-serie-a"
