"""Contract enforcement tests for #082 — Mistral is narrative-only.

Ensures dead audit code stays removed and the narrative endpoint still works.
"""
import importlib
import inspect
import pytest


def test_mistral_auditor_removed():
    """MistralAuditor module must not exist — deleted in #082."""
    with pytest.raises(ImportError):
        importlib.import_module("backend.ai.mistral_auditor")


def test_no_mistral_in_cron_handler():
    """cron_handler must not reference MistralAuditor anywhere."""
    import backend.cron_handler as mod
    source = inspect.getsource(mod)
    assert "MistralAuditor" not in source


def test_deterministic_audit_no_flag():
    """USE_DETERMINISTIC_AUDIT flag must be removed — deterministic is the only path."""
    import backend.cron_handler as mod
    source = inspect.getsource(mod)
    assert "USE_DETERMINISTIC_AUDIT" not in source


def test_no_confidence_adjustment_in_fixtures():
    """_apply_confidence_adjustment must be removed from fixtures_service (#082)."""
    import backend.services.fixtures_service as mod
    source = inspect.getsource(mod)
    assert "_apply_confidence_adjustment" not in source


def test_analysis_endpoint_still_works():
    """ai_analysis router must remain importable after cleanup."""
    from backend.routes.ai_analysis import router
    assert router is not None
