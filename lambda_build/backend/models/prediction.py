from pydantic import BaseModel

class Prediction(BaseModel):
    match_id: str
    lambda_home: float
    lambda_away: float
    markets: dict
