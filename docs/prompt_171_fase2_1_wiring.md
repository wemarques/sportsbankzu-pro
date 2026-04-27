# Prompt #171 FASE 2.1 — Wiring: conectar haircuts e caps ao pipeline

> **Uso:** Copiar o conteúdo abaixo (a partir de "---") e colar no Claude Code como prompt.

---

## LEITURA OBRIGATÓRIA

Leia estes arquivos NA ÍNTEGRA antes de tocar em qualquer código:

1. `backend/services/bankroll_engine.py` — contém as funções `ece_haircut_factor`, `oddsval_haircut_factor`, `apply_family_cap`, `check_daily_loss_breaker` (todas criadas em FASE 2 mas **sem callers**)
2. `backend/routes/market_analysis.py` — ÚNICO lugar onde `compute_stake` é chamado (linhas 63 e 112)
3. `backend/models/market_output.py` — `to_legacy_mercado()` (linha 104) gera o dict passado ao `compute_stake`
4. `backend/ml/predictor.py` — metadata do modelo contém `validation_ece` (linha 448) e `odds_value_added` (linha 456)
5. `backend/services/league_calibrator.py` — `calibrate_league()` retorna brier scores mas **não ECE/OddsVal** (estes vêm do ML retrain)

## ROLE

Atue como Agente Sênior que VAI PERDER DINHEIRO se os haircuts não estiverem efetivamente conectados. Código morto = proteção zero = outra catástrofe de 50%.

## CONTEXTO

A FASE 2 implementou 4 funções de proteção em `bankroll_engine.py`, mas **nenhuma está wired**:

| Função | Problema | Solução |
|--------|----------|---------|
| `ece_haircut_factor()` | `market_output.get("league_ece")` sempre retorna None | Injetar ECE no dict antes de chamar `compute_stake` |
| `oddsval_haircut_factor()` | `market_output.get("league_odds_val")` sempre retorna None | Injetar OddsVal no dict antes de chamar `compute_stake` |
| `apply_family_cap()` | Nenhum caller | Chamar após coletar todos os stakes do batch |
| `check_daily_loss_breaker()` | Nenhum caller | Integrar no endpoint de batch para bloquear stakes |

## TAREFAS — IMPLEMENTAR NESTA ORDEM

### TASK W1 — Propagar `league_ece` e `league_odds_val` para o market_output dict

**Onde:** `backend/routes/market_analysis.py`

**Contexto:**
- ECE e OddsVal vêm do ML model metadata: `bundle["metadata"]["validation_ece"]` e `bundle["metadata"]["odds_value_added"]`
- São acessíveis via `backend/ml/predictor.py` → `_load_models(league_id)` → `.get("metadata", {})`
- Precisamos injetar esses valores no dict `m` (output de `to_legacy_mercado()`) ANTES de passar para `compute_stake`

**Como:**

1. Na função `analyze_match` (linha 36) e `analyze_batch` (linha 76), após obter `league_id`, carregar os metadados ML:

```python
# #171 FASE 2.1: Load ML metadata for ECE/OddsVal haircuts
league_ece = None
league_odds_val = None
try:
    from backend.ml.predictor import _load_models
    ml_bundle = _load_models(req.league_id)
    if ml_bundle:
        ml_meta = ml_bundle.get("metadata", {})
        league_ece = ml_meta.get("validation_ece")
        league_odds_val = ml_meta.get("odds_value_added")
except Exception:
    pass  # ML unavailable — haircuts will be no-ops (return 1.0)
```

2. No loop de markets, ANTES de chamar `compute_stake(m, req.bankroll)`, injetar:

```python
# Inject league-level quality metrics for haircut computation (#171)
m["league_ece"] = league_ece
m["league_odds_val"] = league_odds_val
m["market_type"] = market.market_type  # needed for family cap
```

**IMPORTANTE:** `market.market_type` está disponível no `MarketOutput` (campo definido na linha 48 de `market_output.py`). Precisamos passá-lo no dict porque `to_legacy_mercado()` não o inclui.

**Verificação:**
```bash
grep -n "league_ece\|league_odds_val\|market_type" backend/routes/market_analysis.py
# Deve mostrar as injeções nas duas funções (analyze_match + analyze_batch)
```

---

### TASK W2 — Integrar `apply_family_cap` no batch endpoint

**Onde:** `backend/routes/market_analysis.py`, função `analyze_batch` (linha 76)

**Contexto:**
- `apply_family_cap` precisa de uma lista de dicts com `stake` e `market_type`
- No batch endpoint, os stakes são calculados por match. Precisamos coletar TODOS, aplicar family cap, e devolver

**Como:**

Após o loop principal de matches (depois da linha 123), antes de retornar:

```python
# #171 FASE 2.1: Apply family exposure cap across all matches
if req.bankroll and req.bankroll > 0:
    from backend.services.bankroll_engine import apply_family_cap, apply_daily_cap
    
    # Collect all stakes from all matches
    all_market_stakes = []
    for match_result in results:
        for m in match_result["markets"]:
            if m.get("stake", 0) > 0:
                all_market_stakes.append(m)
    
    # Apply family cap THEN daily cap (order matters)
    if all_market_stakes:
        apply_family_cap(all_market_stakes, req.bankroll)
        apply_daily_cap(all_market_stakes, req.bankroll)
```

**NOTA:** `apply_daily_cap` já existia mas também nunca tinha caller. Agora ambos ficam wired.

**Verificação:**
```bash
grep -n "apply_family_cap\|apply_daily_cap" backend/routes/market_analysis.py
```

---

### TASK W3 — Integrar `check_daily_loss_breaker` no batch endpoint

**Onde:** `backend/routes/market_analysis.py`, função `analyze_batch`

**Contexto:**
- O circuit breaker precisa de `daily_pnl` (P&L do dia) e `bankroll` (banca inicial do dia)
- Essa info não vem no request atual. Temos duas opções:
  - **(A) Request enrichment:** Adicionar campo opcional `daily_pnl` no `BatchAnalysisRequest`
  - **(B) Server-side lookup:** Consultar o DB de picks para calcular P&L do dia

**Implementar opção A** (mais simples, frontend pode calcular P&L):

1. Adicionar ao `BatchAnalysisRequest`:
```python
daily_pnl: Optional[float] = None  # #171: today's P&L for circuit breaker
```

2. No início de `analyze_batch`, após validações:
```python
# #171 FASE 2.1: Daily loss circuit breaker
if req.bankroll and req.daily_pnl is not None:
    from backend.services.bankroll_engine import check_daily_loss_breaker
    if check_daily_loss_breaker(req.daily_pnl, req.bankroll):
        return {
            "success": True,
            "matches": [],
            "total_matches": 0,
            "multiples": [],
            "total_eligible_picks": 0,
            "_circuit_breaker": True,
            "_message": "Daily loss circuit breaker ativado. Novas apostas bloqueadas até amanhã.",
            "_daily_loss_pct": round(abs(req.daily_pnl) / req.bankroll * 100, 1),
        }
```

**Verificação:**
```bash
grep -n "circuit_breaker\|daily_pnl" backend/routes/market_analysis.py
```

---

### TASK W4 — Também injetar no single-match endpoint

**Onde:** `backend/routes/market_analysis.py`, função `analyze_match` (linha 36)

O single endpoint não tem batch, mas deve aplicar:
- ECE/OddsVal haircuts ✓ (handled in W1)
- Family cap: N/A (single match)
- Daily loss breaker: aplicar da mesma forma

1. Adicionar `daily_pnl: Optional[float] = None` ao `MarketAnalysisRequest`
2. Verificar breaker antes de processar:
```python
if req.bankroll and req.daily_pnl is not None:
    from backend.services.bankroll_engine import check_daily_loss_breaker
    if check_daily_loss_breaker(req.daily_pnl, req.bankroll):
        return {
            "success": True,
            "result": {"markets": [], "_circuit_breaker": True,
                       "_message": "Daily loss circuit breaker ativado."},
        }
```

---

### TASK W5 — Expor `_load_models` como função pública (ou criar helper)

**Onde:** `backend/ml/predictor.py`

**Problema:** `_load_models` é função privada (prefixo `_`). Importá-la diretamente de `market_analysis.py` funciona tecnicamente mas viola convenção.

**Opção 1 (simples):** Criar helper público:
```python
def get_ml_metadata(league_id: str) -> Dict[str, Any]:
    """Return ML model metadata for a league, or empty dict if unavailable."""
    bundle = _load_models(league_id)
    if not bundle:
        return {}
    return bundle.get("metadata", {})
```

**Opção 2 (mínimo):** Renomear para `load_models` (sem underscore). Avaliar impacto — se usado em outros lugares com `_`, manter backward alias.

**Recomendação:** Opção 1 — adicionar `get_ml_metadata()` e usar em W1:
```python
from backend.ml.predictor import get_ml_metadata
ml_meta = get_ml_metadata(req.league_id)
league_ece = ml_meta.get("validation_ece")
league_odds_val = ml_meta.get("odds_value_added")
```

---

## PRE-MORTEM

1. **Se o ML não estiver treinado para uma liga**, `_load_models` retorna None → `league_ece=None` → haircut retorna 1.0 (neutro). Correto — ligas sem ML não são penalizadas.
2. **Se `_load_models` falhar com exceção**, o try/except no W1 captura e segue com haircuts neutros. Correto.
3. **Family cap + daily cap em sequência**: family cap reduz stakes individuais, daily cap olha o total. Não há dupla penalização — family cap é *intra-família* e daily cap é *cross-família*. Sequência correta.
4. **Performance:** `_load_models` usa cache em memória (`_model_cache`), então chamada repetida no batch é O(1) após primeiro load.
5. **Backward compatibility:** Campos `daily_pnl` são Optional com default None, então requests existentes sem o campo continuam funcionando normalmente.

## VALIDAÇÃO PÓS-IMPLEMENTAÇÃO

```bash
# 1. Syntax check
python -m py_compile backend/routes/market_analysis.py
python -m py_compile backend/ml/predictor.py

# 2. Verify wiring
grep -n "league_ece\|league_odds_val\|apply_family_cap\|circuit_breaker\|get_ml_metadata" backend/routes/market_analysis.py

# 3. Verify helper exists
grep -n "def get_ml_metadata" backend/ml/predictor.py

# 4. Verify market_type propagation
grep -n "market_type" backend/routes/market_analysis.py

# 5. Quick import test
python -c "from backend.routes.market_analysis import router; print('OK')"

# 6. Diff size check (should be ~50-70 lines added across 2 files)
git diff --stat backend/routes/market_analysis.py backend/ml/predictor.py
```

## PROIBIÇÕES

- NÃO alterar `bankroll_engine.py` — as funções já estão corretas, só faltam callers
- NÃO alterar `to_legacy_mercado()` — injetar campos no dict DEPOIS da chamada, não dentro do modelo
- NÃO criar novos endpoints — apenas modificar os existentes
- NÃO remover ou modificar a lógica existente de `evaluate_match_markets` ou `compute_stake`
- NÃO fazer deploy — apenas implementar e commitar
- Edits pontuais APENAS — não reescrever funções inteiras
