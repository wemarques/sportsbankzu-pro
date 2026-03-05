# CLAUDE.md — Project Instructions for Claude Code

## Project Overview

SportsBankZU Pro is a professional sports prediction system with a 3-layer architecture:
- **Backend**: FastAPI (Python) serving fixtures, probabilities, lambdas, and stats
- **Frontend 1**: Streamlit (app.py) with tables and probability charts
- **Frontend 2**: Next.js 14 dashboard with multi-league selector and match analysis

## Quick Commands

```bash
# Backend
uvicorn backend.main:app --reload --port 5001

# Streamlit
streamlit run app.py

# Next.js dashboard
cd frontend/next && npm run dev

# CLI (unified)
python -m cli --help

# Tests (Python)
pytest -q

# Tests (E2E Playwright)
cd frontend/next && npm run test:e2e
```

## Key Directories

- `backend/` — FastAPI app, routes, services, models, AI integration
- `backend/routes/` — API endpoints (fixtures, leagues, decision, quadro, ai, health)
- `backend/services/` — Business logic (math, market, fixtures, quadro, decision)
- `backend/modeling/` — Statistical models (lambda, xg_filter, chaos_detector, calibrator)
- `backend/ai/` — Mistral AI integration (auditor, context, prompts)
- `frontend/next/` — Next.js 14 App Router dashboard
- `frontend/next/e2e/` — Playwright E2E tests
- `cli/` — Click-based CLI wrapping backend services
- `scripts/` — Deployment and utility scripts

## Context7 Usage

Context7 MCP is configured for this project. Use it to fetch up-to-date documentation:

- Next.js: `use context7 /vercel/next.js`
- Playwright: `use context7 /microsoft/playwright`
- FastAPI: `use context7 /fastapi/fastapi`
- Tailwind CSS: `use context7 /tailwindlabs/tailwindcss`
- Radix UI: `use context7 /radix-ui/primitives`
- Recharts: `use context7 /recharts/recharts`
- Click: `use context7 /pallets/click`

## Environment Variables

- `MISTRAL_API_KEY` — Required for AI audit features
- `PY_BACKEND_URL` — Backend URL for Next.js API routes
- `BACKEND_URL` — Backend URL for Streamlit
- `FUTEBOL_ROOT` / `DATA_ROOT` — Root data directory for backend
- `S3_BUCKET` — Optional S3 bucket for data storage

## Regra de Investigação Obrigatória

Antes de propor ou implementar qualquer correção:

1. **Não assuma a causa raiz** — investigue todos os caminhos de código envolvidos, do backend ao frontend, incluindo mappers, services, routes e componentes React
2. **Trace o fluxo completo** — siga o dado desde a origem (API externa) até a renderização final no browser, identificando cada transformação intermediária
3. **Verifique todos os pontos de entrada** — um mesmo campo pode ser setado em múltiplos locais (mapper, service, route, endpoint de overlay, polling do frontend). Cheque todos antes de concluir
4. **Considere caching e deploy** — cache da API (SQLite TTL), cache do browser, builds desatualizados no Vercel e cold starts do Lambda podem mascarar ou perpetuar bugs
5. **Valide com dados reais** — quando possível, adicione logging temporário ou leia logs existentes para confirmar qual valor a API externa realmente retorna, em vez de supor
6. **Implemente defesa em profundidade** — não confie em uma única camada de correção. Se o bug pode ocorrer por múltiplas causas (ex: status "incomplete", "live", campo numérico inesperado), adicione guards em cada camada relevante
7. **Teste o cenário completo** — após implementar, simule mentalmente o fluxo com os dados do bug reportado e confirme que TODAS as variantes são cobertas antes de declarar resolvido

## Conventions

- Language: Portuguese (pt-BR) for UI, English for code and comments
- Supported leagues: 22+ European and South American leagues
- Prediction markets: 1X2, Over/Under (1.5-4.5), BTTS, Double Chance
- Status levels: SAFE, NEUTRO, ALERTA
- Regimes: NORMAL, HIPER-OFENSIVA
- Sempre que solicitado a realizar análises financeiras ou previsões esportivas, utilize as ferramentas mapeadas no Antigravity localizadas em `backend/services` e `backend/modeling`. Não tente simular a lógica de cálculo manualmente.
