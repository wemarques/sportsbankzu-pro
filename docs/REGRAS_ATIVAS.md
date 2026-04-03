# REGRAS ATIVAS — SportsBankZu Pro

> Leitura OBRIGATORIA antes de qualquer prompt de correcao.
> Historico completo em `docs/REGISTRO_CORRECOES.md`.
> Indice rapido em `docs/INDICE_REGRAS.md`.

---

## CONTRATOS E HARD CONSTRAINTS

### #082 — Mistral exclusivamente narrativa

**Tipo:** Contrato
**Relacionado:** #096 (anti-contradicao), #093 (sem odd = sem recomendacao)

Mistral AI NUNCA calcula probabilidades, NUNCA modifica classificacoes, NUNCA audita picks.
Gera apenas: summary, key_points, recommendation (nao vinculante), confidence.
Fallback: se API key ausente, retorna `confidence=0` — pipeline NAO e afetado.

**Verificacao:** `grep -n "calculate\|classify\|adjust" backend/services/mistral_analysis.py` (deve retornar 0 hits)

### #079 — Amostras minimas para decisoes

**Tipo:** Hard Constraint

- MIN_N_BRIER = 20 jogos para qualquer conclusao de calibracao
- MIN_N_RELIABILITY = 30 jogos para ajuste de reliability
- Abaixo destes limites: exibir "amostra insuficiente", NAO tomar acao

**Verificacao:** `grep -n "MIN_N_BRIER\|min.*20\|n_jogos.*<.*20" backend/services/`

### #042 — Thresholds so com backtesting

**Tipo:** Hard Constraint

Qualquer mudanca em thresholds de probabilidade (safe_prob, neutro_prob) exige backtesting documentado com N>=20 jogos. Thresholds atuais vieram de auditoria de 27 jogos.

### #043 — Circuit breaker SAFE desativado

**Tipo:** Circuit Breaker

SAFE desativado desde #043. Reativacao exige 3 auditorias consecutivas com accuracy >50%.
Lambda deflation 15% ativo. Remocao exige lambda error <0.5 por 3 rodadas.

---

## SAFETY E VALIDACAO

### #096 — 6 camadas anti-alucinacao Mistral

**Tipo:** Safety
**Relacionado:** #001, #002, #082, #093

1. Prompt expandido com 12+ mercados (#001)
2. Instrucao "NAO invente odds" (#002)
3. Recomendacao restrita a mercados com odd real (#093)
4. Picks do pipeline passados no prompt (#096)
5. `_validate_recommendation_vs_pipeline()` bloqueia contradicoes (#096)
6. `_validate_recommendation()` bloqueia "odd nao disponivel" (#093)

**Verificacao:** `grep -c "validate_recommendation" backend/services/mistral_analysis.py` (deve retornar >=2)

### #098 — Mercados complementares >105% bloqueados

**Tipo:** Safety (Hard Constraint)

`validar_mercados_complementares()` em `safety_validation.py` detecta pares Over/Under com probabilidades somando >105% e bloqueia o pick com menor EV. Tolerancia de 5% para arredondamentos.

**Verificacao:** `grep -n "validar_mercados_complementares" backend/services/fixtures_service.py`

### #099 — Filtro acoes auditoria por regras operacionais

**Tipo:** Safety

Bloqueia acoes recomendadas que violam regras: lambda_multiplier (#082), calibration_retrain com N<20 (#079), threshold sem backtesting (#042), safe recalibrar (#043).
Aplicado no backend (`deterministic_audit.py`) E no frontend (`localAudit.ts`).

**Verificacao:** `grep -n "filtrar_acoes_por_regras\|filterActions" backend/services/ frontend/next/src/lib/`

### #093 — Mistral nao recomenda mercado sem odd real

**Tipo:** Safety

Instrucao no prompt: "DEVE ser mercado com odd REAL (NAO N/A)".
`_validate_recommendation()` detecta "odd nao disponivel" e substitui por mensagem padrao.

### #103 — book_odd obrigatorio para stake

**Tipo:** Safety

Stake Quarter Kelly so e calculado quando `book_odd` e real (>1). `odd_minima` (fair value) NUNCA substitui `book_odd`. Picks sem odd real: opacity 0.55, "Sem odd real — stake nao calculavel".

---

## PIPELINE E CLASSIFICACAO

### #028 — Pipeline preditivo V2 de 5 camadas

**Tipo:** Pipeline

```
FootyStats + API-Football → build_records → lambda/xG/chaos → Poisson/Dixon-Coles
→ selecionar_mercados_v2 → ev_classification → bankroll_engine → correlation_matrix
→ API → Frontend
```

### #089 — Todas as datas devem usar BRT (nao UTC)

**Tipo:** Regra permanente
**Relacionado:** #092

`date_range()` parseia ISO dates como dia calendario BRT. `_get_all_finished_matches` usa `datetime.now(BRT)`. `_extract_date_from_id` usa `fromtimestamp(ts, tz=BRT)`.
Grep por `fromtimestamp` sem `tz=BRT` e `utcnow()` antes de cada deploy.

**Verificacao:** `grep -rn "fromtimestamp\|utcnow" backend/ | grep -v "tz=\|BRT\|timezone"`

### #091 — Resolver alias ANTES de gerar match IDs

**Tipo:** Regra permanente

`_process_single_league()` resolve `LEAGUE_ID_ALIASES` ANTES de passar `lid` para `build_records_from_matches`. Match IDs sempre usam o ID canonico do backend.

**Verificacao:** `grep -n "LEAGUE_ID_ALIASES" backend/routes/fixtures.py`

### #104 — Corner lambda em escala total (nao per-team)

**Tipo:** Fix + Regra permanente

`_project_expected_corners()` usa componentes na escala total (`direct_estimate = home_for + away_for`) e NAO valores per-team individuais. Misturar per-team (~4.5) com per-match (~9.0) causa subestimacao sistematica.

**Verificacao:** Pesos WEIGHTS em `backend/modeling/corners/predictor.py` devem usar `direct_estimate` e `cross_estimate`, nao `home_attack`/`away_attack` individuais.

---

## INFRAESTRUTURA E DEPLOY

### #102b — Checklist variaveis de ambiente

**Tipo:** Infra (Regra permanente)

Toda nova variavel de ambiente no codigo DEVE ser verificada:
1. Existe no `.env` local?
2. Existe no Lambda (`aws lambda get-function-configuration`)?
3. Existe no Vercel (se frontend precisa)?

Deploy de codigo sem deploy de infra e deploy incompleto.

### #006 — 7 atualizacoes por novo mercado

**Tipo:** Checklist

Novo mercado exige: engine + ev_classification + market_validator + dedup + correlation_matrix + avaliacao_pos_jogo + tipos frontend. Omitir qualquer passo gera bug silencioso.

---

## REGRA DE FINALIZACAO OBRIGATORIA

Toda alteracao no sistema DEVE:
1. Sincronizar arquivos espelhados (`REGISTRO_CORRECOES.md`, `CLAUDE.md`)
2. Commit no repositorio + push para GitHub
3. Deploy Lambda (se backend alterado)
4. Health check pos-deploy
5. Novas correcoes: registrar no `REGISTRO_CORRECOES.md`
6. Novas regras permanentes: adicionar ao `REGRAS_ATIVAS.md`

### #105 — Deflacao progressiva por banda + per-league

**Tipo:** Pipeline (calibracao)
**Relacionado:** #042, #043, #079

Bandas: <50%->10%, 50-60%->12%, 60-70%->15%, 70-80%->20%, 80%+->25%.
Per-league: brasileirao-serie-a=0.90, league-two=0.95.
Floor: 5% minimo. Fator per-league nunca abaixo de 0.85.
Atualizar fatores quando acumular 50+ picks por liga.

**Verificacao:** `grep -n "apply_probability_deflation\|_LEAGUE_DEFLATION" backend/services/ev_classification.py`

### #106 — Classificacao usa prob raw, EV usa prob deflacionada

**Tipo:** Pipeline (classificacao)
**Relacionado:** #105

classify_market() usa `prob_for_class` (calibrate_prob SEM deflacao) para thresholds SAFE/NEUTRO.
EV calculado com `calibrated_probability` (COM deflacao #105).
Classificacao = confianca do modelo. EV = calibracao para apostas.

**Verificacao:** `grep -n "prob_for_class" backend/services/ev_classification.py`

### #108 — EMA no lambda_calculator

**Tipo:** Pipeline
Half-life: NORMAL=5, HIPER=3. Fallback: 60/40 se EMA falhar. NAO alterar half_life sem revalidacao Brier.

**Verificacao:** `grep -n "ema_from_averages" backend/modeling/lambda_calculator.py`
