"""Tests for backend.audit safety validation and version management."""

from backend.audit import validate_adjustment, ADJUSTMENT_LIMITS


def test_validate_adjustment_within_limits():
    """Adjustment within safety limits should be accepted."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.65, 0.70)
    assert ok is True
    assert reason == "OK"


def test_validate_adjustment_exceeds_delta():
    """Adjustment with delta > max_delta should be rejected."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.50, 0.80)
    assert ok is False
    assert "Delta" in reason


def test_validate_adjustment_out_of_range_high():
    """Adjustment above max value should be rejected."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.90, 0.99)
    assert ok is False
    assert "range" in reason


def test_validate_adjustment_out_of_range_low():
    """Adjustment below min value should be rejected."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.45, 0.35)
    assert ok is False
    assert "range" in reason


def test_validate_adjustment_lambda_weight():
    """Lambda weight adjustment within limits."""
    ok, reason = validate_adjustment("LAMBDA_WEIGHT", "temporada_weight", 0.60, 0.70)
    assert ok is True


def test_validate_adjustment_lambda_weight_out_of_range():
    """Lambda weight adjustment out of range."""
    ok, reason = validate_adjustment("LAMBDA_WEIGHT", "temporada_weight", 0.85, 0.95)
    assert ok is False
    assert "range" in reason


def test_validate_adjustment_unknown_type_uses_threshold_defaults():
    """Unknown correction type should fall back to THRESHOLD limits."""
    ok, reason = validate_adjustment("UNKNOWN_TYPE", "param", 0.60, 0.65)
    assert ok is True


def test_validate_adjustment_exact_boundary():
    """Exact boundary values should be accepted."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.40, 0.40)
    assert ok is True

    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.90, 0.95)
    assert ok is True


def test_validate_adjustment_exact_max_delta():
    """Exactly at max_delta should be accepted."""
    ok, reason = validate_adjustment("THRESHOLD", "safe_threshold", 0.50, 0.60)
    assert ok is True  # delta = 0.10, max_delta = 0.10


def test_increment_version():
    """Version should increment minor component."""
    import backend.audit

    old_ver = backend.audit.APP_VERSION
    try:
        # Set a known version for testing
        backend.audit.APP_VERSION = "pro V2.7"
        new_ver = backend.audit.increment_version()
        assert new_ver == "pro V2.8"
        assert backend.audit.APP_VERSION == "pro V2.8"
    finally:
        # Restore original version
        backend.audit.APP_VERSION = old_ver


def test_increment_version_double_digit():
    """Version increment should handle double-digit minor versions."""
    import backend.audit

    old_ver = backend.audit.APP_VERSION
    try:
        backend.audit.APP_VERSION = "pro V2.9"
        new_ver = backend.audit.increment_version()
        assert new_ver == "pro V2.10"
    finally:
        backend.audit.APP_VERSION = old_ver


def test_increment_version_no_match():
    """If version has no numeric pattern, return as-is."""
    import backend.audit

    old_ver = backend.audit.APP_VERSION
    try:
        backend.audit.APP_VERSION = "unknown"
        new_ver = backend.audit.increment_version()
        assert new_ver == "unknown"
    finally:
        backend.audit.APP_VERSION = old_ver
