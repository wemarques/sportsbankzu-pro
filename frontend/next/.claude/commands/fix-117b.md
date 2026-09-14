# Correção #117b — 4 bugs no DestaquesDoDia.tsx

## Contexto

O componente `DestaquesDoDia.tsx` foi implantado na #117 mas 4 itens da spec ficaram de fora. Esta correção NÃO altera layout nem pipeline — são ajustes cirúrgicos no componente existente.

## Pré-requisitos

```bash
cat CLAUDE.md
cat frontend/next/src/components/DestaquesDoDia.tsx | head -50
```

---

## BUG 1 — Presets de bankroll somam ao invés de definir

**Comportamento atual:** Clicar +100 soma ao valor existente (500 + 100 = 600).
**Comportamento esperado:** Clicar 100 DEFINE o bankroll como 100 (substitui o valor atual).

```bash
grep -n "addBank\|setBankroll\|preset\|onClick.*amount\|onClick.*bank" frontend/next/src/components/DestaquesDoDia.tsx
```

**Fix:** A função de preset deve ser `setBankroll(amount)`, NÃO `setBankroll(prev => prev + amount)`.

```tsx
// ERRADO (soma)
onClick={() => setBankroll(prev => prev + amount)}

// CORRETO (define)
onClick={() => setBankroll(amount)}
```

**Labels dos botões:** Remover o "+" dos labels — devem ser `50, 100, 250, 500, 1000` (sem sinal de soma, já que não somam).

```tsx
// ERRADO
<button>+{amount}</button>

// CORRETO
<button>{amount}</button>
```

O input de digitação (`onChange`) continua DEFININDO o valor normalmente:
```tsx
onChange={(e) => {
  const val = parseFloat(e.target.value);
  if (!isNaN(val)) setBankroll(val);
}}
```

**Teste:** Digitar 500 → clicar 100 → valor deve ser 100. Digitar 750 no input → valor deve ser 750.

---

## BUG 2 — Stake hardcoded no frontend

**Comportamento atual:** O percentual de stake (2.1%, 3.9%, etc.) vem hardcoded ou inventado no frontend.
**Comportamento esperado:** O frontend lê `kelly_percent` (ou campo equivalente) da resposta da API e apenas multiplica pelo bankroll do usuário.

```bash
# Verificar se a API já retorna kelly/stake
grep -rn "kelly\|stake_percent\|suggested_stake\|quarter_kelly" backend/ --include="*.py" | head -15

# Verificar como o frontend consome os picks
grep -n "kelly\|stake\|ev_percent\|markets" frontend/next/src/components/DestaquesDoDia.tsx | head -20
```

**Se a API JÁ retorna `kelly_percent` por pick/mercado:**
- Consumir diretamente: `stake = pick.kelly_percent`
- Valor em R$: `stakeReais = bankroll * (pick.kelly_percent / 100)`

**Se a API NÃO retorna:**
- Calcular no frontend como fallback temporário usando a fórmula:
```tsx
const calcKelly = (prob: number, odd: number): number => {
  const edge = prob * odd - 1;
  if (edge <= 0) return 0;
  const kellyFull = edge / (odd - 1);
  const quarterKelly = kellyFull * 0.25;
  return Math.min(quarterKelly * 100, 5.0); // cap 5%
};
```
- Adicionar comentário `// TODO: substituir por kelly_percent do backend quando disponível`
- prob = `model_prob` ou `calibrated_prob` do pick
- odd = `odd` do mercado

**NUNCA** usar valores fixos como `stake: '2.1%'` em mock data dentro do componente.

---

## BUG 3 — Spinners nativos do input number visíveis no mobile

**Comportamento atual:** `type="number"` mostra setas de incremento nativas (feias no tema dark).
**Comportamento esperado:** Setas escondidas via CSS.

```bash
grep -n "type.*number\|webkit.*spin\|moz.*appearance" frontend/next/src/styles/scoretabs-dashboard.css
grep -n "type.*number\|webkit.*spin\|moz.*appearance" frontend/next/src/components/DestaquesDoDia.tsx
```

**Fix:** Adicionar ao CSS global (`scoretabs-dashboard.css` ou `globals.css`):

```css
/* Esconder spinners nativos do input number */
input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type=number] {
  -moz-appearance: textfield;
}
```

Se o componente usa Tailwind inline, adicionar classe utilitária:
```tsx
className="... [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
```

---

## BUG 4 — Seção cinza: ChevronRight sugere clicável mas cursor-default

**Comportamento atual:** Items da seção "Apenas Análise" têm `ChevronRight` (→) mas `cursor-default` — contradição visual.
**Comportamento esperado:** Items são clicáveis e navegam para o match detail card.

```bash
grep -n "cursor-default\|cursor-pointer\|ChevronRight\|onClick.*match\|router.*push\|href.*match" frontend/next/src/components/DestaquesDoDia.tsx | head -10
```

**Fix:**

1. Trocar `cursor-default` por `cursor-pointer` no container do item
2. Adicionar onClick que navega pro detalhe do jogo:

```tsx
import { useRouter } from 'next/navigation';

// Dentro do componente:
const router = useRouter();

// No item da seção cinza:
<div
  className="... cursor-pointer"
  onClick={() => router.push(`/dashboard?match=${match.match_id}`)}
>
```

Se o dashboard usa outro padrão de navegação (ex: abrir match detail card no painel direito via state), seguir o padrão existente:

```bash
# Verificar como o dashboard atual abre detalhes de jogo
grep -rn "selectedMatch\|setSelectedMatch\|matchDetail\|openMatch" frontend/next/src/ --include="*.tsx" | head -10
```

Adaptar o onClick ao mecanismo que já existe — NÃO inventar rota nova se o padrão atual é via state.

---

## Validação

```bash
# Build
cd frontend/next && npm run build

# Verificar que nenhum mock de stake ficou hardcoded
grep -n "stake.*2\.1\|stake.*3\.9\|stake.*1\.5\|stake.*2\.0" frontend/next/src/components/DestaquesDoDia.tsx
# Deve retornar 0 resultados

# Verificar CSS de spinners
grep -n "webkit.*spin\|moz.*appearance\|appearance.*textfield" frontend/next/src/styles/scoretabs-dashboard.css

# Verificar cursor-pointer na seção cinza
grep -n "cursor-pointer" frontend/next/src/components/DestaquesDoDia.tsx
```

## Registro

```bash
# Atualizar REGISTRO_CORRECOES.md — adicionar entrada #117b:
# Título: "Correção DestaquesDoDia — presets definem valor, stake do backend, spinners, clicável"
# Root cause: "4 itens da spec #117 não implementados na primeira passada"

# Commit + push
git add -A
git commit -m "fix: DestaquesDoDia — presets define value, kelly from API, hide spinners, clickable analysis (#117b)"
git push origin main
```

A tarefa SÓ está concluída quando:
- Digitar 500 + clicar 100 = 100 (define, não soma)
- Stake vem da API ou é calculado via fórmula Kelly (sem hardcode)
- Spinners invisíveis no mobile
- Items cinza clicáveis com cursor-pointer
