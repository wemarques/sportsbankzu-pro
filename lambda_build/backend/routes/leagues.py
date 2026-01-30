from fastapi import APIRouter
import os

router = APIRouter(prefix="/leagues", tags=["leagues"])

def _get_data_dir() -> str:
    return os.getenv("FUTEBOL_DATA_DIR") or os.path.join(os.getenv("FUTEBOL_ROOT") or os.getenv("DATA_ROOT") or r"C:\Users\wxamb\futebol", "data")

@router.get("/")
async def get_leagues():
    data_dir = _get_data_dir()
    leagues = []
    if os.path.isdir(data_dir):
        for name in os.listdir(data_dir):
            if os.path.isdir(os.path.join(data_dir, name)):
                leagues.append(name)
    return {"leagues": leagues}

