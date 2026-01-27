from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(tags=["discover"])

@router.get("/discover")
def discover() -> Dict[str, Any]:
    from backend.main import discover as _discover
    return _discover()
