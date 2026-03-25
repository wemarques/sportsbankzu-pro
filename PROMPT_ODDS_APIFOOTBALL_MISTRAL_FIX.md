# PROMPT — Corrigir Odds + Enriquecer com API-Football + Enriquecer Mistral

## CONTEXTO

O pipeline v2 foi ativado e funciona, mas há 3 problemas interconectados:

1. **Odds de Under estão infladas** — o sistema deriva odds Under a partir de Over sem considerar overround da casa, gerando EV artificialmente alto (ex: 139.9% para Under 2.5). Além disso, a odd real de Under 2.5 que a FootyStats fornece (`odds_ft_under25`) está sendo PERDIDA por mismatch de field name.

2. **A API-Football tem odds reais de Under de múltiplas linhas** mas a função `extract_best_odds()` (já implementada) não é chamada no fluxo de cálculo.

3. **A Mistral recebe dados incompletos** — não recebe corners, xG, shots, chaos score, injuries, lineups, data quality score nem reason codes do pipeline v2.

Implementar as 3 correções abaixo nesta ordem. Após cada bloco, rodar `pytest -q`.

---

## BLOCO 1 — CORRIGIR ODDS DE UNDER (PRIORIDADE MÁXIMA)

### 1.1 Mapear odds Under 2.5 reais da FootyStats

A FootyStats retorna `odds_ft_under25` no endpoint `/league-matches` (confirmado na documentação: `"odds_ft_under25": 1.95, "odds_ft_over25": 1.90`). Mas o sistema não mapeia esse campo.

**Arquivo:** `backend/services/data_mapper.py`

Adicionar no modelo e no mapeamento:
```python
# No modelo (junto com odds_ft_over25, ~linha 109):
odds_ft_under25: Optional[float] = 0.0

# No mapeamento (junto com "odds_ft_over25", ~linha 234):
"odds_ft_under25": api_match.get("odds_ft_under25", 0.0),
```

**Arquivo:** `backend/services/fixtures_service.py`

Na linha ~252, corrigir o field name para buscar a odd real:
```python
# DE:
odds_under25 = r.get("odds_under_25", None)

# PARA:
odds_under25 = r.get("odds_ft_under25", r.get("odds_under_25", r.get("odds_under25", None)))
```

### 1.2 Corrigir derivação de odds Under em ev_classification.py

**Arquivo:** `backend/services/ev_classification.py`

No bloco de Over/Under markets (~linhas 327-351), o Under odd é derivado do Over sem overround:

```python
# PROBLEMA ATUAL (linhas 334-339):
under_odd = None
if book_odd and book_odd > 1.0:
    prob_over = 1.0 / book_odd
    prob_under = 1.0 - prob_over
    if prob_under > 0:
        under_odd = round(1.0 / prob_under, 2)
```

Corrigir para:
1. PRIMEIRO tentar usar a odd real de Under do dict de odds
2. SÓ derivar como fallback, E com desconto de overround

```python
# Under odds: prefer real odds, fallback to derived with overround discount
under_key = f"under{threshold.replace('.', '')}"  # "under25", "under35", "under45"
under_odd = odds.get(under_key)
if under_odd:
    under_odd = float(under_odd) if float(under_odd) > 1.0 else None

if under_odd is None and book_odd and book_odd > 1.0:
    # Derive from Over with overround discount (~5% margin)
    OVERROUND = 1.05
    implied_over = 1.0 / book_odd
    implied_under_raw = max(0.01, 1.0 - implied_over)
    implied_under_fair = implied_under_raw / OVERROUND
    under_odd = round(1.0 / implied_under_fair, 2) if implied_under_fair > 0.01 else None
```

### 1.3 Corrigir derivação de odds Under de corners

**Arquivo:** `backend/services/ev_classification.py`

No bloco de Under corners (~linhas 489-500), mesma correção — adicionar overround:

```python
# Se não tem odd Under de corners direta, derivar com overround:
if under_odd is None:
    over_odd_key = f"cornersOver{line_tag}"
    over_odd = odds.get(over_odd_key)
    if over_odd and float(over_odd) > 1.0:
        OVERROUND = 1.06  # corners market margin ~6%
        implied_over = 1.0 / float(over_odd)
        implied_under_raw = max(0.01, 1.0 - implied_over)
        implied_under_fair = implied_under_raw / OVERROUND
        under_odd = round(1.0 / implied_under_fair, 2) if implied_under_fair > 0.01 else None
    else:
        under_odd = None
```

### 1.4 Corrigir calcular_odd_under no market_service.py

**Arquivo:** `backend/services/market_service.py`

A função `calcular_odd_under()` (linha 131) também ignora overround. Corrigir:

```python
def calcular_odd_under(odd_over: float, overround: float = 1.05) -> Optional[float]:
    if not odd_over or odd_over <= 1.0:
        return None
    prob_over = 1.0 / odd_over
    prob_under_raw = 1.0 - prob_over
    prob_under_fair = prob_under_raw / overround
    if prob_under_fair <= 0:
        return None
    return round(1.0 / prob_under_fair, 2)
```

### 1.5 Passar odds Under 2.5 real no dict de odds do record

**Arquivo:** `backend/services/fixtures_service.py`

Confirmar que na montagem do record (~linha 833), a odd Under 2.5 é passada:
```python
"odds": {
    ...
    "under25": float(odds_under25) if odds_under25 else None,
    ...
}
```

Isso já existe, mas só funciona se 1.1 for corrigido.

Rodar `pytest -q` após este bloco.

---

## BLOCO 2 — API-FOOTBALL ENRICHMENT PARA PRÉ-JOGO

### 2.1 Buscar odds reais da API-Football

A função `extract_best_odds()` em `api_football_client.py` já extrai `under_25`, `over_25`, `btts_yes`, `btts_no`, `home`, `draw`, `away` da API-Football com prioridade para bet365/Pinnacle. Mas ninguém a chama no fluxo de cálculo.

**Arquivo:** `backend/services/fixtures_service.py`

Dentro de `build_records_from_matches()`, APÓS montar o record e ANTES de calcular mercados, adicionar enriquecimento opcional com API-Football:

```python
# Enrich odds from API-Football when available (fills gaps in FootyStats odds)
try:
    from backend.services.api_football_client import APIFootballClient
    _afc = APIFootballClient()
    footystats_id = r.get("id")
    if footystats_id:
        # Try to get API-Football fixture ID (may need mapping)
        af_odds = _afc.get_odds(int(footystats_id), ttl_minutes=180)
        if af_odds:
            best = _afc.extract_best_odds(af_odds)
            # Fill missing odds ONLY — don't override FootyStats odds
            odds_dict = record["odds"]
            if not odds_dict.get("under25") and best.get("under_25"):
                odds_dict["under25"] = best["under_25"]
                logger.info(f"[API-Football] Under 2.5 odd enriched: {best['under_25']}")
            if not odds_dict.get("bttsNo") and best.get("btts_no"):
                odds_dict["bttsNo"] = best["btts_no"]
            # Add source flag
            record.setdefault("source_flags", []).append("api_football_odds")
except Exception as e:
    logger.debug(f"[API-Football] Odds enrichment skipped: {e}")
```

IMPORTANTE: Isso depende de ter o fixture_id da API-Football. Se o mapping não existir, este bloco degrada silenciosamente. NÃO bloquear o fluxo se a API-Football falhar.

### 2.2 Buscar injuries pré-jogo

**Arquivo:** `backend/services/fixtures_service.py`

No mesmo ponto (após montar record, antes de calcular mercados), adicionar injuries:

```python
# Enrich with pre-match injuries when available
try:
    if _afc and footystats_id:
        injuries = _afc.get_injuries_sync(int(footystats_id), ttl_minutes=240)
        if injuries:
            injury_data = {
                "home": [inj for inj in injuries if inj.get("team", {}).get("name") == home],
                "away": [inj for inj in injuries if inj.get("team", {}).get("name") == away],
            }
            record["injuries"] = injury_data
            record.setdefault("source_flags", []).append("api_football_injuries")
except Exception as e:
    logger.debug(f"[API-Football] Injuries enrichment skipped: {e}")
```

### 2.3 Buscar lineups quando disponíveis

```python
# Enrich with lineups (available 30-60 min before kickoff)
try:
    if _afc and footystats_id and status == "incomplete":
        lineups = _afc.get_fixture_lineups(int(footystats_id), ttl_minutes=30)
        if lineups:
            record["lineups"] = lineups
            record.setdefault("source_flags", []).append("api_football_lineups")
except Exception as e:
    logger.debug(f"[API-Football] Lineups enrichment skipped: {e}")
```

NOTA: Lineups e injuries requerem que o fixture_id da API-Football corresponda ao da FootyStats. Se não houver mapeamento direto, essas funcionalidades ficam para implementação futura. O bloco deve degradar silenciosamente.

Rodar `pytest -q` após este bloco.

---

## BLOCO 3 — ENRIQUECER DADOS ENVIADOS À MISTRAL

### 3.1 Enriquecer match_analysis_service.py

**Arquivo:** `backend/ai/match_analysis_service.py`

A função `analyze_match()` (linha 29) recebe `stats`, `odds`, `context`, mas o prompt usa poucos campos. Expandir o prompt para incluir dados do pipeline v2:

Após a seção "ESTATÍSTICAS DO JOGO:" no prompt (~linha 52), adicionar:

```python
# Adicionar APÓS as estatísticas existentes, ANTES do bloco de contexto:
prompt += f"""
DADOS AVANÇADOS DO SISTEMA:
- xG Casa: {stats.get('homeXgForAvg', stats.get('xg_home', 'N/A'))}
- xG Fora: {stats.get('awayXgForAvg', stats.get('xg_away', 'N/A'))}
- Chutes/Jogo Casa: {stats.get('homeShotsPerMatch', 'N/A')}
- Chutes/Jogo Fora: {stats.get('awayShotsPerMatch', 'N/A')}
- Posse Casa: {stats.get('homePossession', 'N/A')}%
- Posse Fora: {stats.get('awayPossession', 'N/A')}%
- Escanteios/Jogo Casa: {stats.get('homeCornersPerMatch', 'N/A')}
- Escanteios/Jogo Fora: {stats.get('awayCornersPerMatch', 'N/A')}
- Escanteios Contra Casa: {stats.get('homeCornersAgainstPerMatch', 'N/A')}
- Escanteios Contra Fora: {stats.get('awayCornersAgainstPerMatch', 'N/A')}
- Chaos Detectado: {stats.get('chaosDetected', False)}
- Regime da Liga: {stats.get('leagueRegime', 'N/A')}
- Volatilidade: {stats.get('leagueVolatility', 'N/A')}
"""

# Se houver dados de odds de corners:
corner_odds = []
for line in ["85", "95", "105", "115"]:
    odd = odds.get(f"cornersOver{line}")
    if odd:
        corner_odds.append(f"Over {line[0]}.{line[1]} = {odd}")
if corner_odds:
    prompt += f"""
ODDS DE ESCANTEIOS:
{chr(10).join(f'- {o}' for o in corner_odds)}
"""
```

### 3.2 Incluir injuries e lineups no contexto da Mistral

No mesmo `analyze_match()`, quando `context` for recebido, incluir injuries e lineups se disponíveis:

```python
if context:
    prompt += f"""
CONTEXTO ADICIONAL:
- Forma Casa: {context.get('home_form', 'N/A')}
- Forma Fora: {context.get('away_form', 'N/A')}
- Confrontos diretos: {context.get('h2h', 'N/A')}
"""
    # Injuries from API-Football
    injuries = context.get('injuries', {})
    if injuries:
        home_inj = injuries.get('home', [])
        away_inj = injuries.get('away', [])
        if home_inj:
            names = [f"{i.get('player', {}).get('name', '?')} ({i.get('player', {}).get('type', '?')})" for i in home_inj[:5]]
            prompt += f"- Lesões/Suspensões Casa: {', '.join(names)}\n"
        if away_inj:
            names = [f"{i.get('player', {}).get('name', '?')} ({i.get('player', {}).get('type', '?')})" for i in away_inj[:5]]
            prompt += f"- Lesões/Suspensões Fora: {', '.join(names)}\n"
        else:
            prompt += f"- Lesões/Suspensões: Sem informações disponíveis\n"

    # Lineups
    lineups = context.get('lineups')
    if lineups:
        prompt += f"- Escalações confirmadas: Sim\n"
    else:
        prompt += f"- Escalações: Não confirmadas\n"
```

### 3.3 Incluir reason codes e classificação do pipeline v2

Quando a Mistral faz análise individual, ela deveria saber quais mercados o sistema já selecionou e por quê. Adicionar ao prompt:

```python
# Se houver mercados já avaliados pelo pipeline v2 (predictions do record):
predictions = context.get('predictions', []) if context else []
if predictions:
    prompt += """
MERCADOS SELECIONADOS PELO SISTEMA:
"""
    for p in predictions[:5]:  # limitar a 5
        prompt += f"- {p.get('mercado', '?')}: {p.get('status', '?')} ({p.get('prob_min', '?')}-{p.get('prob_max', '?')}%)"
        if p.get('ev') is not None:
            prompt += f" EV={p['ev']:.1%}"
        if p.get('reason_codes'):
            prompt += f" [{', '.join(str(r) for r in p['reason_codes'][:3])}]"
        prompt += "\n"
```

### 3.4 Instruir a Mistral a comentar sobre corners quando relevante

Atualizar a instrução final do prompt em `analyze_match()`:

```python
prompt += """
Com base nesses dados, forneça uma análise OBJETIVA no seguinte formato JSON:

{
  "summary": "Resumo de 2-3 frases sobre o jogo, incluindo projeção de escanteios se relevante",
  "key_points": [
    "Ponto sobre gols/resultado",
    "Ponto sobre BTTS/Under/Over",
    "Ponto sobre escanteios se os dados forem relevantes",
    "Ponto sobre contexto tático/lesões",
    "Ponto sobre valor nas odds"
  ],
  "recommendation": "Recomendação com mercado e odd REAL. Pode recomendar mercado de gols OU escanteios. NUNCA invente odds. Use as odds fornecidas.",
  "confidence": 75
}

REGRAS:
- Use APENAS odds fornecidas nos dados acima. NUNCA invente odds.
- Se houver dados de escanteios relevantes, inclua na análise.
- Se o sistema detectou chaos, mencione isso como fator de risco.
- Se houver lesões de jogadores-chave, avalie o impacto.
- Retorne APENAS o JSON, sem texto adicional.
"""
```

### 3.5 Passar dados de enrichment na chamada da Mistral

**Arquivo:** `backend/services/fixtures_service.py`

No trecho onde a Mistral é chamada (~linhas 948-960), passar os dados enriquecidos:

```python
# Ao chamar match analysis (se existir), passar injuries e predictions
if os.getenv("MISTRAL_API_KEY"):
    try:
        # Build enriched context for Mistral
        _context = {
            "home_form": record.get("homeForm"),
            "away_form": record.get("awayForm"),
            "h2h": record.get("h2h"),
            "injuries": record.get("injuries"),  # from API-Football
            "lineups": record.get("lineups"),      # from API-Football
            "predictions": record.get("predictions", mercados),  # pipeline v2 output
        }
        # ... existing ContextAnalyzer call ...
    except Exception as _ctx_err:
        logger.debug(f"[Mistral] Context enrichment skipped: {_ctx_err}")
```

Rodar `pytest -q` após este bloco.

---

## BLOCO 4 — ENRIQUECER mistral_review.py DE CORNERS

### 4.1 Incluir odds reais no prompt de review de corners

**Arquivo:** `backend/modeling/corners/mistral_review.py`

Na função `build_corners_review_prompt()`, após a seção "MELHOR CANDIDATO:", adicionar:

```python
# Adicionar odds reais quando disponíveis
pricing = engine_output.get("pricing", {})
ladder = pricing.get("ladder", [])
odds_info = []
for item in ladder:
    if item.get("book_odd_over"):
        odds_info.append(f"O{item['line']} = {item['book_odd_over']} (real)")
    if item.get("book_odd_under"):
        odds_info.append(f"U{item['line']} = {item['book_odd_under']} (real)")

if odds_info:
    prompt_addition = f"""
ODDS REAIS DE ESCANTEIOS DISPONÍVEIS:
{chr(10).join(f'- {o}' for o in odds_info)}

NOTA: Odds marcadas como "(real)" são de casas de apostas. Odds não listadas foram derivadas pelo modelo.
"""
```

---

## VALIDAÇÃO FINAL

Após todos os 4 blocos:

```bash
pytest -q
cd frontend/next && npm run build
```

Verificar manualmente:
1. Under 2.5 gols deve mostrar odd próxima da real (ex: ~2.50 para bet365) e não mais derivada inflada (ex: 2.89)
2. EV de Under 2.5 não deve mais ser >100% — valores normais são -10% a +15%
3. Escanteios Under devem mostrar odds derivadas com overround (~6% menores que antes)
4. A análise da Mistral deve mencionar xG, shots, corners quando relevante

Fazer commit:
```
fix: use real Under odds + API-Football enrichment + Mistral data enrichment

- Fix Under 2.5 odds: map odds_ft_under25 from FootyStats (was missing due to field name mismatch)
- Fix Under odds derivation: add overround discount (5% goals, 6% corners) to prevent inflated EV
- API-Football: enrich with real odds, injuries, lineups when available
- Mistral: send xG, shots, possession, corners, chaos score, injuries, reason codes
- Mistral corners review: include real odds in prompt
```

---

## REGRAS

- BLOCO 1 é OBRIGATÓRIO — corrige bug real que afeta EV em produção
- BLOCO 2 é DESEJÁVEL — degrada silenciosamente se API-Football não estiver disponível
- BLOCO 3 e 4 são MELHORIAS — enriquecem análise sem quebrar nada
- NÃO alterar a lógica dos modelos (NB, Poisson, ML, lambda)
- NÃO alterar o corners engine v2 (já funciona)
- Toda integração com API-Football deve ser try/except com fallback silencioso
- Se `pytest -q` falhar em qualquer ponto, corrigir antes de prosseguir
