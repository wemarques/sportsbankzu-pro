---
name: novo-mercado
description: Checklist #006 com os 7 pontos obrigatorios para adicionar um mercado novo (engine, ev_classification, market_validator, market_service, correlation_matrix, localAudit.ts, ai_analysis.py). Use ao criar ou estender um mercado.
---

# Checklist novo mercado (#006)

Movido do CLAUDE.md (era sempre carregado; /doctor 2026-09-08). Conteudo integral.

## Checklist novo mercado (#006) — 7 pontos obrigatórios

1. Engine — `backend/modeling/`
2. `backend/services/ev_classification.py`
3. `backend/modeling/market_validator.py`
4. `backend/services/market_service.py` (dedup)
5. `backend/services/correlation_matrix.py`
6. `frontend/next/src/lib/localAudit.ts` (evaluatePick)
7. `backend/routes/ai_analysis.py` (evaluatePick backend)
