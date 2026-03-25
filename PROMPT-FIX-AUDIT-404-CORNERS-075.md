# PROMPT — Fix Auditoria 404 + Verificação Corners (#075)

> **LEITURA OBRIGATÓRIA:** `CLAUDE.md` + `docs/REGRAS_CORRECAO_SISTEMA.md`
> Especialmente: #068-#070 (corners), #072-#073 (migração Mistral v3.0), #069 (auditoria batch)

---

## PROBLEMA 1 — Auditoria retorna HTTP 404 (CRÍTICO)

### Sintoma

Ao clicar "Auditar" no painel de um jogo, a seção "Resultado da Auditoria" mostra:

```
Confiança: 0%
Validação:
  Probabilidades  → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
  Lambdas         → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
  Expected Value  → UNKNOWN  → HTTP 404: {"detail":"Not Found"}
```

A **Análise AI funciona** (75% confiança, resumo, pontos-chave). Só a **validação/auditoria por jogo** está quebrada.

### Causa provável

Durante a migração Mistral v3.0 (#072, #073):
- A rota orphan `POST /ai/match-analysis` foi removida (#073 Passo 2, commit `2a8c896`)
- O novo router `ai_analysis.py` (#072, commit `2d26513`) tem 4 endpoints:
  - `GET /api/ai/match/{match_id}/analysis`
  - `GET /api/ai/match/{match_id}/analysis/legacy`
  - `POST /api/ai/match/{match_id}/analysis/regenerate`
  - `GET /api/ai/batch-analysis`
- **NENHUM endpoint de auditoria/validação por jogo foi criado no novo router**
- O frontend chama endpoints de validação que NÃO existem → 404

### Investigação (seguir 7 Regras)

```bash
# 1. Descobrir quais URLs o frontend chama quando clica "Auditar"
grep -rn "audit\|Auditar\|validate\|validacao\|probabilidades\|lambdas\|expected.value" \
  frontend/next/src/ --include="*.tsx" --include="*.ts" | head -30

# 2. Verificar se há rota de auditoria no backend
grep -rn "audit\|validate\|validacao" backend/routes/ --include="*.py" | head -20
grep -rn "audit\|validate" backend/main.py | head -20

# 3. Verificar o router AI atual
grep -n "def \|@router" backend/routes/ai_analysis.py | head -20

# 4. Verificar se existia endpoint de auditoria no código antigo (antes da remoção #073)
git log --all --oneline -- backend/routes/ai_analysis.py | head -10
git show HEAD~10:backend/routes/ai_analysis.py 2>/dev/null | grep -n "audit\|validate" | head -10
# OU verificar no main.py se havia rota de auditoria removida:
git log --all -p -- backend/main.py | grep -A5 "audit\|validate" | head -30

# 5. Verificar se existe módulo de auditoria por jogo separado
find backend/ -name "*audit*" -o -name "*validat*" | head -10
ls backend/ai/ | grep -i audit
```

### Fix (após investigação)

Existem 2 cenários possíveis:

**Cenário A — Endpoints de auditoria EXISTIAM e foram removidos acidentalmente:**

Recuperar do git history e adaptar ao novo router:
```bash
# Encontrar o commit que removeu
git log --all --diff-filter=D -- "*audit*" | head -10
# Restaurar
git show <commit>~1:backend/routes/<arquivo_de_audit>.py > /tmp/old_audit.py
```
Adaptar para o novo `ai_analysis.py` router, usando `_get_match_data()` e `_map_record_to_v3()` que já existem (#072).

**Cenário B — Endpoints de auditoria NUNCA existiam no router (estavam no main.py ou inline):**

Criar os endpoints no `backend/routes/ai_analysis.py`. O frontend espera 3 endpoints de validação:

```python
# Descobrir os paths exatos que o frontend chama (Passo 1 acima)
# Provavelmente algo como:
# GET /api/ai/match/{match_id}/audit
# GET /api/ai/match/{match_id}/validate/probabilidades
# GET /api/ai/match/{match_id}/validate/lambdas
# GET /api/ai/match/{match_id}/validate/ev

# Implementar no router:
@router.get("/match/{match_id}/audit")
async def audit_match(match_id: str):
    """
    Executa auditoria de validação para um jogo específico.
    Verifica: probabilidades (Poisson vs mercado), lambdas, expected value.
    """
    try:
        # 1. Buscar dados do jogo via pipeline real (#072)
        match_data = await _get_match_data(match_id)
        mapped = _map_record_to_v3(match_data)
        
        # 2. Validar probabilidades
        prob_validation = _validate_probabilities(mapped['stats'])
        
        # 3. Validar lambdas
        lambda_validation = _validate_lambdas(mapped['stats'])
        
        # 4. Validar expected value
        ev_validation = _validate_ev(mapped['stats'], mapped['odds'])
        
        # 5. Calcular confiança
        checks = [prob_validation, lambda_validation, ev_validation]
        passed = sum(1 for c in checks if c['status'] == 'OK')
        confidence = int((passed / len(checks)) * 100)
        
        return {
            'confidence': confidence,
            'validations': {
                'probabilidades': prob_validation,
                'lambdas': lambda_validation,
                'expected_value': ev_validation
            },
            'timestamp': datetime.now().strftime('%d/%m/%Y às %H:%M')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Funções de validação (implementar conforme lógica existente no projeto):**

```python
def _validate_probabilities(stats: dict) -> dict:
    """Verifica se probabilidades Poisson somam ~100% e são coerentes com lambdas"""
    prob_home = stats.get('prob_home', 0)
    prob_draw = stats.get('prob_draw', 0)
    prob_away = stats.get('prob_away', 0)
    total = prob_home + prob_draw + prob_away
    
    status = 'OK' if 95 <= total <= 105 else 'WARN'
    return {
        'status': status,
        'detail': f'Soma: {total:.1f}% (Home:{prob_home:.1f} Draw:{prob_draw:.1f} Away:{prob_away:.1f})',
        'values': {'home': prob_home, 'draw': prob_draw, 'away': prob_away, 'total': total}
    }

def _validate_lambdas(stats: dict) -> dict:
    """Verifica se lambdas são razoáveis (entre 0.3 e 4.0)"""
    lh = stats.get('lambda_home', 0)
    la = stats.get('lambda_away', 0)
    
    issues = []
    if not (0.3 <= lh <= 4.0): issues.append(f'lambda_home={lh:.3f} fora do range')
    if not (0.3 <= la <= 4.0): issues.append(f'lambda_away={la:.3f} fora do range')
    
    status = 'OK' if not issues else 'WARN'
    return {
        'status': status,
        'detail': '; '.join(issues) if issues else f'λH={lh:.3f} λA={la:.3f} (dentro do range)',
        'values': {'lambda_home': lh, 'lambda_away': la}
    }

def _validate_ev(stats: dict, odds: dict) -> dict:
    """Verifica se EVs calculados são coerentes (não absurdos)"""
    evs = {}
    for market in ['home', 'draw', 'away', 'over_25', 'btts_yes']:
        prob_key = f'prob_{market}' if market in ['home', 'draw', 'away'] else f'prob_{market}'
        prob = stats.get(prob_key, 0) / 100.0 if stats.get(prob_key, 0) > 1 else stats.get(prob_key, 0)
        odd = odds.get(market)
        if odd and prob > 0:
            ev = (prob * odd - 1) * 100
            evs[market] = round(ev, 1)
    
    absurd = {k: v for k, v in evs.items() if abs(v) > 50}
    status = 'OK' if not absurd else 'WARN'
    return {
        'status': status,
        'detail': f'EVs absurdos: {absurd}' if absurd else f'EVs dentro do range normal',
        'values': evs
    }
```

**IMPORTANTE:** Antes de implementar, verificar os paths EXATOS que o frontend chama (Passo 1). O schema de response deve corresponder ao que o componente `AuditReportCard` espera. Verificar:
```bash
grep -A20 "interface.*Audit\|type.*Audit\|Audit.*Result" \
  frontend/next/src/ -rn --include="*.tsx" --include="*.ts" | head -40
```

### Registrar no backend/main.py

Se o router ainda não está incluído:
```python
# Verificar se já está registrado
grep "ai_analysis" backend/main.py
# Se não, adicionar:
from backend.routes import ai_analysis
app.include_router(ai_analysis.router)
```

---

## PROBLEMA 2 — Verificação Corners com Jaguares de Córdoba vs Rionegro Águilas

### Contexto

O jogo Jaguares de Córdoba vs Rionegro Águilas está HT (intervalo), 0-0, com pick:
- `NEUTRO | Escanteios Under 9.5 | 63-65% | EV: +14.4%`

Este jogo é ideal para testar os fixes #068-#070 porque:
- Está ao vivo (HT)
- Tem prognóstico de Escanteios Under
- É da liga colombiana (Campeonato Colombiano) — verificar cobertura FootyStats

### Verificação

```bash
# 1. /live-scores retorna currentCorners para este jogo?
curl -s 'https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/live-scores' | python3 -c "
import json, sys
d = json.load(sys.stdin)
for m in d.get('matches', []):
    h = m.get('homeTeam', '?')
    if 'jaguar' in str(h).lower() or 'rionegro' in str(m.get('awayTeam','')).lower():
        print(f'FOUND: {h} vs {m.get(\"awayTeam\", \"?\")}')
        print(f'  status: {m.get(\"status\")}')
        print(f'  currentCorners: {m.get(\"currentCorners\", \"MISSING\")}')
        print(f'  homeCorners: {m.get(\"homeCorners\", m.get(\"home_corners\", \"MISSING\"))}')
        print(f'  awayCorners: {m.get(\"awayCorners\", m.get(\"away_corners\", \"MISSING\"))}')
        print(f'  minute: {m.get(\"minute\")}')
        break
else:
    print('NOT FOUND in live-scores')
    print('All teams:')
    for m in d.get('matches', [])[:20]:
        print(f'  {m.get(\"homeTeam\", \"?\")} vs {m.get(\"awayTeam\", \"?\")} [{m.get(\"status\")}]')
"

# 2. Se NOT FOUND, verificar via /fixtures
curl -s 'https://ipmywgv9d6.execute-api.us-east-1.amazonaws.com/fixtures?leagues=campeonato-colombiano' | python3 -c "
import json, sys
d = json.load(sys.stdin)
ms = d.get('matches', d.get('data', []))
for m in ms:
    h = m.get('homeTeam', {})
    name = h.get('name', h) if isinstance(h, dict) else str(h)
    if 'jaguar' in name.lower():
        cc = m.get('currentCorners', 'MISSING')
        st = m.get('status', '?')
        print(f'FOUND: {name} → currentCorners={cc}, status={st}')
        break
else:
    print('NOT FOUND')
"

# 3. Verificar CloudWatch para logs de corners deste jogo
MSYS_NO_PATHCONV=1 aws logs filter-log-events \
  --log-group-name "/aws/lambda/sportsbank-pro-backend" \
  --filter-pattern "Jaguares" \
  --start-time $(python3 -c "import time; print(int((time.time()-1800)*1000))") \
  --region us-east-1 \
  --limit 10 \
  --query 'events[].message' \
  --output text
```

### Resultado esperado

Se #068-#070 estão deployados:
- `currentCorners` deve ter valor numérico (ex: 3, 5, 7)
- A barra de progresso deve aparecer no painel com status SEGURO (verde) ou ATENÇÃO (laranja)
- O label deve mostrar "Limite: 9" (porque é Under)

Se `currentCorners = MISSING`:
- Verificar se o deploy Lambda contém o commit `799675a` (#070)
- Verificar se FootyStats retorna `team_a_corners` para a liga colombiana
- Aplicar o Cenário B ou C do prompt anterior (#075)

---

## ORDEM DE EXECUÇÃO

1. **PRIMEIRO** — Investigar Problema 1 (Auditoria 404) porque é o mais impactante
2. **SEGUNDO** — Verificar Problema 2 (Corners) com o jogo ao vivo
3. **TERCEIRO** — Deploy Lambda + Vercel se houver mudanças
4. **QUARTO** — Registrar no REGRAS

---

## REGISTRO NO REGRAS

### Para Problema 1:
```markdown
## 075 — Endpoints de auditoria por jogo retornam HTTP 404

**Data:** 2026-03-23
**Commit:** `[SHA]`
**Arquivos afetados:** `backend/routes/ai_analysis.py`, `frontend/next/src/[componente de audit]`
**Severidade:** Alta
**Status:** Corrigido

### Problema identificado

Botão "Auditar" no painel de jogo chama endpoints de validação (Probabilidades, Lambdas, Expected Value) que retornam HTTP 404. A análise AI funciona (75% confiança), mas a auditoria sempre mostra 0%.

### Causa raiz

Durante a migração Mistral v3.0 (#072, #073), a rota orphan POST /ai/match-analysis foi removida (#073 Passo 2) mas os endpoints de validação/auditoria por jogo nunca foram recriados no novo router ai_analysis.py.

### Correções aplicadas

1. [Camada 1 — Endpoints de validação criados no router]
2. [Camada 2 — Funções de validação (prob, lambda, EV)]
3. [Camada 3 — Schema de response alinhado com frontend AuditReportCard]

### Lição aprendida

Ao migrar routers, verificar não apenas os endpoints de CRUD principal mas também endpoints auxiliares (audit, validate, export) que dependem do mesmo serviço.
```

### Para Problema 2 (se houver fix):
```markdown
## 076 — [TÍTULO] (corners — se necessário)
...
```

---

## COMMIT

```bash
git add backend/routes/ai_analysis.py docs/REGRAS_CORRECAO_SISTEMA.md [outros arquivos]
git commit -m "fix: audit validation endpoints return 404 — recreate in v3.0 router (#075)

Refs: #072, #073 (migration removed audit routes)
Adds: /match/{id}/audit endpoint with prob/lambda/EV validation
Defense: 3 validation functions + proper error handling"
git push origin main

# Deploy
python scripts/deploy_lambda.py
cd frontend/next && npx vercel --prod  # se frontend alterado
```
