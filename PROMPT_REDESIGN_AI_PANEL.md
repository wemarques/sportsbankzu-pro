# PROMPT — Redesign do Painel de Análise AI (MISTRAL) no Frontend

## CONTEXTO

O painel de Análise AI no MatchDetailCard está com layout poluído. Os reason codes aparecem como texto corrido sem separação visual (`NO ODDS AVAILABLEHIGH CALIBRATED PROBEARLY SEASON FALLBACK`), ilegível para o usuário. O design precisa ser refinado para ficar limpo, legível e responsivo em mobile/tablet/laptop/monitor 27".

## ESCOPO

Refatorar a seção de AI Analysis + Prognóstico dentro de `frontend/next/src/components/MatchDetailCard.tsx` e seu CSS em `frontend/next/src/styles/match-detail-card.css`. NÃO alterar o backend. Apenas mudar como os dados já existentes são exibidos.

## ARQUIVOS A MODIFICAR

1. `frontend/next/src/lib/leagues.ts` — adicionar `SUSPICIOUS_EV` ao tipo `ReasonCode`
2. `frontend/next/src/components/MatchDetailCard.tsx` — refatorar seção de prognóstico + AI analysis
3. `frontend/next/src/styles/match-detail-card.css` — adicionar/atualizar estilos

---

## 1. ADICIONAR SUSPICIOUS_EV AO TIPO

Arquivo: `frontend/next/src/lib/leagues.ts`

Adicionar `"SUSPICIOUS_EV"` ao tipo `ReasonCode` (~linha 143):

```typescript
export type ReasonCode =
  | "LOW_DATA_QUALITY"
  | "NO_ODDS_AVAILABLE"
  | "NEGATIVE_EV"
  | "INSUFFICIENT_EDGE"
  | "EARLY_SEASON_FALLBACK"
  | "HIGH_MARKET_CORRELATION"
  | "LINEUP_UNCERTAINTY"
  | "HIGH_PREDICTION_RISK"
  | "REGIME_BLOCKED"
  | "POSITIVE_EV"
  | "STRONG_EDGE"
  | "HIGH_CALIBRATED_PROB"
  | "ODDS_TOO_LOW"
  | "STABLE_MARKET"
  | "VOLATILE_MARKET"
  | "COVERAGE_INSUFFICIENT"
  | "SUSPICIOUS_EV";
```

---

## 2. REASON CODES — MAPEAMENTO VISUAL

Criar constante de mapeamento dentro do MatchDetailCard.tsx (ou arquivo separado de constantes). Cada reason code deve ter: ícone, label em português, cor e tipo semântico.

```typescript
const REASON_META: Record<string, { icon: string; label: string; color: string; type: "positive" | "info" | "warning" | "danger" | "neutral" }> = {
  POSITIVE_EV:          { icon: "↑", label: "EV+",           color: "#00ff88", type: "positive" },
  STRONG_EDGE:          { icon: "◆", label: "Edge",          color: "#00ff88", type: "positive" },
  HIGH_CALIBRATED_PROB: { icon: "●", label: "Alta Prob",     color: "#4a9eff", type: "info" },
  EARLY_SEASON_FALLBACK:{ icon: "◷", label: "Início Temp.",  color: "#666",    type: "neutral" },
  NO_ODDS_AVAILABLE:    { icon: "○", label: "Sem Odds",      color: "#ff6b35", type: "warning" },
  SUSPICIOUS_EV:        { icon: "⚠", label: "EV Suspeito",   color: "#ff4444", type: "danger" },
  LOW_DATA_QUALITY:     { icon: "▽", label: "Dados Fraco",   color: "#ff6b35", type: "warning" },
  NEGATIVE_EV:          { icon: "↓", label: "EV−",           color: "#ff4444", type: "danger" },
  INSUFFICIENT_EDGE:    { icon: "−", label: "Sem Edge",      color: "#666",    type: "neutral" },
  HIGH_PREDICTION_RISK: { icon: "◇", label: "Risco Alto",    color: "#ff6b35", type: "warning" },
  STABLE_MARKET:        { icon: "=", label: "Estável",       color: "#4a9eff", type: "info" },
  VOLATILE_MARKET:      { icon: "~", label: "Volátil",       color: "#ff6b35", type: "warning" },
  COVERAGE_INSUFFICIENT:{ icon: "▽", label: "Cobertura Baixa",color: "#ff6b35", type: "warning" },
  REGIME_BLOCKED:       { icon: "✕", label: "Bloqueado",     color: "#ff4444", type: "danger" },
  ODDS_TOO_LOW:         { icon: "↓", label: "Odd Baixa",     color: "#666",    type: "neutral" },
  HIGH_MARKET_CORRELATION:{ icon: "⊞", label: "Correlação",  color: "#666",    type: "neutral" },
  LINEUP_UNCERTAINTY:   { icon: "?", label: "Escalação ?",   color: "#ff6b35", type: "warning" },
};
```

---

## 3. REFATORAR RENDERIZAÇÃO DOS REASON CODES

Substituir o bloco atual de reason codes (~linhas 711-731 do MatchDetailCard.tsx):

```tsx
{/* ANTES — texto corrido cinza sem separação */}
{pred.reason_codes.map((rc, rcIdx) => (
  <span key={rcIdx} style={{
    fontSize: "0.65em",
    padding: "1px 6px",
    borderRadius: 4,
    background: "rgba(255,255,255,0.06)",
    color: "rgba(255,255,255,0.5)",
  }}>
    {rc.replace(/_/g, " ")}
  </span>
))}
```

Substituir por tags coloridas com ícone e label:

```tsx
{pred.reason_codes && pred.reason_codes.length > 0 && (
  <div className="mdc-reason-tags">
    {pred.reason_codes.map((rc, rcIdx) => {
      const meta = REASON_META[rc] || { icon: "•", label: rc.replace(/_/g, " "), color: "#666", type: "neutral" };
      return (
        <span
          key={rcIdx}
          className={`mdc-reason-tag mdc-reason-tag--${meta.type}`}
          title={rc}
        >
          <span className="mdc-reason-tag__icon">{meta.icon}</span>
          {meta.label}
        </span>
      );
    })}
  </div>
)}
```

---

## 4. EV SUSPEITO — VISUAL DE TACHADO

No bloco onde o EV é exibido, quando `pred.reason_codes` contém `"SUSPICIOUS_EV"`, o valor do EV deve aparecer com text-decoration: line-through e opacidade reduzida:

```tsx
{pred.ev != null && (
  <span
    className="mdc-prognostico__ev"
    style={{
      color: pred.reason_codes?.includes("SUSPICIOUS_EV") ? "#ff4444" : "#ffd700",
      textDecoration: pred.reason_codes?.includes("SUSPICIOUS_EV") ? "line-through" : "none",
      opacity: pred.reason_codes?.includes("SUSPICIOUS_EV") ? 0.6 : 1,
    }}
    title={pred.reason_codes?.includes("SUSPICIOUS_EV") ? "EV suspeito — provável divergência entre fonte de probabilidade e odds" : `EV: ${(pred.ev * 100).toFixed(1)}%`}
  >
    EV: {(pred.ev * 100).toFixed(1)}%
  </span>
)}
```

---

## 5. ADICIONAR TAB "GLOSSÁRIO"

No bloco de AI Analysis (após Resumo e Pontos-Chave, ~linha 754+), adicionar uma terceira aba "Glossário" com tabela de 2 colunas (Termo | O que significa).

Criar constante GLOSSARY dentro do componente ou em arquivo separado:

```typescript
const GLOSSARY = [
  { term: "Edge", description: "Margem de vantagem — diferença entre a probabilidade do modelo e a probabilidade implícita na odd" },
  { term: "EV (Expected Value)", description: "Valor esperado do retorno — quanto se espera ganhar ou perder por unidade apostada a longo prazo" },
  { term: "EV+", description: "Retorno positivo esperado — a aposta tem valor matemático favorável" },
  { term: "EV Suspeito", description: "Retorno calculado fora do normal (acima de 40%) — indica provável divergência entre fontes de dados" },
  { term: "Strong Edge", description: "Margem de vantagem forte — o modelo identifica diferença significativa entre sua probabilidade e a da casa" },
  { term: "Alta Prob", description: "Probabilidade alta de acerto segundo o modelo (acima do threshold da classificação)" },
  { term: "Sem Odds", description: "Sem cotação disponível nas casas de apostas para este mercado" },
  { term: "Início Temp.", description: "Dados de início de temporada — calibração usa fallback por amostra insuficiente de jogos" },
  { term: "Fair (Odd Justa)", description: "Cotação justa calculada pelo modelo — se a odd da casa for maior, há valor na aposta" },
  { term: "Odd (Cotação)", description: "Cotação oferecida pela casa de apostas — quanto você recebe por cada R$1 apostado" },
  { term: "SAFE", description: "Classificação máxima — probabilidade alta, EV positivo, dados confiáveis, edge suficiente" },
  { term: "NEUTRO-Q", description: "Neutro qualificado — elegível para combinadas e duplas, tem EV positivo mas não atinge SAFE" },
  { term: "NEUTRO", description: "Mercado identificado mas sem valor suficiente ou sem odds disponíveis" },
  { term: "RESTRITO", description: "Liga com dados limitados ou modelo ML não ativo — prognósticos com cautela" },
  { term: "Overround", description: "Margem da casa de apostas — a soma das probabilidades implícitas excede 100% (tipicamente 5-6%)" },
  { term: "Lambda (λ)", description: "Média de gols esperados por time — base do cálculo Poisson para probabilidades de placares" },
  { term: "xG (Expected Goals)", description: "Gols esperados — métrica que mede a qualidade das finalizações, não apenas a quantidade" },
  { term: "Clean Sheet", description: "Quando o time não sofre gols durante a partida" },
  { term: "BTTS", description: "Both Teams To Score — mercado onde ambas as equipes precisam marcar pelo menos um gol" },
  { term: "FTS%", description: "Failed To Score — percentual de jogos em que o time não marcou gols" },
  { term: "DC 1X", description: "Dupla Chance Casa ou Empate — aposta que cobre dois dos três resultados possíveis" },
  { term: "Under / Over", description: "Menos / Mais — mercado de gols ou escanteios acima ou abaixo de uma linha (ex: Under 2.5 = menos de 3 gols)" },
  { term: "Poisson", description: "Modelo estatístico que calcula a probabilidade de cada placar baseado na média de gols esperados" },
  { term: "Calibração", description: "Ajuste das probabilidades do modelo para reflitam a realidade histórica" },
  { term: "Chaos Detectado", description: "Jogo identificado como imprevisível — alto desvio entre métricas, resultado difícil de modelar" },
];
```

A seção de AI Analysis atualmente tem sub-tabs implícitas (Resumo, Pontos-Chave). Transformar em tabs explícitas:

```tsx
const [aiTab, setAiTab] = useState<"resumo" | "pontos" | "glossario">("resumo");
```

Renderizar as 3 tabs com underline verde na tab ativa:

```tsx
<div className="mdc-ai-tabs">
  <button className={`mdc-ai-tab ${aiTab === "resumo" ? "mdc-ai-tab--active" : ""}`} onClick={() => setAiTab("resumo")}>Resumo</button>
  <button className={`mdc-ai-tab ${aiTab === "pontos" ? "mdc-ai-tab--active" : ""}`} onClick={() => setAiTab("pontos")}>Pontos-Chave</button>
  <button className={`mdc-ai-tab ${aiTab === "glossario" ? "mdc-ai-tab--active" : ""}`} onClick={() => setAiTab("glossario")}>Glossário</button>
</div>
```

Tab Glossário — campo de busca + tabela de 2 colunas:

```tsx
{aiTab === "glossario" && (
  <div className="mdc-glossary">
    <input
      type="text"
      placeholder="Buscar termo..."
      value={glossarySearch}
      onChange={(e) => setGlossarySearch(e.target.value)}
      className="mdc-glossary__search"
    />
    <div className="mdc-glossary__header">
      <span className="mdc-glossary__col-term">Termo</span>
      <span className="mdc-glossary__col-desc">O que significa</span>
    </div>
    <div className="mdc-glossary__list">
      {GLOSSARY
        .filter(g => g.term.toLowerCase().includes(glossarySearch.toLowerCase()) || g.description.toLowerCase().includes(glossarySearch.toLowerCase()))
        .map((item, i) => (
          <div key={i} className="mdc-glossary__row">
            <span className="mdc-glossary__term">{item.term}</span>
            <span className="mdc-glossary__desc">{item.description}</span>
          </div>
        ))}
    </div>
  </div>
)}
```

---

## 6. CSS — ESTILOS NOVOS

Adicionar em `frontend/next/src/styles/match-detail-card.css`:

```css
/* ─── Reason Code Tags ─── */
.mdc-reason-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
  padding-left: 8px;
}

.mdc-reason-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.6em;
  font-weight: 500;
  white-space: nowrap;
  line-height: 1.4;
}

.mdc-reason-tag__icon {
  font-size: 0.85em;
}

.mdc-reason-tag--positive { color: #00ff88; background: rgba(0,255,136,0.08); }
.mdc-reason-tag--info     { color: #4a9eff; background: rgba(74,158,255,0.06); }
.mdc-reason-tag--warning  { color: #ff6b35; background: rgba(255,107,53,0.08); }
.mdc-reason-tag--danger   { color: #ff4444; background: rgba(255,68,68,0.12); }
.mdc-reason-tag--neutral  { color: #666;    background: rgba(255,255,255,0.05); }

/* ─── AI Tabs ─── */
.mdc-ai-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.mdc-ai-tab {
  flex: 1;
  padding: 10px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-text-muted, #555);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.mdc-ai-tab:hover {
  color: var(--color-text-secondary, #999);
}

.mdc-ai-tab--active {
  color: var(--color-text-primary, #e0e0e0);
  border-bottom-color: var(--color-primary, #00ff88);
}

/* ─── Glossary ─── */
.mdc-glossary__search {
  width: 100%;
  padding: 8px 10px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 5px;
  color: #ccc;
  font-size: 0.75rem;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
  margin-bottom: 12px;
}

.mdc-glossary__search:focus {
  border-color: rgba(0,255,136,0.3);
}

.mdc-glossary__header {
  display: flex;
  gap: 12px;
  padding: 6px 0 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 2px;
}

.mdc-glossary__col-term,
.mdc-glossary__col-desc {
  font-size: 0.6rem;
  font-weight: 700;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mdc-glossary__col-term { flex: 0 0 150px; }
.mdc-glossary__col-desc { flex: 1; }

.mdc-glossary__list {
  max-height: 320px;
  overflow-y: auto;
}

.mdc-glossary__row {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  align-items: flex-start;
}

.mdc-glossary__term {
  flex: 0 0 150px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #e0e0e0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
}

.mdc-glossary__desc {
  flex: 1;
  font-size: 0.75rem;
  color: #888;
  line-height: 1.5;
}

/* ─── Responsive ─── */

/* Tablet */
@media (max-width: 768px) {
  .mdc-glossary__col-term,
  .mdc-glossary__term {
    flex: 0 0 120px;
  }
  
  .mdc-reason-tags {
    padding-left: 4px;
  }
}

/* Mobile */
@media (max-width: 480px) {
  .mdc-glossary__header {
    display: none; /* stacked layout, no header needed */
  }

  .mdc-glossary__row {
    flex-direction: column;
    gap: 2px;
  }

  .mdc-glossary__term {
    flex: none;
    font-size: 0.7rem;
  }

  .mdc-glossary__desc {
    font-size: 0.7rem;
  }

  .mdc-glossary__list {
    max-height: 400px;
  }

  .mdc-reason-tags {
    padding-left: 0;
  }

  .mdc-reason-tag {
    font-size: 0.55em;
  }

  .mdc-ai-tab {
    padding: 9px 8px;
    font-size: 0.7rem;
  }

  .mdc-prognostico__item {
    flex-wrap: wrap;
  }

  .mdc-prognostico__market {
    font-size: 0.7rem;
  }

  .mdc-prognostico__prob,
  .mdc-prognostico__ev {
    font-size: 0.65rem;
  }
}

/* Large monitor (27"+) */
@media (min-width: 1440px) {
  .mdc-glossary__col-term,
  .mdc-glossary__term {
    flex: 0 0 180px;
  }

  .mdc-glossary__desc {
    font-size: 0.8rem;
  }

  .mdc-reason-tag {
    font-size: 0.65em;
    padding: 3px 8px;
  }
}
```

---

## 7. ESTADO NO COMPONENTE

Adicionar ao estado do MatchDetailCard:

```typescript
const [aiTab, setAiTab] = useState<"resumo" | "pontos" | "glossario">("resumo");
const [glossarySearch, setGlossarySearch] = useState("");
```

---

## VALIDAÇÃO

Após implementar:

```bash
cd frontend/next && npm run build
```

Verificar em 4 tamanhos de tela:
- **Mobile (375px)**: reason tags legíveis, glossário em coluna única, tabs não cortam
- **Tablet (768px)**: layout intermediário, glossário com termos 120px
- **Laptop (1024px)**: layout completo, termos 150px
- **Monitor 27" (2560px)**: termos 180px, tags ligeiramente maiores

Fazer commit:

```
feat(ui): redesign AI Analysis panel — reason code tags, glossary tab, responsive layout

- Reason codes: color-coded tags with icons (green=positive, blue=info, orange=warning, red=danger)
- SUSPICIOUS_EV: shown with strikethrough on EV value
- New Glossário tab with search and 25 terms explaining all system terminology
- Responsive: mobile (stacked), tablet, laptop, 27" monitor
- CSS-only responsive via media queries
```

Depois push:
```bash
git push origin main
```

---

## REGRAS

- NÃO alterar backend, APIs, nem lógica de cálculo
- NÃO alterar o formato dos dados vindos do backend
- MANTER toda a funcionalidade existente (prognóstico, confidence bar, audit)
- APENAS mudar a apresentação visual dos dados já existentes
- Os reason codes já vêm do backend como array de strings — só precisa renderizar melhor
- Se `npm run build` falhar, corrigir antes de commitar
