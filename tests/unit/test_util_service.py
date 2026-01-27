from datetime import datetime
from backend.services.util_service import status_map, parse_date, pick_column, compute_form
import pandas as pd

def test_status_map():
    assert status_map("FT") == "finished"
    assert status_map("live") == "live"
    assert status_map("PPD") == "postponed"
    assert status_map("unknown") == "scheduled"

def test_parse_date_iso():
    dt = parse_date("2024-06-01T12:00:00")
    assert isinstance(dt, datetime)
    assert dt.year == 2024

def test_pick_column_and_compute_form():
    df = pd.DataFrame([
        {"date_gmt": "2024-06-01 10:00:00", "home_team": "A", "away_team": "B", "home_goals": 1, "away_goals": 0},
        {"date_gmt": "2024-06-02 10:00:00", "home_team": "B", "away_team": "A", "home_goals": 0, "away_goals": 0},
        {"date_gmt": "2024-06-03 10:00:00", "home_team": "A", "away_team": "C", "home_goals": 0, "away_goals": 2},
    ])
    col = pick_column(df, ["home_team", "home_team_name"])
    assert col == "home_team"
    form_a = compute_form(df, "A", 3)
    assert len(form_a) == 3
