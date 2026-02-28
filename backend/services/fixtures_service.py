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
from backend.services.market_service import selecionar_mercados_jogo

logger = logging.getLogger("sportsbankzu")


def _apply_confidence_adjustment(stats: dict, adjustment: dict) -> dict:
    """Apply Mistral confidence_adjustment to 1X2 probabilities (Gap 3).

    Probs in `stats` are on 0-100 scale. Adjustment shifts the favourite up or
    compresses both sides down, then renormalises so homeWinProb + drawProb +
    awayWinProb = 100.
    """
    recommendation = adjustment.get("recommendation", "MANTER")
    if recommendation == "MANTER":
        return stats

    impact = float(adjustment.get("impact_percentage", 10)) / 100.0
    impact = min(0.20, max(0.0, impact))

    h = (stats.get("homeWinProb") or 0) / 100.0
    d = (stats.get("drawProb") or 0) / 100.0
    a = (stats.get("awayWinProb") or 0) / 100.0

    if recommendation == "AUMENTAR":
        if h >= a:
            h = min(0.95, h * (1 + impact))
        else:
            a = min(0.95, a * (1 + impact))
    elif recommendation == "REDUZIR":
        h = max(0.05, h * (1 - impact))
        a = max(0.05, a * (1 - impact))

    total = h + d + a
    if total > 0:
        h /= total
        d /= total
        a /= total

    stats["homeWinProb"] = round(h * 100.0, 1)
    stats["drawProb"] = round(d * 100.0, 1)
    stats["awayWinProb"] = round(a * 100.0, 1)
    return stats


def _safe_int(val: Any) -> Optional[int]:
    """Convert to int if possible, return None for missing/invalid values."""
    if val is None or val == -1:
        return None
    try:
        v = int(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def build_records_from_matches(
    league_id: str,
    matches: "pd.DataFrame",
    teams: Optional["pd.DataFrame"] = None,
    teams2: Optional["pd.DataFrame"] = None,
    league_df: Optional["pd.DataFrame"] = None,
    players: Optional["pd.DataFrame"] = None,
    date_filter: str = "today",
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
    # No automatic fallback — return only matches for the requested period
    records: List[Dict[str, Any]] = []
    for r in rows:
      try:
        dt = row_date(r)
        if dt is None:
            continue
        home = str(r.get("home_team", r.get("home_team_name", r.get("team_a_name", ""))) or "")
        away = str(r.get("away_team", r.get("away_team_name", r.get("team_b_name", ""))) or "")
        stadium = str(r.get("stadium", "")) if "stadium" in r else ""
        status = status_map(str(r.get("status", "scheduled")))
        # Skip postponed / cancelled matches — do not generate predictions for them
        if status in ("postponed", "cancelled"):
            logger.info(f"[fixtures_service] Skipping {home} vs {away} — status: {status}")
            continue
        # Extract score for finished matches
        _home_goals_raw = r.get("home_goals", r.get("home_team_goal_count", None))
        _away_goals_raw = r.get("away_goals", r.get("away_team_goal_count", None))
        match_score = None
        if status == "finished" and _home_goals_raw is not None and _away_goals_raw is not None:
            try:
                match_score = {"home": int(_home_goals_raw), "away": int(_away_goals_raw)}
            except (ValueError, TypeError):
                match_score = None
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
        def team_shots_on_target(name: str) -> Optional[float]:
            if teams is None:
                return None
            for col in ["shots_on_target_per_match", "shots_on_target_per_game", "shotsOnTarget_per_match", "shots_on_target_avg"]:
                if col in teams.columns:
                    name_col = pick_column(teams, ["team_name", "team", "name", "club"])
                    if not name_col:
                        return None
                    row = teams[teams[name_col] == name]
                    if len(row) > 0:
                        val = row.iloc[0].get(col, None)
                        try:
                            v = float(val)
                            return v if v > 0 else None
                        except Exception:
                            return None
            return None
        def team_fouls_per_match(name: str) -> Optional[float]:
            if teams is None:
                return None
            for col in ["fouls_per_match", "fouls_per_game", "foulsPerMatch", "fouls_avg"]:
                if col in teams.columns:
                    name_col = pick_column(teams, ["team_name", "team", "name", "club"])
                    if not name_col:
                        return None
                    row = teams[teams[name_col] == name]
                    if len(row) > 0:
                        val = row.iloc[0].get(col, None)
                        try:
                            v = float(val)
                            return v if v > 0 else None
                        except Exception:
                            return None
            return None
        def team_shots_per_match(name: str) -> Optional[float]:
            if teams is None:
                return None
            for col in ["shots_per_match", "shots_per_game", "shotsPerMatch", "shots_avg"]:
                if col in teams.columns:
                    name_col = pick_column(teams, ["team_name", "team", "name", "club"])
                    if not name_col:
                        return None
                    row = teams[teams[name_col] == name]
                    if len(row) > 0:
                        val = row.iloc[0].get(col, None)
                        try:
                            v = float(val)
                            return v if v > 0 else None
                        except Exception:
                            return None
            return None
        def _team_stat(name: str, col: str) -> Optional[float]:
            """Generic helper: extract a single float stat from teams_df for a team."""
            if teams is None or col not in teams.columns:
                return None
            name_col = pick_column(teams, ["team_name", "team", "name", "club"])
            if not name_col:
                return None
            row = teams[teams[name_col] == name]
            if len(row) == 0:
                return None
            val = row.iloc[0].get(col, None)
            if val is None:
                return None
            try:
                v = float(val)
                return v if v >= 0 else None
            except (TypeError, ValueError):
                return None

        league_avgs = {
            "avg_goals": None, "avg_corners": None, "avg_cards": None,
            "avg_fouls": None, "avg_shots": None,
            "home_advantage_pct": None, "avg_goals_home": None, "avg_goals_away": None,
            "clean_sheets_pct": None, "over25_pct": None, "xg_avg": None,
        }
        if league_df is not None:
            _lg = league_df.iloc[0]
            league_avgs["avg_goals"] = float(_lg.get("average_goals_per_match", 2.5) or 2.5)
            league_avgs["avg_corners"] = float(_lg.get("average_corners_per_match", 10.0) or 10.0)
            league_avgs["avg_cards"] = float(_lg.get("average_cards_per_match", 4.0) or 4.0)
            league_avgs["avg_fouls"] = float(_lg.get("average_fouls_per_match", 22.0) or 22.0)
            league_avgs["avg_shots"] = float(_lg.get("average_shots_per_match", 24.0) or 24.0)
            # Extended league stats (League CSV: 49 cols)
            _ha = _lg.get("home_advantage_percentage")
            if _ha is not None:
                try:
                    league_avgs["home_advantage_pct"] = float(_ha)
                except (TypeError, ValueError):
                    pass
            _agh = _lg.get("average_scored_home_team")
            if _agh is not None:
                try:
                    league_avgs["avg_goals_home"] = float(_agh)
                except (TypeError, ValueError):
                    pass
            _aga = _lg.get("average_scored_away_team")
            if _aga is not None:
                try:
                    league_avgs["avg_goals_away"] = float(_aga)
                except (TypeError, ValueError):
                    pass
            _cs = _lg.get("clean_sheets_percentage")
            if _cs is not None:
                try:
                    league_avgs["clean_sheets_pct"] = float(_cs)
                except (TypeError, ValueError):
                    pass
            _o25 = _lg.get("over_25_percentage")
            if _o25 is not None:
                try:
                    league_avgs["over25_pct"] = float(_o25)
                except (TypeError, ValueError):
                    pass
            _xg = _lg.get("xg_avg")
            if _xg is not None:
                try:
                    league_avgs["xg_avg"] = float(_xg)
                except (TypeError, ValueError):
                    pass
        homeRating = team_rating(home)
        awayRating = team_rating(away)
        home_poss = team_possession(home)
        away_poss = team_possession(away)
        home_corners_pm = team_corners_per_match(home)
        away_corners_pm = team_corners_per_match(away)
        home_cards_pm = team_cards_per_match(home)
        away_cards_pm = team_cards_per_match(away)
        home_shots_on_target = team_shots_on_target(home)
        away_shots_on_target = team_shots_on_target(away)
        home_shots_pm = team_shots_per_match(home)
        away_shots_pm = team_shots_per_match(away)
        home_fouls_pm = team_fouls_per_match(home)
        away_fouls_pm = team_fouls_per_match(away)

        # --- New team-level stats (Team CSV: 186 + Pt.2: 442) ---
        home_btts_pct_team = _team_stat(home, "btts_percentage")
        away_btts_pct_team = _team_stat(away, "btts_percentage")
        home_cs_pct = _team_stat(home, "clean_sheet_percentage")
        away_cs_pct = _team_stat(away, "clean_sheet_percentage")
        home_fts_pct = _team_stat(home, "fts_percentage")
        away_fts_pct = _team_stat(away, "fts_percentage")
        home_over25_pct = _team_stat(home, "over25_percentage")
        away_over25_pct = _team_stat(away, "over25_percentage")
        home_win_pct = _team_stat(home, "win_percentage")
        away_win_pct = _team_stat(away, "win_percentage")
        home_xg_for = _team_stat(home, "xg_for_avg")
        away_xg_for = _team_stat(away, "xg_for_avg")
        home_xg_against = _team_stat(home, "xg_against_avg")
        away_xg_against = _team_stat(away, "xg_against_avg")
        home_corners_against = _team_stat(home, "corners_against_per_match")
        away_corners_against = _team_stat(away, "corners_against_per_match")
        home_league_pos = _team_stat(home, "league_position")
        away_league_pos = _team_stat(away, "league_position")
        home_avg_total_goals = _team_stat(home, "average_total_goals_per_match")
        away_avg_total_goals = _team_stat(away, "average_total_goals_per_match")

        # --- Fallback cascade: team stats from match history ---
        def _avg_from_history(col_name: str, team_name: str, is_home: bool) -> Optional[float]:
            """Compute per-match average from completed match history."""
            if col_name not in matches.columns:
                return None
            tcol = home_col if is_home else away_col
            if not tcol:
                return None
            subset = matches[matches[tcol] == team_name]
            vals = subset[col_name].dropna()
            vals = vals[vals >= 0]
            return round(float(vals.mean()), 1) if len(vals) > 0 else None

        # Corners fallback from match history
        if home_corners_pm is None:
            home_corners_pm = _avg_from_history("home_team_corner_count", home, True)
        if away_corners_pm is None:
            away_corners_pm = _avg_from_history("away_team_corner_count", away, False)

        # Cards fallback from match history (yellow_cards mapped from API)
        if home_cards_pm is None:
            home_cards_pm = _avg_from_history("home_team_yellow_cards", home, True)
        if away_cards_pm is None:
            away_cards_pm = _avg_from_history("away_team_yellow_cards", away, False)

        # Shots fallback from match history
        if home_shots_pm is None:
            home_shots_pm = _avg_from_history("home_team_shots", home, True)
        if away_shots_pm is None:
            away_shots_pm = _avg_from_history("away_team_shots", away, False)

        # Shots on target fallback from match history
        if home_shots_on_target is None:
            home_shots_on_target = _avg_from_history("home_team_shots_on_target", home, True)
        if away_shots_on_target is None:
            away_shots_on_target = _avg_from_history("away_team_shots_on_target", away, False)

        # Fouls fallback from match history
        if home_fouls_pm is None:
            home_fouls_pm = _avg_from_history("home_team_fouls", home, True)
        if away_fouls_pm is None:
            away_fouls_pm = _avg_from_history("away_team_fouls", away, False)

        # --- Final fallback: league average / 2 ---
        if home_corners_pm is None and league_avgs["avg_corners"]:
            home_corners_pm = round(league_avgs["avg_corners"] / 2, 1)
        if away_corners_pm is None and league_avgs["avg_corners"]:
            away_corners_pm = round(league_avgs["avg_corners"] / 2, 1)
        if home_cards_pm is None and league_avgs["avg_cards"]:
            home_cards_pm = round(league_avgs["avg_cards"] / 2, 1)
        if away_cards_pm is None and league_avgs["avg_cards"]:
            away_cards_pm = round(league_avgs["avg_cards"] / 2, 1)
        if home_shots_pm is None and league_avgs["avg_shots"]:
            home_shots_pm = round(league_avgs["avg_shots"] / 2, 1)
        if away_shots_pm is None and league_avgs["avg_shots"]:
            away_shots_pm = round(league_avgs["avg_shots"] / 2, 1)
        if home_fouls_pm is None and league_avgs["avg_fouls"]:
            home_fouls_pm = round(league_avgs["avg_fouls"] / 2, 1)
        if away_fouls_pm is None and league_avgs["avg_fouls"]:
            away_fouls_pm = round(league_avgs["avg_fouls"] / 2, 1)
        over15_pct = r.get("over_15_percentage_pre_match", None)
        over25_pct = r.get("over_25_percentage_pre_match", None)
        over35_pct = r.get("over_35_percentage_pre_match", None)
        over45_pct = r.get("over_45_percentage_pre_match", None)
        btts_pct = r.get("btts_percentage_pre_match", None)
        odds_over15 = r.get("odds_ft_over15", None)
        odds_over35 = r.get("odds_ft_over35", None)
        odds_over45 = r.get("odds_ft_over45", None)
        # Corner potentials from FootyStats (pre-match probabilities, 0-100 scale)
        corners_potential = r.get("corners_potential", None)
        corners_o85_pct = r.get("corners_o85_potential", None)
        corners_o95_pct = r.get("corners_o95_potential", None)
        corners_o105_pct = r.get("corners_o105_potential", None)
        # Corner odds
        odds_corners_o85 = r.get("odds_corners_over_85", None)
        odds_corners_o95 = r.get("odds_corners_over_95", None)
        odds_corners_o105 = r.get("odds_corners_over_105", None)
        odds_corners_o115 = r.get("odds_corners_over_115", None)
        try:
            corners_potential = float(corners_potential) if corners_potential is not None and float(corners_potential) > 0 else None
            corners_o85_pct = float(corners_o85_pct) if corners_o85_pct is not None and float(corners_o85_pct) > 0 else None
            corners_o95_pct = float(corners_o95_pct) if corners_o95_pct is not None and float(corners_o95_pct) > 0 else None
            corners_o105_pct = float(corners_o105_pct) if corners_o105_pct is not None and float(corners_o105_pct) > 0 else None
        except Exception:
            corners_potential = None
            corners_o85_pct = None
            corners_o95_pct = None
            corners_o105_pct = None
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

        # Apply lambda corrections from audit DB (Gap 2 — feedback loop)
        _btts_multiplier = None
        _corner_multiplier = None
        try:
            from backend.modeling.lambda_calculator import get_lambda_corrections, LAMBDA_MIN, LAMBDA_MAX
            _lc = get_lambda_corrections(league_id)
            if _corr := _lc.get("lambda_home_multiplier"):
                lam_home = max(LAMBDA_MIN, min(LAMBDA_MAX, lam_home * float(_corr.get("value", 1.0))))
            if _corr := _lc.get("lambda_away_multiplier"):
                lam_away = max(LAMBDA_MIN, min(LAMBDA_MAX, lam_away * float(_corr.get("value", 1.0))))
            # BTTS and corner multiplier corrections (Gap 2 extension)
            if _corr := _lc.get("btts_multiplier"):
                _btts_multiplier = float(_corr.get("value", 1.0))
                logger.info(f"[Gap2] BTTS multiplier loaded: {_btts_multiplier:.3f}")
            if _corr := _lc.get("corner_multiplier"):
                _corner_multiplier = float(_corr.get("value", 1.0))
                logger.info(f"[Gap2] Corner multiplier loaded: {_corner_multiplier:.3f}")
        except Exception as _e:
            logger.debug(f"[Gap2] Lambda corrections skipped for {league_id}: {_e}")

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

        # Apply BTTS audit correction multiplier (Gap 2 extension)
        if _btts_multiplier is not None and btts_pct is not None:
            btts_pct = min(100.0, max(0.0, float(btts_pct) * _btts_multiplier))
        if _btts_multiplier is not None:
            btts_poisson = min(1.0, max(0.0, btts_poisson * _btts_multiplier))

        # Apply corner audit correction multiplier (Gap 2 extension)
        if _corner_multiplier is not None:
            if corners_o85_pct is not None:
                corners_o85_pct = min(100.0, max(0.0, float(corners_o85_pct) * _corner_multiplier))
            if corners_o95_pct is not None:
                corners_o95_pct = min(100.0, max(0.0, float(corners_o95_pct) * _corner_multiplier))
            if corners_o105_pct is not None:
                corners_o105_pct = min(100.0, max(0.0, float(corners_o105_pct) * _corner_multiplier))

        data_source = "s3" if os.getenv("S3_BUCKET") else "local"
        total_gols = r.get("total_goal_count", None)
        try:
            total_gols = float(total_gols) if total_gols is not None else None
        except Exception:
            total_gols = None
        records.append({
            "id": f"{league_id}-{home}-{away}-{dt.timestamp()}",
            "footystatsId": r.get("id"),
            "leagueId": league_id,
            "leagueName": league_id.replace("-", " ").title(),
            "homeTeam": home,
            "awayTeam": away,
            "datetime": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt.tzinfo else dt.isoformat() + "Z",
            "stadium": stadium,
            "status": status,
            "score": match_score,
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
                "cornersOver85": float(odds_corners_o85) if odds_corners_o85 else None,
                "cornersOver95": float(odds_corners_o95) if odds_corners_o95 else None,
                "cornersOver105": float(odds_corners_o105) if odds_corners_o105 else None,
                "cornersOver115": float(odds_corners_o115) if odds_corners_o115 else None,
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
                "homeShotsOnTarget": home_shots_on_target,
                "awayShotsOnTarget": away_shots_on_target,
                "homeShotsPerMatch": home_shots_pm,
                "awayShotsPerMatch": away_shots_pm,
                "homeFoulsPerMatch": home_fouls_pm,
                "awayFoulsPerMatch": away_fouls_pm,
                "leagueAvgCorners": league_avgs["avg_corners"],
                "leagueAvgCards": league_avgs["avg_cards"],
                "leagueAvgFouls": league_avgs["avg_fouls"],
                "leagueAvgShots": league_avgs["avg_shots"],
                # League extended stats
                "leagueHomeAdvantage": league_avgs.get("home_advantage_pct"),
                "leagueAvgGoalsHome": league_avgs.get("avg_goals_home"),
                "leagueAvgGoalsAway": league_avgs.get("avg_goals_away"),
                "leagueCleanSheetsPct": league_avgs.get("clean_sheets_pct"),
                "leagueOver25Pct": league_avgs.get("over25_pct"),
                "leagueXgAvg": league_avgs.get("xg_avg"),
                # Team-level advanced stats (Team CSV 186 + Pt.2 442)
                "homeBttsPercentage": home_btts_pct_team,
                "awayBttsPercentage": away_btts_pct_team,
                "homeCleanSheetPct": home_cs_pct,
                "awayCleanSheetPct": away_cs_pct,
                "homeFtsPercentage": home_fts_pct,
                "awayFtsPercentage": away_fts_pct,
                "homeOver25Percentage": home_over25_pct,
                "awayOver25Percentage": away_over25_pct,
                "homeWinPercentage": home_win_pct,
                "awayWinPercentage": away_win_pct,
                "homeXgForAvg": home_xg_for,
                "awayXgForAvg": away_xg_for,
                "homeXgAgainstAvg": home_xg_against,
                "awayXgAgainstAvg": away_xg_against,
                "homeCornersAgainstPerMatch": home_corners_against,
                "awayCornersAgainstPerMatch": away_corners_against,
                "homeLeaguePosition": home_league_pos,
                "awayLeaguePosition": away_league_pos,
                "homeAvgTotalGoals": home_avg_total_goals,
                "awayAvgTotalGoals": away_avg_total_goals,
                # Corner predictions (from FootyStats pre-match potentials)
                "cornersPotential": corners_potential,
                "cornerOver85Prob": corners_o85_pct,
                "cornerOver95Prob": corners_o95_pct,
                "cornerOver105Prob": corners_o105_pct,
                # Actual match corner counts (for audit evaluation)
                "homeCornersCount": _safe_int(r.get("home_team_corner_count")),
                "awayCornersCount": _safe_int(r.get("away_team_corner_count")),
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
        # Calculate market predictions (mercados) for this match
        try:
            record = records[-1]
            _regime = record["stats"].get("leagueRegime", "NORMAL")
            _volatilidade = record["stats"].get("leagueVolatility", "MODERADA")

            # Apply Mistral confidence_adjustment (Gap 3 — contextual bridge)
            # Only called when MISTRAL_API_KEY is set; CacheManager(6h) prevents re-calls.
            if os.getenv("MISTRAL_API_KEY"):
                try:
                    from backend.ai.context_analyzer import ContextAnalyzer
                    ctx_result = ContextAnalyzer().analyze_match_context(home, away)
                    _adj = ctx_result.get("confidence_adjustment", {})
                    if _adj and _adj.get("recommendation", "MANTER") != "MANTER":
                        record["stats"] = _apply_confidence_adjustment(record["stats"], _adj)
                        logger.info(
                            f"[Gap3] Confidence adjustment {_adj.get('recommendation')} "
                            f"{_adj.get('impact_percentage', 10)}% applied to {home} vs {away}"
                        )
                except Exception as _ctx_err:
                    logger.debug(f"[Gap3] Context analysis skipped for {home} vs {away}: {_ctx_err}")

            # Apply Isotonic Regression calibration (Gap 5)
            try:
                from backend.modeling.calibrator import calibrate_match_stats
                record["stats"] = calibrate_match_stats(record["stats"], league_id, _regime)
            except Exception as _cal_err:
                logger.debug(f"[Gap5] Calibration skipped for {home} vs {away}: {_cal_err}")

            mercados = selecionar_mercados_jogo(record, _regime, _volatilidade)
            record["mercados"] = mercados
        except Exception as e:
            logger.warning(f"Falha ao calcular mercados para {home} vs {away}: {e}")
            records[-1]["mercados"] = []
      except Exception as e:
        _match_label = f"{r.get('home_team', '?')} vs {r.get('away_team', '?')}"
        logger.error(f"[fixtures_service] Skipping match {_match_label}: {type(e).__name__}: {e}", exc_info=True)
        continue
    return records
