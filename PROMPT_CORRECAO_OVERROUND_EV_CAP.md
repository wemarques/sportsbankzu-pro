# PROMPT — Corrigir Fórmula de Overround + Cap de EV

## CONTEXTO

A fórmula de derivação de odds Under está invertida. Ela DIVIDE a probabilidade pelo overround (tornando a odd MAIOR), quando deveria SUBTRAIR a implied prob de Over do overround total. Resultado: odds Under derivadas ficam infladas (ex: 3.03 em vez de 2.52), gerando EV fictício de 99-139%.

## CORREÇÃO 1 — Fórmula de Overround (3 arquivos)

### Lógica correta:

Em um mercado de 2 resultados (Over/Under), a soma das probabilidades implícitas = 1 + margem (overround). Exemplo real:
- Over 2.5 @ 1.53 → implied_over = 1/1.53 = 0.654 (65.4%)
- Under 2.5 @ 2.50 → implied_under = 1/2.50 = 0.400 (40.0%)
- Soma: 0.654 + 0.400 = 1.054 (overround = 5.4%)

Portanto, quando só temos a odd de Over:
```
implied_over = 1 / odd_over
implied_under = OVERROUND - implied_over   ← CORRETO
under_odd = 1 / implied_under
```

A fórmula ERRADA que está no código:
```
implied_under = (1 - implied_over) / OVERROUND   ← ERRADO (divide, deveria subtrair)
```

### 1.1 Arquivo: `backend/services/ev_classification.py`

Localizar o bloco de derivação de Under para gols (~linhas 340-345):

```python
# DE (ERRADO):
OVERROUND = 1.05
implied_over = 1.0 / book_odd
implied_under_raw = max(0.01, 1.0 - implied_over)
implied_under_fair = implied_under_raw / OVERROUND
under_odd = round(1.0 / implied_under_fair, 2) if implied_under_fair > 0.01 else None

# PARA (CORRETO):
OVERROUND = 1.05
implied_over = 1.0 / book_odd
implied_under = OVERROUND - implied_over
under_odd = round(1.0 / implied_under, 2) if implied_under > 0.01 else None
```

Localizar o bloco de derivação de Under para corners (~linhas 522-527) e aplicar a mesma correção:

```python
# DE (ERRADO):
OVERROUND = 1.06
implied_over = 1.0 / float(over_odd)
implied_under_raw = max(0.01, 1.0 - implied_over)
implied_under_fair = implied_under_raw / OVERROUND
under_odd = round(1.0 / implied_under_fair, 2) if implied_under_fair > 0.01 else None

# PARA (CORRETO):
OVERROUND = 1.06
implied_over = 1.0 / float(over_odd)
implied_under = OVERROUND - implied_over
under_odd = round(1.0 / implied_under, 2) if implied_under > 0.01 else None
```

### 1.2 Arquivo: `backend/services/market_service.py`

Corrigir `calcular_odd_under()` (~linha 216):

```python
# DE (ERRADO):
def calcular_odd_under(odd_over: float, overround: float = 1.05) -> Optional[float]:
    if not odd_over or odd_over <= 1.0:
        return None
    prob_over = 1.0 / odd_over
    prob_under_raw = 1.0 - prob_over
    prob_under_fair = prob_under_raw / overround
    if prob_under_fair <= 0:
        return None
    return round(1.0 / prob_under_fair, 2)

# PARA (CORRETO):
def calcular_odd_under(odd_over: float, overround: float = 1.05) -> Optional[float]:
    if not odd_over or odd_over <= 1.0:
        return None
    implied_over = 1.0 / odd_over
    implied_under = overround - implied_over
    if implied_under <= 0.01:
        return None
    return round(1.0 / implied_under, 2)
```

### 1.3 Arquivo: `backend/modeling/corners/price_ladder.py`

Buscar qualquer derivação de Under odd e aplicar a mesma correção. Procurar por `1.0 - implied_over` e trocar por `OVERROUND - implied_over`.

## CORREÇÃO 2 — Cap de EV Máximo

### 2.1 Adicionar ReasonCode SUSPICIOUS_EV

Arquivo: `backend/models/market_output.py`

No enum `ReasonCode`, adicionar:
```python
SUSPICIOUS_EV = "SUSPICIOUS_EV"
```

### 2.2 Aplicar cap no classify_market

Arquivo: `backend/services/ev_classification.py`

Na função `classify_market()`, APÓS `output.compute_ev()` (~linha 116) e ANTES dos reason_codes checks, adicionar:

```python
# ─── EV sanity cap ───
# EV > 40% is almost certainly a data issue (prob/odds mismatch)
MAX_CREDIBLE_EV = 0.40
if output.ev is not None and output.ev > MAX_CREDIBLE_EV:
    reason_codes.append(ReasonCode.SUSPICIOUS_EV)
    logger.warning(
        f"[EV Cap] {output.display_label}: EV={output.ev:.1%} exceeds {MAX_CREDIBLE_EV:.0%} cap. "
        f"Prob={prob:.1%}, Odd={output.book_odd}. Likely prob/odds source mismatch."
    )
```

Depois, na seção de classificação (~linha 148), adicionar bloqueio de SAFE quando EV é suspeito:

```python
# SAFE: high prob + positive EV + sufficient edge + good data
if (prob >= th.get("safe_prob", 0.60) and
    output.data_quality_score >= th.get("min_quality", 0.3)):
    # BLOCK SAFE if EV is suspiciously high
    if ReasonCode.SUSPICIOUS_EV in reason_codes:
        classification = MarketClassification.NEUTRO
    elif output.odds_available and output.ev is not None and output.ev >= th.get("safe_ev", 0.05):
        classification = MarketClassification.SAFE
    # ... rest unchanged
```

E na seção NEUTRO_QUALIFICADO (~linha 171):

```python
# NEUTRO qualificado: upgrade NEUTRO if it meets additional criteria
# BUT NOT if EV is suspicious
if classification == MarketClassification.NEUTRO:
    if _is_neutro_qualificado(output, prob) and ReasonCode.SUSPICIOUS_EV not in reason_codes:
        classification = MarketClassification.NEUTRO_QUALIFICADO
```

## VALIDAÇÃO

Após as correções, rodar `pytest -q`.

Verificar manualmente com Over 2.5 @ 1.53 (exemplo Flamengo vs Remo):
- `calcular_odd_under(1.53)` deve retornar ~2.52 (não 3.03)
- EV de Under 2.5 com prob 83% e odd 2.52: (0.83 × 2.52) - 1 = 109% → SUSPICIOUS_EV
- EV de Under 2.5 com prob 83% e odd real 2.40: (0.83 × 2.40) - 1 = 99% → SUSPICIOUS_EV
- Classificação: NEUTRO (não NEUTRO-Q, não SAFE)

NOTA: O EV de 99% mesmo com odd real (2.40) indica que a PROBABILIDADE de 83% também está errada para este jogo. Isso é um problema separado (FootyStats Over 2.5 potential = 17% vs casas = 65%). O cap de EV protege o sistema de classificar como SAFE/NEUTRO-Q mercados onde prob e odds divergem muito.

Fazer commit:
```
fix: correct overround formula for Under odds derivation + add EV sanity cap

- Fix: Under odds now derived as 1/(OVERROUND - implied_over) instead of 1/((1-implied_over)/OVERROUND)
- Fix: calcular_odd_under() in market_service.py uses same corrected formula
- Add: SUSPICIOUS_EV reason code for EV > 40%
- Add: Block SAFE/NEUTRO-Q classification when EV is suspiciously high
```

Depois push:
```bash
git push origin main
```
