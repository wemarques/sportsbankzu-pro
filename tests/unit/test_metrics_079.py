"""Tests for BLOCO 2 metrics and deterministic audit (#079)."""
import math
import pytest

from backend.services.backtesting import (
    compute_sharpe_ratio,
    compute_hit_rate_by_ev_band,
    compute_log_loss,
    MIN_N_SHARPE,
)
from backend.services.deterministic_audit import generate_deterministic_audit_report


# ── Sharpe Ratio ────────────────────────────────────────────────────


def test_sharpe_ratio_positive():
    """Majority winning sequence with favorable odds → Sharpe > 0."""
    # 40 wins + 20 losses at 2.0 odds → mean_return > 0, std > 0
    picks = (
        [{"odd": 2.0, "outcome": True, "stake": 10.0} for _ in range(40)]
        + [{"odd": 2.0, "outcome": False, "stake": 10.0} for _ in range(20)]
    )
    result = compute_sharpe_ratio(picks)
    assert result["n_bets"] == 60
    assert result["sharpe"] is not None
    assert result["sharpe"] > 0
    assert result["mean_return"] > 0  # 40 * 1.0 + 20 * (-1.0) → positive mean


def test_sharpe_ratio_insufficient_data():
    """N < MIN_N_SHARPE → sharpe is None."""
    picks = [
        {"odd": 2.0, "outcome": True, "stake": 10.0}
        for _ in range(MIN_N_SHARPE - 1)
    ]
    result = compute_sharpe_ratio(picks)
    assert result["sharpe"] is None
    assert result["n_bets"] == MIN_N_SHARPE - 1


# ── Hit Rate by EV Band ────────────────────────────────────────────


def test_hit_rate_by_ev_band_correct_bands():
    """4 bands returned with correct counts."""
    picks = [
        {"ev_pct": 3.0, "outcome": True},
        {"ev_pct": 3.0, "outcome": False},
        {"ev_pct": 7.0, "outcome": True},
        {"ev_pct": 15.0, "outcome": True},
        {"ev_pct": 25.0, "outcome": False},
    ]
    result = compute_hit_rate_by_ev_band(picks)
    # #196: passaram a existir duas faixas negativas — antes o EV entrava em
    # valor absoluto e um pick de -25% era contado como +25%.
    assert len(result) == 6

    band_0_5 = next(b for b in result if b["band"] == "0-5%")
    assert band_0_5["total"] == 2
    assert band_0_5["correct"] == 1
    assert band_0_5["accuracy"] == 0.5

    band_5_10 = next(b for b in result if b["band"] == "5-10%")
    assert band_5_10["total"] == 1
    assert band_5_10["correct"] == 1

    band_20_100 = next(b for b in result if b["band"] == "20-100%")
    assert band_20_100["total"] == 1
    assert band_20_100["correct"] == 0


# ── Log-Loss ───────────────────────────────────────────────────────


def test_log_loss_perfect_predictions():
    """prob≈1.0 + outcome=1 → loss near 0."""
    preds = [{"prob": 0.99, "outcome": 1} for _ in range(10)]
    result = compute_log_loss(preds)
    assert result is not None
    assert result < 0.02  # near-perfect → very low loss


# ── Deterministic Report ───────────────────────────────────────────


def test_deterministic_report_shape():
    """Output contains all BatchAuditModelEvaluation required keys."""
    batch_summary = {
        "total_audited": 20,
        "overall_correct": 12,
        "overall_total": 20,
        "overall_accuracy_pct": 60.0,
        "safe_correct": 5,
        "safe_total": 8,
        "safe_accuracy_pct": 62.5,
        "neutro_correct": 7,
        "neutro_total": 12,
        "neutro_accuracy_pct": 58.3,
        "avg_brier_score": 0.20,
        "avg_lambda_error": 0.7,
        "avg_ev": 0.05,
        "market_accuracy_text": "",
    }
    result = generate_deterministic_audit_report(batch_summary)

    # Required keys per BatchAuditModelEvaluation interface
    assert result["overall_assessment"] in ("SATISFATORIO", "NECESSITA_AJUSTE", "CRITICO")
    assert "lambda_evaluation" in result
    assert "status" in result["lambda_evaluation"]
    assert "notes" in result["lambda_evaluation"]
    assert "threshold_evaluation" in result
    assert "audit_confidence" in result
    assert isinstance(result["audit_confidence"], int)
    assert "timestamp" in result
    assert "recommended_corrections" in result
    assert "model_update_recommendation" in result


def test_deterministic_report_critico():
    """Bad inputs → CRITICO assessment."""
    batch_summary = {
        "total_audited": 30,
        "overall_correct": 8,
        "overall_total": 30,
        "overall_accuracy_pct": 26.7,
        "safe_correct": 1,
        "safe_total": 10,
        "safe_accuracy_pct": 10.0,  # < 40 → CRITICO
        "neutro_correct": 7,
        "neutro_total": 20,
        "neutro_accuracy_pct": 35.0,
        "avg_brier_score": 0.30,  # > 0.28 → CRITICO
        "avg_lambda_error": 1.6,  # > 1.5 → CRITICO
        "avg_ev": 0.01,
        "market_accuracy_text": "",
    }
    result = generate_deterministic_audit_report(batch_summary)
    assert result["overall_assessment"] == "CRITICO"
    assert result["lambda_evaluation"]["status"] == "CRITICO"
    assert result["model_update_recommendation"]["needs_update"] is True


def test_validate_match_prob_sum():
    """Prob sum > 103 → WARN status."""
    from backend.routes.ai_analysis import _validate_match_deterministic

    match_data = {
        "stats": {
            "homeWinProb": 45.0,
            "drawProb": 30.0,
            "awayWinProb": 30.0,  # sum = 105
            "lambdaHome": 1.5,
            "lambdaAway": 1.2,
        }
    }
    result = _validate_match_deterministic(match_data)
    assert result["status"] in ("WARN", "FAIL")
    prob_check = next(c for c in result["checks"] if c["check"] == "prob_sum")
    assert prob_check["status"] in ("WARN", "FAIL")
