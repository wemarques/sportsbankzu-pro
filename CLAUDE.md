# CLAUDE.md — SportsBankZU Pro

**Stack:** Next.js 14 (Vercel) + FastAPI/Python (AWS Lambda) + PostgreSQL (RDS). Streamlit foi descontinuado — ignorar referências antigas em código/docs.

## Leitura obrigatória antes de qualquer alteração

Ler nesta ordem: `docs/BACKLOG.md` (P0/P1) → `docs/REGRAS_ATIVAS.md` → `docs/INDICE_REGRAS.md`. Consultar `docs/REGISTRO_CORRECOES.md` quando precisar do histórico de um fix `#N`.

## Comandos

```bash
# Backend local
uvicorn backend.main:app --reload --port 5001

# Frontend
cd frontend/next && npm run dev

# Tests
pytest -q
cd frontend/next && npm run test:e2e
```

## Diretórios

- `backend/routes/` — endpoints (fixtures, leagues, decision, quadro, ai, health)
- `backend/services/` — lógica de negócio (math, market, fixtures, decision, **mistral_analysis.py**, ev_classification, correlation_matrix)
- `backend/modeling/` — modelos estatísticos (lambda, xg_filter, chaos_detector, calibrator, market_validator, league_calibrator)
- `frontend/next/src/` — App Router; `frontend/next/e2e/` — Playwright
- `cli/`, `scripts/`

## API Lambda — armadilhas conhecidas

Base: `https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/`

| Rota correta | Errado |
|---|---|
| `/health` | `/api/health` (404) |
| `/api/fixtures/...` | |
| `/api/backtesting/...` | |
| `POST /api/backtesting/calibrate?league=X` | `?league_id=X` |
| `/api/backtesting/calibration-status` | |
| `/api/health/safe-status` | |

API Gateway tem hard limit de **30s**. Calibração leva 15–40s; **503 não significa falha** — Lambda continua processando e persiste o resultado.

## Deploy Lambda

```bash
# Pré-check OBRIGATÓRIO antes de update-function-code
MSYS_NO_PATHCONV=1 aws lambda get-function-configuration \
  --function-name sportsbank-pro-backend --region us-east-1 \
  --query '{State: State, LastUpdateStatus: LastUpdateStatus}'
# Só prosseguir se State=Active e LastUpdateStatus=Successful

MSYS_NO_PATHCONV=1 aws lambda update-function-code \
  --function-name sportsbank-pro-backend \
  --s3-bucket meu-bucket-sportsbank \
  --s3-key deploy/sportsbank_lambda.zip --region us-east-1
```

## Lambda Layer (scipy) — `arn:aws:lambda:us-east-1:838823110426:layer:scipy-numpy-layer:2`

- Layer contém **apenas scipy** (numpy está no ZIP de deploy). Usada por NB2 (cards e corners).
- Sem Layer compatível, **NB2 cai silenciosamente para Poisson** (sem erro visível).
- Mudança de runtime Python (ex.: 3.11 → 3.12) **exige recriar a Layer** — extensões C não são portáveis entre versões.

```bash
pip install scipy -t layer/python/ --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.XX --no-deps
cd layer && zip -r ../scipy-layer.zip python/ -x '*.pyc' '*__pycache__*' '*.dist-info/*' '*/tests/*'
aws lambda publish-layer-version --layer-name scipy-numpy-layer \
  --content S3Bucket=meu-bucket-sportsbank,S3Key=deploy/scipy-layer.zip \
  --compatible-runtimes python3.XX --region us-east-1
aws lambda update-function-configuration --function-name sportsbank-pro-backend \
  --layers <LAYER_ARN> --region us-east-1
```

## Variáveis de ambiente

`MISTRAL_API_KEY`, `PY_BACKEND_URL`, `FUTEBOL_ROOT` / `DATA_ROOT`, `S3_BUCKET` (opcional).

## Pipeline ativo (V2 — REGRAS #028, ativado em #035)

```
FootyStats + API-Football v3
  → build_records_from_matches (fixtures_service.py)
  → calcular_lambda_jogo (deflation 0.85 #043 + γ home #078)
  → xg_filter bidirecional (#035-M3)
  → chaos_detector + SAFE blocker (#035-M2)
  → O/U gols: Poisson(lambdaTotalOU) — stats = insumo raw dos picks (#187)
       + Dixon-Coles τ(ρ) no matrix interno (#028, #078)
  → BTTS: Poisson dos lambdas exibidos (#187) — fusão 40/30/30 (#043)
       preservada em bttsFusionProb (não alimenta mais os picks)
  → Corners Engine v2 (4.5–12.5) com redução 20% (#043)
  → 1X2: implied_probs(odds) [+ ML ensemble] — espelho de mercado ROTULADO
       na UI (#187, decisão opção b; #064)
  → selecionar_mercados_v2 (market_service.py — ativo desde #035-M1)
       ev_classification 4 níveis (#028) — SAFE via circuit breaker (#043)
       linhas altas (cards >2.5, corners >10.5) só com odd real (#187)
       market_reference_signal capping por qualidade (#031, fontes #187)
       bankroll_engine Quarter Kelly com caps (#028)
       correlation_matrix anti-redundância (#028)
  → odds enrichment API-Football (#120; famílias de bet único #187)
       → reclassificação pós-enrichment (#187)
  → Next.js (Vercel)
```

**Calibração per-league automática** (`league_calibrator.py`): deflation (O/U, BTTS, 1X2, cards #056, corners), lambda weights season/recent, xG blend, BTTS fusion, thresholds safe_prob de 6 mercados, Dixon-Coles ρ (#078), home advantage γ (#078), SAFE enabled per liga (#054 — 36/37 ligas com `safe_enabled=true`).

## Contrato Mistral (#082, reforçado #181)

**Mistral é EXCLUSIVAMENTE narrativa.** Arquivo: `backend/services/mistral_analysis.py` (prompt v3.0, `MistralAnalysisService`, **temperature 0.15**).

- **Faz:** `summary`, `key_points`, `recommendation`, `confidence` (informativo), corners review opcional.
- **NÃO faz:** calcular/modificar probabilidades, auditar pipeline, ajustar lambdas/thresholds/pesos, classificar picks (SAFE/NEUTRO), **citar probabilidades raw (pré-deflação) em narrativa (#181)**, **computar EV no texto (#181)**.
- Sem `MISTRAL_API_KEY` ou Mistral indisponível → retorna default com `confidence=0`. **Não afeta** cálculos.
- Não alterar o prompt sem preservar as 4 camadas anti-alucinação (#001, #002).
- **Probs no prompt em duas camadas (#181):** "Estatísticas Poisson" carrega RAW (uso interno do modelo), "PICKS DO PIPELINE" carrega DEFLATED (única fonte legítima para narrativa). Mistral é instruído via prompt rules a só citar deflated. Validação `backend/ai/mistral_contract.py::validate_output` inspeciona resumo + key_points + recomendação (full text) e loga violações via `sportsbankzu.mistral.contract`. Camada 6 (`_validate_recommendation_vs_pipeline` em `mistral_analysis.py`) só inspeciona `recomendacao_principal` e direção Over/Under — limitação documentada na docstring da função.

## Domínio

- Mercados: 1X2, O/U 0.5–4.5, BTTS, Double Chance, Corners 4.5–12.5, Cards O/U 2.5–5.5
- Classificação (#028): SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET
- Regimes: NORMAL, HIPER-OFENSIVA
- 22+ ligas europeias e sul-americanas + Copa do Brasil
- UI em pt-BR; código e comentários em inglês

## Checklist novo mercado (#006) — 7 pontos obrigatórios

1. Engine — `backend/modeling/`
2. `backend/services/ev_classification.py`
3. `backend/modeling/market_validator.py`
4. `backend/services/market_service.py` (dedup)
5. `backend/services/correlation_matrix.py`
6. `frontend/next/src/lib/localAudit.ts` (evaluatePick)
7. `backend/routes/ai_analysis.py` (evaluatePick backend)

## Proibições (regras travadas — NÃO violar sem entrada em REGRAS_ATIVAS)

1. **Não inventar nomes de spec.** Se não está em `REGRAS_ATIVAS.md`, não existe (ex.: "v5.5-ML" foi alucinação propagada).
2. **Não alterar thresholds sem auditoria.** Os atuais (#042) vieram de auditoria de 27 jogos.
3. **Não reativar SAFE** sem 3 auditorias consecutivas com accuracy > 50% (#043).
4. **Não remover deflations** sem lambda error < 0.5 por 3 rodadas (#043).
5. **Não duplicar funções** — verificar `services/` e `modeling/` antes de criar (caso #035-M4: cópia em `main.py`).
6. **Não mergear PR** sem entrada em `docs/REGISTRO_CORRECOES.md` (e `REGRAS_ATIVAS.md` se permanente).
7. **Threshold change > 15% BLOQUEADO** sem dados.
8. **MIN_N_BRIER = 20** (#079) — auditorias com N<20 são apenas diagnósticas, nunca decisórias.
9. **Complementares > 105% BLOQUEADOS** (#098).
10. **Deflação progressiva contínua por nós (#105, contínua desde #189-a)** — NÃO reverter para uniforme nem para degrau por banda.
11. **Classificação usa prob raw; EV usa prob deflacionada** (#106).
12. **Encolhimento de amostra pequena nos DOIS lados do λ (#208)** — ataque e defesa adversária recebem o mesmo peso `n/8`; contagem ausente não encolhe, amostra 0 encolhe.
13. **Auditor de premissas reimplementa a matemática de referência (#209)** — NÃO deduplicar contra o pipeline; a duplicação é o mecanismo. Campo novo da FootyStats entra no manifesto (#210).

## Finalização obrigatória pós-alteração

`CLAUDE.md` e os 3 arquivos de REGRAS existem em **dois diretórios espelhados** — sincronizar antes do commit.

```bash
# 1. Espelhar
cp sportsbankzu-pro/docs/REGISTRO_CORRECOES.md docs/REGISTRO_CORRECOES.md
cp sportsbankzu-pro/docs/REGRAS_ATIVAS.md      docs/REGRAS_ATIVAS.md
cp sportsbankzu-pro/docs/INDICE_REGRAS.md      docs/INDICE_REGRAS.md
cp sportsbankzu-pro/CLAUDE.md                  CLAUDE.md

# 2-3. Commit + push
cd sportsbankzu-pro && git add -A \
  && git commit -m "feat/fix/refactor: descrição curta (#NNN)" \
  && git push origin main

# 4. Deploy (se backend alterado)
python scripts/deploy_lambda.py

# 5. Validar
curl -s https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/health
```

Atalho: `bash scripts/finalize.sh` roda 1–3 automaticamente. Pular apenas para alterações exclusivas de doc local.

## Formato de entrada em REGISTRO_CORRECOES.md

```
## NNN — Título descritivo
**Data:** YYYY-MM-DD | **Arquivos:** ... | **Severidade:** Crítica/Alta/Média/Baixa | **Status:** Corrigido/Implementado

### Problema identificado · Causa raiz · Correções aplicadas (com camadas) · Lição aprendida
```

**Exigem entrada:** lógica de cálculo, thresholds, pesos, pipeline, prompt Mistral, infraestrutura. Typos/formatação não.
