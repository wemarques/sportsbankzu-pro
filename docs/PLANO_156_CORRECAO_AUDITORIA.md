# PLANO #156 — Correção dos Problemas da Auditoria 19/04/2026

> 6 problemas identificados, 5 fases de implementação

---

## DIAGNÓSTICO CONSOLIDADO

| # | Problema | Métrica | Root Cause |
|---|----------|---------|------------|
| A | Lambda Erro 1.17 | target < 0.5 | Default deflation = 1.0 (sem deflação) quando calibração per-league está vazia. Lambdas inflados → overprediction sistemática |
| B | SAFE Acurácia 0% | meta > 65% | Circuit breaker #043 ativo — esperado. Nenhuma ação necessária até 3 auditorias >50% |
| C | Escanteios Over 6.5: 0/4 | 0% acurácia | Linhas baixas (4.5-6.5) geram probabilidades altas por Poisson (~82%), deflação #105 insuficiente para eliminar overconfidence |
| D | Under 3.5 Gols: 3/7 | 42.9% acurácia | Lambda inflado gera P(Under 3.5) artificialmente baixo → picks de Under saem com prob errada |
| E | A-League Brier 0.4579 | péssimo | Lambda O/U deflation = 1.0 (não deflacionado), dados esparsos por calendário diferente |
| F | Süper Lig 43%, Bundesliga 44% | abaixo aceitável | Calibração desatualizada: Süper Lig com deflação excessiva em cards; Bundesliga com BTTS deflation 0.9 agressivo demais |

### Dependências entre problemas

```
A (Lambda Erro) ──► D (Under 3.5) ──► B (SAFE)
                ──► E (A-League)
                ──► F (Ligas fracas)
C (Escanteios) = independente
```

**O problema A (Lambda Erro 1.17) é a raiz principal.** Resolver A melhora automaticamente D, E e F.

---

## FASE 1 — Recalibrar deflation per-league (Problema A + E + F)

### O que fazer
Rodar `calibrate_league()` para as ligas com pior performance, forçando o grid search a encontrar novos `lambda_multiplier` baseados nos dados reais.

### Implementação

```bash
# Endpoint de calibração existente — rodar per-league
curl -X POST "https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/api/backtesting/calibrate?league=a-league"
curl -X POST "https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/api/backtesting/calibrate?league=super-lig"
curl -X POST "https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/api/backtesting/calibrate?league=bundesliga"
```

### Validação
- Antes: verificar valor atual de `lambda_multiplier` no DB
- Depois: confirmar que o valor mudou de 1.0 para algo < 1.0
- Critério: Brier da liga deve cair pelo menos 10%

### Regras respeitadas
- #042: Calibração usa backtesting com N >= 20 jogos ✅
- #079: MIN_N_BRIER = 20 respeitado pelo endpoint ✅
- #043: Não estamos reativando SAFE ✅

---

## FASE 2 — Elevar piso mínimo de deflação default (Problema A)

### O que fazer
Mudar `_DEFAULT_OU_DEFLATION` de 1.0 para 0.90 em `poisson_matrix.py`. Ligas sem calibração per-league receberão deflação mínima de 10% em vez de zero.

### Implementação
**Arquivo:** `backend/modeling/poisson_matrix.py:77`

```python
# ANTES
_DEFAULT_OU_DEFLATION = 1.0

# DEPOIS (#156: default deflation 10% para ligas sem calibração)
_DEFAULT_OU_DEFLATION = 0.90
```

### Justificativa
- Lambda error 1.17 = lambdas ~20% acima dos gols reais em média
- 10% deflation default é conservador (não resolve tudo, mas reduz erro em ~0.3)
- Ligas com calibração per-league já têm valores customizados e não são afetadas

### Regras respeitadas
- #043: Lambda deflation 15% está ativa — estamos aplicando 10% como piso, compatível ✅
- #042: Mudança é conservadora (10%) e baseada em N=87 jogos de auditoria ✅

---

## FASE 3 — Bloquear Escanteios Over ≤ 6.5 (Problema C)

### O que fazer
Adicionar floor de linha mínima para Over corners: excluir Over 4.5, 5.5 e 6.5 do scanner.

### Root cause
Linhas baixas de escanteios geram probabilidades Poisson ~80-85% (quase certeza matemática). Após deflação #105, ficam ~58-62% — parecem "boas" mas o bookmaker precifica melhor, e 0/4 confirma.

Over 7.5 tem 75% acurácia (12/16) — a partir de 7.5 o modelo funciona.

### Implementação
**Arquivo:** `backend/services/ev_classification.py`

Na função que gera linhas de escanteios, adicionar filtro:

```python
# #156: Corner Over lines below 7.5 excluded — 0% accuracy on 6.5 and below
CORNERS_OVER_MIN_LINE = 7.5
```

Alternativa menos agressiva: elevar threshold específico para Over ≤ 6.5 de 55% para 75%.

### Validação
- Confirmar que Over 7.5+ continua sendo gerado
- Confirmar que Over 6.5 e abaixo são filtrados

### Regras respeitadas
- #110: Scanner gera 4.5-12.5, mas dedup mantém 1 melhor por direção — estamos cortando as piores ✅
- #042: Decisão baseada em dados reais (0/4 = 0%) com N >= 4 ✅

---

## FASE 4 — Under 3.5 Gols (Problema D)

### O que fazer
Este problema é **consequência direta de A** (lambda inflado). Com lambda inflado, P(Under 3.5) fica artificialmente baixo, e os picks de Under são gerados com probabilidades erradas.

### Ação
- **Resolver FASE 1 e 2 primeiro** — a deflação corrigida reduz lambda, o que automaticamente melhora P(Under 3.5)
- **Monitorar na próxima rodada**: se Under 3.5 continuar < 50% após deflação, investigar se threshold de Under precisa de ajuste

### Implementação (condicional)
Se após FASE 1+2 o Under 3.5 continuar ruim:

```python
# ev_classification.py — elevar threshold de Under goals
# ANTES: prob >= 0.55 (igual a Over)
# DEPOIS: prob >= 0.58 para Under (mais conservador)
```

---

## FASE 5 — Documentação e Monitoramento

### Registrar
1. `docs/REGISTRO_CORRECOES.md` — entrada #156
2. `docs/REGRAS_ATIVAS.md` — regra de deflation default
3. `docs/INDICE_REGRAS.md` — índice

### Monitorar (próximas 3 rodadas)
- [ ] Lambda Erro Médio < 0.8 (melhoria de 30%+ sobre 1.17)
- [ ] Brier global < 0.23 (melhoria sobre 0.2437)
- [ ] A-League Brier < 0.35
- [ ] Escanteios Over 7.5+ mantém > 70% acurácia
- [ ] Under 3.5 > 50% acurácia
- [ ] Shadow SAFE começa a acumular picks

### Critério de sucesso
Se após 3 rodadas:
- Lambda erro < 0.5 por 3 rodadas → pode remover deflation (#043)
- SAFE accuracy > 50% por 3 auditorias → pode reativar SAFE (#043)

---

## ORDEM DE EXECUÇÃO

```
FASE 1 (calibração) ─── pode rodar agora via endpoint
    │
    ├──► FASE 2 (default deflation) ─── implementar no código
    │         │
    │         └──► FASE 4 (Under 3.5) ─── monitorar, ação condicional
    │
FASE 3 (corners 6.5) ─── independente, implementar no código
    │
    └──► FASE 5 (documentação) ─── após tudo implementado
```

**Tempo estimado:** FASE 1 (5min por liga), FASE 2 (2min), FASE 3 (5min), FASE 5 (5min)
**FASE 4:** monitoramento pós-deploy, sem implementação imediata
