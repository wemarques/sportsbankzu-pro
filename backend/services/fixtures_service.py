from typing import Dict, Any, List, Optional, Tuple
import os
import logging
from datetime import datetime, timedelta
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None
from backend.services.util_service import status_map, parse_date, pick_column, compute_form
from backend.services.math_service import implied_probs, poisson_pmf, poisson_cdf
from backend.modeling.xg_filter import aplicar_filtro_completo
from backend.modeling.chaos_detector import detectar_caos_jogo

logger = logging.getLogger("sportsbank")

def build_records_from_matches(
    league_id: str,
    matches: "pd.DataFrame",
    teams: Optional["pd.DataFrame"],
    teams2: Optional["pd.DataFrame"],
    league_df: Optional["pd.DataFrame"],
    players: Optional["pd.DataFrame"],
    date_filter: str,
) -> List[Dict[str, Any]]:
    from backend.main import date_range, aggregate_team_xg, expected_goals_v2
    date_col = "date_gmt" if "date_gmt" in matches.columns else "date_GMT" if "date_GMT" in matches.columns else "timestamp"
    def row_date(r) -> Optional[datetime]:
        return parse_date(r.get(date_col))
    def filter_rows(start: datetime, end: datetime) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for _, r in matches.iterrows():
            dt = row_date(r)
            if dt is None:
                continue
            if not (start <= dt <= end):
                continue
            items.append(r)
        return items
    start, end = date_range(date_filter)
    rows = filter_rows(start, end)
    if not rows and date_filter in ("today", "tomorrow"):
        start, end = date_range("week")
        rows = filter_rows(start, end)
    if not rows and date_filter == "week":
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30) - timedelta(milliseconds=1)
        rows = filter_rows(start, end)
    records: List[Dict[str, Any]] = []
    for r in rows:
        dt = row_date(r)
        if dt is None:
            continue
        home = str(r.get("home_team", r.get("home_team_name", r.get("team_a_name", ""))) or "")
        away = str(r.get("away_team", r.get("away_team_name", r.get("team_b_name", ""))) or "")
        stadium = str(r.get("stadium", "")) if "stadium" in r else ""
        status = status_map(str(r.get("status", "scheduled")))
        odds_home = r.get("odds_home_win", r.get("odds_ft_home_team_win", None))
        odds_draw = r.get("odds_draw", r.get("odds_ft_draw", None))
        odds_away = r.get("odds_away_win", r.get("odds_ft_away_team_win", None))
        odds_over25 = r.get("odds_over_25", r.get("odds_ft_over25", None))
        odds_under25 = r.get("odds_under_25", None)
        odds_btts_yes = r.get("odds_btts_yes", None)
        odds_btts_no = r.get("odds_btts_no", None)
        homeProb, drawProb, awayProb = implied_probs(odds_home, odds_draw, odds_away)
        home_col = pick_column(matches, ["home_team", "home_team_name", "team_a_name"])
        away_col = pick_column(matches, ["away_team", "away_team_name", "team_b_name"])
        if home_col and away_col:
            h2h_df = matches[((matches[home_col] == home) & (matches[away_col] == away)) |
                             ((matches[home_col] == away) & (matches[away_col] == home))]
        else:
            h2h_df = matches.head(0)
        totalMatches = int(len(h2h_df))
        homeWins = 0
        awayWins = 0
        draws = 0
        avgGoals = 0.0
        if totalMatches > 0:
            tsum = 0
            for _, rr in h2h_df.iterrows():
                hg = rr.get("home_goals", rr.get("home_team_goal_count", 0)) or 0
                ag = rr.get("away_goals", rr.get("away_team_goal_count", 0)) or 0
                try:
                    hg = int(hg); ag = int(ag)
                except Exception:
                    continue
                tsum += (hg + ag)
                if rr.get(home_col, "") == home:
                    if hg > ag: homeWins += 1
                    elif hg == ag: draws += 1
                    else: awayWins += 1
                else:
                    if ag > hg: awayWins += 1
                    elif ag == hg: draws += 1
                    else: homeWins += 1
            avgGoals = tsum / totalMatches if totalMatches > 0 else 0.0
        homeForm = compute_form(matches, home, 5)
        awayForm = compute_form(matches, away, 5)
        def team_rating(name: str) -> float:
            if teams is not None:
                row = teams[teams.get("team_name", "") == name]
                if len(row) > 0:
                    ppg = float(row.iloc[0].get("points_per_game", row.iloc[0].get("points_per_game_overall", 1.5)) or 1.5)
                    return max(0.0, min(10.0, ppg * 4.0))
            return 6.5
        def team_possession(name: str) -> Optional[float]:
            if teams is not None and "average_possession" in teams.columns:
                row = teams[teams.get("team_name", "") == name]
                if len(row) > 0:
                    val = row.iloc[0].get("average_possession", None)
                    try:
                        return float(val)
                    except Exception:
                        return None
            return None
        def team_corners_per_match(name: str) -> Optional[float]:
            if teams is not None and "corners_per_match" in teams.columns:
                row = teams[teams.get("team_name", "") == name]
                if len(row) > 0:
                    val = row.iloc[0].get("corners_per_match", None)
                    try:
                        return float(val)
                    except Exception:
                        return None
            return None
        def team_cards_per_match(name: str) -> Optional[float]:
            if teams is not None and "cards_per_match" in teams.columns:
                row = teams[teams.get("team_name", "") == name]
                if len(row) > 0:
                    val = row.iloc[0].get("cards_per_match", None)
                    try:
                        return float(val)
                    except Exception:
                        return None
            return None
        league_avgs = { "avg_goals": None, "avg_corners": None, "avg_cards": None }
        if league_df is not None:
            league_avgs["avg_goals"] = float(league_df.iloc[0].get("average_goals_per_match", 2.5) or 2.5)
            league_avgs["avg_corners"] = float(league_df.iloc[0].get("average_corners_per_match", 10.0) or 10.0)
            league_avgs["avg_cards"] = float(league_df.iloc[0].get("average_cards_per_match", 4.0) or 4.0)
        homeRating = team_rating(home)
        awayRating = team_rating(away)
        home_poss = team_possession(home)
        away_poss = team_possession(away)
        home_corners_pm = team_corners_per_match(home)
        away_corners_pm = team_corners_per_match(away)
        home_cards_pm = team_cards_per_match(home)
        away_cards_pm = team_cards_per_match(away)
        over15_pct = r.get("over_15_percentage_pre_match", None)
        over25_pct = r.get("over_25_percentage_pre_match", None)
        over35_pct = r.get("over_35_percentage_pre_match", None)
        over45_pct = r.get("over_45_percentage_pre_match", None)
        btts_pct = r.get("btts_percentage_pre_match", None)
        odds_over15 = r.get("odds_ft_over15", None)
        odds_over35 = r.get("odds_ft_over35", None)
        odds_over45 = r.get("odds_ft_over45", None)
        try:
            over15_pct = float(over15_pct) if over15_pct is not None else None
            over25_pct = float(over25_pct) if over25_pct is not None else None
            over35_pct = float(over35_pct) if over35_pct is not None else None
            over45_pct = float(over45_pct) if over45_pct is not None else None
            btts_pct = float(btts_pct) if btts_pct is not None else None
        except Exception:
            over15_pct = None
            over25_pct = None
            over35_pct = None
            over45_pct = None
            btts_pct = None
        league_goal_avg = league_avgs["avg_goals"] if league_avgs["avg_goals"] else 2.7
        league_regime = "HIPER-OFENSIVA" if league_goal_avg > 3.0 else "NORMAL"
        def safe(val: Optional[float], default: float) -> float:
            return float(val) if val is not None and val > 0 else default
        def get_team_row(name: str) -> Optional["pd.Series"]:
            if teams is None:
                return None
            name_col = pick_column(teams, ["team_name", "team", "name", "club"])
            if not name_col:
                return None
            row = teams[teams[name_col] == name]
            if len(row) == 0:
                return None
            return row.iloc[0]
        def get_stat(row: Optional["pd.Series"], keys: List[str]) -> Optional[float]:
            if row is None:
                return None
            for key in keys:
                if key in row:
                    val = row.get(key)
                    if val is not None:
                        return val
            return None
        def parse_series(value: Any) -> List[float]:
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                series = []
                for item in value:
                    try:
                        series.append(float(item))
                    except Exception:
                        continue
                return series
            if isinstance(value, str):
                cleaned = value.replace("[", "").replace("]", "").replace(";", ",")
                parts = [p.strip() for p in cleaned.split(",") if p.strip()]
                series = []
                for part in parts:
                    try:
                        series.append(float(part))
                    except Exception:
                        continue
                return series
            return []
        home_row = get_team_row(home)
        away_row = get_team_row(away)
        home_attack = safe(get_stat(home_row, ["goals_scored_per_match_home", "goals_scored_avg_home"]) if home_row is not None else None, 1.3)
        away_defense = safe(get_stat(away_row, ["goals_conceded_per_match_away", "goals_conceded_avg_away"]) if away_row is not None else None, 1.2)
        away_attack = safe(get_stat(away_row, ["goals_scored_per_match_away", "goals_scored_avg_away"]) if away_row is not None else None, 1.2)
        home_defense = safe(get_stat(home_row, ["goals_conceded_per_match_home", "goals_conceded_avg_home"]) if home_row is not None else None, 1.1)
        xg_home_team = aggregate_team_xg(players, home)
        xg_away_team = aggregate_team_xg(players, away)
        home_goals_avg = safe(get_stat(home_row, ["goals_scored_per_match_overall", "goals_scored_per_match", "goals_scored_avg_overall"]) if home_row is not None else None, home_attack)
        home_goals_avg_home = safe(get_stat(home_row, ["goals_scored_per_match_home", "goals_scored_avg_home"]) if home_row is not None else None, home_attack)
        home_goals_last5 = safe(get_stat(home_row, ["goals_scored_avg_last_5", "goals_scored_avg_last5", "goals_scored_last_5", "goals_scored_last5"]) if home_row is not None else None, home_goals_avg)
        home_conceded_avg = safe(get_stat(home_row, ["goals_conceded_per_match_overall", "goals_conceded_per_match", "goals_conceded_avg_overall"]) if home_row is not None else None, home_defense)
        home_conceded_avg_home = safe(get_stat(home_row, ["goals_conceded_per_match_home", "goals_conceded_avg_home"]) if home_row is not None else None, home_defense)
        away_goals_avg = safe(get_stat(away_row, ["goals_scored_per_match_overall", "goals_scored_per_match", "goals_scored_avg_overall"]) if away_row is not None else None, away_attack)
        away_goals_avg_away = safe(get_stat(away_row, ["goals_scored_per_match_away", "goals_scored_avg_away"]) if away_row is not None else None, away_attack)
        away_goals_last5 = safe(get_stat(away_row, ["goals_scored_avg_last_5", "goals_scored_avg_last5", "goals_scored_last_5", "goals_scored_last5"]) if away_row is not None else None, away_goals_avg)
        away_conceded_avg = safe(get_stat(away_row, ["goals_conceded_per_match_overall", "goals_conceded_per_match", "goals_conceded_avg_overall"]) if away_row is not None else None, away_defense)
        away_conceded_avg_away = safe(get_stat(away_row, ["goals_conceded_per_match_away", "goals_conceded_avg_away"]) if away_row is not None else None, away_defense)
        home_xg_series = parse_series(get_stat(home_row, ["xg_per_game", "xg_last_5", "xg_last5", "xg_series", "xg_recent"]) if home_row is not None else None)
        away_xg_series = parse_series(get_stat(away_row, ["xg_per_game", "xg_last_5", "xg_last5", "xg_series", "xg_recent"]) if away_row is not None else None)
        home_goals_series = parse_series(get_stat(home_row, ["goals_per_game", "goals_scored_last_5", "goals_scored_last5", "goals_last_5", "goals_last5"]) if home_row is not None else None)
        away_goals_series = parse_series(get_stat(away_row, ["goals_per_game", "goals_scored_last_5", "goals_scored_last5", "goals_last_5", "goals_last5"]) if away_row is not None else None)
        home_games_played = safe(get_stat(home_row, ["matches_played", "games_played", "matches"]) if home_row is not None else None, None)
        away_games_played = safe(get_stat(away_row, ["matches_played", "games_played", "matches"]) if away_row is not None else None, None)
        home_goals_scored_total = safe(get_stat(home_row, ["goals_scored", "goals_scored_overall", "goals_scored_total", "goals_scored_for_season"]) if home_row is not None else None, None)
        away_goals_scored_total = safe(get_stat(away_row, ["goals_scored", "goals_scored_overall", "goals_scored_total", "goals_scored_for_season"]) if away_row is not None else None, None)
        home_xg_total = safe(get_stat(home_row, ["xg_for_total", "xg_total", "xg_for", "xg"]) if home_row is not None else None, None)
        away_xg_total = safe(get_stat(away_row, ["xg_for_total", "xg_total", "xg_for", "xg"]) if away_row is not None else None, None)
        home_xg_avg = safe(get_stat(home_row, ["xg_for_avg", "xg_avg", "xg_for_per_match"]) if home_row is not None else None, None)
        away_xg_avg = safe(get_stat(away_row, ["xg_for_avg", "xg_avg", "xg_for_per_match"]) if away_row is not None else None, None)
        if home_xg_total is None and home_xg_avg is not None and home_games_played:
            home_xg_total = home_xg_avg * home_games_played
        if away_xg_total is None and away_xg_avg is not None and away_games_played:
            away_xg_total = away_xg_avg * away_games_played
        if home_goals_scored_total is None and home_goals_avg is not None and home_games_played:
            home_goals_scored_total = home_goals_avg * home_games_played
        if away_goals_scored_total is None and away_goals_avg is not None and away_games_played:
            away_goals_scored_total = away_goals_avg * away_games_played
        league_name = league_df.iloc[0].get("league_name", league_id) if league_df is not None else league_id
        home_team_data = {
            "team_name": home,
            "goals_scored_avg_overall": home_goals_avg,
            "goals_scored_avg_home": home_goals_avg_home,
            "goals_scored_avg_last_5": home_goals_last5,
            "goals_conceded_avg_overall": home_conceded_avg,
            "goals_conceded_avg_home": home_conceded_avg_home,
            "goals_scored": home_goals_scored_total,
            "xg": home_xg_total,
            "games_played": home_games_played,
            "xg_per_game": home_xg_series,
            "goals_per_game": home_goals_series,
        }
        away_team_data = {
            "team_name": away,
            "goals_scored_avg_overall": away_goals_avg,
            "goals_scored_avg_away": away_goals_avg_away,
            "goals_scored_avg_last_5": away_goals_last5,
            "goals_conceded_avg_overall": away_conceded_avg,
            "goals_conceded_avg_away": away_conceded_avg_away,
            "goals_scored": away_goals_scored_total,
            "xg": away_xg_total,
            "games_played": away_games_played,
            "xg_per_game": away_xg_series,
            "goals_per_game": away_goals_series,
        }
        league_data = {
            "league_name": league_name,
            "average_goals_per_match": league_goal_avg,
        }
        lam_home, lam_away = expected_goals_v2(
            home_team_data=home_team_data,
            away_team_data=away_team_data,
            league_data=league_data,
            regime=league_regime,
            xg_home=xg_home_team,
            xg_away=xg_away_team,
        )
        lam_home, lam_away, xg_metadata = aplicar_filtro_completo(
            lambda_home=lam_home,
            lambda_away=lam_away,
            home_team_data=home_team_data,
            away_team_data=away_team_data,
            enable_filter=True,
        )
        has_chaos, chaos_metadata = detectar_caos_jogo(
            home_team_data=home_team_data,
            away_team_data=away_team_data,
        )
        lam_total = lam_home + lam_away
        if lam_total < 2.2:
            league_volatility = "BAIXA"
        elif lam_total < 3.0:
            league_volatility = "MODERADA"
        else:
            league_volatility = "ALTA"
        btts_poisson = (1.0 - poisson_pmf(0, lam_home)) * (1.0 - poisson_pmf(0, lam_away))
        over05 = 1.0 - poisson_cdf(0, lam_total)
        over15 = 1.0 - poisson_cdf(1, lam_total)
        over25 = 1.0 - poisson_cdf(2, lam_total)
        over35 = 1.0 - poisson_cdf(3, lam_total)
        data_source = "s3" if os.getenv("S3_BUCKET") else "local"
        total_gols = r.get("total_goal_count", None)
        try:
            total_gols = float(total_gols) if total_gols is not None else None
        except Exception:
            total_gols = None
        records.append({
            "id": f"{league_id}-{home}-{away}-{dt.timestamp()}",
            "leagueId": league_id,
            "leagueName": league_id.replace("-", " ").title(),
            "homeTeam": home,
            "awayTeam": away,
            "datetime": dt.isoformat(),
            "stadium": stadium,
            "status": status,
            "odds": {
                "home": float(odds_home) if odds_home else None,
                "draw": float(odds_draw) if odds_draw else None,
                "away": float(odds_away) if odds_away else None,
                "over15": float(odds_over15) if odds_over15 else None,
                "over25": float(odds_over25) if odds_over25 else None,
                "over35": float(odds_over35) if odds_over35 else None,
                "over45": float(odds_over45) if odds_over45 else None,
                "under25": float(odds_under25) if odds_under25 else None,
                "bttsYes": float(odds_btts_yes) if odds_btts_yes else None,
                "bttsNo": float(odds_btts_no) if odds_btts_no else None,
            },
            "stats": {
                "homeWinProb": round(homeProb, 1),
                "drawProb": round(drawProb, 1),
                "awayWinProb": round(awayProb, 1),
                "avgGoals": round(avgGoals if avgGoals > 0 else 2.5, 2),
                "bttsProb": float(btts_pct) if btts_pct is not None else round(btts_poisson * 100.0, 1),
                "over05Prob": round(over05 * 100.0, 1),
                "over15Prob": float(over15_pct) if over15_pct is not None else round(over15 * 100.0, 1),
                "over25Prob": float(over25_pct) if over25_pct is not None else round(over25 * 100.0, 1),
                "over35Prob": float(over35_pct) if over35_pct is not None else round(over35 * 100.0, 1),
                "over45Prob": float(over45_pct) if over45_pct is not None else round((1.0 - poisson_cdf(4, lam_total)) * 100.0, 1),
                "under15Prob": 100.0 - (float(over15_pct) if over15_pct is not None else round(over15 * 100.0, 1)),
                "under25Prob": 100.0 - (float(over25_pct) if over25_pct is not None else round(over25 * 100.0, 1)),
                "under35Prob": 100.0 - (float(over35_pct) if over35_pct is not None else round(over35 * 100.0, 1)),
                "under45Prob": 100.0 - (float(over45_pct) if over45_pct is not None else round((1.0 - poisson_cdf(4, lam_total)) * 100.0, 1)),
                "lambdaHome": round(lam_home, 3),
                "lambdaAway": round(lam_away, 3),
                "lambdaTotal": round(lam_total, 3),
                "leagueAvgGoals": league_avgs["avg_goals"],
                "totalGoals": total_gols,
                "leagueRegime": league_regime,
                "leagueVolatility": league_volatility,
                "chaosDetected": has_chaos,
                "chaosHome": chaos_metadata.get("home", {}).get("classification"),
                "chaosAway": chaos_metadata.get("away", {}).get("classification"),
                "chaosHomeCv": round(chaos_metadata.get("home", {}).get("cv_xg", 0.0), 3),
                "chaosAwayCv": round(chaos_metadata.get("away", {}).get("cv_xg", 0.0), 3),
                "homePossession": home_poss,
                "awayPossession": away_poss,
                "homeCornersPerMatch": home_corners_pm,
                "awayCornersPerMatch": away_corners_pm,
                "homeCardsPerMatch": home_cards_pm,
                "awayCardsPerMatch": away_cards_pm,
                "leagueAvgCorners": league_avgs["avg_corners"],
                "leagueAvgCards": league_avgs["avg_cards"],
            },
            "h2h": {
                "totalMatches": totalMatches,
                "homeWins": homeWins,
                "draws": draws,
                "awayWins": awayWins,
                "avgGoals": round(avgGoals, 2),
            },
            "homeForm": homeForm,
            "awayForm": awayForm,
            "ratings": { "home": round(homeRating, 1), "away": round(awayRating, 1) },
            "xg": { "home": xg_home_team, "away": xg_away_team },
            "source": "footystats",
            "dataSource": data_source,
            "lastUpdated": datetime.utcnow().isoformat(),
        })
    return records
