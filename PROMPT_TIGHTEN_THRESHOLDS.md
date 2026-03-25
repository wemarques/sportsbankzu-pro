# PROMPT — Elevar Thresholds SAFE/NEUTRO Baseado na Auditoria da Rodada

## CONTEXTO

A auditoria pós-rodada com 27 jogos revelou:
- **SAFE acurácia: 0.0%** — nenhum pick SAFE acertou
- **Escanteios Over 9.5: 0% acerto** — viés sistemático
- **BTTS: 50% acerto** — moeda jogada
- **Brier Score: 0.3368** — próximo do crítico (>0.35)
- **Under 4.5 com EV: 0.3%** classificado como NEUTRO-Q — min_ev muito baixo

A causa raiz está em 3 problemas no `ev_classification.py`:

1. **SAFE aceita EV >= 0** (linhas 165-167) — qualquer mercado com probabilidade alta e EV marginal (0.1%) vira SAFE
2. **NEUTRO aceita EV negativo até -3%** (linhas 177-178) e o else final (linha 180-181) classifica como NEUTRO sem checar EV
3. **NEUTRO-Q exige apenas EV >= 2%** — baixo demais para ser "qualificado"
4. **SAFE não exige edge mínimo** — pode ser SAFE sem edge nenhum
5. **Corners thresholds são frouxos** (safe_prob=0.65) dado 0% de acerto

## ARQUIVO A MODIFICAR

`backend/services/ev_classification.py`

---

## CORREÇÃO 1 — Elevar thresholds numéricos

Substituir `DEFAULT_THRESHOLDS` (~linhas 41-72) por valores mais conservadores:

```python
DEFAULT_THRESHOLDS = {
    "1X2": {
        "safe_prob": 0.62,    "neutro_prob": 0.45,    # era 0.55 / 0.42
        "safe_ev": 0.08,      "neutro_ev": 0.00,      # era 0.05 / 0.00
        "safe_edge": 0.06,    "neutro_edge": 0.02,    # era 0.04 / 0.01
        "min_quality": 0.40,                            # era 0.30
    },
    "Over/Under": {
        "safe_prob": 0.75,    "neutro_prob": 0.60,    # era 0.68 / 0.58
        "safe_ev": 0.06,      "neutro_ev": 0.00,      # era 0.04 / 0.00
        "safe_edge": 0.05,    "neutro_edge": 0.02,    # era 0.03 / 0.01
        "min_quality": 0.40,                            # era 0.30
    },
    "BTTS": {
        "safe_prob": 0.75,    "neutro_prob": 0.62,    # era 0.70 / 0.60
        "safe_ev": 0.06,      "neutro_ev": 0.00,      # era 0.04 / 0.00
        "safe_edge": 0.05,    "neutro_edge": 0.02,    # era 0.03 / 0.01
        "min_quality": 0.40,                            # era 0.30
    },
    "Double Chance": {
        "safe_prob": 0.82,    "neutro_prob": 0.68,    # era 0.75 / 0.65
        "safe_ev": 0.04,      "neutro_ev": 0.00,      # era 0.03 / 0.00
        "safe_edge": 0.03,    "neutro_edge": 0.01,    # era 0.02 / 0.01
        "min_quality": 0.40,                            # era 0.30
    },
    "Corners": {
        "safe_prob": 0.72,    "neutro_prob": 0.58,    # era 0.65 / 0.55
        "safe_ev": 0.08,      "neutro_ev": 0.02,      # era 0.04 / 0.00
        "safe_edge": 0.06,    "neutro_edge": 0.02,    # era 0.03 / 0.01
        "min_quality": 0.45,                            # era 0.35
    },
}
```

Substituir `NEUTRO_QUALIFICADO_THRESHOLDS` (~linhas 75-80):

```python
NEUTRO_QUALIFICADO_THRESHOLDS = {
    "min_ev": 0.05,          # era 0.02 — EV deve ser >= 5% (não mais 2%)
    "min_edge": 0.03,        # NOVO — edge mínimo de 3%
    "min_quality": 0.45,     # era 0.40
    "min_prob": 0.52,        # era 0.50
    "must_have_odds": True,
}
```

---

## CORREÇÃO 2 — SAFE não pode ter EV marginal

A lógica atual (linhas 165-167) permite SAFE com EV >= 0:

```python
# PROBLEMA: EV 0.1% é tratado como SAFE
elif output.odds_available and output.ev is not None and output.ev >= 0:
    # Has odds, prob is high, but EV is marginal
    classification = MarketClassification.SAFE
```

Corrigir: SAFE exige EV >= safe_ev E edge >= safe_edge:

```python
    # SAFE: high prob + positive EV + sufficient edge + good data
    if (prob >= th.get("safe_prob", 0.60) and
        output.data_quality_score >= th.get("min_quality", 0.3)):
        if ReasonCode.SUSPICIOUS_EV in reason_codes:
            classification = MarketClassification.NEUTRO
        elif (output.odds_available and
              output.ev is not None and output.ev >= th.get("safe_ev", 0.05) and
              output.edge is not None and output.edge >= th.get("safe_edge", 0.04)):
            # All conditions met: high prob + real EV + real edge
            classification = MarketClassification.SAFE
        elif output.odds_available and output.ev is not None and output.ev >= 0:
            # High prob, positive EV but insufficient edge — NEUTRO, not SAFE
            classification = MarketClassification.NEUTRO
        elif not output.odds_available:
            classification = MarketClassification.NEUTRO
```

A diferença: antes EV >= 0 dava SAFE, agora dá NEUTRO. SAFE exige EV >= safe_ev **E** edge >= safe_edge.

---

## CORREÇÃO 3 — NEUTRO não aceita EV negativo sem motivo

A lógica atual (linhas 177-181) aceita EV até -3% e tem um else que pega tudo:

```python
# PROBLEMA: else vira NEUTRO sem checar nada
elif output.odds_available and output.ev is not None and output.ev >= -0.03:
    classification = MarketClassification.NEUTRO
else:
    classification = MarketClassification.NEUTRO  # <-- pega tudo!
```

Corrigir: NEUTRO exige EV >= neutro_ev. Sem odds ou com EV muito negativo, fica NO_BET:

```python
    # NEUTRO: moderate prob
    elif (prob >= th.get("neutro_prob", 0.50) and
          output.data_quality_score >= th.get("min_quality", 0.3) * 0.8):
        if output.odds_available and output.ev is not None and output.ev >= th.get("neutro_ev", 0.0):
            classification = MarketClassification.NEUTRO
        elif not output.odds_available:
            # No odds — show as NEUTRO with fair odd only
            classification = MarketClassification.NEUTRO
        # else: EV negative with odds → stays NO_BET (don't force NEUTRO)
```

Remover o `elif ev >= -0.03` e o `else` que forçava tudo como NEUTRO.

---

## CORREÇÃO 4 — NEUTRO-Q exige edge mínimo

A função `_is_neutro_qualificado` (~linhas 201-217) não checa edge. Adicionar:

```python
def _is_neutro_qualificado(output: MarketOutput, prob: float) -> bool:
    """Check if a NEUTRO market qualifies for multiples eligibility."""
    th = NEUTRO_QUALIFICADO_THRESHOLDS

    if th["must_have_odds"] and not output.odds_available:
        return False

    if output.ev is None or output.ev < th["min_ev"]:
        return False

    # NEW: require minimum edge
    if output.edge is None or output.edge < th.get("min_edge", 0.03):
        return False

    if output.data_quality_score < th["min_quality"]:
        return False

    if prob < th["min_prob"]:
        return False

    return True
```

---

## RESUMO DAS MUDANÇAS

| Parâmetro | Antes | Depois | Impacto |
|-----------|-------|--------|---------|
| 1X2 safe_prob | 0.55 | 0.62 | Menos SAFE em 1X2 |
| Over/Under safe_prob | 0.68 | 0.75 | SAFE precisa > 75% |
| BTTS safe_prob | 0.70 | 0.75 | BTTS mais exigente |
| Corners safe_prob | 0.65 | 0.72 | Corners muito mais restrito |
| safe_ev (todos) | 0.04-0.05 | 0.06-0.08 | EV mínimo para SAFE sobe |
| safe_edge (todos) | 0.02-0.04 | 0.03-0.06 | SAFE exige edge real |
| min_quality | 0.30 | 0.40-0.45 | Dados fracos não geram SAFE |
| NEUTRO-Q min_ev | 0.02 | 0.05 | Under 4.5 EV 0.3% não é mais Q |
| NEUTRO-Q min_edge | (não existia) | 0.03 | Q exige margem real |
| SAFE com EV >= 0 | SAFE | NEUTRO | EV marginal não é SAFE |
| NEUTRO com EV < -3% | NEUTRO | NO_BET | EV negativo sai da lista |

---

## VALIDAÇÃO

```bash
pytest -q
cd frontend/next && npm run build
```

Verificar:
1. Mercados com EV < 5% não devem ser NEUTRO-Q
2. Mercados com EV < 8% (1X2/Corners) ou < 6% (O/U/BTTS) não devem ser SAFE
3. Mercados com EV negativo + odds reais devem ser NO_BET ou NEUTRO (sem o Q)
4. Under 4.5 com EV 0.3% → deve cair de NEUTRO-Q para NEUTRO

Commit:
```
fix: tighten SAFE/NEUTRO thresholds based on 27-game audit (0% SAFE accuracy)

- Raise safe_prob: 1X2 0.55→0.62, O/U 0.68→0.75, Corners 0.65→0.72
- Raise safe_ev: all markets now require 6-8% EV for SAFE (was 4-5%)
- SAFE now requires both EV >= safe_ev AND edge >= safe_edge (was EV >= 0)
- NEUTRO no longer accepts EV < 0 with real odds (was accepting down to -3%)
- NEUTRO-Q min_ev raised from 2% to 5%, added min_edge 3%
- min_quality raised from 0.30 to 0.40-0.45 across all markets
```

Push:
```bash
git push origin main
```
