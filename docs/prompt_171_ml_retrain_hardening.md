# Prompt #171 — ML Retrain Hardening: OddsVal Gate + ECE Haircut + League Pruning

> **Uso:** Copiar o conteúdo abaixo (a partir de "---") e colar no Claude Code como prompt.

---

## LEITURA OBRIGATÓRIA ANTES DE COMEÇAR

Leia estes arquivos na íntegra antes de gerar qualquer código:

1. `backend/ml/train_model.py` linhas 27-34 (thresholds), 64-112 (ECE), 160-191 (MktEff), 459-496 e 585-599 (OddsVal)
2. `backend/ml/predictor.py` linhas 192-232 — gates de ativação ML (`is_ml_available`)
3. `backend/services/bankroll_engine.py` linhas 20-60 — Kelly config, haircuts, caps
4. `scripts/retrain_validate.py` linhas 148-177 — classificação de ligas
5. `.github/workflows/ml-retrain-validate.yml` — workflow CI
6. `docs/REGRAS_ATIVAS.md` — regras permanentes do sistema
7. `CLAUDE.md` seção "Workflow de Validação" — pre-mortem e red team obrigatórios

## ROLE

Atue como Engenheiro de ML Sênior especializado em modelos de calibração probabilística para apostas esportivas. Sua tarefa é endurecer o pipeline de retrain com gates adicionais baseados em dados reais de produção.

## CONTEXTO

O ML Retrain Validation Run #15 revelou um **paradoxo operacional**: o sistema ML bate o Poisson baseline internamente (5 ligas ML_ACTIVE com Brier < 0.60) mas perde para o mercado externamente (OddsVal NEGATIVO em TODAS as 22 ligas). Isso significa que nossas probabilidades são menos calibradas que as odds implícitas do mercado — e o Kelly está calculando stakes com edge fantasma.

**Dados concretos do Run #15:**

| Métrica | Observação |
|---------|------------|
| OddsVal | Negativo em 22/22 ligas (pior: Super Lig -0.0145, La Liga -0.0125) |
| ECE | 0.07-0.11 nas ML_ACTIVE (Eredivisie 0.1101 = overconfidence severa) |
| MktEff=0 | Serie A e A-League com zero ineficiência detectada |
| Accuracy | A-League 38.05% (marginalmente acima de random 33%) |
| Brier | Melhor: 0.5689 (Primeira Liga) — melhoria marginal sobre baseline |

**Riscos identificados:**
1. Kelly opera com edge positivo quando OddsVal diz que não existe edge
2. ECE alto = overconfidence → stakes maiores do que deveriam
3. Ligas que NUNCA ativam consomem compute e chamadas API desnecessárias
4. GitHub Actions Node.js 20 deprecation vai quebrar CI

## INSTRUÇÃO PRINCIPAL: STEELMAN THE FIX

Não implemente as correções de forma isolada. Cada mudança deve ser defendida contra contra-argumentos:

1. **"OddsVal negativo é esperado — ML não precisa bater o mercado, só o Poisson."**
   → Verdade parcial. Para classificação pura, bater Poisson basta. Mas o Kelly usa a probabilidade ML diretamente para calcular edge vs odds de mercado. Se OddsVal < 0, a probabilidade ML é sistematicamente pior que a implied prob para sizing de apostas. O gate deve afetar o bankroll, não necessariamente a ativação ML.

2. **"ECE haircut penaliza ligas que são boas mas mal calibradas."**
   → A calibração PODE ser corrigida (Platt scaling, isotonic regression). Mas até implementar recalibração, o haircut é a defesa correta — melhor subapostar que superapostar com overconfidence.

3. **"Remover ligas do pipeline reduz diversificação."**
   → Ligas com Brier > 0.65 e Accuracy < 40% em N runs consecutivos não estão diversificando — estão adicionando ruído. Manter no pipeline de dados (FootyStats), remover do retrain ML.

## RESTRIÇÕES TÉCNICAS INVIOLÁVEIS

- **NÃO altere a lógica de treinamento do modelo** (RF+XGB ensemble, features, walk-forward). Escopo é EXCLUSIVAMENTE gates e bankroll adjustment.
- **NÃO reescreva arquivos inteiros.** Use edits pontuais. Diff only — mostre as linhas exatas que mudam antes de editar.
- **NÃO altere thresholds existentes** (BRIER_DEACTIVATION_THRESHOLD=0.63, KELLY_FRACTION=0.25) sem dados de backtesting documentado.
- **NÃO remova ligas do LEAGUES_CONFIG.** A exclusão é no pipeline de retrain ML, não na ingestão de dados gerais.
- **NÃO quebre o workflow CI.** Mudanças no `.yml` devem ser testáveis via `act` ou `workflow_dispatch`.

## TAREFAS DE EXECUÇÃO

### Task 1 — ODDSVAL GATE NO BANKROLL ENGINE (Prioridade: IMEDIATA)

**Problema:** Kelly calcula edge = `prob_model - (1/odd)`. Se OddsVal < 0, `prob_model` é sistematicamente pior que `1/odd` para este cálculo, gerando edge fantasma.

**Objetivo:** Quando OddsVal da liga é negativo, aplicar haircut adicional no bankroll engine que reduza a stake proporcionalmente à magnitude do OddsVal negativo.

**Implementação:**

1. Em `bankroll_engine.py`, adicionar novo haircut:
   ```python
   # ─── OddsVal Haircut (#171) ───
   # When ML odds calibration is worse than market (OddsVal < 0),
   # reduce stake proportionally. max haircut = 30% at OddsVal = -0.02
   HAIRCUT_NEGATIVE_ODDSVAL_MAX = 0.30   # Maximum 30% haircut
   ODDSVAL_HAIRCUT_FLOOR = -0.02         # OddsVal at which max haircut applies
   ```

2. Na função de cálculo de stake, após os haircuts existentes, adicionar:
   ```python
   # #171: OddsVal negative → model is less calibrated than market for sizing
   odds_val = league_meta.get("odds_value_added")
   if odds_val is not None and odds_val < 0:
       # Linear interpolation: 0 at OddsVal=0, max at ODDSVAL_HAIRCUT_FLOOR
       ratio = min(1.0, abs(odds_val) / abs(ODDSVAL_HAIRCUT_FLOOR))
       haircut_oddsval = ratio * HAIRCUT_NEGATIVE_ODDSVAL_MAX
       stake *= (1.0 - haircut_oddsval)
       if haircut_oddsval > 0.05:
           logger.info(f"[bankroll] {league_id}: OddsVal haircut {haircut_oddsval:.1%} (OddsVal={odds_val:.4f})")
   ```

3. **Problema de propagação:** `bankroll_engine.py` atualmente NÃO recebe metadados ML da liga. Investigar o call chain:
   - Quem chama `kelly_stake()`?
   - O caller tem acesso ao `league_id` e pode carregar `metadata.json`?
   - Se não, adicionar parâmetro `league_meta: Optional[dict] = None` à função.

4. **ATENÇÃO:** O OddsVal do metadata reflete o TREINO, não a previsão live. É um proxy de calibração, não uma métrica per-fixture. Documentar essa limitação.

**Validação:** Calcular impacto retroativo — para as 5 ligas ML_ACTIVE do Run #15, quanto a stake seria reduzida:
- La Liga: OddsVal=-0.0125 → ratio=0.625 → haircut=18.8%
- Eredivisie: OddsVal=-0.0040 → ratio=0.20 → haircut=6.0%
- Primeira Liga: OddsVal=-0.0055 → ratio=0.275 → haircut=8.3%
- Super Lig: OddsVal=-0.0145 → ratio=0.725 → haircut=21.8%
- Premiership: OddsVal=-0.0014 → ratio=0.07 → haircut=2.1%

### Task 2 — ECE HAIRCUT NO BANKROLL ENGINE (Prioridade: IMEDIATA)

**Problema:** ECE > 0.09 significa que probabilidades emitidas são ~9% off da frequência real. Se o modelo diz 65% mas a realidade é 56%, Kelly superaposta.

**Objetivo:** Adicionar haircut proporcional ao ECE quando acima de threshold.

**Implementação:**

1. Em `bankroll_engine.py`:
   ```python
   # ─── ECE Haircut (#171) ───
   # When model probabilities are poorly calibrated (ECE > threshold),
   # reduce stake. Kick in at ECE > 0.06, max haircut 25% at ECE >= 0.12
   ECE_HAIRCUT_THRESHOLD = 0.06    # ECE below this = no haircut
   ECE_HAIRCUT_MAX = 0.25          # Maximum 25% haircut
   ECE_HAIRCUT_CEILING = 0.12      # ECE at which max haircut applies
   ```

2. Na função de cálculo de stake:
   ```python
   # #171: High ECE → overconfident probabilities → reduce stake
   ece = league_meta.get("validation_ece")
   if ece is not None and ece > ECE_HAIRCUT_THRESHOLD:
       ratio = min(1.0, (ece - ECE_HAIRCUT_THRESHOLD) / (ECE_HAIRCUT_CEILING - ECE_HAIRCUT_THRESHOLD))
       haircut_ece = ratio * ECE_HAIRCUT_MAX
       stake *= (1.0 - haircut_ece)
       if haircut_ece > 0.05:
           logger.info(f"[bankroll] {league_id}: ECE haircut {haircut_ece:.1%} (ECE={ece:.4f})")
   ```

**Validação retroativa:**
- Eredivisie: ECE=0.1101 → ratio=0.835 → haircut=20.9%
- Ligue-1: ECE=0.0941 → ratio=0.568 → haircut=14.2%
- Primeira Liga: ECE=0.0881 → ratio=0.468 → haircut=11.7%

**Interação com Task 1:** Os haircuts são MULTIPLICATIVOS. Para Eredivisie (OddsVal + ECE):
- Stake × 0.94 (OddsVal) × 0.79 (ECE) = 0.743 → redução total de ~26%.
- Isso é aceitável? Se stake combinado < 0 seria cap no VIAVEL_FLOOR_PCT.

### Task 3 — LEAGUE PRUNING NO RETRAIN (Prioridade: CURTO PRAZO)

**Problema:** Ligas que NUNCA ativam consomem:
- ~5-10 chamadas FootyStats API por liga (3 seasons × endpoint por season)
- ~2-5 min de compute por liga no retrain
- Artifacts e S3 storage desnecessários

**Objetivo:** Criar lista de exclusão para ligas crônicas, sem remover do pipeline principal.

**Implementação:**

1. Em `scripts/retrain_validate.py`, adicionar no topo:
   ```python
   # #171: Leagues excluded from ML retrain due to chronic poor performance.
   # Still processed by main pipeline (FootyStats, Poisson, calibrator).
   # Review quarterly — if league improves, re-enable.
   ML_RETRAIN_EXCLUDED = {
       "a-league",           # Brier 0.658, Acc 38.1% — consistently worst
       "primera-division",   # Brier 0.652, Acc 40.9% — DEACTIVATED 5+ runs
   }
   ```

2. No loop de treinamento (linha ~85), filtrar:
   ```python
   if league_id in ML_RETRAIN_EXCLUDED:
       logger.info(f"[retrain] {league_id}: SKIPPED (ML_RETRAIN_EXCLUDED #171)")
       results_1x2.append({
           "league_id": league_id,
           "status": "excluded",
           "ml_deactivated": True,
           "reason": "chronic_poor_performance",
       })
       continue
   ```

3. Na classificação (linha ~156), tratar `status == "excluded"`:
   ```python
   elif r.get("status") == "excluded":
       classification = "EXCLUDED"
   ```

4. **Critério de re-inclusão:** Se backtesting manual (via `--leagues a-league`) mostrar Brier < 0.62 por 2 runs, remover da lista.

**NÃO excluir ainda:**
- Championship (0.6402) — próximo do threshold, pode melhorar
- Serie B (0.6414) — mercado brasileiro importante
- 2-Bundesliga (0.6357) — marginal, manter por diversificação
- Superliga (0.6349) — idem

### Task 4 — MKTEFF=0 WARNING E GATE ADICIONAL (Prioridade: CURTO PRAZO)

**Problema:** Serie A e A-League têm MktEff=0.0000. Isso significa que as odds implícitas não explicam NADA dos outcomes. Duas interpretações:
- (a) O mercado é realmente ineficiente (oportunidade) — improvável para Serie A
- (b) Os dados de odds implícitas estão corrompidos ou ausentes

**Objetivo:** Adicionar warning no retrain_validate.py e investigar a causa raiz.

**Implementação:**

1. Em `retrain_validate.py`, após a classificação:
   ```python
   # #171: Warning when MktEff is zero — likely data issue, not market inefficiency
   mkt_eff = r.get("market_efficiency_r2")
   if mkt_eff is not None and mkt_eff == 0.0:
       logger.warning(
           f"[retrain] {lid}: MktEff=0.0000 — odds data may be missing or corrupted. "
           f"Check implied_odds features in training data."
       )
       entry["mkt_eff_warning"] = "ZERO_LIKELY_DATA_ISSUE"
   ```

2. Em `predictor.py`, adicionar gate para MktEff=0 quando ML_ACTIVE:
   ```python
   # #171: If MktEff is exactly 0, odds features may be corrupted.
   # Don't suppress ML (it may still be useful) but log warning for monitoring.
   if market_eff is not None and market_eff == 0.0:
       logger.warning(
           f"[{league_id}] MktEff=0.0 — implied odds features may be missing. "
           f"ML activated but odds-dependent features are suspect."
       )
   ```

3. **Investigação obrigatória ANTES de implementar:** Verificar em `train_model.py` se `_compute_market_efficiency()` está recebendo `implied_probs=None` para essas ligas (linha 170 retorna None se vazio). Se sim, a causa é odds ausentes no dataset de treino, não ineficiência real.

### Task 5 — GITHUB ACTIONS NODE.JS 24 (Prioridade: MÉDIO PRAZO)

**Problema:** Warning no Run #15:
```
Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24:
actions/cache@v4, actions/checkout@v4, actions/setup-python@v5, actions/upload-artifact@v4.
```

**Objetivo:** Atualizar para versões compatíveis com Node 24.

**Implementação:**

1. Em `.github/workflows/ml-retrain-validate.yml`, atualizar:
   ```yaml
   # Antes:
   - uses: actions/checkout@v4
   - uses: actions/setup-python@v5
   - uses: actions/cache@v4
   - uses: actions/upload-artifact@v4

   # Depois:
   - uses: actions/checkout@v5
   - uses: actions/setup-python@v5  # Manter — v5 já suporta Node 24? Verificar.
   - uses: actions/cache@v5
   - uses: actions/upload-artifact@v5
   ```

2. **VERIFICAR antes de alterar:** Checar se `@v5` existe para cada action:
   ```bash
   # No terminal, verificar releases:
   gh api repos/actions/checkout/releases/latest --jq '.tag_name'
   gh api repos/actions/cache/releases/latest --jq '.tag_name'
   gh api repos/actions/upload-artifact/releases/latest --jq '.tag_name'
   gh api repos/actions/setup-python/releases/latest --jq '.tag_name'
   ```

3. **Aplicar também em:** `.github/workflows/ml-retrain-promote.yml` e qualquer outro workflow que use as mesmas actions.

4. **Remover** a variável `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` (linha 47) se as actions atualizadas já forem nativas Node 24.

### Task 6 — REGISTRO E DOCUMENTAÇÃO

1. Registrar #171 em `docs/REGISTRO_CORRECOES.md` seguindo o formato padrão
2. Adicionar regra permanente em `docs/REGRAS_ATIVAS.md`:
   ```
   #171 — ML Retrain Hardening
   - OddsVal negativo → haircut proporcional no bankroll (max 30%)
   - ECE > 0.06 → haircut proporcional no bankroll (max 25%)
   - A-League e Primera División excluídas do retrain ML (review trimestral)
   - MktEff=0 gera warning obrigatório (possível dado corrompido)
   ```
3. Adicionar entrada no `docs/INDICE_REGRAS.md`

## SAÍDA ESPERADA

### 1. Argumento Steelman (máx 200 palavras)
Por que haircuts baseados em OddsVal e ECE são superiores a gates binários (on/off)? Qual o risco de over-correction?

### 2. Diff de Código (arquivos modificados)

| Arquivo | Alteração |
|---------|-----------|
| `backend/services/bankroll_engine.py` | OddsVal haircut + ECE haircut + league_meta propagation |
| `backend/ml/predictor.py` | MktEff=0 warning (logging only) |
| `scripts/retrain_validate.py` | ML_RETRAIN_EXCLUDED + MktEff=0 warning + "excluded" status |
| `.github/workflows/ml-retrain-validate.yml` | Node.js 24 compatible actions |
| `.github/workflows/ml-retrain-promote.yml` | Node.js 24 compatible actions |
| `docs/REGISTRO_CORRECOES.md` | Entrada #171 |
| `docs/REGRAS_ATIVAS.md` | Regra #171 |
| `docs/INDICE_REGRAS.md` | Entrada #171 |

### 3. Plano de Validação

- **Antes de deploy:** Calcular impacto retroativo dos haircuts para as 5 ligas ML_ACTIVE. Documentar a redução percentual de stake para cada liga.
- **Após deploy:** Próximo retrain run (#16) deve mostrar "EXCLUDED" para A-League e primera-division. Comparar stakes do bankroll engine com e sem haircuts para 10 fixtures reais.
- **Kill switch:** Se ROI cair > 5% em 2 semanas pós-deploy, reverter haircuts setando `HAIRCUT_NEGATIVE_ODDSVAL_MAX = 0` e `ECE_HAIRCUT_MAX = 0`.

### 4. Impacto Esperado

| Métrica | Antes | Depois |
|---------|-------|--------|
| Overbet risk (ECE alta) | Unchecked | Haircut max 25% |
| Edge fantasma (OddsVal neg) | Unchecked | Haircut max 30% |
| Compute retrain | 22 ligas | 20 ligas (-9%) |
| CI stability | Node 20 deprecated | Node 24 native |

## SEQUÊNCIA DE EXECUÇÃO

```
1. Ler arquivos obrigatórios (bankroll_engine, predictor, retrain_validate, workflows)
2. "Diff only" — mostrar linhas exatas que mudam ANTES de editar
3. Investigar MktEff=0: verificar se implied_probs é None para Serie A e A-League
4. Investigar call chain de bankroll_engine: como propagar league_meta
5. Implementar Task 1 (OddsVal haircut) — edits pontuais
6. Implementar Task 2 (ECE haircut) — edits pontuais
7. Implementar Task 3 (League pruning) — edits pontuais
8. Implementar Task 4 (MktEff=0 warning) — edits pontuais
9. Implementar Task 5 (Node.js 24) — edits pontuais
10. "Pre-mortem this change" — listar o que pode dar errado
11. py_compile em TODOS os arquivos Python modificados
12. Implementar Task 6 (registro e documentação)
13. Commit: "feat: ML retrain hardening — OddsVal/ECE haircuts + league pruning (#171)"
```
