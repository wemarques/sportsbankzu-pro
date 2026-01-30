from fastapi import APIRouter
from backend.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])
service = PredictionService()

@router.post("/")
async def get_predictions(match_data: dict):
    return await service.calculate_predictions(match_data)

@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str):
    return await service.get_prediction_by_id(prediction_id)

