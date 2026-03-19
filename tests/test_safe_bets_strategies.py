"""Tests for V3.7 Safe Bets strategies: Under 2.5, BTTS YES, Over 2.5."""

import pytest
from backend.models.safe_bets import (
    SafeBetTag,
    LeagueSeasonStats,
    TeamSafeBetsStats,
)
from backend.services.safe_bets_service import (
    _strategy_under_25,
    _strategy_btts_yes,
    _strategy_over_25,
)


class TestStrategyUnder25:
    def test_passes_when_all_criteria_met(self):
        league = LeagueSeasonStats(seasonAVG_overall=2.00)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=0.90)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=0.85)
        result = _strategy_under_25(league, home, away, prediction_risk=0.30)
        assert result.passed is True
        assert result.tag == SafeBetTag.UNDER_25
        assert result.market_label == "Under 2.5 Gols"

    def test_fails_when_league_avg_too_high(self):
        league = LeagueSeasonStats(seasonAVG_overall=2.80)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=0.90)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=0.85)
        result = _strategy_under_25(league, home, away, prediction_risk=0.30)
        assert result.passed is False

    def test_fails_when_prediction_risk_high(self):
        league = LeagueSeasonStats(seasonAVG_overall=2.00)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=0.90)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=0.85)
        result = _strategy_under_25(league, home, away, prediction_risk=0.60)
        assert result.passed is False


class TestStrategyBttsYes:
    def test_passes_when_all_criteria_met(self):
        league = LeagueSeasonStats(seasonBTTSPercentage=60.0)
        home = TeamSafeBetsStats(seasonBTTSPercentage=75.0)
        away = TeamSafeBetsStats(seasonBTTSPercentage=72.0)
        result = _strategy_btts_yes(league, home, away)
        assert result.passed is True
        assert result.tag == SafeBetTag.BTTS_YES
        assert "SIM" in result.market_label

    def test_fails_when_league_btts_low(self):
        league = LeagueSeasonStats(seasonBTTSPercentage=40.0)
        home = TeamSafeBetsStats(seasonBTTSPercentage=75.0)
        away = TeamSafeBetsStats(seasonBTTSPercentage=72.0)
        result = _strategy_btts_yes(league, home, away)
        assert result.passed is False

    def test_fails_when_team_btts_low(self):
        league = LeagueSeasonStats(seasonBTTSPercentage=60.0)
        home = TeamSafeBetsStats(seasonBTTSPercentage=50.0)
        away = TeamSafeBetsStats(seasonBTTSPercentage=72.0)
        result = _strategy_btts_yes(league, home, away)
        assert result.passed is False


class TestStrategyOver25:
    def test_passes_when_all_criteria_met(self):
        league = LeagueSeasonStats(seasonAVG_overall=3.20)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=1.80)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=1.60)
        result = _strategy_over_25(league, home, away)
        assert result.passed is True
        assert result.tag == SafeBetTag.OVER_25
        assert result.market_label == "Over 2.5 Gols"

    def test_fails_when_league_avg_low(self):
        league = LeagueSeasonStats(seasonAVG_overall=2.50)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=1.80)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=1.60)
        result = _strategy_over_25(league, home, away)
        assert result.passed is False

    def test_fails_when_team_scored_low(self):
        league = LeagueSeasonStats(seasonAVG_overall=3.20)
        home = TeamSafeBetsStats(seasonScoredAVG_overall=1.20)
        away = TeamSafeBetsStats(seasonScoredAVG_overall=1.60)
        result = _strategy_over_25(league, home, away)
        assert result.passed is False
