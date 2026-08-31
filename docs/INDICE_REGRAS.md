# INDICE DE REGRAS — SportsBankZu Pro

> Uma linha por regra. Status **ATIVA** = regra permanente em `REGRAS_ATIVAS.md`.
> Detalhes completos em `REGISTRO_CORRECOES.md`.

| # | Status | Tipo | Resumo |
|---|--------|------|--------|
| 001 | Corrigido | Fix | Defesa contra odds alucinadas pela Mistral |
| 002 | Corrigido | Fix | Reincidencia Under 4.5 @1.95 alucinada |
| 003 | Corrigido | Feature | Integracao API-Football v3 |
| 004 | Corrigido | Fix | Auditoria API-Football precisao lesoes |
| 005 | Corrigido | Fix | Placar ao vivo congelado em 0-0 |
| 006 | **ATIVA** | Fix + Regra | Checklist 7 pontos para novo mercado |
| 007 | Corrigido | Fix | Livescore 0-0 ligas arabes |
| 008 | Corrigido | Fix | Placar "- : -" em jogos ao vivo |
| 009 | Corrigido | Fix | Jogo ao vivo excluido quando FootyStats remove |
| 010 | Corrigido | Fix | Status "started" nao reconhecido como "live" |
| 011 | Corrigido | Fix | Conformidade API-Football rate limit/timezone |
| 012 | Corrigido | Feature | Apostas em Sistema (System Bets) |
| 013 | Corrigido | Fix | Aba Duplas nao carrega jogos |
| 014 | Corrigido | Feature | Corner Progress Bar |
| 015 | Corrigido | Fix | CornerProgressBar invisivel Path B |
| 016 | Corrigido | Fix | Corners ausentes no contexto Mistral |
| 017 | Corrigido | Fix | Extracao stats ao vivo + vies BTTS |
| 018 | Corrigido | Fix | Remocao submodule worktrees CI |
| 019 | Corrigido | Fix | Liga dinamarquesa misturada + Duplas 504 |
| 020 | Corrigido | Fix | Auditoria duplas escanteios ERROU |
| 021 | Corrigido | Fix | Jogos dinamarqueses misturados EPL |
| 021a | Corrigido | Fix | CornerProgressBar ligas sem stats |
| 021b | Corrigido | Fix | Placar/minuto nao atualizam |
| 021c | Corrigido | Fix | CornerProgressBar parser robusto |
| 022 | Corrigido | Fix | League mismatch correcoes "ALL" |
| 023 | Corrigido | Fix | TypeScript period type |
| 024 | Corrigido | Feature | Filtros status, ordenacao, separador |
| 025 | Corrigido | Fix | Dropdown tema escuro + PL unknown |
| 026 | Corrigido | Fix | Jogos duplicados apelido vs nome |
| 027 | Corrigido | Fix | Fallback ID match indice numerico |
| 028 | **ATIVA** | Pipeline | Pipeline preditivo 5 camadas V2 |
| 029 | Corrigido | Feature | ML pipeline improvements |
| 030 | Corrigido | Feature | ML retrain validate workflows |
| 031 | Corrigido | Feature | Market Reference Signal governance |
| 032 | Corrigido | Fix | Live score stuck 0-0 |
| 033 | Corrigido | Feature | Corners Engine v2 bidirecional |
| 034 | Corrigido | Feature | Corner Betting Governance Framework |
| 035 | Corrigido | Feature | Ativacao Pipeline V2 M1-M6 |
| 036 | Corrigido | Fix | Deduplicacao mercados corners/gols |
| 037 | Corrigido | Fix | Formula overround Under + redundancia |
| 038 | Corrigido | Fix | Odds Under reais + enrichment |
| 039 | Corrigido | Feature | Prompt Mistral +40 campos |
| 040 | Corrigido | Feature | UI EV% real + redesign AI |
| 041 | Corrigido | Feature | Auditoria lambda root cause |
| 042 | **ATIVA** | Hard Constraint | Thresholds so com backtesting |
| 043 | **ATIVA** | Circuit Breaker | SAFE desativado + deflacao lambda 15% |
| 044 | Corrigido | Feature | AuditReportCard + League Confidence |
| 045 | Corrigido | Feature | Expansao 5->20 modelos binarios |
| 046 | Corrigido | Fix | Health/DB endpoint |
| 047 | Corrigido | Fix | Mistral timeout + Copa do Brasil |
| 048 | Corrigido | Fix | Live fallback "- : -" -> 0-0 |
| 049 | Corrigido | Fix | Format string bug market_models |
| 050 | Corrigido | Feature | Relatorio V3 backtesting |
| 051 | Corrigido | Fix | Lambda error null backtesting |
| 052 | Corrigido | Feature | Calibracao por liga |
| 053 | Corrigido | Fix | Lambda underestimation Dixon-Coles |
| 054 | Corrigido | Fix | BTTS calibration + SAFE save |
| 055 | Corrigido | Feature | Calibracao completa todos mercados |
| 056 | Corrigido | Fix | Extracao cards/corners/BTTS |
| 057 | Corrigido | Fix | Governanca testes documentacao |
| 058 | Corrigido | Feature | Deflacao per-league producao |
| 059 | Corrigido | Feature | Export/import calibracoes S3 |
| 060 | Corrigido | Fix | Live scores resilience cache |
| 061 | Corrigido | Fix | _prob() priorizar Poisson deflacionado |
| 062 | Corrigido | Fix | Team name mismatch EVs absurdos |
| 063 | Corrigido | Fix | EVs absurdos LAMBDA_MIN + fuzzy |
| 064 | Corrigido | Feature | Fallback temporada anterior |
| 065 | Corrigido | Fix | EVs absurdos 1X2 Poisson + cap |
| 066 | Corrigido | Fix | Ligas desaparecendo timeout fan-out |
| 067 | Corrigido | Fix | Live-score swap + proxy timeout |
| 068 | Corrigido | Fix | CornerProgressBar invisivel ao vivo |
| 069 | Corrigido | Fix | Auditoria Brier/SAFE per-league |
| 070 | Corrigido | Fix | /live-scores nao lia corners FootyStats |
| 071 | Corrigido | Fix | Jogos "VIVO 2T 90'" indefinidamente |
| 072 | Corrigido | Fix | Router AI Mistral mock |
| 073 | Corrigido | Fix | Migracao Mistral v3.7->v3.0 |
| 074 | Corrigido | Infra | Vercel Fluid Compute maxDuration |
| 075 | Corrigido | Fix | Endpoints auditoria 404 |
| 076 | Corrigido | Fix | /live-scores 0 jogos filtrados |
| 077 | Corrigido | Fix | CornerProgressBar visual + Brier |
| 078 | Corrigido | Feature | Dixon-Coles Complete Model |
| 078v | Corrigido | Fix | Validacao rho Dixon-Coles |
| 078r | Corrigido | Infra | Limpeza ligas 37->22 + recalibracao |
| 079 | **ATIVA** | Hard Constraint | MIN_N_BRIER=20, MIN_N_RELIABILITY=30 |
| 080 | Corrigido | Feature | Rename Classifications + Tooltips |
| 081 | Corrigido | Feature | Corners Engine v2 NB2 + barra 3 zonas |
| 082 | **ATIVA** | Contrato | Mistral EXCLUSIVAMENTE narrativa |
| 083 | Corrigido | Feature | Post-Match Diagnostic Engine V4.0 |
| 084 | Corrigido | Feature | Metricas no cron loop + baseline odds |
| 085 | Corrigido | Feature | Cartoes como mercado de picks |
| 085b | Corrigido | Fix | Avaliacao pos-jogo cartoes + NB2 v2 |
| 086 | Corrigido | Fix | Dupla contagem lambda cartoes |
| 087 | Corrigido | Fix | Standings ligas calendario-ano |
| 088 | Corrigido | Fix | Highlight odds pipeline |
| 089 | **ATIVA** | Fix + Regra | date_range deve usar BRT (nao UTC) |
| 089b | Corrigido | Fix | Dedup linhas cartoes |
| 090 | Corrigido | Fix | Fallback Mistral HTTP 400 |
| 090b | Corrigido | Fix | Auto-fetch AI ao selecionar jogo |
| 091 | **ATIVA** | Fix + Regra | Resolver alias ANTES de gerar match IDs |
| 092 | Corrigido | Fix | _extract_date BRT (mesma classe #089) |
| 093 | **ATIVA** | Safety | Mistral nao recomenda mercado sem odd |
| 094 | Corrigido | Feature | Bankroll editavel + Quarter Kelly |
| 095 | Corrigido | Feature | Odds reais cartoes API-Football |
| 096 | **ATIVA** | Safety | 6 camadas anti-alucinacao Mistral |
| 097 | Corrigido | Fix | Standings highlight fuzzy matching |
| 098 | **ATIVA** | Safety | Complementares >105% bloqueados |
| 099 | **ATIVA** | Safety | Filtro acoes auditoria por regras |
| 100 | Corrigido | Feature | ECE calibracao por faixa |
| 101 | Corrigido | Feature | Dashboard Confiabilidade Princeton |
| 102 | Corrigido | Feature | Tracker PostgreSQL + API clients |
| 102b | **ATIVA** | Infra | Checklist variaveis ambiente Lambda |
| 103 | **ATIVA** | Fix + Regra | book_odd obrigatorio para stake (nao odd_minima) |
| 104 | **ATIVA** | Fix + Regra | Corner lambda escala total (nao per-team) |
| 105 | **ATIVA** | Calibracao | Deflacao progressiva por banda + per-league |
| 106 | **ATIVA** | Fix + Regra | Raw prob para classificacao, deflated para EV |
| 107 | Corrigido | Feature | ELO service (coleta, sem integracao lambda) |
| 108 | **ATIVA** | Feature | EMA half-life=5 no lambda calculator |
| 109 | **ATIVA** | Feature | Brier Score automatico + persistencia |
| 110 | **ATIVA** | Feature | Scanner expandido 0.5-5.5 gols, 1.5-6.5 cards |
| 111 | Corrigido | Feature | 1X2/DC markets scanner |
| 112 | Corrigido | Perf | Cache EMA goals O(N) single pass |
| 112b | Corrigido | Infra | Lambda 1024MB + cache warm fix |
| 113 | **ATIVA** | Fix | Cron live + corredor cartoes + duplas + Under 2.5 |
| 114 | Corrigido | Infra | Lambda Function URL (elimina timeout 30s) |
| 115 | Corrigido | Perf | ThreadPoolExecutor paralleliza jogos em batches |
| 116 | Corrigido | Fix | EV fixo +40.0% em escanteios — null EV when suspicious |
| 117 | Corrigido | Feature | Redesign aba Destaques — Valor Detectado + Apenas Analise |
| 118 | Corrigido | Fix | Cards Over 0% accuracy — totalCards=0 (campos nao populados) |
| 120 | Corrigido | Fix | Odds enrichment: correct fixture ID + expand O/U lines |
| 121 | Corrigido | Perf | API-Football cache TTLs otimizados — 8500 to ~3000 req/dia |
| 122 | Corrigido | Fix | Auto-finish incorreto quando /live-scores retorna vazio |
| 117b | Corrigido | Fix | DestaquesDoDia presets definem valor (nao somam) |
| 119 | **ATIVA** | Fix + Regra | Duplas: elegibilidade + correlacao + corredor + cap + diversidade |
| 119a | Corrigido | Perf | Loading progressivo frontend (onBatchReady, merge incremental) |
| 119b | Corrigido | Perf | Paralelizar FootyStats dentro da liga (ThreadPoolExecutor 3 workers) |
| 119c | Corrigido | Perf | Fan-out tuning (LEAGUES_PER_BATCH 3→5, MAX_CONCURRENT 4→2) |
| 119d | Corrigido | Perf | SQLite WAL mode cache FootyStats + API-Football |
| 119e | Corrigido | Fix | Lambda error /2 (media per-team, nao soma) |
| 119f | Corrigido | Fix | Backtest window 14→30 dias (N=15→437) |
| 119g | Corrigido | Perf | CORNER_BRIER_GRID granularidade fina 0.83-0.97 |
| 119h | Corrigido | Perf | CARDS_DEFLATION_GRID inclui inflacao >1.0 |
| 120 | **ATIVA** | Fix + Regra | Margem seguranca 5% selecao linha escanteios+gols |
| 121 | **ATIVA** | Fix + Regra | Enforce monotonicidade probs corners (P(Over N+1) <= P(Over N)) |
| 122 | **ATIVA** | Fix + Regra | Calibrador cards NB2 + Brier bilateral + override condicional + linhas expandidas |
| 123 | **ATIVA** | Fix + Regra | Direcao natural projFT + risk penalty + shrinkage assimetrico corners |
| 124 | **ATIVA** | Fix | Extrair cornersAgainst + cardsAgainst do FootyStats + fallback historico |
| 124b | Corrigido | Fix | xG blend conectado no pipeline de gols (calibrador → lambda) |
| 126 | **ATIVA** | Fix + Regra | Classificacao por direcao natural — gols, corners, cards (VIA 2) |
| 127 | **ATIVA** | Fix + Regra | VIA 2 antes do NO_BET + zona neutra proporcional + filtro Over 0.5 |
| 128 | Corrigido | Fix | Corner/card percentages mapeados + xG fallback None + calibrador extrai xG |
| 128e | **ATIVA** | Regra | xG blend so ativa com cobertura >= 80% home E away |
| 128i | **ATIVA** | Regra | Medicao obrigatoria Lambda Erro pre/pos recalibracao (limite 0.90) |
| 129b | **ATIVA** | Fix + Regra | Threshold Lambda Erro revisado 0.50 → 0.90 (benchmark Dixon-Coles) |
| 129c | **ATIVA** | Feature | Shadow Mode SAFE: computa internamente, exibe como NQ, loga para auditoria |
| 129e | Implantado | Infra | Pipedream webhook para notificacao shadow SAFE — email validado 09/04 23:11 |
| 130 | **ATIVA** | Fix + Regra | VIA 2 exige EV >= 0 para promocao a NEUTRO_QUALIFICADO |
| 131 | **ATIVA** | Fix + Dados | cornersTotalAVG + projFT ponderado (cross 35% + direct 30% + total 20% + league 15%) |
| 133 | Corrigido | Fix | V2 corners desbloqueado (matchesPlayed passado ao stats dict) |
| 134 | Corrigido | Fix | Legacy corners engine + cornersTotalAVG (terceira estimativa) |
| 137 | Corrigido | Fix | cards_engine denominador: league_avg → half_league (lambda era ~50% do real) |
| 138 | Corrigido (#139+#140) | Diagnose | Gaps silenciosos team_stats: ambas as camadas fechadas (mapper + resolver) |
| 139 | Corrigido | Fix | data_mapper canonical FootyStats field names: ~30+ campos com primary key season* + novos home/away splits |
| 140 | Corrigido | Fix | fix-133: 8 helpers de team_stat extraction roteados via _find_team_in_df (5-strategy fuzzy) |
| 128h | Corrigido | Fix | Recalibracao: xG blend ativado em 20 ligas, Brier O/U -0.0036 |
| 141 | Implementado | Feature | FootyStats /league-referees: referee avg cards wired into cards engine (referee_factor) |
| 142 | Implementado | Feature | FootyStats /lastx: recent form canonica (goals/cards/corners last5) → EMA/lambda calculator |
| 143 | Implementado | Feature | API-Football /fixtures/players: per-player cards/fouls para auditoria pos-jogo |
| 144 | Implementado | Feature | extract_best_odds: Corners O/U 4.5-12.5 desbloqueando scanner #110 |
| 145 | **ATIVA** | Fix + Regra | cornersRecorded_matches é match count, não média — projeção inflada 16→10.6 |
| 146 | **ATIVA** | Safety | Regra de EV obrigatório no prompt Mistral — NUNCA afirmar EV+ sem verificar prob × odd > 1 |
| 146b | **ATIVA** | Safety | Corredores devem ser apresentados como unidade (Over + Under = faixa esperada) |
| 147 | Implementado | Feature | Redesign Match Analysis + Rename VIÁVEL + Glossário + LiveTracker + CorridorCard |
| 148 | Implementado | Feature | Stake Kelly VIÁVEL (QK×0.30, cap 2%, floor 0.5%) + Badge resultado + Simulador banca |
| 149 | Implementado | Feature | Modo Oportunidade: stake por tier de classificação + desconto EV + barra exposição |
| 152 | **ATIVA** | Fix + Feature | Deflação BTTS reduzida (metade da banda) + monotonidade para cartões + rejected insights na UI |
| 153 | **ATIVA** | Fix | Complementar league-matches (page 1) com todays-matches para capturar todos os jogos da rodada |
| 154 | **ATIVA** | Fix | Paginar league-matches (todas as páginas, max_per_page=1000) para análise completa em todas as ligas |
| 155 | **ATIVA** | Fix | Mapear period API-Football→frontend (1H→1T, HT→HT, 2H→2T) + anular minute no HT |
| 156 | **ATIVA** | Pipeline | Deflation default 0.90 para ligas sem calibração per-league |
| 157 | **ATIVA** | Safety | Bloquear pares Double Chance antagonistas (DC 1X+DC 12, DC 1X+DC X2, DC 12+DC X2) |
| 158 | **ATIVA** | Fix | Direction rescue requer EV >= -5% — picks com EV muito negativo não podem ser "rescued" |
| 159 | **ATIVA** | Fix | Reliability N usa Brier acumulado (não batch único) — /health/reliability agora lê calculate_snapshot() |
| 160 | **ATIVA** | Infra | Late audit 02:00 BRT para jogos das Américas (Liga MX, MLS, Libertadores) que terminam após 23:45 BRT |
| 161 | **ATIVA** | Fix | Under-2.5 extra ×0.90 (#113) gated — skip quando `_DEFAULT_OU_DEFLATION < 1.0` ou liga em `_LEAGUE_DEFLATION` (evita dupla penalidade pós-#156) |
| 162 | **ATIVA** | Pipeline + UI | SAFE/NEUTRO accuracy = None quando sem picks (exibe "N/A" ao invés de "0.0%") + EV metrics no relatório (ev_medio_geral/positivo, picks_acionaveis, picks_ev_positivo) |
| 163 | **ATIVA** | Feature | Acurácia ponderada por 1/fair_odd — picks difíceis pesam mais; exposto via `compute_weighted_accuracy()` em `backtesting.py` |
| 161 | **ATIVA** | Fix | Gate Under-2.5 penalty ×0.90 quando lambda já deflacionado (#156). Evita ~19% deflação cumulativa matando gols |
| 162 | **ATIVA** | Fix+Feat | SAFE 0/0 exibe N/A (não 0%), compute_ev_summary() no relatório de auditoria |
| 163 | **ATIVA** | Feature | Accuracy ponderada (1/fair_odd) — favoritos pesam mais que underdogs |
| 164 | **ATIVA** | Fix | Logger `sportsbankzu` forçado a INFO (LOG_LEVEL env, fallback INFO) — AWS Lambda filtrava INFO via root handler em WARNING |
| 164b | **ATIVA** | Fix | Escopar logging à namespace sportsbankzu (sem root override) — evita spam boto3/urllib3/mangum no CloudWatch |
| 164c | **ATIVA** | Fix | Hook 5 V2-BUNDLES: chave `nome`→`mercado` + filtrar só `gols`/`btts` (exclui corners/cards do gols_total) |
| 165 | **ATIVA** | Fix + Feat | O/U half-band quando lambda pré-deflacionado (#156) + EV Floor 1% (EV_FLOOR_DROP) + Cards corridor dedup (sum>105% → maior EV) |
| 166 | **ATIVA** | Feature | Odds ingestion v2 — checklist break (home+over_25+btts_yes) + PRIORITY_BOOKMAKERS per-league + paginação 5→10 + endpoint debug gated. Flag `ODDS_INGESTION_V2` |
| 167 | **INFORMATIVA** | Investigação | MLS corners Brier 0.241 confirmado como floor do modelo atual — grid search rejeitou deflation 0.95 e safe_prob 0.75 |
| 169 | **ATIVA** | Guideline | Strict Contract (tipos/nulls/fallbacks em APIs externas) + First Principles (campos subutilizados = oportunidade de Brier) — complemento à Regra de Investigação |
| 170 | **ATIVA** | Feature | Corners diagnostic endpoint — 4 métricas empíricas (coverage homeAttackAdvantage, correlations, home×away, NB2 dispersion) para decisões sobre modelo de corners |
| 170-A | **ATIVA** | Pipeline | NB2 α corners calibrado per-league — resolve super-dispersão 5-30× detectada pelo #170 (MLS α_emp=0.033 vs α_prod=0.15, EPL α_emp=0.005). Flag `CORNERS_ALPHA_CALIBRATED` |
| 171 | **ATIVA** | Pipeline (P0) | Proteção banca pós-#170-A: ECE haircut (até -25%), OddsVal haircut (até -30%), market-family cap (corners 5%, goals 10%), daily loss circuit breaker (15%), `lambda_deflation` em ADJUSTMENT_LIMITS, env-var-gated auto-apply (AUTO_APPLY_CONFIDENCE_MIN=101) |
| 172 | Implementado | Infra | Vercel Build Minutes: Turbo→Standard + ignoreCommand com pathspec `:(top)` (~$580/mês → ~$58) |
| 173 | Implementado | Observabilidade | Medição degradação fim-de-temporada (script local) + snapshot diário de standings em S3 (cron 06:00 UTC) para backtest retroativo de features de contexto de temporada |
| 174 | Implementado | Fix + Política | Bug Report Card (null guards `safe_accuracy` em AuditReportCard.tsx, espelho do #168) + política de não-mexer com N=11 + watchlist Cartões Over 2.5 (calibrar α per-league se accuracy <40% com N≥15) |
| 175 | Implementado | FinOps | EC2 prognosticos-brasileirao-server t3.micro terminada (dark spend ~$90/ano, sem utilização) — captura de metadados em `infra/decommissioned/` para audit trail |
| 176 | Implementado | Security | FootyStats key rotacionada + helper `_redact_key` em `footstats_client.py` mascara `?key=`/`&key=` em 4 logger.* + retention temp 7d (restaurar 90d em 2026-05-08) |
| 177 | Implementado | Backend | Joint `by_league_market` JSONB no `brier_service` (MIN_N=5 diagnóstico + flag `diagnostic_only` quando N<20) — destrava validação red-team de subset (VALIDATE_REPORT 2026-05-04) |
| 178 | Implementado | UI + Backend | Brier target unificado em 0.22 (constante `BRIER_TARGET` em `brier_service.py`) + `model_beats_house_ci` com Wilcoxon p-value + N + badge `<ModelBeatsHouseRow>` no ReliabilityCard — destrava confiança operacional |
| 179 | Shadow Mode | Modelo | Recalibração shadow banda 50-60% (deflation 0.12→0.05) — observability via /metrics/shadow_v179, gate 2 semanas + 3% improvement; flag `SHADOW_BAND_50_60_V179` (default off) |
| 180 | Implementado | Backend + UI | Family pick selection (1 winner por família via `_market_family` reusado de #171; flag `ENABLE_FAMILY_SELECTION_180`; ranking por classification > EV > delta > band; annotate, not filter) |
| 181 | Implementado | Backend AI | Mistral input/output contract — proíbe citar probs raw e computar EV em narrativa; novo módulo `mistral_contract.py` com `validate_output` full-text + log-only observability (sem retry); prompt rules explícitas; documenta limitação estrutural da Camada 6 |
| 182 | Hotfix (P0) | Backend | Scipy lazy import em `brier_service.py` — top-level `from scipy.stats import wilcoxon` (#178) quebrou `/metrics/brier` em produção (`numpy._core.tests` ausente no Lambda Layer); import movido para dentro de `_with_ci()` em try/except. Fail-safe: `p_value=None` → `significant_at_5pct=False` |
| 183 | Implementado | Backend | Enrichment de matches via `get_match_details` — jogos via complement #153 agora podem ter `mercados[]` populado reusando `teams_df`/`league_df` do caller; rejeita record sem mercados (degrade gracefully); flag `ENABLE_MATCH_DETAILS_ENRICHMENT_183` default **false** (rollout pendente de validação empírica) |
| 184 | Implementado | Backend | xG filter None-guard — short-circuit em `ajustar_lambda_por_xg` quando games_played/goals_scored/xg=None + coerce na fronteira `ajustar_lambda_jogo_por_xg:218-225`. Cura raiz que #183 mascarava: outer except em `build_records_from_matches` derrubava silenciosamente records cujo team row faltava em teams_df. Label de skip-log corrigido (team_a_name vs home_team obsoleto) + warning observability em fixtures_service:1290. Smoke local: 3/6→6/6 jogos com mercados. |
| 186 | **ATIVA** | Fix + Feature | B-011 resolvido: date="week" invalidava TODO enrichment API-Football (guard Y-m-d + datas derivadas dos records via `_af_query_dates`); injuries/lineups consultavam /injuries com FootyStats id (ID space errado — nunca funcionou) → movidos para fixtures.py pós-matching com `apiFootballFixtureId` real; transparência de fontes: `_sources` no envelope /fixtures + `probSources`/`predictionSource` em stats; ladder O/U display com complemento e monotonicidade garantidos (`compute_ou_stats`); identidade lambda estrutural (`lambda_stats_block`); categoria Cards no market_reference_signal (não herda mais metadata over25 de gols) |
| 187 | **ATIVA** | Fix + Regra | Prioridades do pedido original: famílias de cartões/escanteios de bet único com validação de escada (elimina odds contaminadas); reclassificação de mercados pós-enrichment; 1X2 espelho ROTULADO na UI (decisão opção b, #028/#064); stats O/U de Poisson(lambdaTotalOU) e BTTS de (1-e^-λh)(1-e^-λa) — verificáveis pelo payload, reconecta feedback loop aos picks; calibrate_match_stats só corners; cartões >2.5 e escanteios >10.5 só com odd real (emenda #110); fonte fallback_default eliminada dos sinais |
| 188 | Fase 1/4 | Feature (infra IA) | Migração Qwen Fase 1: ai_audit_log (PG + fallback SQLite, log-and-degrade, psycopg2 lazy #182) com inputs/output/latência/valid_json/actual_result por jogo auditado; validador de schema (confidence 0-100, explanation não vazia, auditOdds condicional); hooks log-only no analyze_match + rotas; script de backfill de resultados. Zero mudança de comportamento; Mistral único em produção |
| 189 | **ATIVA** | Fix + Regra | Sugestão da AI reconciliada com a tabela de EV: Camada 7 (`_enforce_recommendation_contract`) substitui recomendação que cite mercado fora dos picks aprovados por `aligned_recommendation()` determinística (mesmos prob deflacionada/odd/EV do display); prompt #096 endurecido — cláusula "ou um mercado complementar" revogada + ramo "Sem recomendação" para jogos sem pick aprovado; `_MARKET_PATTERNS` cobre grafia inglesa `Double Chance` e `1X2 Home/Away` (regressão KRC Genk 2026-08-28: Sugestão exibia DC 1X "EV positivo, 87%" com a tabela listando EV -29.8%); stake sem odd bloqueado em `calcStakeOportunidade` (`odd<=1`, EV 0 era sentinela mentindo como medido) e `StakeRow` ocultada quando `bookOdd` ausente |
| 189-a/b/d | **ATIVA** | Fix + Regra | Pacote de cálculos (auditoria 2026-08-29): deflação CONTÍNUA por interpolação entre nós (`_DEFLATION_KNOTS`) substitui o degrau do #105 — monotonicidade de p·(1-d(p)) provada e testada em varredura 1e-4 (raw 60.0% exibia prob pior que 59.9%); #179 PROMOVIDO (nó 0.55 = 0.05, era 0.12; flag shadow inerte, /metrics/shadow_v179 reporta improvement 0); cross de cartões corrigido para fórmula simétrica (hf+aa+af+ha)/2 (viés -10% no λ eliminado) com guarda against>0 contra sentinela 0.0; floor #148 condicionado a EV≥0 — EV negativo vira ordem-limite `await_min_odd` com min_odd=fair nos dois modos de stake, backend e frontend |
| 189-e | **ATIVA** | Fix + Regra | Stake por família com edge comprovado (5.505 picks, Δ Brier vs mercado): cartões INFORMATIVOS (stake 0 em todos os modos/ligas até re-medição pós #189-b + árbitro), escanteios só linhas extremas (≥10.5/≤9.5), gols/1X2 plenos — `FAMILY_STAKE_POLICY` no bankroll_engine espelhada no frontend; calibração hierárquica mercado→família (pools por família em retrain, cartões finalmente em CALIBRATED_MARKETS); `_league_deflation_factor` resolve alias #185 antes do lookup (fator 0.90 do Brasileirão estava morto no fluxo do dashboard); migração idempotente unifica rótulos de liga fragmentados no audit_results; fetch diário restrito a `ACTIVE_LEAGUES()` (13 ativas, 9 desativadas) |
| 189-f | Implementado | Fix + Observabilidade | Odds de escanteios finalmente copiadas no enrichment (#120/#144: extraídas desde sempre, descartadas na cópia — todo pick de Escanteios nascia "sem odd", inutilizando as linhas extremas do gate #189-e); `_FOOTYSTATS_ODD_MAP` completo 4.5–12.5; fator de árbitro (#141) entra nos PICKS de cartões (lookup movido para antes de selecionar_mercados_v2, `refereeAvgCards` no record repassado ao predict_cards — pré-requisito da re-medição de cartões do #189-e); telemetria `[ODDS-COVERAGE]` por liga/família no CloudWatch (meta ≥70% com odd real) |
| 189-g | Implementado | UX | Camada visual do gate #189-e (display-only, zero cálculo): badge INFO cinza p/ picks de família sem stake (era "VIÁVEL" azul contradizendo o gate) + ProbBar dessaturada; AICard "analisando…" sem % falsa durante loading; contagem real de ligas no loading do dashboard; bloco de não-recomendados legível (motivo em chip, números tabulares); fmtMercado acentua rótulos só no display |
| 194 | Implementado | Fix (Live) | Relógio live fiel ao feed (liveClock.ts: feed como fonte única, interpolação ancorada com teto 3min, acréscimos/INT reais, useLiveTick 10s) + contrato do overlay (IDs canônicos footystatsId/apiFootballId, observedAtUnix/serverTimeUnix, minuteSource, nextUpdate 20s unificado com clamp no cliente) + crash corrigido no /live-scores (log lia detail_candidate.home antes do guard de None — um jogo ruim congelava placar/tempo de todos; teste de regressão) — commits rotulados "(#190)" pela sessão de origem |
