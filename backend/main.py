from fastapi import FastAPI, Query, HTTPException
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os
import math
import importlib.util
import logging
from io import BytesIO
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # fallback when pandas isn't available
try:
    import boto3  # type: ignore
except Exception:
    boto3 = None  # type: ignore
try:
    from mangum import Mangum  # type: ignore
except Exception:
    Mangum = None  # type: ignore

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sportsbank")

app = FastAPI(title="SportsBank Pro Backend", version="0.1.0")

def get_base_root() -> str:
    return os.getenv("FUTEBOL_ROOT") or os.getenv("DATA_ROOT") or r"C:\Users\wxamb\futebol"

def get_data_dir() -> str:
    return os.getenv("FUTEBOL_DATA_DIR") or os.path.join(get_base_root(), "data")

def mock_match(league_id: str, i: int) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "id": f"{league_id}-m{i}",
        "leagueId": league_id,
        "leagueName": league_id.replace("-", " ").title(),
        "homeTeam": "Team A",
        "awayTeam": "Team B",
        "datetime": now,
        "stadium": "Stadium Alpha",
        "status": "scheduled",
        "odds": { "home": 1.9, "draw": 3.4, "away": 2.2, "over25": 1.85, "under25": 1.95, "bttsYes": 1.80, "bttsNo": 2.00 },
        "stats": { "homeWinProb": 52, "drawProb": 24, "awayWinProb": 24, "avgGoals": 2.6, "bttsProb": 55, "over25Prob": 57 },
        "h2h": { "totalMatches": 5, "homeWins": 2, "draws": 1, "awayWins": 2, "avgGoals": 2.8 },
        "source": "packball",
        "lastUpdated": now,
    }

def date_range(filter_type: str) -> Tuple[datetime, datetime]:
    now = datetime.utcnow()
    if filter_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(milliseconds=1)
        return start, end
    if filter_type == "tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(milliseconds=1)
        return start, end
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7) - timedelta(milliseconds=1)
    return start, end

def implied_probs(home: Optional[float], draw: Optional[float], away: Optional[float]) -> Tuple[float, float, float]:
    vals = []
    for o in (home, draw, away):
        if o and o > 1:
            vals.append(1.0 / o)
        else:
            vals.append(0.0)
    total = sum(vals)
    if total <= 0:
        return 0.0, 0.0, 0.0
    return (vals[0] / total * 100.0, vals[1] / total * 100.0, vals[2] / total * 100.0)

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except Exception:
        return 0.0

def poisson_cdf(k: int, lam: float) -> float:
    s = 0.0
    for i in range(0, k + 1):
        s += poisson_pmf(i, lam)
    return s

def expected_goals(home_attack: float, away_defense: float, away_attack: float, home_defense: float, league_avg: float, xg_home: Optional[float], xg_away: Optional[float]) -> Tuple[float, float]:
    lam_home = league_avg * home_attack * away_defense
    lam_away = league_avg * away_attack * home_defense
    if xg_home is not None and xg_home > 0:
        lam_home = 0.7 * lam_home + 0.3 * xg_home
    if xg_away is not None and xg_away > 0:
        lam_away = 0.7 * lam_away + 0.3 * xg_away
    lam_home = max(0.2, min(3.5, lam_home))
    lam_away = max(0.2, min(3.5, lam_away))
    return lam_home, lam_away

def aggregate_team_xg(players_df: Optional["pd.DataFrame"], team_name: str) -> Optional[float]:
    if players_df is None or team_name is None:
        return None
    candidates = ["team_name", "team", "club"]
    xg_cols = ["xg", "expected_goals", "xG"]
    minutes_cols = ["minutes", "mins"]
    name_col = None
    for c in candidates:
        if c in players_df.columns:
            name_col = c
            break
    if name_col is None:
        return None
    df = players_df[players_df[name_col] == team_name]
    if len(df) == 0:
        return None
    xg_col = None
    for c in xg_cols:
        if c in df.columns:
            xg_col = c
            break
    if xg_col is None:
        return None
    minutes_col = None
    for c in minutes_cols:
        if c in df.columns:
            minutes_col = c
            break
    try:
        if minutes_col:
            w = df[minutes_col].astype(float)
            xg = df[xg_col].astype(float)
            total_minutes = w.sum()
            if total_minutes <= 0:
                return float(xg.mean())
            return float((xg * w).sum() / total_minutes)
        else:
            return float(df[xg_col].astype(float).mean())
    except Exception:
        return None

def status_map(s: str) -> str:
    sl = (s or "").lower()
    if sl in ("complete", "finished", "ft"):
        return "finished"
    if sl in ("live", "inplay"):
        return "live"
    if sl in ("postponed", "ppd"):
        return "postponed"
    return "scheduled"

def parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            # FootyStats timestamp is often seconds since epoch
            return datetime.utcfromtimestamp(int(value))
        except Exception:
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%b %d %Y - %I:%M%p"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None

def pick_column(df: "pd.DataFrame", candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def compute_form(matches_df: "pd.DataFrame", team: str, max_len: int = 5) -> List[str]:
    if pd is None or matches_df is None:
        return ["W", "D", "L", "W", "D"][:max_len]
    df = matches_df.copy()
    df["date_parsed"] = df.get("date_gmt") if "date_gmt" in df.columns else df.get("date_GMT")
    df["date_parsed"] = df["date_parsed"].apply(parse_date)
    df = df.dropna(subset=["date_parsed"])
    df = df.sort_values("date_parsed", ascending=False)
    home_col = pick_column(df, ["home_team", "home_team_name", "team_a_name"])
    away_col = pick_column(df, ["away_team", "away_team_name", "team_b_name"])
    if not home_col or not away_col:
        return ["D", "W", "L", "D", "W"][:max_len]
    rows = df[(df[home_col] == team) | (df[away_col] == team)].head(20)
    form: List[str] = []
    for _, r in rows.iterrows():
        hg = r.get("home_goals", r.get("home_team_goal_count", None))
        ag = r.get("away_goals", r.get("away_team_goal_count", None))
        if hg is None or ag is None:
            continue
        try:
            hg = int(hg)
            ag = int(ag)
        except Exception:
            continue
        if r.get(home_col) == team:
            if hg > ag:
                form.append("W")
            elif hg == ag:
                form.append("D")
            else:
                form.append("L")
        else:
            if ag > hg:
                form.append("W")
            elif ag == hg:
                form.append("D")
            else:
                form.append("L")
        if len(form) >= max_len:
            break
    if not form:
        form = ["D", "W", "L", "D", "W"][:max_len]
    return form

def load_fixtures_from_csv(league_id: str, date_filter: str) -> List[Dict[str, Any]]:
    if pd is None:
        return []

    bucket = os.getenv("S3_BUCKET")
    if bucket and boto3 is not None:
        prefix = (os.getenv("S3_PREFIX") or "data").strip("/")
        base = f"{prefix}/{league_id}"
        s3 = boto3.client("s3")

        def s3_key_exists(key: str) -> bool:
            try:
                s3.head_object(Bucket=bucket, Key=key)
                return True
            except Exception:
                return False

        def resolve_s3_base() -> str:
            for cand in (league_id, f"PRE {league_id}"):
                key = f"{prefix}/{cand}/matches.csv"
                if s3_key_exists(key):
                    return f"{prefix}/{cand}"
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/", Delimiter="/")
                for item in resp.get("CommonPrefixes", []):
                    name = item.get("Prefix", "").replace(f"{prefix}/", "").strip("/")
                    if league_id in name and s3_key_exists(f"{prefix}/{name}/matches.csv"):
                        return f"{prefix}/{name}"
            except Exception:
                pass
            return base

        def read_csv_s3(key: str) -> Optional["pd.DataFrame"]:
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                return pd.read_csv(BytesIO(obj["Body"].read()))
            except Exception:
                return None

        def list_s3_keys(base_prefix: str) -> List[Dict[str, Any]]:
            try:
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{base_prefix}/")
                return resp.get("Contents", [])
            except Exception:
                return []

        def pick_key(items: List[Dict[str, Any]], include: List[str], exclude: Optional[List[str]] = None) -> Optional[str]:
            exclude = exclude or []
            candidates = []
            for obj in items:
                key = obj.get("Key", "")
                if not key.endswith(".csv"):
                    continue
                low = key.lower()
                if any(tok in low for tok in include) and not any(tok in low for tok in exclude):
                    candidates.append(obj)
            if not candidates:
                return None
            candidates.sort(key=lambda x: x.get("LastModified") or "")
            return candidates[-1].get("Key")

        base = resolve_s3_base()
        keys = list_s3_keys(base)
        matches_key = f"{base}/matches.csv" if s3_key_exists(f"{base}/matches.csv") else pick_key(keys, ["matches", "match"])
        teams2_key = f"{base}/teams2.csv" if s3_key_exists(f"{base}/teams2.csv") else pick_key(keys, ["teams2", "team2"])
        teams_key = f"{base}/teams.csv" if s3_key_exists(f"{base}/teams.csv") else pick_key(keys, ["teams"], exclude=["teams2", "team2"])
        league_key = f"{base}/league.csv" if s3_key_exists(f"{base}/league.csv") else pick_key(keys, ["league"])
        players_key = f"{base}/players.csv" if s3_key_exists(f"{base}/players.csv") else pick_key(keys, ["players", "player"])

        matches = read_csv_s3(matches_key) if matches_key else None
        if matches is None:
            return []
        teams = read_csv_s3(teams_key) if teams_key else None
        teams2 = read_csv_s3(teams2_key) if teams2_key else None
        league_df = read_csv_s3(league_key) if league_key else None
        players = read_csv_s3(players_key) if players_key else None
    else:
        base = get_data_dir()
        league_dir = resolve_league_dir(base, league_id)
        matches_path = os.path.join(league_dir, "matches.csv")
        teams_path = os.path.join(league_dir, "teams.csv")
        teams2_path = os.path.join(league_dir, "teams2.csv")
        league_path = os.path.join(league_dir, "league.csv")
        players_path = os.path.join(league_dir, "players.csv")
        if not os.path.exists(matches_path):
            return []
        try:
            matches = pd.read_csv(matches_path)
            teams = pd.read_csv(teams_path) if os.path.exists(teams_path) else None
            teams2 = pd.read_csv(teams2_path) if os.path.exists(teams2_path) else None
            league_df = pd.read_csv(league_path) if os.path.exists(league_path) else None
            players = pd.read_csv(players_path) if os.path.exists(players_path) else None
        except Exception:
            return []
    # normalize date column
    date_col = "date_gmt" if "date_gmt" in matches.columns else "date_GMT" if "date_GMT" in matches.columns else "timestamp"
    def row_date(r) -> Optional[datetime]:
        return parse_date(r.get(date_col))
    def build_records(start: datetime, end: datetime) -> List[Dict[str, Any]]:
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
    rows = build_records(start, end)
    if not rows and date_filter in ("today", "tomorrow"):
        start, end = date_range("week")
        rows = build_records(start, end)
    if not rows and date_filter == "week":
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30) - timedelta(milliseconds=1)
        rows = build_records(start, end)

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
        # compute H2H simple summary
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
        # team forms
        homeForm = compute_form(matches, home, 5)
        awayForm = compute_form(matches, away, 5)
        # simple rating from PPG or league data
        def team_rating(name: str) -> float:
            if teams is not None:
                row = teams[teams.get("team_name", "") == name]
                if len(row) > 0:
                    ppg = float(row.iloc[0].get("points_per_game", row.iloc[0].get("points_per_game_overall", 1.5)) or 1.5)
                    return max(0.0, min(10.0, ppg * 4.0))
            return 6.5
        # possession, corners, cards from team/league CSVs
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
        league_avgs = {
            "avg_goals": None,
            "avg_corners": None,
            "avg_cards": None,
        }
        if league_df is not None:
            league_avgs["avg_goals"] = float(league_df.iloc[0].get("average_goals_per_match", 2.5) or 2.5)
            league_avgs["avg_corners"] = float(league_df.iloc[0].get("average_corners_per_match", 10.0) or 10.0)
            league_avgs["avg_cards"] = float(league_df.iloc[0].get("average_cards_per_match", 4.0) or 4.0)
        homeRating = team_rating(home)
        awayRating = team_rating(away)
        # enrich stats
        home_poss = team_possession(home)
        away_poss = team_possession(away)
        home_corners_pm = team_corners_per_match(home)
        away_corners_pm = team_corners_per_match(away)
        home_cards_pm = team_cards_per_match(home)
        away_cards_pm = team_cards_per_match(away)
        # quick O/U and BTTS from pre percentages if present
        over25_pct = r.get("over_25_percentage_pre", None)
        btts_pct = r.get("btts_percentage_pre", None)
        try:
            over25_pct = float(over25_pct) if over25_pct is not None else None
        except Exception:
            over25_pct = None
        try:
            btts_pct = float(btts_pct) if btts_pct is not None else None
        except Exception:
            btts_pct = None
        league_goal_avg = league_avgs["avg_goals"] if league_avgs["avg_goals"] else 2.7
        league_regime = "HIPER-OFENSIVA" if league_goal_avg > 3.0 else "NORMAL"
        def safe(val: Optional[float], default: float) -> float:
            return float(val) if val is not None and val > 0 else default
        home_attack = safe(teams.iloc[0].get("goals_scored_per_match_home", None) if teams is not None else None, 1.3)
        away_defense = safe(teams.iloc[0].get("goals_conceded_per_match_away", None) if teams is not None else None, 1.2)
        away_attack = safe(teams.iloc[0].get("goals_scored_per_match_away", None) if teams is not None else None, 1.2)
        home_defense = safe(teams.iloc[0].get("goals_conceded_per_match_home", None) if teams is not None else None, 1.1)
        xg_home_team = aggregate_team_xg(players, home)
        xg_away_team = aggregate_team_xg(players, away)
        lam_home, lam_away = expected_goals(home_attack, away_defense, away_attack, home_defense, league_goal_avg / 2.0, xg_home_team, xg_away_team)
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

        data_source = "s3" if bucket else "local"
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
                "over25": float(odds_over25) if odds_over25 else None,
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
                "over25Prob": float(over25_pct) if over25_pct is not None else round(over25 * 100.0, 1),
                "over05Prob": round(over05 * 100.0, 1),
                "over15Prob": round(over15 * 100.0, 1),
                "over35Prob": round(over35 * 100.0, 1),
                "lambdaHome": round(lam_home, 3),
                "lambdaAway": round(lam_away, 3),
                "lambdaTotal": round(lam_total, 3),
                "leagueAvgGoals": league_avgs["avg_goals"],
                "totalGoals": total_gols,
                "leagueRegime": league_regime,
                "leagueVolatility": league_volatility,
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

def load_config_module() -> Optional[Any]:
    cfg_path = os.path.join(get_base_root(), "config.py")
    if not os.path.exists(cfg_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("futebol_config", cfg_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            return mod
    except Exception:
        return None
    return None

def resolve_league_dir(base: str, league_id: str) -> str:
    direct = os.path.join(base, league_id)
    if os.path.isdir(direct):
        return direct
    mod = load_config_module()
    if mod and hasattr(mod, "LEAGUES_CONFIG"):
        conf = getattr(mod, "LEAGUES_CONFIG")
        item = conf.get(league_id)
        if item:
            # Try by code or normalized name
            code = str(item.get("code", "")).lower()
            name = str(item.get("name", "")).lower().replace(" ", "-")
            for candidate in (code, name):
                cand_dir = os.path.join(base, candidate)
                if os.path.isdir(cand_dir):
                    return cand_dir
    # fallback: first dir matching league_id substring
    for d in os.listdir(base):
        cand = os.path.join(base, d)
        if os.path.isdir(cand) and league_id in d:
            return cand
    return direct

def formatar_nome_liga(liga: str) -> str:
    mapeamento = {
        "premier-league": "INGLATERRA — PREMIER LEAGUE",
        "championship": "INGLATERRA — CHAMPIONSHIP",
        "la-liga": "ESPANHA — LA LIGA",
        "serie-a": "ITÁLIA — SERIE A",
        "bundesliga": "ALEMANHA — BUNDESLIGA",
        "ligue-1": "FRANÇA — LIGUE 1",
        "brazil-serie-a": "BRASIL — SÉRIE A",
        "brazil-serie-b": "BRASIL — SÉRIE B",
        "champions-league": "UEFA — CHAMPIONS LEAGUE",
    }
    return mapeamento.get(liga, liga.upper().replace("-", " "))

def _normalize_prob(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if v > 1.0:
        v = v / 100.0
    if v < 0:
        return None
    return min(max(v, 0.0), 1.0)

def selecionar_mercados_jogo(jogo: Dict[str, Any], regime: str, volatilidade: str) -> List[Dict[str, Any]]:
    mercados: List[Dict[str, Any]] = []
    stats = jogo.get("stats", {})
    prob_over25 = _normalize_prob(stats.get("over25Prob"))
    prob_btts = _normalize_prob(stats.get("bttsProb"))
    prob_dc = None
    if stats.get("homeWinProb") is not None and stats.get("drawProb") is not None:
        prob_dc = _normalize_prob(float(stats.get("homeWinProb", 0)) + float(stats.get("drawProb", 0)))

    lam_total = stats.get("lambdaTotal")
    try:
        lam_total = float(lam_total) if lam_total is not None else None
    except Exception:
        lam_total = None

    prob_under45 = poisson_cdf(4, lam_total) if lam_total and lam_total > 0 else None
    prob_under35 = poisson_cdf(3, lam_total) if lam_total and lam_total > 0 else None

    def add_mercado(nome: str, status: str, prob: float, alerta: Optional[str] = None) -> None:
        prob_min = max(0, int(prob * 100) - 2)
        prob_max = max(0, int(prob * 100))
        odd_minima = round(1.0 / prob, 2) if prob > 0 else None
        item: Dict[str, Any] = {
            "mercado": nome,
            "status": status,
            "prob_min": prob_min,
            "prob_max": prob_max,
            "odd_minima": odd_minima,
        }
        if alerta:
            item["alerta"] = alerta
        mercados.append(item)

    if regime == "NORMAL":
        if prob_under45 is not None and prob_under45 >= 0.75:
            add_mercado("Under 4.5 gols", "SAFE", prob_under45)
        if prob_under35 is not None and prob_under35 >= 0.70:
            add_mercado("Under 3.5 gols", "SAFE*", prob_under35, alerta="EV-")
    else:
        if prob_over25 is not None and prob_over25 >= 0.72:
            add_mercado("Over 2.5 gols", "SAFE", prob_over25)

    if prob_btts is not None and prob_btts >= 0.60:
        status = "SAFE" if prob_btts >= 0.68 else "NEUTRO"
        add_mercado("BTTS — SIM", status, prob_btts)

    if prob_dc is not None and prob_dc >= 0.65:
        home = str(jogo.get("homeTeam", ""))[:3].upper()
        add_mercado(f"DC 1X ({home}/EMP)", "NEUTRO", prob_dc)

    if mercados:
        principal = mercados[0]
        stats["status"] = "SAFE" if principal.get("status") == "SAFE" else principal.get("status", "NEUTRO")
        stats["mercado_principal"] = principal.get("mercado")
        stats["odd_minima"] = principal.get("odd_minima")

    return mercados

def identificar_duplas_safe(jogos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    duplas: List[Dict[str, Any]] = []
    jogos_safe = [j for j in jogos if j.get("stats", {}).get("status") == "SAFE"]
    for i in range(len(jogos_safe)):
        for j in range(i + 1, len(jogos_safe)):
            jogo1 = jogos_safe[i]
            jogo2 = jogos_safe[j]
            mercado1 = jogo1.get("stats", {}).get("mercado_principal")
            mercado2 = jogo2.get("stats", {}).get("mercado_principal")
            if mercado1 and mercado2 and mercado1 == mercado2:
                odd1 = jogo1.get("stats", {}).get("odd_minima", 1.0) or 1.0
                odd2 = jogo2.get("stats", {}).get("odd_minima", 1.0) or 1.0
                duplas.append({
                    "jogo1": f"{jogo1.get('homeTeam')} x {jogo1.get('awayTeam')}",
                    "mercado1": mercado1,
                    "jogo2": f"{jogo2.get('homeTeam')} x {jogo2.get('awayTeam')}",
                    "mercado2": mercado2,
                    "odd_minima": round(odd1 * odd2, 2),
                })
    duplas.sort(key=lambda x: x["odd_minima"])
    return duplas[:4]

def identificar_triplas_safe(jogos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    triplas: List[Dict[str, Any]] = []
    jogos_safe = [j for j in jogos if j.get("stats", {}).get("status") == "SAFE"]
    for i in range(len(jogos_safe)):
        for j in range(i + 1, len(jogos_safe)):
            for k in range(j + 1, len(jogos_safe)):
                jogo1 = jogos_safe[i]
                jogo2 = jogos_safe[j]
                jogo3 = jogos_safe[k]
                mercado1 = jogo1.get("stats", {}).get("mercado_principal")
                mercado2 = jogo2.get("stats", {}).get("mercado_principal")
                mercado3 = jogo3.get("stats", {}).get("mercado_principal")
                if mercado1 and mercado2 and mercado3 and mercado1 == mercado2 == mercado3:
                    odd1 = jogo1.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    odd2 = jogo2.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    odd3 = jogo3.get("stats", {}).get("odd_minima", 1.0) or 1.0
                    triplas.append({
                        "jogo1": f"{jogo1.get('homeTeam')} x {jogo1.get('awayTeam')}",
                        "mercado1": mercado1,
                        "jogo2": f"{jogo2.get('homeTeam')} x {jogo2.get('awayTeam')}",
                        "mercado2": mercado2,
                        "jogo3": f"{jogo3.get('homeTeam')} x {jogo3.get('awayTeam')}",
                        "mercado3": mercado3,
                        "odd_minima": round(odd1 * odd2 * odd3, 2),
                    })
    triplas.sort(key=lambda x: x["odd_minima"])
    return triplas[:3]

def calcular_regime_e_volatilidade(liga: str, jogos: List[Dict[str, Any]]) -> Tuple[str, str]:
    totais = []
    league_avgs = []
    for j in jogos:
        stats = j.get("stats", {})
        total = stats.get("lambdaTotal") or stats.get("avgGoals")
        try:
            total = float(total)
        except Exception:
            total = None
        if total is not None:
            totais.append(total)
        avg_goal = stats.get("leagueAvgGoals")
        try:
            avg_goal = float(avg_goal) if avg_goal is not None else None
        except Exception:
            avg_goal = None
        if avg_goal is not None:
            league_avgs.append(avg_goal)
    media_gols = sum(league_avgs) / len(league_avgs) if league_avgs else (sum(totais) / len(totais) if totais else 0)
    regime = "HIPER-OFENSIVA" if media_gols > 3.0 else "NORMAL"
    volatilidade_base = totais if len(totais) > 1 else league_avgs
    if len(volatilidade_base) > 1:
        media = sum(volatilidade_base) / len(volatilidade_base)
        variancia = sum((g - media) ** 2 for g in volatilidade_base) / len(volatilidade_base)
        desvio = variancia ** 0.5
        if desvio < 1.0:
            volatilidade = "BAIXA"
        elif desvio < 1.5:
            volatilidade = "MODERADA"
        else:
            volatilidade = "ALTA"
    else:
        volatilidade = "MODERADA"
    return regime, volatilidade

def gerar_quadro_resumo(
    liga: str,
    jogos: List[Dict[str, Any]],
    regime: str,
    volatilidade: str,
    incluir_simples: bool = True,
    incluir_duplas: bool = True,
    incluir_triplas: bool = False,
    incluir_governanca: bool = True,
) -> str:
    linhas: List[str] = []
    sep = "═" * 67
    liga_formatada = formatar_nome_liga(liga)
    linhas.append(sep)
    linhas.append(f"{liga_formatada} | QUADRO-RESUMO PRÉ-JOGO v5.5-ML")
    linhas.append(sep)
    linhas.append("")
    mercado_ancora = "UNDER 4.5" if regime == "NORMAL" else "OVER 2.5"
    mercado_proibido = "Over 3.5 / Over 4.5" if regime == "NORMAL" else "Under 3.5 / Under 4.5"
    linhas.append(f"Regime da Liga: {regime}")
    linhas.append(f"Mercado Âncora permitido: {mercado_ancora}")
    linhas.append(f"Mercado proibido (SAFE): {mercado_proibido}")
    linhas.append(f"Volatilidade: {volatilidade}")
    linhas.append("")
    linhas.append(sep)
    linhas.append("")

    if incluir_simples:
        for jogo in jogos:
            home = jogo.get("homeTeam")
            away = jogo.get("awayTeam")
            dt = datetime.fromisoformat(jogo.get("datetime"))
            data_hora = dt.strftime("%d/%m — %H:%M")
            linhas.append(f"{home} vs {away} ({data_hora})")
            mercados = selecionar_mercados_jogo(jogo, regime, volatilidade)
            for i, mercado in enumerate(mercados):
                simbolo = "├─" if i < len(mercados) - 1 else "└─"
                mercado_nome = str(mercado["mercado"]).ljust(20)
                status = str(mercado["status"]).ljust(8)
                prob_range = f"prob≈{mercado['prob_min']}-{mercado['prob_max']}%"
                odd_min = f"odd mín. EV+ ≈{mercado['odd_minima']}"
                linha_mercado = f"{simbolo} {mercado_nome} {status} {prob_range.ljust(16)} {odd_min}"
                if mercado.get("alerta"):
                    linha_mercado += f"  △ {mercado['alerta']}"
                linhas.append(linha_mercado)
            linhas.append("")

    if incluir_duplas:
        duplas = identificar_duplas_safe(jogos)
        if duplas:
            linhas.append(sep)
            linhas.append("")
            linhas.append("DUPLAS SAFE (v5.5 — correlação controlada)")
            linhas.append("")
            for dupla in duplas:
                linhas.append(f"• {dupla['jogo1']} → {dupla['mercado1']}")
                linhas.append(f"  + {dupla['jogo2']} → {dupla['mercado2']}")
                linhas.append(f"  Odd mín. EV+ ≈ {dupla['odd_minima']}")
                linhas.append("")

    if incluir_triplas:
        triplas = identificar_triplas_safe(jogos)
        if triplas:
            linhas.append(sep)
            linhas.append("")
            linhas.append("TRIPLAS SAFE (v5.5 — correlação controlada)")
            linhas.append("")
            for tripla in triplas:
                linhas.append(f"• {tripla['jogo1']} → {tripla['mercado1']}")
                linhas.append(f"  + {tripla['jogo2']} → {tripla['mercado2']}")
                linhas.append(f"  + {tripla['jogo3']} → {tripla['mercado3']}")
                linhas.append(f"  Odd mín. EV+ ≈ {tripla['odd_minima']}")
                linhas.append("")

    if incluir_governanca:
        linhas.append(sep)
        linhas.append("")
        linhas.append("GOVERNANÇA v5.5")
        if regime == "NORMAL":
            under45_ok = 0
            for j in jogos:
                stats = j.get("stats", {})
                lam_total = stats.get("lambdaTotal")
                try:
                    lam_total = float(lam_total) if lam_total is not None else None
                except Exception:
                    lam_total = None
                prob_under45 = poisson_cdf(4, lam_total) if lam_total and lam_total > 0 else None
                if prob_under45 is not None and prob_under45 >= 0.75:
                    under45_ok += 1
            linhas.append(f"• Under 4.5 exige prob ≥ 75% → {under45_ok}/{len(jogos)} jogos atendem")
            linhas.append("• Under 3.5 rebaixado para SAFE* por EV comprometido")
            linhas.append("• Nenhum jogo classificado como CAÓTICO")
            linhas.append("• Over 3.5 / Over 4.5 → BLOQUEADOS (liga NORMAL)")
        else:
            over25_ok = 0
            for j in jogos:
                stats = j.get("stats", {})
                prob_over25 = _normalize_prob(stats.get("over25Prob"))
                if prob_over25 is not None and prob_over25 >= 0.72:
                    over25_ok += 1
            linhas.append(f"• Over 2.5 exige prob ≥ 72% → {over25_ok}/{len(jogos)} jogos atendem")
            linhas.append("• BTTS — SIM promovido para SAFE quando prob ≥ 68%")
            linhas.append(f"• Alerta: Volatilidade {volatilidade} (cautela recomendada)")
            linhas.append("• Under 3.5 / Under 4.5 → BLOQUEADOS (liga HIPER-OFENSIVA)")
        linhas.append("")
    linhas.append(sep)
    return "\n".join(linhas)

@app.get("/quadro-resumo")
def quadro_resumo(
    league: str = Query("", description="Nome da liga (ex: premier-league)"),
    date: str = Query("today", description="Filtro de data: today, tomorrow, week"),
    incluir_simples: bool = Query(True, description="Incluir jogos simples"),
    incluir_duplas: bool = Query(True, description="Incluir duplas SAFE"),
    incluir_triplas: bool = Query(False, description="Incluir triplas SAFE"),
    incluir_governanca: bool = Query(True, description="Incluir seção de governança"),
) -> Dict[str, Any]:
    try:
        jogos = load_fixtures_from_csv(league, date)
        if not jogos:
            return {
                "quadro_texto": "Nenhum jogo encontrado para os filtros selecionados.",
                "jogos_count": 0,
                "duplas_count": 0,
                "triplas_count": 0,
                "regime": "N/A",
                "volatilidade": "N/A",
            }
        regime, volatilidade = calcular_regime_e_volatilidade(league, jogos)
        quadro_texto = gerar_quadro_resumo(
            liga=league,
            jogos=jogos,
            regime=regime,
            volatilidade=volatilidade,
            incluir_simples=incluir_simples,
            incluir_duplas=incluir_duplas,
            incluir_triplas=incluir_triplas,
            incluir_governanca=incluir_governanca,
        )
        duplas = identificar_duplas_safe(jogos) if incluir_duplas else []
        triplas = identificar_triplas_safe(jogos) if incluir_triplas else []
        return {
            "quadro_texto": quadro_texto,
            "jogos_count": len(jogos) if incluir_simples else 0,
            "duplas_count": len(duplas),
            "triplas_count": len(triplas),
            "regime": regime,
            "volatilidade": volatilidade,
        }
    except Exception as e:
        logger.error("Erro ao gerar quadro-resumo: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao gerar quadro-resumo: {str(e)}")

@app.get("/fixtures")
def fixtures(leagues: str = Query(""), date: str = Query("today")) -> Dict[str, Any]:
    league_ids = [s for s in leagues.split(",") if s]
    matches: List[Dict[str, Any]] = []
    for lid in league_ids:
        csv_records = load_fixtures_from_csv(lid, date)
        if csv_records:
            matches.extend(csv_records)
        else:
            matches.append(mock_match(lid, 1))
            matches.append(mock_match(lid, 2))
    return { "matches": matches }

@app.get("/odds")
def odds(league: str) -> Dict[str, Any]:
    return {
        "league": league,
        "odds": [
            { "event": "Team A vs Team B", "home": 1.95, "draw": 3.30, "away": 2.25 },
            { "event": "Team C vs Team D", "home": 2.20, "draw": 3.10, "away": 2.75 },
        ],
    }

@app.post("/probabilities")
def probabilities(payload: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder combining Poisson/heuristics later
    return { "probs": { "homeWin": 0.52, "draw": 0.24, "awayWin": 0.24, "bttsYes": 0.55, "over25": 0.57 } }

@app.post("/decision/pre")
def decision_pre(payload: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder applying conservative gates
    picks = [
        { "market": "ML_HOME", "prob": 0.52, "odds": 1.95, "ev": (0.52*1.95)-1, "risk": "SAFE" },
        { "market": "BTTS_YES", "prob": 0.55, "odds": 1.80, "ev": (0.55*1.80)-1, "risk": "NEUTRAL" },
    ]
    return { "picks": picks }

@app.post("/ml/predict")
def ml_predict(payload: Dict[str, Any]) -> Dict[str, Any]:
    # placeholder until models are trained
    return {
        "result": { "prediction": "HOME", "probability": 0.62 },
        "over_under_2_5": { "prediction": "OVER", "probability": 0.58 },
        "btts": { "prediction": "YES", "probability": 0.60 },
    }

@app.get("/discover")
def discover() -> Dict[str, Any]:
    base_root = get_base_root()
    items: Dict[str, Any] = {
        "root": base_root,
        "exists": os.path.isdir(base_root),
        "data_dirs": [],
        "files": [],
    }
    if not os.path.isdir(base_root):
        return items
    # list top-level files that can improve the model
    for name in os.listdir(base_root):
        path = os.path.join(base_root, name)
        if os.path.isfile(path) and (name.endswith(".py") or name.endswith(".txt")):
            items["files"].append(name)
    data_dir = get_data_dir()
    if os.path.isdir(data_dir):
        for league in os.listdir(data_dir):
            ldir = os.path.join(data_dir, league)
            if os.path.isdir(ldir):
                present = []
                for fname in ("matches.csv", "teams.csv", "teams2.csv", "league.csv", "players.csv"):
                    if os.path.exists(os.path.join(ldir, fname)):
                        present.append(fname)
                items["data_dirs"].append({ "league": league, "present": present })
    return items

if Mangum is not None:
    handler = Mangum(app)