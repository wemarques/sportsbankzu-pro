# Prompt #171 FASE 2 — Hardening Bankroll Engine + Circuit Breaker

> **Uso:** Copiar o conteúdo abaixo (a partir de "---") e colar no Claude Code como prompt.

---

## LEITURA OBRIGATÓRIA

Leia estes arquivos NA ÍNTEGRA antes de tocar em qualquer código:

1. `backend/services/bankroll_engine.py` — TODO o arquivo (375 linhas). Este é o arquivo principal de alteração.
2. `docs/REGRAS_ATIVAS.md` — regras permanentes do sistema
3. `CLAUDE.md` seções "Workflow de Validação" e "Proibições"

## ROLE

Atue como Agente Sênior de Engenharia de Dados que VAI PERDER DINHEIRO PESSOAL se a implementação estiver errada. Cada linha de código afeta dinheiro real.

## CONTEXTO CONFIRMADO DO INCIDENTE #171

A banca do SportsBankZU caiu 50% em 24h. A investigação forense de 48h confirmou:

- **Causa raiz primária:** #170-A reduziu NB2 α de 0.15 para 0.005-0.03, estreitando a variância das probabilidades de corners. Resultado: picks/dia de corners subiram 2.89× e stake/dia subiu 5.93× (1.20% → 7.11%).
- **Amplificador:** ECE de 0.07-0.11 nas ligas ML_ACTIVE infla probabilidades → Kelly aloca mais do que deveria.
- **Agravante:** VIÁVEL floor forçava stakes quando Kelly retornava 0.

### Emergências já deployadas (FASE 0):
- `AUTO_APPLY_CONFIDENCE_MIN=101` (bloqueia auto-apply de correções)
- `VIAVEL_FLOOR_PCT=0` (desabilita floor forçado)
- `CORNERS_ALPHA_CALIBRATED=false` (reverte α para 0.15 default)
- `lambda_deflation` adicionado ao `ADJUSTMENT_LIMITS` em `audit.py`

## TAREFAS FASE 2 — IMPLEMENTAR NESTA ORDEM

### TASK 2C — ECE Haircut no bankroll_engine.py

**O quê:** Quando a liga tem ECE > threshold, aplicar haircut no Kelly para compensar a overconfidence.

**Onde:** `backend/services/bankroll_engine.py`

**Como:**

1. Adicionar constantes no topo do arquivo (seção Haircut factors):
```python
# ─── ECE Haircut (#171 FASE 2C) ───
# When league ECE exceeds threshold, reduce Kelly stake proportionally.
# ECE = 0.08 means model is 8% overconfident → haircut reduces stake.
ECE_HAIRCUT_THRESHOLD = float(os.getenv("ECE_HAIRCUT_THRESHOLD", "0.06"))
ECE_HAIRCUT_MAX = float(os.getenv("ECE_HAIRCUT_MAX", "0.25"))         # max 25% reduction
ECE_HAIRCUT_CEILING = float(os.getenv("ECE_HAIRCUT_CEILING", "0.12"))  # ECE above this caps at max haircut
```

2. Adicionar função:
```python
def ece_haircut_factor(ece: Optional[float]) -> float:
    """Calculate ECE-based haircut multiplier (0.75-1.0).
    
    ECE < threshold → 1.0 (no haircut)
    ECE between threshold and ceiling → linear interpolation
    ECE > ceiling → 1.0 - ECE_HAIRCUT_MAX
    """
    if ece is None or ece <= ECE_HAIRCUT_THRESHOLD:
        return 1.0
    if ece >= ECE_HAIRCUT_CEILING:
        return 1.0 - ECE_HAIRCUT_MAX
    # Linear interpolation
    ratio = (ece - ECE_HAIRCUT_THRESHOLD) / (ECE_HAIRCUT_CEILING - ECE_HAIRCUT_THRESHOLD)
    return 1.0 - (ratio * ECE_HAIRCUT_MAX)
```

3. Na função `compute_stake()`, ANTES de aplicar o haircut existente (`calculate_haircut`), ler `ece` do `market_output` e multiplicar:
```python
    # ECE haircut (#171 FASE 2C)
    ece = market_output.get("league_ece")
    ece_factor = ece_haircut_factor(ece)
```
E depois multiplicar: `adjusted *= ece_factor` (tanto no branch VIÁVEL quanto no branch normal).

4. Incluir `ece_factor` no dict de retorno para rastreabilidade.

**IMPORTANTE:** O campo `league_ece` precisa ser passado via `market_output`. Verificar se `fixtures_service.py` ou `market_service.py` já propaga ECE da liga. Se não, adicionar propagação do calibration data para o market_output. Grep por "ece" nos services para entender o fluxo atual.

---

### TASK 2B — OddsVal Haircut no bankroll_engine.py

**O quê:** Quando o modelo é MENOS calibrado que o mercado (OddsVal negativo), reduzir stakes.

**Onde:** `backend/services/bankroll_engine.py`

**Como:**

1. Adicionar constantes:
```python
# ─── OddsVal Haircut (#171 FASE 2B) ───
# OddsVal < 0 means model is worse than market implied odds.
# Haircut scales linearly: at FLOOR, haircut reaches MAX.
ODDSVAL_HAIRCUT_FLOOR = float(os.getenv("ODDSVAL_HAIRCUT_FLOOR", "-0.02"))
HAIRCUT_NEGATIVE_ODDSVAL_MAX = float(os.getenv("HAIRCUT_NEGATIVE_ODDSVAL_MAX", "0.30"))
```

2. Adicionar função:
```python
def oddsval_haircut_factor(odds_val: Optional[float]) -> float:
    """Calculate OddsVal-based haircut multiplier (0.70-1.0).
    
    OddsVal >= 0 → 1.0 (no haircut, model is better than market)
    OddsVal between 0 and FLOOR → linear interpolation  
    OddsVal <= FLOOR → 1.0 - HAIRCUT_NEGATIVE_ODDSVAL_MAX
    """
    if odds_val is None or odds_val >= 0:
        return 1.0
    if odds_val <= ODDSVAL_HAIRCUT_FLOOR:
        return 1.0 - HAIRCUT_NEGATIVE_ODDSVAL_MAX
    # Linear interpolation between 0 and FLOOR
    ratio = odds_val / ODDSVAL_HAIRCUT_FLOOR  # both negative, ratio is positive
    return 1.0 - (ratio * HAIRCUT_NEGATIVE_ODDSVAL_MAX)
```

3. Na função `compute_stake()`, junto com o ECE haircut:
```python
    odds_val = market_output.get("league_odds_val")
    oddsval_factor = oddsval_haircut_factor(odds_val)
    adjusted *= oddsval_factor
```

4. Incluir `oddsval_factor` no dict de retorno.

**IMPORTANTE:** Mesmo aviso — `league_odds_val` precisa chegar via `market_output`. Verificar propagação.

---

### TASK 2D — Market Family Exposure Cap

**O quê:** Limitar exposição diária por família de mercado para evitar que corners (ou qualquer família) domine a alocação.

**Onde:** `backend/services/bankroll_engine.py`

**Como:**

1. Adicionar constantes:
```python
# ─── Market Family Exposure Caps (#171 FASE 2D) ───
# Prevent any single market family from dominating daily exposure.
# Keys match market_type prefixes from MarketOutput.
MAX_FAMILY_STAKE_DAY_PCT = {
    "corners": float(os.getenv("MAX_CORNER_STAKE_DAY_PCT", "0.05")),    # 5%
    "cards": float(os.getenv("MAX_CARDS_STAKE_DAY_PCT", "0.05")),       # 5%
    "goals": float(os.getenv("MAX_GOALS_STAKE_DAY_PCT", "0.10")),       # 10% (includes O/U, BTTS)
    "1x2": float(os.getenv("MAX_1X2_STAKE_DAY_PCT", "0.10")),           # 10%
}
DEFAULT_FAMILY_CAP_PCT = 0.10  # fallback for unknown families
```

2. Adicionar helper para classificar market_type em família:
```python
def _market_family(market_type: str) -> str:
    """Map market_type to family for exposure capping."""
    mt = market_type.lower()
    if "corner" in mt:
        return "corners"
    if "card" in mt:
        return "cards"
    if any(k in mt for k in ("over", "under", "btts", "gol")):
        return "goals"
    if "1x2" in mt or "result" in mt or "double" in mt:
        return "1x2"
    return mt  # unknown family
```

3. Adicionar nova função `apply_family_cap`:
```python
def apply_family_cap(
    all_stakes: List[Dict[str, Any]],
    bankroll: float,
) -> List[Dict[str, Any]]:
    """Apply per-market-family daily cap.
    
    Groups stakes by market family, scales down proportionally
    if any family exceeds its cap.
    """
    from collections import defaultdict
    
    family_totals = defaultdict(float)
    family_items = defaultdict(list)
    
    for s in all_stakes:
        family = _market_family(s.get("market_type", "unknown"))
        family_totals[family] += s.get("stake", 0)
        family_items[family].append(s)
    
    for family, total in family_totals.items():
        cap_pct = MAX_FAMILY_STAKE_DAY_PCT.get(family, DEFAULT_FAMILY_CAP_PCT)
        max_family = bankroll * cap_pct
        if total > max_family and total > 0:
            scale = max_family / total
            for s in family_items[family]:
                s["stake"] = round(s["stake"] * scale, 2)
                s["family_capped"] = True
                s["family_cap_scale"] = round(scale, 3)
            logger.warning(
                f"[bankroll] Family '{family}' capped: {total:.2f} → {max_family:.2f} "
                f"(scale={scale:.3f}, cap={cap_pct:.0%})"
            )
    
    return all_stakes
```

**IMPORTANTE:** Esta função deve ser chamada ANTES de `apply_daily_cap` na cadeia de processamento. Verificar onde `apply_daily_cap` é chamada (provavelmente em `market_service.py` ou `fixtures_service.py`) e inserir `apply_family_cap` imediatamente antes.

---

### TASK 2A — Daily Loss Circuit Breaker (Backend)

**O quê:** Se as perdas do dia excedem 15% da banca, bloquear novos stakes.

**Onde:** `backend/services/bankroll_engine.py`

**Como:**

1. Adicionar constante:
```python
# ─── Daily Loss Circuit Breaker (#171 FASE 2A) ───
DAILY_LOSS_BREAKER_PCT = float(os.getenv("DAILY_LOSS_BREAKER_PCT", "0.15"))  # 15%
```

2. Adicionar função:
```python
def check_daily_loss_breaker(
    daily_pnl: float,
    bankroll: float,
) -> bool:
    """Return True if daily loss exceeds circuit breaker threshold.
    
    Args:
        daily_pnl: Today's P&L (negative = loss)
        bankroll: Starting bankroll for the day
    
    Returns:
        True if breaker tripped (should block new bets)
    """
    if bankroll <= 0:
        return True
    loss_pct = abs(min(0, daily_pnl)) / bankroll
    if loss_pct >= DAILY_LOSS_BREAKER_PCT:
        logger.warning(
            f"[bankroll] CIRCUIT BREAKER: daily loss {loss_pct:.1%} >= {DAILY_LOSS_BREAKER_PCT:.0%} threshold"
        )
        return True
    return False
```

3. A integração no frontend (dashboard mostrando alerta quando breaker ativo) fica para task separada. Por ora, o backend apenas expõe a lógica. Adicionar verificação no endpoint de picks/decisions se existir.

---

### TASK 2E — Documentação (#171 FASE 4)

**ATENÇÃO:** Registrar com a causa raiz REAL, NÃO a hipótese inicial H1.

1. Adicionar ao `docs/REGISTRO_CORRECOES.md`:

```markdown
## 171 — INCIDENTE CRÍTICO: Perda de 50% da banca em 24h

**Data:** 2026-04-27
**Arquivos afetados:** backend/services/bankroll_engine.py, backend/cron_handler.py, backend/audit.py, backend/routes/debug.py
**Severidade:** Crítica (P0)
**Status:** Corrigido (FASE 0 + FASE 2)

### Problema identificado
A banca foi reduzida em 50% em 24 horas por overexposure em corners.

### Causa raiz (confirmada por análise forense de 48h)
1. **Trigger primário — #170-A (NB2 α per-league):** Redução do α de 0.15 para 0.005-0.03 estreitou a variância do NB2, gerando probabilidades mais confiantes. Resultado: picks de corners/dia subiram 2.89× (3.72 → 10.75) e stake de corners/dia subiu 5.93× (1.20% → 7.11% da banca).
2. **Amplificador — ECE 0.07-0.11:** Overconfidence de 7-11% nas probabilidades inflou alocações Kelly.
3. **Agravante — VIÁVEL floor:** Forçava stakes de 0.5% quando Kelly retornava 0, acumulando exposição em mercados sem edge real.

### Correções aplicadas

**FASE 0 (emergência, deployada 27/04):**
- AUTO_APPLY_CONFIDENCE_MIN=101 (bloqueia auto-apply)
- VIAVEL_FLOOR_PCT=0 (desabilita floor)
- CORNERS_ALPHA_CALIBRATED=false (reverte α)
- lambda_deflation adicionado ao ADJUSTMENT_LIMITS

**FASE 2 (hardening):**
- ECE haircut: reduz Kelly quando ECE > 0.06 (até -25%)
- OddsVal haircut: reduz Kelly quando modelo pior que mercado (até -30%)
- Market family exposure cap: corners max 5%, goals max 10% por dia
- Daily loss circuit breaker: bloqueia novos stakes quando perda diária > 15%

### Lição aprendida
Reduzir variância de distribuição (α do NB2) SEM recalibrar thresholds de EV cria overexposure silenciosa. Mais picks cruzam threshold → mais stake → concentração em mercados de cauda. ECE amplifica porque Kelly confia em probabilidades infladas. Defesas obrigatórias: (1) cap de exposição por família de mercado, (2) haircut por qualidade de calibração (ECE/OddsVal), (3) circuit breaker de perda diária.
```

2. Adicionar ao `docs/REGRAS_ATIVAS.md` uma regra #171 com o mesmo conteúdo resumido.

3. Adicionar ao `docs/INDICE_REGRAS.md`:
```
| #171 | Proteção de banca: ECE/OddsVal haircuts, family cap, daily loss breaker | bankroll_engine.py |
```

4. Atualizar `docs/prompt_171_emergency_bankroll_protection.md`:
- Na seção de hipóteses, marcar H1 como REFUTADA, H5 (#170-A) como CONFIRMADA
- Adicionar seção "CAUSA RAIZ CONFIRMADA" com os dados da análise forense

---

## PRE-MORTEM OBRIGATÓRIO

Antes de implementar cada task, responder:
1. O que pode dar errado com essa mudança?
2. Se ECE/OddsVal não estiverem disponíveis no market_output, o haircut retorna 1.0 (neutro) — confirmar que é o fallback correto.
3. O family cap pode over-reduce stakes se combinado com daily cap — confirmar que a ordem family → daily não causa dupla penalização excessiva.

## VALIDAÇÃO PÓS-IMPLEMENTAÇÃO

```bash
# 1. Python syntax check
python -m py_compile backend/services/bankroll_engine.py

# 2. Grep para verificar que os novos haircuts estão sendo aplicados
grep -n "ece_haircut_factor\|oddsval_haircut_factor\|apply_family_cap" backend/services/bankroll_engine.py

# 3. Verificar que market_output propaga ECE/OddsVal
grep -rn "league_ece\|league_odds_val" backend/

# 4. Contar linhas (deve ser ~500-550, partindo de 375)
wc -l backend/services/bankroll_engine.py

# 5. Diff para confirmar que mudanças são pontuais
git diff backend/services/bankroll_engine.py | head -100
```

## PROIBIÇÕES

- NÃO reescrever o arquivo inteiro. Fazer edits pontuais.
- NÃO alterar constantes existentes (KELLY_FRACTION, STAKE_MULTIPLIER, etc.)
- NÃO tocar em compute_stake_oportunidade (modo Oportunidade é separado)
- NÃO remover os feature flags (env vars) — eles permitem rollback zero-downtime
- NÃO fazer deploy automático — apenas implementar e commitar
