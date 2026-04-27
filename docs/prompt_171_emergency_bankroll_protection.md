# Prompt #171 — INCIDENTE CRÍTICO: Proteção de Banca e Correção de Pipeline

> **Severidade:** P0 — Perda de 50% da banca em 24h
> **Uso:** Copiar o conteúdo abaixo (a partir de "---") e colar no Claude Code como prompt.

---

## LEITURA OBRIGATÓRIA ANTES DE QUALQUER AÇÃO

Leia estes arquivos NA ÍNTEGRA antes de tocar em qualquer código. Se não ler tudo, vai piorar o problema:

1. `backend/cron_handler.py` linhas 625-676 — auto-apply de correções (AQUI ESTÁ O PROBLEMA PRINCIPAL)
2. `backend/audit.py` linhas 780-815 — ADJUSTMENT_LIMITS e validate_adjustment()
3. `backend/services/deterministic_audit.py` linhas 305-379 — geração de correções automáticas
4. `backend/services/bankroll_engine.py` linhas 20-60 e 195-226 — Kelly + VIÁVEL floor
5. `backend/ml/predictor.py` linhas 192-232 — gates de ativação ML
6. `backend/ml/train_model.py` linhas 27-34 (thresholds), 64-112 (ECE), 160-191 (MktEff), 585-599 (OddsVal)
7. `scripts/retrain_validate.py` linhas 148-177 — classificação de ligas
8. `docs/REGRAS_ATIVAS.md` — regras permanentes do sistema
9. `CLAUDE.md` seções "Workflow de Validação" e "Proibições"

## ROLE

Atue como Agente Sênior de Engenharia de Dados e Ciência de Dados que VAI PERDER DINHEIRO PESSOAL se o diagnóstico ou a correção estiverem errados. Cada linha de código que você alterar afeta dinheiro real. Cada suposição não verificada é uma aposta cega.

**Mindset obrigatório:**
- "From the perspective of someone who will lose money if this is wrong"
- "First principles" — não confie em suposições; trace o dado do início ao fim
- "Invert the problem" — o que precisaria dar certo para a banca NÃO cair 50%?
- "What would make this fail" — para cada fix, pergunte como ele pode piorar as coisas

## CONTEXTO DO INCIDENTE

### O que aconteceu
A banca do SportsBankZU foi reduzida em **50% em 24 horas** por prognósticos incorretos.

### Timeline conhecida
- **26/04 05:05:** Auditoria cron executou. Banner: "Acuracia: 71.0% — 2 correcao(oes) aplicada(s) (lambda_ou, lambda_ou) — NECESSITA_AJUSTE"
- **26/04-27/04:** Dashboard apresentou erros de carregamento (timeout em requests multi-liga — fix de batch size já aplicado mas NÃO deployado ainda)
- **27/04:** Usuário reporta 50% de perda na banca

### Alterações recentes no sistema (últimas 2 semanas)
- **#166:** Odds ingestion v2 — novo loop de bookmakers, per-league priority (feature flag ODDS_INGESTION_V2)
- **#170-A:** NB2 alpha per-league para corners (feature flag CORNERS_ALPHA_CALIBRATED)
- **#168:** Fix BatchAuditPanel crash (null guards)
- **#169:** Strict Contract + First Principles no CLAUDE.md

## DIAGNÓSTICO PRÉ-INVESTIGAÇÃO (HIPÓTESES RANQUEADAS)

### HIPÓTESE #1 — AUTO-CORREÇÃO CASCATEANTE (90% provável) — **REFUTADA EM 2026-04-19**

> **Status pós-forense:** REFUTADA. Forense via `/api/debug/corrections-audit` mostrou apenas 3 correções `cron_auto`, todas escritas em `parameter_name="lambda_ou"` — chave que NENHUM consumer lê (consumers usam `lambda_multiplier`). Eram dead writes. O bug de validação existia, mas não foi o vetor da perda.

**Cadeia de falha identificada:**

```
Auditoria cron detecta Brier > 0.25
    │
    ▼
deterministic_audit.py gera correção lambda_ou
    │ suggested_deflation = max(0.80, 1.0 - delta*2)
    │ confidence = 80 (se total >= 50 picks)
    │
    ▼
cron_handler.py auto-aplica se confidence >= 80
    │
    ▼
validate_adjustment("lambda_deflation", "lambda_ou", old, new)
    │
    ▼ ⚠️ BUG CONFIRMADO:
    │ ADJUSTMENT_LIMITS NÃO TEM ENTRADA PARA "lambda_deflation"
    │ Fallback para "THRESHOLD" → {min: 0.40, max: 0.95, max_delta: 0.10}
    │ Lambda deflation de 0.80 PASSA na validação (0.40 ≤ 0.80 ≤ 0.95)
    │ Mas deflation normal de 1.0 seria REJEITADA (1.0 > 0.95) ← INVERTIDO!
    │
    ▼
Lambda corrections table atualizada LIVE
    │
    ▼
TODAS as previsões O/U usam lambda deflacionado em 20%
    │
    ▼
Previsões sistematicamente enviesadas → picks errados → perda
    │
    ▼
Próxima auditoria vê Brier PIOR → gera OUTRA correção
    │
    ▼
CICLO DE FEEDBACK POSITIVO (cascata destrutiva)
```

**Evidência concreta no código:**
- `audit.py` linha 780-789: `ADJUSTMENT_LIMITS` NÃO contém "lambda_deflation"
- `audit.py` linha 803: fallback para "THRESHOLD" → range [0.40, 0.95]
- `deterministic_audit.py` linha 326: `suggested_deflation = max(0.80, 1.0 - delta*2)`
- Se Brier = 0.28: delta=0.06, deflation=0.88 → PASSA validação (0.88 ≤ 0.95)
- Se Brier = 0.30: delta=0.08, deflation=0.84 → PASSA validação
- `cron_handler.py` linha 633: threshold confidence >= 80 → auto-aplica com ≥50 picks
- `cron_handler.py` linha 651: `log_correction()` grava em DB → LIVE imediatamente

**O bug:** As limits de validação para lambda_deflation estão usando os ranges de THRESHOLD (probabilidades 0.40-0.95), quando deveriam usar ranges de deflation (0.80-1.20 por exemplo). Resultado: deflações agressivas PASSAM, deflações normais (1.0) FALHAM.

### HIPÓTESE #2 — VIÁVEL FLOOR MULTIPLICANDO EXPOSIÇÃO (70% provável, agravante)

**Cadeia:**
- VIÁVEL floor garante 0.5% da banca por pick MESMO quando Kelly retorna zero
- Com 60+ picks/dia × 0.5% = 30% de exposição no piso
- Se a maioria perde (porque lambdas estão deflacionados incorretamente) → -15% a -20%/dia fácil
- Cap diário de 30% (`MAX_STAKE_PER_DAY_PCT`) pode NÃO estar sendo enforced (verificar call chain)

### HIPÓTESE #3 — ODDSVAL NEGATIVO UNIVERSAL (60% provável, agravante)

**Do ML Retrain Run #15:**
- OddsVal negativo em TODAS as 22 ligas
- Kelly calcula edge = `prob_model - (1/odd)`. Se prob_model é sistematicamente overconfidente, Kelly superaloca
- ECE de 0.07-0.11 confirma: modelo diz 65% quando realidade é 55% → Kelly aloca 3× mais do que deveria

### HIPÓTESE #4 — COMBINAÇÃO DE FLAGS ATIVAS (40% provável)

- ODDS_INGESTION_V2=true → pode estar puxando odds de bookmakers menos confiáveis
- CORNERS_ALPHA_CALIBRATED=true → pode estar aplicando alphas incorretos
- Ambos ativados junto com auto-correção = múltiplas variáveis mudando simultaneamente

### HIPÓTESE #5 — CORNERS_ALPHA_CALIBRATED (#170-A) — **CONFIRMADA EM 2026-04-19**

> **Status pós-forense:** CONFIRMADA como causa raiz primária. NB2 α calibrado per-league
> rebaixou α de 0.15 (default) para valores próximos de 0 em várias ligas. Quando α→0, NB2
> degenera em Poisson, com cauda mais leve e probabilidades de mercados de cauda (Over 10.5
> escanteios, etc.) infladas. Kelly superalocou sistematicamente nesses mercados.

## CAUSA RAIZ CONFIRMADA (forense de 2026-04-19)

**Vetor:** Ativação de `CORNERS_ALPHA_CALIBRATED=true` (#170-A) em produção.

**Dados forenses (`/api/debug/pick-outcomes`, janelas pré/pós ativação):**

| Métrica | Pré ativação (7d) | Pós ativação (7d) | Δ |
|---------|-------------------|-------------------|---|
| Picks de escanteios / dia | 30,4 | 88,0 | **2,89×** |
| Stake médio em escanteios / dia (% banca) | 1,20 % | 7,11 % | **5,93×** |
| Hit rate Escanteios Over 10.5 | 100 % (n=4) | 33 % (n=15) | colapso de cauda |

**Mecanismo da cascata:**
1. `#170-A` calibra α NB2 per-league. Em várias ligas, α calibrado ≈ 0 (Poisson).
2. Cauda mais leve → probabilidade implícita de Over alto fica acima do mercado.
3. Kelly vê edge fantasma e dispara picks de cauda em volume (88/dia vs 30/dia).
4. VIÁVEL floor (0,5 %) garantiu stake mesmo em cells com Kelly ~0 → exposição diária dispara.
5. Mercado pune; hit rate de cauda cai de 100 % para 33 %.
6. Sem circuit breaker de perda diária, o sistema continua apostando o dia inteiro.

**Por que H1 era plausível mas errada:** O bug de validação existia (lambda_deflation caía
no fallback de THRESHOLD), mas o cron escrevia em chave que ninguém consumia. O dano foi
feito por #170-A, não pela cascata de auto-correção.

**Mitigações ativadas em FASE 0 (já em produção):**
- `CORNERS_ALPHA_CALIBRATED=false` (kill switch primário — reverte para α=0.15 fixo)
- `VIAVEL_FLOOR_PCT=0` (corta o piso forçado)
- `AUTO_APPLY_CONFIDENCE_MIN=101` (defesa secundária — desliga auto-apply de qualquer correção)
- `lambda_deflation` adicionado a `ADJUSTMENT_LIMITS` (fecha o bug de validação)

**Defesas adicionadas em FASE 2 (esta entrega — não deployadas ainda):**
- ECE haircut (até −25 % quando ECE ≥ 0,12)
- OddsVal haircut (até −30 % quando OddsVal ≤ −0,02)
- Cap por família de mercado (5 % corners/cards, 10 % goals/1x2 por dia)
- Daily loss circuit breaker (15 %)

## RESTRIÇÕES INVIOLÁVEIS

- **NÃO faça deploy de nenhuma mudança sem ANTES confirmar o diagnóstico com dados reais**
- **NÃO altere múltiplos parâmetros simultaneamente** — cada fix deve ser isolável e reversível
- **NÃO confie em suposições** — todo valor deve ser verificado contra o DB real
- **NÃO reescreva arquivos inteiros** — edits pontuais com diff preview obrigatório
- **NÃO altere a lógica de treinamento ML** — escopo é gates, validação e bankroll

## SEQUÊNCIA DE EXECUÇÃO OBRIGATÓRIA

### FASE 0 — PARAR A HEMORRAGIA (executar ANTES de qualquer investigação)

**Tempo estimado: 5 minutos. Prioridade: ABSOLUTA.**

#### Task 0A — Circuit Breaker de Auto-Correção

**Objetivo:** Impedir que o cron aplique novas correções automáticas até investigação completa.

**Implementação:** Em `cron_handler.py`, linha 633, alterar threshold de confidence:

```python
# ANTES (linha 633):
if confidence >= 80:

# DEPOIS:
# #171: Emergency circuit breaker — disable auto-apply until investigation complete.
# Manual corrections still possible via API. Revert to 80 after root cause fixed.
AUTO_APPLY_CONFIDENCE_THRESHOLD = int(os.getenv("AUTO_APPLY_CONFIDENCE_MIN", "101"))
if confidence >= AUTO_APPLY_CONFIDENCE_THRESHOLD:
```

**Efeito:** Com threshold=101, NENHUMA correção passa (confidence máx possível é 80). Env var permite reativar sem redeploy.

#### Task 0B — Reduzir VIÁVEL Floor

**Objetivo:** Eliminar o piso de 0.5% que força apostas quando Kelly diz "não apostar".

**Implementação:** Em `bankroll_engine.py`, alterar:

```python
# ANTES (linha 41):
VIAVEL_FLOOR_PCT = 0.005  # 0.5% da banca

# DEPOIS:
# #171: Reduce floor to 0.1% during investigation. If Kelly returns 0,
# forcing a bet is dangerous when model calibration is suspect.
VIAVEL_FLOOR_PCT = float(os.getenv("VIAVEL_FLOOR_PCT", "0.001"))  # 0.1% default, configurable
```

#### Task 0C — Adicionar LAMBDA_DEFLATION aos ADJUSTMENT_LIMITS

**Objetivo:** Corrigir o bug CONFIRMADO onde lambda_deflation usa limits de THRESHOLD.

**Implementação:** Em `audit.py`, após linha 788, adicionar:

```python
    "BTTS_MULTIPLIER": {"min": 0.70, "max": 1.40, "max_delta": 0.15},
    # #171: Lambda deflation has its own range — NOT a probability threshold!
    # Deflation multipliers should be 0.80-1.20 (not 0.40-0.95).
    # max_delta=0.08 prevents corrections larger than 8% per cycle.
    "lambda_deflation": {"min": 0.80, "max": 1.20, "max_delta": 0.08},
    "lambda_calibration": {"min": 0.10, "max": 0.90, "max_delta": 0.10},
}
```

**ATENÇÃO:** Isso NÃO desfaz correções já aplicadas. Só previne novas correções erradas.

### FASE 1 — FORENSE: CONFIRMAR O QUE ACONTECEU (executar DEPOIS da Fase 0)

**Tempo estimado: 15-30 minutos. Prioridade: ALTA.**

#### Task 1A — Auditar Correções Aplicadas

**Objetivo:** Descobrir exatamente quais correções o cron aplicou e com quais valores.

```python
# Criar script temporário: scripts/audit_corrections_171.py
"""
Forensic script — list all auto-applied corrections from the last 7 days.
Run: python -m scripts.audit_corrections_171
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.audit import AuditDB

db = AuditDB()
corrections = db.get_recent_corrections(days=7)

print(f"\n{'='*80}")
print(f"CORREÇÕES DOS ÚLTIMOS 7 DIAS ({len(corrections)} encontradas)")
print(f"{'='*80}\n")

for c in corrections:
    print(f"  [{c['created_at']}] {c['parameter_name']}: {c['old_value']} → {c['new_value']}")
    print(f"    type={c['correction_type']} | confidence={c.get('audit_confidence')} | applied_by={c['applied_by']}")
    print(f"    reason: {c.get('reason', 'N/A')}")
    print()

# Check current lambda_corrections for ALL leagues
from backend.modeling.lambda_calculator import get_lambda_corrections
from backend.config.leagues_config import LEAGUES_CONFIG

print(f"\n{'='*80}")
print("LAMBDA CORRECTIONS ATIVAS POR LIGA")
print(f"{'='*80}\n")

for lc in LEAGUES_CONFIG:
    lid = lc if isinstance(lc, str) else lc.get("id", "?")
    corrs = get_lambda_corrections(lid)
    if corrs:
        deflation_ou = corrs.get("lambda_deflation_ou", {}).get("value")
        deflation_btts = corrs.get("lambda_deflation_btts", {}).get("value")
        safe = corrs.get("safe_enabled", {}).get("value")
        print(f"  {lid}: defl_ou={deflation_ou} | defl_btts={deflation_btts} | safe={safe}")
```

**AÇÃO OBRIGATÓRIA:** Executar este script antes de qualquer correção adicional. O output revela se a hipótese #1 é confirmada.

#### Task 1B — Reverter Correções Tóxicas

**Objetivo:** Se a forense confirmar correções de lambda_ou aplicadas pelo cron, reverter para valores de antes da cascata.

**Implementação:**
1. Identificar o valor ANTERIOR (antes do cron de 26/04) via log de correções
2. Aplicar reversão via `save_calibration()` (o mesmo mecanismo que o calibrator usa)
3. **NÃO usar delete** — gravar nova entrada com valor original para manter audit trail

```python
# Se a forense mostrar deflation_ou = 0.84 aplicado pelo cron:
# Reverter para 1.0 (ou para o valor calibrado pelo league_calibrator)
from backend.services.league_calibrator import save_calibration
save_calibration(league_id, {"lambda_deflation_ou": valor_correto}, source="manual_revert_171")
```

#### Task 1C — Verificar Estado Real das Feature Flags

```bash
# Verificar quais flags estão ativas em produção:
MSYS_NO_PATHCONV=1 aws lambda get-function-configuration \
  --function-name sportsbank-pro-backend \
  --region us-east-1 \
  --query 'Environment.Variables' \
  | python -m json.tool | grep -E "ODDS_INGESTION|CORNERS_ALPHA|AUTO_APPLY|VIAVEL"
```

Se ODDS_INGESTION_V2=true E CORNERS_ALPHA_CALIBRATED=true, considerar desativar uma de cada vez para isolar variáveis.

### FASE 2 — CORREÇÕES ESTRUTURAIS (executar DEPOIS da Fase 1 confirmada)

**Tempo estimado: 30-45 minutos. Prioridade: ALTA.**

#### Task 2A — Daily Loss Circuit Breaker

**Problema:** Não existe mecanismo que PARA de apostar quando a banca cai X% no dia. O cap de 30% (`MAX_STAKE_PER_DAY_PCT`) limita a exposição mas não as perdas.

**Objetivo:** Adicionar circuit breaker que bloqueia novos picks quando perda diária acumulada excede threshold.

**Implementação:** Em `bankroll_engine.py`, adicionar:

```python
# #171: Daily loss circuit breaker — halt all new picks when cumulative
# daily loss exceeds threshold. Client-side enforcement (backend provides signal).
DAILY_LOSS_CIRCUIT_BREAKER_PCT = float(os.getenv("DAILY_LOSS_CIRCUIT_BREAKER", "0.15"))  # 15% default
```

**NOTA CRÍTICA:** A banca é client-side (frontend). O backend NÃO sabe a banca real. Duas opções:
- (a) Frontend implementa o circuit breaker (bloqueia UI quando perda > threshold)
- (b) Backend estima perda baseada em picks emitidos + resultados conhecidos via post_match_diagnostic

Recomendar opção (a) como fix imediato + (b) como TODO futuro.

**Frontend implementation (AIReviewDashboard.tsx ou componente dedicado):**
```typescript
// #171: Daily loss circuit breaker
const DAILY_LOSS_LIMIT = 0.15; // 15% of starting daily bankroll

// Track daily P&L client-side (localStorage or state)
// When accumulated loss > DAILY_LOSS_LIMIT:
// - Show warning banner: "Circuit breaker ativado: perda diária de X%"
// - Disable stake buttons
// - Log to analytics
```

#### Task 2B — OddsVal Gate no Bankroll Engine

**Problema:** ML Retrain Run #15 mostra OddsVal negativo em 22/22 ligas. Kelly calcula edge com probabilidades menos calibradas que o mercado.

**Implementação:** Em `bankroll_engine.py`, adicionar haircut proporcional ao OddsVal negativo.

```python
# #171: OddsVal Haircut — when ML is less calibrated than market
HAIRCUT_NEGATIVE_ODDSVAL_MAX = 0.30   # Max 30% reduction
ODDSVAL_HAIRCUT_FLOOR = -0.02         # OddsVal at which max haircut applies
```

**Cálculo:** Interpolação linear de 0% (OddsVal=0) a 30% (OddsVal≤-0.02).

**Propagação:** A função de stake precisa receber `league_meta` com os campos do metadata ML. Investigar o call chain:
1. Quem chama `compute_stake()` em `bankroll_engine.py`?
2. O caller tem `league_id`?
3. O caller pode carregar metadata ML?
4. Se não, adicionar parâmetro `league_meta: Optional[dict] = None`

**Impacto retroativo (Run #15 ML_ACTIVE):**
- La Liga: -0.0125 → haircut 18.8%
- Super Lig: -0.0145 → haircut 21.8%
- Eredivisie: -0.0040 → haircut 6.0%
- Primeira Liga: -0.0055 → haircut 8.3%
- Premiership: -0.0014 → haircut 2.1%

#### Task 2C — ECE Haircut no Bankroll Engine

**Problema:** ECE 0.07-0.11 = overconfidence de 7-11 pontos percentuais. Kelly calcula edge baseado em probabilidades infladas.

**Implementação:**

```python
# #171: ECE Haircut — high ECE = overconfident probabilities
ECE_HAIRCUT_THRESHOLD = 0.06     # No haircut below this
ECE_HAIRCUT_MAX = 0.25           # Max 25% reduction
ECE_HAIRCUT_CEILING = 0.12       # ECE at which max applies
```

**Interação com OddsVal:** Haircuts são MULTIPLICATIVOS. Para Eredivisie (pior caso):
- OddsVal: ×0.94, ECE: ×0.79 → total ×0.743 (redução ~26%)
- Isso é CORRETO dado que Eredivisie tem ECE=0.11 + OddsVal=-0.004

**Sanity check:** Se haircut combinado reduzir stake abaixo do VIÁVEL floor (0.1%), o floor prevalece. Não gera stake negativo.

#### Task 2D — Desacoplar Auditoria de Auto-Correção

**Problema:** A auditoria E a auto-correção rodam no MESMO cron job. Não há gate humano entre "detectar problema" e "aplicar correção".

**Objetivo:** Auditoria gera recomendações → ARMAZENA em tabela de "pending_corrections" → humano aprova via endpoint ou CLI → só então aplica.

**Implementação:**

1. Em `cron_handler.py`, substituir auto-apply por pending queue:

```python
# ANTES (linhas 625-676): auto-apply direto
# DEPOIS:
    pending = []
    if model_evaluation and model_evaluation.get("recommended_corrections"):
        for corr in model_evaluation["recommended_corrections"]:
            confidence = corr.get("confidence", 0)
            if confidence >= int(os.getenv("AUTO_APPLY_CONFIDENCE_MIN", "101")):
                # Auto-apply path (disabled by default via env var)
                # ... existing auto-apply code ...
            else:
                # Queue for human approval
                audit_db.queue_pending_correction(
                    correction=corr,
                    source="cron_audit",
                    audit_date=datetime.now().isoformat(),
                )
                pending.append(corr["parameter"])
    
    if pending:
        logger.info(f"Queued {len(pending)} corrections for approval: {pending}")
```

2. Novo método em `audit.py`: `queue_pending_correction()` e `approve_correction(id)`
3. Novo endpoint em `backend/routes/audit_status.py`: `POST /api/audit/approve-correction/{id}`

**NOTA:** Esse é o fix MAIS IMPORTANTE de longo prazo. O auto-apply com confidence >= 80 é o mecanismo que permitiu a cascata destrutiva.

### FASE 3 — ML RETRAIN HARDENING (executar DEPOIS da Fase 2)

**Tempo estimado: 20-30 minutos. Prioridade: MÉDIA.**

#### Task 3A — League Pruning no Retrain

**Objetivo:** Excluir ligas que NUNCA ativam do pipeline de retrain ML (não do pipeline principal).

```python
# scripts/retrain_validate.py, topo do arquivo:
ML_RETRAIN_EXCLUDED = {
    "a-league",           # Brier 0.658, Acc 38.1% — worst in 5+ runs
    "primera-division",   # Brier 0.652, Acc 40.9% — DEACTIVATED chronically
}
```

**Critério de re-inclusão:** Backtesting manual mostra Brier < 0.62 por 2 runs consecutivos.

#### Task 3B — MktEff=0 Investigation

**Problema:** Serie A e A-League com MktEff=0 sugere dados de odds corrompidos, não mercado ineficiente.

**Ação:** Em `retrain_validate.py`, adicionar warning:
```python
if mkt_eff is not None and mkt_eff == 0.0:
    logger.warning(f"[retrain] {lid}: MktEff=0.0 — implied_odds features likely missing/corrupted")
    entry["mkt_eff_warning"] = "ZERO_SUSPECT_DATA"
```

#### Task 3C — GitHub Actions Node.js 24

**Ação:** Atualizar actions versions em AMBOS os workflows:
- `.github/workflows/ml-retrain-validate.yml`
- `.github/workflows/ml-retrain-promote.yml`

```yaml
# Verificar versões disponíveis ANTES de alterar:
# gh api repos/actions/checkout/releases/latest --jq '.tag_name'
# gh api repos/actions/cache/releases/latest --jq '.tag_name'
# gh api repos/actions/upload-artifact/releases/latest --jq '.tag_name'
# gh api repos/actions/setup-python/releases/latest --jq '.tag_name'
```

Remover `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` após atualização.

### FASE 4 — REGISTRO E DOCUMENTAÇÃO

#### Task 4A — REGISTRO_CORRECOES.md

```markdown
## 171 — INCIDENTE CRÍTICO: Proteção de Banca

**Data:** 2026-04-27
**Arquivos afetados:** cron_handler.py, audit.py, bankroll_engine.py, retrain_validate.py, workflows
**Severidade:** Crítica (P0 — 50% perda de banca)
**Status:** Implementado

### Problema identificado
Banca reduzida em 50% em 24h por prognósticos sistematicamente errados.

### Causa raiz
1. ADJUSTMENT_LIMITS em audit.py não continha entrada para "lambda_deflation", causando
   fallback para "THRESHOLD" (range 0.40-0.95) que valida deflações agressivas e rejeita
   valores normais (1.0 > 0.95). Bug de validação permitiu auto-correções cascateantes.
2. Sem circuit breaker de perda diária.
3. VIÁVEL floor de 0.5% forçava apostas quando Kelly retornava zero.
4. OddsVal negativo em 22/22 ligas + ECE alto gerando edge fantasma no Kelly.

### Correções aplicadas
- Camada 1: Circuit breaker de auto-correção (env var AUTO_APPLY_CONFIDENCE_MIN=101)
- Camada 2: LAMBDA_DEFLATION entry nos ADJUSTMENT_LIMITS (range 0.80-1.20)
- Camada 3: Redução do VIÁVEL floor (0.5% → 0.1%)
- Camada 4: OddsVal haircut no bankroll (max 30%)
- Camada 5: ECE haircut no bankroll (max 25%)
- Camada 6: Pending corrections queue (desacoplamento audit → apply)
- Camada 7: Daily loss circuit breaker (15%)
- Camada 8: League pruning no retrain (A-League, Primera División)

### Lição aprendida
Auto-correção sem gate humano é uma arma apontada para si mesmo. O sistema deve RECOMENDAR
correções e ESPERAR aprovação humana. A validação de ranges deve ter entries explícitas para
cada tipo de correção — fallback para "THRESHOLD" causou a cascata.
```

#### Task 4B — REGRAS_ATIVAS.md

```markdown
#171 — Proteção de Banca e Auto-Correção
- Auto-apply de correções DESABILITADO por padrão (env AUTO_APPLY_CONFIDENCE_MIN=101)
- ADJUSTMENT_LIMITS DEVE ter entrada explícita para cada correction_type
- VIÁVEL floor configurável via env (VIAVEL_FLOOR_PCT, default 0.001)
- OddsVal negativo → haircut proporcional no bankroll (max 30%)
- ECE > 0.06 → haircut proporcional no bankroll (max 25%)
- A-League e Primera División excluídas do retrain ML (review trimestral)
- TODA nova correção automática passa por pending queue + aprovação humana
```

#### Task 4C — INDICE_REGRAS.md
Adicionar entrada para #171.

## SAÍDA ESPERADA

### 1. Steelman (máx 200 palavras)
Defenda por que desabilitar auto-correção é melhor que melhorar a validação. E por que haircuts graduais são melhores que gates binários.

### 2. Diff de Código

| Arquivo | Alteração | Fase |
|---------|-----------|------|
| `backend/cron_handler.py` | Circuit breaker env var + pending queue | 0A, 2D |
| `backend/audit.py` | LAMBDA_DEFLATION limits + queue_pending_correction() | 0C, 2D |
| `backend/services/bankroll_engine.py` | VIÁVEL floor env + OddsVal haircut + ECE haircut | 0B, 2B, 2C |
| `backend/ml/predictor.py` | MktEff=0 warning | 3B |
| `scripts/retrain_validate.py` | ML_RETRAIN_EXCLUDED + MktEff=0 warning + "excluded" status | 3A, 3B |
| `scripts/audit_corrections_171.py` | Script forense (novo, temporário) | 1A |
| `.github/workflows/ml-retrain-validate.yml` | Node.js 24 actions | 3C |
| `.github/workflows/ml-retrain-promote.yml` | Node.js 24 actions | 3C |
| `docs/REGISTRO_CORRECOES.md` | Entrada #171 | 4A |
| `docs/REGRAS_ATIVAS.md` | Regra #171 | 4B |
| `docs/INDICE_REGRAS.md` | Entrada #171 | 4C |

### 3. Kill Switches

| Switch | Mecanismo | Efeito |
|--------|-----------|--------|
| AUTO_APPLY_CONFIDENCE_MIN=101 | Env var Lambda | Bloqueia auto-apply de correções |
| VIAVEL_FLOOR_PCT=0 | Env var Lambda | Elimina piso de aposta forçada |
| DAILY_LOSS_CIRCUIT_BREAKER=0.15 | Env var / frontend | Para apostas após -15% no dia |
| ODDS_INGESTION_V2=false | Env var Lambda | Reverte para odds pipeline v1 |
| CORNERS_ALPHA_CALIBRATED=false | Env var Lambda | Reverte para alpha fixo 0.15 |

### 4. Plano de Rollout

```
FASE 0 — EMERGÊNCIA (deploy imediato)
├── 0A: Circuit breaker auto-correção → deploy Lambda
├── 0B: Reduzir VIÁVEL floor → deploy Lambda
└── 0C: Fix ADJUSTMENT_LIMITS → deploy Lambda

FASE 1 — FORENSE (30 min após Fase 0)
├── 1A: Rodar script audit_corrections_171.py → analisar output
├── 1B: Reverter correções tóxicas (se confirmadas)
└── 1C: Verificar feature flags ativas

FASE 2 — CORREÇÕES ESTRUTURAIS (após Fase 1 confirmada)
├── 2A: Daily loss circuit breaker
├── 2B: OddsVal haircut no bankroll
├── 2C: ECE haircut no bankroll
└── 2D: Pending corrections queue

FASE 3 — HARDENING (próxima semana)
├── 3A: League pruning
├── 3B: MktEff=0 investigation
└── 3C: GitHub Actions Node.js 24

FASE 4 — DOCUMENTAÇÃO (junto com cada fase)
```

## SEQUÊNCIA DE EXECUÇÃO NO CLAUDE CODE

```
1. LER TODOS os arquivos obrigatórios (NÃO pular)
2. "Diff only" — preview de CADA mudança antes de editar
3. Implementar FASE 0 (3 tasks de emergência)
4. py_compile em TODOS os arquivos modificados
5. "Pre-mortem this change" — o que pode piorar?
6. Deploy Lambda (Fase 0 apenas)
7. Executar script forense (Task 1A)
8. Analisar output e decidir reversões (Task 1B)
9. Verificar flags (Task 1C)
10. SOMENTE DEPOIS: Implementar Fase 2
11. py_compile novamente
12. Deploy Lambda (Fase 2)
13. Implementar Fase 3 (pode ser próximo dia)
14. Registrar #171 em REGISTRO, REGRAS, INDICE
15. Commit: "fix(P0): bankroll protection — circuit breakers + validation fix (#171)"
```

## ANTI-PATTERNS A EVITAR

1. **NÃO implemente tudo de uma vez.** Deploy Fase 0 primeiro, valide, depois Fase 2.
2. **NÃO confie no script forense sem validar manualmente.** Cruze com CloudWatch logs.
3. **NÃO assuma que reverter correções resolve tudo.** As perdas já ocorreram; o fix é prevenir recorrência.
4. **NÃO adicione complexidade desnecessária.** Circuit breaker via env var é simples e reversível. Pending queue é mais complexa mas essencial para longo prazo.
5. **NÃO esqueça de testar os kill switches.** Cada env var deve ser testada com value=true E value=false antes de confiar nela em produção.
