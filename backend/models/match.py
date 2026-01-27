from pydantic import BaseModel

class Match(BaseModel):
    id: str
    home_team: str
    away_team: str
    date: str
    league: str
