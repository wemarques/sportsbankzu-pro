from fastapi import APIRouter, Query
from typing import Dict, Any, List
from backend.services.combinadas_service import gerar_combinadas

router = APIRouter(tags=["combinadas"])


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
    Retorna duplas de apostas intra e inter jogos.

    - **intra**: dois mercados do mesmo jogo (e.g. BTTS + Over 2.5 em Botafogo x Vitória)
    - **inter**: um mercado de cada jogo diferente (e.g. Under 3.5 em jogo 1 + DC 1X em jogo 2)
    """
    from backend.routes.fixtures import fixtures as get_fixtures

    tipos_list: List[str] = [t.strip().lower() for t in tipos.split(",") if t.strip()]

    try:
        raw = get_fixtures(leagues=leagues, date=date)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {
            "intra": [],
            "inter": [],
            "total_intra": 0,
            "total_inter": 0,
            "total_jogos": 0,
            "_error": f"Erro ao buscar jogos: {exc}",
        }

    jogos: List[Dict[str, Any]] = raw.get("matches", [])

    if not jogos:
        return {
            "intra": [],
            "inter": [],
            "total_intra": 0,
            "total_inter": 0,
            "total_jogos": 0,
            "_info": "Nenhum jogo encontrado para os filtros selecionados.",
        }

    try:
        result = gerar_combinadas(
            jogos=jogos,
            tipos=tipos_list,
            min_status=min_status,
            limite_intra=limite_intra,
            limite_inter=limite_inter,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {
            "intra": [],
            "inter": [],
            "total_intra": 0,
            "total_inter": 0,
            "total_jogos": 0,
            "_error": f"Erro ao gerar combinadas: {exc}",
        }

    return result
