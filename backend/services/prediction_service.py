class PredictionService:
    async def calculate_predictions(self, match_data: dict):
        picks = [
            { "market": "ML_HOME", "prob": 0.52, "odds": 1.95, "ev": (0.52*1.95)-1, "risk": "SAFE" },
            { "market": "BTTS_YES", "prob": 0.55, "odds": 1.80, "ev": (0.55*1.80)-1, "risk": "NEUTRAL" },
        ]
        return { "picks": picks }
    async def get_prediction_by_id(self, prediction_id: str):
        return { "id": prediction_id, "status": "N/A" }
