# PROMPT — Corrigir Display de EV no Dashboard e MatchDetailCard

## PROBLEMA

O prognóstico do sistema mostra "EV+ >= 1.64" para TODOS os mercados, incluindo mercados com EV negativo. Exemplo real:

- Dashboard mostra: `1X2 Home 51-53% EV+ >= 1.64` (parece EV positivo)
- Aba Mistral mostra: `1X2 Home 51-53% Odd: 1.64 EV: -12.6%` (EV é negativo)

O "EV+ >= 1.64" significa "a odd mínima para EV ser positivo é 1.64", mas o usuário entende como "o EV é positivo". Isso é enganoso quando a odd real é menor que a odd mínima e o EV é de fato negativo.

O tipo `MatchPrediction` já tem o campo `ev` (número real) disponível. O dashboard simplesmente não o usa — mostra `odd_minima` com prefixo fixo "EV+".

## ARQUIVOS A MODIFICAR

1. `frontend/next/src/app/dashboard/page.tsx` — linha ~2232 (prognóstico no match row)
2. Opcionalmente: CSS para cores do EV no match row

---

## CORREÇÃO

### Arquivo: `frontend/next/src/app/dashboard/page.tsx`

Localizar a linha ~2232:

```tsx
{/* ANTES — sempre mostra EV+ independente do sinal real */}
<span className="st-prediction-odd">EV+ &gt;= {pred.odd_minima != null ? pred.odd_minima.toFixed(2) : "-"}</span>
```

Substituir por display inteligente que usa `pred.ev` quando disponível, e fallback para `odd_minima`:

```tsx
{/* EV display — show real EV% when available, fallback to odd_minima */}
{pred.ev != null ? (
  <span
    className="st-prediction-odd"
    style={{
      color: pred.ev >= 0.05 ? "#00df82" : pred.ev >= 0 ? "#ffaa44" : "#ff5555",
    }}
    title={`EV: ${(pred.ev * 100).toFixed(1)}% | Odd mín: ${pred.odd_minima?.toFixed(2) ?? "-"}`}
  >
    EV: {pred.ev >= 0 ? "+" : ""}{(pred.ev * 100).toFixed(1)}%
  </span>
) : pred.odd_minima != null ? (
  <span className="st-prediction-odd" style={{ opacity: 0.7 }} title="Odd mínima para EV positivo">
    Odd mín: {pred.odd_minima.toFixed(2)}
  </span>
) : null}
```

Isso renderiza:
- **EV positivo (>= 5%)**: `EV: +13.6%` em verde (#00df82)
- **EV marginal (0% a 5%)**: `EV: +1.2%` em amarelo (#ffaa44)
- **EV negativo**: `EV: -12.6%` em vermelho (#ff5555)
- **Sem EV disponível**: `Odd mín: 1.64` em cinza (fallback)
- **Tooltip**: mostra ambos os valores (EV real + odd mínima)

---

## VERIFICAR COMPATIBILIDADE

O campo `pred.ev` vem do tipo `MatchPrediction` em `leagues.ts`:
```typescript
ev?: number | null;
```

É preenchido pelo backend no pipeline v2 (`ev_classification.py` → `MarketOutput.compute_ev()`). Para mercados processados pelo pipeline legado (`selecionar_mercados_jogo`), `ev` pode ser `null` — nesse caso o fallback para `odd_minima` mantém compatibilidade.

---

## VALIDAÇÃO

```bash
cd frontend/next && npm run build
```

Verificar no dashboard:
- Grêmio vs Vitória: 1X2 Home deve mostrar `EV: -12.6%` em vermelho (não mais "EV+ >= 1.64")
- BTTS SIM deve mostrar `EV: +39.0%` em verde
- Escanteios Over 9.5 deve mostrar `EV: +4.8%` em amarelo
- DC 1X deve mostrar `EV: -12.3%` em vermelho

Commit:
```
fix(ui): show real EV% with correct sign and color instead of always "EV+"

- Replace "EV+ >= odd_minima" with actual EV percentage from pipeline v2
- Color-coded: green (EV >= 5%), yellow (0-5%), red (negative)
- Fallback to "Odd mín: X.XX" when EV not available (legacy pipeline)
- Tooltip shows both EV% and odd_minima for reference
```

Push:
```bash
git push origin main
```
