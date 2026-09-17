# CLAUDE.md — SportsBankZU Pro

**Stack:** Next.js 14 (Vercel) + FastAPI/Python (AWS Lambda) + PostgreSQL (RDS). Streamlit foi descontinuado — ignorar referências antigas em código/docs.

## Leitura obrigatória antes de qualquer alteração

Ler nesta ordem: `docs/BACKLOG.md` (P0/P1) → `docs/REGRAS_ATIVAS.md` → `docs/INDICE_REGRAS.md`. Consultar `docs/REGISTRO_CORRECOES.md` quando precisar do histórico de um fix `#N`.

## Protocolo de Execução Silenciosa (precede o SDD)

Estas regras têm precedência sobre o estilo de resposta. Violá-las invalida a entrega, mesmo que o código esteja correto.

1. **Proibido narrar descoberta antes de agir.** Se encontrou um problema, corrija ou reporte em 1 linha factual. Proibido: "descobri que...", "o que isso revela...", "a ironia é...", "vou parar aqui porque...". Formato permitido de reporte:
   `CORREÇÃO: <campo> afetado por <causa>. Fix: <ação>. Impacto: <N>.`

2. **Proibido parar para pedir permissão em tarefa já autorizada.** Se o usuário disse "sim" a um plano, execute até o fim. Só pare em bloqueio que exija decisão nova, e pare em 1 linha.

3. **Proibido oferecer escolha binária quando existe ordem correta demonstrável.** Se a análise indica que A deve vir antes de B, execute A e diga "fiz A, próximo é B, confirma?". Nunca pergunte "A ou B?".

4. **Toda descoberta retroativa vira regra ANTES de virar correção.** Se descobriu que o SDD não pegou X, adicione X ao SDD e só então corrija o código afetado. Sem isso, o mesmo vão reaparece na próxima tarefa e a sessão vira firefighting.

5. **Máximo 2 linhas de texto entre ações de código.** Código antes de prosa. Fatos antes de hedging. Sem preâmbulo, sem pós-escrito.

## Protocolo SDD (Spec-Driven Development) — Obrigatório para qualquer alteração

Toda tarefa de ajuste de cálculo, modelo, pipeline ou tela deve seguir rigorosamente as 4 etapas antes de qualquer commit:

### 1. Especificação Prévia (Spec)
Antes de alterar qualquer código, descrever explicitamente:
- **Objetivo e Contexto**: Qual comportamento ou anomalia está sendo tratado.
- **Rastreabilidade de Dados (Origem → Destino)**: Identificar o produtor do dado, os intermediários que transportam o payload e o consumidor final. Confirmar se o dado existe em todo o trajeto (sem inferir).
- **Critérios de Aceite Mensuráveis**: Definir em formato factual (ex: `Entrada X -> Saída esperada Y`, ou antes/depois esperado nos rótulos/valores).
- **Cenários de Borda e Fallback**: O que acontece se a chave faltar, a liga for nova ou a amostra for 0?

### 2. Validação de Contrato (Auditoria de Payload)
- É proibido adicionar `.get("chave")` em um consumidor sem inspecionar e provar que o produtor e a rota de fixtures/pipeline serializam essa chave no dicionário.
- Proibido criar contratos de ordem invisíveis (como `.pop()` pós-consumo).

### 2-bis. Contratos de Saída (extensão obrigatória da Etapa 2)
A Etapa 2 original audita o caminho de entrada do dado (produtor → intermediário → consumidor). Esta extensão audita o caminho de **saída**: o que a mudança **escreve** e quem, **fora do escopo da mudança**, lê.

Antes de alterar qualquer campo, listar:
- **Campos escritos pela mudança.** Nome exato, tabela exata.
- **Consumidores externos desses campos.** Quem lê, em qual subsistema, para qual finalidade. Incluir: ledgers, gates, métricas, dashboards, auditorias, jobs de avaliação.
- **Contrato implícito.** O que o consumidor assume sobre o campo? Ex: "`calibrated_prob` é a probabilidade pura do modelo, imune a camadas". Se a mudança viola essa suposição, é proibido prosseguir sem atualizar o consumidor ou isolar o campo.

**Rejeição automática:** se a mudança escreve em um campo que outro subsistema lê, e essa leitura não foi auditada, a entrega está rejeitada — mesmo que todos os testes internos passem.

### 3. Implementação Guiada
- Implementar estritamente o que foi delimitado na Spec. Não adicionar refatorações paralelas ou suposições não documentadas.

### 4. Prova Empírica Obrigatória (Definition of Done)
- **Proibido declarar sucesso com base apenas na leitura do código escrito.**
- Executar teste unitário ou script de validação comparando o estado **ANTES** e **DEPOIS** com um payload real ou fixture completa.
- Se o teste de saída apresentar resultados idênticos (como no caso do `EARLY_SEASON_FALLBACK`), a entrega está **rejeitada** e deve-se rastrear o elo faltante na cadeia de dados.

### 5. Efeito Acumulado (obrigatório para alterações que rodam em laço)
Vale para qualquer mudança que execute N vezes: ciclos de calibragem, jobs agendados, retries, backfills, qualquer coisa que rode em produção mais de uma vez sem intervenção humana.

Antes de ativar, declarar por escrito:
- **Comportamento esperado após 1 ciclo, 10 ciclos, 100 ciclos.** Números, não adjetivos. Ex: "a=0,23 → a=0,25 → a=0,27 (trava em 0,30)".
- **Condição de parada (rede de segurança).** O que faz a mudança parar ou reverter sozinha.
- **Prova de que a rede de segurança DISPARA.** Não basta existir no código. É obrigatório um teste com condição forçada que mostre a reversão/parada acionando. Se a condição nunca ocorre naturalmente, o teste tem que forçá-la.
- **Campo de saída lido por outros subsistemas** (ver Etapa 2-bis). Declarar quem lê, o que espera, e o que acontece se o valor mudar.

**Rejeição automática:** se a rede de segurança existe mas nunca foi vista disparar em teste, a entrega está rejeitada. Existir no código não é prova.

## Comandos

```bash
# Backend local
uvicorn backend.main:app --reload --port 5001

# Frontend
cd frontend/next && npm run dev

# Tests
pytest -q
cd frontend/next && npm run test:e2e
cd frontend/next && npm run test:unit
cd frontend/next && npm run lint:fonts
```

## API Lambda — armadilhas conhecidas

Base: `https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/`

**Nunca apontar `PY_BACKEND_URL` para `*.execute-api.*.amazonaws.com` (#114/#203).** O API Gateway corta a integracao em 30s — limite duro que nao se eleva por configuracao. O sintoma da violacao engana: ligas COM jogos (as unicas caras de montar) estouram e somem da tela, enquanto ligas sem jogos respondem em ~2s e aparecem — parece "algumas ligas nao carregam", nunca "o backend caiu". A guarda e `isApiGatewayBackend()` em `frontend/next/src/lib/backend.ts`.

| Rota correta | Errado |
|---|---|
| `/health` | `/api/health` (404) |
| `/fixtures` | `/api/fixtures` (404) |
| `/live-scores`, `/standings` | `/api/...` (404) |
| `/ledger/dia?data=YYYY-MM-DD` (#255) (dia do operador, BRT — #256) | `/api/ledger/dia` (404) |
| `/ledger/agregado?periodo=7d\|30d\|temporada&familia=&liga=` (#255); `resolvidos` em `acerto`/`por_familia`/`por_liga` (#256) | `?periodo=1ano` etc. → 400, nunca 200 com dado inventado |
| `/ledger/picks?periodo=&familia=&liga=` (#257) — leitura pura, mesmo filtro do agregado | base para retorno retroativo no cliente, nunca cálculo de Kelly no backend |
| `/api/backtesting/...` | |
| `POST /api/backtesting/calibrate?league=X` | `?league_id=X` |
| `/api/backtesting/calibration-status` | |
| `/api/health/safe-status` | |

Calibração leva 15–40s. Atrás da Function URL o teto é o timeout da própria Lambda (60s) e **503 não significa falha** — a Lambda continua processando e persiste o resultado. **503 em ~30s cravados é outra coisa:** é o teto do API Gateway, ou seja, backend errado (#203), nunca cold start.

## Deploy Lambda e Layer scipy

Procedimento completo (pré-check obrigatório, update via S3, recriação da Layer por runtime) na skill `deploy-lambda` (`.claude/skills/deploy-lambda/SKILL.md`). Regra que fica aqui: **sem Layer compatível, NB2 cai silenciosamente para Poisson**.

## Variáveis de ambiente

`MISTRAL_API_KEY`, `PY_BACKEND_URL`, `FUTEBOL_ROOT` / `DATA_ROOT`, `S3_BUCKET` (opcional).

`PROB_SOURCE` (#231): `modelo` (padrão) | `mercado`. **Não ligar `mercado`** antes do gate #230 (300 jogos no ledger, **só geração publicada antes do apito** — #252: o cron regrava jogos pós-apito; `kickoff_utc` é gravada desde #252-c e, nas linhas antigas (nulas), o kickoff sai do sufixo epoch do `match_id` — regra única em `prediction_ledger.kickoff_da_linha`; desconhecido exclui; e **fora da janela contaminada** 2026-09-10 23:02:06 → 2026-09-14 04:50:22 UTC — #252-a); itens 2–4 do passo 4 já implementados (#232–#234). `TAXAS_BASE_PATH` (opcional) aponta o artefato de taxas-base; padrão `backend/config/taxas_base.json`. `LAMBDA_CORRECTIONS_TTL_S` (#231-a): cache por liga das correções do banco, padrão 300 s; `0` desliga.

`CALIBRAGEM_ENABLED` (#248): liga o **ciclo de escrita** da camada de calibragem aprendida no cron. **Padrão `false` — deploy não é ativação.** Desligada, `ciclo.executar` devolve `{"status": "desligado"}` sem tocar o banco (nem DDL, nem leitura, nem escrita). Governa só a escrita: o *serving* segue ligado e, sem versões gravadas, delega ao legado (versão 0) — o painel publica o que publicava na véspera. Os dois avisos que este parágrafo trazia foram resolvidos e não valem mais: a trava de 2pp é **exata desde o primeiro ciclo** (#248 Task 13 — a curva compõe com o legado, `p' = σ(a + b·logit(legado(p)))`, então `(0,1)` **é** a versão 0 por construção), e os limiares re-derivados **são consumidos** por `_get_thresholds` (#249), com piso de amostra do #079 (#249-a). Antes de ligar, rodar `python scripts/ensaio_calibragem.py`: ele mostra exatamente o que o primeiro ciclo faria, **sem escrever nada**. Medido em 2026-09-15 (depois do #253-b, que faz o ensaio contar cada pick pela curva que o serving usaria): 126 células, 18 encurtadas em 2,00pp, 0 adotadas, 0 revertidas, volume publicado 402 → 403 — conferido por medição independente no serving. Antes do #253-b o ensaio dizia 402 → 403 e o serving publicaria 365. `CALIBRAGEM_TTL_S` (#248): cache dos parâmetros vigentes no serving, padrão 300 s. `CALIBRAGEM_SEMENTE_PATH` (#248, opcional): artefato do backfill usado como semente.

**Contaminação do gate #230 — RESOLVIDA em #251 (2026-09-14).** Enquanto a camada servia uma versão real, `curva.aplicar_versao` sobrescrevia `detalhe.final` com a composição e o valor do legado morria ali; `_prob_do_modelo` só lia `model_probability` sob `PROB_SOURCE=mercado` e, no padrão `modelo`, caía na saída da camada. `prediction_ledger.calibrated_prob` volta a ser **a probabilidade do modelo em qualquer estado das duas flags** (`DetalheCalibracao.modelo` → `MarketOutput.model_probability` → ledger); `published_prob` continua sendo o publicado. Medido: 21/21 picks com os dois campos separados, 2,43pp médios. Gate: `tests/test_251_calibrated_prob_e_o_modelo.py`. **Isto não autoriza ligar `CALIBRAGEM_ENABLED`** — a trava que resta é a proibição 16 (Etapa 5 do ciclo de escrita), não esta.

## Pipeline ativo (V2 — REGRAS #028, ativado em #035)

```
FootyStats + API-Football v3
  → build_records_from_matches (fixtures_service.py)
  → calcular_lambda_jogo (deflation 0.85 #043 + γ home #078)
  → xg_filter bidirecional (#035-M3)
  → chaos_detector + SAFE blocker (#035-M2)
  → O/U gols: Poisson(lambdaTotalOU) — stats = insumo raw dos picks (#187)
       + Dixon-Coles τ(ρ) no matrix interno (#028, #078)
  → BTTS: Poisson dos lambdas exibidos (#187) — fusão 40/30/30 (#043)
       preservada em bttsFusionProb (não alimenta mais os picks)
  → Corners Engine v2 (4.5–12.5) com redução 20% (#043)
  → 1X2: implied_probs(odds) [+ ML ensemble] — espelho de mercado ROTULADO
       na UI (#187, decisão opção b; #064)
  → selecionar_mercados_v2 (market_service.py — ativo desde #035-M1)
       ev_classification 4 níveis (#028) — SAFE via circuit breaker (#043)
       linhas altas (cards >2.5, corners >10.5) só com odd real (#187)
       market_reference_signal capping por qualidade (#031, fontes #187)
       bankroll_engine Quarter Kelly com caps (#028)
       correlation_matrix anti-redundância (#028)
  → odds enrichment API-Football (#120; famílias de bet único #187)
       → reclassificação pós-enrichment (#187)
  → ancora_mercado.aplicar_ancora (#231) — só com PROB_SOURCE=mercado; flag desligada = payload inalterado
       EV contra consenso entre casas (#232): consenso_odds.py, `odds_consenso` do record, n_casas ≥ 3
       classificação em valor + confiança na âncora (#233): mesmos limiares, só âncora fresca chega a SAFE/NQ
  → Next.js (Vercel) — rótulos da fonte/EV só com a flag (#234, lib/fonteProbabilidade.ts)
```

**Calibração per-league automática** (`league_calibrator.py`): deflation (O/U, BTTS, 1X2, cards #056, corners), lambda weights season/recent, xG blend, BTTS fusion, thresholds safe_prob de 6 mercados, Dixon-Coles ρ (#078), home advantage γ (#078), SAFE enabled per liga (#054 — 36/37 ligas com `safe_enabled=true`).

## Contrato Mistral (#082, reforçado #181)

**Mistral é EXCLUSIVAMENTE narrativa.** Arquivo: `backend/services/mistral_analysis.py` (prompt v3.0, `MistralAnalysisService`, **temperature 0.15**).

- **Faz:** `summary`, `key_points`, `recommendation`, `confidence` (informativo), corners review opcional.
- **NÃO faz:** calcular/modificar probabilidades, auditar pipeline, ajustar lambdas/thresholds/pesos, classificar picks (SAFE/NEUTRO), **citar probabilidades raw (pré-deflação) em narrativa (#181)**, **computar EV no texto (#181)**.
- Sem `MISTRAL_API_KEY` ou Mistral indisponível → retorna default com `confidence=0`. **Não afeta** cálculos.
- Não alterar o prompt sem preservar as 4 camadas anti-alucinação (#001, #002).
- **Probs no prompt em duas camadas (#181):** "Estatísticas Poisson" carrega RAW (uso interno do modelo), "PICKS DO PIPELINE" carrega DEFLATED (única fonte legítima para narrativa). Mistral é instruído via prompt rules a só citar deflated. Validação `backend/ai/mistral_contract.py::validate_output` inspeciona resumo + key_points + recomendação (full text) e loga violações via `sportsbankzu.mistral.contract`. Camada 6 (`_validate_recommendation_vs_pipeline` em `mistral_analysis.py`) só inspeciona `recomendacao_principal` e direção Over/Under — limitação documentada na docstring da função.
- **Vocabulário de operador — prompt v3.1 (#255).** A narrativa não pode citar "lambda", "deflação"/"deflacionado" nem "banda" — o operador lê "chance", "mínimo" (fair_odd), "paga" (book_odd), "gols/escanteios esperados por jogo". `validate_output` ganha uma quarta camada (`_VOCABULARIO_INTERNO`) sobre o mesmo texto completo das três anteriores. `SEM_RECOMENDACAO` (`backend/ai/mistral_contract.py`) é a única ocorrência do texto de "sem recomendação" — o prompt a importa em vez de repetir.

## Domínio

- Mercados: 1X2, O/U 0.5–4.5, BTTS, Double Chance, Corners 4.5–12.5, Cards O/U 2.5–5.5
- Classificação (#028): SAFE / NEUTRO_QUALIFICADO / NEUTRO / NO_BET
- Regimes: NORMAL, HIPER-OFENSIVA
- 22+ ligas europeias e sul-americanas + Copa do Brasil
- UI em pt-BR; código e comentários em inglês

## Checklist novo mercado (#006)

Os 7 pontos obrigatórios estão na skill `novo-mercado` (`.claude/skills/novo-mercado/SKILL.md`).

## Proibições (regras travadas — NÃO violar sem entrada em REGRAS_ATIVAS)

1. **Não inventar nomes de spec.** Se não está em `REGRAS_ATIVAS.md`, não existe (ex.: "v5.5-ML" foi alucinação propagada).
2. **Não alterar thresholds sem auditoria.** Os atuais (#042) vieram de auditoria de 27 jogos.
3. **Não reativar SAFE** sem 3 auditorias consecutivas com accuracy > 50% (#043).
4. **Não remover deflations** sem lambda error < 0.5 por 3 rodadas (#043).
5. **Não duplicar funções** — verificar `services/` e `modeling/` antes de criar (caso #035-M4: cópia em `main.py`).
6. **Não mergear PR** sem entrada em `docs/REGISTRO_CORRECOES.md` (e `REGRAS_ATIVAS.md` se permanente).
7. **Threshold change > 15% BLOQUEADO** sem dados.
8. **MIN_N_BRIER = 20** (#079) — auditorias com N<20 são apenas diagnósticas, nunca decisórias.
9. **Complementares > 105% BLOQUEADOS** (#098).
10. **Deflação progressiva contínua por nós (#105, contínua desde #189-a)** — NÃO reverter para uniforme nem para degrau por banda.
11. **Classificação usa prob raw; EV usa prob deflacionada** (#106).
12. **Encolhimento de amostra pequena nos DOIS lados do λ (#208)** — ataque e defesa adversária recebem o mesmo peso `n/8`; contagem ausente não encolhe, amostra 0 encolhe.
13. **Auditor de premissas reimplementa a matemática de referência (#209)** — NÃO deduplicar contra o pipeline; a duplicação é o mecanismo. Campo novo da FootyStats entra no manifesto (#210).
14. **Proibido afirmar efeito ou concluir patch sem medição empírica (SDD)** — Alterações de cálculo, filtro ou classificação exigem diff de execução real (antes vs. depois). Hipóteses teóricas não substituem teste de payload ponta a ponta.
15. **Proibido `.get(k, alternativa)` no caminho de decisão (#225-c)** — `.get` só usa a alternativa quando a chave está AUSENTE; o record cria as chaves sempre, então a alternativa é inalcançável por construção (#201, #208, #217, #225-b são a mesma falha). Use `primeiro_valido`/`pegar` de `backend/utils/valores.py`, que preservam `0`, `""` e `False`. Inventário: `python3 scripts/varredura_get.py`. Gate: `tests/test_225c_fallback_morto.py`.
16. **Proibido ativar alteração em laço sem Etapa 5 declarada e testada** — rede de segurança que nunca disparou em teste não conta como rede. A camada de calibragem (#248) é o caso de referência: a reversão existia no código, mas a janela de versões ficava vazia a cada ciclo e ela nunca disparou em 10 ciclos. Redesenhada no #253 (âncora validada + teto de deriva de 4pp; disparo provado em `tests/calibragem/test_15_governanca_por_ancora.py`). O julgamento é por família, somando as ligas (#253-a; janela de 20 jogos em mediana de 5,5 ciclos, prova em `test_16_julgamento_por_familia.py`). **Isso não liga a camada.**
17. **Proibido alterar campo lido por outro subsistema sem auditar o consumidor externo (Etapa 2-bis)** — vale mesmo que o teste interno passe e o SDD original (etapas 1–4) tenha sido cumprido. O caso `calibrated_prob` ↔ gate #230 é o precedente: a camada escrevia no campo, o ledger lia, e ninguém auditou o contrato de saída.

## Finalização obrigatória pós-alteração

`CLAUDE.md` e os 3 arquivos de REGRAS existem em **dois diretórios espelhados** — sincronizar antes do commit.

```bash
# 1. Espelhar
cp sportsbankzu-pro/docs/REGISTRO_CORRECOES.md docs/REGISTRO_CORRECOES.md
cp sportsbankzu-pro/docs/REGRAS_ATIVAS.md      docs/REGRAS_ATIVAS.md
cp sportsbankzu-pro/docs/INDICE_REGRAS.md      docs/INDICE_REGRAS.md
cp sportsbankzu-pro/CLAUDE.md                  CLAUDE.md

# 2-3. Commit + push
cd sportsbankzu-pro && git add -A \
  && git commit -m "feat/fix/refactor: descrição curta (#NNN)" \
  && git push origin main

# 4. Deploy do backend — JA E AUTOMATICO no push acima
#    .github/workflows/deploy-lambda.yml dispara em push na main quando o commit toca
#    backend/**, scripts/deploy_lambda.py ou o proprio workflow. Ele roda pytest -q e, se
#    passar, empacota, sobe pro S3, faz update-function-code e aquece o cache de 22 ligas.
#    Rodar o script na mao apos o push e um SEGUNDO deploy do mesmo codigo. Use-o apenas
#    fora do fluxo de push (hotfix a partir de branch, ou quando o workflow falhou):
# python scripts/deploy_lambda.py

# 5. Validar
curl -s https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws/health
```

Atalho: `bash scripts/finalize.sh` roda 1–3 automaticamente. Pular apenas para alterações exclusivas de doc local.

## Formato de entrada em REGISTRO_CORRECOES.md

```
## NNN — Título descritivo
**Data:** YYYY-MM-DD | **Arquivos:** ... | **Severidade:** Crítica/Alta/Média/Baixa | **Status:** Corrigido/Implementado

### Problema identificado · Causa raiz · Correções aplicadas (com camadas) · Lição aprendida
```

**Exigem entrada:** lógica de cálculo, thresholds, pesos, pipeline, prompt Mistral, infraestrutura. Typos/formatação não.
