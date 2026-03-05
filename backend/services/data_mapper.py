from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pandas as pd
import logging
from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger("sportsbankzu.mapper")


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
    homeGoalCount: Optional[int] = None
    awayGoalCount: Optional[int] = None
    totalGoalCount: Optional[int] = None
    # Half-time
    total_goals_at_half_time: Optional[int] = -1
    home_team_goal_count_half_time: Optional[int] = -1
    away_team_goal_count_half_time: Optional[int] = -1
    # Goal timings
    home_team_goal_timings: Optional[str] = ""
    away_team_goal_timings: Optional[str] = ""
    # Attendance & referee
    attendance: Optional[int] = -1
    referee: Optional[str] = None
    team_a_corners: Optional[int] = -1
    team_b_corners: Optional[int] = -1
    team_a_possession: Optional[float] = -1.0
    team_b_possession: Optional[float] = -1.0
    team_a_shots: Optional[int] = -1
    team_b_shots: Optional[int] = -1
    team_a_shotsOnTarget: Optional[int] = -1
    team_b_shotsOnTarget: Optional[int] = -1
    team_a_yellow_cards: Optional[int] = -1
    team_b_yellow_cards: Optional[int] = -1
    team_a_red_cards: Optional[int] = -1
    team_b_red_cards: Optional[int] = -1
    # Card splits by half
    home_team_first_half_cards: Optional[int] = -1
    away_team_first_half_cards: Optional[int] = -1
    home_team_second_half_cards: Optional[int] = -1
    away_team_second_half_cards: Optional[int] = -1
    team_a_fouls: Optional[int] = -1
    team_b_fouls: Optional[int] = -1
    team_a_offsides: Optional[int] = -1
    team_b_offsides: Optional[int] = -1
    team_a_shotsOffTarget: Optional[int] = -1
    team_b_shotsOffTarget: Optional[int] = -1
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
    odds_btts_no: Optional[float] = 0.0
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
            "attendance": api_match.get("attendance", -1),
            "referee": api_match.get("referee") or api_match.get("refree"),
            "home_team_goal_count": api_match.get("homeGoalCount"),
            "away_team_goal_count": api_match.get("awayGoalCount"),
            "total_goal_count": api_match.get("totalGoalCount"),
            # Half-time
            "total_goals_at_half_time": api_match.get("total_goals_at_half_time", -1),
            "home_team_goal_count_half_time": api_match.get("home_team_goal_count_half_time", -1),
            "away_team_goal_count_half_time": api_match.get("away_team_goal_count_half_time", -1),
            # Goal timings
            "home_team_goal_timings": api_match.get("home_team_goal_timings", ""),
            "away_team_goal_timings": api_match.get("away_team_goal_timings", ""),
            "home_team_corner_count": api_match.get("team_a_corners", -1),
            "away_team_corner_count": api_match.get("team_b_corners", -1),
            "home_team_possession": api_match.get("team_a_possession", -1),
            "away_team_possession": api_match.get("team_b_possession", -1),
            "home_team_shots": api_match.get("team_a_shots", -1),
            "away_team_shots": api_match.get("team_b_shots", -1),
            "home_team_shots_on_target": api_match.get("team_a_shotsOnTarget", -1),
            "away_team_shots_on_target": api_match.get("team_b_shotsOnTarget", -1),
            "home_team_yellow_cards": api_match.get("team_a_yellow_cards", -1),
            "away_team_yellow_cards": api_match.get("team_b_yellow_cards", -1),
            "home_team_red_cards": api_match.get("team_a_red_cards", -1),
            "away_team_red_cards": api_match.get("team_b_red_cards", -1),
            # Card splits by half
            "home_team_first_half_cards": api_match.get("home_team_first_half_cards", -1),
            "away_team_first_half_cards": api_match.get("away_team_first_half_cards", -1),
            "home_team_second_half_cards": api_match.get("home_team_second_half_cards", -1),
            "away_team_second_half_cards": api_match.get("away_team_second_half_cards", -1),
            "home_team_fouls": api_match.get("team_a_fouls", -1),
            "away_team_fouls": api_match.get("team_b_fouls", -1),
            "home_team_offsides": api_match.get("team_a_offsides", -1),
            "away_team_offsides": api_match.get("team_b_offsides", -1),
            "home_team_shots_off_target": api_match.get("team_a_shotsOffTarget", -1),
            "away_team_shots_off_target": api_match.get("team_b_shotsOffTarget", -1),
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
            "odds_btts_no": api_match.get("odds_btts_no", 0.0),
            "competition_id": api_match.get("competition_id"),
            "game_week": api_match.get("game_week"),
            "stadium": api_match.get("stadium_name", ""),
            "stadium_location": api_match.get("stadium_location", ""),
        }

    @staticmethod
    def map_team_to_internal(api_team: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um objeto de time da API para o formato esperado pelo backend.

        Maps real FootyStats league-teams field names (cardsAVG_overall, foulsAVG_overall, etc.)
        to the internal column names expected by fixtures_service helper functions.
        """
        stats = api_team.get("stats", {}) or {}

        def _pick(primary_keys: list, fallback_keys: list = None, default=None):
            """Try stats dict first, then api_team root."""
            for key in primary_keys:
                val = stats.get(key)
                if val is not None:
                    return val
            for key in (fallback_keys or []):
                val = api_team.get(key)
                if val is not None:
                    return val
            return default

        return {
            "team_name": api_team.get("name") or api_team.get("cleanName"),
            "common_name": api_team.get("cleanName"),
            "season": api_team.get("season"),
            "country": api_team.get("country"),
            # --- Record / Form (Team CSV: 186) ---
            "matches_played": _pick(["matchesPlayed_overall"], ["matchesPlayed", "matches_played"], None),
            "wins": _pick(["wins_overall"], ["wins"], None),
            "wins_home": _pick(["wins_home"], default=None),
            "wins_away": _pick(["wins_away"], default=None),
            "draws": _pick(["draws_overall"], ["draws"], None),
            "losses": _pick(["losses_overall"], ["losses"], None),
            "win_percentage": _pick(["winPercentage_overall", "win_percentage_overall"], default=None),
            "draw_percentage": _pick(["drawPercentage_overall", "draw_percentage_overall"], default=None),
            "loss_percentage": _pick(["lossPercentage_overall", "loss_percentage_overall"], default=None),
            "league_position": _pick(["league_position_overall", "league_position"], ["table_position"], None),
            # PPG (Team CSV: 186 — points_per_game Total/Home/Away)
            "points_per_game": api_team.get("pointsPerGame", 0.0) or api_team.get("ppg", 0.0),
            "points_per_game_overall": _pick(["pointsPerGame_overall"], ["pointsPerGame", "ppg"], 0.0),
            "points_per_game_home": _pick(["pointsPerGame_home"], default=None),
            "points_per_game_away": _pick(["pointsPerGame_away"], default=None),
            # --- Goals (Team CSV: 186) ---
            "goals_scored": api_team.get("seasonGoals_overall", 0) or api_team.get("seasonGoals", 0),
            "goals_conceded": api_team.get("seasonConceded_overall", 0) or api_team.get("seasonConceded", 0),
            "goal_difference": _pick(["goalDifference_overall"], ["goal_difference"], None),
            "average_total_goals_per_match": _pick(
                ["averageTotalGoalsPerMatch_overall", "average_total_goals_per_match_overall"],
                default=None,
            ),
            "goals_scored_per_match_overall": _pick(
                ["seasonScoredAVG_overall", "seasonGoalsAVG_overall",
                 "goals_scored_per_match_overall"], default=None,
            ),
            "goals_scored_per_match_home": _pick(
                ["seasonScoredAVG_home", "seasonGoalsAVG_home",
                 "goals_scored_per_match_home"], default=None,
            ),
            "goals_scored_per_match_away": _pick(
                ["seasonScoredAVG_away", "seasonGoalsAVG_away",
                 "goals_scored_per_match_away"], default=None,
            ),
            "goals_conceded_per_match_overall": _pick(
                ["seasonConcededAVG_overall", "goals_conceded_per_match_overall"], default=None,
            ),
            "goals_conceded_per_match_home": _pick(
                ["seasonConcededAVG_home", "goals_conceded_per_match_home"], default=None,
            ),
            "goals_conceded_per_match_away": _pick(
                ["seasonConcededAVG_away", "goals_conceded_per_match_away"], default=None,
            ),
            "minutes_per_goal_scored": _pick(["minutesPerGoalScored_overall"], default=None),
            "minutes_per_goal_conceded": _pick(["minutesPerGoalConceded_overall"], default=None),
            # --- Half-time goals (Team CSV: 186) ---
            "goals_scored_half_time": _pick(["goals_scored_half_time_overall", "seasonGoalsHT_overall"], default=None),
            "goals_conceded_half_time": _pick(["goals_conceded_half_time_overall", "seasonConcededHT_overall"], default=None),
            "goals_scored_per_match_half_time": _pick(
                ["goals_scored_per_match_half_time_overall", "seasonScoredAVGHT_overall"], default=None,
            ),
            "goals_conceded_per_match_half_time": _pick(
                ["goals_conceded_per_match_half_time_overall", "seasonConcededAVGHT_overall"], default=None,
            ),
            # --- Clean sheets / BTTS / FTS (Team CSV: 186 — critical for prediction) ---
            "clean_sheets": _pick(["cleanSheets_overall", "clean_sheets_overall"], default=None),
            "clean_sheet_percentage": _pick(
                ["cleanSheetPercentage_overall", "clean_sheet_percentage_overall"], default=None,
            ),
            "btts_count": _pick(["bttsCount_overall", "btts_count_overall"], default=None),
            "btts_percentage": _pick(
                ["bttsPercentage_overall", "btts_percentage_overall"], default=None,
            ),
            "fts_count": _pick(["ftsCount_overall", "fts_count_overall"], default=None),
            "fts_percentage": _pick(
                ["ftsPercentage_overall", "fts_percentage_overall"], default=None,
            ),
            "first_team_to_score_percentage": _pick(
                ["firstTeamToScorePercentage_overall", "first_team_to_score_percentage_overall"], default=None,
            ),
            # --- Over/Under percentages (Team CSV: 186 — directly relevant for markets!) ---
            "over05_percentage": _pick(["over05Percentage_overall", "over05_percentage_overall"], default=None),
            "over15_percentage": _pick(["over15Percentage_overall", "over15_percentage_overall"], default=None),
            "over25_percentage": _pick(["over25Percentage_overall", "over25_percentage_overall"], default=None),
            "over35_percentage": _pick(["over35Percentage_overall", "over35_percentage_overall"], default=None),
            "over45_percentage": _pick(["over45Percentage_overall", "over45_percentage_overall"], default=None),
            "under15_percentage": _pick(["under15Percentage_overall", "under15_percentage_overall"], default=None),
            "under25_percentage": _pick(["under25Percentage_overall", "under25_percentage_overall"], default=None),
            # --- Possession (Team CSV: 186) ---
            "average_possession": _pick(
                ["possessionAVG_overall", "average_possession_overall"],
                ["average_possession", "possessionAVG"],
                None,
            ),
            "average_possession_home": _pick(["possessionAVG_home", "average_possession_home"], default=None),
            "average_possession_away": _pick(["possessionAVG_away", "average_possession_away"], default=None),
            # --- Corners (Team CSV: 186 + Pt.2: 442) ---
            "corners_per_match": _pick(
                ["cornersAVG_overall", "corners_per_match_overall"],
                ["cornersAVG", "corners_per_match"],
                None,
            ),
            "corners_per_match_home": _pick(["cornersAVG_home", "corners_per_match_home"], default=None),
            "corners_per_match_away": _pick(["cornersAVG_away", "corners_per_match_away"], default=None),
            "corners_total": _pick(["cornersTotal_overall", "corners_total_overall"], default=None),
            # Pt.2: corners against (opponent corners)
            "corners_against_per_match": _pick(
                ["cornersAgainstAVG_overall", "corners_against_per_match_overall"], default=None,
            ),
            "corners_against_per_match_home": _pick(["cornersAgainstAVG_home", "corners_against_per_match_home"], default=None),
            "corners_against_per_match_away": _pick(["cornersAgainstAVG_away", "corners_against_per_match_away"], default=None),
            # Pt.2: corner over percentages (for corner markets)
            "over85_corners_percentage": _pick(
                ["over85CornersPercentage_overall", "over85_corners_percentage_overall"], default=None,
            ),
            "over95_corners_percentage": _pick(
                ["over95CornersPercentage_overall", "over95_corners_percentage_overall"], default=None,
            ),
            "over105_corners_percentage": _pick(
                ["over105CornersPercentage_overall", "over105_corners_percentage_overall"], default=None,
            ),
            # --- Cards (Team CSV: 186 + Pt.2: 442) ---
            "cards_per_match": _pick(
                ["cardsAVG_overall", "cards_per_match_overall"],
                ["cardsAVG", "cards_per_match"],
                None,
            ),
            "cards_per_match_home": _pick(["cardsAVG_home", "cards_per_match_home"], default=None),
            "cards_per_match_away": _pick(["cardsAVG_away", "cards_per_match_away"], default=None),
            "cards_total": _pick(["cardsTotal_overall", "cards_total_overall"], default=None),
            # --- Shots (Team CSV: 186 + Pt.2: 442) ---
            "shots_per_match": _pick(
                ["shotsAVG_overall", "shots_per_match_overall"],
                ["shotsAVG", "shots_per_match"],
                None,
            ),
            "shots_per_match_home": _pick(["shotsAVG_home", "shots_per_match_home"], default=None),
            "shots_per_match_away": _pick(["shotsAVG_away", "shots_per_match_away"], default=None),
            "shots_on_target_per_match": _pick(
                ["shotsOnTargetAVG_overall", "shots_on_target_per_match_overall"],
                ["shotsOnTargetAVG", "shots_on_target_per_match"],
                None,
            ),
            "shots_on_target_per_match_home": _pick(["shotsOnTargetAVG_home", "shots_on_target_per_match_home"], default=None),
            "shots_on_target_per_match_away": _pick(["shotsOnTargetAVG_away", "shots_on_target_per_match_away"], default=None),
            "shots_off_target_per_match": _pick(
                ["shotsOffTargetAVG_overall", "shots_off_target_per_match_overall"], default=None,
            ),
            # --- Fouls (Pt.2: 442) ---
            "fouls_per_match": _pick(
                ["foulsAVG_overall", "fouls_per_match_overall"],
                ["foulsAVG", "fouls_per_match"],
                None,
            ),
            "fouls_per_match_home": _pick(["foulsAVG_home", "fouls_per_match_home"], default=None),
            "fouls_per_match_away": _pick(["foulsAVG_away", "fouls_per_match_away"], default=None),
            "fouls_total": _pick(["foulsTotal_overall", "fouls_by_this_team_overall", "fouls_total_overall"], default=None),
            # --- Offsides (Pt.2: 442) ---
            "offsides_per_match": _pick(["offsidesAVG_overall", "offsidesTeamAVG_overall"], default=None),
            # --- xG (Team CSV: 186) ---
            "xg_for_avg": _pick(
                ["xg_for_avg_overall", "xgForAVG_overall", "xg_for_avg"],
                default=None,
            ),
            "xg_for_avg_home": _pick(["xg_for_avg_home", "xgForAVG_home"], default=None),
            "xg_for_avg_away": _pick(["xg_for_avg_away", "xgForAVG_away"], default=None),
            "xg_against_avg": _pick(
                ["xg_against_avg_overall", "xgAgainstAVG_overall", "xg_against_avg"],
                default=None,
            ),
            "xg_against_avg_home": _pick(["xg_against_avg_home", "xgAgainstAVG_home"], default=None),
            "xg_against_avg_away": _pick(["xg_against_avg_away", "xgAgainstAVG_away"], default=None),
            # --- Prediction Risk (Team CSV: 186) ---
            "prediction_risk": _pick(["predictionRisk_overall", "prediction_risk_overall"], default=None),
            # --- 2nd half (Pt.2: 442) ---
            "goals_scored_2h_per_match": _pick(["goals_scored_2h_per_match_overall"], default=None),
            "goals_conceded_2h_per_match": _pick(["goals_conceded_2h_per_match_overall"], default=None),
            "average_total_goals_2h_per_match": _pick(["average_total_goals_2h_per_match_overall"], default=None),
            "btts_2h_percentage": _pick(["btts_2h_percentage_overall"], default=None),
            # --- BTTS compound (Pt.2: 442) ---
            "btts_and_win_percentage": _pick(
                ["BTTS_and_win_percentage_overall", "btts_and_win_percentage_overall"], default=None,
            ),
            "scored_both_halves_percentage": _pick(
                ["scoredBothHalvesPercentage_overall", "scored_both_halves_percentage_overall"], default=None,
            ),
            # --- Home advantage (Team CSV: 186) ---
            "home_advantage_percentage": _pick(
                ["homeAdvantagePercentage_home", "home_advantage_percentage_home",
                 "homeAdvantagePercentage", "home_advantage_percentage"], default=None,
            ),
            # --- Goal timings (Team CSV: 186) — goals per 10-min interval ---
            "goals_scored_min_0_to_10": _pick(["goals_scored_min_0_to_10_overall"], default=None),
            "goals_scored_min_11_to_20": _pick(["goals_scored_min_11_to_20_overall"], default=None),
            "goals_scored_min_21_to_30": _pick(["goals_scored_min_21_to_30_overall"], default=None),
            "goals_scored_min_31_to_40": _pick(["goals_scored_min_31_to_40_overall"], default=None),
            "goals_scored_min_41_to_50": _pick(["goals_scored_min_41_to_50_overall"], default=None),
            "goals_scored_min_51_to_60": _pick(["goals_scored_min_51_to_60_overall"], default=None),
            "goals_scored_min_61_to_70": _pick(["goals_scored_min_61_to_70_overall"], default=None),
            "goals_scored_min_71_to_80": _pick(["goals_scored_min_71_to_80_overall"], default=None),
            "goals_scored_min_81_to_90": _pick(["goals_scored_min_81_to_90_overall"], default=None),
            "goals_conceded_min_0_to_10": _pick(["goals_conceded_min_0_to_10_overall"], default=None),
            "goals_conceded_min_81_to_90": _pick(["goals_conceded_min_81_to_90_overall"], default=None),
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
        mapped_teams = []
        for i, t in enumerate(api_teams):
            try:
                mapped_teams.append(cls.map_team_to_internal(t))
            except Exception as exc:
                logger.warning("[DataMapper] Skipping malformed team record #%d: %s", i, exc)
        return pd.DataFrame(mapped_teams)
