from fastapi import APIRouter, Query
from backend.services.match_service import MatchService

router = APIRouter(prefix="/matches", tags=["matches"])
service = MatchService()

@router.get("/")
async def get_matches(league: str = Query(None), date: str = Query("today")):
    if not league:
        return {"matches": []}
    return {"matches": await service.get_matches(league, date)}

