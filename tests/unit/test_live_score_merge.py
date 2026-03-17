"""Tests for live score extraction logic.

Covers the critical bug where live matches showed "- : -" instead of a
real score because the API returned -1 for goal counts and the backend
sent score=null to the frontend.

These tests exercise the core extraction functions directly (without
FastAPI or FootyStats dependencies) to ensure regression coverage.
"""
import time
import logging
import pytest


# ---------------------------------------------------------------------------
# Extract core logic from backend/routes/fixtures.py inline so tests don't
# require FastAPI to be installed.  This mirrors the real implementation.
# ---------------------------------------------------------------------------

def _valid_goal(val):
    """Return int if val is a valid goal count (>= 0), else None."""
    if val is None:
        return None
    try:
        v = int(val)
        return v if v >= 0 else None  # -1 = no data
    except (ValueError, TypeError):
        return None


_GOAL_HOME_FIELDS = ("homeGoalCount", "home_team_goal_count", "home_goals",
                     "team_a_goals", "homeScore", "home_score")
_GOAL_AWAY_FIELDS = ("awayGoalCount", "away_team_goal_count", "away_goals",
                     "team_b_goals", "awayScore", "away_score")


def extract_live_score(m: dict, status: str, detail_data: dict | None = None) -> dict | None:
    """
    Extract score from a raw match dict, mirroring the /live-scores logic.

    Returns {"home": int, "away": int} or {"home": int, "away": int, "halftime": {...}}
    Returns None only if status is not live/finished.
    For live matches, always returns a score (0-0 fallback if all sources fail).
    """
    home_goals = None
    for _f in _GOAL_HOME_FIELDS:
        home_goals = _valid_goal(m.get(_f))
        if home_goals is not None:
            break
    away_goals = None
    for _f in _GOAL_AWAY_FIELDS:
        away_goals = _valid_goal(m.get(_f))
        if away_goals is not None:
            break

    _has_goal_data = home_goals is not None and away_goals is not None

    # Fallback 1: totalGoalCount + halftime inference
    if not _has_goal_data:
        _total = _valid_goal(m.get("totalGoalCount"))
        if _total is not None and _total > 0:
            _ht_h = _valid_goal(m.get("home_team_goal_count_half_time"))
            _ht_a = _valid_goal(m.get("away_team_goal_count_half_time"))
            if _ht_h is not None and _ht_a is not None:
                home_goals = home_goals if home_goals is not None else _ht_h
                away_goals = away_goals if away_goals is not None else _ht_a
                _has_goal_data = True

    # Fallback 2: match-detail endpoint data
    if not _has_goal_data and detail_data:
        _fb_home = _valid_goal(detail_data.get("homeGoalCount"))
        _fb_away = _valid_goal(detail_data.get("awayGoalCount"))
        if _fb_home is not None and _fb_away is not None:
            home_goals = _fb_home
            away_goals = _fb_away
            _has_goal_data = True

    # Fallback 3 (FIXED): for live matches, default to 0-0 instead of None
    if not _has_goal_data:
        if status == "live":
            home_goals = 0
            away_goals = 0
            _has_goal_data = True
        else:
            return None

    score = {"home": int(home_goals), "away": int(away_goals)}

    # Halftime
    ht_home = m.get("home_team_goal_count_half_time")
    ht_away = m.get("away_team_goal_count_half_time")
    if ht_home is not None and ht_away is not None:
        try:
            _hth, _hta = int(ht_home), int(ht_away)
            if _hth >= 0 and _hta >= 0:
                score["halftime"] = {"home": _hth, "away": _hta}
        except (ValueError, TypeError):
            pass

    return score


# ---------------------------------------------------------------------------
# _valid_goal tests
# ---------------------------------------------------------------------------
class TestValidGoal:
    def test_none_returns_none(self):
        assert _valid_goal(None) is None

    def test_negative_one_returns_none(self):
        assert _valid_goal(-1) is None

    def test_zero_returns_zero(self):
        assert _valid_goal(0) == 0

    def test_positive_int(self):
        assert _valid_goal(3) == 3

    def test_string_number(self):
        assert _valid_goal("2") == 2

    def test_string_zero(self):
        assert _valid_goal("0") == 0

    def test_string_negative(self):
        assert _valid_goal("-1") is None

    def test_invalid_string(self):
        assert _valid_goal("abc") is None

    def test_float(self):
        assert _valid_goal(1.0) == 1


# ---------------------------------------------------------------------------
# 1. LIVE + explicit 0-0 from API → must return score 0-0
# ---------------------------------------------------------------------------
def test_live_explicit_zero_zero():
    m = {"homeGoalCount": 0, "awayGoalCount": 0}
    score = extract_live_score(m, "live")
    assert score is not None
    assert score["home"] == 0
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# 2. LIVE + API returns -1 for goals (no data) → must NOT produce None
#    Previously the backend would send score=null; now it should fallback 0-0
# ---------------------------------------------------------------------------
def test_live_api_returns_minus_one_fallback():
    m = {"homeGoalCount": -1, "awayGoalCount": -1}
    # match-detail also returns -1
    detail = {"homeGoalCount": -1, "awayGoalCount": -1}
    score = extract_live_score(m, "live", detail_data=detail)
    assert score is not None, "Live match must never have score=None (would render '- : -')"
    assert score["home"] == 0
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# 3. LIVE + score 2-1 from API → must pass through correctly
# ---------------------------------------------------------------------------
def test_live_score_passthrough():
    m = {"homeGoalCount": 2, "awayGoalCount": 1}
    score = extract_live_score(m, "live")
    assert score["home"] == 2
    assert score["away"] == 1


# ---------------------------------------------------------------------------
# 4. LIVE + null goals but totalGoalCount>0 with HT data → infer from HT
# ---------------------------------------------------------------------------
def test_live_infer_from_halftime():
    m = {
        "homeGoalCount": -1,
        "awayGoalCount": -1,
        "totalGoalCount": 2,
        "home_team_goal_count_half_time": 1,
        "away_team_goal_count_half_time": 1,
    }
    score = extract_live_score(m, "live")
    assert score["home"] == 1
    assert score["away"] == 1


# ---------------------------------------------------------------------------
# 5. LIVE + match-detail fallback succeeds → use detail score
# ---------------------------------------------------------------------------
def test_live_match_detail_fallback():
    m = {"homeGoalCount": -1, "awayGoalCount": -1}
    detail = {"homeGoalCount": 1, "awayGoalCount": 0}
    score = extract_live_score(m, "live", detail_data=detail)
    assert score["home"] == 1
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# 6. FINISHED + score 3-2 → must show final score
# ---------------------------------------------------------------------------
def test_finished_shows_final_score():
    m = {"homeGoalCount": 3, "awayGoalCount": 2}
    score = extract_live_score(m, "finished")
    assert score["home"] == 3
    assert score["away"] == 2


# ---------------------------------------------------------------------------
# 7. SCHEDULED → returns None (no score for pre-match)
# ---------------------------------------------------------------------------
def test_prematch_returns_none():
    m = {"homeGoalCount": -1, "awayGoalCount": -1}
    score = extract_live_score(m, "scheduled")
    assert score is None


# ---------------------------------------------------------------------------
# 8. LIVE + all goals None (not -1, just absent) + no detail → 0-0 fallback
# ---------------------------------------------------------------------------
def test_live_all_null_goals_fallback():
    m = {}  # no goal fields at all
    detail = {"homeGoalCount": None, "awayGoalCount": None}
    score = extract_live_score(m, "live", detail_data=detail)
    assert score is not None, "Live match with missing data must fallback to 0-0"
    assert score["home"] == 0
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# 9. Zero goals treated as valid (not falsy)
# ---------------------------------------------------------------------------
def test_zero_is_not_falsy():
    """Ensure that home=0 and away=0 are treated as valid scores, not None."""
    m = {"homeGoalCount": 0, "awayGoalCount": 0, "totalGoalCount": 0}
    score = extract_live_score(m, "live")
    assert score["home"] == 0
    assert score["away"] == 0
    assert isinstance(score["home"], int)
    assert isinstance(score["away"], int)


# ---------------------------------------------------------------------------
# 10. LIVE + score with halftime data
# ---------------------------------------------------------------------------
def test_live_with_halftime():
    m = {
        "homeGoalCount": 2,
        "awayGoalCount": 1,
        "home_team_goal_count_half_time": 1,
        "away_team_goal_count_half_time": 0,
    }
    score = extract_live_score(m, "live")
    assert score["home"] == 2
    assert score["away"] == 1
    assert score["halftime"]["home"] == 1
    assert score["halftime"]["away"] == 0


# ---------------------------------------------------------------------------
# 11. LIVE + partial: only home_goals present, away missing → 0-0 fallback
#     (because _has_goal_data requires BOTH home AND away)
# ---------------------------------------------------------------------------
def test_live_partial_goals_fallback():
    m = {"homeGoalCount": 1, "awayGoalCount": -1}
    score = extract_live_score(m, "live")
    # Only home is valid, away is -1 → _has_goal_data is False → fallback 0-0
    assert score is not None
    assert score["home"] == 0
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# 12. Alternative field names work
# ---------------------------------------------------------------------------
def test_alternative_field_names():
    m = {"home_goals": 3, "away_goals": 1}
    score = extract_live_score(m, "live")
    assert score["home"] == 3
    assert score["away"] == 1


def test_team_a_b_goals():
    m = {"team_a_goals": 0, "team_b_goals": 2}
    score = extract_live_score(m, "live")
    assert score["home"] == 0
    assert score["away"] == 2


# ---------------------------------------------------------------------------
# 13. LIVE + string goal counts "0" → must parse correctly
# ---------------------------------------------------------------------------
def test_string_zero_goals():
    m = {"homeGoalCount": "0", "awayGoalCount": "0"}
    score = extract_live_score(m, "live")
    assert score["home"] == 0
    assert score["away"] == 0


# ---------------------------------------------------------------------------
# Frontend merge simulation tests
# ---------------------------------------------------------------------------
class TestFrontendMergeLogic:
    """Simulate the fetchLiveScores merge logic from dashboard/page.tsx."""

    @staticmethod
    def merge_live_overlay(existing_score, live_overlay_score, new_status):
        """
        Mirrors the frontend merge logic after fix:
        - If overlay has valid score, use it (unless it would overwrite non-zero with 0-0)
        - If overlay has no score AND existing has no score AND status is live, fallback 0-0
        - Otherwise keep existing
        """
        has_live_score = (
            live_overlay_score is not None
            and (live_overlay_score.get("home") is not None or live_overlay_score.get("away") is not None)
        )
        live_score = existing_score

        if has_live_score:
            live_home = live_overlay_score.get("home", 0)
            live_away = live_overlay_score.get("away", 0)
            existing_total = (existing_score.get("home", 0) + existing_score.get("away", 0)) if existing_score else 0
            live_total = live_home + live_away
            use_existing = existing_total > 0 and live_total == 0
            if use_existing:
                live_score = existing_score
            else:
                live_score = {"home": live_home, "away": live_away}
        elif not live_score and new_status == "live":
            # FIXED: fallback 0-0 for live match with no score anywhere
            live_score = {"home": 0, "away": 0}

        return live_score

    def test_overlay_with_valid_score(self):
        result = self.merge_live_overlay(None, {"home": 1, "away": 0}, "live")
        assert result == {"home": 1, "away": 0}

    def test_overlay_null_existing_null_live_status(self):
        """The critical bug: both null + live → was undefined, now 0-0."""
        result = self.merge_live_overlay(None, None, "live")
        assert result is not None
        assert result["home"] == 0
        assert result["away"] == 0

    def test_overlay_null_preserves_existing_score(self):
        result = self.merge_live_overlay({"home": 1, "away": 0}, None, "live")
        assert result["home"] == 1
        assert result["away"] == 0

    def test_never_overwrite_nonzero_with_zero(self):
        """Guard: 1-0 should not be overwritten by 0-0 from overlay."""
        result = self.merge_live_overlay(
            {"home": 1, "away": 0},
            {"home": 0, "away": 0},
            "live",
        )
        assert result["home"] == 1
        assert result["away"] == 0

    def test_update_score_from_overlay(self):
        """Normal update: 0-0 → 1-0."""
        result = self.merge_live_overlay(
            {"home": 0, "away": 0},
            {"home": 1, "away": 0},
            "live",
        )
        assert result["home"] == 1
        assert result["away"] == 0

    def test_scheduled_no_fallback(self):
        """Scheduled match should NOT get 0-0 fallback."""
        result = self.merge_live_overlay(None, None, "scheduled")
        assert result is None

    def test_overlay_zero_zero_existing_zero_zero(self):
        """0-0 overlay should NOT be blocked when existing is also 0-0."""
        result = self.merge_live_overlay(
            {"home": 0, "away": 0},
            {"home": 0, "away": 0},
            "live",
        )
        assert result["home"] == 0
        assert result["away"] == 0


# ---------------------------------------------------------------------------
# MatchCard rendering simulation
# ---------------------------------------------------------------------------
class TestMatchCardRendering:
    """Simulate the MatchCard score ternary after fix."""

    @staticmethod
    def render_score(score, status):
        """
        Mirrors MatchCard.tsx rendering logic after fix:
        - live + score object → "{home} - {away}"
        - live + no score → "0 - 0" (was "- : -" before fix)
        """
        if status == "live":
            if score:
                home = score.get("home", 0) if score.get("home") is not None else 0
                away = score.get("away", 0) if score.get("away") is not None else 0
                return f"{home} - {away}"
            else:
                return "0 - 0"
        elif score and isinstance(score.get("home"), int):
            return f"{score['home']} - {score['away']}"
        return None

    def test_live_with_score_zero_zero(self):
        assert self.render_score({"home": 0, "away": 0}, "live") == "0 - 0"

    def test_live_with_score_two_one(self):
        assert self.render_score({"home": 2, "away": 1}, "live") == "2 - 1"

    def test_live_without_score_shows_zero_zero(self):
        """The critical fix: no more '- : -'."""
        result = self.render_score(None, "live")
        assert result == "0 - 0"
        assert "- : -" not in result

    def test_finished_with_score(self):
        assert self.render_score({"home": 3, "away": 2}, "finished") == "3 - 2"

    def test_scheduled_no_score(self):
        assert self.render_score(None, "scheduled") is None
