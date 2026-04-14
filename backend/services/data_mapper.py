from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pandas as pd
import logging
from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger("sportsbankzu.mapper")


def sanitize_api_value(val: Any, *, treat_minus2: bool = False) -> Any:
    """Normalize FootyStats sentinel values to None.

    The FootyStats API uses -1 (and -2 for total shots) to indicate
    "data not available".  This helper converts those sentinels to None
    so downstream code never sees fake negative stats.

    Args:
        val: raw value from the API.
        treat_minus2: if True, also treat -2 as unavailable (for shots fields).
    """
    if val is None:
        return None
    try:
        numeric = float(val)
    except (ValueError, TypeError):
        return val
    if numeric == -1:
        return None
    if treat_minus2 and numeric == -2:
        return None
    return val


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
    btts_potential: Optional[float] = None
    o15_potential: Optional[float] = None
    o25_potential: Optional[float] = None
    o35_potential: Optional[float] = None
    o45_potential: Optional[float] = None
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
    odds_ft_under25: Optional[float] = 0.0
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

        _s = sanitize_api_value
        _s2 = lambda v: sanitize_api_value(v, treat_minus2=True)

        # Goal counts: sanitize -1 (API sentinel for "no data") to None
        home_goals = _s(api_match.get("homeGoalCount"))
        away_goals = _s(api_match.get("awayGoalCount"))
        total_goals = _s(api_match.get("totalGoalCount"))

        return {
            "id": api_match.get("id"),
            "timestamp": date_unix,
            "date_gmt": date_gmt,
            "status": api_match.get("status"),
            "team_a_name": api_match.get("home_name") or api_match.get("homeID"),
            "team_b_name": api_match.get("away_name") or api_match.get("awayID"),
            "attendance": _s(api_match.get("attendance", -1)),
            "referee": api_match.get("referee") or api_match.get("refree"),
            "home_team_goal_count": home_goals,
            "away_team_goal_count": away_goals,
            "total_goal_count": total_goals,
            # Half-time
            "total_goals_at_half_time": _s(api_match.get("total_goals_at_half_time", -1)),
            "home_team_goal_count_half_time": _s(api_match.get("home_team_goal_count_half_time", -1)),
            "away_team_goal_count_half_time": _s(api_match.get("away_team_goal_count_half_time", -1)),
            # Goal timings
            "home_team_goal_timings": api_match.get("home_team_goal_timings", ""),
            "away_team_goal_timings": api_match.get("away_team_goal_timings", ""),
            "home_team_corner_count": _s(api_match.get("team_a_corners", -1)),
            "away_team_corner_count": _s(api_match.get("team_b_corners", -1)),
            "home_team_possession": _s(api_match.get("team_a_possession", -1)),
            "away_team_possession": _s(api_match.get("team_b_possession", -1)),
            "home_team_shots": _s2(api_match.get("team_a_shots", -2)),
            "away_team_shots": _s2(api_match.get("team_b_shots", -2)),
            "home_team_shots_on_target": _s(api_match.get("team_a_shotsOnTarget", -1)),
            "away_team_shots_on_target": _s(api_match.get("team_b_shotsOnTarget", -1)),
            "home_team_yellow_cards": _s(api_match.get("team_a_yellow_cards", -1)),
            "away_team_yellow_cards": _s(api_match.get("team_b_yellow_cards", -1)),
            "home_team_red_cards": _s(api_match.get("team_a_red_cards", -1)),
            "away_team_red_cards": _s(api_match.get("team_b_red_cards", -1)),
            # Card splits by half
            "home_team_first_half_cards": _s(api_match.get("home_team_first_half_cards", -1)),
            "away_team_first_half_cards": _s(api_match.get("away_team_first_half_cards", -1)),
            "home_team_second_half_cards": _s(api_match.get("home_team_second_half_cards", -1)),
            "away_team_second_half_cards": _s(api_match.get("away_team_second_half_cards", -1)),
            "home_team_fouls": _s(api_match.get("team_a_fouls", -1)),
            "away_team_fouls": _s(api_match.get("team_b_fouls", -1)),
            "home_team_offsides": _s(api_match.get("team_a_offsides", -1)),
            "away_team_offsides": _s(api_match.get("team_b_offsides", -1)),
            "home_team_shots_off_target": _s(api_match.get("team_a_shotsOffTarget", -1)),
            "away_team_shots_off_target": _s(api_match.get("team_b_shotsOffTarget", -1)),
            "home_team_xg": api_match.get("team_a_xg") or None,  # #128c: None not 0.0
            "away_team_xg": api_match.get("team_b_xg") or None,  # #128c: None not 0.0
            "btts_percentage_pre_match": api_match.get("btts_potential") or None,
            "over_15_percentage_pre_match": api_match.get("o15_potential") or None,
            "over_25_percentage_pre_match": api_match.get("o25_potential") or None,
            "over_35_percentage_pre_match": api_match.get("o35_potential") or None,
            "over_45_percentage_pre_match": api_match.get("o45_potential") or None,
            # Corner potentials (pre-match probabilities)
            "corners_potential": api_match.get("corners_potential"),
            "corners_o85_potential": api_match.get("corners_o85_potential"),
            "corners_o95_potential": api_match.get("corners_o95_potential"),
            "corners_o105_potential": api_match.get("corners_o105_potential"),
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
            "odds_ft_under25": api_match.get("odds_ft_under25", 0.0),
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

        # ============================================================
        # CANONICAL FOOTYSTATS FIELD NAMES — #139 (fix sistemico de #138)
        # ============================================================
        # Fonte: documentacao oficial /league-teams + /team + /lastx
        # https://footystats.org/api/documentations/league-teams
        #
        # Convencao: para CADA campo, primario = chave canonica oficial,
        # fallbacks = chaves alternativas / endpoints secundarios / legados.
        # NUNCA inverter a ordem sem revalidar contra a doc.
        # ============================================================

        return {
            # #142 — preserve FootyStats team id for /lastx (recent-form) lookups
            "team_id": api_team.get("id"),
            "team_name": api_team.get("name") or api_team.get("cleanName"),
            "common_name": api_team.get("cleanName"),
            "season": api_team.get("season"),
            "country": api_team.get("country"),
            # --- Record / Form (FootyStats /league-teams stats block) ---
            # Doc: seasonMatchesPlayed_overall (NAO matchesPlayed_overall — esse era o bug #138)
            "matches_played": _pick(
                ["seasonMatchesPlayed_overall"],
                ["matchesPlayed_overall", "matchesPlayed", "matches_played"],
                None,
            ),
            "matches_played_home": _pick(
                ["seasonMatchesPlayed_home"], ["matchesPlayed_home"], None,
            ),
            "matches_played_away": _pick(
                ["seasonMatchesPlayed_away"], ["matchesPlayed_away"], None,
            ),
            "wins": _pick(
                ["seasonWinsNum_overall"],
                ["wins_overall", "seasonWins_overall", "wins"],
                None,
            ),
            "wins_home": _pick(
                ["seasonWinsNum_home"], ["wins_home"], None,
            ),
            "wins_away": _pick(
                ["seasonWinsNum_away"], ["wins_away"], None,
            ),
            "draws": _pick(
                ["seasonDrawsNum_overall"],
                ["draws_overall", "seasonDraws_overall", "draws"],
                None,
            ),
            "draws_home": _pick(["seasonDrawsNum_home"], ["draws_home"], None),
            "draws_away": _pick(["seasonDrawsNum_away"], ["draws_away"], None),
            "losses": _pick(
                ["seasonLossesNum_overall"],
                ["losses_overall", "seasonLosses_overall", "losses"],
                None,
            ),
            "losses_home": _pick(["seasonLossesNum_home"], ["losses_home"], None),
            "losses_away": _pick(["seasonLossesNum_away"], ["losses_away"], None),
            # Doc: winPercentage_overall / drawPercentage_overall / losePercentage_overall
            # Atencao: 'lose' (NAO 'loss') no nome canonico
            "win_percentage": _pick(
                ["winPercentage_overall"],
                ["win_percentage_overall", "win_percentage"],
                None,
            ),
            "win_percentage_home": _pick(["winPercentage_home"], default=None),
            "win_percentage_away": _pick(["winPercentage_away"], default=None),
            "draw_percentage": _pick(
                ["drawPercentage_overall"],
                ["draw_percentage_overall", "draw_percentage"],
                None,
            ),
            "loss_percentage": _pick(
                ["losePercentage_overall"],
                ["lossPercentage_overall", "loss_percentage_overall", "loss_percentage"],
                None,
            ),
            "league_position": _pick(
                ["league_position_overall", "league_position"],
                ["table_position", "performance_rank"],
                None,
            ),
            # PPG: doc canonica = seasonPPG_*
            "points_per_game": api_team.get("seasonPPG_overall")
                or api_team.get("pointsPerGame", 0.0)
                or api_team.get("ppg", 0.0),
            "points_per_game_overall": _pick(
                ["seasonPPG_overall"],
                ["pointsPerGame_overall", "pointsPerGame", "ppg"],
                0.0,
            ),
            "points_per_game_home": _pick(
                ["seasonPPG_home"], ["pointsPerGame_home"], None,
            ),
            "points_per_game_away": _pick(
                ["seasonPPG_away"], ["pointsPerGame_away"], None,
            ),
            "points_per_game_recent": _pick(["seasonRecentPPG"], default=None),
            # --- Goals (canonico: seasonGoals_overall em stats block) ---
            # IMPORTANTE: ate #138 isto buscava em api_team root, nao em stats.
            # /league-teams retorna esses campos DENTRO de stats.
            "goals_scored": _pick(
                ["seasonGoals_overall", "seasonScoredNum_overall"],
                ["seasonGoals", "goals_scored"],
                0,
            ),
            "goals_scored_home": _pick(
                ["seasonScoredNum_home"], ["seasonGoals_home"], None,
            ),
            "goals_scored_away": _pick(
                ["seasonScoredNum_away"], ["seasonGoals_away"], None,
            ),
            "goals_conceded": _pick(
                ["seasonConceded_overall", "seasonConcededNum_overall"],
                ["seasonConceded", "goals_conceded"],
                0,
            ),
            "goals_conceded_home": _pick(
                ["seasonConcededNum_home"], ["seasonConceded_home"], None,
            ),
            "goals_conceded_away": _pick(
                ["seasonConcededNum_away"], ["seasonConceded_away"], None,
            ),
            "goal_difference": _pick(
                ["seasonGoalDifference_overall"],
                ["goalDifference_overall", "goal_difference"],
                None,
            ),
            "goal_difference_home": _pick(["seasonGoalDifference_home"], default=None),
            "goal_difference_away": _pick(["seasonGoalDifference_away"], default=None),
            # Media total de gols (marcados+sofridos): canonico = seasonAVG_*
            "average_total_goals_per_match": _pick(
                ["seasonAVG_overall"],
                ["averageTotalGoalsPerMatch_overall", "average_total_goals_per_match_overall"],
                None,
            ),
            "average_total_goals_per_match_home": _pick(["seasonAVG_home"], default=None),
            "average_total_goals_per_match_away": _pick(["seasonAVG_away"], default=None),
            # Media de gols MARCADOS: canonico = seasonScoredAVG_*
            "goals_scored_per_match_overall": _pick(
                ["seasonScoredAVG_overall"],
                ["seasonGoalsAVG_overall", "goals_scored_per_match_overall"],
                None,
            ),
            "goals_scored_per_match_home": _pick(
                ["seasonScoredAVG_home"],
                ["seasonGoalsAVG_home", "goals_scored_per_match_home"],
                None,
            ),
            "goals_scored_per_match_away": _pick(
                ["seasonScoredAVG_away"],
                ["seasonGoalsAVG_away", "goals_scored_per_match_away"],
                None,
            ),
            # Media de gols SOFRIDOS: canonico = seasonConcededAVG_*
            "goals_conceded_per_match_overall": _pick(
                ["seasonConcededAVG_overall"],
                ["goals_conceded_per_match_overall"],
                None,
            ),
            "goals_conceded_per_match_home": _pick(
                ["seasonConcededAVG_home"],
                ["goals_conceded_per_match_home"],
                None,
            ),
            "goals_conceded_per_match_away": _pick(
                ["seasonConcededAVG_away"],
                ["goals_conceded_per_match_away"],
                None,
            ),
            # Minutes per goal: doc /team usa seasonGoalsMin_overall
            "minutes_per_goal_scored": _pick(
                ["seasonGoalsMin_overall"], ["minutesPerGoalScored_overall"], None,
            ),
            "minutes_per_goal_conceded": _pick(
                ["seasonConcededMin_overall"], ["minutesPerGoalConceded_overall"], None,
            ),
            # --- Half-time goals (canonico: scoredGoalsHT_*, concededGoalsHT_*, scoredAVGHT_*) ---
            "goals_scored_half_time": _pick(
                ["scoredGoalsHT_overall"],
                ["seasonGoalsHT_overall", "goals_scored_half_time_overall"],
                None,
            ),
            "goals_conceded_half_time": _pick(
                ["concededGoalsHT_overall"],
                ["seasonConcededHT_overall", "goals_conceded_half_time_overall"],
                None,
            ),
            "goals_scored_per_match_half_time": _pick(
                ["scoredAVGHT_overall"],
                ["seasonScoredAVGHT_overall", "goals_scored_per_match_half_time_overall"],
                None,
            ),
            "goals_conceded_per_match_half_time": _pick(
                ["concededAVGHT_overall"],
                ["seasonConcededAVGHT_overall", "goals_conceded_per_match_half_time_overall"],
                None,
            ),
            "average_total_goals_per_match_half_time": _pick(
                ["AVGHT_overall"], default=None,
            ),
            # --- Clean sheets / BTTS / FTS (CRITICOS PARA PREDICAO) ---
            # Doc canonica: seasonCS_overall, seasonCSPercentage_overall
            "clean_sheets": _pick(
                ["seasonCS_overall"],
                ["cleanSheets_overall", "clean_sheets_overall", "cleanSheets"],
                None,
            ),
            "clean_sheets_home": _pick(["seasonCS_home"], default=None),
            "clean_sheets_away": _pick(["seasonCS_away"], default=None),
            "clean_sheet_percentage": _pick(
                ["seasonCSPercentage_overall"],
                ["cleanSheetPercentage_overall", "clean_sheet_percentage_overall"],
                None,
            ),
            "clean_sheet_percentage_home": _pick(["seasonCSPercentage_home"], default=None),
            "clean_sheet_percentage_away": _pick(["seasonCSPercentage_away"], default=None),
            # BTTS: canonico = seasonBTTS_overall, seasonBTTSPercentage_overall
            "btts_count": _pick(
                ["seasonBTTS_overall"],
                ["bttsCount_overall", "btts_count_overall"],
                None,
            ),
            "btts_percentage": _pick(
                ["seasonBTTSPercentage_overall"],
                ["bttsPercentage_overall", "btts_percentage_overall"],
                None,
            ),
            "btts_percentage_home": _pick(["seasonBTTSPercentage_home"], default=None),
            "btts_percentage_away": _pick(["seasonBTTSPercentage_away"], default=None),
            # FTS: canonico = seasonFTS_overall, seasonFTSPercentage_overall
            "fts_count": _pick(
                ["seasonFTS_overall"],
                ["ftsCount_overall", "fts_count_overall"],
                None,
            ),
            "fts_percentage": _pick(
                ["seasonFTSPercentage_overall"],
                ["ftsPercentage_overall", "fts_percentage_overall"],
                None,
            ),
            "first_team_to_score_percentage": _pick(
                ["firstTeamToScorePercentage_overall", "first_team_to_score_percentage_overall"],
                default=None,
            ),
            # --- Over/Under percentages (CRITICO para mercados) ---
            # Doc canonica: seasonOver*Percentage_overall, seasonUnder*Percentage_overall
            "over05_percentage": _pick(
                ["seasonOver05Percentage_overall"],
                ["over05Percentage_overall", "over05_percentage_overall"],
                None,
            ),
            "over15_percentage": _pick(
                ["seasonOver15Percentage_overall"],
                ["over15Percentage_overall", "over15_percentage_overall"],
                None,
            ),
            "over25_percentage": _pick(
                ["seasonOver25Percentage_overall"],
                ["over25Percentage_overall", "over25_percentage_overall"],
                None,
            ),
            "over35_percentage": _pick(
                ["seasonOver35Percentage_overall"],
                ["over35Percentage_overall", "over35_percentage_overall"],
                None,
            ),
            "over45_percentage": _pick(
                ["seasonOver45Percentage_overall"],
                ["over45Percentage_overall", "over45_percentage_overall"],
                None,
            ),
            "over55_percentage": _pick(
                ["seasonOver55Percentage_overall"], default=None,
            ),
            "under05_percentage": _pick(["seasonUnder05Percentage_overall"], default=None),
            "under15_percentage": _pick(
                ["seasonUnder15Percentage_overall"],
                ["under15Percentage_overall", "under15_percentage_overall"],
                None,
            ),
            "under25_percentage": _pick(
                ["seasonUnder25Percentage_overall"],
                ["under25Percentage_overall", "under25_percentage_overall"],
                None,
            ),
            "under35_percentage": _pick(["seasonUnder35Percentage_overall"], default=None),
            "under45_percentage": _pick(["seasonUnder45Percentage_overall"], default=None),
            # --- Possession ---
            # NAO documentado em /league-teams oficial; mantido como best-effort.
            "average_possession": _pick(
                ["possessionAVG_overall", "average_possession_overall"],
                ["average_possession", "possessionAVG"],
                None,
            ),
            "average_possession_home": _pick(
                ["possessionAVG_home"], ["average_possession_home"], None,
            ),
            "average_possession_away": _pick(
                ["possessionAVG_away"], ["average_possession_away"], None,
            ),
            # --- Corners ---
            # #145: cornersRecorded_matches_* is the NUMBER OF MATCHES with
            # corner data, NOT the average corners per match.  Previous mapping
            # used it as primary key for corners_per_match which inflated the
            # corners engine projection (e.g. 41 instead of ~5).
            # Correct source: cornersAVG_overall (league-season level) or
            # derive from corners_total_avg - corners_against_per_match.
            "corners_per_match": _pick(
                ["cornersAVG_overall", "corners_per_match_overall",
                 "cornersAVG", "corners_per_match"],
                default=None,
            ),
            "corners_per_match_home": _pick(
                ["cornersAVG_home", "corners_per_match_home"],
                default=None,
            ),
            "corners_per_match_away": _pick(
                ["cornersAVG_away", "corners_per_match_away"],
                default=None,
            ),
            "corners_total": _pick(
                ["cornersTotal_overall", "corners_total_overall"], default=None,
            ),
            # Corners against: NAO existe campo direto em /league-teams.
            # Derivado por #124 a partir de fallback historico (cornersAgainst*).
            "corners_against_per_match": _pick(
                ["cornersAgainstAVG_overall", "corners_against_per_match_overall",
                 "seasonCornersAgainst_overall", "seasonCornersAgainstAVG_overall"],
                default=None,
            ),
            "corners_against_per_match_home": _pick(
                ["cornersAgainstAVG_home", "corners_against_per_match_home",
                 "seasonCornersAgainst_home", "seasonCornersAgainstAVG_home"],
                default=None,
            ),
            "corners_against_per_match_away": _pick(
                ["cornersAgainstAVG_away", "corners_against_per_match_away",
                 "seasonCornersAgainst_away", "seasonCornersAgainstAVG_away"],
                default=None,
            ),
            # #131: Corner TOTAL averages (corners totais do jogo = for + against)
            # Nao documentado oficialmente; provavel chave do plano premium.
            "corners_total_avg_overall": _pick(
                ["cornersTotalAVG_overall", "corners_total_avg_overall"], default=None,
            ),
            "corners_total_avg_home": _pick(
                ["cornersTotalAVG_home", "corners_total_avg_home"], default=None,
            ),
            "corners_total_avg_away": _pick(
                ["cornersTotalAVG_away", "corners_total_avg_away"], default=None,
            ),
            # Sample size for confidence
            "corners_recorded_matches_overall": _pick(
                ["cornersRecorded_matches_overall", "corners_recorded_matches_overall"],
                default=None,
            ),
            # Corner over percentages — doc /league-teams confirma ate 13.5
            "over65_corners_percentage": _pick(
                ["over65CornersPercentage_overall"], default=None,
            ),
            "over75_corners_percentage": _pick(
                ["over75CornersPercentage_overall"], default=None,
            ),
            "over85_corners_percentage": _pick(
                ["over85CornersPercentage_overall"], default=None,
            ),
            "over95_corners_percentage": _pick(
                ["over95CornersPercentage_overall"], default=None,
            ),
            "over105_corners_percentage": _pick(
                ["over105CornersPercentage_overall"], default=None,
            ),
            "over115_corners_percentage": _pick(
                ["over115CornersPercentage_overall"], default=None,
            ),
            "over125_corners_percentage": _pick(
                ["over125CornersPercentage_overall"], default=None,
            ),
            "over135_corners_percentage": _pick(
                ["over135CornersPercentage_overall"], default=None,
            ),
            # Compat: 14.5 nao existe na doc oficial; manter como None com fallback legado
            "over145_corners_percentage": _pick(
                ["over145CornersPercentage_overall"], default=None,
            ),
            # --- Cards ---
            # ATENCAO: NAO existe cardsAVG_overall em team-level /league-teams
            # (vive so em /league-season league-level — esse era um dos sintomas de #137).
            # Doc /league-teams expoe SOMENTE os buckets over*Cards*. Para obter media,
            # ev_classification deriva via cards_engine. Mantemos lookup com fallbacks
            # para o caso de o plano premium expor cardsAVG_overall.
            "cards_per_match": _pick(
                ["cardsAVG_overall"],
                ["cards_per_match_overall", "cardsAVG", "cards_per_match"],
                None,
            ),
            "cards_per_match_home": _pick(
                ["cardsAVG_home"], ["cards_per_match_home"], None,
            ),
            "cards_per_match_away": _pick(
                ["cardsAVG_away"], ["cards_per_match_away"], None,
            ),
            "cards_total": _pick(["cardsTotal_overall", "cards_total_overall"], default=None),
            # Cards against: idem corners — sem campo direto, derivado.
            "cards_against_per_match": _pick(
                ["cardsAgainstAVG_overall", "cards_against_avg_overall",
                 "seasonCardsAgainst_overall", "seasonCardsAgainstAVG_overall"],
                default=None,
            ),
            "cards_against_per_match_home": _pick(
                ["cardsAgainstAVG_home", "cards_against_avg_home",
                 "seasonCardsAgainst_home"], default=None,
            ),
            "cards_against_per_match_away": _pick(
                ["cardsAgainstAVG_away", "cards_against_avg_away",
                 "seasonCardsAgainst_away"], default=None,
            ),
            "cards_variance": _pick(
                ["cardsVariance_overall", "cards_variance_overall"], default=None,
            ),
            # Cards over-percentages — doc /league-teams confirma 0.5 ate 8.5
            "over05_cards_percentage": _pick(["over05CardsPercentage_overall"], default=None),
            "over15_cards_percentage": _pick(["over15CardsPercentage_overall"], default=None),
            "over25_cards_percentage": _pick(["over25CardsPercentage_overall"], default=None),
            "over35_cards_percentage": _pick(["over35CardsPercentage_overall"], default=None),
            "over45_cards_percentage": _pick(["over45CardsPercentage_overall"], default=None),
            "over55_cards_percentage": _pick(["over55CardsPercentage_overall"], default=None),
            "over65_cards_percentage": _pick(["over65CardsPercentage_overall"], default=None),
            "over75_cards_percentage": _pick(["over75CardsPercentage_overall"], default=None),
            "over85_cards_percentage": _pick(["over85CardsPercentage_overall"], default=None),
            # --- Shots ---
            # NAO existe em team-level /league-teams oficial. Vive so em /league-season.
            # Mantido como best-effort para planos premium / endpoints alternativos.
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
            "shots_on_target_per_match_home": _pick(
                ["shotsOnTargetAVG_home", "shots_on_target_per_match_home"], default=None,
            ),
            "shots_on_target_per_match_away": _pick(
                ["shotsOnTargetAVG_away", "shots_on_target_per_match_away"], default=None,
            ),
            "shots_off_target_per_match": _pick(
                ["shotsOffTargetAVG_overall", "shots_off_target_per_match_overall"], default=None,
            ),
            # --- Fouls ---
            # NAO existe em team-level /league-teams oficial. Best-effort apenas.
            "fouls_per_match": _pick(
                ["foulsAVG_overall", "fouls_per_match_overall"],
                ["foulsAVG", "fouls_per_match"],
                None,
            ),
            "fouls_per_match_home": _pick(["foulsAVG_home", "fouls_per_match_home"], default=None),
            "fouls_per_match_away": _pick(["foulsAVG_away", "fouls_per_match_away"], default=None),
            "fouls_total": _pick(
                ["foulsTotal_overall", "fouls_by_this_team_overall", "fouls_total_overall"],
                default=None,
            ),
            # --- Offsides ---
            # NAO existe em team-level /league-teams oficial. Best-effort.
            "offsides_per_match": _pick(
                ["offsidesAVG_overall", "offsidesTeamAVG_overall"], default=None,
            ),
            # --- xG ---
            # NAO documentado oficialmente em /league-teams.
            # Pode existir em planos premium ou ser derivado de /match.
            # Manter lookup com fallbacks; consumidor (xg_blend #128e) checa cobertura.
            "xg_for_avg": _pick(
                ["xg_for_avg_overall", "xgForAVG_overall", "xg_for_avg"], default=None,
            ),
            "xg_for_avg_home": _pick(["xg_for_avg_home", "xgForAVG_home"], default=None),
            "xg_for_avg_away": _pick(["xg_for_avg_away", "xgForAVG_away"], default=None),
            "xg_against_avg": _pick(
                ["xg_against_avg_overall", "xgAgainstAVG_overall", "xg_against_avg"],
                default=None,
            ),
            "xg_against_avg_home": _pick(["xg_against_avg_home", "xgAgainstAVG_home"], default=None),
            "xg_against_avg_away": _pick(["xg_against_avg_away", "xgAgainstAVG_away"], default=None),
            # --- Prediction Risk ---
            # Doc /team: campo canonico = 'risk' (NAO predictionRisk_overall)
            "prediction_risk": _pick(
                ["risk"],
                ["predictionRisk_overall", "prediction_risk_overall"],
                None,
            ),
            # --- 2nd half ---
            "goals_scored_2h_per_match": _pick(["goals_scored_2h_per_match_overall"], default=None),
            "goals_conceded_2h_per_match": _pick(["goals_conceded_2h_per_match_overall"], default=None),
            "average_total_goals_2h_per_match": _pick(["average_total_goals_2h_per_match_overall"], default=None),
            "btts_2h_percentage": _pick(["btts_2h_percentage_overall"], default=None),
            # --- BTTS compound ---
            "btts_and_win_percentage": _pick(
                ["BTTS_and_win_percentage_overall", "btts_and_win_percentage_overall"], default=None,
            ),
            "scored_both_halves_percentage": _pick(
                ["scoredBothHalvesPercentage_overall", "scored_both_halves_percentage_overall"],
                default=None,
            ),
            # --- Home advantage ---
            # Doc /league-teams: homeOverallAdvantage / homeAttackAdvantage / homeDefenceAdvantage
            # (NAO homeAdvantagePercentage_*)
            "home_advantage_overall": _pick(
                ["homeOverallAdvantage"],
                ["homeAdvantagePercentage_home", "home_advantage_percentage"],
                None,
            ),
            "home_advantage_attack": _pick(
                ["homeAttackAdvantage"],
                ["homeAttackAdvantagePercentage"],
                None,
            ),
            "home_advantage_defence": _pick(
                ["homeDefenceAdvantage"],
                ["homeDefenceAdvantagePercentage"],
                None,
            ),
            # Compat: chave legada usada por consumidores antigos
            "home_advantage_percentage": _pick(
                ["homeOverallAdvantage"],
                ["homeAdvantagePercentage_home", "home_advantage_percentage_home",
                 "homeAdvantagePercentage", "home_advantage_percentage"],
                None,
            ),
            # --- Goal timings (10-min interval) ---
            # ATENCAO: estes campos vivem em /league-season league-level (goals_min_*),
            # NAO em team-level /league-teams. Mantido com sufixo _overall para o caso
            # de plano premium; consumidor deve tolerar None.
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
