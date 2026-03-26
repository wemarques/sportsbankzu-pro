"""Tests for #089: date_range ISO date parsing + BRT date computation in cron."""
from datetime import datetime, timedelta, timezone


def test_date_range_parses_iso_date():
    """date_range('2026-03-24') should return BRT calendar boundaries for that date."""
    from backend.main import date_range

    start, end = date_range("2026-03-24")
    BRT = timezone(timedelta(hours=-3))

    # Start should be 2026-03-24 00:00 BRT = 2026-03-24 03:00 UTC
    expected_start = datetime(2026, 3, 24, 3, 0, 0, tzinfo=timezone.utc)
    assert start == expected_start, f"Expected {expected_start}, got {start}"

    # End should be 2026-03-24 23:59:59.999 BRT = 2026-03-25 02:59:59.999 UTC
    expected_end_approx = datetime(2026, 3, 25, 2, 59, 59, tzinfo=timezone.utc)
    assert end.year == 2026 and end.month == 3 and end.day == 25
    assert end.hour == 2 and end.minute == 59 and end.second == 59


def test_date_range_yesterday_still_works():
    """'yesterday' keyword should still work correctly."""
    from backend.main import date_range

    start, end = date_range("yesterday")
    # Should return a 1-day window (end - start ≈ 24h)
    delta = end - start
    assert 23 * 3600 < delta.total_seconds() < 25 * 3600


def test_date_range_today_still_works():
    """'today' keyword should still work correctly."""
    from backend.main import date_range

    start, end = date_range("today")
    delta = end - start
    assert 23 * 3600 < delta.total_seconds() < 25 * 3600


def test_date_range_default_fallback():
    """Unrecognized string should still return 7-day default window."""
    from backend.main import date_range

    start, end = date_range("nonsense_string")
    delta = end - start
    # 7-day window ≈ 7 * 86400 seconds
    assert 6 * 86400 < delta.total_seconds() < 8 * 86400


def test_date_range_iso_date_includes_late_brt_match():
    """A match at 22:00 BRT on March 24 (= 01:00 UTC March 25) should be
    INSIDE the date_range('2026-03-24') window."""
    from backend.main import date_range

    start, end = date_range("2026-03-24")

    # Match at 22:00 BRT March 24 = 01:00 UTC March 25
    match_utc = datetime(2026, 3, 25, 1, 0, 0, tzinfo=timezone.utc)
    assert start <= match_utc <= end, (
        f"Match at 01:00 UTC (22:00 BRT) should be in range [{start}, {end}]"
    )


def test_date_range_iso_date_excludes_next_day_brt():
    """A match at 00:30 BRT on March 25 (= 03:30 UTC March 25) should be
    OUTSIDE the date_range('2026-03-24') window."""
    from backend.main import date_range

    start, end = date_range("2026-03-24")

    # Match at 00:30 BRT March 25 = 03:30 UTC March 25
    match_utc = datetime(2026, 3, 25, 3, 30, 0, tzinfo=timezone.utc)
    assert not (start <= match_utc <= end), (
        f"Match at 03:30 UTC (00:30 BRT next day) should NOT be in range [{start}, {end}]"
    )


def test_cards_in_mercados_validos():
    """Cards markets should be in MERCADOS_VALIDOS after #089."""
    from backend.modeling.market_validator import MERCADOS_VALIDOS

    for line in ["2.5", "3.5", "4.5", "5.5"]:
        assert f"Cartoes Over {line}" in MERCADOS_VALIDOS
        assert f"Cartoes Under {line}" in MERCADOS_VALIDOS
