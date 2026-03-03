"""
Pydantic models for the Safe Bets Engine.

Covers:
- League season stats (from FootyStats /league-season endpoint)
- Team stats (from FootyStats /league-teams endpoint)
- Safe Bet evaluation input/output
- API response shapes
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class SafeBetTag(str, Enum):
    UNDER_35 = "UNDER_35"
    BTTS_NO = "BTTS_NO"
    SAFE_CORNERS = "SAFE_CORNERS"
    SAFE_CORNERS_HT = "SAFE_CORNERS_HT"
    TIMING_2H = "TIMING_2H"
    NO_BET = "NO_BET"


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    NO_BET = "NO_BET"


class LeagueCategory(str, Enum):
    DEFENSIVE = "DEFENSIVE"
    BALANCED = "BALANCED"
    OFFENSIVE = "OFFENSIVE"


# =============================================================================
# FootyStats API input models (league-season stats)
# =============================================================================

class LeagueSeasonStats(BaseModel):
    """Parsed league-level season stats from FootyStats /league-season endpoint."""
    season_id: Optional[int] = None
    league_id: Optional[str] = None
    # Core averages
    seasonAVG_overall: Optional[float] = Field(None, description="Average goals per match in the season")
    seasonBTTSPercentage: Optional[float] = Field(None, description="% of matches with both teams scoring")
    seasonCSPercentage: Optional[float] = Field(None, description="% of matches with clean sheet (any side)")
    # Corners
    cornersAVG_overall: Optional[float] = Field(None, description="Average corners per match")
    corners_fh_avg: Optional[float] = Field(None, description="Average corners in first half")
    # Cards
    cardsAVG_overall: Optional[float] = Field(None, description="Average cards per match")
    # Goal timing
    goalTimingDisabled: Optional[int] = Field(0, description="1 if goal timing data is disabled")
    corner_disabled: Optional[int] = Field(0, description="1 if corner data is disabled")
    # Over/Under percentages
    over05_2hg_percentage: Optional[float] = Field(None, description="% of matches with >0.5 goals in 2nd half")
    half_with_most_goals_is_2h_percentage_overall: Optional[float] = None

    model_config = {"extra": "allow"}


# =============================================================================
# Team stats for Safe Bets evaluation
# =============================================================================

class TeamSafeBetsStats(BaseModel):
    """Team-level stats needed for Safe Bets validation."""
    team_name: Optional[str] = None
    team_id: Optional[int] = None
    # Goals
    seasonScoredAVG_overall: Optional[float] = None
    seasonConcededAVG_overall: Optional[float] = None
    seasonScoredAVG_home: Optional[float] = None
    seasonScoredAVG_away: Optional[float] = None
    seasonConcededAVG_home: Optional[float] = None
    seasonConcededAVG_away: Optional[float] = None
    # Clean sheet / FTS
    seasonCSPercentage_home: Optional[float] = Field(None, description="Home clean sheet %")
    seasonCSPercentage_away: Optional[float] = Field(None, description="Away clean sheet %")
    seasonCSPercentage_overall: Optional[float] = None
    seasonFTSPercentage_home: Optional[float] = Field(None, description="Home failed to score %")
    seasonFTSPercentage_away: Optional[float] = Field(None, description="Away failed to score %")
    seasonFTSPercentage_overall: Optional[float] = None
    # BTTS
    seasonBTTSPercentage: Optional[float] = None
    # Corners
    cornersAVG_overall: Optional[float] = None
    cornersAVG_home: Optional[float] = None
    cornersAVG_away: Optional[float] = None
    corners_fh_avg: Optional[float] = Field(None, description="Average first-half corners for this team")
    # Prediction risk
    predictionRisk: Optional[float] = Field(None, description="0-1 prediction risk score")
    riskNum: Optional[float] = Field(None, description="Alternative risk score from API")
    # 2nd half goals
    over05_2hg_percentage: Optional[float] = None
    half_with_most_goals_is_2h_percentage_overall: Optional[float] = None

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def extract_from_stats(cls, data: Any) -> Any:
        """If data comes with nested 'stats' dict, flatten it."""
        if isinstance(data, dict) and "stats" in data:
            stats = data.get("stats", {}) or {}
            merged = {**stats, **{k: v for k, v in data.items() if k != "stats"}}
            return merged
        return data


# =============================================================================
# Safe Bets evaluation input
# =============================================================================

class SafeBetsMatchInput(BaseModel):
    """Input for evaluating a single match through the Safe Bets engine."""
    match_id: str
    league_id: str
    home_team: str
    away_team: str
    match_date: Optional[str] = None
    # League-level stats
    league_stats: Optional[LeagueSeasonStats] = None
    # Team-level stats
    home_stats: Optional[TeamSafeBetsStats] = None
    away_stats: Optional[TeamSafeBetsStats] = None
    # Prediction risk from match-level data
    prediction_risk: Optional[float] = Field(None, description="Match-level risk (0-1)")


# =============================================================================
# Safe Bets evaluation output
# =============================================================================

class StrategyResult(BaseModel):
    """Result of a single strategy evaluation."""
    strategy: str                       # e.g. "UNDER_35", "BTTS_NO"
    tag: SafeBetTag
    passed: bool
    confidence: Optional[float] = None  # 0-100%
    reason: str = ""                    # Human-readable explanation
    market_label: str = ""              # Display label (e.g. "Under 3.5 Gols")
    details: Optional[Dict[str, Any]] = None


class SafeBetsResult(BaseModel):
    """Full output from the Safe Bets engine for a single match."""
    match_id: str
    league_id: str
    home_team: str
    away_team: str
    # Overall verdict
    tags: List[SafeBetTag] = []
    risk_level: RiskLevel = RiskLevel.NO_BET
    # Layer-by-layer details
    layer1_dna: Dict[str, Any] = {}
    layer2_risk: Dict[str, Any] = {}
    layer3_strategies: List[StrategyResult] = []
    # Blocked?
    blocked: bool = False
    block_reason: str = ""


# =============================================================================
# API response model
# =============================================================================

class SafeBetsResponse(BaseModel):
    """API response wrapping multiple match evaluations."""
    success: bool = True
    total_matches: int = 0
    safe_count: int = 0
    blocked_count: int = 0
    results: List[SafeBetsResult] = []
