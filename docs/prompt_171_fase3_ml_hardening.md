# Prompt #171 FASE 3 — ML Retrain Hardening

> **Uso:** Copiar o conteúdo abaixo (a partir de "---") e colar no Claude Code como prompt.

---

## LEITURA OBRIGATÓRIA

Leia estes arquivos NA ÍNTEGRA antes de tocar em qualquer código:

1. `scripts/retrain_validate.py` — pipeline de retrain completo (≈370 linhas)
2. `backend/ml/train_model.py` — linhas 27-34 (thresholds), 64-112 (ECE), 160-191 (MktEff), 585-599 (OddsVal)
3. `backend/ml/predictor.py` — linhas 192-232 (`is_ml_available` gating)
4. `.github/workflows/ml-retrain-validate.yml` — workflow do GitHub Actions
5. `backend/config/leagues_config.py` — configuração de ligas
6. `CLAUDE.md` seções "Workflow de Validação" e "Proibições"

## ROLE

Atue como Agente Sênior de ML Ops. O sistema de ML contribuiu para uma perda de 50% da banca (#171) por gerar probabilidades overconfident (ECE 0.07-0.11) com OddsVal negativo em TODAS as 22 ligas. Isso significa que o modelo ML é PIOR que simplesmente usar odds implícitas. Não podemos permitir que modelos ruins entrem em produção novamente.

## CONTEXTO

### Resultados do Run #15 (último retrain)

| Liga | Brier | ECE | OddsVal | MktEff | Status |
|------|-------|-----|---------|--------|--------|
| serie-a (IT) | 0.5441 | 0.0703 | -0.0128 | **0.0000** | ML_ACTIVE |
| a-league (AU) | 0.5566 | 0.0831 | -0.0259 | **0.0000** | ML_ACTIVE |
| primera-division (AR) | 0.5687 | 0.1102 | -0.0412 | 0.0312 | ML_ACTIVE |
| (todas as 22 ligas) | — | 0.07-0.11 | **NEGATIVO** | — | ML_ACTIVE |

### Problemas críticos identificados:

1. **OddsVal NEGATIVO em TODAS as ligas** → modelo é pior que mercado em todas as ligas, mas permanece ML_ACTIVE
2. **MktEff = 0.0000 em Serie A e A-League** → R² = 0 significa que implied odds não foram normalizadas corretamente OU dados de odds faltam completamente (não que o mercado é ineficiente!)
3. **ECE 0.07-0.11 universalmente alto** → modelo overconfident; bins de alta confiança acertam menos do que proclamam
4. **A-League e primera-division com Brier > 0.55** → muito próximo do threshold de deactivation (0.63) mas continuam ML_ACTIVE, amplificando dano

### Root cause do #171 (já confirmado):

A combinação de ECE alto + OddsVal negativo + ausência de haircuts no Kelly causou overalocação sistemática. FASE 2 + 2.1 adicionaram haircuts no bankroll engine. FASE 3 ataca o problema na FONTE: impedir que modelos ruins sejam ativados.

## TAREFAS — IMPLEMENTAR NESTA ORDEM

### TASK 3A — Adicionar OddsVal gate em `is_ml_available()`

**Onde:** `backend/ml/predictor.py`, função `is_ml_available()` (linha 192)

**O quê:** Se OddsVal é negativo E significativo, ML não deveria ser ativo — o modelo adiciona ruído, não sinal.

**Como:**

Após o bloco existente de market_eff gating (linhas 222-230), adicionar:

```python
    # #171 FASE 3A: OddsVal gate — if model is WORSE than market odds,
    # prefer Poisson (which uses odds-implied as calibration signal).
    # Small negative OddsVal (-0.01) is noise; significant negative (-0.02+) is signal.
    ODDSVAL_DEACTIVATION_THRESHOLD = float(os.getenv("ODDSVAL_DEACTIVATION_THRESHOLD", "-0.015"))
    if odds_value is not None and odds_value < ODDSVAL_DEACTIVATION_THRESHOLD:
        logger.info(
            f"[{league_id}] ML suppressed: OddsVal={odds_value:.4f} < {ODDSVAL_DEACTIVATION_THRESHOLD} "
            f"(model worse than market)"
        )
        return False
```

**Efeito:** Com threshold -0.015, TODAS as 22 ligas do Run #15 teriam sido suprimidas (o melhor OddsVal era -0.0128). Isso é o comportamento CORRETO — se o modelo não bate o mercado, use Poisson + odds implícitas.

**Nota:** Adicionar `import os` no topo se não existir.

---

### TASK 3B — Adicionar ECE gate em `is_ml_available()`

**Onde:** `backend/ml/predictor.py`, função `is_ml_available()` (linha 192)

**O quê:** ECE > threshold indica overconfidence perigosa para Kelly.

**Como:**

Após o gate de OddsVal (3A):

```python
    # #171 FASE 3B: ECE gate — overconfident models inflate Kelly allocations.
    # ECE > 0.10 means model is consistently 10%+ overconfident.
    ECE_DEACTIVATION_THRESHOLD = float(os.getenv("ECE_DEACTIVATION_THRESHOLD", "0.10"))
    validation_ece = meta.get("validation_ece")
    if validation_ece is not None and validation_ece > ECE_DEACTIVATION_THRESHOLD:
        logger.info(
            f"[{league_id}] ML suppressed: ECE={validation_ece:.4f} > {ECE_DEACTIVATION_THRESHOLD} "
            f"(overconfident model)"
        )
        return False
```

**Efeito:** Com threshold 0.10, ligas como primera-division (ECE=0.1102) seriam suprimidas. Ligas com ECE 0.07-0.09 ainda passam MAS são penalizadas pelo ECE haircut no bankroll engine (FASE 2C).

---

### TASK 3C — Tratar MktEff=0 como dados corrompidos (não mercado ineficiente)

**Onde:** `backend/ml/train_model.py`, função `_compute_market_efficiency()` (linha 160)

**Problema:** Quando `market_efficiency_r2 = 0.0`, o gate de market_eff em `is_ml_available()` (linhas 222-230) NÃO suprime o ML — a condição é `market_eff > 0.15`. Isso é invertido: R²=0 pode significar:
- (a) Mercado é completamente ineficiente (raro, improvável em Serie A)
- (b) Dados de odds implícitas estão faltando/corrompidos (muito mais provável)

**Como:**

1. Na função `_compute_market_efficiency`, adicionar logging quando R²=0:
```python
    r_squared = 1.0 - (brier_market / brier_uniform)
    r_squared = round(max(0.0, r_squared), 4)
    
    # #171 FASE 3C: R²=0 in top leagues is almost certainly data corruption,
    # not market inefficiency. Log a warning for investigation.
    if r_squared == 0.0 and n_samples > 100:
        logger.warning(
            f"market_efficiency_r2=0.0 with {n_samples} samples — "
            f"likely missing/corrupted implied odds data. "
            f"brier_market={brier_market:.4f}, brier_uniform={brier_uniform:.4f}"
        )
    
    return r_squared
```

2. Em `is_ml_available()`, tratar R²=0 como dados suspeitos (NÃO como mercado ineficiente):
```python
    # #171 FASE 3C: R²=0 with substantial samples is data corruption, not inefficiency.
    # Suppress ML when we can't verify the market isn't already efficient.
    if market_eff is not None and market_eff == 0.0:
        n_samples = meta.get("n_samples", 0)
        if n_samples > 200:
            logger.info(
                f"[{league_id}] ML suppressed: MktEff=0.0 with n={n_samples} "
                f"(likely corrupted odds data — cannot verify market inefficiency)"
            )
            return False
```

**Efeito:** Serie A e A-League (ambas MktEff=0) seriam suprimidas ao invés de ativadas como ML_ACTIVE.

---

### TASK 3D — Adicionar quality gates no `retrain_validate.py`

**Onde:** `scripts/retrain_validate.py`, seção de classificação (linhas 148-177)

**O quê:** Adicionar alertas/warnings no output quando condições perigosas são detectadas.

**Como:**

Após a classificação (depois da linha 177), adicionar bloco de warnings:

```python
    # #171 FASE 3D: Quality warnings — conditions that amplified the P0 incident.
    warnings = []
    
    # W1: ALL leagues have negative OddsVal → model universally worse than market
    ov_values = [c.get("odds_value_added") for c in classifications 
                 if isinstance(c.get("odds_value_added"), float)]
    if ov_values and all(v < 0 for v in ov_values):
        warnings.append(
            f"CRITICAL: OddsVal negative in ALL {len(ov_values)} leagues — "
            f"ML model is universally worse than market implied odds"
        )
    
    # W2: Average ECE too high
    ece_values = [c["ece"] for c in classifications if c.get("ece") is not None]
    if ece_values:
        avg_ece = sum(ece_values) / len(ece_values)
        if avg_ece > 0.08:
            warnings.append(
                f"WARNING: Average ECE={avg_ece:.4f} across {len(ece_values)} leagues — "
                f"models are {avg_ece*100:.0f}% overconfident on average"
            )
    
    # W3: MktEff=0 in leagues with >200 samples (data corruption signal)
    for c in classifications:
        if (c.get("market_efficiency_r2") == 0.0 
            and isinstance(c.get("n_samples"), int) and c["n_samples"] > 200):
            warnings.append(
                f"DATA_ISSUE: {c['league_id']} has MktEff=0 with n={c['n_samples']} — "
                f"check implied odds extraction"
            )
    
    # W4: ML_ACTIVE league with ECE > 0.10 (overconfident and active = dangerous)
    for c in classifications:
        if (c["classification"] == "ML_ACTIVE" 
            and c.get("ece") is not None and c["ece"] > 0.10):
            warnings.append(
                f"RISKY: {c['league_id']} is ML_ACTIVE with ECE={c['ece']:.4f} — "
                f"consider deactivation"
            )
    
    # Print warnings
    if warnings:
        logger.warning("")
        logger.warning("=" * 70)
        logger.warning("QUALITY WARNINGS (requires human review before promote)")
        logger.warning("=" * 70)
        for w in warnings:
            logger.warning(f"  ⚠ {w}")
        logger.warning("")
```

Também incluir `warnings` no training_summary.json:
```python
    training_summary["quality_warnings"] = warnings
```

---

### TASK 3E — Adicionar warnings no workflow summary (GitHub Actions)

**Onde:** `.github/workflows/ml-retrain-validate.yml`, step "Generate workflow summary" (linha 145)

**O quê:** Mostrar quality warnings no GitHub Step Summary para revisão humana.

**Como:**

Após o bloco que imprime a tabela de ligas (linha ~195), adicionar:

```python
          # Print quality warnings if any
          warnings = data.get('quality_warnings', [])
          if warnings:
              print()
              print('### ⚠️ Quality Warnings')
              print()
              for w in warnings:
                  print(f'- {w}')
              print()
              print('> **These warnings require human review before running ml-retrain-promote.**')
```

---

### TASK 3F — Opcional: Prune ligas problemáticas do retrain

**AVALIAR mas NÃO implementar automaticamente.** Algumas ligas consistentemente produzem modelos ruins:

- **a-league** (Australia): Poucos times, poucos jogos por temporada, odds de bookmakers de nicho
- **primera-division** (Argentina): Alta volatilidade tática (3 formatos diferentes por ano — Apertura, Clausura, Copa)

**Opção 1 — Excluir do retrain:** Adicionar `ML_EXCLUDE_LEAGUES` env var e skip no loop
**Opção 2 — Threshold mais alto para ativação:** Exigir Brier < 0.50 (em vez de 0.60) para ligas voláteis
**Opção 3 — Leave as-is:** Os gates 3A+3B+3C já impedem ativação se métricas forem ruins

**Recomendação:** Opção 3 (leave as-is). Os gates inteligentes são melhor que prune hard-coded. Se uma liga melhorar no futuro, ela é automaticamente ativada.

Apenas documentar no training_summary.json quais ligas foram suprimidas e por qual gate, para visibilidade.

---

### TASK 3G — Registrar quais gates suprimiram cada liga

**Onde:** `backend/ml/predictor.py`, função `is_ml_available()`

**O quê:** Retornar não apenas True/False, mas QUAL gate suprimiu (para debugging e retrain reports).

**Como:**

Criar variante `get_ml_activation_status(league_id)` que retorna dict:

```python
def get_ml_activation_status(league_id: str) -> Dict[str, Any]:
    """Return detailed ML activation status with gate reasons.
    
    Returns:
        {
            "active": bool,
            "suppressed_by": str or None,  # e.g. "oddsval_gate", "ece_gate", "mkteff_zero"
            "metrics": { "brier": ..., "ece": ..., "odds_value": ..., "market_eff": ... }
        }
    """
    result = {"active": True, "suppressed_by": None, "metrics": {}}
    
    if np is None:
        result["active"] = False
        result["suppressed_by"] = "numpy_unavailable"
        return result
    
    bundle = _load_models(league_id)
    if not bundle:
        result["active"] = False
        result["suppressed_by"] = "no_model"
        return result
    
    meta = bundle.get("metadata", {})
    
    result["metrics"] = {
        "brier": meta.get("validation_brier"),
        "ece": meta.get("validation_ece"),
        "odds_value": meta.get("odds_value_added"),
        "market_eff": meta.get("market_efficiency_r2"),
        "n_samples": meta.get("n_samples"),
    }
    
    if meta.get("ml_deactivated"):
        result["active"] = False
        result["suppressed_by"] = "explicit_deactivation"
        return result
    
    val_brier = meta.get("validation_brier")
    if val_brier is not None and val_brier >= 0.60:
        result["active"] = False
        result["suppressed_by"] = "brier_threshold"
        return result
    
    # OddsVal gate (#171 FASE 3A)
    odds_value = meta.get("odds_value_added")
    ODDSVAL_DEACTIVATION_THRESHOLD = float(os.getenv("ODDSVAL_DEACTIVATION_THRESHOLD", "-0.015"))
    if odds_value is not None and odds_value < ODDSVAL_DEACTIVATION_THRESHOLD:
        result["active"] = False
        result["suppressed_by"] = "oddsval_gate"
        return result
    
    # ECE gate (#171 FASE 3B)
    ECE_DEACTIVATION_THRESHOLD = float(os.getenv("ECE_DEACTIVATION_THRESHOLD", "0.10"))
    validation_ece = meta.get("validation_ece")
    if validation_ece is not None and validation_ece > ECE_DEACTIVATION_THRESHOLD:
        result["active"] = False
        result["suppressed_by"] = "ece_gate"
        return result
    
    # MktEff=0 gate (#171 FASE 3C)
    market_eff = meta.get("market_efficiency_r2")
    if market_eff is not None and market_eff == 0.0:
        n_samples = meta.get("n_samples", 0)
        if n_samples > 200:
            result["active"] = False
            result["suppressed_by"] = "mkteff_zero"
            return result
    
    # Original market_eff + odds_value combined gate
    if market_eff is not None and market_eff > 0.15:
        if odds_value is not None and abs(odds_value) < 0.01:
            result["active"] = False
            result["suppressed_by"] = "market_efficient_no_value"
            return result
    
    return result
```

**IMPORTANTE:** NÃO alterar `is_ml_available()` para chamar `get_ml_activation_status()` — manter as duas funções separadas para performance (o hot path `is_ml_available()` deve ser rápido, sem construir dicts). Mas copiar a lógica dos novos gates (3A, 3B, 3C) para `is_ml_available()` também.

---

## PRE-MORTEM

1. **Gate 3A (OddsVal < -0.015) suprime TODAS as 22 ligas do Run #15.** Isso é intencional — o Run #15 mostrou que nenhum modelo ML bate o mercado. Os matches continuarão usando Poisson (que é calibrado por per-league deflation e funciona). Quando um futuro retrain produzir modelos com OddsVal >= 0, eles serão automaticamente ativados.

2. **Gate 3B (ECE > 0.10) é redundante com 3A neste run** (todas as ligas já falham em 3A). Mas se um modelo futuro tiver OddsVal=+0.01 mas ECE=0.12, o gate 3B protege contra overconfidence mesmo com edge positivo.

3. **Gate 3C (MktEff=0) pode ter falsos positivos** se uma liga muito pequena genuinamente tem R²=0 por acaso. O guard `n_samples > 200` protege contra isso.

4. **Performance:** Adicionar 3 comparações de float em `is_ml_available()` é O(1) — negligível.

5. **Backwards compatibility:** `is_ml_available()` continua retornando bool. `get_ml_activation_status()` é apenas para debugging/reports.

## VALIDAÇÃO PÓS-IMPLEMENTAÇÃO

```bash
# 1. Syntax check
python -m py_compile backend/ml/predictor.py
python -m py_compile backend/ml/train_model.py
python -m py_compile scripts/retrain_validate.py

# 2. Verify gates exist
grep -n "ODDSVAL_DEACTIVATION\|ECE_DEACTIVATION\|mkteff_zero\|oddsval_gate\|ece_gate" backend/ml/predictor.py

# 3. Verify quality warnings
grep -n "quality_warnings\|QUALITY WARNINGS" scripts/retrain_validate.py

# 4. Verify workflow summary includes warnings
grep -n "quality_warnings\|Quality Warnings" .github/workflows/ml-retrain-validate.yml

# 5. Verify get_ml_activation_status exists
grep -n "def get_ml_activation_status" backend/ml/predictor.py

# 6. Line counts (sanity — predictable growth)
wc -l backend/ml/predictor.py scripts/retrain_validate.py backend/ml/train_model.py

# 7. Import check
python -c "from backend.ml.predictor import is_ml_available, get_ml_activation_status, get_ml_metadata; print('OK')"
```

## PROIBIÇÕES

- NÃO alterar thresholds de Brier (0.60 para ML_ACTIVE, 0.63 para deactivation) — foram calibrados em auditoria anterior
- NÃO remover ligas do config (`leagues_config.py`) — usar gates inteligentes, não prune hard-coded
- NÃO alterar o workflow `ml-retrain-promote.yml` — apenas o validate
- NÃO tocar em `bankroll_engine.py` — FASE 2/2.1 já trataram esse arquivo
- NÃO fazer deploy automático
- NÃO usar `--no-gpg-sign` no commit (se GPG falhar, commitar sem essa flag)
- Edits pontuais APENAS
