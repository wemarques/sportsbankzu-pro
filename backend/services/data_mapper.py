from typing import Dict, Any, List, Optional
import pandas as pd
import logging

logger = logging.getLogger("sportsbank.mapper")

class DataMapper:
    """Traduz dados da API FootyStats para o formato interno baseado nos layouts CSV."""

    @staticmethod
    def map_match_to_internal(api_match: Dict[str, Any]) -> Dict[str, Any]:
        """Converte um objeto de partida da API para o formato esperado pelo backend."""
        # Mapeamento básico baseado no Match CSV - 64 Data Columns
        return {
            "id": api_match.get("id"),
            "timestamp": api_match.get("date_unix"),
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
            "over_25_percentage_pre_match": api_match.get("o25_potential", 0),
            "home_ppg": api_match.get("home_ppg", 0.0),
            "away_ppg": api_match.get("away_ppg", 0.0),
            "odds_ft_home_team_win": api_match.get("odds_ft_1", 0.0),
            "odds_ft_draw": api_match.get("odds_ft_x", 0.0),
            "odds_ft_away_team_win": api_match.get("odds_ft_2", 0.0),
            "odds_ft_over25": api_match.get("odds_ft_over25", 0.0),
            "odds_btts_yes": api_match.get("odds_btts_yes", 0.0),
            "competition_id": api_match.get("competition_id"),
            "game_week": api_match.get("game_week"),
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
        """Converte uma lista de partidas da API em um DataFrame formatado como o CSV."""
        mapped_matches = [cls.map_match_to_internal(m) for m in api_matches]
        return pd.DataFrame(mapped_matches)

    @classmethod
    def teams_to_df(cls, api_teams: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converte uma lista de times da API em um DataFrame formatado como o CSV."""
        mapped_teams = [cls.map_team_to_internal(t) for t in api_teams]
        return pd.DataFrame(mapped_teams)
