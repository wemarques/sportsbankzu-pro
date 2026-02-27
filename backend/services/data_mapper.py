from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pandas as pd
import logging
from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger("sportsbank.mapper")


class FootyStatsMatchInput(BaseModel):
    """Validates raw match data from the FootyStats API before internal mapping.

    All fields are Optional because FootyStats may omit stats for scheduled matches.
    Coercion is used for numeric fields so string "0" → int 0 without raising errors.
    """

    id: Optional[int] = None
    date_unix: Optional[int] = None
    status: Optional[str] = None
    home_name: Optional[str] = None
    away_name: Optional[str] = None
    homeID: Optional[int] = None
    awayID: Optional[int] = None
    homeGoalCount: Optional[int] = 0
    awayGoalCount: Optional[int] = 0
    totalGoalCount: Optional[int] = 0
    team_a_corners: Optional[int] = -1
    team_b_corners: Optional[int] = -1
    team_a_possession: Optional[float] = -1.0
    team_b_possession: Optional[float] = -1.0
    team_a_shots: Optional[int] = -1
    team_b_shots: Optional[int] = -1
    team_a_shotsOnTarget: Optional[int] = -1
    team_b_shotsOnTarget: Optional[int] = -1
    team_a_xg: Optional[float] = 0.0
    team_b_xg: Optional[float] = 0.0
    btts_potential: Optional[float] = 0.0
    o15_potential: Optional[float] = 0.0
    o25_potential: Optional[float] = 0.0
    o35_potential: Optional[float] = 0.0
    o45_potential: Optional[float] = 0.0
    corners_potential: Optional[float] = 0.0
    corners_o85_potential: Optional[float] = 0.0
    corners_o95_potential: Optional[float] = 0.0
    corners_o105_potential: Optional[float] = 0.0
    odds_corners_over_85: Optional[float] = 0.0
    odds_corners_over_95: Optional[float] = 0.0
    odds_corners_over_105: Optional[float] = 0.0
    odds_corners_over_115: Optional[float] = 0.0
    home_ppg: Optional[float] = 0.0
    away_ppg: Optional[float] = 0.0
    pre_match_home_ppg: Optional[float] = 0.0
    pre_match_away_ppg: Optional[float] = 0.0
    pre_match_teamA_overall_ppg: Optional[float] = 0.0
    pre_match_teamB_overall_ppg: Optional[float] = 0.0
    odds_ft_1: Optional[float] = 0.0
    odds_ft_x: Optional[float] = 0.0
    odds_ft_2: Optional[float] = 0.0
    odds_ft_over15: Optional[float] = 0.0
    odds_ft_over25: Optional[float] = 0.0
    odds_ft_over35: Optional[float] = 0.0
    odds_ft_over45: Optional[float] = 0.0
    odds_btts_yes: Optional[float] = 0.0
    competition_id: Optional[int] = None
    game_week: Optional[int] = None
    stadium_name: Optional[str] = None
    stadium_location: Optional[str] = None

    model_config = {"extra": "allow"}  # Preserve unknown fields for forward-compatibility

    @field_validator("home_name", "away_name", mode="before")
    @classmethod
    def name_not_empty(cls, v: Any) -> Optional[str]:
        """Coerce non-string names; return None if empty so downstream uses ID fallback."""
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @model_validator(mode="after")
    def require_team_identity(self) -> "FootyStatsMatchInput":
        """At least one of (home_name, homeID) must be present for the match to be identifiable."""
        if not self.home_name and not self.homeID:
            logger.warning("[FootyStatsMatchInput] Match missing both home_name and homeID — data may be corrupt")
        if not self.away_name and not self.awayID:
            logger.warning("[FootyStatsMatchInput] Match missing both away_name and awayID — data may be corrupt")
        return self


class DataMapper:
    """Traduz dados da API FootyStats para o formato interno baseado nos layouts CSV."""

    @staticmethod
    def map_match_to_internal(api_match: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um objeto de partida da API para o formato esperado pelo backend."""
        # Convert unix timestamp to date string for compute_form compatibility
        date_unix = api_match.get("date_unix")
        date_gmt = None
        if date_unix:
            try:
                date_gmt = datetime.fromtimestamp(int(date_unix), tz=timezone.utc).strftime("%b %d %Y - %I:%M%p")
            except Exception:
                pass

        return {
            "id": api_match.get("id"),
            "timestamp": date_unix,
            "date_gmt": date_gmt,
            "status": api_match.get("status"),
            "team_a_name": api_match.get("home_name") or api_match.get("homeID"),
            "team_b_name": api_match.get("away_name") or api_match.get("awayID"),
            "home_team_goal_count": api_match.get("homeGoalCount", 0),
            "away_team_goal_count": api_match.get("awayGoalCount", 0),
            "total_goal_count": api_match.get("totalGoalCount", 0),
            "home_team_corner_count": api_match.get("team_a_corners", -1),
            "away_team_corner_count": api_match.get("team_b_corners", -1),
            "home_team_possession": api_match.get("team_a_possession", -1),
            "away_team_possession": api_match.get("team_b_possession", -1),
            "home_team_shots": api_match.get("team_a_shots", -1),
            "away_team_shots": api_match.get("team_b_shots", -1),
            "home_team_shots_on_target": api_match.get("team_a_shotsOnTarget", -1),
            "away_team_shots_on_target": api_match.get("team_b_shotsOnTarget", -1),
            "home_team_xg": api_match.get("team_a_xg", 0.0),
            "away_team_xg": api_match.get("team_b_xg", 0.0),
            "btts_percentage_pre_match": api_match.get("btts_potential", 0),
            "over_15_percentage_pre_match": api_match.get("o15_potential", 0),
            "over_25_percentage_pre_match": api_match.get("o25_potential", 0),
            "over_35_percentage_pre_match": api_match.get("o35_potential", 0),
            "over_45_percentage_pre_match": api_match.get("o45_potential", 0),
            # Corner potentials (pre-match probabilities)
            "corners_potential": api_match.get("corners_potential", 0),
            "corners_o85_potential": api_match.get("corners_o85_potential", 0),
            "corners_o95_potential": api_match.get("corners_o95_potential", 0),
            "corners_o105_potential": api_match.get("corners_o105_potential", 0),
            # Corner odds
            "odds_corners_over_85": api_match.get("odds_corners_over_85", 0.0),
            "odds_corners_over_95": api_match.get("odds_corners_over_95", 0.0),
            "odds_corners_over_105": api_match.get("odds_corners_over_105", 0.0),
            "odds_corners_over_115": api_match.get("odds_corners_over_115", 0.0),
            # PPG
            "home_ppg": api_match.get("home_ppg", 0.0),
            "away_ppg": api_match.get("away_ppg", 0.0),
            "pre_match_home_ppg": api_match.get("pre_match_home_ppg", 0.0),
            "pre_match_away_ppg": api_match.get("pre_match_away_ppg", 0.0),
            "pre_match_teamA_overall_ppg": api_match.get("pre_match_teamA_overall_ppg", 0.0),
            "pre_match_teamB_overall_ppg": api_match.get("pre_match_teamB_overall_ppg", 0.0),
            # Odds
            "odds_ft_home_team_win": api_match.get("odds_ft_1", 0.0),
            "odds_ft_draw": api_match.get("odds_ft_x", 0.0),
            "odds_ft_away_team_win": api_match.get("odds_ft_2", 0.0),
            "odds_ft_over15": api_match.get("odds_ft_over15", 0.0),
            "odds_ft_over25": api_match.get("odds_ft_over25", 0.0),
            "odds_ft_over35": api_match.get("odds_ft_over35", 0.0),
            "odds_ft_over45": api_match.get("odds_ft_over45", 0.0),
            "odds_btts_yes": api_match.get("odds_btts_yes", 0.0),
            "competition_id": api_match.get("competition_id"),
            "game_week": api_match.get("game_week"),
            "stadium": api_match.get("stadium_name", ""),
            "stadium_location": api_match.get("stadium_location", ""),
        }

    @staticmethod
    def map_team_to_internal(api_team: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um objeto de time da API para o formato esperado pelo backend."""
        # Mapeamento baseado no Team CSV - 186 Data Columns
        return {
            "team_name": api_team.get("name"),
            "common_name": api_team.get("cleanName"),
            "season": api_team.get("season"),
            "country": api_team.get("country"),
            "points_per_game": api_team.get("ppg_geral", 0.0),
            "goals_scored": api_team.get("seasonGoals", 0),
            "goals_conceded": api_team.get("seasonConceded", 0),
            "average_possession": api_team.get("posse_media", 0),
            "shots_on_target_per_match": api_team.get("chutes_no_gol_media", 0),
        }

    @classmethod
    def matches_to_df(cls, api_matches: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converte uma lista de partidas da API em um DataFrame formatado como o CSV.

        Each record is validated via FootyStatsMatchInput before mapping so that
        type coercions and missing-field warnings are applied consistently.
        """
        mapped_matches = []
        for i, raw in enumerate(api_matches):
            try:
                validated = FootyStatsMatchInput.model_validate(raw)
                mapped_matches.append(cls.map_match_to_internal(validated.model_dump()))
            except Exception as exc:
                logger.warning("[DataMapper] Skipping malformed match record #%d: %s", i, exc)
        return pd.DataFrame(mapped_matches)

    @classmethod
    def teams_to_df(cls, api_teams: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converte uma lista de times da API em um DataFrame formatado como o CSV."""
        mapped_teams = [cls.map_team_to_internal(t) for t in api_teams]
        return pd.DataFrame(mapped_teams)
