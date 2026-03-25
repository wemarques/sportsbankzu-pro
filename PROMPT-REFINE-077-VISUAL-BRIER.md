# PROMPT — Refinamento visual CornerProgressBar + Fix Brier per-league (#077)

> **LEITURA OBRIGATÓRIA:** `CLAUDE.md` + `docs/REGRAS_CORRECAO_SISTEMA.md` (especialmente #068, #069, #076)
> **CONTEXTO:** Corners e auditoria FUNCIONAM (#075, #076 corrigidos). Este prompt é de REFINAMENTO visual e correção de dados.

---

## TAREFA 1 — Refinamento visual do CornerProgressBar (DESIGN)

### Estado atual (screenshot de referência)

A barra de escanteios ("ESCANTEIOS Limite: 8" com badge verde "11" na ponta) está funcional mas visualmente desalinhada:
- Mais larga que a barra "Confiança da Análise" abaixo dela
- Ocupa 100% da largura do container sem margem lateral
- Esteticamente "pesada" comparada aos outros elementos do painel (badges de prognóstico, tabs)
- O badge "11" na ponta direita está grudado na borda

### Diretrizes de design — tom: REFINADO / PREMIUM

O SportsBank Pro V3.7 usa estética **dark premium com acentos cirúrgicos**: fundo #141414, borders #1f1f1f, texto #e0e0e0, acentos gold #ffd700 (odds), verde neon #00ff88 (positivo), vermelho #ef4444 (negativo/danger). Os elementos do painel lateral são **compactos e densos** — badges pequenos, tipografia 10-12px, espaçamentos apertados. A barra de confiança tem um visual minimalista (track fino com glow sutil).

### Especificação visual

**A barra de escanteios deve ser mais estreita e elegante que a de confiança.** Referência: se a confiança tem ~6px de altura, a de escanteios deve ter ~4-5px. A ideia é que ela funcione como **indicador complementar**, não como elemento principal.

#### Investigação (antes de editar)

```bash
# 1. Medir a barra de confiança — track height, padding, margins
grep -A15 "confidence-bar-container\|confidence-bar\b" \
  frontend/next/src/styles/match-detail-card.css

# 2. Medir a barra de escanteios — track, fill, badge, root
grep -A15 "cpb-root\|cpb-track\|cpb-fill\|cpb-badge\|cpb-header" \
  frontend/next/src/styles/match-detail-card.css

# 3. Ver o container pai de ambas
grep -B10 "CornerProgressBar\|confidence-bar" \
  frontend/next/src/components/MatchDetailCard.tsx | head -40

# 4. Ver o componente atual completo
cat frontend/next/src/components/CornerProgressBar.tsx
```

#### Alterações CSS (`match-detail-card.css`)

Aplicar este refinamento ao `.cpb-*`:

```css
/* ── CornerProgressBar — refinado para ficar mais estreito que confiança ── */

.cpb-root {
  /* Margem lateral: cria respiro visual e fica mais estreito que o container pai */
  margin: 0 8px;
  padding: 10px 12px;
  /* Borda sutil com tint da cor de status (mantém a lógica JS existente) */
  border-radius: 6px;
  /* Tipografia compacta */
  font-size: 11px;
}

.cpb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.cpb-header .cpb-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: #888;
}

.cpb-header .cpb-target {
  font-size: 10px;
  color: #666;
  font-weight: 500;
}

/* Track mais fino que a confiança — elegante, não dominante */
.cpb-track {
  position: relative;
  height: 4px;           /* confiança usa ~6-8px; este é menor */
  background: #1a1a1a;
  border-radius: 2px;
  overflow: visible;      /* permite badge sair do track */
  border: 1px solid #222;
}

.cpb-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s ease-out, background 0.4s;
  /* Glow sutil — não exagerado */
  box-shadow: 0 0 6px rgba(0, 255, 136, 0.2);
}

/* Over: verde → atingiu meta */
.cpb-fill--hit {
  background: linear-gradient(90deg, #059669, #10b981);
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.3);
}

/* Under: vermelho → ultrapassou limite */
.cpb-fill--danger {
  background: linear-gradient(90deg, #dc2626, #ef4444);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
}

/* Progresso normal (nem hit nem danger) */
.cpb-fill:not(.cpb-fill--hit):not(.cpb-fill--danger) {
  background: linear-gradient(90deg, #0d9488cc, #14b8a6);
}

/* Badge na ponta da barra — compacto, sem ser dominante */
.cpb-badge {
  position: absolute;
  right: -1px;
  top: 50%;
  transform: translate(50%, -50%);
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  color: #000;
  background: #14b8a6;
  border: 2px solid #141414;  /* borda da cor do fundo cria "recorte" */
  box-shadow: 0 0 6px rgba(20, 184, 166, 0.3);
  transition: background 0.4s, box-shadow 0.4s;
  font-variant-numeric: tabular-nums;
  z-index: 2;
}

.cpb-badge--hit {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
}

.cpb-badge--danger {
  background: #ef4444;
  color: #fff;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
}

/* Placeholder quando corners ainda não chegaram */
.cpb-root.cpb-placeholder {
  display: flex !important;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin: 0 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px dashed #2a2a2a;
  border-radius: 6px;
  font-size: 10px;
  color: #555;
}

.cpb-placeholder .cpb-label {
  color: #666;
  font-weight: 600;
}

.cpb-placeholder .cpb-loading {
  color: #444;
  font-style: italic;
  animation: cpb-pulse 2s ease-in-out infinite;
}

@keyframes cpb-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
```

#### Alterações no componente (`CornerProgressBar.tsx`)

Verificar se a estrutura HTML atual corresponde às classes CSS acima. O componente deve ter esta hierarquia:

```tsx
<div className="cpb-root">
  <div className="cpb-header">
    <span className="cpb-label">ESCANTEIOS</span>
    <span className="cpb-target">Limite: {targetCorners}</span>
  </div>
  <div className="cpb-track">
    <div 
      className={`cpb-fill ${fillClass}`}
      style={{ width: `${pct}%` }}
    >
      <span className={`cpb-badge ${badgeClass}`}>
        {currentCorners}
      </span>
    </div>
  </div>
</div>
```

Se a estrutura atual for diferente, adaptar as classes CSS para corresponder. **NÃO reescrever o componente inteiro** — apenas ajustar classes e estilos.

#### Alterações no container pai (`MatchDetailCard.tsx`)

Verificar se o `CornerProgressBar` está dentro de um container com padding excessivo. Se estiver, o `margin: 0 8px` do `.cpb-root` cuida do respiro visual. Se o container pai JÁ tem padding, pode ser necessário ajustar para evitar duplo espaçamento:

```bash
# Verificar o wrapper do CornerProgressBar
grep -B5 -A2 "CornerProgressBar" frontend/next/src/components/MatchDetailCard.tsx
```

Se estiver dentro de um `<div style={{ padding: '...' }}>`, o `margin: 0 8px` pode não ser suficiente. Nesse caso, remover o padding do wrapper e usar apenas o margin do `.cpb-root`.

#### Resultado visual esperado

```
┌─────────────────────────────────────────────────┐
│  Analise AI (MISTRAL)  PRO V3.7            ∧   │
│  ▌PROGNOSTICO                                   │
│  [NEUTRO-Q] Escanteios Under 8.5  78-80% ...   │
│  ↑ EV+  ◆ Edge  ● Alta Prob  ◷ Início Temp.    │
│                                                  │
│    ┌─────────────────────────────────────────┐   │  ← margin 8px cada lado
│    │ ESCANTEIOS                  Limite: 8   │   │
│    │ ████████████████████████████████████ ⓫  │   │  ← track 4px, badge 20px
│    └─────────────────────────────────────────┘   │
│                                                  │
│  [NEUTRO] Under 2.5 gols  73-75%  Odd: 1.38 ... │
│                                                  │
│  Confiança da Análise                    70%     │
│  ████████████████████████████████████████████    │  ← track 6-8px, full width
│                                                  │
└─────────────────────────────────────────────────┘
```

A barra de escanteios tem **margem lateral de 8px**, **track de 4px** e **tipografia 10px** — sutilmente menor e mais recuada que a de confiança. O efeito é que a confiança é o indicador PRINCIPAL e os escanteios são COMPLEMENTAR.

---

## TAREFA 2 — Fix Brier Score idêntico por liga na auditoria (PERSISTENTE)

### Sintoma

Dois relatórios de auditoria consecutivos (23/03/2026):

**Relatório 1 (5 jogos, 23:14):**
```
GLOBAL:                 Brier: 0.3006 | SAFE: 0.0%
Campeonato Colombiano:  Brier: 0.3006 | SAFE: 80% (4/5)   ← IDÊNTICO
Primera Division:       Brier: 0.3006 | SAFE: 75% (3/4)   ← IDÊNTICO
```

**Relatório 2 (4 jogos, 23:13):**
```
GLOBAL:                 Brier: 0.3533 | SAFE: 0.0%
Campeonato Colombiano:  Brier: 0.3533 | SAFE: 80% (4/5)   ← IDÊNTICO
Primera Division:       Brier: 0.3533 | SAFE: 50% (1/2)   ← IDÊNTICO
```

O fix #069 (commit `832c0a8`) deveria ter resolvido com `league_metrics` dict. Dois sub-bugs:

**Bug A:** Brier per-league usa o valor global em vez do calculado por liga
**Bug B:** "SAFE" per-league mostra 80% mas global mostra 0% (label incorreto — conta todos os picks como SAFE)

### Investigação

```bash
# 1. Verificar se commit 832c0a8 está no Lambda deployado
git log --oneline -20 | grep -i "brier\|069\|audit"
MSYS_NO_PATHCONV=1 aws lambda get-function-configuration \
  --function-name sportsbank-pro-backend \
  --region us-east-1 \
  --query 'LastModified' --output text

# 2. Verificar se league_metrics existe no cron_handler
grep -n "league_metrics" backend/cron_handler.py | head -10

# 3. Se existe, verificar como Brier per-league é calculado
# HIPÓTESE PRINCIPAL: usa avg_brier (global) em vez de league_metrics[league]["brier_scores"]
grep -B3 -A15 "league_accuracy_text\|league_metrics.*brier" backend/cron_handler.py | head -50

# 4. Verificar se o prompt template recebe dados per-league
grep -n "league_accuracy\|brier.*league\|ACURACIA POR LIGA" backend/ai/prompt_templates.py | head -10

# 5. Verificar se a Mistral está recebendo dados reais ou inventando
# Rodar auditoria manualmente e ver o prompt enviado
grep -B2 -A5 "avg_brier\|league_accuracy" backend/cron_handler.py | head -30
```

### Cenários e fixes

**Cenário 1 — Deploy desatualizado:**
```bash
python scripts/deploy_lambda.py
```
Depois re-rodar a auditoria e verificar se Brier varia por liga.

**Cenário 2 — league_metrics acumula mas calcula com lista global:**
```python
# BUGADO (provável):
for league, metrics in league_metrics.items():
    league_brier = avg_brier  # ← USA O GLOBAL!
    text += f"    Brier: {league_brier:.4f}\n"

# CORRETO:
for league, metrics in league_metrics.items():
    lb_list = metrics.get("brier_scores", [])
    league_brier = sum(lb_list) / len(lb_list) if lb_list else None
    text += f"    Brier: {league_brier:.4f}\n" if league_brier else "    Brier: N/A\n"
```

**Cenário 3 — Dados corretos no prompt mas Mistral repete o global:**
Se a investigação mostra que `league_accuracy_text` tem valores DIFERENTES por liga, mas o relatório final mostra valores iguais → a Mistral está ignorando os dados per-league.

**Fix:** Não pedir à Mistral para formatar a tabela. Gerar o texto da tabela per-league DIRETAMENTE no `cron_handler.py` e injetar como texto pronto no relatório, não como input para a Mistral reformatar:

```python
# Em vez de pedir à Mistral para gerar a tabela:
audit_text += "\n────────────────────────────────────────────────────────\n"
audit_text += "LIGAS ANALISADAS\n"
audit_text += "────────────────────────────────────────────────────────\n"
for league, metrics in league_metrics.items():
    lb_list = metrics.get("brier_scores", [])
    league_brier = sum(lb_list) / len(lb_list) if lb_list else None
    league_correct = metrics.get("correct", 0)
    league_total = metrics.get("total", 0)
    league_pct = round(league_correct / league_total * 100, 1) if league_total > 0 else 0
    
    brier_str = f"Brier: {league_brier:.4f}" if league_brier else "Brier: N/A"
    audit_text += f"  ⚽ {league}\n"
    audit_text += f"    Jogos: {metrics.get('match_count', 0)} | {brier_str} | Acurácia: {league_pct}% ({league_correct}/{league_total})\n"
```

**Bug B — SAFE label:**

```bash
# Verificar o que per-league conta como "SAFE"
grep -B3 -A10 "safe_correct\|safe_total" backend/cron_handler.py | head -40
```

```python
# Fix: quando circuit breaker ativo (0 picks SAFE), mostrar label correto
if league_safe_total > 0:
    safe_str = f"SAFE: {safe_pct}% ({league_safe_correct}/{league_safe_total})"
else:
    # Circuit breaker #043 ativo — mostrar acurácia geral, não "SAFE"
    safe_str = f"Acurácia: {league_pct}% ({league_correct}/{league_total})"
```

### Teste pós-fix

1. Rodar auditoria com pelo menos 2 ligas diferentes
2. Verificar que Brier per-league é DIFERENTE para cada liga
3. Verificar que "SAFE" per-league mostra "Acurácia" quando circuit breaker ativo
4. Comparar com global para sanity check (Brier global = média ponderada dos per-league)

---

## ORDEM DE EXECUÇÃO

1. **Tarefa 1 (visual)** — CSS + verificação de estrutura HTML → deploy Vercel
2. **Tarefa 2 (Brier)** — investigar deploy → fix cálculo/label → deploy Lambda
3. Registrar no REGRAS

---

## REGISTRO NO REGRAS

```markdown
## 077 — Refinamento visual CornerProgressBar + Brier per-league persistente

**Data:** 2026-03-24
**Commit:** `[SHA]`
**Arquivos afetados:** `frontend/next/src/styles/match-detail-card.css`, `frontend/next/src/components/CornerProgressBar.tsx`, `backend/cron_handler.py`
**Severidade:** Baixa (visual), Alta (Brier)
**Status:** Corrigido

### Problema identificado

1. CornerProgressBar mais larga que a barra de confiança — desproporcional no painel lateral
2. Brier Score idêntico para todas as ligas no relatório de auditoria (fix #069 não efetivo)
3. Label "SAFE" per-league contava todos os picks quando circuit breaker #043 ativo

### Correções aplicadas

**Visual (frontend):**
- `.cpb-root`: margin 0 8px (recuada das bordas), border-radius 6px
- `.cpb-track`: height 4px (vs 6-8px da confiança), overflow visible para badge
- `.cpb-badge`: 20px circular, border 2px #141414 (recorte no track), tabular-nums
- `.cpb-placeholder`: border dashed, animação pulse sutil
- Resultado: barra complementar, mais estreita e elegante que a de confiança

**Auditoria (backend):**
- [PREENCHER: causa encontrada e fix aplicado]
- Label SAFE per-league alterado para "Acurácia" quando circuit breaker ativo

### Lição aprendida

- Elementos complementares devem ser visualmente SUBORDINADOS ao elemento principal. A barra de escanteios é complementar; a confiança é principal. Track height, margin e tipografia menores comunicam hierarquia visual.
- Dados per-league no relatório devem ser calculados E formatados no código, não delegados à Mistral. LLMs tendem a repetir valores globais quando recebem dados per-league como input numérico.
```

---

## COMMIT

```bash
git add frontend/next/src/styles/match-detail-card.css \
       frontend/next/src/components/CornerProgressBar.tsx \
       backend/cron_handler.py \
       docs/REGRAS_CORRECAO_SISTEMA.md
git commit -m "refine: CornerProgressBar narrower + Brier per-league calc (#077)

Visual: track 4px, margin 8px, badge 20px — subordinate to confidence bar
Audit: Brier per-league uses league-specific scores (was global repeat)
Audit: SAFE label → 'Acurácia' when circuit breaker active
Refs: #068, #069, #076"
git push origin main

cd frontend/next && npx vercel --prod  # visual
python scripts/deploy_lambda.py        # Brier (se alterado)
```
