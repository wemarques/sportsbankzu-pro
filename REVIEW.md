# Regras de Review — SportsBank Pro

> Este arquivo é lido pelo Claude Code Review (GitHub Actions) e pelo plugin /code-review.
> Referência: CLAUDE.md + docs/REGRAS_CORRECAO_SISTEMA.md

## BLOQUEAR PR se:

- Altera `ev_classification.py` sem mencionar estado do circuit breaker SAFE (#043)
- Altera `lambda_calculator.py` sem mencionar deflation ativo 0.85 (#043)
- Altera `market_service.py` sem verificar impacto no pipeline V2 (#035)
- Altera `corners_engine.py` sem mencionar redução 20% ativa (#043)
- Altera `fixtures_service.py` sem verificar pesos BTTS (40/30/30) e deflation 0.80 (#043)
- Altera `prompt_templates.py` ou `match_analysis_service.py` sem manter defesas anti-alucinação (#001, #002)
- Altera thresholds em `ev_classification.py` sem dados de auditoria que justifiquem
- Cria nomes de especificação não documentados no REGRAS (ex: "v5.5-ML")
- Commita credenciais reais ou reverte remoção de placeholders (#046)
- Altera pesos calibráveis (lambda, BTTS, corners, xG blend) sem backtesting documentado

## EXIGIR em todo PR:

- Entrada correspondente no `docs/REGRAS_CORRECAO_SISTEMA.md` para qualquer mudança em lógica de cálculo
- Referência a regras CLAUDE.md de investigação aplicadas
- `pytest -q` passando
- Se frontend: `cd frontend/next && npm run build` sem erros
- Se altera pipeline: verificar que `selecionar_mercados_v2` continua sendo chamado (não reverter para v1)

## ATENÇÃO ESPECIAL:

- **SAFE está desabilitado** via circuit breaker (#043). Não reativar sem 3 auditorias com accuracy > 50%
- **Lambda tem deflation** 0.85 O/U, 0.80 BTTS (#043). Não remover sem lambda error < 0.5
- **Corners reduzidos** 20% (#043). Não remover sem corners accuracy > 50%
- **26+ branches** no repositório — verificar conflitos antes de mergear branches antigas
- **Pipeline V2 ativo** desde #035 — `fixtures_service.py` chama `selecionar_mercados_v2`

## MERCADOS E PARÂMETROS (referência rápida):

| Mercado | safe_prob | safe_ev | safe_edge | Arquivo |
|---------|-----------|---------|-----------|---------|
| 1X2 | 62% | 8% | 6% | ev_classification.py |
| Over/Under | 75% | 6% | 5% | ev_classification.py |
| BTTS | 75% | 6% | 5% | ev_classification.py |
| Double Chance | 82% | 4% | 3% | ev_classification.py |
| Corners | 72% | 8% | 6% | ev_classification.py |
| Cards | 75% | 8% | 6% | ev_classification.py |
