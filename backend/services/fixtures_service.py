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
from backend.services.market_service import selecionar_mercados_v2

logger = logging.getLogger("sportsbankzu")


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
        home = str(r.get("home_team", r.get("home_team_name", r.get("team_a_name", ""))) or "").strip()
        away = str(r.get("away_team", r.get("away_team_name", r.get("team_b_name", ""))) or "").strip()
        stadium = str(r.get("stadium", "")) if "stadium" in r else ""
        status = status_map(str(r.get("status", "scheduled")))
        # Guard: if API reports "live" but kickoff is in the future, override to "scheduled".
        # FootyStats sometimes returns "incomplete" or even "live" for matches that haven't
        # kicked off yet. We check date_unix to confirm the match has actually started.
        import time as _time
        _kickoff_ts = r.get("date_unix") or r.get("timestamp")
        _elapsed_min = None
        if _kickoff_ts:
            try:
                _elapsed_min = (int(_time.time()) - int(_kickoff_ts)) // 60
            except (ValueError, TypeError):
                pass
        if status == "live":
            if _elapsed_min is not None and _elapsed_min < -2:  # More than 2 minutes before kickoff
                logger.info(
                    f"[fixtures_service] Overriding 'live' → 'scheduled' for {home} vs {away} "
                    f"(kickoff in {abs(_elapsed_min)} min, raw_status={r.get('status')!r})"
                )
                status = "scheduled"
        # Promote scheduled → live when kickoff has passed (same heuristic as /live-scores)
        if status == "scheduled" and _elapsed_min is not None and 0 <= _elapsed_min < 150:
            logger.info(
                f"[fixtures_service] Promoting 'scheduled' → 'live' for {home} vs {away} "
                f"(elapsed={_elapsed_min}min, raw_status={r.get('status')!r})"
            )
            status = "live"
        # Skip postponed / cancelled matches — do not generate predictions for them
        if status in ("postponed", "cancelled"):
            logger.info(f"[fixtures_service] Skipping {home} vs {away} — status: {status}")
            continue
        # Extract score for finished and live matches
        # FootyStats uses -1 to mean "no data available" — treat as None
        def _valid_goal_count(val):
            if val is None:
                return None
            try:
                v = int(val)
                return v if v >= 0 else None
            except (ValueError, TypeError):
                return None

        # Try multiple field names — todays-matches API can return goal counts
        # under different keys depending on match status and API version.
        # For live matches, some fields may be stale (0) while others have the
        # real score. We take the MAX across all fields to avoid showing 0-0.
        _GOAL_HOME_FB = ("homeGoalCount", "home_team_goal_count", "home_goals",
                         "team_a_goals", "homeScore", "home_score")
        _GOAL_AWAY_FB = ("awayGoalCount", "away_team_goal_count", "away_goals",
                         "team_b_goals", "awayScore", "away_score")

        _home_goals = None
        _away_goals = None

        if status == "live":
            # For live matches: check ALL fields and take the highest valid value,
            # because some API fields lag behind (report 0) while others are current.
            _h_candidates = [_valid_goal_count(r.get(_f)) for _f in _GOAL_HOME_FB]
            _a_candidates = [_valid_goal_count(r.get(_f)) for _f in _GOAL_AWAY_FB]
            
            _h_valid = [v for v in _h_candidates if v is not None]
            _a_valid = [v for v in _a_candidates if v is not None]
            
            _home_goals = max(_h_valid) if _h_valid else None
            _away_goals = max(_a_valid) if _a_valid else None
        else:
            # For finished/scheduled: first valid value wins (standard behavior)
            for _gf in _GOAL_HOME_FB:
                _home_goals = _valid_goal_count(r.get(_gf))
                if _home_goals is not None:
                    break
            for _gf in _GOAL_AWAY_FB:
                _away_goals = _valid_goal_count(r.get(_gf))
                if _away_goals is not None:
                    break

        _ht_home = _valid_goal_count(r.get("home_team_goal_count_half_time"))
        _ht_away = _valid_goal_count(r.get("away_team_goal_count_half_time"))
        
        match_score = None
        _has_goals_fb = _home_goals is not None and _away_goals is not None

        # Fallback: fetch individual match details if live and goal fields missing
        # This is expensive, so only do it for LIVE matches that are missing scores
        if not _has_goals_fb and status == "live":
            _fb_id = r.get("id")
            if _fb_id is not None:
                try:
                    # Import here to avoid circular dependency if possible, or use existing client
                    from backend.services.footstats_client import FootyStatsClient
                    # We need an instance or a way to call the API. 
                    # Assuming we can't easily get the client instance here without refactoring,
                    # we'll skip this fallback for now or need to inject the client.
                    # For now, we'll rely on the MAX strategy above which covers 99% of cases.
                    pass 
                except Exception:
                    pass

        if status in ("finished", "live") and _has_goals_fb:
            _ht = None
            if _ht_home is not None and _ht_away is not None:
                _ht = {"home": _ht_home, "away": _ht_away}
            match_score = {"home": _home_goals, "away": _away_goals}
            if _ht:
                match_score["halftime"] = _ht
        # Log finished matches with missing goal data — indicates API coverage gap
        if status == "finished" and match_score is None:
            _raw_h = r.get("home_goals", r.get("home_team_goal_count", None))
            _raw_a = r.get("away_goals", r.get("away_team_goal_count", None))
            logger.warning(
                f"[fixtures_service] Finished match {home} vs {away} has NO goal data — "
                f"score will be null (raw home_goals={_raw_h}, away_goals={_raw_a}). "
                f"Possible API coverage gap for this league."
            )
        # Do NOT default live matches to 0-0 when goal data is missing —
        # a fake 0-0 corrupts audit accuracy (e.g. Lanús vs Boca 0-3 shown as 0-0).
        # Instead, leave match_score as None so the frontend knows data is unavailable.
        if status == "live" and match_score is None:
            _raw_h = r.get("home_goals", r.get("home_team_goal_count", None))
            _raw_a = r.get("away_goals", r.get("away_team_goal_count", None))
            logger.warning(
                f"[fixtures_service] Live match {home} vs {away} has no goal data — "
                f"NOT defaulting to 0-0 (raw home_goals={_raw_h}, away_goals={_raw_a})"
            )
        # Compute period/minute for live matches using _elapsed_min from above
        period = None
        minute = None
        if status == "live":
            has_ht = match_score and match_score.get("halftime") is not None
            if _elapsed_min is not None:
                try:
                    elapsed = max(0, _elapsed_min)
                    if elapsed <= 47:
                        period = "1T"
                        minute = min(elapsed, 45)
                    elif elapsed <= 62:
                        period = "HT"
                        minute = None
                    else:
                        period = "2T"
                        minute = min(elapsed - 15, 90)
                except (ValueError, TypeError):
                    pass
            if has_ht and period == "1T":
                period = "2T"

        odds_home = r.get("odds_home_win", r.get("odds_ft_home_team_win", None))
        odds_draw = r.get("odds_draw", r.get("odds_ft_draw", None))
        odds_away = r.get("odds_away_win", r.get("odds_ft_away_team_win", None))
        odds_over25 = r.get("odds_over_25", r.get("odds_ft_over25", None))
        odds_under25 = r.get("odds_ft_under25", r.get("odds_under_25", r.get("odds_under25", None)))
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
        # Pre-match probabilities from FootyStats (0-100 scale).
        # Guard: treat 0 or near-zero as missing — early-season / MLS-start data
        # often returns 0 which would suppress the Poisson model fallback.
        def _valid_pct(val):
            """Return val only if it's a positive percentage, else None."""
            try:
                v = float(val) if val is not None else None
            except (ValueError, TypeError):
                return None
            return v if v is not None and v > 0.0 else None

        over15_pct = _valid_pct(r.get("over_15_percentage_pre_match"))
        over25_pct = _valid_pct(r.get("over_25_percentage_pre_match"))
        over35_pct = _valid_pct(r.get("over_35_percentage_pre_match"))
        over45_pct = _valid_pct(r.get("over_45_percentage_pre_match"))
        btts_pct = _valid_pct(r.get("btts_percentage_pre_match"))
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
            over15_pct = float(over15_pct) if over15_pct is not None and float(over15_pct) > 0 else None
            over25_pct = float(over25_pct) if over25_pct is not None and float(over25_pct) > 0 else None
            over35_pct = float(over35_pct) if over35_pct is not None and float(over35_pct) > 0 else None
            over45_pct = float(over45_pct) if over45_pct is not None and float(over45_pct) > 0 else None
            btts_pct = float(btts_pct) if btts_pct is not None and float(btts_pct) > 0 else None
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
        # Known aliases: API name -> canonical substring to search in DB
        _TEAM_ALIASES = {
            "psg": "paris saint-germain",
            "inter milan": "internazionale",
            "nec": "n.e.c.",
            "rennes": "rennais",
            "man united": "manchester united",
            "man city": "manchester city",
            "atletico madrid": "atletico de madrid",
            "fc barcelona": "barcelona",
            "ac milan": "milan",
            "napoli": "napoli",
            "real sociedad": "real sociedad",
            "celta vigo": "celta de vigo",
            "betis": "real betis",
            "hertha": "hertha",
            "mainz": "mainz",
            "wolfsburg": "wolfsburg",
            "rb leipzig": "rasenballsport leipzig",
        }

        def _normalize_team_name(name: str) -> str:
            """Strip common suffixes/prefixes and normalize for matching."""
            import re
            n = name.strip().lower()
            # Remove common suffixes/prefixes
            for suffix in [" fc", " sc", " ec", " ac", " cf", " fk", " bk", " sk",
                           " afc", " ssc", " as", " rcd", " cd", " se", " rc",
                           " fr", " nfc", " if", " ff"]:
                if n.endswith(suffix):
                    n = n[:-len(suffix)].strip()
            for prefix in ["fc ", "sc ", "fk ", "sk ", "ac ", "as ", "rc ", "se ",
                           "club atletico ", "clube atletico ", "ca "]:
                if n.startswith(prefix):
                    n = n[len(prefix):].strip()
            # Remove dots (N.E.C. -> NEC)
            n = n.replace(".", "")
            # Normalize whitespace
            n = re.sub(r'\s+', ' ', n).strip()
            return n

        def _token_match_score(name_a: str, name_b: str) -> float:
            """Token overlap score between two names (0.0-1.0)."""
            a_tokens = set(_normalize_team_name(name_a).split())
            b_tokens = set(_normalize_team_name(name_b).split())
            if not a_tokens or not b_tokens:
                return 0.0
            overlap = a_tokens & b_tokens
            # Score = overlap relative to the smaller set
            smaller = min(len(a_tokens), len(b_tokens))
            return len(overlap) / smaller if smaller > 0 else 0.0

        # ---- Previous season blending (#064) ----
        _MIN_SEASON_MATCHES = 5
        _BLEND_STAT_COLS = [
            "goals_scored_per_match_home", "goals_scored_per_match_away",
            "goals_scored_per_match_overall", "goals_conceded_per_match_home",
            "goals_conceded_per_match_away", "goals_conceded_per_match_overall",
            "goals_scored_avg_home", "goals_scored_avg_away",
            "goals_conceded_avg_home", "goals_conceded_avg_away",
            "goals_scored_avg_overall", "goals_conceded_avg_overall",
            "corners_per_match", "cards_per_match",
            "btts_percentage", "clean_sheet_percentage",
            "xg_for_avg", "xg_against_avg",
        ]

        def _find_team_in_df(name: str, df, log_prefix: str = "") -> Optional["pd.Series"]:
            """Find a team in a DataFrame using 6 matching strategies. Shared by current/prev season."""
            if df is None:
                return None
            nc = pick_column(df, ["team_name", "team", "name", "club"])
            if not nc:
                return None
            # 1. Exact
            row = df[df[nc] == name]
            if len(row) > 0:
                return row.iloc[0]
            # 1b. Alias
            alias = _TEAM_ALIASES.get(name.lower())
            if alias:
                for idx, tv in df[nc].items():
                    if alias in str(tv).lower():
                        return df.loc[idx]
            # 2. Substring
            for idx, tv in df[nc].items():
                tvl = str(tv).lower()
                nl = name.lower()
                if nl in tvl or tvl in nl:
                    return df.loc[idx]
            # 3. Normalized
            norm = _normalize_team_name(name)
            for idx, tv in df[nc].items():
                if _normalize_team_name(str(tv)) == norm:
                    return df.loc[idx]
            # 4. Token overlap
            best_s, best_i, best_v = 0.0, None, None
            for idx, tv in df[nc].items():
                s = _token_match_score(name, str(tv))
                if s > best_s:
                    best_s, best_i, best_v = s, idx, tv
            if best_s >= 0.5 and len(name) > 2:
                return df.loc[best_i]
            # 5. Prefix
            if len(name) <= 4:
                nl = name.lower()
                for idx, tv in df[nc].items():
                    tvl = str(tv).lower()
                    if tvl.startswith(nl + " ") or tvl.startswith(nl + "."):
                        return df.loc[idx]
            return None

        def _blend_row(current_row, prev_row, games_played):
            """Blend current + previous season stats based on games played.

            weight = current season weight (0.0 = 100% previous season, 1.0 = 100% current).
            E.g. mp=0 → weight=0.00 (fully previous), mp=3 → weight=0.60, mp>=5 → weight=1.00.
            """
            if prev_row is None:
                return current_row
            if current_row is None:
                return prev_row
            # weight = current season weight: 0.0 means 100% prev, 1.0 means 100% current
            weight = min(1.0, (games_played or 0) / _MIN_SEASON_MATCHES)
            blended = current_row.copy()
            for col in _BLEND_STAT_COLS:
                curr_v = current_row.get(col) if col in current_row.index else None
                prev_v = prev_row.get(col) if col in prev_row.index else None
                try:
                    if curr_v is not None and prev_v is not None:
                        blended[col] = float(curr_v) * weight + float(prev_v) * (1 - weight)
                    elif prev_v is not None and (curr_v is None or weight < 0.5):
                        blended[col] = float(prev_v)
                except (ValueError, TypeError):
                    pass
            return blended

        def get_team_row(name: str) -> Optional["pd.Series"]:
            if teams is None:
                logger.warning(f"[lambda-diag] teams DataFrame is None for league={league_id}")
                return None
            name_col = pick_column(teams, ["team_name", "team", "name", "club"])
            if not name_col:
                logger.warning(f"[lambda-diag] no name column found in teams. cols={list(teams.columns)[:10]}")
                return None
            # 1. Exact match
            row = teams[teams[name_col] == name]
            if len(row) > 0:
                return row.iloc[0]

            # 1b. Known alias lookup
            alias = _TEAM_ALIASES.get(name.lower())
            if alias:
                for idx, team_val in teams[name_col].items():
                    if alias in str(team_val).lower():
                        logger.warning(
                            f"[lambda-diag] Exact match failed for '{name}', "
                            f"alias matched '{team_val}' (alias='{alias}') in col={name_col}"
                        )
                        return teams.loc[idx]

            # 2. Substring match (both directions)
            for idx, team_val in teams[name_col].items():
                tv = str(team_val).lower()
                nl = name.lower()
                if nl in tv or tv in nl:
                    logger.warning(
                        f"[lambda-diag] Exact match failed for '{name}', "
                        f"fuzzy matched '{team_val}' (substring) in col={name_col}"
                    )
                    return teams.loc[idx]

            # 3. Normalized exact match (strip FC/SC/AC etc.)
            norm_name = _normalize_team_name(name)
            for idx, team_val in teams[name_col].items():
                if _normalize_team_name(str(team_val)) == norm_name:
                    logger.warning(
                        f"[lambda-diag] Exact match failed for '{name}', "
                        f"normalized matched '{team_val}' in col={name_col}"
                    )
                    return teams.loc[idx]

            # 4. Token overlap (>= 50% token match for multi-word names)
            best_score = 0.0
            best_idx = None
            best_val = None
            for idx, team_val in teams[name_col].items():
                score = _token_match_score(name, str(team_val))
                if score > best_score:
                    best_score = score
                    best_idx = idx
                    best_val = team_val
            if best_score >= 0.5 and len(name) > 2:
                logger.warning(
                    f"[lambda-diag] Exact match failed for '{name}', "
                    f"token matched '{best_val}' (score={best_score:.2f}) in col={name_col}"
                )
                return teams.loc[best_idx]

            # 5. Short name prefix match (for "AZ" -> "AZ Alkmaar", "NEC" -> "NEC Nijmegen")
            if len(name) <= 4:
                nl = name.lower()
                for idx, team_val in teams[name_col].items():
                    tv = str(team_val).lower()
                    # Check if db name starts with the short name + space
                    if tv.startswith(nl + " ") or tv.startswith(nl + "."):
                        logger.warning(
                            f"[lambda-diag] Exact match failed for '{name}', "
                            f"prefix matched '{team_val}' in col={name_col}"
                        )
                        return teams.loc[idx]

            sample = list(teams[name_col].head(5))
            logger.warning(
                f"[lambda-diag] Team '{name}' NOT FOUND after 5 strategies. "
                f"norm='{norm_name}' Sample: {sample}"
            )
            return None
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

        # #064: Blend with previous season if current season has insufficient data
        if teams2 is not None:
            mp_cols = ["matches_played", "games_played", "matches"]
            home_mp = safe(get_stat(home_row, mp_cols) if home_row is not None else None, None)
            away_mp = safe(get_stat(away_row, mp_cols) if away_row is not None else None, None)
            try:
                home_mp_f = float(home_mp) if home_mp is not None else 0
            except (ValueError, TypeError):
                home_mp_f = 0
            try:
                away_mp_f = float(away_mp) if away_mp is not None else 0
            except (ValueError, TypeError):
                away_mp_f = 0

            if home_mp_f < _MIN_SEASON_MATCHES or home_row is None:
                prev_home = _find_team_in_df(home, teams2, log_prefix="prev-home")
                if prev_home is not None:
                    home_row = _blend_row(home_row, prev_home, home_mp_f)
                    logger.warning(
                        f"[lambda-diag] Blended {home}: mp={home_mp_f}, "
                        f"prev-season data available, weight={min(1.0, home_mp_f / _MIN_SEASON_MATCHES):.2f}"
                    )
            if away_mp_f < _MIN_SEASON_MATCHES or away_row is None:
                prev_away = _find_team_in_df(away, teams2, log_prefix="prev-away")
                if prev_away is not None:
                    away_row = _blend_row(away_row, prev_away, away_mp_f)
                    logger.warning(
                        f"[lambda-diag] Blended {away}: mp={away_mp_f}, "
                        f"prev-season data available, weight={min(1.0, away_mp_f / _MIN_SEASON_MATCHES):.2f}"
                    )
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
            league_id=league_id,
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
        _ou_deflation = 1.0
        _1x2_deflation = 1.0
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
            # O/U and 1X2 deflation per-league (calibration #052-#058)
            if _corr := _lc.get("lambda_multiplier"):
                _ou_deflation = float(_corr.get("value", 1.0))
            if _corr := _lc.get("1x2_multiplier"):
                _1x2_deflation = float(_corr.get("value", 1.0))
        except Exception as _e:
            logger.debug(f"[Gap2] Lambda corrections skipped for {league_id}: {_e}")

        # Apply O/U deflation to lambdas for Poisson (#058)
        lam_home_ou = lam_home * _ou_deflation
        lam_away_ou = lam_away * _ou_deflation
        lam_total_ou = lam_home_ou + lam_away_ou

        # Raw total for volatility classification (no deflation)
        lam_total_raw = lam_home + lam_away
        if lam_total_raw < 2.2:
            league_volatility = "BAIXA"
        elif lam_total_raw < 3.0:
            league_volatility = "MODERADA"
        else:
            league_volatility = "ALTA"

        # Over/Under with deflation applied (#058)
        over05 = 1.0 - poisson_cdf(0, lam_total_ou)
        over15 = 1.0 - poisson_cdf(1, lam_total_ou)
        over25 = 1.0 - poisson_cdf(2, lam_total_ou)
        over35 = 1.0 - poisson_cdf(3, lam_total_ou)

        # BTTS with deflation via lambdas (#058)
        lam_home_btts = lam_home * (_btts_multiplier if _btts_multiplier else 1.0)
        lam_away_btts = lam_away * (_btts_multiplier if _btts_multiplier else 1.0)
        btts_poisson = (1.0 - poisson_pmf(0, lam_home_btts)) * (1.0 - poisson_pmf(0, lam_away_btts))

        # Apply BTTS multiplier to FootyStats pre-match % (separate source)
        if _btts_multiplier is not None and btts_pct is not None:
            btts_pct = min(100.0, max(0.0, float(btts_pct) * _btts_multiplier))

        if _ou_deflation != 1.0:
            logger.info(
                f"[deflation] {league_id}: O/U defl={_ou_deflation:.2f}, "
                f"lam_raw={lam_total_raw:.3f}, lam_defl={lam_total_ou:.3f}, "
                f"P(O2.5)={over25:.3f}"
            )

        # BTTS fusion: blend available sources for more robust estimate
        # Sources: (1) FootyStats pre-match %, (2) Poisson model, (3) team-level BTTS %
        btts_final: float
        _btts_sources = []
        if btts_pct is not None:
            _btts_sources.append(("footystats", float(btts_pct)))
        _btts_sources.append(("poisson", round(btts_poisson * 100.0, 1)))
        if home_btts_pct_team is not None and away_btts_pct_team is not None:
            # Average of both teams' BTTS percentages as an independent estimator
            _btts_team_avg = (float(home_btts_pct_team) + float(away_btts_pct_team)) / 2.0
            _btts_sources.append(("team_avg", round(_btts_team_avg, 1)))

        if len(_btts_sources) >= 3:
            # 3 sources: read calibrated weights per league, fallback to defaults (#055)
            _w_default = {"footystats": 0.40, "poisson": 0.30, "team_avg": 0.30}
            try:
                from backend.modeling.lambda_calculator import get_lambda_corrections
                _corr = get_lambda_corrections(league_id)
                _btts_fs = _corr.get("btts_weight_footystats", {}).get("value")
                _btts_po = _corr.get("btts_weight_poisson", {}).get("value")
                _btts_ta = _corr.get("btts_weight_team_avg", {}).get("value")
                if _btts_fs is not None and _btts_po is not None and _btts_ta is not None:
                    _w = {"footystats": float(_btts_fs), "poisson": float(_btts_po), "team_avg": float(_btts_ta)}
                else:
                    _w = _w_default
            except Exception:
                _w = _w_default
            btts_final = sum(v * _w[k] for k, v in _btts_sources)
        elif len(_btts_sources) == 2:
            k1, v1 = _btts_sources[0]
            k2, v2 = _btts_sources[1]
            if k1 == "footystats":
                # FootyStats + Poisson: 60/40
                btts_final = v1 * 0.60 + v2 * 0.40
            else:
                # Poisson + Team avg: 50/50
                btts_final = v1 * 0.50 + v2 * 0.50
        else:
            # Single source (Poisson only)
            btts_final = _btts_sources[0][1]
        btts_final = round(min(100.0, max(0.0, btts_final)), 1)

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
            "footystatsId": int(r.get("id")) if r.get("id") is not None else None,
            "leagueId": league_id,
            "leagueName": league_id.replace("-", " ").title(),
            "homeTeam": {"name": home, "logo": "", "form": [], "rating": 0},
            "awayTeam": {"name": away, "logo": "", "form": [], "rating": 0},
            "datetime": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt.tzinfo else dt.isoformat() + "Z",
            "stadium": stadium,
            "status": status,
            "score": match_score,
            "period": period,
            "minute": minute,
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
                "bttsProb": btts_final,
                "over05Prob": round(over05 * 100.0, 1),
                "over15Prob": float(over15_pct) if over15_pct is not None else round(over15 * 100.0, 1),
                "over25Prob": float(over25_pct) if over25_pct is not None else round(over25 * 100.0, 1),
                "over35Prob": float(over35_pct) if over35_pct is not None else round(over35 * 100.0, 1),
                "over45Prob": float(over45_pct) if over45_pct is not None else round((1.0 - poisson_cdf(4, lam_total_ou)) * 100.0, 1),
                "under15Prob": 100.0 - (float(over15_pct) if over15_pct is not None else round(over15 * 100.0, 1)),
                "under25Prob": 100.0 - (float(over25_pct) if over25_pct is not None else round(over25 * 100.0, 1)),
                "under35Prob": 100.0 - (float(over35_pct) if over35_pct is not None else round(over35 * 100.0, 1)),
                "under45Prob": 100.0 - (float(over45_pct) if over45_pct is not None else round((1.0 - poisson_cdf(4, lam_total_ou)) * 100.0, 1)),
                "lambdaHome": round(lam_home, 3),
                "lambdaAway": round(lam_away, 3),
                "lambdaTotal": round(lam_total_raw, 3),
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
        # --- API-Football enrichment (odds, injuries, lineups) ---
        # Fills gaps in FootyStats data; degrades silently if unavailable.
        _afc = None
        try:
            from backend.services.api_football_client import APIFootballClient
            _afc = APIFootballClient()
            _current_record = records[-1]
            footystats_id = r.get("id")
            if footystats_id and _afc:
                # 2.1 — Enrich odds from API-Football (fill missing only)
                try:
                    af_odds = _afc.get_odds(int(footystats_id), ttl_minutes=180)
                    if af_odds:
                        best = _afc.extract_best_odds(af_odds)
                        odds_dict = _current_record["odds"]
                        if not odds_dict.get("under25") and best.get("under_25"):
                            odds_dict["under25"] = best["under_25"]
                            logger.info(f"[API-Football] Under 2.5 odd enriched: {best['under_25']}")
                        if not odds_dict.get("bttsNo") and best.get("btts_no"):
                            odds_dict["bttsNo"] = best["btts_no"]
                        # Cards odds (#095)
                        for line_sfx in ("25", "35", "45", "55"):
                            ov_key = f"cards_over_{line_sfx}"
                            un_key = f"cards_under_{line_sfx}"
                            line_dot = f"{line_sfx[0]}.{line_sfx[1]}"
                            if best.get(ov_key) and not odds_dict.get(f"cards_over_{line_dot}"):
                                odds_dict[f"cards_over_{line_dot}"] = best[ov_key]
                            if best.get(un_key) and not odds_dict.get(f"cards_under_{line_dot}"):
                                odds_dict[f"cards_under_{line_dot}"] = best[un_key]
                        _current_record.setdefault("source_flags", []).append("api_football_odds")
                except Exception as e:
                    logger.debug(f"[API-Football] Odds enrichment skipped: {e}")

                # 2.2 — Enrich with pre-match injuries
                try:
                    injuries = _afc.get_injuries_sync(int(footystats_id), ttl_minutes=240)
                    if injuries:
                        injury_data = {
                            "home": [inj for inj in injuries if inj.get("team", {}).get("name") == home],
                            "away": [inj for inj in injuries if inj.get("team", {}).get("name") == away],
                        }
                        _current_record["injuries"] = injury_data
                        _current_record.setdefault("source_flags", []).append("api_football_injuries")
                except Exception as e:
                    logger.debug(f"[API-Football] Injuries enrichment skipped: {e}")

                # 2.3 — Enrich with lineups (available 30-60 min before kickoff)
                try:
                    if status == "incomplete":
                        lineups = _afc.get_fixture_lineups(int(footystats_id), ttl_minutes=30)
                        if lineups:
                            _current_record["lineups"] = lineups
                            _current_record.setdefault("source_flags", []).append("api_football_lineups")
                except Exception as e:
                    logger.debug(f"[API-Football] Lineups enrichment skipped: {e}")
        except Exception as e:
            logger.debug(f"[API-Football] Client init skipped: {e}")

        # Calculate market predictions (mercados) for this match
        try:
            record = records[-1]
            _regime = record["stats"].get("leagueRegime", "NORMAL")
            _volatilidade = record["stats"].get("leagueVolatility", "MODERADA")

            # For finished matches: compute mercados from raw FootyStats probabilities
            # only — skip Mistral AI and calibration adjustments that cause instability
            # (e.g. Under 3.5 → Under 4.5 flip when recalculated post-match).
            if status != "finished":
                # Apply Isotonic Regression calibration (Gap 5)
                try:
                    from backend.modeling.calibrator import calibrate_match_stats
                    record["stats"] = calibrate_match_stats(record["stats"], league_id, _regime)
                except Exception as _cal_err:
                    logger.debug(f"[Gap5] Calibration skipped for {home} vs {away}: {_cal_err}")

                # ML Ensemble — Champion/Challenger (Gap 6)
                # Uses trained RF + XGBoost models when available; falls back to Poisson.
                try:
                    from backend.ml.predictor import predict_1x2, is_ml_available, champion_vs_challenger
                    if is_ml_available(league_id):
                        _ml_features = {
                            "home_goals_scored_avg_r5": record["stats"].get("lambdaHome", 1.3),
                            "away_goals_scored_avg_r5": record["stats"].get("lambdaAway", 1.0),
                            "home_goals_conceded_avg_r5": record["stats"].get("lambdaAway", 1.0),
                            "away_goals_conceded_avg_r5": record["stats"].get("lambdaHome", 1.3),
                            "home_xg_avg_r5": xg_home_team or 0.0,
                            "away_xg_avg_r5": xg_away_team or 0.0,
                            "home_possession_avg_r5": home_poss or 50.0,
                            "away_possession_avg_r5": away_poss or 50.0,
                            "home_corners_avg_r5": home_corners_pm or 5.0,
                            "away_corners_avg_r5": away_corners_pm or 5.0,
                            "home_shots_avg_r5": home_shots_pm or 12.0,
                            "away_shots_avg_r5": away_shots_pm or 10.0,
                            "elo_diff": (homeRating - awayRating) if homeRating and awayRating else 0.0,
                            "home_elo": homeRating or 1500.0,
                            "away_elo": awayRating or 1500.0,
                            "league_avg_goals": league_avgs.get("avg_goals", 2.5),
                            "league_avg_corners": league_avgs.get("avg_corners", 10.0),
                            "league_avg_cards": league_avgs.get("avg_cards", 3.5),
                        }
                        _poisson_probs = {
                            "homeWinProb": record["stats"].get("homeWinProb", 0),
                            "drawProb": record["stats"].get("drawProb", 0),
                            "awayWinProb": record["stats"].get("awayWinProb", 0),
                        }
                        _ml_result = predict_1x2(_ml_features, league_id)
                        _final = champion_vs_challenger(_poisson_probs, _ml_result, league_id)
                        if _final.get("_source") == "ml_ensemble":
                            record["stats"]["homeWinProb"] = _final.get("home_win", record["stats"]["homeWinProb"])
                            record["stats"]["drawProb"] = _final.get("draw", record["stats"]["drawProb"])
                            record["stats"]["awayWinProb"] = _final.get("away_win", record["stats"]["awayWinProb"])
                            record["stats"]["predictionSource"] = "ml_ensemble"
                            logger.info(f"[Gap6] ML prediction applied to {home} vs {away}")
                        else:
                            record["stats"]["predictionSource"] = "poisson"
                        # Market models (Over/Under + BTTS) from ML
                        try:
                            from backend.ml.market_models import predict_all_markets
                            _market_preds = predict_all_markets(_ml_features, league_id)
                            for mkt, prob in _market_preds.items():
                                if prob is not None:
                                    record["stats"][f"ml_{mkt}"] = prob
                        except Exception as _mkt_err:
                            logger.debug(f"[Gap6] Market ML skipped for {home} vs {away}: {_mkt_err}")

                except Exception as _ml_err:
                    logger.debug(f"[Gap6] ML prediction skipped for {home} vs {away}: {_ml_err}")

            mercados = selecionar_mercados_v2(record, _regime, _volatilidade, league_id=league_id)
            # Safety hard constraint (#098): block complementary markets >105%
            try:
                from backend.services.safety_validation import validar_mercados_complementares
                mercados = validar_mercados_complementares(mercados)
            except Exception as _safety_err:
                logger.debug(f"[Safety] Validation skipped: {_safety_err}")
            record["mercados"] = mercados

            # Track picks per match (#102)
            try:
                from backend.services.reliability_tracker import track_event
                track_event("consistency", "picks_per_match", float(len(mercados)))
            except Exception:
                pass

            # Expose v2 corner predictions in the API response
            try:
                from backend.modeling.corners.predictor import predict_corners
                _corner_result = predict_corners(
                    home_stats=record["stats"],
                    away_stats=record["stats"],
                    league_id=league_id,
                    league_stats=league_avgs if isinstance(league_avgs, dict) else None,
                    footystats_probs=record["stats"],
                    odds=record.get("odds"),
                )
                _proj = _corner_result.get("projection", {})
                _dec = _corner_result.get("decision", {})
                _dq = _corner_result.get("data_quality", {})
                record["cornerPredictions"] = {
                    "projectedTotalFT": _proj.get("expected_total_corners_ft"),
                    "projectedTotal1H": _proj.get("expected_total_corners_1h"),
                    "projectedTotal2H": _proj.get("expected_total_corners_2h"),
                    "modelSource": _proj.get("model_source", "unknown"),
                    "dataQualityTier": _dq.get("data_quality_tier", "UNKNOWN"),
                    "governanceState": _dec.get("governance_state", "UNKNOWN"),
                    "recommendedLine": _dec.get("line"),
                    "recommendedSide": _dec.get("side"),
                    "recommendedEdge": _dec.get("edge"),
                    "noBet": _dec.get("no_bet", False),
                    "engineVersion": _corner_result.get("engineVersion", "v2"),
                }
            except Exception as _corner_err:
                logger.debug(f"[Corners] Prediction enrichment skipped for {home} vs {away}: {_corner_err}")

            # Expose v2 card predictions in the API response (#085, #085b NB2)
            try:
                from backend.modeling.cards_engine import predict_cards
                _cards_result = predict_cards(
                    home_stats=record["stats"],
                    away_stats=record["stats"],
                    league_id=league_id,
                    league_stats=league_avgs if isinstance(league_avgs, dict) else None,
                )
                record["cardsPredictions"] = {
                    "projectedTotalCards": _cards_result.get("projected_total_cards"),
                    "cardsLambda": _cards_result.get("cards_lambda"),
                    "cardsLambdaHome": _cards_result.get("cards_lambda_home"),
                    "cardsLambdaAway": _cards_result.get("cards_lambda_away"),
                    "cardsMultiplier": _cards_result.get("cards_multiplier"),
                    "overdispersion": _cards_result.get("overdispersion"),
                    "modelSource": _cards_result.get("model_source", "poisson_fallback"),
                    "adjustments": _cards_result.get("adjustments"),
                    "lines": {
                        k: {"prob": v["prob_pct"]}
                        for k, v in _cards_result.get("lines", {}).items()
                    },
                }
            except Exception as _cards_err:
                logger.debug(f"[Cards] Prediction enrichment skipped for {home} vs {away}: {_cards_err}")

            # Build enriched context for Mistral match analysis
            record["_mistral_context"] = {
                "home_form": record.get("homeForm"),
                "away_form": record.get("awayForm"),
                "h2h": record.get("h2h"),
                "injuries": record.get("injuries"),
                "lineups": record.get("lineups"),
                "predictions": mercados,
            }
        except Exception as e:
            logger.warning(f"Falha ao calcular mercados para {home} vs {away}: {e}")
            records[-1]["mercados"] = []
      except Exception as e:
        _match_label = f"{r.get('home_team', '?')} vs {r.get('away_team', '?')}"
        logger.error(f"[fixtures_service] Skipping match {_match_label}: {type(e).__name__}: {e}", exc_info=True)
        continue
    return records
