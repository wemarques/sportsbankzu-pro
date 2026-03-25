# PROMPT — Corrigir 3 Problemas de Apresentação de Mercados

## CONTEXTO

O pipeline v2 está funcionando corretamente nos cálculos, mas a apresentação dos mercados ao usuário tem 3 problemas:

1. **DC 1X mostra `({'N/EMP)` em vez de `(KON/EMP)`** — o campo `homeTeam` chega como dict em vez de string, e `str(dict)[:3]` gera lixo
2. **1X2 Home e DC 1X aparecem juntos** — redundante, DC 1X é versão conservadora da mesma aposta
3. **Over 2.5 e Under 3.5 aparecem juntos sem sinalização** — é um corredor legítimo apontando para exatamente 3 gols, mas confunde o usuário

Todas as correções são no arquivo `backend/services/ev_classification.py`.

---

## CORREÇÃO 1 — Label do DC 1X (bug de formatação)

Arquivo: `backend/services/ev_classification.py`, linha ~397

O código atual:
```python
home_label = str(match_data.get("homeTeam", ""))[:3].upper()
```

Se `homeTeam` for um dict (ex: `{"name": "Konyaspor", "id": 123}`), `str(dict)[:3]` retorna `{'n` → `.upper()` = `{'N`. Resultado: `DC 1X ({'N/EMP)`.

Corrigir para extrair o nome do time corretamente:

```python
# Extract home team name — handle both string and dict formats
_raw_home = match_data.get("homeTeam", match_data.get("home_team", ""))
if isinstance(_raw_home, dict):
    home_label = str(_raw_home.get("name", _raw_home.get("team_name", "")))[:3].upper()
elif isinstance(_raw_home, str):
    home_label = _raw_home[:3].upper()
else:
    home_label = str(_raw_home)[:3].upper()

# Fallback: use first 3 chars of home_team from top-level
if not home_label or home_label.startswith("{"):
    home_label = str(home_team)[:3].upper() if home_team else "CAS"
```

Nota: `home_team` já é extraído corretamente na linha 225: `home_team = match_data.get("homeTeam", "")`. Se esse também for dict, aplicar a mesma lógica. Corrigir as linhas 225-226:

```python
# Lines 225-226 — normalize team names
_raw_home = match_data.get("homeTeam", match_data.get("home_team", ""))
_raw_away = match_data.get("awayTeam", match_data.get("away_team", ""))
home_team = _raw_home.get("name", _raw_home.get("team_name", str(_raw_home))) if isinstance(_raw_home, dict) else str(_raw_home)
away_team = _raw_away.get("name", _raw_away.get("team_name", str(_raw_away))) if isinstance(_raw_away, dict) else str(_raw_away)
```

E então na linha 397 simplificar:
```python
home_label = home_team[:3].upper() if home_team else "CAS"
```

---

## CORREÇÃO 2 — Filtrar redundância 1X2 Home + DC 1X

Quando o sistema mostra "1X2 Home" E "DC 1X" para o mesmo jogo, é redundante. Toda vitória do mandante é também um acerto de DC 1X.

Regra: se ambos aparecem nos mercados ativos, manter apenas um:
- Se prob de 1X2 Home >= 50% → manter 1X2 Home (mais valor), remover DC 1X
- Se prob de 1X2 Home < 50% → manter DC 1X (mais seguro), remover 1X2 Home

Adicionar este filtro APÓS a linha 576 (`active_markets = [m for m in markets...]`) e ANTES da linha 578 (`bundle = MatchMarketBundle(...)`):

```python
# ─── Filter redundant 1X2 ↔ Double Chance ───
# If both "1X2 Home" and "DC 1X" are present, keep only the better one.
# Same logic for "1X2 Away" + "DC X2".
active_markets = _filter_1x2_dc_redundancy(active_markets)
```

Criar a função helper (antes de `evaluate_match_markets` ou no final do arquivo):

```python
def _filter_1x2_dc_redundancy(markets: List[MarketOutput]) -> List[MarketOutput]:
    """Remove redundant 1X2/DC pairs — keep only the more appropriate one.
    
    Rules:
    - 1X2 Home + DC 1X → keep 1X2 Home if prob >= 50%, else keep DC 1X
    - 1X2 Away + DC X2 → keep 1X2 Away if prob >= 50%, else keep DC X2
    """
    # Index markets by selection
    by_sel = {}
    for m in markets:
        by_sel.setdefault(m.selection, []).append(m)
    
    remove_set = set()
    
    # Check Home + DC 1X
    home_markets = [m for m in markets if m.selection == "Home" and m.market_type == "1X2"]
    dc1x_markets = [m for m in markets if m.selection == "DC 1X" and m.market_type == "Double Chance"]
    
    if home_markets and dc1x_markets:
        home_m = home_markets[0]
        dc1x_m = dc1x_markets[0]
        home_prob = home_m.calibrated_probability or home_m.raw_probability or 0
        if home_prob >= 0.50:
            # Home has enough probability — remove DC 1X (redundant safer version)
            remove_set.add(id(dc1x_m))
            logger.debug(f"[Redundancy] Removed DC 1X (Home prob={home_prob:.1%} >= 50%)")
        else:
            # Home is risky — remove 1X2 Home, keep DC 1X (safer)
            remove_set.add(id(home_m))
            logger.debug(f"[Redundancy] Removed 1X2 Home (prob={home_prob:.1%} < 50%), keeping DC 1X")
    
    # Check Away + DC X2
    away_markets = [m for m in markets if m.selection == "Away" and m.market_type == "1X2"]
    dcx2_markets = [m for m in markets if m.selection == "DC X2" and m.market_type == "Double Chance"]
    
    if away_markets and dcx2_markets:
        away_m = away_markets[0]
        dcx2_m = dcx2_markets[0]
        away_prob = away_m.calibrated_probability or away_m.raw_probability or 0
        if away_prob >= 0.50:
            remove_set.add(id(dcx2_m))
            logger.debug(f"[Redundancy] Removed DC X2 (Away prob={away_prob:.1%} >= 50%)")
        else:
            remove_set.add(id(away_m))
            logger.debug(f"[Redundancy] Removed 1X2 Away (prob={away_prob:.1%} < 50%), keeping DC X2")
    
    return [m for m in markets if id(m) not in remove_set]
```

---

## CORREÇÃO 3 — Filtrar corredor Over X.5 + Under (X+1).5

Quando Over 2.5 e Under 3.5 aparecem juntos, é um corredor apontando para exatamente 3 gols. O mesmo vale para Over 1.5 + Under 2.5 (corredor de 2 gols) e Over 3.5 + Under 4.5 (corredor de 4 gols).

Regra: manter apenas o mercado com **maior probabilidade** dos dois.

Adicionar logo após o filtro de redundância 1X2/DC:

```python
# ─── Filter corridor bets (Over X.5 + Under (X+1).5) ───
# When both appear, keep only the one with higher probability.
# E.g., Over 2.5 (67%) + Under 3.5 (66%) → keep Over 2.5
active_markets = _filter_corridor_bets(active_markets)
```

Criar a função helper:

```python
def _filter_corridor_bets(markets: List[MarketOutput]) -> List[MarketOutput]:
    """When Over X.5 and Under (X+1).5 both appear, keep only the higher probability one.
    
    Corridors detected:
    - Over 1.5 + Under 2.5 → corridor of exactly 2 goals
    - Over 2.5 + Under 3.5 → corridor of exactly 3 goals
    - Over 3.5 + Under 4.5 → corridor of exactly 4 goals
    """
    CORRIDOR_PAIRS = [
        ("Over 1.5", "Under 2.5"),
        ("Over 2.5", "Under 3.5"),
        ("Over 3.5", "Under 4.5"),
    ]
    
    remove_set = set()
    
    for over_sel, under_sel in CORRIDOR_PAIRS:
        over_markets = [m for m in markets if m.selection == over_sel and m.market_type == "Over/Under"]
        under_markets = [m for m in markets if m.selection == under_sel and m.market_type == "Over/Under"]
        
        if over_markets and under_markets:
            over_m = over_markets[0]
            under_m = under_markets[0]
            over_prob = over_m.calibrated_probability or over_m.raw_probability or 0
            under_prob = under_m.calibrated_probability or under_m.raw_probability or 0
            
            if over_prob >= under_prob:
                remove_set.add(id(under_m))
                logger.debug(
                    f"[Corridor] {over_sel} ({over_prob:.1%}) + {under_sel} ({under_prob:.1%}) "
                    f"→ kept {over_sel} (higher prob)"
                )
            else:
                remove_set.add(id(over_m))
                logger.debug(
                    f"[Corridor] {over_sel} ({over_prob:.1%}) + {under_sel} ({under_prob:.1%}) "
                    f"→ kept {under_sel} (higher prob)"
                )
    
    return [m for m in markets if id(m) not in remove_set]
```

---

## LOCAL EXATO DAS INSERÇÕES

No `evaluate_match_markets()`, após a linha 576 e antes da linha 578, o código final deve ficar:

```python
    # ─── Filter NO_BET markets that have zero probability ───
    active_markets = [m for m in markets if (m.calibrated_probability or m.raw_probability or 0) > 0.05]

    # ─── Filter redundant 1X2 ↔ Double Chance ───
    active_markets = _filter_1x2_dc_redundancy(active_markets)

    # ─── Filter corridor bets (Over X.5 + Under (X+1).5) ───
    active_markets = _filter_corridor_bets(active_markets)

    # ─── Build bundle ───
    bundle = MatchMarketBundle(
```

---

## VALIDAÇÃO

Rodar `pytest -q` após as 3 correções.

Verificar manualmente:
1. DC 1X deve mostrar `DC 1X (KON/EMP)` para Konyaspor, não `DC 1X ({'N/EMP)`
2. Konyaspor vs Gençlerbirliği: se 1X2 Home prob >= 50%, DC 1X desaparece. Se < 50%, 1X2 Home desaparece.
3. Kayserispor vs Fatih Karagümrük: Over 2.5 (67%) e Under 3.5 (66%) → aparece só Over 2.5 (maior prob)

Fazer commit:
```
fix: clean DC label, filter 1X2/DC redundancy, filter corridor bets

- Fix DC 1X label: handle homeTeam as dict (was showing {'N/EMP)
- Filter: when 1X2 Home + DC 1X both appear, keep only the better one based on probability
- Filter: when Over X.5 + Under (X+1).5 form a corridor, keep only the higher probability one
```

Depois push:
```bash
git push origin main
```

---

## REGRAS

- Todas as 3 correções são no mesmo arquivo: `backend/services/ev_classification.py`
- NÃO alterar cálculos de probabilidade, odds ou EV
- NÃO alterar o frontend (isso será feito em prompt separado)
- Os filtros removem mercados da lista ANTES de montar o bundle — os mercados filtrados simplesmente não aparecem
- Se `pytest -q` falhar, corrigir antes de commitar
