from fastapi import APIRouter, Query, Body
from typing import Dict, Any, List, Optional
from backend.services.combinadas_service import gerar_combinadas

router = APIRouter(tags=["combinadas"])

_EMPTY = {
    "intra": [],
    "inter": [],
    "total_intra": 0,
    "total_inter": 0,
    "total_jogos": 0,
}


def _run_combinadas(
    jogos: List[Dict[str, Any]],
    tipos_list: List[str],
    min_status: str,
    limite_intra: int,
    limite_inter: int,
) -> Dict[str, Any]:
    """Shared logic for GET and POST endpoints."""
    if not jogos:
        return {**_EMPTY, "_info": "Nenhum jogo encontrado para os filtros selecionados."}

    try:
        return gerar_combinadas(
            jogos=jogos,
            tipos=tipos_list,
            min_status=min_status,
            limite_intra=limite_intra,
            limite_inter=limite_inter,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {**_EMPTY, "_error": f"Erro ao gerar combinadas: {exc}"}


@router.post("/combinadas")
def combinadas_post(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """
    POST endpoint that accepts pre-loaded matches directly.

    Avoids re-fetching fixtures from external APIs (which caused 504 timeouts
    when many leagues were selected). The frontend already has all match data
    loaded, so it sends the matches array in the request body.

    Expected body: {
        "matches": [...],        // array of match objects with mercados/predictions
        "tipos": "intra,inter",  // optional
        "min_status": "NEUTRO",  // optional
        "limite_intra": 10,      // optional
        "limite_inter": 10,      // optional
    }
    """
    jogos: List[Dict[str, Any]] = payload.get("matches") or []

    # Map frontend field name "predictions" → backend field name "mercados"
    for jogo in jogos:
        if "mercados" not in jogo and "predictions" in jogo:
            jogo["mercados"] = jogo["predictions"]

    tipos_raw: str = payload.get("tipos", "intra,inter")
    tipos_list = [t.strip().lower() for t in tipos_raw.split(",") if t.strip()]
    min_status = payload.get("min_status", "NEUTRO")
    limite_intra = min(int(payload.get("limite_intra", 8)), 20)
    limite_inter = min(int(payload.get("limite_inter", 8)), 20)

    return _run_combinadas(jogos, tipos_list, min_status, limite_intra, limite_inter)


@router.get("/combinadas")
def combinadas(
    leagues: str = Query("", description="Liga(s) separadas por vírgula"),
    date: str = Query("today"),
    tipos: str = Query("intra,inter", description="Tipos de combinada: intra, inter ou ambos"),
    min_status: str = Query("NEUTRO", description="Status mínimo dos mercados: SAFE ou NEUTRO"),
    limite_intra: int = Query(8, ge=1, le=20),
    limite_inter: int = Query(8, ge=1, le=20),
) -> Dict[str, Any]:
    """
    GET endpoint (legacy) — re-fetches fixtures from APIs.

    Prefer POST /combinadas with pre-loaded matches for better performance.
    """
    from backend.routes.fixtures import fixtures as get_fixtures

    tipos_list: List[str] = [t.strip().lower() for t in tipos.split(",") if t.strip()]

    try:
        raw = get_fixtures(leagues=leagues, date=date)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {**_EMPTY, "_error": f"Erro ao buscar jogos: {exc}"}

    jogos: List[Dict[str, Any]] = raw.get("matches", [])
    return _run_combinadas(jogos, tipos_list, min_status, limite_intra, limite_inter)
