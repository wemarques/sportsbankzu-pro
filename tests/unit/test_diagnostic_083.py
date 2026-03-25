"""Unit tests for Post-Match Diagnostic Engine (#083)."""

from backend.services.post_match_diagnostic import (
    decompose_error,
    detect_patterns,
    generate_diagnostic_narrative,
    run_post_match_diagnostic,
)


def test_decompose_error_lambda_overestimate():
    """Lambda alto -> LAMBDA_OVERESTIMATE."""
    pick = {"acertou": False, "lambda_home": 2.0, "lambda_away": 1.5, "prob": 70, "ev": 8}
    result = {"homeGoals": 0, "awayGoals": 1}
    diag = decompose_error(pick, result)
    assert diag["cause"] == "LAMBDA_OVERESTIMATE"
    assert diag["confidence"] > 0.5


def test_decompose_error_correct_pick():
    """Pick correto -> CORRECT."""
    pick = {"acertou": True}
    diag = decompose_error(pick, {})
    assert diag["cause"] == "CORRECT"


def test_decompose_error_unknown():
    """Sem dados suficientes -> UNKNOWN."""
    pick = {"acertou": False, "prob": 55, "ev": 3}
    diag = decompose_error(pick, {})
    assert diag["cause"] == "UNKNOWN"


def test_detect_patterns_lambda_systematic():
    """3+ LAMBDA_OVERESTIMATE -> SYSTEMATIC_LAMBDA_OVER pattern."""
    diagnostics = [
        {"cause": "LAMBDA_OVERESTIMATE", "league": "premier-league", "market": "Over 2.5"},
        {"cause": "LAMBDA_OVERESTIMATE", "league": "premier-league", "market": "Over 2.5"},
        {"cause": "LAMBDA_OVERESTIMATE", "league": "la-liga", "market": "Over 2.5"},
        {"cause": "UNKNOWN", "league": "serie-a", "market": "BTTS"},
    ]
    report = detect_patterns(diagnostics)
    assert len(report["patterns"]) >= 1
    assert report["patterns"][0]["type"] == "SYSTEMATIC_LAMBDA_OVER"
    assert report["summary"]["top_cause"] == "LAMBDA_OVERESTIMATE"


def test_detect_patterns_no_errors():
    """Sem erros -> sem padroes."""
    report = detect_patterns([])
    assert report["patterns"] == []
    assert report["summary"]["total_errors"] == 0


def test_narrative_deterministic():
    """Narrativa deterministica funciona sem Mistral."""
    pattern_report = {
        "summary": {"total_errors": 5, "unknown": 1, "top_cause": "LAMBDA_OVERESTIMATE", "top_cause_pct": 0.60},
        "patterns": [{"type": "SYSTEMATIC_LAMBDA_OVER", "severity": "HIGH", "frequency": 0.60, "count": 3, "recommendation": "Recalibrar"}],
    }
    text = generate_diagnostic_narrative(pattern_report, use_mistral=False)
    assert "LAMBDA_OVERESTIMATE" in text
    assert "60%" in text
    assert "Recalibrar" in text


def test_run_full_diagnostic():
    """Orquestracao completa funciona."""
    picks = [
        {"acertou": False, "match_id": "1", "league": "premier-league", "mercado": "Over 2.5",
         "lambda_home": 2.0, "lambda_away": 1.5, "prob": 70, "ev": 8},
        {"acertou": True, "match_id": "2", "league": "la-liga", "mercado": "BTTS"},
    ]
    results = [
        {"match_id": "1", "homeGoals": 0, "awayGoals": 1},
        {"match_id": "2", "homeGoals": 2, "awayGoals": 1},
    ]
    report = run_post_match_diagnostic(picks, results, use_mistral_narrative=False)
    assert "error_decomposition" in report
    assert "pattern_report" in report
    assert "narrative" in report
    assert len(report["error_decomposition"]) == 2
