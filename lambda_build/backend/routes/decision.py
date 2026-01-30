from fastapi import APIRouter
from typing import Dict, Any
from backend.services.decision_service import DecisionService

router = APIRouter(tags=["decision"])
service = DecisionService()

@router.post("/decision/pre")
def decision_pre(payload: Dict[str, Any]) -> Dict[str, Any]:
    return service.pre(payload)
