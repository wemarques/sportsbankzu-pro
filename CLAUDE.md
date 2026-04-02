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

## API Routes (Lambda / API Gateway)

O backend Lambda é acessado via API Gateway em `https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/`.

**ATENÇÃO:** Os prefixos são inconsistentes:

| Endpoint | Rota Correta | ERRADO |
|----------|-------------|--------|
| Health check | `/health` | ~~/api/health~~ (404) |
| Fixtures | `/api/fixtures/...` | |
| Backtesting | `/api/backtesting/...` | |
| Calibrate | `POST /api/backtesting/calibrate?league=X` | ~~/api/backtesting/calibrate?league_id=X~~ (param errado) |
| Calibration status | `/api/backtesting/calibration-status` | |
| SAFE status | `/api/health/safe-status` | |

**Parâmetro de calibração:** O endpoint usa `league=` (NÃO `league_id=`).

**Timeout:** API Gateway tem hard limit de 30s. Calibração leva 15-40s. Se retornar 503, o Lambda continua processando e salva os dados.

**Deploy Lambda:**
```bash
# Verificar estado ANTES de deploy
MSYS_NO_PATHCONV=1 aws lambda get-function-configuration --function-name sportsbank-pro-backend --region us-east-1 --query '{State: State, LastUpdateStatus: LastUpdateStatus}'

# Só deployar quando State=Active e LastUpdateStatus=Successful
MSYS_NO_PATHCONV=1 aws lambda update-function-code --function-name sportsbank-pro-backend --s3-bucket meu-bucket-sportsbank --s3-key deploy/sportsbank_lambda.zip --region us-east-1
```

**Lambda Layer (scipy):**
O Lambda usa uma Layer separada (`scipy-numpy-layer`) com scipy para
os modelos NB2 (cards e corners). A Layer é independente do ZIP de deploy.
numpy já está no ZIP de deploy — a Layer contém apenas scipy.

- **Se a versão Python do Lambda mudar** (ex: python3.11 → python3.12),
  a Layer DEVE ser recriada — extensões C compiladas para 3.11 não carregam em 3.12.
- Sem Layer compatível, cards NB2 cai silenciosamente para Poisson fallback.
- Recriar: `pip install scipy -t layer/python/ --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.XX --no-deps`
- ZIP: `cd layer && zip -r ../scipy-layer.zip python/ -x '*.pyc' '*__pycache__*' '*.dist-info/*' '*/tests/*'`
- Publicar: `aws lambda publish-layer-version --layer-name scipy-numpy-layer --content S3Bucket=meu-bucket-sportsbank,S3Key=deploy/scipy-layer.zip --compatible-runtimes python3.XX --region us-east-1`
- Atachar: `aws lambda update-function-configuration --function-name sportsbank-pro-backend --layers <LAYER_ARN> --region us-east-1`
- Layer ARN atual: `arn:aws:lambda:us-east-1:838823110426:layer:scipy-numpy-layer:2`

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
- Supported leagues: 22+ European and South American leagues + Copa do Brasil
- Prediction markets: 1X2, Over/Under (0.5-4.5), BTTS, Double Chance, Corners (4.5-12.5), Cards Over/Under (2.5-5.5)
- Classification levels: SAFE, NEUTRO_QUALIFICADO, NEUTRO, NO_BET (see REGRAS #028)
- Regimes: NORMAL, HIPER-OFENSIVA
- Sempre que solicitado a realizar análises financeiras ou previsões esportivas, utilize as ferramentas mapeadas no Antigravity localizadas em `backend/services` e `backend/modeling`. Não tente simular a lógica de cálculo manualmente.

## Leitura Obrigatória

Antes de qualquer alteração no sistema, LEIA:

1. **`docs/REGRAS_ATIVAS.md`** — Regras permanentes que afetam decisoes futuras (~20 regras). LEIA SEMPRE antes de propor correcoes.
   - **`docs/INDICE_REGRAS.md`** — Indice rapido de todas as 104+ regras (uma linha cada).
   - **`docs/REGISTRO_CORRECOES.md`** — Historico completo de todos os fixes e correcoes. Consultar quando precisar de contexto.
2. **Este arquivo (CLAUDE.md)** — Especialmente as seções "Estado Atual do Pipeline" e "Proibições".

Se o arquivo REGRAS tiver uma entrada sobre o problema que você está investigando, leia-a inteira antes de propor qualquer correção.

## Estado Atual do Pipeline (Março 2026)

> **ATENÇÃO:** Esta seção reflete o estado real em produção. Atualizar sempre que uma REGRA nova for adicionada.

### Pipeline Ativo: V2 de 5 Camadas (REGRAS #028, ativado em #035)

```
FootyStats API + API-Football v3
    │
    ▼
build_records_from_matches (fixtures_service.py)
    ├─► calcular_lambda_jogo (lambda_calculator.py) — com deflation 0.85 ATIVO (#043) + γ home (#078)
    ├─► xg_filter BIDIRECIONAL (#035-M3)
    ├─► chaos_detector com SAFE blocker (#035-M2)
    ├─► Poisson matrix + Dixon-Coles τ(ρ) → todos mercados de gols (#028, #078)
    ├─► BTTS fusion: FootyStats 40% + Poisson 30% + team_avg 30% — com deflation 0.80 (#043)
    ├─► Corners Engine v2 bidirecional 4.5-12.5 (#033) — com redução 20% (#043)
    ├─► 1X2: implied_probs(odds) [+ ML ensemble quando ativo]
    │
    ▼
selecionar_mercados_v2 (market_service.py) ← ATIVO desde #035-M1
    ├─► ev_classification: 4 níveis (#028) — SAFE desabilitado via circuit breaker (#043)
    ├─► market_reference_signal: capping por qualidade (#031)
    ├─► bankroll_engine: Quarter Kelly com caps (#028)
    ├─► correlation_matrix: anti-redundância (#028)
    │
    ▼
API → Next.js 14 (Vercel) + Streamlit
```

### Alertas Críticos Ativos

| Alerta | REGRA | Status |
|--------|-------|--------|
| **SAFE reativado** per liga | #054 | 36/37 ligas com safe_enabled=true |
| **Lambda deflation per liga** | #052-#053 | Dixon-Coles + grid 0.80-1.50 |
| **BTTS deflation per liga** | #054-#056 | Calibrado contra seasonBTTSPercentage real |
| **Corners per liga** | #055-#056 | Brier-based + season stats |
| **Cards per liga** | #056 | Fix extração + season stats Poisson |
| **Thresholds per liga** | #055 | safe_prob calibrado por Brier quality |

### Parâmetros Calibráveis (PER-LEAGUE desde #052, calibrados automaticamente)

| Módulo | Parâmetro | Calibrado? | Arquivo |
|--------|-----------|-----------|---------|
| Lambda O/U | deflation | Per-league | league_calibrator.py |
| Lambda BTTS | deflation | Per-league | league_calibrator.py |
| Lambda 1X2 | deflation | Per-league | league_calibrator.py |
| Lambda weights | season/recent | Per-league | league_calibrator.py |
| Cards | deflation | Per-league (#056) | league_calibrator.py |
| Corners | deflation (Brier) | Per-league | league_calibrator.py |
| xG blend | weight | Per-league | league_calibrator.py |
| BTTS fusion | weights | Heuristic | league_calibrator.py |
| Thresholds | safe_prob x 6 mercados | Per-league | league_calibrator.py |
| Dixon-Coles ρ | rho | Per-league (#078) | league_calibrator.py |
| Home advantage γ | gamma | Per-league (#078) | league_calibrator.py |
| SAFE | enabled | Per-league | league_calibrator.py |

## CONTRATO DA MISTRAL AI (#082)

> **Princípio:** Mistral é EXCLUSIVAMENTE narrativa. Nunca calcula, nunca ajusta, nunca audita.

### O que a Mistral FAZ (narrativa):
- `summary` — resumo textual do jogo
- `key_points` — fatores qualitativos relevantes
- `recommendation` — sugestão narrativa (não vinculante)
- `confidence` — auto-avaliação de confiança (informativa)
- Corners review opcional (`mistral_review.py`)

### O que a Mistral NÃO FAZ (cálculo):
- Calcular ou modificar probabilidades (1X2, O/U, BTTS)
- Validar ou auditar cálculos do pipeline
- Gerar correções de parâmetros (lambda, thresholds, deflation)
- Auditar picks ou classificações (SAFE/NEUTRO)
- Ajustar lambdas, thresholds ou pesos de calibração

### Arquivo principal:
- `backend/services/mistral_analysis.py` (prompt v3.0, serviço `MistralAnalysisService`)

### Fallback:
- Se `MISTRAL_API_KEY` ausente ou Mistral indisponível: retorna análise default com `confidence=0`
- Ausência da Mistral **NÃO afeta** probabilidades, classificações ou pipeline de cálculo

## Proibições

1. **NÃO criar nomes de especificação fictícios** — Exemplo: "v5.5-ML" foi inventado por uma sessão anterior e propagado como se fosse real. Se não está no REGRAS, não existe.
2. **NÃO alterar thresholds sem dados de auditoria** — Os thresholds atuais (#042) vieram de uma auditoria de 27 jogos. Qualquer mudança exige backtesting documentado.
3. **NÃO reativar SAFE** sem 3 auditorias consecutivas com accuracy > 50% (#043).
4. **NÃO remover deflations de lambda** sem lambda error < 0.5 por 3 rodadas (#043).
5. **NÃO duplicar funções** — `main.py` tinha cópia de `selecionar_mercados_jogo` (deprecated em #035-M4). Verificar se a função já existe em services/ ou modeling/ antes de criar.
6. **NÃO alterar o prompt Mistral** sem manter as 4 camadas de defesa anti-alucinação (#001, #002).
7. **NÃO mergear PRs** sem registrar a alteração no `docs/REGISTRO_CORRECOES.md` (e `REGRAS_ATIVAS.md` se for regra permanente).
8. **NÃO assumir causa raiz** — Seguir as 7 regras de investigação obrigatória acima.

## Registro de Alterações

Toda alteração significativa DEVE ser registrada em `docs/REGISTRO_CORRECOES.md` seguindo o formato (e em `docs/REGRAS_ATIVAS.md` se for regra permanente):

```
## NNN — Título descritivo

**Data:** YYYY-MM-DD
**Arquivos afetados:** lista de arquivos
**Severidade:** Crítica / Alta / Média / Baixa
**Status:** Corrigido / Implementado

### Problema identificado
(descrição do problema)

### Causa raiz
(análise da causa)

### Correções aplicadas
(lista de correções com camadas)

### Lição aprendida
(o que aprendemos para não repetir)
```

Se a alteração não justifica uma entrada no REGRAS (ex: typo, formatação), não precisa de registro. Mas qualquer mudança em lógica de cálculo, thresholds, pesos, pipeline, prompt Mistral, ou infraestrutura DEVE ter entrada.

## Regra de Finalização Obrigatória (Pós-Alteração)

**TODA alteração no sistema DEVE seguir estes passos antes de ser considerada concluída:**

### 1. Sincronizar arquivos espelhados
```bash
# REGRAS — manter cópia idêntica nos dois diretórios
cp sportsbankzu-pro/docs/REGISTRO_CORRECOES.md docs/REGISTRO_CORRECOES.md
cp sportsbankzu-pro/docs/REGRAS_ATIVAS.md docs/REGRAS_ATIVAS.md
cp sportsbankzu-pro/docs/INDICE_REGRAS.md docs/INDICE_REGRAS.md

# CLAUDE.md — manter cópia idêntica nos dois diretórios
cp sportsbankzu-pro/CLAUDE.md CLAUDE.md
```

### 2. Commit no repositório local
```bash
cd sportsbankzu-pro
git add -A
git commit -m "feat/fix/refactor: descrição curta (#NNN)"
```

### 3. Push para GitHub
```bash
git push origin main
```

### 4. Deploy (se backend alterado)
```bash
python scripts/deploy_lambda.py
```

### 5. Validação pós-deploy
```bash
curl -s https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/health
```

**Atalho:** execute `bash scripts/finalize.sh` para rodar os passos 1-3 automaticamente.

**Quando NÃO executar:** alterações exclusivamente em documentação local (ex: notas pessoais) que não afetam o sistema.
