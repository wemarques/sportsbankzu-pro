from fastapi import APIRouter, Query
from typing import Dict, Any
from backend.services.quadro_service import build_quadro_response

router = APIRouter(tags=["quadro"])

@router.get("/quadro-resumo")
def quadro_resumo(
    league: str = Query("", description="Nome da liga"),
    date: str = Query("today"),
    incluir_simples: bool = Query(True),
    incluir_duplas: bool = Query(True),
    incluir_triplas: bool = Query(False),
    incluir_governanca: bool = Query(True),
    formato: str = Query("detalhado"),
) -> Dict[str, Any]:
    return build_quadro_response(
        league=league,
        date=date,
        incluir_simples=incluir_simples,
        incluir_duplas=incluir_duplas,
        incluir_triplas=incluir_triplas,
        incluir_governanca=incluir_governanca,
        formato=formato,
    )
