"""Tests for classification display names (#080)."""

from backend.services.deterministic_audit import (
    DISPLAY_NAMES,
    _display_name,
    _compute_threshold_evaluation,
)


def test_display_name_safe():
    assert _display_name("SAFE") == "ALTA CONFIANCA"


def test_display_name_all():
    assert _display_name("NEUTRO_QUALIFICADO") == "VALOR DETECTADO"
    assert _display_name("NEUTRO") == "INFORMATIVO"
    assert _display_name("NO_BET") == "BLOQUEADO"


def test_display_name_unknown():
    assert _display_name("SOMETHING_ELSE") == "SOMETHING_ELSE"


def test_deterministic_audit_uses_display_names():
    """Threshold evaluation notes should use display names."""
    result = _compute_threshold_evaluation(safe_acc=40.0, neutro_acc=35.0)
    assert "ALTA CONFIANCA" in result["notes"]
    assert "INFORMATIVO" in result["notes"]
    # Structural fields keep internal names
    assert result["safe_status"] == "BAIXO"
    assert result["neutro_status"] == "BAIXO"
