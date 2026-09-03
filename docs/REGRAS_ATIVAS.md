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

### #108c — EMA real + clamp

**Tipo:** Pipeline
`extract_team_goals()` do DataFrame league-matches. Clamp: floor 70%, cap 130% season_avg.
Fallback: `ema_from_averages()` se sem dados. NAO remover clamp sem Brier.

**Verificacao:** `grep -n "extract_team_goals\|clamp_to_season" backend/modeling/ema_weights.py`

### #109 — Automacao Brier

**Tipo:** Pipeline (automacao)
Tabela: brier_history. Endpoints: /metrics/brier, /metrics/brier/history.
Cron: run_after_audit() pos-batch. MIN_N=20 por segmento.

**Verificacao:** `curl -s .../metrics/brier | python -c "import sys,json; print(json.load(sys.stdin).get('model_beats_house'))"`

### #110 — Scanner de valor (linhas expandidas)

**Tipo:** Pipeline
Gols: 0.5-5.5 (6 linhas Over + 6 Under). Cartoes: 1.5-6.5. Escanteios: 4.5-12.5 (ja abrangente).
Dedup mantido: 1 melhor por direcao (Over/Under) por mercado.

**Verificacao:** `grep -c "threshold.*stat_over" backend/services/ev_classification.py` (deve ser 6)

### #146 — EV obrigatorio no prompt Mistral

**Tipo:** Safety
**Relacionado:** #082, #096, #093

Mistral NUNCA deve afirmar "EV positivo" sem verificar: prob x odd > 1.0.
Formula explicita e exemplo numerico incluidos no prompt. Mercados com EV negativo
devem separar "chance de acerto" de "valor de longo prazo".

**Verificacao:** `grep -n "REGRA DE EV" backend/services/mistral_analysis.py` (deve retornar 1+ hit)

### #146b — Corredores no prompt Mistral

**Tipo:** Safety
**Relacionado:** #146, #113

Over X + Under Y do mesmo mercado devem ser apresentados como CORREDOR com faixa esperada.
Nunca listar como picks independentes.

**Verificacao:** `grep -n "REGRA DE CORREDORES" backend/services/mistral_analysis.py` (deve retornar 1+ hit)

### #152 — Deflação BTTS reduzida + Monotonidade cartões + Transparência rejeição

**Tipo:** Fix + Feature
**Relacionado:** #105, #106, #043, #120

1. BTTS: banda deflação reduzida pela metade em `_calibrate_and_deflate()` (lambda per-league já deflaciona)
2. Cards: adicionado ao enforcement de monotonidade em `_apply_line_safety_margin()` (ao lado de Corners e Goals)
3. UI: novo campo `rejected_insights` expõe mercados rejeitados com prob ≥ 55% — exibido no MatchAnalysis

**Verificação:** `grep -n "BTTS" backend/services/ev_classification.py | grep -i half` (deflação reduzida)
**Verificação:** `grep -n "Cards" backend/services/ev_classification.py | grep -i families` (monotonidade)

### #153 — Complementar league-matches com todays-matches para completude de jogos

**Tipo:** Fix
**Relacionado:** #089

`get_league_matches(page=1)` pagina por temporada — ligas avançadas podem ter jogos de hoje na página 2+.
Fix: SEMPRE buscar `_fallback_todays_matches()` como COMPLEMENTO (não apenas fallback).
Rich records (lambda/Poisson/xG) são preservados; todays-matches preenche jogos ausentes da page 1.
`_fallback_todays_matches()` agora aceita ISO dates além de "today"/"tomorrow".

**Verificação:** `grep -n "#153" backend/routes/fixtures.py` (complement logic)

### #154 — Paginar league-matches (todas as páginas) para análise completa

**Tipo:** Fix
**Relacionado:** #153

`get_all_league_matches()` busca TODAS as páginas com `max_per_page=1000`.
Cache in-memory TTL 15min + cache SQLite 2h por página.
Substitui `get_league_matches(page=1)` em fixtures.py.
todays-matches complement (#153) mantido como rede de segurança.

**Verificação:** `grep -n "get_all_league_matches" backend/services/footstats_client.py backend/routes/fixtures.py`

### #155 — Mapear period e anular minute durante HT no live

**Tipo:** Fix
**Relacionado:** #089

Backend `live.py` mapeia status API-Football (1H/HT/2H) → labels frontend (1T/HT/2T) via `_PERIOD_MAP`.
Quando `status in ("HT","BT")`, `minute=None` — nunca mostrar minuto no intervalo.
Frontend `computeLiveInfo()` retorna `{period:"HT", minute:null}` imediatamente quando backend diz HT.
`Math.max()` só se aplica a 1T/2T, nunca a HT.

**Verificação:** `grep -n "_PERIOD_MAP\|#155" backend/routes/live.py frontend/next/src/app/dashboard/page.tsx`

### #156 — Deflation default 0.90 para ligas sem calibração

**Tipo:** Pipeline (calibração)
**Relacionado:** #043, #105

`_DEFAULT_OU_DEFLATION = 0.90` em `poisson_matrix.py` — piso de 10% deflação para ligas sem calibração per-league.
Previne lambdas inflados quando `lambda_multiplier` não existe no DB.
Corners Over 6.5 (0/4) monitorado mas NÃO bloqueado — amostra insuficiente (N=4 < MIN_N=20, regra #079).

**Verificação:** `grep -n "_DEFAULT_OU_DEFLATION" backend/modeling/poisson_matrix.py`

### #157 — Bloquear pares Double Chance antagonistas

**Tipo:** Safety (Hard Constraint)
**Relacionado:** #098

Qualquer par de mercados Double Chance (DC 1X + DC 12, DC 1X + DC X2, DC 12 + DC X2) soma >100% por definição
(DC 1X + DC 12 = 100% + P(Home), DC 1X + DC X2 = 100% + P(Draw), DC 12 + DC X2 = 100% + P(Away)).
`_sao_complementares()` em `safety_validation.py` detecta pares DC distintos via `_DC_PATTERN` e bloqueia o pick com menor EV.

**Verificação:** `grep -n "_DC_PATTERN" backend/services/safety_validation.py`

### #158 — Direction rescue requer EV >= -5%

**Tipo:** Fix (Hard Constraint)
**Relacionado:** #127, #130, #106

VIA 2 direction rescue (#127) permitia classificar picks como NEUTRO (VIÁVEL) com EV arbitrariamente negativo (-10%, -20%) se a direção do modelo confirmasse. Isso gerava picks com perda esperada sistemática.
Fix: ambos os rescues (prob >= neutro_prob e prob >= rescue_prob) agora exigem `ev >= -0.05` (ou ev=None para mercados sem odd). Picks com EV < -5% são NO_BET mesmo com direção natural.

**Verificação:** `grep -n "#158" backend/services/ev_classification.py`

### #159 — Reliability N usa Brier acumulado

**Tipo:** Fix
**Relacionado:** #109, #079

`/health/reliability` lia `total_matches` do último batch do cron (um único dia), mostrando N=13 em vez do acumulado.
Fix: agora usa `calculate_snapshot()` do `brier_service`, que consulta TODOS os picks em `audit_results`.
Fallback: se `brier_service` falhar, volta ao comportamento anterior (batch único).

**Verificação:** `grep -n "calculate_snapshot\|#159" backend/routes/health.py`

### #160 — Late audit 02:00 BRT para Américas

**Tipo:** Infra (Automação)
**Relacionado:** #109, #089

Cron `late_audit` às 05:00 UTC (02:00 BRT) audita jogos das Américas que terminam após 23:45 BRT.
Liga MX, MLS, Copa Libertadores tipicamente terminam 00:00-01:30 BRT — fora do cutoff do today_audit.
Dedup natural: `ON CONFLICT (match_id) DO UPDATE` — se today_audit já auditou, late_audit atualiza sem duplicar.
EventBridge rule: `sportsbank-late-audit`, setup via `scripts/setup_late_audit.py`.

**Verificação:** `grep -n "late_audit" backend/cron_handler.py`

### #161 — Under-2.5 extra ×0.90 (#113) gated pós-#156

**Tipo:** Fix (Pipeline)
**Relacionado:** #113, #156, #105

#113 adicionava `×0.90` em `_calibrate_and_deflate()` para Under 2.5 (pior mercado Brier #104).
Pós-#156 (`_DEFAULT_OU_DEFLATION = 0.90` global + per-league `lambda_multiplier` no DB), o lambda já
vem deflacionado antes da deriv. Prob Poisson — a penalidade extra causava dupla deflação
(~19% cumulativa), zerando EV de gols e suprimindo picks mesmo a 75% raw.
Fix: aplicar `×0.90` apenas quando `_DEFAULT_OU_DEFLATION >= 1.0 AND league_id not in _LEAGUE_DEFLATION`
(caminho legado sem deflação de lambda). Kill-switch signal: se Lambda Erro > 1.0 na próxima auditoria,
reabrir #113. Instrumentação: 5 hooks (`GOLS-TRACE`, `GOLS-CLASSIFY`, `FLOOR-DROP`,
`CORRIDOR-DROPPED`, `V2-BUNDLES`) expõem raw→deflated→EV→classificação em CloudWatch.

**Verificação:** `grep -n "#161\|extra_under_applied" backend/services/ev_classification.py`

### #162 — SAFE/NEUTRO accuracy = None quando sem picks + EV metrics no relatório

**Tipo:** UI + Pipeline (observabilidade)
**Relacionado:** #069, #077, #043

`safe_accuracy_pct` e `neutro_accuracy_pct` retornam `None` (não `0.0`) quando `safe_total=0`/`neutro_total=0`.
Frontend e exportações exibem "N/A" ao invés de "0.0%" (que gerava alarme falso).
Guards adicionados em `AuditReportCard.tsx`, `localAudit.ts`, `deterministic_audit.py`.

Novas métricas no `batch_summary` (acurácia sem EV é enganosa — 80% a odd 1.10 perde dinheiro):
- `ev_medio_geral` — média de EV de todos os picks
- `ev_medio_positivo` — média de EV apenas de picks com EV > 0
- `total_picks_acionaveis` — picks com book_odd > 1.0 (odd real disponível)
- `total_picks_ev_positivo` — picks com EV estritamente > 0

Implementação: `compute_ev_summary()` em `backend/services/backtesting.py`. Exposto no topo de
`overall_notes` do relatório determinístico + campo no `/cron_audit` result.

**Verificação:** `grep -n "#162\|compute_ev_summary" backend/services/backtesting.py backend/cron_handler.py`

### #163 — Acurácia ponderada por 1/fair_odd

**Tipo:** Feature (métrica)
**Relacionado:** #162, #106

`compute_weighted_accuracy(picks)` em `backtesting.py` calcula `Σ(w_i · hit_i) / Σ(w_i)` com `w_i = 1/fair_odd_i`.
Picks difíceis (fair_odd alta) pesam mais; acertar favoritos óbvios não infla a métrica. Comparada com
acurácia bruta no relatório — se bruta alta e ponderada baixa, modelo está acertando só os "chutos".
Limitação v1: peso ignora `book_odd` — fair 2.0 a book 2.5 (EV+25%) pesa igual a fair 2.0 a book 1.8 (EV-10%).
v2 poderá usar EV ou (book_odd - fair_odd) como peso.

**Verificação:** `grep -n "compute_weighted_accuracy" backend/services/backtesting.py`

### #161 — Gate Under-2.5 penalty quando lambda já deflacionado

**Tipo:** Fix
**Relacionado:** #113, #105, #156

Under-2.5 extra ×0.90 (#113) redundante quando `_DEFAULT_OU_DEFLATION < 1.0` (#156) ou `league_id in _LEAGUE_DEFLATION`.
Gate em `_calibrate_and_deflate()`: penalty só aplica no path legado sem deflação lambda.
6 hooks de diagnóstico: GOLS-TRACE, **CALIB-TRACE (#216)**, GOLS-CLASSIFY, FLOOR-DROP, CORRIDOR-DROPPED, V2-BUNDLES. O #216 estendeu o trace às famílias que não tinham nenhum (1X2, Double Chance, escanteios, cartões) — justamente as que levam banda **inteira**. Os dois prefixos carregam `calib_iso=` e `tipo=`, então **`grep calib_iso` cobre todas as famílias**.
Kill switch: se Lambda Error > 1.0, revisitar.

**Verificação:** `grep -n "extra_under_applied\|GOLS-TRACE" backend/services/ev_classification.py`

### #162 — SAFE 0/0 exibe N/A + EV metrics no relatório

**Tipo:** Fix + Feature
**Relacionado:** #043, #079

`safe_accuracy_pct` e `neutro_accuracy_pct` retornam `None` quando total=0.
Backend: `_compute_assessment()` skip SAFE alarms, `_compute_threshold_evaluation()` retorna "N/A".
Frontend: tipo `number | null`, display "N/A" cinza, guards em comparações.
`compute_ev_summary()`: EV médio geral e positivo adicionados ao relatório.

**Verificação:** `grep -n "safe_acc is not None\|ev_metrics" backend/services/deterministic_audit.py backend/cron_handler.py`

### #163 — Accuracy ponderada por 1/fair_odd

**Tipo:** Feature
**Relacionado:** #162

`compute_weighted_accuracy()` usa peso = 1/fair_odd.
Favoritos (odd 1.50, w=0.67) pesam mais que underdogs (odd 4.00, w=0.25).
Integrado ao cron_handler batch_summary e deterministic_audit overall_notes.

**Verificação:** `grep -n "compute_weighted_accuracy" backend/services/backtesting.py backend/cron_handler.py`

### #165 — O/U half-band + EV floor 1% + cards corridor dedup

**Tipo:** Fix + Feature (Pipeline + UX)
**Relacionado:** #105, #152, #156, #161, #098

**Parte A — O/U half-band quando lambda pré-deflacionado:** `#105` band deflation (10-25%) foi
calibrado com `_DEFAULT_OU_DEFLATION = 1.0`. Pós-#156 (`_DEFAULT_OU_DEFLATION = 0.90`), lambda e prob
ficam duplamente deflacionados. Fix mirrors #152 BTTS logic: se `ou_defl < 1.0 OR _DEFAULT_OU_DEFLATION < 1.0`,
aplicar metade da banda (`deflation_band / 2.0`). Full band remains como fallback legacy.
Log `[OU-HALFBAND]` em cada aplicação. Validação real: NY City vs FC Cincinnati Over 2.5 passou de
EV −0.7% (NO_BET) → +11.7% (NEUTRO/SAFE) — simétrico com BTTS já passando.

**Parte B — EV Floor 1%:** picks com `0 ≤ EV < 1%` são ruído estatístico (dentro do erro do modelo).
Filtro em `classify_market()` força NO_BET com `ReasonCode.EV_FLOOR_DROP`. Inline (sem nova constante
global). Picks com EV negativo continuam tratados pelos gates existentes (neutro_ev, ev<-0.05).

**Parte C — Cards corridor dedup:** `_dedup_market_groups()` em `market_service.py` tratava `cards_over`
e `cards_under` separadamente → "Cartoes Over 2.5 + Cartoes Under 4.5" coexistiam como picks ruidosos.
Fix: se ambos `best_co` e `best_cu` existem e `prob_max_co + prob_max_cu > 105%` (mesmo threshold do #098),
manter só o de maior EV absoluto. Log `[CARDS-CORRIDOR]`.

**Kill switch:** Brier O/U regredir > 0.03 na próxima auditoria → reverter Parte A; picks SAFE caírem >30% → reverter Parte B.

### #166 — Odds Ingestion v2 (checklist break + per-league priority)

**Tipo:** Feature (Pipeline de ingestão)
**Relacionado:** #120 (odds enrichment), #144 (corners odds), #095 (cards odds)

**Gap raiz:** `extract_best_odds()` em `api_football_client.py` parava no primeiro
bookmaker com 1X2 (`if "home" in result: break`), perdendo O/U de ligas latinas
(MLS, Brasileirão A/B, Liga MX, Argentina, Colômbia) onde a cobertura de O/U
está fragmentada fora das top 5 casas europeias. Detalhado em
`docs/gap_analysis_api_football.md`.

**Fix (flag-gated via `ODDS_INGESTION_V2=true`):**
1. **Checklist break**: loop interno E externo quebram apenas quando
   `{home, over_25, btts_yes}` estão todos presentes. Flag-off preserva
   comportamento legado (break após 1X2).
2. **PRIORITY_BOOKMAKERS por liga** em `leagues_config.py`: MLS → DraftKings/
   FanDuel/Caesars; Brasileirão → Betano/Sportingbet; México/Argentina/Colômbia
   → 1xBet/local. Fallback = default europeu. Chave usa internal slug.
3. **Paginação** de 5 → 10 páginas (always-on, low-risk).
4. **Bet ID logging** (BET_ID_MAP vazio): loga IDs desconhecidos para validação
   futura via `curl /odds/bets`. Name matching continua primário.
5. **Endpoint `/api/debug/odds-coverage`** registrado somente quando flag on,
   protegido por header `X-Debug-Key` (match `ODDS_DEBUG_KEY` env var).
6. **Log `[ODDS-SLOW]`** se extract_best_odds levar > 1.0s.

**Kill switch:** `ODDS_INGESTION_V2=false` (env var; zero redeploy). Triggers:
`[ODDS-SLOW]` > 10% dos requests, ou Brier O/U > 0.25 pós-ativação.

**Verificação:** `grep -n "_ODDS_V2\|_ESSENTIAL_ODDS\|get_priority_bookmakers" backend/services/api_football_client.py backend/config/leagues_config.py`

**Verificação:** `grep -n "#165\|OU-HALFBAND\|EV_FLOOR_DROP\|CARDS-CORRIDOR" backend/services/ev_classification.py backend/services/market_service.py backend/models/market_output.py`

### #170-A — NB2 α corners calibrado per-league

**Tipo:** Pipeline (calibração)
**Relacionado:** #167 (Brier floor), #170 (diagnostic endpoint), #122 (cards NB2)

#170 Fase 1 mostrou que o α NB2 de produção (0.15 default) é **5-30× maior** que
o empírico (MLS 0.033, EPL 0.005). Resultado: variância NB2 2-4× maior que a
real → distribuição achatada → P(Over X.5) sub-confiante → Brier alto.

**Fix (flag-gated via `CORNERS_ALPHA_CALIBRATED=true`):**
- Novo grid `CORNER_ALPHA_GRID = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]`
  em `league_calibrator.py`
- Busca sequencial (não aninhada) — α não afeta média da projeção, só variância
- `_simulate_all_markets` agora aceita `corner_alpha` e usa `nb_cdf` da
  `backend/modeling/corners/negative_binomial` (mesmo NB2 que o predictor live usa)
- Quando α=0, `nb_cdf` degrada para Poisson → backward compat byte-exact com
  comportamento pré-#170-A
- Persistido como `corners_alpha` na `lambda_corrections` DB
- `predictor._get_alpha(league_id, _)` lê DB quando flag on, fallback
  artifact/0.15 quando off ou sem valor

**Kill switch:** `CORNERS_ALPHA_CALIBRATED=false` (env var). Predictor volta ao
path legado, calibrator ignora o loop. Valores em DB permanecem mas são ignorados.

**Verificação:** `grep -n "CORNER_ALPHA_GRID\|corners_alpha\|_ALPHA_CALIBRATED" backend/services/league_calibrator.py backend/modeling/corners/predictor.py`

### #171 — Proteção de banca: ECE/OddsVal haircuts, family cap, daily loss breaker

**Tipo:** Pipeline (proteção de capital)
**Relacionado:** #148 (Kelly), #149 (Oportunidade), #170-A (trigger), incidente P0 27/04

Após incidente P0 (50% banca em 24h causado por #170-A reduzindo α NB2 →
corners stake/dia subiu 5.93×), `bankroll_engine.py` recebeu 4 camadas de
proteção:

1. **ECE haircut (#171 FASE 2C):** quando ECE da liga ∈ [0.06, 0.12], reduzir
   Kelly até 25% (interpolação linear). Acima de 0.12 satura no máximo.
   Função `ece_haircut_factor(ece)`. None → 1.0 (neutro).

2. **OddsVal haircut (#171 FASE 2B):** quando OddsVal ∈ [-0.02, 0), reduzir
   Kelly até 30% (interpolação linear). Função `oddsval_haircut_factor(odds_val)`.
   OddsVal ≥ 0 ou None → 1.0.

3. **Market family cap (#171 FASE 2D):** `apply_family_cap(stakes, bankroll)`
   agrupa por família (corners/cards/goals/1x2) e escala se exceder cap diário.
   Defaults: corners 5%, cards 5%, goals 10%, 1x2 10%. **Deve ser chamada
   ANTES de `apply_daily_cap`.**

4. **Daily loss circuit breaker (#171 FASE 2A):** `check_daily_loss_breaker(daily_pnl, bankroll)`
   retorna True quando perda diária ≥ 15%. Backend expõe lógica; frontend
   deve respeitar o sinal.

**Notas operacionais:**
- ECE/OddsVal precisam ser propagados em `market_output` como `league_ece` /
  `league_odds_val`. Hoje não estão — haircuts retornam 1.0 (neutro). Pipeline
  upstream deve passar a popular esses campos.
- `apply_daily_cap` e `apply_game_cap` existem como library functions mas não
  são chamadas em backend hoje; integração é caller-side.

**Kill switches (env vars, sem redeploy):** `AUTO_APPLY_CONFIDENCE_MIN`,
`VIAVEL_FLOOR_PCT`, `CORNERS_ALPHA_CALIBRATED`, `ECE_HAIRCUT_THRESHOLD/MAX/CEILING`,
`ODDSVAL_HAIRCUT_FLOOR/MAX`, `MAX_CORNER_STAKE_DAY_PCT`, `DAILY_LOSS_BREAKER_PCT`.

**Verificação:** `grep -n "ece_haircut_factor\|oddsval_haircut_factor\|apply_family_cap\|check_daily_loss_breaker" backend/services/bankroll_engine.py`

### #180 — Display de picks segue family_winner por default (annotate, don't filter)

**Tipo:** Regra permanente (UX)
**Relacionado:** #171 (`_market_family`), #165 (cards corridor dedup), #098 (complementares >105%)

Toda lista de picks exposta ao frontend DEVE ser anotada por `select_family_winners()`
(em `backend/services/family_selection.py`) — agrupa por família via `market_family()`
(wrapper público de `_market_family`, regra #171) e marca `family_winner: bool` no
pick mais forte de cada família.

Princípio: **annotate, don't filter.** Picks não-winners mantêm probs, EV, odds,
classificação intactos. Display layer decide visibilidade. Telemetria/auditoria
continuam vendo o universo completo.

Ranking (tupla maior = melhor): `(classification_rank, ev, delta_brier, band_score)`.
- classification: SAFE > NEUTRO_QUALIFICADO > NEUTRO > INFORMATIVO > NO_BET
- band preferida: 60-70% > 50-60% ≈ 70-80% > 80%+ > <50%

**Kill switch:** `ENABLE_FAMILY_SELECTION_180=false` (env var, sem redeploy) — todos
os picks ficam `family_winner=True` mas `family` continua anotada.

**Verificação:** `grep -n "select_family_winners\|market_family" backend/services/family_selection.py backend/services/market_service.py backend/routes/market_analysis.py`

### #179 — Shadow mode obrigatório para mudanças de calibração/deflação

**Tipo:** Regra permanente (Governança de modelo)
**Relacionado:** #105 (deflação progressiva), #042 (backtesting), #079 (MIN_N=20),
#171 (incidente P0 −50% banca em 24h por calibração promovida sem shadow), #170-A.

Toda mudança em calibração ou deflação (band deflation `_band_deflation`, IsotonicRegression
em `calibrator.py`, fatores per-league em `_LEAGUE_DEFLATION`, NB2 α em corners, etc.) DEVE
ser introduzida em **shadow mode** antes de promover ao caminho live, atendendo
obrigatoriamente todos os critérios abaixo:

1. **Persistência paralela** dos valores live e shadow no `audit_results.predicted_probs`
   JSONB (campos `prob_deflated` + `prob_<feature>_<id>`), sem alterar comportamento live.
2. **Endpoint diff** dedicado (padrão `GET /metrics/shadow_<id>`) que computa Brier
   live vs shadow e retorna `improvement_pct`. Honra `MIN_N=20` (regra #079).
3. **Janela mínima de observação:** 2 semanas calendário com flag de shadow ativada
   em produção, acumulando picks reais.
4. **Gate de promoção:** `improvement_pct >= 3.0` no Brier out-of-sample do segmento
   afetado. Promoção parcial (apenas a banda/segmento que satisfaz o gate) é aceitável.
5. **Rollback obrigatoriamente via env var** (sem redeploy). O kill-switch deve estar
   documentado na entrada do REGISTRO. Default da flag = `false`.

Promoção sem shadow é **bloqueada** — exceções exigem entrada explícita em REGRAS_ATIVAS
descrevendo a razão (ex.: hotfix de segurança, não recalibração).

**Verificação:** `grep -n "SHADOW_BAND_50_60_V179\|apply_probability_deflation_with_shadow" backend/services/ev_classification.py`

### #186 — API-Football date guard + IDs corretos + transparência de fontes

**Tipo:** Fix + Regra permanente
**Relacionado:** #003, #120, #155, #166, B-011

1. **Nunca enviar date fora de Y-m-d à API-Football.** `_af_query_dates()` em
   `routes/fixtures.py` resolve today/tomorrow/week/ISO para datas Y-m-d válidas
   ("week" → datas derivadas dos records, cap 8). Qualquer novo chamador de
   `get_fixtures_by_date` DEVE passar por ele.
2. **IDs de sistemas distintos nunca na mesma variável.** `footystatsId` NÃO é
   `apiFootballFixtureId` — endpoints API-Football (`/injuries`, `/fixtures/lineups`,
   `/odds`) só podem ser chamados com o id da própria API-Football, disponível
   APÓS `_enrich_with_api_football()`. Enrichments que dependem dele vivem em
   `routes/fixtures.py`, nunca dentro de `build_records_from_matches()`.
3. **Payload declara as fontes.** Envelope `/fixtures` expõe `_sources`
   (api_football_matched, flags); `stats` expõe `probSources` + `predictionSource`
   (`odds_implied` | `ml_ensemble`). Novos campos derivados devem declarar origem.
4. **Ladder O/U de display com invariantes.** `compute_ou_stats()` garante
   over+under=100 e monotonicidade O0.5 ≥ … ≥ O4.5 (log `[OU-MONO]` ao clampar);
   identidade `lambdaTotal = lambdaHome + lambdaAway` via `lambda_stats_block()`.
5. **Cards tem categoria própria no market_reference_signal** (`cards_engine_default`)
   — nunca herda metadata do modelo over25 de gols.

**Verificação:** `grep -n "_af_query_dates\|_enrich_context_from_api_football\|_summarize_sources" backend/routes/fixtures.py`
**Verificação:** `grep -n "compute_ou_stats\|lambda_stats_block\|probSources" backend/services/fixtures_service.py`
**Verificação:** `grep -n "_CARDS_TOKENS\|cards_engine_default" backend/services/market_reference_signal.py`

### #187 — Odds por família única + display derivado dos lambdas + espelho 1X2 rotulado + linhas altas só com odd

**Tipo:** Fix + Regra permanente (Pipeline + UX)
**Relacionado:** #028, #064, #095, #103, #110 (emendado), #120, #166, #186

1. **Famílias de linhas (cartões/escanteios) vêm de UM único bet coerente.**
   `_extract_line_family()` rejeita bets por time/tempo/handicap e descarta
   escadas incoerentes (over não pode pagar menos em linha maior). NUNCA
   misturar linhas de bets/bookmakers diferentes na mesma família.
2. **Mercados são reclassificados após o enrichment de odds** (`_reclassify_after_odds`,
   exceto jogos finished). Odds que chegam depois do build DEVEM alcançar book_odd/EV.
3. **Display O/U e BTTS derivam dos lambdas do payload** — `overXXProb` de
   Poisson(`lambdaTotalOU`), `bttsProb` de (1-e^-λh)(1-e^-λa); invariantes
   over+under=100 e monotonicidade testadas. Esses campos são TAMBÉM o insumo
   raw dos picks de gols/BTTS (ev_classification) — mudanças neles são mudança
   de modelo. Potentials FS em `fsPotentials`; fusão em `bttsFusionProb`.
   `calibrate_match_stats` calibra APENAS corners (picks continuam com
   isotonic próprio, #106).
4. **1X2 é espelho de mercado ROTULADO (decisão de produto, opção b).** UI
   exibe "(mercado)" / "(modelo ML)" conforme `predictionSource`. Trocar para
   modelo próprio como 1X2 principal exige backtesting (#042) e nova entrada.
5. **Cartões > 2.5 e escanteios > 10.5 só exibem com odd real** (emenda ao
   #110: a linha expandida é escaneada, mas só exibida com suporte real).
6. **Nenhum sinal exibido com fonte `fallback_default`** — fontes válidas:
   league_classification, market_model, poisson_pipeline, corners_v2_governance,
   cards_engine_default, indeterminate.

**Verificação:** `grep -n "_extract_line_family\|_reclassify_after_odds" backend/services/api_football_client.py backend/routes/fixtures.py`
**Verificação:** `grep -n "compute_btts_from_lambdas\|lambdaTotalOU\|bttsFusionProb" backend/services/fixtures_service.py`
**Verificação:** `grep -n "fallback_default" backend/services/market_reference_signal.py` (0 hits em retornos)
**Verificação:** `pytest tests/unit/test_odds_family_187.py tests/unit/test_fixtures_stats_186.py -q`

### #189 — Recomendação da IA é subordinada à tabela de EV (Camada 7) + sem odd não há stake

**Tipo:** Fix + Regra permanente (Backend AI + UX)
**Relacionado:** #082, #096 (endurecido), #105, #106, #110, #146, #181 (enforcement), #187

1. **A `recomendacao_principal` DEVE ser exatamente um dos picks aprovados
   pelo pipeline.** A cláusula "ou um mercado complementar" do #096 está
   REVOGADA — não reintroduzir. Mercado fora da lista aprovada foi rejeitado
   pela tabela de EV deflacionado; recomendá-lo contradiz o que o operador vê.
2. **Camada 7 é enforcement, não observabilidade.** `_enforce_recommendation_contract`
   roda após a Camada 6 e SUBSTITUI a recomendação violadora por
   `mistral_contract.aligned_recommendation()`, construída do pick de maior EV
   entre os aprovados com os mesmos `prob_deflated_pct`/`odd`/`ev_pct` do display.
   Fail-open por design: falha do próprio enforcement devolve o texto original
   e nunca derruba a análise.
3. **Jogo sem pick aprovado → "Sem recomendação".** Nem prompt nem enforcement
   podem produzir um mercado quando o pipeline não aprovou nenhum, por mais
   alta que seja a probabilidade.
4. **#082 permanece intocado.** O enforcement restringe o que a narrativa pode
   citar; NÃO calcula probabilidade, NÃO reclassifica pick, NÃO altera EV.
5. **`_MARKET_PATTERNS` cobre as grafias que o modelo emite, não só as
   canônicas** — inclui a variante inglesa `Double Chance`, linha opcional em
   `Dupla chance` e `1X2 (Home|Away|Casa|Fora)`. Nova grafia observada em
   produção entra no padrão.
6. **Sem odd real não existe EV nem stake.** `calcStakeOportunidade` bloqueia
   com `odd <= 1` ANTES de qualquer tier (EV `0` como sentinela de "não medido"
   atravessava os `evBloqueio` negativos) e `StakeRow` oculta a linha inteira
   quando `bookOdd == null || <= 1`. Complementa o #187-5: linha suprimida por
   falta de odd nunca sugere valor.

**Verificação:** `grep -n "_enforce_recommendation_contract\|aligned_recommendation" backend/services/mistral_analysis.py backend/ai/mistral_contract.py`
**Verificação:** `grep -n "ou um mercado complementar" backend/services/mistral_analysis.py`
(0 hits — a frase só sobrevive negada no prompt e citada na docstring da Camada 7)
**Verificação:** `grep -n "Sem odd disponível" frontend/next/src/components/BankrollCard.tsx`
**Verificação:** `pytest tests/unit/test_recommendation_enforcement.py tests/unit/test_mistral_contract_181.py -q`

### #189-a/b/d — Deflação contínua por nós + cross simétrico de cartões + floor condicionado a EV ≥ 0

**Tipo:** Fix + Regra permanente (Modelo + Bankroll + UX)
**Relacionado:** #105 (evoluído), #106, #148 (emendado), #165, #179 (PROMOVIDO), #189

1. **Deflação é contínua por interpolação linear entre nós (`_DEFLATION_KNOTS`).**
   Substitui a função-degrau do #105 preservando a progressividade — NÃO
   reverter nem para uniforme (proibição 10) nem para degrau por banda:
   o degrau é não-monotônico em p·(1-d(p)) nas fronteiras (raw 60.0% exibia
   prob/EV piores que 59.9%). Novo nó só entra ancorado em auditoria e com a
   prova de monotonicidade refeita (d' máximo tal que 1 - d - p·d' > 0).
2. **#179 está PROMOVIDO:** nó de 0.55 = 0.05 (era 0.12 na banda 50-60%).
   Base: UNBLOCK_REPORT, banda subconfiante em -12.7pp com N=1796.
   `SHADOW_BAND_50_60_V179` é flag inerte; `/metrics/shadow_v179` reporta
   improvement 0 por construção (shadow ≡ live). Não remover a função shadow
   sem migrar o endpoint e o cron_handler.
3. **Cross de cartões é SIMÉTRICO:** `(hf + aa + af + ha)/2`, o mesmo padrão
   do corners_engine. Termos "against" exigem valor > 0 — sentinela 0.0 de
   feed não entra no blend (não arrastar λ para 0.8λ sem dado real).
4. **Floor do VIÁVEL (#148) só com EV ≥ 0.** Kelly ≤ 0 ⟺ EV ≤ 0 na odd atual;
   EV < 0 NUNCA recebe stake em NENHUM modo (Kelly ou Oportunidade) — o pick
   vira ordem-limite: `stake_reason="await_min_odd"`, `min_odd = 1/prob`
   (fair), UI exibe "Aguarde odd ≥ fair". EV = 0 exato mantém o floor.
   O "desconto por EV negativo" do modo Oportunidade está REVOGADO para
   EV < 0 (desconto não muda o sinal do valor esperado).

**Verificação:** `grep -n "_DEFLATION_KNOTS" backend/services/ev_classification.py`
**Verificação:** `grep -n "await_min_odd" backend/services/bankroll_engine.py frontend/next/src/components/BankrollCard.tsx` (backend; frontend usa "Aguarde odd")
**Verificação:** `grep -n "home_cards_against and away_cards_against" backend/modeling/cards_engine.py`
**Verificação:** `pytest tests/unit/test_deflation_continuous_189.py tests/unit/test_cards_cross_189.py tests/unit/test_viavel_floor_ev_189.py tests/unit/test_calibrator_179.py -q`

### #189-e — Stake por família com edge comprovado + calibração hierárquica + alias de liga

**Tipo:** Fix + Regra permanente (Bankroll + Modelo + Dados)
**Relacionado:** #056, #094, #148, #171 (reusa _market_family), #185 (alias), #189-a/b/d

1. **Stake segue `FAMILY_STAKE_POLICY` (bankroll_engine):** goals/1x2 = full;
   corners = só linhas extremas (Over ≥ 10.5 / Under ≤ 9.5); cards = none
   (INFORMATIVO: pick visível, stake 0, `stake_reason="family_gate_cards"`).
   Base: Δ Brier vs mercado em 5.505 picks (29-30/08/2026). Reativar stake de
   cartões EXIGE re-medição pós #189-b + fator de árbitro (janela 60 dias) com
   Δ positivo e nova entrada aqui. Frontend espelha via `familyStakePolicy()`.
2. **Calibração é hierárquica:** `mercado|liga → mercado|regime →
   mercado|global → família|liga → família|global → passthrough`. Pools por
   família treinados em `retrain_all_calibrators` com o mesmo protocolo
   anti-piora de Brier. Cartões pertencem a CALIBRATED_MARKETS — não remover.
3. **Lookup de `_LEAGUE_DEFLATION` passa por `_league_deflation_factor()`**
   (resolve alias #185 antes do get). Novo fator de liga = nova entrada com o
   id CANÔNICO.
4. **IDs de liga no audit_results são canônicos** — merges em
   `migrate_189e_unify_league_ids.py` (idempotente; rodar após deploy).
   Novo alias observado = adicionar ao LEAGUE_LABEL_MERGES e re-rodar.
5. **Fetch diário usa `ACTIVE_LEAGUES()`** (13 ligas; 9 inativas com
   `active: false` em leagues.ts). Reativar liga = flag + entrada aqui.

**Verificação:** `grep -n "FAMILY_STAKE_POLICY\|family_stake_allowed" backend/services/bankroll_engine.py`
**Verificação:** `grep -n "train_family_calibrator\|_FAMILY_PREFIX" backend/modeling/calibrator.py`
**Verificação:** `grep -n "_league_deflation_factor" backend/services/ev_classification.py`
**Verificação:** `pytest tests/unit/test_family_gate_189e.py -q`

### #114/#203 — O backend fica ATRÁS da Lambda Function URL, nunca do API Gateway

**Tipo:** Regra permanente (Infra)
**Relacionado:** #114 (origem, 2026-04-04), #203 (guarda, após regressão)

1. **`PY_BACKEND_URL` DEVE apontar para `*.lambda-url.*.on.aws`.** O API Gateway
   HTTP API v2 corta a integração em **30s — limite duro que não se eleva por
   configuração**. A Function URL respeita o timeout da própria Lambda (60s).
2. **O sintoma da violação é enganoso e já custou uma investigação inteira:**
   ligas COM jogos (caras de montar) estouram 30s e somem da tela; ligas SEM
   jogos respondem em ~2s e aparecem. Parece "algumas ligas não carregam".
3. **`isApiGatewayBackend()` é a guarda** — loga no boot, expõe `backendKind`
   no debug e nomeia a causa na mensagem de erro. Não remover: sem ela a
   regressão volta a ser silenciosa (foi o que aconteceu entre #114 e #203).
4. **503 em ~30s cravados nunca é cold start.** É o teto do gateway.

**Verificação:** `grep -n "isApiGatewayBackend" frontend/next/src/lib/backend.ts`
**Verificação (produção):** `curl -s -o NUL -w "%{http_code} @ %{time_total}s" "$PY_BACKEND_URL/fixtures?leagues=<liga-com-jogos>&date=today"` — 503 em ~30s = gateway errado

### #208 — O encolhimento de amostra pequena vale para os DOIS lados da conta

**Tipo:** Regra permanente (Modelo)
**Relacionado:** #064 (origem da regressão), #201 (baseline por lado), #208

1. **`λ = baseline × ataque_relativo × defesa_relativa` — os dois fatores vêm da
   mesma fonte e da mesma amostra, logo recebem o MESMO encolhimento.** Aplicar
   regressão à média só no ataque é um viés estrutural, não uma simplificação.
2. **Limiar: 8 jogos DAQUELE recorte** (casa-apenas ou fora-apenas, via
   `_jogos_do_recorte`), peso linear `n/8`. Ajustável por
   `LAMBDA_SHRINK_MIN_GAMES` sem deploy — **não alterar o default sem medição
   contra o mercado por faixa de rodadas jogadas**, que foi como o viés apareceu.
3. **Acima do limiar o λ é byte a byte o de antes** (|Δλ| = 0,000 verificado em
   5.625 combinações). O #208 não toca no regime que já funciona.
4. **Contagem AUSENTE devolve peso 1,0. Amostra vazia CONHECIDA (0) devolve 0,0.**
   Não unificar os dois casos: a FootyStats nem sempre manda `games_played`, e
   encolher por ausência de campo apagaria o time inteiro — trocaria um viés por
   um apagamento.

**Verificação:** `pytest tests/unit/test_encolhimento_simetrico_208.py -q`
**Verificação (limite):** amostra 0 jogos deve devolver exatamente os baselines
`avg_goals_scored_by_home/away_teams` da liga.

### #209/#210 — O contrato do modelo é executável, e roda sobre a SAÍDA MONTADA

**Tipo:** Regra permanente (QA)
**Relacionado:** #209 (auditor), #210 (manifesto), #187/#189-f/#201 (o buraco que motivou)

1. **Teste unitário verde não é sistema correto.** Cada etapa pode cumprir a
   própria promessa e a composição estar errada — foi #201 (dupla contagem entre
   duas etapas corretas) e #189-f (extração correta, cópia ausente). O auditor
   verifica o artefato que o `/fixtures` devolve, não as funções.
2. **A matemática de referência do auditor é reimplementada de propósito.** Um
   auditor que importa a função auditada concorda com ela inclusive quando ela
   está errada. **Não "deduplicar" `p_over25`/`p_btts`/`lambda_minimo_para` de
   `auditor_premissas.py` contra as do pipeline** — a duplicação é o mecanismo.
3. **Premissa nova entra como afirmação falsificável com o número que a
   falsifica**, e com severidade (CRÍTICO = número impossível, o sistema está
   mentindo; ALTO = premissa do modelo violada; MÉDIO = diagnóstico degradado).
4. **Campo novo da FootyStats consumido no código entra no manifesto (#210)** —
   CONSUMIDO / PLANEJADO / DESCARTADO. Campo consumido fora do manifesto, ou
   campo do manifesto que perdeu o consumidor, falha a premissa estrutural.

**Verificação:** `python3 scripts/verificar_manifesto.py` (exit 0 = de acordo)
**Verificação:** `python3 scripts/auditar_premissas.py --arquivo <payload.json>`
(exit 1 com violação crítica, 0 sem — serve de gate de CI direto)

### #213 — Placar exibido é observação, nunca preenchimento

**Tipo:** Regra permanente (Live)
**Relacionado:** #194 (relógio fiel ao feed), #213

1. **Quando a promoção a `live` foi NOSSA** (status bruto não dizia `live`), o
   placar daquela linha **não é observação** — a FootyStats só preenche
   `homeGoalCount` quando a partida termina. 0-0 nesse caso vira `score=null`.
2. **Preservados sempre:** placar com gol, 0-0 vindo de fonte que declara
   `live`, e 0-0 de jogo encerrado. A correção é estreita de propósito.
3. **Ausência e zero são o mesmo caso aqui.** Um guard que só trata `None`
   deixa passar o `0` pelo mesmo caminho — foi exatamente o defeito.
4. **O relógio não depende do placar.** `score=null` com `minute` preenchido é
   o estado correto de um jogo em andamento sem dado de gol.

**Verificação:** `pytest tests/unit/test_placar_ao_vivo_falso_213.py -q`
**Verificação (produção):** rodada inteira 0-0 após o minuto 25 dispara a
premissa `placar_ao_vivo_e_observado` do auditor (#209) como CRÍTICO.

### #216 — Isotônico e deflação são passos distintos e devem ser medidos separados

**Tipo:** Regra permanente (Calibração / QA)
**Relacionado:** #105 (deflação por nós), #106 (proibição #11), #200 (`.pkl` vazados), #215 (âncora)

1. **`calibrated_probability` é o PRODUTO de dois passos:** `calibrate_prob()`
   (o isotônico, os `.pkl` que o #200 congelou) **e** a deflação progressiva por
   bandas (#105) mais o fator por liga. Medir só o produto atribui a um o que é
   do outro — quase aconteceu na primeira leitura do #215.
2. **`iso_probability` e `banda` viajam no payload** (`to_legacy_mercado`), e o
   comparador do #215 reporta os dois. **Não remover:** sem eles a pergunta do
   #200 volta a ser inrespondível.
3. **A prob deflacionada é deliberadamente conservadora** (proibição #11: EV usa
   deflacionada). Compará-la com frequência empírica e concluir "calibra pior" é
   erro de categoria — a comparação válida contra a âncora é a **isotônica**.
4. **`iso == raw` significa calibrador INERTE**, não calibrador bom. Nesse caso
   a discussão de quarentena dos `.pkl` perde o objeto.
5. **Todo mercado deixa rastro.** Antes do #216, 1X2, Double Chance, escanteios
   e cartões passavam pelo mesmo caminho sem log — e são exatamente os que levam
   banda **inteira**, o corte maior (medido: `Cartoes Over 1.5` 0,8767 → 0,6575).

**Verificação:** `pytest tests/unit/test_separacao_calibrador_216.py -q`
**Verificação (produção):** `--filter-pattern calib_iso` no CloudWatch cobre as
duas famílias de prefixo; `python scripts/comparar_ancora.py` imprime o veredito
do isotônico separado do veredito do produto.

### #217/#218 — Todo veto tem consumidor; toda publicação vira linha de ledger

**Tipo:** Regra permanente (Publicação / QA)
**Relacionado:** #189-f (extração sem consumo), #200 (vazamento), #208 (ausência ≠ zero), #216

1. **Sinal de veto sem leitor é defeito, não redundância.** `predict_corners`
   marcava `no_bet` em 4 situações e ninguém lia. Ao adicionar qualquer sinal de
   bloqueio, o teste que importa é o do **consumidor**, não o do produtor.
2. **Pick vetado não some — vira NO_BET com reason code visível.** Sumir da tela
   impede auditar quantos foram vetados e por quê.
3. **Escopo do veto é explícito:** `insufficient_data` e `restricted_market`
   valem para a família; filtros de linha valem só para a linha e o lado.
4. **Ausência de contagem não é início de temporada** (`season_data_state`:
   OK / EARLY / UNKNOWN). Mesma regra do #208 no λ.
5. **`audit_results` NÃO é fonte de treino** — `INSERT OR REPLACE` guarda o
   recomputado pós-jogo. A fonte limpa é `prediction_ledger`, append-only, com
   as **entradas** gravadas junto da saída. Não introduzir UPDATE/DELETE nele.

**Verificação:** `pytest tests/test_217_veto_escanteios.py tests/test_218_prediction_ledger.py -q`

### #219/#220 — EV se compara com probabilidade, e resolução vem antes de calibração

**Tipo:** Regra permanente (Odds / Calibração)

1. **`1/odd` não é probabilidade** — soma mais que 1. Comparar EV contra ela
   confunde "perder para a margem" com "perder para a realidade".
2. **Margem é detector, não só viés a remover.** Fora de 1–12% a odd é velha ou
   corrompida (#214), e não deve derivar preço de outro mercado.
3. **Margem suposta gera de-vig circular.** Derivar a odd Under de uma constante
   e depois de-vigar o par devolve exatamente a constante.
4. **Inclinação antes de calibrador.** Nenhum método de calibração cria
   resolução: todos são transformações monótonas de uma dimensão. Com
   inclinação perto de zero, a pergunta deixa de ser "como calibrar" e passa a
   ser "quais mercados têm resolução para publicar".
5. **Bootstrap por jogo, nunca por pick**, e Benjamini-Hochberg nas 440 células.

**Verificação:** `pytest tests/test_219_devig.py tests/test_220_inclinacao.py -q`
**Verificação (suíte):** `pytest tests/ -q` deve coletar **753** testes — se
voltar a 489, a coleta quebrou de novo em algum import de nível de módulo.


### #222 — Protocolo SDD: proibido afirmar efeito sem prova no payload montado

**Tipo:** Regra permanente (Engenharia / QA)
**Relacionado:** #189-f (extração sem cópia), #209/#210 (saída montada e manifesto), #217 (veto sem leitor), #221

1. **A intenção do código não é o comportamento do sistema.** É terminantemente
   proibido afirmar em prompt, PR ou commit que um patch "remove flag X",
   "corrige cálculo Y" ou "reativa Z" com base na leitura do código escrito.
   Toda afirmação de efeito exige **medição empírica antes/depois** sobre o payload
   real de fixtures/partida.
2. **Auditoria obrigatória dos 4 Elos de Dados:**
   Toda nova chave consumida via `.get("chave")` exige a comprovação na Spec:
   - *Elo 1 (Origem):* Onde o dado bruto nasce (ex: FootyStats client / DB).
   - *Elo 2 (Montagem):* Onde a chave é explicitamente inserida no record em `routes/fixtures.py` ou `fixtures_service.py`.
   - *Elo 3 (Consumo):* As linhas exatas que leem a chave.
   - *Elo 4 (Impacto Real):* Diff comprovado no payload que o endpoint devolve.

   Para chaves do **record** (`match_data`/`record`/`stats`/`league_stats`), os
   elos 2 e 3 sao provados por maquina: `pytest tests/test_223_contrato_record.py`
   — chave lida e nunca escrita **bloqueia**. Pedir prova em prosa para algo que
   um teste decide e convidar o teatro. A comprovacao escrita fica restrita ao
   que o contrato ainda nao cobre: o dicionario de contexto do
   `mistral_analysis.py`/`ai_analysis.py`, que tem outra forma e merece contrato
   proprio.
3. **Critério de Aceite Falsificável Pré-Implementação (SDD):**
   Antes de editar arquivos, o plano deve declarar o critério de aceite com um
   teste que falhe antes e passe depois (ex: `season_data_state` mudar de
   `EARLY_SEASON_FALLBACK` para `OK` em liga com N rodadas).
4. **Patch que AFIRMA efeito e produz payload idêntico está rejeitado** —
   indica elo quebrado na esteira de dados, mesmo com a função consumidora
   perfeita. **A recíproca não vale:** patch que declara na Spec que *não* altera
   número — instrumentação (#212), ou funcionalidade atrás de flag desligada
   (#218 `PREDICTION_LEDGER_ENABLED=0`, #219 `DEVIG_ENABLED=0`) — tem o critério
   invertido: payload idêntico é o **aceite**, e qualquer diferença é regressão.
   A versão anterior desta regra, sem essa ressalva, reprovaria os três patches
   citados, que estão corretos e nasceram desligados justamente por prudência.
5. **O contrato vale nas DUAS direções.** Sinal produzido sem leitor é defeito,
   não redundância: `predict_corners` marcava `no_bet` em quatro situações e um
   `grep no_bet` no classificador devolvia zero (#217) — o veto existia e não
   vetava, publicando EV de +31,3% e +34,7% em mercado que o próprio motor havia
   rejeitado. Ao adicionar qualquer sinal de bloqueio ou campo novo no payload,
   o teste que importa é o do **consumidor**, não o do produtor.
6. **Teste que constrói a própria entrada não testa o contrato — testa a si
   mesmo.** Ao validar consumo de chave, a entrada tem de vir do produtor real
   (`build_records_from_matches`), nunca de um dicionário de conveniência montado
   dentro do teste. O caso: o teste do #218 fabricava um `stats` contendo
   exatamente as chaves erradas que o ledger lia (`cardsLambda`,
   `homeMatchesPlayed`, `dataAgeHours` — nenhuma existe no record), então
   **concordava com a suposição do código** e ficava verde enquanto a produção
   gravaria 6 de 10 entradas nulas. Um dicionário escrito por quem escreveu o
   consumidor sempre contém as chaves que o consumidor espera.

**Verificação:** `python3 scripts/testar_payload_diff.py --antes a.json --depois d.json` (exit 1 quando idêntico)
**Verificação (gate automático):** `pytest tests/test_223_contrato_record.py -q` — roda no CI sem configuração adicional, porque o `pytest -q` do workflow já varre `tests/`.
**Verificação (premissas da saída):** `python3 scripts/auditar_premissas.py --arquivo <payload.json>`

---

### #225-c — Proibido `.get(k, alternativa)` no caminho de decisao

**Tipo:** Hard Constraint
**Relacionado:** #201, #208, #217, #225-b (as quatro instancias), #223 (contrato do record)

`d.get(k, alternativa)` so usa a alternativa quando a chave esta **AUSENTE**. Quando
ela existe valendo `None` — a regra, nao a excecao, porque
`build_records_from_matches` monta o record com o dicionario inteiro — o `get`
devolve `None` e a alternativa e **inalcancavel por construcao**. Nao e um caso
raro: e um caso impossivel de acontecer.

Nos modulos que decidem numero publicado (lambda, veto, classificacao, stake) a
forma encadeada esta **proibida**. Use `backend/utils/valores.py`:

```python
from backend.utils.valores import primeiro_valido, pegar

primeiro_valido(a.get("x"), b.get("y"), padrao=0)   # dicionarios diferentes
pegar(d, "x", "y", padrao=0)                        # mesmo dicionario
```

Os dois pulam `None` e **preservam `0`, `0.0`, `""` e `False`** — `a or b` nao
preserva, e 0 escanteios e um resultado, nao uma ausencia.

Fora do caminho de decisao a forma degrada narrativa e exibicao: e divida
registrada, nao regressao bloqueante.

**Excecao com motivo declarado:** `backend/modeling/corners/features.py` (13
confirmadas) fica de fora ate haver retrain. `predictor.py` calcula as features
em tempo de servico e carrega `.pkl` treinados com as features do jeito errado;
corrigir so um lado cria skew treino/servico.

**Verificacao (gate automatico):** `pytest tests/test_225c_fallback_morto.py -q` —
varre por AST os 7 modulos de decisao e falha se a forma voltar. Inclui
`test_a_guarda_esta_mesmo_olhando_arquivos`, que impede a guarda de morrer em
silencio quando um caminho e renomeado.
**Verificacao (inventario):** `python3 scripts/varredura_get.py [--detalhe]` — cruza as
cadeias encontradas por AST com as chaves que o produtor cria em **todos** os
cenarios do contrato do #223. Confirmadas hoje: **38** (eram 52).
**Verificacao (efeito na saida):** `python3 scripts/ab_motores.py [--ref <commit>]` —
carrega a versao ANTES direto do git e roda o mesmo payload nos dois modulos.
