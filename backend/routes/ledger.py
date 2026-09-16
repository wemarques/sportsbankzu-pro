# -*- coding: utf-8 -*-
"""#255 — `GET /ledger/dia` e `GET /ledger/agregado` (Fase 1 da reformulacao
do frontend, spec §6.3).

Fonte unica para o que o usuario ve: `prediction_ledger x ledger_outcomes`,
nunca `audit_results` (Regra #244, proibicao 13). Leitura pura: nenhuma rota
aqui grava nada. `backend/services/ledger_leitura.py` faz o trabalho; este
modulo so valida parametro HTTP e traduz erro em status code.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services import ledger_leitura

router = APIRouter(tags=["ledger"])


@router.get("/ledger/dia")
async def ledger_dia(data: str = Query(..., description="YYYY-MM-DD")):
    try:
        return ledger_leitura.dia(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")


@router.get("/ledger/agregado")
async def ledger_agregado(
    periodo: str = Query("30d", description="7d|30d|temporada"),
    familia: Optional[str] = Query(None),
    liga: Optional[str] = Query(None),
):
    try:
        return ledger_leitura.agregado(periodo, familia, liga)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")


@router.get("/ledger/picks")
async def ledger_picks(
    periodo: str = Query("30d", description="7d|30d|temporada"),
    familia: Optional[str] = Query(None),
    liga: Optional[str] = Query(None),
):
    try:
        return ledger_leitura.picks(periodo, familia, liga)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")
