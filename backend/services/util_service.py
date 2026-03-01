try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None
from datetime import datetime, timezone
from typing import Any, List, Optional

def status_map(s: str) -> str:
    sl = (s or "").lower()
    if sl in ("complete", "finished", "ft"):
        return "finished"
    if sl in ("live", "inplay", "incomplete"):
        return "live"
    if sl in ("postponed", "ppd"):
        return "postponed"
    if sl in ("cancelled", "canceled", "void", "abandoned"):
        return "cancelled"
    return "scheduled"

def parse_date(value: Any) -> Optional[datetime]:
    """Parse date from various formats. Returns timezone-aware datetime in UTC."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%b %d %Y - %I:%M%p"):
            try:
                dt = datetime.strptime(value, fmt)
                # FootyStats date_gmt fields are GMT — attach UTC timezone
                return dt.replace(tzinfo=timezone.utc)
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
        return []
    df = matches_df.copy()
    # Parse dates — support both date_gmt string and unix timestamp columns
    if "date_gmt" in df.columns:
        df["date_parsed"] = df["date_gmt"]
    elif "date_GMT" in df.columns:
        df["date_parsed"] = df["date_GMT"]
    elif "timestamp" in df.columns:
        df["date_parsed"] = df["timestamp"]
    else:
        return []
    from backend.services.util_service import parse_date as _parse
    df["date_parsed"] = df["date_parsed"].apply(_parse)
    df = df.dropna(subset=["date_parsed"])
    # Filter only finished matches (exclude scheduled, live, postponed)
    status_col = pick_column(df, ["status"])
    if status_col:
        finished_statuses = ["complete", "finished", "ft"]
        df = df[df[status_col].astype(str).str.lower().isin(finished_statuses)]
    df = df.sort_values("date_parsed", ascending=False)
    home_col = pick_column(df, ["home_team", "home_team_name", "team_a_name"])
    away_col = pick_column(df, ["away_team", "away_team_name", "team_b_name"])
    if not home_col or not away_col:
        return []
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
    return form
