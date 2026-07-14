"""
#186 (B-011) — API-Football date resolution guard.

The /fixtures date param accepts "today" | "tomorrow" | "week" | Y-m-d.
API-Football only accepts Y-m-d; before #186, "week" leaked verbatim into
the AF query ("The Date field must contain a valid date: Y-m-d"), silently
disabling every API-Football enrichment (live overlay, apiFootballFixtureId,
odds #120, injuries/lineups). _af_query_dates must NEVER return a value that
does not match Y-m-d.
"""

import re

import pytest

from backend.routes.fixtures import _af_query_dates, _AF_MAX_DATES

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _record(dt: str) -> dict:
    return {"datetime": dt, "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"}}


class TestAfQueryDates:

    def test_today_returns_single_valid_date(self):
        dates = _af_query_dates("today", [])
        assert len(dates) == 1
        assert _ISO.match(dates[0])

    def test_tomorrow_returns_single_valid_date(self):
        dates = _af_query_dates("tomorrow", [])
        assert len(dates) == 1
        assert _ISO.match(dates[0])

    def test_iso_date_passthrough(self):
        assert _af_query_dates("2026-07-14", []) == ["2026-07-14"]

    def test_week_derives_from_record_dates(self):
        records = [
            _record("2026-07-18T19:00:00Z"),
            _record("2026-07-18T21:30:00Z"),
            _record("2026-07-19T16:00:00Z"),
            _record("2026-07-20T20:00:00Z"),
        ]
        dates = _af_query_dates("week", records)
        assert dates == ["2026-07-18", "2026-07-19", "2026-07-20"]

    def test_week_without_records_covers_next_seven_days(self):
        dates = _af_query_dates("week", [])
        assert len(dates) == 7
        assert all(_ISO.match(d) for d in dates)

    def test_invalid_date_without_records_returns_empty(self):
        assert _af_query_dates("banana", []) == []
        assert _af_query_dates("", []) == []

    def test_invalid_date_with_records_derives_from_records(self):
        records = [_record("2026-07-18T19:00:00Z")]
        assert _af_query_dates("garbage", records) == ["2026-07-18"]

    def test_unparseable_record_datetimes_are_skipped(self):
        records = [_record("not-a-date"), _record(""), {"datetime": None}]
        # falls through to the week range only for "week"; garbage input → []
        assert _af_query_dates("garbage", records) == []

    def test_record_dates_are_bounded(self):
        records = [_record(f"2026-07-{day:02d}T12:00:00Z") for day in range(1, 20)]
        dates = _af_query_dates("week", records)
        assert len(dates) <= _AF_MAX_DATES

    def test_never_returns_non_iso_values(self):
        for date_str in ("today", "tomorrow", "week", "2026-01-02", "junk"):
            for dates in (_af_query_dates(date_str, []),
                          _af_query_dates(date_str, [_record("2026-07-18T19:00:00Z")])):
                assert all(_ISO.match(d) for d in dates)
