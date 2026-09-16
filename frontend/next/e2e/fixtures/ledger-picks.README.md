# `ledger-picks.json` — proveniência (Task 25-bis, #257)

**Mesma fonte de `ledger-agregado.json`** (ver `ledger-agregado.README.md`), não uma nova captura: união dos `picks` das 14 respostas `GET /ledger/dia?data=D` (D=2026-09-03..2026-09-16) da Function URL de produção, filtrada por `classification ∈ {SAFE, NEUTRO_QUALIFICADO}` e `outcome != null` — mesma regra de `ledger_leitura.picks()`.

`picks.length == 78`, igual a `ledger-agregado.json.acerto.resolvidos` — checagem cruzada obrigatória (as duas fixtures têm que concordar, senão os testes que comparam as duas telas ficam inconsistentes entre si). Verificado nesta tarefa com um script que carrega os dois arquivos e compara `len(picks)` contra `acerto.resolvidos`: os dois valem 78. Todo `outcome` é `0` ou `1`, nunca `null` (checado programaticamente).
