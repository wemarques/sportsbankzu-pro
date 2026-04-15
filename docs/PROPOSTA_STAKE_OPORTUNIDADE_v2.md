# Sistema de Stake por Oportunidade v2 (Refinado)

**Data:** 2026-04-15
**Status:** Proposta para aprovação
**Regra:** #149 (pendente)

---

## 1. Filosofia

O sistema atual (Quarter Kelly + EV ≥ 5%) é conservador demais para o perfil do operador. Picks classificados como VIÁVEL e VALOR DETECTADO recebem stake R$ 0,00 quando o EV é marginal ou negativo, desperdiçando oportunidades com sinal estatístico positivo.

**Novo paradigma:** Alocação de capital proporcional à confiança no sinal, com penalização gradual por EV negativo e transparência total sobre o custo esperado.

**O que NÃO muda:** As 4 classificações existentes (SAFE, NEUTRO_QUALIFICADO, NEUTRO, NO_BET) permanecem. Não será criada uma 5ª camada. O pipeline de cálculo de probabilidades, thresholds e deflação não é alterado.

---

## 2. Modo Dual: Kelly vs Oportunidade

O usuário escolhe o modo no BankrollCard:

| Modo | Quando usar | Lógica |
|------|-------------|--------|
| **Kelly** (atual) | Otimizar crescimento de banca a longo prazo | Quarter Kelly × multiplicador por classificação. Stake = 0 se EV < 0 |
| **Oportunidade** (novo) | Capturar sinais de momento, aceitar custo de EV negativo | Stake por tier de classificação, com desconto por EV negativo |

Isso evita refatorar o pipeline inteiro — é uma camada de cálculo alternativa no frontend e backend.

---

## 3. Tiers de Stake (Modo Oportunidade)

```python
STAKE_TIERS = {
    "SAFE": {
        "stake_base_pct": 0.03,     # 3% da banca
        "cap_max_pct": 0.05,        # Máximo 5%
        "ev_bloqueio": -0.05,       # Bloqueia se EV < -5%
        "label": "ALTA CONFIANÇA"
    },
    "NEUTRO_QUALIFICADO": {
        "stake_base_pct": 0.02,     # 2% da banca
        "cap_max_pct": 0.04,        # Máximo 4%
        "ev_bloqueio": -0.10,       # Bloqueia se EV < -10%
        "label": "VALOR DETECTADO"
    },
    "NEUTRO": {
        "stake_base_pct": 0.01,     # 1% da banca
        "cap_max_pct": 0.02,        # Máximo 2%
        "ev_bloqueio": -0.15,       # Bloqueia se EV < -15%
        "label": "VIÁVEL"
    },
    "NO_BET": {
        "stake_base_pct": 0.00,     # 0% — bloqueado
        "cap_max_pct": 0.00,
        "ev_bloqueio": 999,
        "label": "BLOQUEADO"
    }
}
```

### Diferenças da proposta v1

- **Removida camada INFORMATIVO** — evita mudança estrutural no pipeline. Picks abaixo do threshold do mercado mas acima de 50% continuam como NEUTRO com stake mínimo (1%).
- **`ev_minimo` renomeado para `ev_bloqueio`** — deixa claro que é um filtro de segurança, não um alvo.
- **Tiers mais conservadores que v1** — NEUTRO bloqueado em -15% (não -20%), SAFE em -5% (não indefinido).

---

## 4. Fórmula de Cálculo

```python
def calcular_stake_oportunidade(
    classificacao: str,
    banca: float,
    prob_raw: float,
    odd: float,
    ev_deflacionado: float,
    mercado: str,
) -> dict:
    """
    Stake baseado na confiança da classificação com desconto
    proporcional ao EV negativo.
    """
    tier = STAKE_TIERS.get(classificacao, STAKE_TIERS["NO_BET"])

    # 1. Filtro de piso absoluto (50%)
    if prob_raw < 0.50:
        return {"stake": 0, "motivo": "Prob < 50%"}

    # 2. Filtro de bloqueio por EV
    if ev_deflacionado < tier["ev_bloqueio"]:
        return {
            "stake": 0,
            "motivo": f"EV {ev_deflacionado:.1%} abaixo do limite {tier['ev_bloqueio']:.0%}"
        }

    # 3. Stake base
    stake_pct = tier["stake_base_pct"]

    # 4. Bônus por excesso de confiança (saturado)
    #    prob_raw acima do threshold do mercado dá bônus, com teto de +2%
    threshold = get_threshold_mercado(mercado, classificacao)
    excesso = max(0, prob_raw - threshold)
    bonus_pct = min(excesso * 0.3, 0.02)  # Satura em +2%
    stake_pct += bonus_pct

    # 5. DESCONTO por EV negativo (proporcional)
    #    EV 0% = 100% do stake, EV -10% = 90%, EV -15% = 85%
    if ev_deflacionado < 0:
        desconto = max(0.50, 1.0 + ev_deflacionado)  # Piso: 50% do stake
        stake_pct *= desconto

    # 6. Aplica cap máximo
    stake_pct = min(stake_pct, tier["cap_max_pct"])

    # 7. Calcula valor
    stake_valor = round(banca * stake_pct, 2)

    # 8. Custo esperado (transparência)
    custo_por_100 = round((-ev_deflacionado) * 100, 2) if ev_deflacionado < 0 else 0

    return {
        "stake": stake_valor,
        "stake_pct": round(stake_pct, 4),
        "classificacao": classificacao,
        "confianca": tier["label"],
        "ev": ev_deflacionado,
        "desconto_ev": round(desconto, 2) if ev_deflacionado < 0 else 1.0,
        "custo_por_100": custo_por_100,
        "cap_aplicado": stake_pct >= tier["cap_max_pct"],
    }
```

### Diferenças da v1

| Aspecto | Proposta v1 | Proposta v2 (refinada) |
|---------|-------------|----------------------|
| EV negativo no stake | Sem impacto (stake cheio) | Desconto proporcional: -10% EV = 90% do stake |
| Bônus confiança | Linear sem limite (`excesso × 0.5`) | Saturado: `min(excesso × 0.3, 0.02)` |
| Piso do desconto | Inexistente | 50% (nunca menos da metade do stake base) |
| Custo esperado | Não calculado | Exibido ao usuário: "R$ X por R$ 100 apostados" |

---

## 5. Exemplos de Cálculo (Revisados)

### Exemplo 1: Cartões Over 1.5

- Classificação: NEUTRO (VIÁVEL), prob 60%, threshold 60%
- Banca: R$ 1.000, Odd: 1.65, EV: -15.8%

```
stake_base = 1000 × 0.01 = R$ 10,00
excesso = 60% - 60% = 0% → bônus = 0
EV -15.8% < bloqueio -15% → BLOQUEADO ❌
Resultado: Stake R$ 0,00 (EV muito negativo para VIÁVEL)
```

Se o EV fosse -12%:
```
stake_base = R$ 10,00
desconto = max(0.50, 1.0 + (-0.12)) = 0.88
stake_ajustado = R$ 10,00 × 0.88 = R$ 8,80
cap = R$ 20,00 → não aplicado
Resultado: Stake R$ 8,80 (0.88% da banca)
Custo esperado: R$ 12,00 por R$ 100 apostados
```

### Exemplo 2: Escanteios Under 12.5

- Classificação: NEUTRO (VIÁVEL), prob 53%, threshold 58%
- Banca: R$ 1.000, Odd: 1.89, EV: ~0%

```
stake_base = 1000 × 0.01 = R$ 10,00
excesso = 53% - 58% = -5% → bônus = 0 (abaixo do threshold)
EV ~0% → sem desconto
stake_final = R$ 10,00
Resultado: Stake R$ 10,00 (1% da banca)
Custo esperado: R$ 0 por R$ 100 apostados
```

### Exemplo 3: Pick SAFE com EV positivo

- Classificação: SAFE, prob 75%, threshold 72% (Escanteios)
- Banca: R$ 1.000, Odd: 1.50, EV: +3%

```
stake_base = 1000 × 0.03 = R$ 30,00
excesso = 75% - 72% = 3% → bônus = min(0.03 × 0.3, 0.02) = 0.9% → R$ 9,00
stake_ajustado = R$ 30,00 + R$ 9,00 = R$ 39,00
EV +3% → sem desconto
cap = R$ 50,00 → não aplicado
Resultado: Stake R$ 39,00 (3.9% da banca)
```

### Exemplo 4: NEUTRO_QUALIFICADO com EV negativo

- Classificação: NEUTRO_QUALIFICADO, prob 55%, threshold 52%
- Banca: R$ 1.000, Odd: 1.80, EV: -7%

```
stake_base = 1000 × 0.02 = R$ 20,00
excesso = 55% - 52% = 3% → bônus = min(0.03 × 0.3, 0.02) = 0.9% → R$ 9,00
subtotal = R$ 29,00
desconto = max(0.50, 1.0 + (-0.07)) = 0.93
stake_ajustado = R$ 29,00 × 0.93 = R$ 26,97
cap = R$ 40,00 → não aplicado
Resultado: Stake R$ 26,97 (2.7% da banca)
Custo esperado: R$ 7,00 por R$ 100 apostados
```

---

## 6. Proteção de Banca (Fase 1 — apenas alerta visual)

A proposta original incluía proteções de controle de estado (stop-loss, cooldown, max picks simultâneos). Essas dependem de tracking de apostas reais — o sistema atual apenas sugere, o usuário aposta na casa. Sem integração com a casa ou registro manual, controles automáticos são inaplicáveis.

### Fase 1 (implementar agora): Alerta visual

```python
PROTECOES_FASE1 = {
    "max_exposure_diario_pct": 0.15,    # Alerta se stake acumulado > 15% da banca
    "max_exposure_mercado_pct": 0.08,   # Alerta se stake total em um mercado > 8%
}
```

No frontend, uma barra de exposição no BankrollCard mostra:

```
Exposição: ████████░░░░ 12% / 15%
Cartões:   ██████░░░░░░ 6% / 8%
Escanteios: ████░░░░░░░░ 4% / 8%
```

Quando ultrapassa o limite: barra fica vermelha + alerta textual. Mas NÃO bloqueia — o usuário decide.

### Fase 2 (futura): Tracking real

Exige registro manual de apostas feitas ou integração API com a casa. Features: stop-loss diário, cooldown pós-loss, histórico de P&L. Não faz parte desta implementação.

---

## 7. Frontend — Toggle Kelly/Oportunidade

### BankrollCard

Adicionar toggle abaixo da banca:

```
┌─────────────────────────────────────────────┐
│ BANCA DISPONÍVEL              [EDITÁVEL]    │
│                                             │
│ R$                           1000           │
│                                             │
│ [ 50 ] [ 100 ] [ 250 ] [ 500 ] [ 1k ]      │
│                                             │
│ Modo: [ Kelly ] [ Oportunidade ]  ← toggle  │
│                                             │
│ Exposição: ████████░░░░ 12% / 15%           │
└─────────────────────────────────────────────┘
```

### StakeRow (em cada pick)

Modo Kelly (atual): mostra % Kelly + R$ + campo editável
Modo Oportunidade: mostra tier + % + R$ + desconto EV + custo esperado

```
┌─ Modo Oportunidade ─────────────────────────┐
│ VIÁVEL  1.0%  │  R$ 8,80  │  Desc -12%      │
│ ⚠️ Custo: R$ 12/R$ 100 apostados            │
└─────────────────────────────────────────────┘
```

O campo editável de % (já implementado no #148d) continua funcionando em ambos os modos — o usuário sempre pode sobrescrever.

---

## 8. Impacto no Código

### Backend (bankroll_engine.py)

- Adicionar função `compute_stake_oportunidade()` ao lado da `compute_stake()` existente
- Parâmetro `mode: "kelly" | "oportunidade"` na API de stake
- Sem impacto no pipeline de cálculo (prob, deflação, classificação)

### Frontend

| Arquivo | Alteração |
|---------|-----------|
| BankrollCard.tsx | Toggle Kelly/Oportunidade + barra de exposição |
| atoms.tsx (StakeRow) | Lógica condicional por modo + alerta EV negativo |
| PickCard.tsx | Passar modo como prop |
| MatchAnalysis.tsx | Receber e propagar modo |
| dashboard/page.tsx | State do modo + persistir em localStorage |

### Arquivos NÃO alterados

- ev_classification.py (classificação não muda)
- market_service.py (seleção não muda)
- localAudit.ts (avaliação hit/miss não muda)
- matchDataMapper.ts (mapeamento não muda)
- Thresholds, deflações, pipeline inteiro

---

## 9. Configuração Externalizável

```yaml
# config/stake_oportunidade.yaml
modo_default: "kelly"

tiers:
  SAFE:
    stake_base_pct: 0.03
    cap_max_pct: 0.05
    ev_bloqueio: -0.05
  NEUTRO_QUALIFICADO:
    stake_base_pct: 0.02
    cap_max_pct: 0.04
    ev_bloqueio: -0.10
  NEUTRO:
    stake_base_pct: 0.01
    cap_max_pct: 0.02
    ev_bloqueio: -0.15
  NO_BET:
    stake_base_pct: 0.00
    cap_max_pct: 0.00
    ev_bloqueio: 999

bonus:
  fator: 0.3          # multiplicador do excesso de confiança
  max_bonus_pct: 0.02 # teto do bônus

desconto_ev:
  piso: 0.50           # mínimo 50% do stake base quando EV negativo

protecoes:
  max_exposure_diario_pct: 0.15
  max_exposure_mercado_pct: 0.08
```

Permite ajustar stakes sem redeploy — basta atualizar o YAML ou env vars.

---

## 10. Simulação de Cenário de Risco

Com banca de R$ 1.000 e 5 picks VIÁVEL por dia (EV médio -10%):

| Cenário | Stake diário | Perda esperada/dia | Perda/mês (20 dias) |
|---------|-------------|-------------------|---------------------|
| **v1 (sem desconto)** | 5 × R$ 10 = R$ 50 | R$ 5,00 | R$ 100 (10%) |
| **v2 (com desconto)** | 5 × R$ 9 = R$ 45 | R$ 4,50 | R$ 90 (9%) |
| **Kelly (atual)** | R$ 0 | R$ 0 | R$ 0 |

O desconto por EV reduz ~10% da exposição. O custo é visível e aceito pelo operador como "custo de participação", não como bug do sistema.

Para referência: 5 picks SAFE/dia com EV +3% geram +R$ 4,50/dia (+R$ 90/mês). O modo Oportunidade em picks VIÁVEL subsidia participação com custo controlado.

---

## 11. Checklist de Implementação

1. Backend: `compute_stake_oportunidade()` em bankroll_engine.py
2. Config: stake_oportunidade.yaml com tiers configuráveis
3. Frontend: Toggle Kelly/Oportunidade no BankrollCard
4. Frontend: StakeRow condicional por modo + alerta custo
5. Frontend: Barra de exposição diária (visual, não bloqueante)
6. Testes: Unit tests para cada tier + desconto EV + bloqueio
7. Docs: Registrar como REGRA #149
