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
| 128h | Corrigido | Fix | Recalibracao: xG blend ativado em 20 ligas, Brier O/U -0.0036 |
