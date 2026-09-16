# Reformulação do frontend — plano 2 (fase 1: backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar, ao lado do dashboard atual e sem tocar em cálculo do pipeline, os três contratos de backend que a reformulação do frontend depende (spec §6.3): `GET /ledger/dia`, `GET /ledger/agregado`, o contrato `fair_odd`/`book_odd` já existente em `/fixtures` (prova, não implementação) e o prompt Mistral v3.1 em vocabulário de operador.

**Architecture:** `prediction_ledger × ledger_outcomes` é a fonte única do que o usuário vê (spec §6.3: "tudo que o usuário vê sai do ledger... isso inclui Brier e calibração"). `backend/services/ledger_leitura.py` faz uma consulta por janela de `published_at`, aplica os mesmos filtros que o backfill do #248 já valida (`filtrar_amostra` #252/#252-a, `escolher_ultima_geracao`, `classificar_familia`) e nunca lê `audit_results` (Regra #244, proibição 13). `backend/routes/ledger.py` só traduz parâmetro HTTP e erro em status code. Os filtros de amostra saem de `scripts/` (que a Lambda não empacota) para `backend/services/`, porque agora um caminho de produção — não só scripts locais — depende deles em runtime. O prompt Mistral troca "lambda"/"deflação"/"banda" por vocabulário de operador; `mistral_contract.py` ganha uma quarta camada de rejeição que trava o vocabulário interno na narrativa, ao lado das três que já existem (#181 mercado fora da lista, #238-a número divergente, #146 EV computado no texto).

**Tech Stack:** FastAPI (Python 3.11), psycopg2 (PostgreSQL/RDS), pytest (`python -m pytest -q -o addopts=""`). Frontend: Next.js 14 App Router (proxies de rota, sem novo componente visual).

**Spec:** `docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md` — ler inteira antes de implementar; este plano argumenta a partir dela, sobretudo §0 (contratos conferidos), §6.3 (contratos novos de backend) e §7 (validação). Ver também `docs/superpowers/plans/2026-09-15-reformulacao-frontend-fases-0-2-3.md` (plano irmão, fases 0/2/3 do frontend — este plano não depende dele para rodar, mas as fases 4-6 dependem deste).

**Global Constraints**

- Fonte única: `prediction_ledger × ledger_outcomes`, só geração pré-apito (#252) fora da janela contaminada (#252-a, e só onde ela se aplica — ver Task 2). `audit_results` é diagnóstico interno; nenhuma rota nova o lê (proibição 13, Regra #244).
- Nenhuma mudança em `backend/modeling/calibragem/` nem em cálculo de pipeline (proibições 1-13 do CLAUDE.md continuam valendo). Este plano é leitura nova + reorganização de onde os filtros moram + texto de prompt.
- `.get(k, alternativa)` no caminho de decisão é proibido (proibição 15) — usar checagem explícita `is None`, nunca depender de um valor-alternativa alcançável.
- Nenhum teste chama `psycopg2.connect` de verdade. Todo teste que precisa de "banco" substitui a função `_conn()` do módulo por um dublê (padrão já usado em `tests/test_252b_consumidores_do_ledger.py`, `tests/test_252c_ledger_grava_kickoff.py`).
- Numeração **#255**. Todo teste novo é `tests/test_255_*.py`. Toda entrada de registro cita #255.
- `MIN_N_BRIER = 20` (#079, proibição 8) — abaixo disso, `brier`/`buckets` vêm `null`, nunca um número calculado sobre amostra pequena.
- `stake` nunca foi gravado no ledger (`linhas_do_bundle`, `backend/services/prediction_ledger.py:706-729`, não passa `stake=`) — gravar o stake é mudança no PRODUTOR e fica fora desta fase. `retorno` em `/ledger/agregado` vem `null` com `motivo: "stake_nao_gravado_no_ledger"`; o contrato de unidade (fração de banca, `0 < stake ≤ 1`) fica escrito aqui para quem implementar o produtor depois.
- Cada tarefa fecha com: `python -m pytest -q -o addopts=""` verde (suíte inteira, não só o arquivo novo — a mudança do Mistral mexe em teste alheio), commit próprio. Commits terminam com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` (ver Task 7 para a exceção do commit de fechamento).
- Sem commit automático de docs a cada tarefa: os quatro arquivos de regra (`CLAUDE.md`, `docs/REGISTRO_CORRECOES.md`, `docs/REGRAS_ATIVAS.md`, `docs/INDICE_REGRAS.md`) só mudam na Task 7 (fechamento), junto com o espelho para `c:\painel_apostas\sportsbank-pro\`.

---

## Contradições spec × código encontradas (ler antes de implementar)

1. **`retorno` em `/ledger/agregado`.** A spec (§6.3) descreve a fórmula completa (`soma de stake × (book_odd − 1)... stake = a coluna gravada em prediction_ledger convertida a fração da banca`) como se a coluna já tivesse dado. Ela não tem — `stake` é sempre `NULL` (confirmado lendo `linhas_do_bundle`, `backend/services/prediction_ledger.py:706-729`: a chamada a `montar_linha` nunca passa `stake=`). Este plano implementa o campo como `null` com `motivo`, documentado no Global Constraints acima; a fórmula da spec fica pronta para quando a coluna existir.
2. **Contrato `fair_odd`/`book_odd`.** A spec trata como "o que falta" (§6.2: "`fair_odd` e `book_odd` separados no mapeamento" | "Existe: sim"). Lendo `backend/models/market_output.py:64` e `:176-177`, `MarketOutput` já tem os dois campos e `to_legacy_mercado()` já os inclui sempre. O que falta é só a **prova** (Task 5) — não há gap de produção aqui, ao contrário do que a lista de "o que falta" sugere.
3. **Janela contaminada #252-a e `published_prob`.** A spec não menciona a diferença, e o texto do #252-a em `docs/REGRAS_ATIVAS.md` fala genericamente em "todo consumidor que precisa de prognóstico". `fora_da_janela_contaminada` (em `scripts/amostra_ledger.py` hoje) só corta quando `campo == "calibrated_prob"` — para qualquer outro campo (aqui, `published_prob`) a função é no-op por desenho. Isso é o comportamento CORRETO para o ledger público (`published_prob` é o que o operador viu de verdade, contaminado ou não pelo bug da camada #248/#251; o corte existe para proteger a medição do MODELO contra mercado, não para apagar histórico real), mas como o texto de #252-a nunca nomeou essa distinção, a Task 7 estende a "Estado de aplicação" das duas regras para deixar isso explícito.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/services/amostra_ledger.py` (criar) | `filtrar_amostra`/`so_pre_jogo`/`fora_da_janela_contaminada`/`descrever`/`JANELA_CONTAMINADA_251`, movidos de `scripts/` — a Lambda só empacota `backend/` |
| `scripts/amostra_ledger.py` (modificar → shim) | reexporta de `backend/services/amostra_ledger.py`; os três scripts consumidores não mudam |
| `backend/services/ledger_leitura.py` (criar) | `dia(data)`, `agregado(periodo, familia, liga)` — leitura pura do ledger |
| `backend/routes/ledger.py` (criar) | `GET /ledger/dia`, `GET /ledger/agregado` |
| `backend/main.py` (modificar) | registro do router de `ledger` |
| `frontend/next/src/app/api/ledger/dia/route.ts` (criar) | proxy no padrão de `api/ml/status/route.ts` |
| `frontend/next/src/app/api/ledger/agregado/route.ts` (criar) | idem |
| `backend/ai/mistral_contract.py` (modificar) | `_VOCABULARIO_INTERNO`, `SEM_RECOMENDACAO`, quarta camada de `validate_output`, `aligned_recommendation` sem "deflação" |
| `backend/services/mistral_analysis.py` (modificar) | prompt v3.1 — regra "Vocabulário de operador", exemplos sem "lambda", `SEM_RECOMENDACAO` importado |
| `tests/test_255_amostra_ledger_no_backend.py` (criar) | prova a Task 1 |
| `tests/test_255_ledger_leitura.py` (criar) | prova a Task 2, com dublê de conexão |
| `tests/test_255_rotas_ledger.py` (criar) | prova a Task 3, com `TestClient` |
| `tests/test_255_fair_odd_book_odd.py` (criar) | prova a Task 5 (contrato já existente) |
| `tests/test_255_vocabulario_mistral.py` (criar) | prova a Task 6 |
| `tests/test_238a_contrato_numerico.py` (modificar, 2 linhas) | fixture não pode mais usar "deflacao" no texto esperado sem violação |
| `docs/REGISTRO_CORRECOES.md`, `docs/REGRAS_ATIVAS.md`, `docs/INDICE_REGRAS.md`, `CLAUDE.md` (modificar, Task 7) | registro #255, estado de aplicação de #252/#252-a, tabela de rotas, parágrafo Mistral v3.1 |

---

## Task 1: Mover `amostra_ledger` para `backend/services/`, com shim em `scripts/`

**Por quê (Spec da tarefa — Etapa 1 do SDD).** `backend/services/ledger_leitura.py` (Task 2) roda dentro da Lambda em produção e precisa de `filtrar_amostra`. O deploy da Lambda só empacota `backend/`: `scripts/deploy_lambda.py:38` (`shutil.copytree(SRC_DIR / "backend", BUILD_DIR / "backend", ...)`) e `.github/workflows/deploy-lambda.yml:97` (`cp -r backend lambda_build/backend`) — `scripts/` nunca entra no zip. Hoje `filtrar_amostra` mora em `scripts/amostra_ledger.py`; se `ledger_leitura.py` importasse de lá, a primeira chamada em produção quebraria com `ModuleNotFoundError`. Rastreabilidade: produtor = `backend/services/prediction_ledger.py::kickoff_da_linha` (já usado por `scripts/amostra_ledger.py` hoje); consumidor novo = `backend/services/ledger_leitura.py` (Task 2), rodando dentro do mesmo processo Lambda.

**Critério de aceite.** `backend.services.amostra_ledger` expõe os mesmos objetos que `scripts/amostra_ledger.py` expõe hoje. `scripts/amostra_ledger.py` vira uma reexportação — `A.so_pre_jogo is B.so_pre_jogo` onde `A` é o módulo de scripts e `B` o de backend. `tests/test_252b_consumidores_do_ledger.py` e `tests/test_252c_ledger_grava_kickoff.py` continuam verdes sem alteração.

**Cenários de borda.** Nenhum comportamento de filtro muda — é puro reposicionamento de arquivo; qualquer diferença de resultado entre antes/depois é regressão, não decisão de produto.

- [ ] **Step 1: Teste primeiro (falha: `backend.services.amostra_ledger` não existe)**

`tests/test_255_amostra_ledger_no_backend.py`:
```python
# -*- coding: utf-8 -*-
"""#255 — os filtros do ledger tem de estar DENTRO de backend/, porque o
deploy da Lambda so empacota backend/ (`scripts/deploy_lambda.py:38`,
`.github/workflows/deploy-lambda.yml:97`) e as rotas `/ledger/*` (#255,
`backend/services/ledger_leitura.py`) os usam em runtime. Antes desta tarefa
a implementacao morava em `scripts/amostra_ledger.py`, invisivel para a
Lambda.
"""
import importlib
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]


def test_implementacao_mora_em_backend_services():
    from backend.services.amostra_ledger import (
        JANELA_CONTAMINADA_251, descrever, filtrar_amostra,
        fora_da_janela_contaminada, kickoff_da_linha, so_pre_jogo,
    )
    assert callable(filtrar_amostra) and callable(so_pre_jogo)
    assert callable(fora_da_janela_contaminada) and callable(descrever)
    assert callable(kickoff_da_linha)
    assert JANELA_CONTAMINADA_251[0].year == 2026


def test_scripts_amostra_ledger_e_um_shim():
    """`scripts/amostra_ledger.py` so reexporta. Sem isso, dois lugares
    implementariam o mesmo filtro (proibicao 5) e um deles ficaria fora do
    pacote que a Lambda empacota — o proprio defeito que esta tarefa fecha."""
    src = (_RAIZ / "scripts" / "amostra_ledger.py").read_text(encoding="utf-8")
    assert "def so_pre_jogo" not in src
    assert "def fora_da_janela_contaminada" not in src
    assert "def filtrar_amostra" not in src
    assert "from backend.services.amostra_ledger import" in src


def test_mesmos_objetos_dos_dois_caminhos():
    sys.path.insert(0, str(_RAIZ))
    from backend.services import amostra_ledger as B
    A = importlib.import_module("scripts.amostra_ledger")
    assert A.so_pre_jogo is B.so_pre_jogo
    assert A.fora_da_janela_contaminada is B.fora_da_janela_contaminada
    assert A.filtrar_amostra is B.filtrar_amostra
    assert A.descrever is B.descrever
    assert A.kickoff_da_linha is B.kickoff_da_linha
    assert A.JANELA_CONTAMINADA_251 == B.JANELA_CONTAMINADA_251
```

Run: `python -m pytest -q -o addopts="" tests/test_255_amostra_ledger_no_backend.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.amostra_ledger'`.

- [ ] **Step 2: Criar `backend/services/amostra_ledger.py` — mesmo corpo, novo lar**

Conteúdo integral (corpo idêntico ao de `scripts/amostra_ledger.py` hoje; só o cabeçalho muda para explicar o novo endereço e o `sys.path` hack sai, porque dentro de `backend/` o pacote já resolve sem ele):

```python
# -*- coding: utf-8 -*-
"""#255 - validade da amostra lida do `prediction_ledger` (movido de
`scripts/amostra_ledger.py`; a implementacao original e de #252/#252-a/#252-b).

Por que mora em `backend/services/` e nao em `scripts/`: o deploy da Lambda
so empacota `backend/` (`scripts/deploy_lambda.py:38`,
`.github/workflows/deploy-lambda.yml:97` — `cp -r backend lambda_build/backend`,
nada de `scripts/`). As rotas `/ledger/dia` e `/ledger/agregado` (#255,
`backend/services/ledger_leitura.py`) rodam DENTRO da Lambda em producao e
precisam destes filtros em runtime; um modulo em `scripts/` la dentro daria
`ModuleNotFoundError` na primeira chamada. `scripts/amostra_ledger.py`
continua existindo como reexportacao (mesmos objetos) para os tres
consumidores de script (`comparar_com_mercado.py`, `medir_inclinacao.py`,
`grade_deflacao_por_familia.py`) e para os testes #252b/#252c, que continuam
verdes sem alteracao.

- #252: so geracao publicada ANTES do apito e prognostico. `kickoff_utc` e
  nula no ledger, entao o kickoff sai do sufixo epoch do match_id; sem
  kickoff nenhum a linha SAI (falha fechada) e e contada.
- #252-a: `calibrated_prob` publicada em [inicio, fim) era a saida da camada
  #248, nao o modelo (#251). So essa coluna e cortada — qualquer outro campo
  (ex.: `published_prob`, usado por `ledger_leitura.py`) passa intacto, por
  desenho: ver Task 2 do plano #255 para o porque.

As linhas de entrada sao dicts com `match_id`, `published_at` e `kickoff_utc`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

# #252-c: a resolucao do kickoff tem UMA implementacao, no proprio backend.
from backend.services.prediction_ledger import kickoff_da_linha  # noqa: F401

# Inicio = primeira versao (a,b) != (0,1) em calibragem_versoes; fim = Deploy
# Lambda de b2eec7d (#251). Mover so com nova medicao registrada.
JANELA_CONTAMINADA_251 = (
    datetime(2026, 9, 10, 23, 2, 6, tzinfo=timezone.utc),
    datetime(2026, 9, 14, 4, 50, 22, tzinfo=timezone.utc),
)

Linhas = Sequence[Dict[str, Any]]


def so_pre_jogo(linhas: Linhas) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Mantem `published_at < kickoff`; no apito tambem sai. Conta picks e
    jogos que SUMIRAM (nenhuma geracao deles sobreviveu)."""
    mantidas: List[Dict[str, Any]] = []
    pos, sem = [], []
    for ln in linhas:
        kickoff = kickoff_da_linha(ln.get("match_id"), ln.get("kickoff_utc"))
        if kickoff is None:
            sem.append(ln)
        elif ln.get("published_at") is None or ln["published_at"] >= kickoff:
            pos.append(ln)
        else:
            mantidas.append(ln)
    ficaram = {ln.get("match_id") for ln in mantidas}
    return mantidas, {
        "pos_kickoff": len(pos),
        "sem_kickoff": len(sem),
        "jogos_pos_kickoff": len({ln.get("match_id") for ln in pos} - ficaram),
        "jogos_sem_kickoff": len({ln.get("match_id") for ln in sem} - ficaram),
    }


def fora_da_janela_contaminada(linhas: Linhas, campo: str
                               ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Tira da serie `calibrated_prob` o publicado em [inicio, fim). As outras
    colunas nao passaram pela camada e ficam inteiras."""
    if campo != "calibrated_prob":
        return list(linhas), {"contaminados": 0, "jogos_contaminados": 0}
    ini, fim = JANELA_CONTAMINADA_251
    mantidas, fora = [], []
    for ln in linhas:
        pub = ln.get("published_at")
        (fora if pub is not None and ini <= pub < fim else mantidas).append(ln)
    ficaram = {ln.get("match_id") for ln in mantidas}
    return mantidas, {
        "contaminados": len(fora),
        "jogos_contaminados": len({ln.get("match_id") for ln in fora} - ficaram),
    }


def filtrar_amostra(linhas: Linhas, campo: str
                    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """#252 e depois #252-a, na ordem do gate. Devolve as duas contagens juntas."""
    mantidas, c1 = so_pre_jogo(linhas)
    mantidas, c2 = fora_da_janela_contaminada(mantidas, campo)
    return mantidas, {**c1, **c2}


def descrever(c: Dict[str, int]) -> str:
    """As duas linhas de relatorio. Filtro silencioso nao conta (#252, item 3)."""
    return (
        f"#252 so pre-kickoff: fora {c.get('pos_kickoff', 0)} picks publicados no/apos o apito "
        f"({c.get('jogos_pos_kickoff', 0)} jogos sumiram) e {c.get('sem_kickoff', 0)} sem kickoff "
        f"conhecido ({c.get('jogos_sem_kickoff', 0)} jogos sumiram)\n"
        f"#252-a janela contaminada da camada (#251): fora {c.get('contaminados', 0)} picks "
        f"pre-apito publicados entre 2026-09-10 23:02:06 e 2026-09-14 04:50:22 UTC "
        f"({c.get('jogos_contaminados', 0)} jogos sumiram)"
    )
```

- [ ] **Step 3: `scripts/amostra_ledger.py` vira shim**

Substituir o arquivo inteiro por:
```python
# -*- coding: utf-8 -*-
"""#255 - reexportacao. A implementacao mora em
`backend/services/amostra_ledger.py` (deploy da Lambda so empacota
`backend/`; as rotas `/ledger/*` precisam destes filtros em runtime — ver a
docstring de la). Os tres consumidores de script (`comparar_com_mercado.py`,
`medir_inclinacao.py`, `grade_deflacao_por_familia.py`) continuam importando
DAQUI e recebem os MESMOS objetos
(`tests/test_252b_consumidores_do_ledger.py::test_filtro_existe_em_um_modulo_so`,
`tests/test_255_amostra_ledger_no_backend.py`).
"""
from backend.services.amostra_ledger import (  # noqa: F401
    JANELA_CONTAMINADA_251,
    Linhas,
    descrever,
    filtrar_amostra,
    fora_da_janela_contaminada,
    kickoff_da_linha,
    so_pre_jogo,
)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -q -o addopts="" tests/test_255_amostra_ledger_no_backend.py tests/test_252b_consumidores_do_ledger.py tests/test_252c_ledger_grava_kickoff.py tests/test_252_gate_so_pre_kickoff.py tests/test_252a_gate_exclui_janela_contaminada.py`
Expected: PASS em todos — nenhum dos quatro arquivos #252* muda de comportamento, só de onde a implementação mora.

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde (o baseline antes desta tarefa é o mesmo depois).

- [ ] **Step 5: Commit**

```bash
git add backend/services/amostra_ledger.py scripts/amostra_ledger.py tests/test_255_amostra_ledger_no_backend.py
git commit -m "$(cat <<'EOF'
refactor(backend): move filtros do ledger para backend/services (#255)

A Lambda so empacota backend/; scripts/amostra_ledger.py fica reexportacao
para as rotas /ledger/* (Task 2) poderem importar os filtros em runtime.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `backend/services/ledger_leitura.py` — `dia(data)` e `agregado(periodo, familia, liga)`

**Objetivo e contexto (Etapa 1).** A spec (§6.3) pede duas leituras do ledger: o dia (para `/jogos?dia=ontem`) e o agregado (para `/desempenho`). Hoje nenhuma rota expõe `prediction_ledger × ledger_outcomes` — confirmado em spec §0 ("nenhuma rota expõe `prediction_ledger × ledger_outcomes`") e por leitura de `backend/main.py` (roteadores registrados, nenhum chamado `ledger`).

**Rastreabilidade de dados (produtor → consumidor).**
- Produtor: `backend/services/prediction_ledger.py::linhas_do_bundle` grava `prediction_ledger` (colunas usadas aqui: `match_id`, `league_id`, `market`, `selection`, `published_prob`, `book_odd`, `classification`, `published_at`, `kickoff_utc`) e `backend/cron_handler.py:213` grava `ledger_outcomes` via `registrar_desfechos_do_jogo`, com `detail` = o dict `actual_result` inteiro (`cron_handler.py:198-206`: `home_goals`, `away_goals`, `total_goals`, `btts`, `result_1x2`, `total_corners`, `total_cards`).
- Intermediário: nenhum — leitura direta com `psycopg2`, mesmo padrão de `backend/modeling/calibragem/repositorio.py::carregar_amostra` (reaproveitado, não reimplementado — proibição 5).
- Consumidor: `backend/routes/ledger.py` (Task 3) serve o retorno como JSON.
- Confirmado no código, sem inferir: `prediction_ledger` não tem `fair_odd` (só `book_odd`; `calibrated_prob`; `published_prob`) — `fair_odd` é **derivado** aqui como `round(1/published_prob, 2)`, nunca lido de coluna.

**Critérios de aceite.**
- `dia("2026-09-14")` com uma linha cujo `kickoff_utc` cai em 14/09 UTC aparece em `picks`; uma linha idêntica mas com `kickoff_utc` em 15/09 não aparece em `picks` do dia 14, mas conta em `mes`.
- Duas gerações do mesmo `(match_id, market, selection)`: só a mais recente published-antes-do-kickoff aparece (via `escolher_ultima_geracao`).
- `classification == "NO_BET"` nunca aparece em `picks` nem nos acumulados (filtrado na própria consulta SQL).
- `classification == "NEUTRO"` aparece em `picks` (listado) mas não conta em `resumo.picks`/`resumo.acertos` (só SAFE/NEUTRO_QUALIFICADO contam — espelha o estado `vale` do `JogoView` da spec §4.2).
- `agregado("7d")` com < 20 jogos resolvidos → `brier: null`, `buckets: null`, `amostra_curta: true`. Com ≥ 20 → `brier` numérico e `buckets` com 10 entradas cuja soma de `n` bate com o total de picks resolvidos.
- `agregado("temporada")` inclui tudo desde `2026-09-03` (primeiro pick do ledger, spec §6.3).
- `retorno` é sempre `{"valor": null, "pct_banca": null, "motivo": "stake_nao_gravado_no_ledger"}` (ver Global Constraints).
- Data/período inválidos levantam `ValueError` (a rota traduz para 400 — Task 3).

**Cenários de borda e fallback.**
- Kickoff desconhecido (nem `kickoff_utc` nem sufixo epoch do `match_id`) → a linha não entra em `picks` de dia nenhum (mesma falha fechada do #252-c em `escolher_ultima_geracao`/`so_pre_jogo`).
- `familia`/`liga` que não batem com nada → `por_familia`/`por_liga` com listas vazias, sem erro.
- Falha de conexão (`DATABASE_URL` ausente ou RDS fora) → `RuntimeError`/exceção do driver sobe; a rota (Task 3) traduz para 503, nunca 200 com dado inventado.

- [ ] **Step 1: Teste primeiro (falha: módulo não existe)**

`tests/test_255_ledger_leitura.py`:
```python
# -*- coding: utf-8 -*-
"""#255 — `backend/services/ledger_leitura.py`: leitura pura do ledger.

Dublê de conexao no padrao de `tests/test_252b_consumidores_do_ledger.py`:
uma classe `_Cursor`/`_Conn` que devolve linhas fixas para `execute`/
`fetchall`, sem tocar rede. `ledger_leitura._conn` e substituida direto —
mais simples que interceptar `psycopg2.connect` global, e nao ha guarda
autouse fora de `tests/calibragem/` proibindo o real (por isso a
substituicao explicita e obrigatoria em CADA teste que chama `dia`/`agregado`).
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.services import ledger_leitura as L

_UTC = timezone.utc


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._linhas

    def close(self):
        pass


class _Conn:
    def __init__(self, linhas):
        self.cur = _Cursor(linhas)

    def cursor(self):
        return self.cur

    def close(self):
        pass


def _linha(match_id, market, selection, prob, book_odd, classification,
          published_at, kickoff_utc, outcome=None, detail=None,
          league_id="premier-league"):
    return (match_id, league_id, market, selection, prob, book_odd,
            classification, published_at, kickoff_utc, outcome, detail)


# Um jogo com kickoff em 14/09, duas geracoes (so a ultima pre-kickoff conta).
_M1 = "premier-league-A-B-1789344000.0"          # 2026-09-14
_K1 = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
# Corners NEUTRO_QUALIFICADO no mesmo jogo — conta e aparece.
_M2 = "premier-league-C-D-1789344000.0"
# BTTS NEUTRO — aparece na lista, nao conta no resumo.
_M3 = "premier-league-E-F-1789344000.0"
# 1X2 NO_BET — nunca aparece (cortado na propria consulta).
_M4 = "premier-league-G-H-1789344000.0"
# Publicado APOS o kickoff (#252) — sumiu mesmo sem NO_BET.
_M5 = "premier-league-I-J-1789344000.0"
_K5 = datetime(2026, 9, 14, 18, 0, tzinfo=_UTC)


def _linhas_do_dia():
    return [
        # M1: geracao antiga (perde) + geracao nova (vence)
        _linha(_M1, "Over/Under", "Over 2.5", 0.62, 1.75, "SAFE",
              datetime(2026, 9, 12, 9, 0, tzinfo=_UTC), _K1),
        _linha(_M1, "Over/Under", "Over 2.5", 0.58, 1.80, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), _K1,
              outcome=1, detail={"total_goals": 3}),
        _linha(_M2, "Corners", "Corners Over 6.5", 0.60, None, "NEUTRO_QUALIFICADO",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1,
              outcome=0, detail={"total_corners": 5}),
        _linha(_M3, "BTTS", "BTTS Yes", 0.55, 1.90, "NEUTRO",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1,
              outcome=1, detail={"btts": True}),
        _linha(_M4, "1X2", "Home", 0.70, 1.20, "NO_BET",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1),
        _linha(_M5, "Cards", "Over 3.5", 0.60, 1.80, "SAFE",
              datetime(2026, 9, 14, 19, 0, tzinfo=_UTC), _K5),  # pos-kickoff
    ]


def test_dia_lista_a_ultima_geracao_pre_kickoff(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    por_match = {p["match_id"]: p for p in r["picks"]}
    assert por_match[_M1]["published_prob"] == 0.58          # a geracao NOVA
    assert por_match[_M1]["fair_odd"] == round(1 / 0.58, 2)
    assert por_match[_M1]["detail"] == "3 gols"


def test_dia_no_bet_nunca_aparece(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M4 not in {p["match_id"] for p in r["picks"]}


def test_dia_pos_kickoff_some_242(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M5 not in {p["match_id"] for p in r["picks"]}


def test_dia_neutro_aparece_mas_nao_conta(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M3 in {p["match_id"] for p in r["picks"]}          # listado
    # resumo so conta SAFE/NEUTRO_QUALIFICADO: M1 (SAFE) + M2 (NQ) = 2
    assert r["resumo"]["picks"] == 2


def test_dia_resumo_acertos_e_jogos(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    # M1 outcome=1 (acerto), M2 outcome=0 (erro) — os dois contados
    assert r["resumo"]["acertos"] == 1
    assert r["resumo"]["jogos"] == 2


def test_dia_data_invalida_levanta_value_error(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn([]))
    with pytest.raises(ValueError):
        L.dia("14-09-2026")


def test_detalhe_textual_por_familia():
    assert L._detalhe_textual("Corners", {"total_corners": 8}) == "8 escanteios"
    assert L._detalhe_textual("Cards", {"total_cards": 4}) == "4 cartões"
    assert L._detalhe_textual("Over/Under", {"total_goals": 3}) == "3 gols"
    assert L._detalhe_textual("BTTS", {"btts": True}) == "ambos marcaram"
    assert L._detalhe_textual("BTTS", {"btts": False}) == "só um marcou (ou nenhum)"
    assert L._detalhe_textual("Corners", None) is None
    assert L._detalhe_textual("Corners", {}) is None


def _linhas_agregado(n_jogos, acertos):
    """`n_jogos` picks Over/Under distintos, `acertos` deles com outcome=1."""
    base = datetime(2026, 9, 5, 12, 0, tzinfo=_UTC)
    out = []
    for i in range(n_jogos):
        mid = f"premier-league-T{i}-U{i}-{1788000000 + i * 10000}.0"
        kickoff = base + timedelta(hours=i)
        out.append(_linha(
            mid, "Over/Under", "Over 2.5", 0.55 + (i % 10) * 0.01, 1.80, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < acertos else 0, detail={"total_goals": 3},
        ))
    return out


def test_agregado_abaixo_do_piso_vem_null(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(10, 6)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["amostra_curta"] is True
    assert r["brier"] is None
    assert r["buckets"] is None
    assert r["acerto"]["jogos"] == 10


def test_agregado_acima_do_piso_calcula(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(25, 15)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["amostra_curta"] is False
    assert r["brier"] is not None
    assert r["buckets"] is not None
    assert len(r["buckets"]) == 10
    assert sum(b["n"] for b in r["buckets"]) == 25


def test_agregado_retorno_e_sempre_null_com_motivo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(25, 15)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["retorno"] == {
        "valor": None, "pct_banca": None,
        "motivo": "stake_nao_gravado_no_ledger",
    }


def test_agregado_periodo_invalido_levanta_value_error(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn([]))
    with pytest.raises(ValueError):
        L.agregado("1ano")


def test_agregado_filtra_por_familia_e_liga(monkeypatch):
    linhas = _linhas_agregado(25, 15)  # todos premier-league, Over/Under
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r_familia_errada = L.agregado("temporada", familia="Corners",
                                  hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r_familia_errada["acerto"]["picks"] == 0
    r_liga_certa = L.agregado("temporada", liga="premier-league",
                              hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r_liga_certa["acerto"]["jogos"] == 25
```

Run: `python -m pytest -q -o addopts="" tests/test_255_ledger_leitura.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.ledger_leitura'`.

- [ ] **Step 2: Implementar `backend/services/ledger_leitura.py`**

```python
# -*- coding: utf-8 -*-
"""#255 — leitura do ledger para `/ledger/dia` e `/ledger/agregado` (Fase 1
da reformulacao do frontend, spec §6.3).

Fonte unica: `prediction_ledger x ledger_outcomes`, so geracao pre-apito
(#252). NUNCA le `audit_results` — proibicao 13 / Regra #244 do CLAUDE.md
tambem valem para a tela que o usuario ve, nao so para calibracao.

Reaproveita, sem reimplementar (proibicao 5): `filtrar_amostra` (#252,
`backend/services/amostra_ledger.py` — movido da Task 1 deste plano),
`escolher_ultima_geracao` e `classificar_familia`
(`backend/modeling/calibragem/repositorio.py`, #248), e `_brier`/`MIN_N`
(`backend/services/brier_service.py`, #109/#079).

Contrato de saida (Etapa 2-bis, CLAUDE.md): este modulo e leitura pura — nao
grava nada, nao existe consumidor externo alem das rotas HTTP deste mesmo
plano (`backend/routes/ledger.py`, Task 3) e do frontend novo que ainda nao
existe (fase 4). `stake` nunca e gravado no ledger
(`prediction_ledger.linhas_do_bundle` nao passa `stake=` a `montar_linha`) —
por isso `retorno` sai `null` com `motivo`, nunca um numero inventado.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.modeling.calibragem.repositorio import (
    classificar_familia, escolher_ultima_geracao,
)
from backend.services.amostra_ledger import filtrar_amostra
from backend.services.brier_service import MIN_N, _brier

_FAMILIAS = ("Over/Under", "BTTS", "Corners", "Cards", "1X2", "Double Chance")
_PICKS_CONTADOS = ("SAFE", "NEUTRO_QUALIFICADO")     # o talao, spec §4.2 estado `vale`
_INICIO_TEMPORADA = "2026-09-03"                     # primeiro pick do ledger, spec §6.3
_FOLGA_PUBLICACAO_DIAS = 3   # published_at pode anteceder o kickoff em ate 3 dias


def _conn():
    import psycopg2
    dsn = (os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL nao esta definida — sem ela o psycopg2 tentaria "
            "localhost:5432, que nao e o banco (mesma guarda de #230-a)."
        )
    return psycopg2.connect(dsn, connect_timeout=5)


# #255: NO_BET nunca aparece (spec §4.2) — cortado na propria consulta, nao
# em Python, para ser estruturalmente impossivel de vazar numa rota nova.
_SQL_JANELA = """
    SELECT l.match_id, l.league_id, l.market, l.selection,
           l.published_prob, l.book_odd, l.classification,
           l.published_at, l.kickoff_utc,
           o.outcome, o.detail
      FROM prediction_ledger l
      LEFT JOIN ledger_outcomes o
        ON o.match_id  = l.match_id
       AND o.market    = l.market
       AND o.selection = l.selection
     WHERE l.published_at >= %s AND l.published_at < %s
       AND l.published_prob IS NOT NULL
       AND l.classification IN ('SAFE', 'NEUTRO_QUALIFICADO', 'NEUTRO')
"""


def _buscar_janela(inicio: datetime, fim: datetime) -> List[Dict[str, Any]]:
    """Uma consulta por chamada de `dia`/`agregado`. `filtrar_amostra` aplica
    #252 (pos-kickoff sai); o corte #252-a e no-op aqui porque so age sobre
    `calibrated_prob` — `published_prob` e o que o operador viu de verdade,
    contaminado ou nao pelo bug da camada #248 (ver Task 2 do plano #255).

    O `WHERE classification IN (...)` do SQL ja tira NO_BET na origem; o
    filtro em Python abaixo REPETE essa regra de proposito (defesa em
    profundidade, nao redundancia morta): um teste com dublê de cursor nao
    interpreta o texto do SQL (so devolve linhas fixas), e uma consulta
    futura que esqueca a clausula nao pode deixar NO_BET vazar — spec §4.2,
    "NO_BET nunca"."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(_SQL_JANELA, (inicio, fim))
        brutas = [
            {"match_id": r[0], "league_id": r[1] or "", "market": r[2],
             "selection": r[3],
             "published_prob": float(r[4]) if r[4] is not None else None,
             "book_odd": float(r[5]) if r[5] is not None else None,
             "classification": r[6], "published_at": r[7], "kickoff_utc": r[8],
             "outcome": r[9], "detail": r[10]}
            for r in cur.fetchall()
            if r[6] in ("SAFE", "NEUTRO_QUALIFICADO", "NEUTRO")
        ]
        cur.close()
    finally:
        conn.close()
    mantidas, _ = filtrar_amostra(brutas, "published_prob")
    return escolher_ultima_geracao(mantidas)


def _fair_odd(published_prob: Optional[float]) -> Optional[float]:
    """Nao ha coluna `fair_odd` no ledger (so `book_odd`) — deriva-se aqui,
    igual ao que `MarketOutput.compute_display` faz no momento da publicacao
    (`backend/models/market_output.py:147`)."""
    if published_prob is None or published_prob <= 0:
        return None
    return round(1.0 / published_prob, 2)


def _detalhe_textual(market: str, detail: Optional[Dict[str, Any]]) -> Optional[str]:
    """`detail` e o `actual_result` bruto do cron (`backend/cron_handler.py:198-206`):
    `home_goals`, `away_goals`, `total_goals`, `btts`, `result_1x2`,
    `total_corners`, `total_cards`. Aqui vira o texto por familia que a spec
    pede (§6.3): "8 escanteios", "3 gols". `None` quando falta a chave ou o
    desfecho ainda nao existe."""
    if not isinstance(detail, dict):
        return None
    m = (market or "").strip()
    if m == "Corners":
        v = detail.get("total_corners")
        return f"{int(v)} escanteios" if v is not None else None
    if m == "Cards":
        v = detail.get("total_cards")
        return f"{int(v)} cartões" if v is not None else None
    if m == "Over/Under":
        v = detail.get("total_goals")
        return f"{int(v)} gols" if v is not None else None
    if m == "BTTS":
        v = detail.get("btts")
        if v is None:
            return None
        return "ambos marcaram" if v else "só um marcou (ou nenhum)"
    if m in ("1X2", "Double Chance"):
        hg, ag = detail.get("home_goals"), detail.get("away_goals")
        if hg is not None and ag is not None:
            return f"{int(hg)}-{int(ag)}"
        return None
    return None


def _pick_json(l: Dict[str, Any]) -> Dict[str, Any]:
    familia = classificar_familia(l["market"], l["selection"])
    return {
        "match_id": l["match_id"], "league_id": l["league_id"],
        "kickoff_utc": l["kickoff_utc"].isoformat() if l["kickoff_utc"] else None,
        "familia": familia, "market": l["market"], "selection": l["selection"],
        "published_prob": l["published_prob"],
        "fair_odd": _fair_odd(l["published_prob"]),
        "book_odd": l["book_odd"],
        "classification": l["classification"],
        "outcome": l["outcome"],
        "detail": _detalhe_textual(l["market"], l["detail"]),
    }


def _resumo(linhas: List[Dict[str, Any]]) -> Dict[str, int]:
    contados = [l for l in linhas if l["classification"] in _PICKS_CONTADOS]
    resolvidos = [l for l in contados if l["outcome"] is not None]
    return {
        "picks": len(contados),
        "acertos": sum(1 for l in resolvidos if l["outcome"]),
        "jogos": len({l["match_id"] for l in resolvidos}),
    }


def dia(data: str) -> Dict[str, Any]:
    """Um dia: os picks cujo KICKOFF cai no dia `data` (UTC), mais os
    acumulados de 7 e 30 dias terminando neste dia (inclusive), por familia.

    Decisao de implementacao (a spec §6.3 nao fixa o limite exato de
    "semana"/"mes", so define `temporada` = desde 2026-09-03): semana = 7
    dias terminando em `data` (inclusive), mes = 30 dias — mesmos tamanhos
    de `/ledger/agregado?periodo=7d|30d`, para as duas rotas contarem do
    mesmo jeito (spec §7: "os numeros do ResumoDoDia de /ontem == os do
    agregado de /desempenho para o mesmo periodo").
    """
    try:
        dia_dt = datetime.strptime(data, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"data invalida: {data!r} (esperado YYYY-MM-DD)") from e

    fim_dia = dia_dt + timedelta(days=1)
    # Uma unica consulta cobrindo a maior janela necessaria (mes = 30 dias)
    # mais a folga de publicacao.
    linhas = _buscar_janela(
        dia_dt - timedelta(days=29 + _FOLGA_PUBLICACAO_DIAS), fim_dia,
    )

    def _na_janela(desde: datetime) -> List[Dict[str, Any]]:
        return [l for l in linhas
                if l.get("kickoff_utc") is not None
                and desde <= l["kickoff_utc"] < fim_dia]

    do_dia = _na_janela(dia_dt)
    picks_json = [_pick_json(l) for l in do_dia]

    def _acumulado(desde: datetime) -> Dict[str, Any]:
        na_janela = _na_janela(desde)
        return {
            fam: _resumo([l for l in na_janela
                         if classificar_familia(l["market"], l["selection"]) == fam])
            for fam in _FAMILIAS
        }

    return {
        "data": data,
        "picks": picks_json,
        "resumo": _resumo(do_dia),
        "semana": _acumulado(dia_dt - timedelta(days=6)),
        "mes": _acumulado(dia_dt - timedelta(days=29)),
    }


def _janela_periodo(periodo: str, hoje: Optional[datetime] = None
                    ) -> Tuple[datetime, datetime]:
    hoje = hoje or datetime.now(timezone.utc)
    fim = hoje.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if periodo == "7d":
        return fim - timedelta(days=7), fim
    if periodo == "30d":
        return fim - timedelta(days=30), fim
    if periodo == "temporada":
        inicio = datetime.strptime(_INICIO_TEMPORADA, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return inicio, fim
    raise ValueError(f"periodo invalido: {periodo!r} (esperado 7d|30d|temporada)")


def _segmento(linhas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Picks/acertos/jogos + Brier com o piso MIN_N=20 em JOGOS (#079)."""
    r = _resumo(linhas)
    resolvidos = [l for l in linhas
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]
    brier = None
    if r["jogos"] >= MIN_N:
        brier = round(_brier(
            [l["published_prob"] for l in resolvidos],
            [l["outcome"] for l in resolvidos],
        ), 4)
    return {**r, "brier": brier}


def _buckets_calibracao(resolvidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """10 faixas fixas [0,0.1) .. [0.9,1.0]. Soma de `n` == len(resolvidos)."""
    faixas = [(i / 10, (i + 1) / 10) for i in range(10)]
    out = []
    for lo, hi in faixas:
        cesta = [l for l in resolvidos
                 if lo <= l["published_prob"] < hi
                 or (hi == 1.0 and l["published_prob"] == 1.0)]
        if not cesta:
            out.append({"prob_media": None, "freq_real": None, "n": 0})
            continue
        prob_media = sum(l["published_prob"] for l in cesta) / len(cesta)
        freq_real = sum(l["outcome"] for l in cesta) / len(cesta)
        out.append({"prob_media": round(prob_media, 4),
                    "freq_real": round(freq_real, 4), "n": len(cesta)})
    return out


def agregado(periodo: str, familia: Optional[str] = None,
            liga: Optional[str] = None, hoje: Optional[datetime] = None
            ) -> Dict[str, Any]:
    """`periodo`: 7d|30d|temporada. `familia`/`liga` filtram o conjunto
    inteiro (acerto, brier, buckets, por_familia, por_liga)."""
    inicio, fim = _janela_periodo(periodo, hoje)
    linhas = _buscar_janela(inicio - timedelta(days=_FOLGA_PUBLICACAO_DIAS), fim)
    na_janela = [l for l in linhas
                 if l.get("kickoff_utc") is not None and inicio <= l["kickoff_utc"] < fim]

    contados = na_janela
    if liga:
        contados = [l for l in contados if l["league_id"] == liga]
    if familia:
        contados = [l for l in contados
                   if classificar_familia(l["market"], l["selection"]) == familia]

    resumo_geral = _segmento(contados)
    resolvidos = [l for l in contados
                  if l["classification"] in _PICKS_CONTADOS and l["outcome"] is not None]

    por_familia = {
        fam: _segmento([l for l in contados
                       if classificar_familia(l["market"], l["selection"]) == fam])
        for fam in _FAMILIAS
    }
    por_liga = {
        lg: _segmento([l for l in contados if l["league_id"] == lg])
        for lg in sorted({l["league_id"] for l in contados if l["league_id"]})
    }

    buckets = _buckets_calibracao(resolvidos) if resumo_geral["jogos"] >= MIN_N else None

    return {
        "periodo": periodo, "familia": familia, "liga": liga,
        "acerto": {"picks": resumo_geral["picks"], "acertos": resumo_geral["acertos"],
                  "jogos": resumo_geral["jogos"]},
        # #255: stake nunca e gravado no ledger — ver Global Constraints do plano.
        "retorno": {"valor": None, "pct_banca": None,
                   "motivo": "stake_nao_gravado_no_ledger"},
        "brier": resumo_geral["brier"],
        "amostra_curta": resumo_geral["jogos"] < MIN_N,
        "por_familia": por_familia,
        "por_liga": por_liga,
        "buckets": buckets,
    }
```

- [ ] **Step 3: Rodar e ver passar**

Run: `python -m pytest -q -o addopts="" tests/test_255_ledger_leitura.py`
Expected: PASS (12 testes).

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde.

- [ ] **Step 4: Commit**

```bash
git add backend/services/ledger_leitura.py tests/test_255_ledger_leitura.py
git commit -m "$(cat <<'EOF'
feat(backend): ledger_leitura.dia/agregado — leitura pura do ledger (#255)

Fonte unica prediction_ledger x ledger_outcomes; reaproveita filtrar_amostra
(#252), escolher_ultima_geracao e classificar_familia (#248) sem duplicar.
retorno vem null (stake nunca gravado) e brier/buckets respeitam MIN_N=20.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `backend/routes/ledger.py` — `GET /ledger/dia` e `GET /ledger/agregado`

**Spec.** Traduzir HTTP para as funções da Task 2: `data`/`periodo` inválidos → 400; falha de leitura (banco fora, `DATABASE_URL` ausente) → 503; sucesso → 200 com o dict de `ledger_leitura` serializado em JSON. Registrar o router em `backend/main.py` no mesmo padrão try/except dos demais (`backend/main.py:130-223`), para uma falha de import não derrubar o app inteiro.

**Critérios de aceite.** `GET /ledger/dia?data=2026-09-14` → 200. `GET /ledger/dia?data=lixo` → 400. `GET /ledger/agregado?periodo=1ano` → 400. Falha simulada de `ledger_leitura` → 503. `/ledger/dia` e `/ledger/agregado` aparecem em `app.routes`.

- [ ] **Step 1: Teste primeiro**

`tests/test_255_rotas_ledger.py`:
```python
# -*- coding: utf-8 -*-
"""#255 — contrato HTTP de `/ledger/dia` e `/ledger/agregado`.

A logica de consulta ja e testada em `test_255_ledger_leitura.py` com dublê
de conexão; aqui so o roteamento — substitui `ledger_leitura.dia`/`agregado`
por funcoes fake (nenhuma delas toca banco).
"""
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ledger_leitura

client = TestClient(app)


def test_dia_ok(monkeypatch):
    monkeypatch.setattr(ledger_leitura, "dia", lambda data: {"data": data, "picks": []})
    r = client.get("/ledger/dia", params={"data": "2026-09-14"})
    assert r.status_code == 200
    assert r.json()["data"] == "2026-09-14"


def test_dia_data_invalida_400(monkeypatch):
    def _falha(data):
        raise ValueError(f"data invalida: {data!r}")
    monkeypatch.setattr(ledger_leitura, "dia", _falha)
    r = client.get("/ledger/dia", params={"data": "lixo"})
    assert r.status_code == 400


def test_dia_falha_de_banco_503(monkeypatch):
    def _falha(data):
        raise RuntimeError("DATABASE_URL nao esta definida")
    monkeypatch.setattr(ledger_leitura, "dia", _falha)
    r = client.get("/ledger/dia", params={"data": "2026-09-14"})
    assert r.status_code == 503


def test_dia_sem_parametro_e_422_do_fastapi():
    r = client.get("/ledger/dia")
    assert r.status_code == 422        # Query(...) obrigatorio — validacao do FastAPI


def test_agregado_ok_com_filtros(monkeypatch):
    recebido = {}

    def _fake(periodo, familia=None, liga=None):
        recebido.update(periodo=periodo, familia=familia, liga=liga)
        return {"periodo": periodo, "familia": familia, "liga": liga}

    monkeypatch.setattr(ledger_leitura, "agregado", _fake)
    r = client.get("/ledger/agregado", params={
        "periodo": "7d", "familia": "Corners", "liga": "premier-league",
    })
    assert r.status_code == 200
    assert recebido == {"periodo": "7d", "familia": "Corners", "liga": "premier-league"}


def test_agregado_periodo_padrao_30d(monkeypatch):
    recebido = {}

    def _fake(periodo, familia=None, liga=None):
        recebido["periodo"] = periodo
        return {}

    monkeypatch.setattr(ledger_leitura, "agregado", _fake)
    client.get("/ledger/agregado")
    assert recebido["periodo"] == "30d"


def test_agregado_periodo_invalido_400(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise ValueError(f"periodo invalido: {periodo!r}")
    monkeypatch.setattr(ledger_leitura, "agregado", _falha)
    r = client.get("/ledger/agregado", params={"periodo": "1ano"})
    assert r.status_code == 400


def test_agregado_falha_de_banco_503(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise RuntimeError("conexao recusada")
    monkeypatch.setattr(ledger_leitura, "agregado", _falha)
    r = client.get("/ledger/agregado")
    assert r.status_code == 503


def test_rotas_registradas_no_app():
    paths = {r.path for r in app.routes}
    assert "/ledger/dia" in paths
    assert "/ledger/agregado" in paths
```

Run: `python -m pytest -q -o addopts="" tests/test_255_rotas_ledger.py`
Expected: FAIL — `/ledger/dia` e `/ledger/agregado` não existem (404) ou `ModuleNotFoundError: backend.routes.ledger`, e `test_rotas_registradas_no_app` falha.

- [ ] **Step 2: Criar `backend/routes/ledger.py`**

```python
# -*- coding: utf-8 -*-
"""#255 — `GET /ledger/dia` e `GET /ledger/agregado` (Fase 1 da reformulacao
do frontend, spec §6.3).

Fonte unica para o que o usuario ve: `prediction_ledger x ledger_outcomes`,
nunca `audit_results` (Regra #244, proibicao 13). Leitura pura: nenhuma rota
aqui grava nada. `backend/services/ledger_leitura.py` faz o trabalho; este
modulo so valida parametro HTTP e traduz erro em status code.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services import ledger_leitura

router = APIRouter(tags=["ledger"])


@router.get("/ledger/dia")
async def ledger_dia(data: str = Query(..., description="YYYY-MM-DD")):
    try:
        return ledger_leitura.dia(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")


@router.get("/ledger/agregado")
async def ledger_agregado(
    periodo: str = Query("30d", description="7d|30d|temporada"),
    familia: Optional[str] = Query(None),
    liga: Optional[str] = Query(None),
):
    try:
        return ledger_leitura.agregado(periodo, familia, liga)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:                                    # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"falha ao ler o ledger: {e}")
```

- [ ] **Step 3: Registrar em `backend/main.py`**

Em `backend/main.py`, logo depois do bloco `backtesting` (linhas 219-223):
```python
try:
    from backend.routes import backtesting as _r_backtesting
    app.include_router(_r_backtesting.router, prefix="/api")
except Exception:
    pass
```
acrescentar:
```python
try:
    from backend.routes import ledger as _r_ledger
    app.include_router(_r_ledger.router)
except Exception:
    pass
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest -q -o addopts="" tests/test_255_rotas_ledger.py`
Expected: PASS (9 testes).

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde. Se `fastapi.testclient` reclamar de `httpx` ausente localmente, confirmar antes: `python -c "import httpx; print(httpx.__version__)"` — já é dependência transitiva de `mistralai>=1.2.0` (`backend/requirements.txt:9`), sem necessidade de nova entrada.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/ledger.py backend/main.py tests/test_255_rotas_ledger.py
git commit -m "$(cat <<'EOF'
feat(backend): rotas GET /ledger/dia e /ledger/agregado (#255)

Traduz parametro HTTP e falha para status code; a leitura em si mora em
ledger_leitura.py (Task 2). Registrado em main.py no padrao try/except dos
demais routers.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Proxies Next.js `/api/ledger/dia` e `/api/ledger/agregado`

**Por quê.** A spec (§6.2) lista `/ledger/dia`/`/ledger/agregado` como "não existe/rota nova" no fluxo de dados de `Ontem` e `Desempenho` (fases 4 e 5 do frontend, fora deste plano). Sem os proxies, a Task 3 fica inacessível do browser: o navegador não conhece `PY_BACKEND_URL` nem a guarda #114/#203 (nunca `*.execute-api.*`) — só `frontend/next/src/lib/backend.ts` centraliza isso, e todo proxy existente passa por `fetchBackend`. Este é o mesmo padrão de `frontend/next/src/app/api/ml/status/route.ts` (lido: usa `fetchBackend`/`getBackendUrl`, devolve 503 estruturado quando `PY_BACKEND_URL` não está configurado ou o backend falha).

**Nota de processo:** este plano é backend-first e roda em paralelo à fase 0 do frontend (`docs/superpowers/plans/2026-09-15-reformulacao-frontend-fases-0-2-3.md`), que é quem instala o Vitest. Por isso a prova desta tarefa é `curl` contra `next dev` local (SDD Etapa 4), não teste automatizado — o teste automatizado destas rotas fica coberto quando a fase 4 do frontend (que consome estes proxies de verdade) escrever seus próprios testes de integração sobre eles.

- [ ] **Step 1: Criar `frontend/next/src/app/api/ledger/dia/route.ts`**

```ts
import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #255 — proxy de `GET /ledger/dia` (Lambda). Mesmo padrao de
 * `api/ml/status/route.ts`: o navegador nao conhece PY_BACKEND_URL, e
 * fetchBackend concentra a guarda #114/#203 (nunca api Gateway).
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function statusDoErro(kind?: string, message?: string): number {
  if (kind === "HTTP_ERROR") {
    const m = /^HTTP (\d+):/.exec(message ?? "");
    if (m) return Number(m[1]);
  }
  return 503;
}

export async function GET(request: Request) {
  if (!getBackendUrl()) {
    return Response.json(
      { ok: false, error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL não configurado" } },
      { status: 503 },
    );
  }

  const { searchParams } = new URL(request.url);
  const data = searchParams.get("data");
  if (!data) {
    return Response.json(
      { ok: false, error: { kind: "BAD_REQUEST", message: "parâmetro 'data' obrigatório (YYYY-MM-DD)" } },
      { status: 400 },
    );
  }

  const result = await fetchBackend(`/ledger/dia?data=${encodeURIComponent(data)}`, { timeoutMs: 25_000 });
  if (!result.ok) {
    const status = statusDoErro(result.error?.kind, result.error?.message);
    console.error(`[ledger/dia] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`);
    return Response.json(
      {
        ok: false,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível carregar o ledger do dia.",
        },
      },
      { status },
    );
  }
  return Response.json({ ok: true, ...(result.data as Record<string, unknown>) });
}
```

- [ ] **Step 2: Criar `frontend/next/src/app/api/ledger/agregado/route.ts`**

```ts
import { fetchBackend, getBackendUrl } from "@/lib/backend";

/**
 * #255 — proxy de `GET /ledger/agregado` (Lambda). Mesmo padrao de
 * `api/ledger/dia/route.ts` e `api/ml/status/route.ts`.
 */
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function statusDoErro(kind?: string, message?: string): number {
  if (kind === "HTTP_ERROR") {
    const m = /^HTTP (\d+):/.exec(message ?? "");
    if (m) return Number(m[1]);
  }
  return 503;
}

export async function GET(request: Request) {
  if (!getBackendUrl()) {
    return Response.json(
      { ok: false, error: { kind: "NOT_CONFIGURED", message: "PY_BACKEND_URL não configurado" } },
      { status: 503 },
    );
  }

  const { searchParams } = new URL(request.url);
  const periodo = searchParams.get("periodo") ?? "30d";
  const params = new URLSearchParams({ periodo });
  const familia = searchParams.get("familia");
  const liga = searchParams.get("liga");
  if (familia) params.set("familia", familia);
  if (liga) params.set("liga", liga);

  const result = await fetchBackend(`/ledger/agregado?${params.toString()}`, { timeoutMs: 25_000 });
  if (!result.ok) {
    const status = statusDoErro(result.error?.kind, result.error?.message);
    console.error(`[ledger/agregado] ${result.error?.kind} | ${result.error?.message} | ${result.durationMs}ms`);
    return Response.json(
      {
        ok: false,
        error: {
          kind: result.error?.kind ?? "BACKEND_ERROR",
          message: "Não foi possível carregar o desempenho agregado.",
        },
      },
      { status },
    );
  }
  return Response.json({ ok: true, ...(result.data as Record<string, unknown>) });
}
```

- [ ] **Step 3: Prova empírica local**

Run (dois terminais):
```bash
# terminal 1 — backend local
uvicorn backend.main:app --reload --port 5001
# terminal 2 — frontend local, apontando para o backend local
cd frontend/next && PY_BACKEND_URL=http://localhost:5001 npm run dev
```
Run:
```bash
curl -s "http://localhost:3000/api/ledger/dia?data=2026-09-14" | head -c 300
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3000/api/ledger/dia"           # sem 'data'
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3000/api/ledger/agregado?periodo=7d"
```
Expected: primeiro curl devolve JSON com `"ok":true` (ou `503` estruturado se a RDS local não estiver configurada — aceitável, o contrato de erro é o que se prova aqui); segundo curl `400`; terceiro `200` ou `503` estruturado.

Run: `npx tsc --noEmit` (dentro de `frontend/next`) — Expected: sem erros nos dois arquivos novos.

- [ ] **Step 4: Commit**

```bash
git add frontend/next/src/app/api/ledger
git commit -m "$(cat <<'EOF'
feat(front): proxies /api/ledger/dia e /api/ledger/agregado (#255)

Mesmo padrao de api/ml/status/route.ts: fetchBackend centraliza a guarda
#114/#203, 400 quando falta 'data', 503 estruturado em falha de backend.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Teste de contrato `fair_odd`/`book_odd`

**Por quê.** A spec (§6.2, §6.3) lista o contrato `fair_odd`/`book_odd` separados como algo que falta implementar. Lendo `backend/models/market_output.py:64` (`fair_odd: Optional[float]`), `:147` (`compute_display` calcula `fair_odd = round(1/prob, 2)`) e `:176-177` (`to_legacy_mercado` inclui `"fair_odd": self.fair_odd, "book_odd": self.book_odd` incondicionalmente), o contrato **já existe** — não há gap de produção. Esta tarefa é só a prova que falta (contradição #2 do topo deste plano), com payload real via `evaluate_match_markets`, no mesmo formato de `tests/test_251_calibrated_prob_e_o_modelo.py`.

**Critério de aceite.** Todo dict de `to_legacy_mercado()` tem as chaves `fair_odd` e `book_odd` (podem ser `None`). Existe pelo menos um mercado com `book_odd` real no payload de teste, e nesse mercado `fair_odd != book_odd` (prova que "distintos" não é vácuo).

- [ ] **Step 1: Escrever o teste (já deve passar — é prova, não implementação)**

`tests/test_255_fair_odd_book_odd.py`:
```python
# -*- coding: utf-8 -*-
"""#255 — contrato `fair_odd`/`book_odd` (spec §6.3): "sempre presentes e
distintos no payload de /fixtures".

Achado da Etapa 1 (Validacao de Contrato): o contrato JA EXISTE em
`backend/models/market_output.py` — `fair_odd` (:64, calculado em
`compute_display`, :147) e `book_odd` (:65) sao campos do proprio
`MarketOutput`, e `to_legacy_mercado()` (:176-177) sempre inclui os dois. A
spec listava isto como "falta implementar"; nao falta — falta a prova, que e
este arquivo. Payload no mesmo formato de
`tests/test_251_calibrated_prob_e_o_modelo.py`.
"""
import copy

from backend.services.ev_classification import evaluate_match_markets

_ODDS = {
    "home": 1.95, "draw": 3.60, "away": 3.70,
    "over25": 1.80, "under25": 1.90, "over15": 1.22, "under15": 3.54,
    "bttsYes": 1.75, "bttsNo": 2.00,
    "cornersOver95": 1.77, "cornersUnder95": 1.95, "cornersOver115": 2.63,
}
_MATCH = {
    "id": "999250", "homeTeam": "Casa FC", "awayTeam": "Fora FC",
    "stats": {"lambdaHome": 1.55, "lambdaAway": 1.15, "lambdaTotal": 2.70,
              "homeWinProb": 47.0, "drawProb": 26.0, "awayWinProb": 27.0,
              "homeCornersPerMatch": 5.6, "awayCornersPerMatch": 4.9,
              "leagueAvgCorners": 10.2,
              "homeCardsPerMatch": 2.1, "awayCardsPerMatch": 2.4,
              "leagueAvgCards": 4.6,
              "matchesPlayed_home": 18, "matchesPlayed_away": 18},
    "league_stats": {"matches_completed": 200, "average_goals_per_match": 2.65,
                     "average_corners_per_match": 10.2,
                     "average_cards_per_match": 4.6},
    "odds": {**_ODDS, "over05": 1.03, "under05": 9.50, "over35": 2.99,
             "under35": 1.30, "over45": 5.85, "under45": 1.10,
             "dc_1x": 1.25, "dc_12": 1.28, "dc_x2": 1.83,
             "cornersOver75": 1.24, "cornersUnder75": 3.55,
             "cornersUnder115": 1.41},
}


def _mercados():
    bundle = evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    return [m.to_legacy_mercado() for m in bundle.markets]


def test_fair_odd_e_book_odd_sempre_presentes():
    mercados = _mercados()
    assert mercados, "bundle sem mercados — payload de teste desatualizado"
    for m in mercados:
        assert "fair_odd" in m
        assert "book_odd" in m


def test_fair_odd_e_book_odd_distintos_quando_ha_preco_de_casa():
    mercados = _mercados()
    com_book = [m for m in mercados if m["book_odd"] is not None]
    assert com_book, "nenhum mercado com book_odd — payload de teste sem odds reais"
    distintos = [m for m in com_book if m["fair_odd"] != m["book_odd"]]
    assert distintos, "fair_odd == book_odd em todo mercado com preco de casa"


def test_fair_odd_e_o_inverso_da_probabilidade_calibrada():
    mercados = _mercados()
    for m in mercados:
        if m["fair_odd"] is not None and m["calibrated_probability"]:
            assert m["fair_odd"] == round(1.0 / m["calibrated_probability"], 2)
```

Run: `python -m pytest -q -o addopts="" tests/test_255_fair_odd_book_odd.py`
Expected: PASS (3 testes) — sem alterar nenhum arquivo de produção. Se `test_fair_odd_e_book_odd_distintos_quando_ha_preco_de_casa` falhar, o contrato tem um gap real e a contradição #2 deste plano está errada — investigar `MarketOutput.compute_ev`/`compute_display` antes de seguir para a Task 6.

- [ ] **Step 2: Commit**

```bash
git add tests/test_255_fair_odd_book_odd.py
git commit -m "$(cat <<'EOF'
test(backend): prova o contrato fair_odd/book_odd ja existente (#255)

market_output.py ja calcula e serializa os dois campos separados; a spec da
reformulacao listava como pendente. Este teste e a prova que falta, nao uma
implementacao nova.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Prompt Mistral v3.1 — vocabulário de operador

**Objetivo e contexto (Etapa 1).** O operador apontou "lambda" no texto da Mistral como sem utilidade (spec §0). A spec (§4.4, tabela "Hoje → Novo") define a troca: `"lambda", "deflação", "banda"` (texto Mistral) → vocabulário de operador (`"chance"`, `"mínimo"`, `"paga"`, `"gols por jogo"`), como item de backend. Hoje o prompt v3.0 ensina esse vocabulário ativamente: `backend/services/mistral_analysis.py:321` dá "lambda_home de 1.45" como exemplo de "Justificativa Numérica"; `:322` instrui "cite lambdas, ..."; `:547` (schema JSON) exemplifica `key_points[0]` como "golos (com lambda/prob/odd)"; `:315` instrui "Use Poisson com lambda de escanteios". `backend/ai/mistral_contract.py::validate_output` hoje tem três camadas (mercado fora da lista aprovada, #181/#238-a número divergente do publicado, #146 EV computado no texto) — nenhuma rejeita vocabulário de cálculo interno.

**Validação de contrato (Etapa 2).** `validate_output` é chamado com o texto completo que o operador lê (`resumo_analitico + recomendacao_principal + key_points`, `mistral_analysis.py:930-937`) — confirmado lendo `_log_contract_violations`. A nova camada entra no mesmo lugar, sobre o mesmo texto; não precisa de payload novo.

**Contratos de saída (Etapa 2-bis).** `aligned_recommendation()` (`mistral_contract.py:194-212`) é chamada por `_enforce_recommendation_contract` (`mistral_analysis.py:838-891`) quando a Camada 7 substitui `recomendacao_principal` — o texto dela **também** chega ao operador, e hoje contém "após deflação" duas vezes (linha 204 e linha 210 do arquivo atual). Essa string não é revalidada por `validate_output` depois de substituída (nenhum loop de re-checagem) — se não for corrigida aqui, o vocabulário interno voltaria pela porta dos fundos, sem a nova camada nunca detectar (ela mesma seria a origem da violação). `tests/unit/test_recommendation_enforcement.py:74,104` só checa `"Sem recomenda" in texto` (prefixo) — a mudança de sufixo não quebra esse teste.

**Critérios de aceite.**
- `validate_output(texto, ...)` rejeita `"lambda"`, `"lambdas"`, `"deflação"`, `"deflacao"`, `"deflacionada"`/`"deflacionado"`, `"banda"`, `"bandas"` (case-insensitive) em qualquer lugar do texto.
- Vocabulário de operador (`"chance"`, `"mínimo"`, `"paga"`, `"gols por jogo"`) não é tocado pela nova camada.
- `SEM_RECOMENDACAO` é uma única constante, sem "deflação", usada tanto no prompt (`mistral_analysis.py`) quanto no fallback determinístico (`mistral_contract.py::aligned_recommendation`).
- As três camadas anteriores de `validate_output` (mercado fora da lista, número divergente #238-a, EV computado #146) continuam rejeitando os mesmos casos de antes.
- `MistralAnalysisService.VERSION == "3.1"`.

**Cenários de borda.** Um texto legítimo que cite "banda de frequência" no sentido de "faixa horária" (nunca acontece no domínio, mas hipoteticamente) seria falso positivo — aceitável: o vocabulário é de calibração estatística, não existe uso legítimo de "banda" numa narrativa de prognóstico esportivo em português.

- [ ] **Step 1: Teste primeiro (falha: `_VOCABULARIO_INTERNO`/`SEM_RECOMENDACAO` não existem)**

`tests/test_255_vocabulario_mistral.py`:
```python
# -*- coding: utf-8 -*-
"""#255 — v3.1: vocabulario de operador na narrativa Mistral.

`validate_output` ja rejeitava mercado fora da lista (#181), numero
divergente do publicado (#238-a) e EV computado no texto (#146). Esta
camada acrescenta um quarto motivo: termos de CALCULO INTERNO ("lambda",
"deflacao"/"deflação"/"deflacionado", "banda") no texto que o operador le
(spec docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md
§4.4). Este arquivo nao duplica os testes das tres camadas anteriores (ja
cobertos em test_238a_contrato_numerico.py e tests/unit/); so prova que elas
continuam rejeitando o que rejeitavam E que a nova pega o caso novo.
"""
import pytest

from backend.ai.mistral_contract import ApprovedPick, SEM_RECOMENDACAO, validate_output

CARD = [ApprovedPick(market="Over 2.5 gols", classification="SAFE",
                     prob_deflated_pct=58, odd=1.75, ev_pct=2.0)]


@pytest.mark.parametrize("termo", [
    "o lambda casa de 1.45 sustenta o cenario",
    "apos a deflação a chance cai para 58%",
    "apos a deflacao a chance cai para 58%",
    "a probabilidade deflacionada e 58%",
    "o modelo esta deflacionado nesta banda",
    "dentro da banda de 55-60% o mercado paga bem",
])
def test_vocabulario_interno_e_rejeitado(termo):
    v = validate_output(termo, CARD)
    assert not v["ok"], termo
    assert any("interno" in x.lower() for x in v["violations"]), v["violations"]


def test_vocabulario_de_operador_nao_e_tocado():
    texto = ("Chance de 58%, mínimo 1,67, mercado paga 1,75. Média de 1,45 "
             "gols por jogo em casa.")
    v = validate_output(texto, CARD)
    assert v["ok"], v["violations"]


def test_sem_recomendacao_e_constante_unica_sem_vocabulario_interno():
    v = validate_output(SEM_RECOMENDACAO, [])
    # so a violacao de "mercado ausente" pode aparecer (lista aprovada vazia),
    # nunca uma de vocabulario interno.
    assert not any("interno" in x.lower() for x in v["violations"]), v["violations"]
    assert "deflaç" not in SEM_RECOMENDACAO.lower()
    assert "deflac" not in SEM_RECOMENDACAO.lower()
    assert "lambda" not in SEM_RECOMENDACAO.lower()
    assert "banda" not in SEM_RECOMENDACAO.lower()


def test_camada_181_mercado_fora_da_lista_continua():
    v = validate_output("Recomendo Under 3.5 gols", CARD)
    assert not v["ok"]
    assert any("Mercado fora da lista" in x for x in v["violations"])


def test_camada_146_ev_computado_continua():
    v = validate_output("Over 2.5 gols com EV +12%", CARD)
    assert not v["ok"]
    assert any("computou EV" in x for x in v["violations"])


def test_prompt_v31_versao():
    from backend.services.mistral_analysis import MistralAnalysisService
    assert MistralAnalysisService.VERSION == "3.1"


def test_prompt_nao_reintroduz_deflacao_no_texto_de_sem_recomendacao():
    import pathlib
    src = pathlib.Path("backend/services/mistral_analysis.py").read_text(encoding="utf-8")
    assert "nenhum mercado com EV positivo após deflação" not in src
    assert "SEM_RECOMENDACAO" in src


def test_aligned_recommendation_sem_vocabulario_interno():
    from backend.ai.mistral_contract import aligned_recommendation
    texto_vazio = aligned_recommendation([])
    texto_com_pick = aligned_recommendation(CARD)
    for texto in (texto_vazio, texto_com_pick):
        v = validate_output(texto, CARD)
        assert not any("interno" in x.lower() for x in v["violations"]), (texto, v["violations"])
```

Run: `python -m pytest -q -o addopts="" tests/test_255_vocabulario_mistral.py`
Expected: FAIL — `ImportError: cannot import name 'SEM_RECOMENDACAO'` e/ou os `test_vocabulario_interno_e_rejeitado[...]` passando como falso-negativo (`v["ok"]` ainda `True` porque a camada não existe).

- [ ] **Step 2: Ajustar a fixture de `test_238a_contrato_numerico.py` (quebraria com a nova camada)**

Em `tests/test_238a_contrato_numerico.py`, a função `test_percentual_publicado_nao_gera_violacao` (linhas 59-63) usa "apos deflacao" como texto **sem** violação esperada — com a Task 6 isso passaria a ter violação (vocabulário interno), quebrando o teste. Trocar:

```python
old_string:
    texto = ("Escanteios Over 6.5 aparece com 59% apos deflacao e Cartoes Over 2.5 "
             "com 60%. Nenhum outro mercado foi aprovado.")
```
```python
new_string:
    texto = ("Escanteios Over 6.5 aparece com 59% de chance e Cartoes Over 2.5 "
             "com 60%. Nenhum outro mercado foi aprovado.")
```

- [ ] **Step 3: `backend/ai/mistral_contract.py` — `_VOCABULARIO_INTERNO`, `SEM_RECOMENDACAO`, quarta camada**

Acrescentar, logo abaixo de `_EV_COMPUTATION_PATTERN` (depois da linha `_EV_COMPUTATION_PATTERN = re.compile(...)`):
```python
old_string:
# Pattern for "Mistral computed EV" — narrative must NEVER assert EV.
# System computes EV; narrative narrates context.
_EV_COMPUTATION_PATTERN = re.compile(r"EV\s*[+\-]?\s*\d+[\.,]?\d*\s*%", re.IGNORECASE)
```
```python
new_string:
# Pattern for "Mistral computed EV" — narrative must NEVER assert EV.
# System computes EV; narrative narrates context.
_EV_COMPUTATION_PATTERN = re.compile(r"EV\s*[+\-]?\s*\d+[\.,]?\d*\s*%", re.IGNORECASE)

# #255 — vocabulario de CALCULO INTERNO. O operador apontou "lambda" no
# texto da Mistral como sem utilidade (spec docs/superpowers/specs/
# 2026-09-15-reformulacao-frontend-design.md §4.4): "lambda"/"deflação"/
# "banda" saem, "chance"/"mínimo"/"paga"/"gols por jogo" entram. O pipeline
# continua usando esses termos internamente (prompt, logs, variaveis) — a
# regra e so sobre o texto que o operador le.
_VOCABULARIO_INTERNO = [
    re.compile(r"\blambdas?\b", re.IGNORECASE),
    re.compile(r"\bdeflac(?:a|ã)[a-zç]*", re.IGNORECASE),   # deflação/deflacao/deflacionad*
    re.compile(r"\bbandas?\b", re.IGNORECASE),
]

# #255 — unica ocorrencia do texto de "sem recomendacao". Antes duplicado
# aqui (`aligned_recommendation`) e no prompt v3.0
# (`mistral_analysis.py`, regra de alinhamento #096) — as duas mudavam
# juntas so na teoria; a v3.0 -> v3.1 e o caso real em que uma mudaria e a
# outra nao. O prompt agora IMPORTA esta constante em vez de repetir o texto.
SEM_RECOMENDACAO = (
    "Sem recomendação — nenhum mercado do pipeline vale a pena hoje."
)
```

Dentro de `validate_output`, depois do bloco `_EV_COMPUTATION_PATTERN.search(text)` e antes do `return`:
```python
old_string:
    if _EV_COMPUTATION_PATTERN.search(text):
        violations.append(
            "Mistral computou EV no texto narrativo — proibido (regra #146); "
            "system computa EV, narrativa narra contexto."
        )

    return {"ok": len(violations) == 0, "violations": violations}
```
```python
new_string:
    if _EV_COMPUTATION_PATTERN.search(text):
        violations.append(
            "Mistral computou EV no texto narrativo — proibido (regra #146); "
            "system computa EV, narrativa narra contexto."
        )

    # #255 — vocabulario de operador (spec §4.4). Um match por padrao basta;
    # nao precisa nomear cada ocorrencia como o #238-a faz com numero.
    for padrao in _VOCABULARIO_INTERNO:
        m = padrao.search(text)
        if m:
            violations.append(
                f"Vocabulario interno de calculo na narrativa: '{m.group()}' — "
                f"use vocabulario de operador (chance, mínimo, paga, gols por jogo), regra #255."
            )

    return {"ok": len(violations) == 0, "violations": violations}
```

Em `aligned_recommendation`, trocar as duas ocorrências de texto com "deflação":
```python
old_string:
def aligned_recommendation(approved: List[ApprovedPick]) -> str:
    """Recomendação determinística construída a partir dos picks aprovados.

    Usada como substituição quando a recomendacao_principal do Mistral
    viola o contrato (cita mercado fora da lista aprovada, i.e. rejeitado
    pela tabela de EV deflacionado). Consome exatamente os mesmos valores
    exibidos na tabela de mercados — nunca contradiz o display.
    """
    if not approved:
        return (
            "Sem recomendação — nenhum mercado com EV positivo após deflação "
            "para este jogo. Consulte a tabela de mercados analisados."
        )
    top = max(approved, key=lambda p: p.ev_pct)
    return (
        f"Recomendação alinhada ao pipeline: {top.market} "
        f"({top.prob_deflated_pct:.0f}%, odd {top.odd:.2f}, EV {top.ev_pct:+.1f}%) — "
        f"mercado com maior EV após deflação entre os aprovados pelo sistema."
    )
```
```python
new_string:
def aligned_recommendation(approved: List[ApprovedPick]) -> str:
    """Recomendação determinística construída a partir dos picks aprovados.

    Usada como substituição quando a recomendacao_principal do Mistral
    viola o contrato (cita mercado fora da lista aprovada, i.e. rejeitado
    pela tabela de EV pos-calibracao). Consome exatamente os mesmos valores
    exibidos na tabela de mercados — nunca contradiz o display.

    #255: vocabulario de operador — nao usa "deflação"/"lambda"/"banda",
    porque este texto e o que o operador le quando a Camada 7
    (`mistral_analysis.py::_enforce_recommendation_contract`) substitui a
    recomendacao da Mistral e NAO revalida o resultado com validate_output.
    """
    if not approved:
        return (
            f"{SEM_RECOMENDACAO} Consulte a tabela de mercados analisados."
        )
    top = max(approved, key=lambda p: p.ev_pct)
    return (
        f"Recomendação alinhada ao pipeline: {top.market} "
        f"({top.prob_deflated_pct:.0f}%, odd {top.odd:.2f}, EV {top.ev_pct:+.1f}%) — "
        f"mercado com maior EV entre os aprovados pelo sistema."
    )
```

- [ ] **Step 4: `backend/services/mistral_analysis.py` — prompt v3.1**

Bump de versão:
```python
old_string:
class MistralAnalysisService:
    """Serviço para análise de jogos com MISTRAL AI — v3.0"""

    VERSION = "3.0"

    SYSTEM_PROMPT = (
        "Você é o motor de análise estatística do SportsBankzu-Pro v3.0. "
```
```python
new_string:
class MistralAnalysisService:
    """Serviço para análise de jogos com MISTRAL AI — v3.1 (#255: vocabulário
    de operador — "lambda"/"deflação"/"banda" saem do texto lido pelo
    usuário; o cálculo interno não muda)."""

    VERSION = "3.1"

    SYSTEM_PROMPT = (
        "Você é o motor de análise estatística do SportsBankzu-Pro v3.1. "
```

Regra de vocabulário, acrescentada às "Regras de Ouro (Invioláveis)", logo depois da regra de EV do #181:
```python
old_string:
- **REGRA #181 — Cálculo de EV:** Você NUNCA computa EV. EV vem pronto em cada pick do pipeline. Não escreva "EV +X%" para mercados fora da lista, nem recompute para os da lista. Se quiser justificar valor, use "EV positivo" / "EV negativo" qualitativo, sem número.

# Dados do Confronto
```
```python
new_string:
- **REGRA #181 — Cálculo de EV:** Você NUNCA computa EV. EV vem pronto em cada pick do pipeline. Não escreva "EV +X%" para mercados fora da lista, nem recompute para os da lista. Se quiser justificar valor, use "EV positivo" / "EV negativo" qualitativo, sem número.
- **REGRA #255 — Vocabulário de operador:** Você é lida por um operador, não por um analista de dados. PROIBIDO escrever "lambda", "deflação"/"deflacionado" ou "banda" em resumo_analitico, key_points ou recomendacao_principal — mesmo que esses termos apareçam nos dados abaixo (eles são insumo interno do modelo). Troque por: "lambda" → "gols esperados por jogo" / "escanteios esperados"; "deflação"/"probabilidade deflacionada" → "chance" (o número já é o publicado, não precisa qualificar); "banda" → não mencione, é detalhe interno de calibração. Use "chance" para probabilidade, "mínimo" para a odd justa (fair_odd) e "paga" para a odd da casa (book_odd) quando character existir.

# Dados do Confronto
```

Exemplo de "Justificativa Numérica" sem "lambda_home" literal:
```python
old_string:
- **Justificativa Numérica:** Toda conclusão deve ter dado numérico (ex: "lambda_home de 1.45 indica média de 1.45 gols esperados").
- **Seja Específico:** Nos key_points, cite lambdas, probabilidades, odds, %. Nunca genérico.
```
```python
new_string:
- **Justificativa Numérica:** Toda conclusão deve ter dado numérico (ex: "média de 1,45 gols esperados em casa").
- **Seja Específico:** Nos key_points, cite gols esperados por jogo, chance, mínimo, paga, %. Nunca genérico. Vocabulário de operador (regra #255) — sem "lambda".
```

Instrução interna de cálculo (não ensinar o termo mesmo em instrução metodológica, defensivo):
```python
old_string:
   - Escanteios: Use Poisson com lambda de escanteios quando disponível
```
```python
new_string:
   - Escanteios: Use Poisson com a média esperada de escanteios quando disponível
```

Exemplo no schema de saída (`key_points`):
```python
old_string:
  "key_points": [
    "Ponto 1 — golos (com lambda/prob/odd)",
    "Ponto 2 — 1X2 ou DC (com prob/odd)",
```
```python
new_string:
  "key_points": [
    "Ponto 1 — golos (com gols esperados por jogo/chance/mínimo)",
    "Ponto 2 — 1X2 ou DC (com chance/odd)",
```

Docstring do builder:
```python
old_string:
    # -----------------------------------------------------------------
    # PROMPT BUILDER — v3.0
    # -----------------------------------------------------------------

    def _build_prompt(
```
```python
new_string:
    # -----------------------------------------------------------------
    # PROMPT BUILDER — v3.1
    # -----------------------------------------------------------------

    def _build_prompt(
```
```python
old_string:
        """Constrói o prompt v3.0 para a MISTRAL AI"""
```
```python
new_string:
        """Constrói o prompt v3.1 para a MISTRAL AI (#255: vocabulário de operador)"""
```

`SEM_RECOMENDACAO` importado e usado no branch sem picks:
```python
old_string:
        else:
            prompt += """
PICKS SELECIONADOS PELO PIPELINE (Dixon-Coles): NENHUM.

REGRA DE ALINHAMENTO (#096, endurecida):
- O pipeline NAO aprovou nenhum mercado (EV positivo apos deflacao) para este jogo.
- Sua recomendacao_principal DEVE ser exatamente: "Sem recomendação — nenhum mercado com EV positivo após deflação para este jogo."
- NAO recomende nenhum mercado, mesmo com probabilidade alta.
"""
```
```python
new_string:
        else:
            from backend.ai.mistral_contract import SEM_RECOMENDACAO
            prompt += f"""
PICKS SELECIONADOS PELO PIPELINE (Dixon-Coles): NENHUM.

REGRA DE ALINHAMENTO (#096, endurecida):
- O pipeline NAO aprovou nenhum mercado com valor para este jogo.
- Sua recomendacao_principal DEVE ser exatamente: "{SEM_RECOMENDACAO}"
- NAO recomende nenhum mercado, mesmo com probabilidade alta.
"""
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest -q -o addopts="" tests/test_255_vocabulario_mistral.py tests/test_238a_contrato_numerico.py tests/unit/test_recommendation_enforcement.py`
Expected: PASS em tudo. Se `test_238a` falhar em algum outro caso, ler a mensagem — só a fixture da linha ~61 deveria ter mudado de comportamento.

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde. Prestar atenção especial a qualquer teste que use a string `"apos deflacao"`/`"após deflação"` como texto esperado SEM violação em `mistral_contract`/`mistral_analysis` — `grep -rn "apos deflac\|após deflaç" tests/` antes de declarar sucesso, porque a nova camada rejeita esse vocabulário em qualquer lugar do texto validado.

- [ ] **Step 6: Commit**

```bash
git add backend/ai/mistral_contract.py backend/services/mistral_analysis.py tests/test_255_vocabulario_mistral.py tests/test_238a_contrato_numerico.py
git commit -m "$(cat <<'EOF'
feat(backend): prompt Mistral v3.1 — vocabulario de operador (#255)

validate_output ganha a quarta camada (lambda/deflacao/banda na narrativa);
SEM_RECOMENDACAO vira constante unica entre mistral_contract e o prompt;
aligned_recommendation() nao reintroduz "deflacao" no texto substituido.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Fechamento — REGISTRO, INDICE, REGRAS_ATIVAS, CLAUDE.md, espelho, deploy, prova

- [ ] **Step 1: Rodar tudo antes de escrever qualquer doc**

Run: `python -m pytest -q -o addopts=""`
Expected: suíte inteira verde. Anotar o total de testes (para citar no REGISTRO).

Run (dentro de `frontend/next`): `npx tsc --noEmit`
Expected: sem erros nos dois arquivos novos da Task 4.

- [ ] **Step 2: Entrada em `docs/REGISTRO_CORRECOES.md`**

Acrescentar ao final do arquivo:
```markdown
## 255 — Fase 1 da reformulação: rotas de ledger e vocabulário Mistral
**Data:** 2026-09-15 | **Arquivos:** `backend/services/amostra_ledger.py`, `scripts/amostra_ledger.py`, `backend/services/ledger_leitura.py`, `backend/routes/ledger.py`, `backend/main.py`, `frontend/next/src/app/api/ledger/{dia,agregado}/route.ts`, `backend/ai/mistral_contract.py`, `backend/services/mistral_analysis.py`, `tests/test_255_*.py`, `tests/test_238a_contrato_numerico.py` | **Severidade:** Média | **Status:** Corrigido/Implementado

### Problema identificado
A reformulação do frontend (spec `docs/superpowers/specs/2026-09-15-reformulacao-frontend-design.md`) depende de três contratos de backend que não existiam: nenhuma rota expunha `prediction_ledger × ledger_outcomes` (spec §0), o prompt Mistral ensinava vocabulário interno de cálculo ("lambda", "deflação", "banda") ao operador (spec §4.4), e os filtros de amostra do ledger (#252/#252-a) moravam em `scripts/`, inacessíveis a um caminho de produção.

### Causa raiz
`scripts/deploy_lambda.py:38` e `.github/workflows/deploy-lambda.yml:97` só empacotam `backend/` — qualquer módulo em `scripts/` que uma rota nova precisasse em runtime quebraria com `ModuleNotFoundError` na primeira chamada. O prompt Mistral v3.0 nunca teve uma regra de vocabulário porque a narrativa foi desenhada para auditoria interna primeiro (#082/#181/#238-a validam CONTEÚDO — mercado certo, número certo, sem EV computado —, nunca VOCABULÁRIO).

### Correções aplicadas (com camadas)
1. **Camada de origem (Task 1):** `filtrar_amostra`/`so_pre_jogo`/`fora_da_janela_contaminada`/`descrever` movidos de `scripts/amostra_ledger.py` para `backend/services/amostra_ledger.py`; `scripts/amostra_ledger.py` vira reexportação. Mesmos objetos (`is`), mesmos testes #252b/#252c verdes sem alteração.
2. **Camada de leitura (Task 2):** `backend/services/ledger_leitura.py::dia`/`agregado` — uma consulta por janela de `published_at`, LEFT JOIN em `ledger_outcomes`, `escolher_ultima_geracao` (#248) para uma linha por seleção, `classificar_familia` (#248) para a família, `MIN_N=20` (#079) para o piso de Brier/buckets. `fair_odd` derivado (`round(1/published_prob, 2)`) porque a coluna não existe no ledger. `retorno` sempre `null` com `motivo: "stake_nao_gravado_no_ledger"` — a coluna `stake` nunca é gravada (`linhas_do_bundle` não passa `stake=`).
3. **Camada HTTP (Task 3):** `backend/routes/ledger.py` — `GET /ledger/dia`, `GET /ledger/agregado`; `ValueError` → 400, qualquer outra exceção → 503; registrado em `backend/main.py` no padrão try/except dos demais routers.
4. **Camada de proxy (Task 4):** `frontend/next/src/app/api/ledger/{dia,agregado}/route.ts`, mesmo padrão de `api/ml/status/route.ts` (guarda #114/#203 via `fetchBackend`).
5. **Prova de contrato existente (Task 5):** `tests/test_255_fair_odd_book_odd.py` confirma que `fair_odd`/`book_odd` já eram campos separados em `MarketOutput`/`to_legacy_mercado` — a spec listava como pendente por engano (ver "Contradições spec × código" no plano).
6. **Camada de vocabulário (Task 6):** `backend/ai/mistral_contract.py::validate_output` ganha a quarta camada de rejeição (`_VOCABULARIO_INTERNO`: lambda/deflação/banda); `SEM_RECOMENDACAO` unificado entre `aligned_recommendation` e o prompt; prompt v3.1 troca os exemplos que ensinavam o vocabulário interno.

### Etapa 2-bis — contrato de saída: consumidores do ledger

| Campo escrito | Tabela | Consumidor externo | Contrato implícito assumido |
|---|---|---|---|
| nenhum — leitura pura | — | `GET /ledger/dia`, `GET /ledger/agregado` (novas) | as duas rotas são as ÚNICAS leitoras destes campos; nenhum sistema existente lê `ledger_leitura.py` |
| `recomendacao_principal` (texto Mistral, campo já existente) | não é tabela — resposta de `/api/ai/match/{id}/analysis` | `MatchDetailCard.tsx` (dashboard atual) exibe o texto ao operador; `tests/unit/test_recommendation_enforcement.py` checa só o prefixo `"Sem recomenda"` | o consumidor assume que o texto é seguro para exibir verbatim — a troca de vocabulário (Task 6) preserva esse contrato: o texto continua sendo prosa em português, só sem os três termos banidos |

Nenhum campo do `prediction_ledger`/`ledger_outcomes` teve seu contrato de ESCRITA alterado (Task 1 só moveu onde a leitura mora; Tasks 2-5 são leitura nova). A Task 6 altera o TEXTO de um campo já existente (`recomendacao_principal`) — o consumidor (dashboard atual) não distingue por conteúdo, só renderiza a string, então a troca de vocabulário não quebra o contrato de exibição.

### Etapa 5 — efeito acumulado
Não se aplica: este trabalho é leitura pura (rotas HTTP sem estado, chamadas sob demanda) e troca de texto estático (prompt). Não há laço, cron nem retreino envolvido — proibição 16 do CLAUDE.md não incide aqui.

### Prova empírica
```
[PREENCHER com a saída real dos curls — ver Step 6 abaixo. Etapa 4 do SDD
proíbe inventar números; este é o único placeholder permitido no registro.]
```

### Lição aprendida
Todo módulo que uma rota HTTP nova precisa em runtime tem de morar em `backend/` — `scripts/` é invisível para a Lambda. A spec de design de uma reformulação de frontend pode listar como "pendente" um contrato que já existe no backend (fair_odd/book_odd): a Etapa 1 do SDD (rastreabilidade de dados, "confirmar se o dado existe em todo o trajeto sem inferir") pegou isso antes de gerar trabalho redundante.
```

- [ ] **Step 3: Linha em `docs/INDICE_REGRAS.md`**

Localizar a linha `| 253-b | ...` e acrescentar logo depois (mesmo formato de coluna: `| número | status | tipo | resumo em negrito na primeira frase |`):
```markdown
| 255 | Implementado | Feature (Backend / Ledger / Mistral) | **`GET /ledger/dia` e `GET /ledger/agregado` (fonte única prediction_ledger × ledger_outcomes) e prompt Mistral v3.1 em vocabulário de operador.** Filtros de amostra (#252/#252-a) movidos de `scripts/` para `backend/services/amostra_ledger.py` — a Lambda só empacota `backend/`. `retorno` vem `null` (stake nunca gravado no ledger); `fair_odd`/`book_odd` já existiam em `market_output.py`, este item só prova o contrato. `validate_output` ganha a quarta camada: rejeita "lambda"/"deflação"/"banda" na narrativa |
```

- [ ] **Step 4: `docs/REGRAS_ATIVAS.md` — estado de aplicação de #252 e #252-a**

No bloco de `#252` (procurar `**Estado de aplicacao:**` logo antes da entrada de `#252-a`), acrescentar ao final do parágrafo existente:
```markdown
old_string:
**Estado de aplicacao:** `scripts/comparar_com_mercado.py` (gate #230) aplica desde #252;
`scripts/medir_inclinacao.py` e `scripts/grade_deflacao_por_familia.py` desde #252-b. Os tres
importam os filtros de UM modulo, `scripts/amostra_ledger.py` — reimplementar o filtro num
consumidor e proibido (proibicao 5).
`backend/modeling/calibragem/repositorio.py::escolher_ultima_geracao` (#248) falha FECHADA desde
#252-c (antes mantinha a linha quando `kickoff_utc` era None).
```
```markdown
new_string:
**Estado de aplicacao:** `scripts/comparar_com_mercado.py` (gate #230) aplica desde #252;
`scripts/medir_inclinacao.py` e `scripts/grade_deflacao_por_familia.py` desde #252-b. Os tres
importam os filtros de UM modulo — desde #255, `backend/services/amostra_ledger.py`
(`scripts/amostra_ledger.py` e reexportacao) — reimplementar o filtro num consumidor e proibido
(proibicao 5).
`backend/modeling/calibragem/repositorio.py::escolher_ultima_geracao` (#248) falha FECHADA desde
#252-c (antes mantinha a linha quando `kickoff_utc` era None).
Desde #255, `backend/services/ledger_leitura.py` (rotas `GET /ledger/dia` e `GET /ledger/agregado`)
e o quarto consumidor, tambem via `backend/services/amostra_ledger.py`.
```

No bloco de `#252-a`, localizar `**Estado de aplicacao:**` correspondente e acrescentar:
```markdown
old_string:
**Estado de aplicacao:** `scripts/comparar_com_mercado.py` desde #252-a;
`scripts/medir_inclinacao.py` e `scripts/grade_deflacao_por_familia.py` desde #252-b, todos via
`scripts/amostra_ledger.py`.
```
```markdown
new_string:
**Estado de aplicacao:** `scripts/comparar_com_mercado.py` desde #252-a;
`scripts/medir_inclinacao.py` e `scripts/grade_deflacao_por_familia.py` desde #252-b, todos via
`backend/services/amostra_ledger.py` desde #255 (`scripts/amostra_ledger.py` e reexportacao).
Desde #255, `backend/services/ledger_leitura.py` chama `filtrar_amostra(linhas, "published_prob")`
para `/ledger/dia` e `/ledger/agregado`: o corte desta regra e NO-OP nesse campo por desenho —
`fora_da_janela_contaminada` so age sobre `calibrated_prob`. `published_prob` e o que o operador
viu de verdade, contaminado ou nao pelo bug da camada #248; o ledger publico existe para mostrar
o historico real, nao para proteger uma medicao de qualidade do MODELO — quem precisa do corte e
o gate #230/#251.
```

- [ ] **Step 5: `CLAUDE.md` — tabela de rotas e parágrafo Mistral v3.1**

Na tabela "API Lambda — armadilhas conhecidas", acrescentar duas linhas depois de `| /live-scores, /standings | /api/... (404) |`:
```markdown
old_string:
| `/live-scores`, `/standings` | `/api/...` (404) |
| `/api/backtesting/...` | |
```
```markdown
new_string:
| `/live-scores`, `/standings` | `/api/...` (404) |
| `/ledger/dia?data=YYYY-MM-DD` (#255) | `/api/ledger/dia` (404) |
| `/ledger/agregado?periodo=7d\|30d\|temporada&familia=&liga=` (#255) | `?periodo=1ano` etc. → 400, nunca 200 com dado inventado |
| `/api/backtesting/...` | |
```

No fim da seção "Contrato Mistral (#082, reforçado #181)", acrescentar parágrafo:
```markdown
old_string:
- **Probs no prompt em duas camadas (#181):** "Estatísticas Poisson" carrega RAW (uso interno do modelo), "PICKS DO PIPELINE" carrega DEFLATED (única fonte legítima para narrativa). Mistral é instruído via prompt rules a só citar deflated. Validação `backend/ai/mistral_contract.py::validate_output` inspeciona resumo + key_points + recomendação (full text) e loga violações via `sportsbankzu.mistral.contract`. Camada 6 (`_validate_recommendation_vs_pipeline` em `mistral_analysis.py`) só inspeciona `recomendacao_principal` e direção Over/Under — limitação documentada na docstring da função.
```
```markdown
new_string:
- **Probs no prompt em duas camadas (#181):** "Estatísticas Poisson" carrega RAW (uso interno do modelo), "PICKS DO PIPELINE" carrega DEFLATED (única fonte legítima para narrativa). Mistral é instruído via prompt rules a só citar deflated. Validação `backend/ai/mistral_contract.py::validate_output` inspeciona resumo + key_points + recomendação (full text) e loga violações via `sportsbankzu.mistral.contract`. Camada 6 (`_validate_recommendation_vs_pipeline` em `mistral_analysis.py`) só inspeciona `recomendacao_principal` e direção Over/Under — limitação documentada na docstring da função.
- **Vocabulário de operador — prompt v3.1 (#255).** A narrativa não pode citar "lambda", "deflação"/"deflacionado" nem "banda" — o operador lê "chance", "mínimo" (fair_odd), "paga" (book_odd), "gols/escanteios esperados por jogo". `validate_output` ganha uma quarta camada (`_VOCABULARIO_INTERNO`) sobre o mesmo texto completo das três anteriores. `SEM_RECOMENDACAO` (`backend/ai/mistral_contract.py`) é a única ocorrência do texto de "sem recomendação" — o prompt a importa em vez de repetir.
```

- [ ] **Step 6: Espelhar, commit, push, deploy, prova**

```bash
cp docs/REGISTRO_CORRECOES.md ../docs/REGISTRO_CORRECOES.md
cp docs/REGRAS_ATIVAS.md      ../docs/REGRAS_ATIVAS.md
cp docs/INDICE_REGRAS.md      ../docs/INDICE_REGRAS.md
cp CLAUDE.md                  ../CLAUDE.md
```
(ajustar o caminho relativo conforme o layout real dos dois diretórios espelhados — `c:\painel_apostas\sportsbank-pro\` é o segundo diretório, com a mesma estrutura `docs/` e `CLAUDE.md` na raiz.)

```bash
git add docs/REGISTRO_CORRECOES.md docs/REGRAS_ATIVAS.md docs/INDICE_REGRAS.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: REGISTRO #255 — rotas de ledger e vocabulario Mistral v3.1

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
git push origin main
```

Acompanhar o deploy automático (o push tocou `backend/**`):
```bash
gh run watch --exit-status
```
Expected: o workflow `Deploy Lambda` roda `pytest -q`, empacota, sobe pro S3, atualiza a função e aquece o cache de 22 ligas — ver `.github/workflows/deploy-lambda.yml`. Se o job `test` falhar, NÃO rodar `python scripts/deploy_lambda.py` por cima — corrigir o teste e deixar o push seguinte reacionar o workflow (Regra do CLAUDE.md, seção "Finalização obrigatória pós-alteração").

Curls de prova (contra a Function URL de produção, nunca `*.execute-api.*` — guarda #114/#203):
```bash
BASE="https://smjc75r2ob2oo53yknph7kbxb40aauko.lambda-url.us-east-1.on.aws"
curl -s "$BASE/health"
curl -s "$BASE/ledger/dia?data=2026-09-14" | head -c 500
time curl -s "$BASE/ledger/agregado?periodo=7d" | head -c 500
time curl -s "$BASE/ledger/agregado?periodo=temporada" | head -c 500
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/ledger/dia?data=14-09-2026"     # esperado: 400
curl -s -o /dev/null -w "%{http_code}\n" "$BASE/ledger/agregado?periodo=1ano"   # esperado: 400
```
Expected: `/health` → `{"status":"ok"}`; `/ledger/dia` e `/ledger/agregado?periodo=7d` → 200 com JSON (ou 503 estruturado, aceitável se a RDS não tiver dados na janela testada — o que importa é a FORMA da resposta, não o conteúdo); `periodo=temporada` (a maior janela) com tempo total **abaixo de 10s** — se estourar, é sinal de que a rota precisa de índice em `prediction_ledger(published_at)` ou de paginação, investigar antes de declarar a tarefa pronta; os dois últimos, 400 cravado.

Colar a saída real desses seis comandos no lugar do placeholder `[PREENCHER...]` do REGISTRO #255 (Step 2), e commitar separado:
```bash
git add docs/REGISTRO_CORRECOES.md
git commit -m "$(cat <<'EOF'
docs: prova pos-deploy do #255

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
git push origin main
```
(este último push não deve reacionar o deploy Lambda — só `docs/` mudou; confirmar com `gh run list --limit 3` que nenhum novo run de `Deploy Lambda` disparou.)

Espelhar de novo o `REGISTRO_CORRECOES.md` atualizado (Step 6, primeiro bloco) antes deste último commit, para os dois diretórios ficarem consistentes com o número real.

---

## Autorrevisão (fazer ao terminar, corrigir inline neste arquivo)

- [ ] Reler spec §6.3 item a item contra as Tasks 2/3/5: `dia` tem todos os campos listados (`match_id, league_id, kickoff_utc, familia, market, selection, published_prob, fair_odd, book_odd, classification, outcome, detail`, mais `picks/acertos/jogos` e os acumulados `semana`/`mes`)? `agregado` tem `acerto`, `retorno` (com o `motivo` documentado), por família/liga (`picks, acertos, brier, n_jogos`), `buckets` de 10 faixas, piso `MIN_N=20`? `fair_odd`/`book_odd` provados em `/fixtures`? Prompt Mistral rejeita os três termos?
- [ ] Nenhum placeholder além do único marcado `[PREENCHER com a saída real dos curls]` na Task 7.
- [ ] Nomes e assinaturas consistentes entre tarefas: `ledger_leitura.dia(data: str)` e `ledger_leitura.agregado(periodo, familia=None, liga=None, hoje=None)` usados do mesmo jeito nas Tasks 2, 3 e nos testes. `_conn()` é o nome do dublê monkeypatchado em todos os testes de `ledger_leitura`. `SEM_RECOMENDACAO` importado com o mesmo nome nas Tasks 6/7.
- [ ] Toda alteração em arquivo existente citada com número de linha aproximado confere com o conteúdo lido nesta sessão (`mistral_analysis.py:315/321-322/481/547`, `mistral_contract.py:194-212`, `market_output.py:64/147/176-177`, `prediction_ledger.py:706-729`, `deploy_lambda.py:38`, `deploy-lambda.yml:97`).
