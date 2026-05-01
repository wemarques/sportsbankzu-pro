# BACKLOG — sportsbankzu-pro

> **Propósito:** Itens em aberto para próximas sessões. Lido obrigatoriamente
> no início de cada conversa para construção evolutiva. Quando um item é
> concluído, migra para `docs/REGISTRO_CORRECOES.md` com numeração `#N` e é
> marcado como ✅ aqui.

**Última revisão:** 2026-04-29
**Itens abertos:** 14 (4 novos do incidente HTTP_ERROR de 29/04)
**Última conversa:** Sessão de 2026-04-28/29 — fechou #173 (Caminho 1+2 EOS audit + standings snapshot), #174 (Report Card null guards + watchlist cards), #175 (decommission EC2 prognosticos-brasileirao + 3 SGs + key + IPv4). Higiene de repo: `.gitattributes` + `.gitignore` tightening + 31 arquivos untracked.

**Incidente HTTP_ERROR (0s) de 29/04:** causa raiz = degradação upstream (FootyStats 429 + api-football date format bug). 5 hipóteses originais (H1-H5) refutadas. Achado lateral CRÍTICO (secret leak): **resolvido em 2026-05-01 (#176, B-010 ✅)**. Pendentes: B-011 (date format bug), B-012 (backoff/circuit breaker), B-013 (variantes do leak).

---

## Como usar este arquivo

**No início de cada sessão:**
1. Ler este BACKLOG.md
2. Ler `docs/REGRAS_ATIVAS.md` (regras permanentes)
3. Ler `CLAUDE.md` (estado do pipeline, proibições)

**Ao concluir um item:**
1. Migrar para `REGISTRO_CORRECOES.md` como `#N`
2. Adicionar linha em `INDICE_REGRAS.md`
3. Marcar como ✅ aqui na seção "Concluídos recentemente"
4. Após 3 meses, mover para histórico de release notes ou deletar

**Ao descobrir novo débito técnico:**
1. Adicionar aqui na categoria correta (P0/P1/P2/P3 ou Estudo)
2. Se for crítico (P0), mencionar imediatamente na resposta atual
3. Se for descoberta lateral (não relacionada à tarefa), apenas anotar e continuar

**Revisão trimestral:**
- Items "Deferred" com >6 meses → deletar ou re-priorizar
- Items "Open" sem progresso há 60 dias → questionar se ainda fazem sentido

---

## Estrutura de cada item

```
### [B-NNN] Título curto

**Categoria:** Analytics | Cost | Hygiene | Security | Tooling | Open Question
**Prioridade:** P0 (crítico) | P1 (alta) | P2 (média) | P3 (baixa) | Q (estudo)
**Esforço:** XS (≤5min) | S (15-30min) | M (1-3h) | L (4-8h) | XL (>1d)
**Status:** Open | In Progress | Blocked | Deferred
**Adicionado:** YYYY-MM-DD

**Contexto:** Por que existe. Qual problema resolve.
**Critério de sucesso:** Como saber que está pronto.
**Notas:** Tentativas anteriores, links, dependências.
```

---

## P0 — CRÍTICO (fazer ANTES de qualquer outra coisa)

### B-010 Rotacionar FootyStats API key + sanitizar logs ✅ CONCLUÍDO 2026-05-01 (#176)

**Categoria:** Security (secret leak ativo)
**Prioridade:** P0
**Esforço:** S (45 min total: rotação + sanitização + retention)
**Status:** Done — ver `REGISTRO_CORRECOES.md#176`
**Adicionado:** 2026-04-29
**Descoberto em:** incidente HTTP_ERROR de 29/04 — diagnóstico mostrou logs FootyStats imprimindo `?key=...` em CloudWatch.

**Contexto:** Cliente FootyStats (`backend/services/footstats_client.py`) está logando URL completa com query string, incluindo `?key=<API_KEY>`. CloudWatch retention=None → milhares de cópias da key persistem indefinidamente. Qualquer principal IAM com `logs:GetLogEvents` lê tudo. Equivale a key já comprometida.

**Critério de sucesso (em ordem):**
1. Rotacionar key no dashboard FootyStats → invalida a antiga
2. Atualizar `FOOTYSTATS_API_KEY` na Lambda env via `aws lambda update-function-configuration --environment ...`
3. Patch em `footstats_client.py`: mascarar `?key=...` em qualquer `logger.error/info/debug` antes de logar URL. Padrão típico: `logged_url = re.sub(r'(\?|&)key=[^&]+', r'\1key=***REDACTED***', url)`
4. Set log retention temporário curto (7 dias) para expirar logs com key antiga: `aws logs put-retention-policy --log-group-name /aws/lambda/sportsbank-pro-backend --retention-in-days 7`
5. Após 7+ dias, voltar retention para 90d (B-003)
6. Smoke test: rodar `aws logs tail /aws/lambda/sportsbank-pro-backend --since 5m | grep "key="` → esperado vazio

**Notas:** Documentar como REGRA #N. Padrão reutilizável: nenhum cliente HTTP deve logar URL com query string sem sanitizar segredos. Aplicar mesmo princípio aos clients de API-Football, Mistral.

---

## P1 — Alta prioridade (próxima sessão)

### B-011 Bug de date format em api-football fixtures

**Categoria:** Hygiene (regressão)
**Prioridade:** P1
**Esforço:** M (1-2h)
**Status:** Open
**Adicionado:** 2026-04-29
**Descoberto em:** incidente HTTP_ERROR de 29/04.

**Contexto:** CloudWatch tem dezenas de erros `[api-football/fixtures] API error: {'date': 'The Date field must contain a valid date: Y-m-d.'}` em 30 min. Algum chamador está passando date inválida (vazia, None, formato errado). Pode ser regressão recente.

**Critério de sucesso:**
- Identificar local que monta o param `date` para api-football com formato errado
- `grep -rn "api_football.*fixtures" backend/services/` para mapear chamadores
- `git log -p backend/services/api_football_client.py | head -200` para ver mudanças recentes
- Adicionar guard antes de mandar request: se `date is None or date == "" or not re.match(r'^\d{4}-\d{2}-\d{2}$', date)`, omitir parâmetro ou raise descritivo
- Verificar logs após fix: zero ocorrências de "must contain a valid date"

**Notas:** O sintoma "(0s)" reportado pelo usuário pode ter contribuição parcial deste bug se a rota chamadora retorna erro sem retry.

---

### B-012 FootyStats 429 — retry com backoff + circuit breaker

**Categoria:** Resilience
**Prioridade:** P1
**Esforço:** M (2-3h)
**Status:** Open
**Adicionado:** 2026-04-29
**Descoberto em:** incidente HTTP_ERROR de 29/04 — centenas de 429s sem tratamento.

**Contexto:** Cliente FootyStats (`backend/services/footstats_client.py`) fez "Failed after 2 attempts: 429 Client Error: Too Many Requests" em massa. Sem backoff exponencial nem circuit breaker, qualquer rate-limit do provedor vira HTTP_ERROR para o usuário final.

**Critério de sucesso:**
- Adicionar backoff exponencial nos retries (não só max_attempts=2 fixo): wait 2s, 4s, 8s entre tentativas para 429
- Implementar circuit breaker simples: após N 429s em janela de M minutos, parar de chamar FootyStats por X minutos. Cache stale data ou retornar `[]` em vez de propagar erro
- Adicionar header `X-RateLimit-Remaining` parsing se FootyStats retornar (alguns providers retornam) — antecipar throttling
- Métrica: contar 429s/hora em CloudWatch metric custom para alarme proativo

**Dependência:** B-010 deve ser feito primeiro (sanitização de logs evita que reintentos exponham mais cópias da key).

---

## P3 — Baixa prioridade (cosmético)

### B-013 Frontend: incluir 429 no retry regex + mensagem informativa

**Categoria:** Tooling (UX)
**Prioridade:** P3
**Esforço:** XS (30 min)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** Frontend retry regex atual: `/HTTP (502|503|504)/`. 429 (rate limit) não retentado, vira HTTP_ERROR direto. Usuário vê "Servidor indisponivel (0s)" quando na verdade é rate limit transitório do upstream.

**Critério de sucesso:**
- Adicionar 429 ao regex: `/HTTP (429|502|503|504)/`
- Mensagem específica para 429: "Limite de requisições atingido. Tentando novamente em alguns segundos..."
- Backoff no client-side antes de retry (1s, 2s, 4s)

**Notas:** Resolve só o sintoma. Causa raiz é B-012 (não atingir 429 no upstream). Mas é defesa em profundidade — se algum dia FootyStats reduzir quota, frontend não precisa mudar de novo.

---

## P1 — Alta prioridade (Analytics — continuação)

### B-001 EOS audit re-run com filtros corretos

**Categoria:** Analytics
**Prioridade:** P1
**Esforço:** M (2-3h)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** A decisão "SINAL REAL com 4 ligas flagged" do EOS audit foi suspensa. Verify (`scripts/verify_eos_audit.py`) confirmou H1 (contaminação de 35 ligas legacy em audit_results) e H4 inconclusivo (coluna `brier_score` é NULL). Sem fix, qualquer conclusão sobre degradação fim-de-temporada é especulação.

**Critério de sucesso:**
- Patch em `scripts/audit_end_of_season_picks.py` filtrando `WHERE league IN (active 22)` ou `WHERE timestamp >= '2026-03-23'` (post-rename)
- Patch para segmentar por season explícita usando `get_season_for_league()` para calendar-year leagues (Brasileirão, MLS, Liga MX)
- Adicionar bootstrap CI95% no relatório — flagar liga só se `late_lower_CI > early_upper_CI`
- Re-rodar via `scripts/run_eos_audit.bat`
- Decisão final: SINAL REAL / SINAL FRACO / SEM SINAL com confiança estatística

**Notas:** Bloqueia decisão sobre features de contexto de temporada (B-Q01). Verify script já existe em `scripts/verify_eos_audit.py`.

---

### B-002 Cleanup audit_results — 35 ligas legacy

**Categoria:** Hygiene (data)
**Prioridade:** P1
**Esforço:** S (30 min)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** `audit_results` em PostgreSQL tem 48 ligas distintas (esperado: 22). Os 26+ extras são aliases pré-2026-03-22 ("Brazil Serie A" vs "Brasileirão Série A", "Usa Mls" vs "MLS", etc.) que ficaram parados quando houve rename de ligas. Toda análise por liga (Brier per-league, calibradores, accuracy reports) está sub-correta porque está agrupando inconsistente.

**Critério de sucesso:**
- Query `SELECT DISTINCT league FROM audit_results` retorna ≤22 nomes
- Mapear cada legacy → canonical via `UPDATE audit_results SET league = ? WHERE league IN (...)`
- Decidir: migrar (preserva histórico) ou deletar (perde mas simplifica)
- Documentar como REGRA #N (provavelmente #176) com mapa de aliases para referência futura

**Notas:** Resolver isso ANTES do B-001 — sem cleanup, EOS audit re-run continua agrupando errado. Mas tecnicamente pode ser combinado em um único patch que filtra ativos.

---

## P2 — Média prioridade (quando der vontade)

### B-003 Lambda log group retention 90d

**Categoria:** Cost / Hygiene
**Prioridade:** P2
**Esforço:** XS (1 min)
**Status:** Open
**Adicionado:** 2026-04-29
**Data alvo:** 2026-05-08 (após expiração dos logs com FootyStats key vazada — ver #176)

**Contexto:** Log group `/aws/lambda/sportsbank-pro-backend` está em `retention=7d` temporário desde 2026-05-01 (#176, B-010) para expirar logs antigos com `?key=...` vazado. A partir de 2026-05-08 todos os logs anteriores a 2026-05-01 já foram pruned, e podemos restaurar 90d (compromisso entre retenção para debug e custo).

**Critério de sucesso:** retention=90 confirmado via `describe-log-groups`, zero `key=` em logs recentes (sanitização ainda efetiva), B-003 marcado como concluído + commit no repo.

**Comando pronto (executar em 2026-05-08, sequencialmente):**
```bash
# Verificacao 1: retention atual ainda eh 7
MSYS_NO_PATHCONV=1 aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/sportsbank-pro-backend \
  --region us-east-1 \
  --query "logGroups[].{Name:logGroupName,Retention:retentionInDays}"

# Verificacao 2: zero leaks de key= em logs recentes (24h)
START_TS=$(python -c "import time; print(int(time.time()*1000 - 86400000))")
MSYS_NO_PATHCONV=1 aws logs filter-log-events \
  --log-group-name /aws/lambda/sportsbank-pro-backend \
  --region us-east-1 --start-time $START_TS \
  --filter-pattern '?"?key=" ?"&key="' \
  --query "events[*].message" --output text | head -5

# Aplicar retention=90 (so se as 2 verificacoes acima estao OK)
MSYS_NO_PATHCONV=1 aws logs put-retention-policy \
  --log-group-name /aws/lambda/sportsbank-pro-backend \
  --retention-in-days 90 --region us-east-1

# Confirmar
MSYS_NO_PATHCONV=1 aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/sportsbank-pro-backend \
  --region us-east-1 --query "logGroups[].retentionInDays"
```

**Notas:**
- Marcar como concluído + commit `chore(B-003): restaurar CloudWatch retention=90d pos-expiracao logs com FootyStats key (B-010 done em 30/04)` após execução bem-sucedida.
- 90 dias é compromisso entre retenção para debug e custo. Pode ajustar para 30d se virar problema.
- Se Verificação 2 retornar key= em logs recentes: PARAR — sanitização quebrou, investigar regressão no `_redact_key` em `footstats_client.py` antes de mexer em retention.

---

### B-004 RDS Public Access → Private

**Categoria:** Security
**Prioridade:** P2
**Esforço:** L (2-4h)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** RDS `sportsbank-pro-db` está em modo Public Access. Para 10 usuários com Lambda no mesmo VPC, public access não é necessário — Lambda acessa via SG interno. Tornar privado:
- Remove vetor de ataque (RDS exposto à internet)
- Pode liberar EIP gerenciado pela AWS RDS service (eni-047ebe7223ea8fdf1, IP 52.205.88.74)
- Não muda funcionalidade SE Lambda já está em VPC + SG correto

**Critério de sucesso:**
- Confirmar Lambda está em VPC com acesso ao subnet do RDS (ou colocar)
- `aws rds modify-db-instance --no-publicly-accessible`
- Validar Lambda continua acessando RDS (smoke test)
- EIP some automaticamente OU release manual

**Notas:** Risco real de derrubar conexão Lambda↔RDS se VPC config errar. Fazer em janela de baixa atividade. Documentar SG IDs antes/depois.

---

### B-005 Status reporting fix em standings_snapshot.py

**Categoria:** Tooling (UX)
**Prioridade:** P2
**Esforço:** XS (15 min)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** `snapshot_all_leagues_to_s3()` retorna `status="partial"` quando `successes=[]` mas `failures=[20]`. "partial" para olho humano parece "deu uns errinhos" quando na verdade é "100% falhou". Atrasou detecção do problema do AccessDenied no #173.

**Critério de sucesso:**
```python
if not successes and failures:
    status = "error"
elif successes and failures:
    status = "partial"
else:
    status = "success"
```
Aplicar mesma lógica em outros batch jobs (`run_post_match_diagnostic`, `retrain_all_calibrators`).

**Notas:** Possível REGRA #N: "batch jobs devem retornar status='error' quando 100% falham". Padrão reutilizável.

---

### B-006 Cleanup script para audit trimestral de recursos AWS

**Categoria:** Tooling
**Prioridade:** P2
**Esforço:** M (1-2h)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** A descoberta da EC2 órfã (#175) e dos 3 SGs legacy aconteceu por acaso, não por processo. A REGRA #173 já estabeleceu "tudo em AWS deve ter referência em `infra/` ou `scripts/`", mas falta automação para detectar drift.

**Critério de sucesso:**
- `scripts/audit_aws_resources.sh` lista: EC2 + EIPs + SGs + Key Pairs + Snapshots/AMIs + Log Groups + RDS instances + Lambda functions
- Cruza com lista esperada documentada em `infra/inventory.json` ou similar
- Reporta drift (recurso existe mas não documentado, ou documentado mas não existe)
- Rodar trimestralmente; output em `reports/aws_audit_<DATE>.md`

**Notas:** Não automatizar deletes — só detecção. Manter humano no loop.

---

## P3 — Baixa prioridade

### B-007 Watchlist Cartões Over 2.5 — monitoring ativo

**Categoria:** Analytics (reflexão)
**Prioridade:** P3
**Esforço:** Reflexão contínua
**Status:** Open
**Adicionado:** 2026-04-28 (REGRA #174)

**Contexto:** REGRA #174 estabeleceu watchlist: se Cartões Over 2.5 atingir N≥15 picks com accuracy <40% E Brier >0.27, calibrar α NB2 per-league para cards (espelho do #170-A). Hoje o monitoramento depende de você lembrar.

**Critério de sucesso:** verificar a cada 1-2 semanas:
```sql
SELECT COUNT(*) as n,
       SUM(CASE WHEN actual_result='hit' THEN 1 ELSE 0 END)::float / COUNT(*) as accuracy,
       AVG(brier_score) as brier
FROM audit_results
WHERE market = 'CARTOES OVER 2.5' AND brier_score IS NOT NULL
  AND timestamp >= NOW() - INTERVAL '21 days';
```
Se `n >= 15 AND accuracy < 0.40 AND brier > 0.27` → escalar para P0 (calibrar urgente).

**Notas:** Pode ser automatizado em B-006 como mais um check.

---

### B-008 .gitignore — exceções para logs intencionais (caso surjam)

**Categoria:** Hygiene
**Prioridade:** P3
**Esforço:** XS (5 min on-demand)
**Status:** Open (latente)
**Adicionado:** 2026-04-29

**Contexto:** O `.gitignore` agora tem `*.log` global. Se surgir caso de uso legítimo (regression test, expected output, etc.), adicionar exceção `!path/to/specific.log`.

**Critério de sucesso:** N/A — só ativar quando alguém perguntar "por que meu .log não foi pra git?".

---

### B-009 .git/ shrink via filter-branch ou BFG

**Categoria:** Hygiene
**Prioridade:** P3
**Esforço:** L (1-2h, mas destrutivo)
**Status:** Deferred
**Adicionado:** 2026-04-29

**Contexto:** `.git/` está em 417 MB porque carrega blobs antigos de `api_cache.db` (10 MB), `decisions.log`, screenshots Playwright, etc. Reduzir exigiria reescrita de histórico (filter-branch ou BFG), force-push, e quebra para qualquer fork/clone existente.

**Critério de sucesso:** decidir SE vale o trade-off. Para 10 usuários, provavelmente não.

**Notas:** Reavaliar se .git/ chegar a >2GB e atrapalhar clone times.

---

## Estudos / Open Questions

### B-Q01 Aurora Serverless v2 migration?

**Categoria:** Cost / Architecture
**Prioridade:** Q (estudo)
**Esforço:** L (3-4h migração se decidido positivo)
**Status:** Blocked (precisa dados Performance Insights)
**Adicionado:** 2026-04-29

**Contexto:** Análise anterior mostrou que Aurora Serverless v2 com `MinCapacity=0` + auto-pausa pode custar $1-10/mês vs RDS atual $14/mês. Mas depende crucialmente de quanto tempo o banco fica realmente ativo. Performance Insights foi habilitado nesta sessão — precisa coletar 14-30 dias de dados antes de decidir.

**Critério para migrar:**
- DBLoad < 4h/dia em média sobre 14+ dias → migrar (save ~$60-108/ano)
- DBLoad > 8h/dia → manter RDS, talvez upgrade para t4g.small se crescer

**Notas:** Não tomar decisão antes de 2026-05-15 (15 dias de dados). Documento de análise em conversa anterior — se precisar reler, buscar "Aurora Serverless v2" + steelman.

---

### B-Q02 Features de contexto de temporada

**Categoria:** Analytics / Modeling
**Prioridade:** Q (estudo)
**Esforço:** XL (semanas de feature engineering)
**Status:** Blocked (precisa B-001 verdict)
**Adicionado:** 2026-04-29

**Contexto:** Hipótese: jogos de fim-de-temporada (rebaixados, garantidos, sem motivação) têm dinâmica diferente — modelo lambda atual não captura. Features candidatas: rank atual, gap_to_relegation, days_to_season_end, motivation_score (vagas decididas).

**Critério para investir:**
- B-001 retorna SINAL REAL (≥3 ligas com Brier(late) significativamente pior, sobrevivendo bootstrap CI)
- Caminho 2 (snapshot S3) acumulou ≥30 dias de dados → permite reconstruir rank no momento de cada pick
- Estimativa de Brier improvement justifica esforço (1-3% melhoria já vale)

**Notas:** Sem B-001 verde, não investir. Continuar coletando standings via cron 06:00 UTC.

---

### B-Q03 Migrar key da Mistral para SSM Parameter Store?

**Categoria:** Tooling / Security
**Prioridade:** Q (estudo)
**Esforço:** S (30 min)
**Status:** Open
**Adicionado:** 2026-04-29

**Contexto:** Hoje `MISTRAL_API_KEY` vive em `.env` local (gitignored, validado que nunca foi tracked) e em Lambda env. Padrão é OK mas não tem rotação automática nem audit trail. SSM Parameter Store SecureString daria CloudTrail logging + versionamento.

**Critério para migrar:**
- Decidir se valor incremental de audit/rotação justifica complexidade
- Para 10 usuários: provavelmente não vale agora
- Reavaliar se houver requisito de compliance ou rotação obrigatória

**Notas:** Mesma análise vale para `API_FOOTBALL_KEY` (já em Lambda env, acessada via wrapper `scripts/api_football.sh`).

---

## Concluídos recentemente (últimos 30 dias)

Migrar para `REGISTRO_CORRECOES.md` quando atingirem 90 dias. Lista mantida apenas como contexto rápido para sessões próximas.

- ✅ **#176** (2026-05-01) FootyStats key rotacionada + `_redact_key` em logs (`footstats_client.py`) + retention temp 7d. Resolve B-010 (P0 — secret leak). 616 leaks/24h → 0.
- ✅ **#175** (2026-04-29) Decommission EC2 prognosticos-brasileirao + 3 SGs + key. Save $132/ano.
- ✅ **#174** (2026-04-28) Bug Report Card null guards `safe_accuracy` + política N=11 + watchlist Cartões Over 2.5
- ✅ **#173** (2026-04-27/29) Caminho 1 (audit_end_of_season_picks.py) + Caminho 2 (standings snapshot S3 daily 06:00 UTC) + IAM `S3SportsbankWrite` versionada em `infra/`
- ✅ **Higiene repo** (2026-04-29) `.gitattributes` + `.gitignore` tightening (11 patterns) + 31 arquivos untracked (3 runtime artifacts + 19 logs Playwright + 9 PNGs Playwright)
- ✅ **Tooling** (2026-04-29) `scripts/api_football.sh` wrapper resolve key on-demand sem export
- ✅ **FinOps quick wins** (2026-04-29) Budget alarm $50/mês + Performance Insights enabled (já estava)

---

## Histórico de revisões deste arquivo

| Data | Mudança | Itens abertos |
|---|---|---|
| 2026-04-29 | Criação inicial | 10 |

---

## Notas para próximo Claude / próxima sessão

**Estado do produto agora:**
- Caminho 2 do #173 (snapshot S3) coleta dados diariamente. Em ~30-60 dias terá amostra para análises retroativas mais limpas.
- Bug do Report Card está em produção corrigido (commit `d5d0a4f`).
- Bill AWS reduzido para ~$18/mês. Próximo grande save depende de B-Q01 (Aurora).
- 10 usuários ativos. Otimizações de escala não fazem sentido até 10× crescimento.

**Próxima ação de maior leverage:**
B-001 + B-002 combinados (~3h total): cleanup audit_results + EOS audit re-run com filtros corretos. Destrava B-Q02 (decisão sobre features de contexto).

**Decisões pendentes do usuário:**
- Confirmar prioridade entre higiene técnica (B-001/B-002) e feature work no produto
- Reavaliar B-Q01 quando Performance Insights tiver 14-30 dias de dados (após ~2026-05-15)
