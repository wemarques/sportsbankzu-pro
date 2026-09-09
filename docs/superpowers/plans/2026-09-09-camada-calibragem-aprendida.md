# Camada de Calibragem Aprendida — Plano de Implementação

> **Para trabalhadores agênticos:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam caixas (`- [ ]`) para acompanhamento.

**Objetivo:** Substituir a deflação fixa de probabilidade por uma correção de dois parâmetros por família que se ajusta sozinha a cada lote de jogos liquidados, com trava de passo, reversão fora da amostra e auditoria de toda decisão.

**Arquitetura:** Quatro módulos com fronteiras duras em `backend/modeling/calibragem/` — `curva` (matemática pura), `estimador` (ajuste, sem I/O), `repositorio` (único que toca o banco) e `governanca` (política, sem ajuste). A pilha de deflação de hoje é movida inteira para `legado.py`, congelada, e serve como versão 0 para que o deploy não mude nenhum número. `_calibrar_com_detalhe` passa a ter um único caminho.

**Stack:** Python 3, pytest, psycopg2. **Sem numpy, sem scipy, sem sklearn** no caminho de `curva`, `estimador` e `governanca` — o ajuste é intercepto + um regressor, e a inversa 2×2 é escrita à mão. Motivo: `scipy` vive numa Layer do Lambda que já falhou em silêncio (B-014, NB2 de cartões caindo para Poisson sem aviso). Um estimador sem dependência não pode ter esse modo de falha.

**Spec:** `docs/superpowers/specs/2026-09-09-camada-calibragem-aprendida-design.md`

## Restrições globais

Valores copiados literalmente da spec. Todas as tarefas as herdam.

- **Trava de passo:** entre a versão vigente e a proposta, `max |curva_nova(p) − curva_vigente(p)| ≤ 0,02` para `p ∈ [0,02; 0,98]`. Proposta que ultrapassa é **encurtada**, nunca rejeitada, e o fator fica gravado.
- **Piso de amostra:** `MIN_N_JOGOS = 20` (reusa `MIN_N_BRIER` do #079). Abaixo disso a célula usa o pai e registra `abaixo_do_piso`.
- **`k` do encolhimento:** estimado dos dados; com menos de 5 células acima do piso, `k = 40` jogos, e a queda no valor fixo fica gravada.
- **`n_prior` da semente:** `150 · concordancia`, teto 150, piso 0. Menos de 30 picks sobrepostos → `n_prior = 75`, status `semente_nao_validada`.
- **`n_efetivo` conta JOGOS, nunca picks.** Em todo lugar.
- **`b > 0` obrigatório.** `b ≤ 0` → célula rejeitada, usa o pai.
- **Reversão:** pelo ponto, exigindo ≥ 20 jogos na janela. Duas reversões seguidas congelam a célula e alertam.
- **Auditoria:** toda célula gera linha em todo ciclo, inclusive `inalterada`.
- **Fonte proibida:** `audit_results` não pode ser lida por nenhum módulo deste pacote (regra #244).
- **Entrada:** `prediction_ledger.raw_prob`. Nunca `iso_prob`, nunca `calibrated_prob`.
- **Contagem no ledger:** uma linha por `(match_id, market, selection)` — a última geração antes do kickoff.
- **Protocolo do repositório (`CLAUDE.md`):** toda alteração exige entrada em `docs/REGISTRO_CORRECOES.md` e `docs/INDICE_REGRAS.md`; regras permanentes também em `docs/REGRAS_ATIVAS.md`. Commits vão direto na `main`. Rodar `pytest -q -p no:cacheprovider -o addopts=""` (o `addopts` do `pytest.ini` exige o plugin de cobertura).

---

## Estrutura de arquivos

| arquivo | responsabilidade |
|---|---|
| `backend/modeling/calibragem/__init__.py` | Constantes públicas do pacote (`MIN_N_JOGOS`, `PASSO_MAXIMO_PP`, `K_FIXO`, `TETO_N_PRIOR`). |
| `backend/modeling/calibragem/legado.py` | **Congelado.** A pilha de deflação de hoje, movida sem alteração. Único chamador: `curva.aplicar_versao` na versão 0. |
| `backend/modeling/calibragem/curva.py` | `aplicar(p, a, b)` e `aplicar_versao(...)`. Matemática pura. |
| `backend/modeling/calibragem/estimador.py` | Ajuste por célula (IRLS), encolhimento hierárquico, semente. Sem I/O. |
| `backend/modeling/calibragem/governanca.py` | Trava, piso, `b > 0`, reversão, anti-oscilação. Sem ajuste, sem I/O. |
| `backend/modeling/calibragem/repositorio.py` | Único módulo com `psycopg2`. Amostra, versões, auditoria. |
| `backend/modeling/calibragem/ciclo.py` | Orquestra: carrega → ajusta → governa → grava. Chamado pelo cron. |
| `tests/calibragem/test_01_legado_controle_positivo.py` … `test_09_guardas.py` | Um arquivo por tarefa. |
| `tests/calibragem/fixtures/golden_legado.json` | Pares entrada→saída capturados da produção antes do refactor. |

Modificados: `backend/services/ev_classification.py` (a costura), `backend/cron_handler.py` (o ciclo), `backend/services/prediction_ledger.py` (nada — só leitura de fora).

---

## Task 1: Fixture dourada, `legado.py` e a costura

O controle positivo tem de estar verde antes de existir qualquer coisa para calibrar. A fixture é capturada do código **atual**, antes de qualquer movimentação — é a única forma de provar igualdade exata através de um refactor.

**Files:**
- Create: `tests/calibragem/__init__.py`
- Create: `scripts/capturar_golden_legado.py`
- Create: `tests/calibragem/fixtures/golden_legado.json`
- Create: `backend/modeling/calibragem/__init__.py`
- Create: `backend/modeling/calibragem/legado.py`
- Create: `tests/calibragem/test_01_legado_controle_positivo.py`
- Modify: `backend/services/ev_classification.py` (função `_calibrar_com_detalhe`)

**Interfaces:**
- Consumes: nada.
- Produces: `legado.calibrar_legado(raw: float, market: str, league_id: str, regime: str) -> DetalheCalibracao`, onde `DetalheCalibracao` é a dataclass que já existe em `ev_classification.py` (campos `iso`, `banda`, `tipo_banda`, `liga`, `ou_defl`, `under25_extra`, `final`).

- [ ] **Step 1: Criar o pacote de testes**

```bash
mkdir -p tests/calibragem/fixtures backend/modeling/calibragem
printf '' > tests/calibragem/__init__.py
```

- [ ] **Step 2: Escrever o capturador da fixture dourada**

Create `scripts/capturar_golden_legado.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Captura pares entrada->saida de `_calibrar_com_detalhe` ANTES do refactor.

A fixture existe para provar IGUALDADE EXATA depois que a pilha de deflacao
for movida para `calibragem/legado.py`. Rodar UMA vez, com o codigo ainda
intacto, e versionar o JSON. Rodar de novo depois do refactor invalida o
proprio controle.
"""
import json
import os
import pathlib
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from backend.services.ev_classification import _calibrar_com_detalhe  # noqa: E402

MERCADOS = [
    "Over 0.5", "Over 1.5", "Over 2.5", "Over 3.5", "Over 4.5",
    "Under 1.5", "Under 2.5", "Under 3.5", "Under 4.5",
    "BTTS",
    "Escanteios Over 4.5", "Escanteios Over 7.5", "Escanteios Over 11.5",
    "Escanteios Under 8.5", "Escanteios Under 12.5",
    "Cartoes Over 1.5", "Cartoes Over 2.5", "Cartoes Under 4.5",
    "1X2 Home", "1X2 Draw", "DC 1X", "DC X2", "DC 12",
]
LIGAS = ["", "premier-league", "mls", "primeira-liga", "serie-a", "liga-inexistente"]
REGIMES = ["NORMAL", "HIPER-OFENSIVA"]
PROBS = [round(0.02 + i * 0.02, 2) for i in range(49)]   # 0.02 .. 0.98


def main() -> int:
    casos = []
    for market in MERCADOS:
        for league_id in LIGAS:
            for regime in REGIMES:
                for raw in PROBS:
                    d = _calibrar_com_detalhe(raw, market, league_id, regime)
                    casos.append({
                        "raw": raw, "market": market, "league_id": league_id,
                        "regime": regime,
                        "final": d.final, "iso": d.iso, "banda": d.banda,
                        "tipo_banda": d.tipo_banda, "liga": d.liga,
                        "ou_defl": d.ou_defl, "under25_extra": d.under25_extra,
                    })
    destino = pathlib.Path(RAIZ) / "tests/calibragem/fixtures/golden_legado.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")
    print(f"{len(casos)} casos gravados em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Rodar o capturador com o código ainda intacto**

Run: `PYTHONIOENCODING=utf-8 python scripts/capturar_golden_legado.py`
Expected: `13524 casos gravados em .../golden_legado.json` (23 mercados × 6 ligas × 2 regimes × 49 probs).

Se o número for diferente, conferir se algum mercado levantou exceção — a fixture tem de cobrir os quatro caminhos (`meia-btts`, `meia`, `inteira`, e o extra de Under 2.5).

- [ ] **Step 4: Escrever o teste do controle positivo (vai falhar)**

Create `tests/calibragem/test_01_legado_controle_positivo.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 1 da spec — a versao 0 reproduz a producao com IGUALDADE EXATA.

A fixture foi capturada do codigo anterior ao refactor. Se este teste passar,
mover a pilha de deflacao para `legado.py` nao mudou nenhum numero publicado.
Se falhar, a costura esta errada e nada mais no pacote importa.
"""
import json
import pathlib

import pytest

from backend.modeling.calibragem.legado import calibrar_legado

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "golden_legado.json"


@pytest.fixture(scope="module")
def casos():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_cobre_os_quatro_caminhos(casos):
    tipos = {c["tipo_banda"] for c in casos}
    assert {"meia-btts", "meia", "inteira"} <= tipos, tipos
    assert any(c["under25_extra"] for c in casos), "extra de Under 2.5 nao coberto"


def test_legado_reproduz_a_producao_exatamente(casos):
    divergentes = []
    for c in casos:
        d = calibrar_legado(c["raw"], c["market"], c["league_id"], c["regime"])
        if d.final != c["final"]:
            divergentes.append((c["market"], c["league_id"], c["raw"],
                                c["final"], d.final))
    assert not divergentes, f"{len(divergentes)} divergencias: {divergentes[:5]}"


def test_legado_preserva_o_detalhe_inteiro(casos):
    for c in casos[:500]:
        d = calibrar_legado(c["raw"], c["market"], c["league_id"], c["regime"])
        assert d.iso == c["iso"]
        assert d.banda == c["banda"]
        assert d.tipo_banda == c["tipo_banda"]
        assert d.liga == c["liga"]
        assert d.ou_defl == c["ou_defl"]
        assert d.under25_extra == c["under25_extra"]
```

- [ ] **Step 5: Rodar o teste para vê-lo falhar**

Run: `python -m pytest tests/calibragem/test_01_legado_controle_positivo.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.legado'`

- [ ] **Step 6: Criar `__init__.py` do pacote com as constantes**

Create `backend/modeling/calibragem/__init__.py`:

```python
# -*- coding: utf-8 -*-
"""Camada de calibragem aprendida.

Substitui a deflacao fixa por uma correcao de dois parametros por familia que
se ajusta a cada lote de jogos liquidados. Spec:
docs/superpowers/specs/2026-09-09-camada-calibragem-aprendida-design.md
"""

# Piso de decisao. Reusa a constante do #079 (`MIN_N_BRIER = 20`): abaixo
# disso o repositorio ja trata amostra como diagnostica, nunca decisoria.
MIN_N_JOGOS = 20

# Trava: mudanca maxima de probabilidade que um pick pode sofrer num ciclo.
PASSO_MAXIMO_PP = 0.02

# `k` do encolhimento quando ha celulas de menos para estima-lo dos dados.
# O dobro do piso: uma celula precisa do dobro do minimo para valer tanto
# quanto o pai.
K_FIXO = 40
MIN_CELULAS_PARA_ESTIMAR_K = 5

# Semente do backfill.
TETO_N_PRIOR = 150
N_PRIOR_NAO_VALIDADA = 75
MIN_PICKS_PARA_VALIDAR_SEMENTE = 30
TOLERANCIA_CONCORDANCIA = 0.02

VERSAO_LEGADO = 0
```

- [ ] **Step 7: Mover a pilha de deflação para `legado.py`**

Create `backend/modeling/calibragem/legado.py`. Copiar, **sem alterar uma linha de lógica**, o corpo de `_calibrar_com_detalhe` de `backend/services/ev_classification.py` e renomeá-lo para `calibrar_legado`. Manter todos os comentários históricos (#105, #113, #152, #156, #161, #165, #165-e, #189-a, #216) — eles são o registro de por que cada exceção existe.

Cabeçalho obrigatório do arquivo:

```python
# -*- coding: utf-8 -*-
"""CONGELADO — a pilha de deflacao anterior a camada aprendida.

PROIBIDO EDITAR. Este modulo existe por um motivo unico: ser a versao 0, para
que o deploy da camada nao mude nenhum numero publicado (spec, secao 6.1).
Cada celula que sai da versao 0 deixa de chama-lo. Quando nenhuma celula
referenciar mais a versao 0, este arquivo e APAGADO — o teste 1b guarda essa
transicao.

Unico chamador permitido: `calibragem.curva.aplicar_versao`.
"""
```

As dependências que vinham de `ev_classification` (`_band_deflation`, `_league_deflation_factor`, `apply_probability_deflation`, `_canonical_league`, `_DEFAULT_OU_DEFLATION`, `_LEAGUE_DEFLATION`, `_DEFLATION_KNOTS`, `calibrate_prob`, `DetalheCalibracao`) vêm **junto** para `legado.py`, exceto `DetalheCalibracao` e `calibrate_prob`, que ficam importados. Isso é deliberado: `legado.py` tem de ser deletável sem deixar buraco.

- [ ] **Step 8: Rodar o teste — agora tem de passar**

Run: `python -m pytest tests/calibragem/test_01_legado_controle_positivo.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 3 testes.

Se `test_legado_reproduz_a_producao_exatamente` falhar, algo foi alterado na movimentação. A mensagem lista as cinco primeiras divergências com mercado, liga e raw — comparar o caminho daquele mercado no arquivo novo com o original no `git diff`.

- [ ] **Step 9: Costurar `_calibrar_com_detalhe` ao legado**

Modify `backend/services/ev_classification.py`: o corpo de `_calibrar_com_detalhe` vira uma delegação, preservando a assinatura e o docstring com um ponteiro:

```python
def _calibrar_com_detalhe(raw: float, market: str, league_id: str, regime: str) -> DetalheCalibracao:
    """Calibra a probabilidade publicada.

    #248: o corpo desta funcao — bandas do #105, meia-banda de BTTS (#152),
    meia-banda de gols (#165-e), fator por liga (#189-e) e o extra de Under
    2.5 (#113) — mudou inteiro para `calibragem/legado.py`, congelado, e passa
    a ser a VERSAO 0 da camada aprendida. Nao ha segundo caminho vivo: quem
    decide qual versao serve e `curva.aplicar_versao`.
    """
    from backend.modeling.calibragem.curva import aplicar_versao
    return aplicar_versao(raw, market, league_id, regime)
```

**Ainda não** criar `curva.py` — isso é a Task 2. Neste passo, importar `calibrar_legado` diretamente para manter a suíte verde:

```python
    from backend.modeling.calibragem.legado import calibrar_legado
    return calibrar_legado(raw, market, league_id, regime)
```

- [ ] **Step 10: Rodar a suíte inteira**

Run: `python -m pytest -q -p no:cacheprovider -o addopts=""`
Expected: `1017 passed, 8 skipped` — o mesmo número de antes do refactor. Qualquer teste novo que falhe indica que a movimentação alterou comportamento.

- [ ] **Step 11: Commit**

```bash
git add backend/modeling/calibragem/ tests/calibragem/ scripts/capturar_golden_legado.py backend/services/ev_classification.py
git commit -m "refactor: pilha de deflacao vira calibragem/legado.py, congelada (#248)

Controle positivo: 13.524 pares entrada->saida capturados da producao ANTES
do refactor; o legado reproduz todos com igualdade exata, incluindo o detalhe
(iso, banda, tipo_banda, liga, ou_defl, under25_extra).

Nenhum numero publicado muda. Suite: 1017 passed, 8 skipped."
```

---

## Task 2: `curva.py` — a função de dois parâmetros e o sentinela da versão 0

**Files:**
- Create: `backend/modeling/calibragem/curva.py`
- Create: `tests/calibragem/test_02_curva.py`
- Modify: `backend/services/ev_classification.py` (trocar o import direto do legado por `aplicar_versao`)

**Interfaces:**
- Consumes: `legado.calibrar_legado(raw, market, league_id, regime) -> DetalheCalibracao`.
- Produces:
  - `curva.aplicar(p: float, a: float, b: float) -> float`
  - `curva.familia_do_mercado(market: str) -> str` (devolve `"Over/Under" | "BTTS" | "Corners" | "Cards" | "1X2" | "Double Chance"`)
  - `curva.aplicar_versao(raw, market, league_id, regime) -> DetalheCalibracao`
  - `curva.distancia_maxima(a1, b1, a2, b2) -> float`

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_02_curva.py`:

```python
# -*- coding: utf-8 -*-
"""A curva de dois parametros: identidade, monotonicidade, bordas, versao 0."""
import math

import pytest

from backend.modeling.calibragem import VERSAO_LEGADO
from backend.modeling.calibragem.curva import (
    aplicar, distancia_maxima, familia_do_mercado,
)


def test_a_zero_b_um_e_a_identidade():
    for p in (0.05, 0.2, 0.5, 0.734, 0.95):
        assert aplicar(p, 0.0, 1.0) == pytest.approx(p, abs=1e-12)


def test_a_positivo_sobe_a_probabilidade():
    assert aplicar(0.5, 0.4, 1.0) > 0.5


def test_b_menor_que_um_encolhe_os_extremos():
    """b < 1 puxa as pontas para o meio; o meio (p=0,5) fica parado."""
    assert aplicar(0.5, 0.0, 0.7) == pytest.approx(0.5, abs=1e-12)
    assert aplicar(0.9, 0.0, 0.7) < 0.9
    assert aplicar(0.1, 0.0, 0.7) > 0.1


def test_e_monotona_quando_b_positivo():
    anterior = -1.0
    for i in range(1, 1000):
        atual = aplicar(i / 1000.0, 0.3, 0.8)
        assert atual > anterior, i
        anterior = atual


def test_bordas_nao_estouram():
    """p=0 e p=1 dariam logit infinito; a funcao prende antes."""
    assert 0.0 < aplicar(0.0, 0.0, 1.0) < 0.001
    assert 0.999 < aplicar(1.0, 0.0, 1.0) < 1.0
    assert 0.0 < aplicar(1e-300, 2.0, 3.0) < 1.0


@pytest.mark.parametrize("market,esperado", [
    ("Over 2.5", "Over/Under"), ("Under 3.5", "Over/Under"),
    ("BTTS", "BTTS"),
    ("Escanteios Over 7.5", "Corners"), ("Escanteios Under 12.5", "Corners"),
    ("Cartoes Over 2.5", "Cards"), ("Cartoes Under 4.5", "Cards"),
    ("1X2 Home", "1X2"), ("1X2 Draw", "1X2"),
    ("DC 1X", "Double Chance"), ("DC X2", "Double Chance"),
])
def test_familia_do_mercado(market, esperado):
    assert familia_do_mercado(market) == esperado


def test_familia_desconhecida_levanta():
    """Mercado novo tem de quebrar aqui, nao virar silenciosamente 1X2."""
    with pytest.raises(ValueError, match="familia desconhecida"):
        familia_do_mercado("Handicap Asiatico -1.5")


def test_distancia_maxima_e_zero_para_parametros_iguais():
    assert distancia_maxima(0.3, 0.9, 0.3, 0.9) == pytest.approx(0.0, abs=1e-12)


def test_distancia_maxima_encontra_o_pior_ponto():
    d = distancia_maxima(0.0, 1.0, 0.4, 1.0)
    # a=0.4 em p=0.5 leva a sigmoid(0.4)=0.5987 -> 0.0987 de diferenca
    assert d == pytest.approx(0.0987, abs=0.002)


def test_versao_legado_e_zero():
    assert VERSAO_LEGADO == 0
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_02_curva.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.curva'`

- [ ] **Step 3: Implementar `curva.py`**

Create `backend/modeling/calibragem/curva.py`:

```python
# -*- coding: utf-8 -*-
"""A curva de correcao: logit(p') = a + b*logit(p).

Matematica pura, sem I/O e sem dependencia externa. `a` e o deslocamento
sistematico (positivo = o motor publica abaixo da realidade); `b` e a
dispersao (b < 1 = o motor exagera nos extremos).
"""
import math
from typing import Optional

from backend.modeling.calibragem import VERSAO_LEGADO

# Prende p antes do logit. 1e-6 mantem logit em ~±13,8, longe de estourar em
# float, e a diferenca em probabilidade e invisivel no card (0,0001%).
_EPS = 1e-6

_FAMILIAS = (
    ("escanteios", "Corners"),
    ("cartoes", "Cards"),
    ("cartões", "Cards"),
    ("btts", "BTTS"),
    ("dc ", "Double Chance"),
    ("dupla chance", "Double Chance"),
    ("1x2", "1X2"),
    ("over ", "Over/Under"),
    ("under ", "Over/Under"),
)


def _prender(p: float) -> float:
    return min(max(float(p), _EPS), 1.0 - _EPS)


def _logit(p: float) -> float:
    p = _prender(p)
    return math.log(p / (1.0 - p))


def _sigmoide(x: float) -> float:
    # Forma estavel nos dois lados: evita overflow de exp(+x) para x grande.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def aplicar(p: float, a: float, b: float) -> float:
    """logit(p_corrigida) = a + b * logit(p). Monotona crescente se b > 0."""
    return _sigmoide(a + b * _logit(p))


def familia_do_mercado(market: str) -> str:
    """Familia a que o rotulo pertence. Levanta se nao reconhecer.

    Mercado novo tem de quebrar aqui em vez de cair numa familia por acaso —
    calibrar Handicap com a curva de 1X2 seria um erro invisivel.
    """
    m = (market or "").strip().lower()
    for prefixo, familia in _FAMILIAS:
        if prefixo in m:
            return familia
    raise ValueError(f"familia desconhecida para o mercado '{market}'")


def distancia_maxima(a1: float, b1: float, a2: float, b2: float,
                     passo: float = 0.001) -> float:
    """max |curva(p; a1,b1) - curva(p; a2,b2)| para p em [0,02; 0,98].

    Varredura em grade em vez de solucao analitica: a diferenca de duas
    sigmoides pode ter dois maximos locais, e a grade de 0,001 erra no maximo
    alguns milesimos de ponto — folgado para uma trava de 2 pontos.
    """
    pior = 0.0
    p = 0.02
    while p <= 0.98 + 1e-12:
        d = abs(aplicar(p, a1, b1) - aplicar(p, a2, b2))
        if d > pior:
            pior = d
        p += passo
    return pior


def aplicar_versao(raw: float, market: str, league_id: str, regime: str,
                   parametros: Optional[dict] = None):
    """Aplica a versao vigente da celula. Versao 0 delega ao legado.

    `parametros` e o mapa {(familia, liga): (versao, a, b)} lido pelo
    repositorio e passado pelo chamador. Ausente, ou celula ausente dele,
    significa versao 0 — o comportamento de hoje.
    """
    from backend.modeling.calibragem.legado import calibrar_legado

    if not parametros:
        return calibrar_legado(raw, market, league_id, regime)

    try:
        familia = familia_do_mercado(market)
    except ValueError:
        return calibrar_legado(raw, market, league_id, regime)

    chave = (familia, league_id or "")
    entrada = parametros.get(chave) or parametros.get((familia, ""))
    if not entrada or entrada[0] == VERSAO_LEGADO:
        return calibrar_legado(raw, market, league_id, regime)

    _versao, a, b = entrada
    detalhe = calibrar_legado(raw, market, league_id, regime)
    detalhe.final = aplicar(raw, a, b)
    detalhe.tipo_banda = f"curva-v{_versao}"
    return detalhe
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_02_curva.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 20 testes (os 11 parametrizados contam separado).

- [ ] **Step 5: Trocar a costura para `aplicar_versao`**

Modify `backend/services/ev_classification.py`, dentro de `_calibrar_com_detalhe`, trocando o import do passo 9 da Task 1:

```python
    from backend.modeling.calibragem.curva import aplicar_versao
    return aplicar_versao(raw, market, league_id, regime)
```

Sem `parametros`, `aplicar_versao` delega ao legado — o comportamento continua idêntico.

- [ ] **Step 6: Rodar Task 1 e a suíte**

Run: `python -m pytest tests/calibragem/ -q -p no:cacheprovider -o addopts="" && python -m pytest -q -p no:cacheprovider -o addopts=""`
Expected: `1017 passed, 8 skipped` na suíte inteira. O controle positivo da Task 1 continua verde através de `aplicar_versao`.

- [ ] **Step 7: Commit**

```bash
git add backend/modeling/calibragem/curva.py tests/calibragem/test_02_curva.py backend/services/ev_classification.py
git commit -m "feat: curva de dois parametros e sentinela da versao 0 (#248)

logit(p') = a + b*logit(p), monotona por construcao quando b > 0 — a ordem
das linhas e preservada, e portanto o filtro de corredor (#246-a) nao muda
por efeito colateral.

Mercado sem familia reconhecida LEVANTA em vez de cair numa familia por
acaso. Sem parametros, delega ao legado: nenhum numero muda."
```

---

## Task 3: Tabela `calibragem_versoes` e a leitura da amostra

**Files:**
- Create: `backend/modeling/calibragem/repositorio.py`
- Create: `tests/calibragem/test_03_repositorio_amostra.py`

**Interfaces:**
- Consumes: `curva.familia_do_mercado`.
- Produces:
  - `repositorio.garantir_tabela() -> bool`
  - `repositorio.carregar_amostra(desde: Optional[str] = None) -> List[Pick]`, onde `Pick` é o `NamedTuple` `(match_id, familia, liga, p_raw, y)`
  - `repositorio.escolher_ultima_geracao(linhas) -> List[dict]` (pura, testável sem banco)

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_03_repositorio_amostra.py`:

```python
# -*- coding: utf-8 -*-
"""A regra de contagem do ledger.

O `prediction_ledger` e append-only e guarda VARIAS geracoes por jogo. Toronto
x Nashville (09/09) tem duas, 03:09 e 11:09, com numeros diferentes. Treinar
em todas conta o mesmo jogo mais de uma vez e da mais peso aos jogos que foram
recomputados mais vezes.
"""
import datetime as dt

import pytest

from backend.modeling.calibragem.repositorio import escolher_ultima_geracao


def _linha(match_id, market, selection, publicado, kickoff, raw):
    return {
        "match_id": match_id, "market": market, "selection": selection,
        "published_at": publicado, "kickoff_utc": kickoff, "raw_prob": raw,
    }


KICK = dt.datetime(2026, 9, 9, 20, 30, tzinfo=dt.timezone.utc)


def test_mantem_a_ultima_geracao_antes_do_kickoff():
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.61),
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), KICK, 0.58),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1
    assert saida[0]["raw_prob"] == 0.58


def test_descarta_geracao_posterior_ao_kickoff():
    """Recomputacao pos-jogo nao e prognostico — e o defeito do #200."""
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), KICK, 0.58),
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.timezone.utc), KICK, 0.99),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1
    assert saida[0]["raw_prob"] == 0.58


def test_selecoes_diferentes_do_mesmo_jogo_sobrevivem_as_duas():
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.61),
        _linha("m1", "Over/Under", "Under 3.5", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), KICK, 0.64),
    ]
    assert len(escolher_ultima_geracao(linhas)) == 2


def test_sem_kickoff_mantem_a_ultima_publicacao():
    """kickoff_utc e nulo em parte do historico; a regra degrada, nao quebra."""
    linhas = [
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 3, 9, tzinfo=dt.timezone.utc), None, 0.55),
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 11, 9, tzinfo=dt.timezone.utc), None, 0.57),
    ]
    saida = escolher_ultima_geracao(linhas)
    assert len(saida) == 1 and saida[0]["raw_prob"] == 0.57


def test_todas_as_geracoes_posteriores_ao_kickoff_nao_deixa_nada():
    linhas = [
        _linha("m1", "BTTS", "BTTS Yes", dt.datetime(2026, 9, 9, 23, 0, tzinfo=dt.timezone.utc), KICK, 0.99),
    ]
    assert escolher_ultima_geracao(linhas) == []


def test_nao_ha_caminho_de_codigo_para_audit_results():
    """Teste 9 da spec, aplicado cedo — a regra #244 vale desde o primeiro modulo."""
    import pathlib
    fonte = pathlib.Path("backend/modeling/calibragem/repositorio.py").read_text(encoding="utf-8")
    assert "audit_results" not in fonte
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_03_repositorio_amostra.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.repositorio'`

- [ ] **Step 3: Implementar `repositorio.py` (tabela + regra de contagem + leitura)**

Create `backend/modeling/calibragem/repositorio.py`:

```python
# -*- coding: utf-8 -*-
"""Unico modulo do pacote que toca o banco.

FONTE PROIBIDA: `audit_results`. Ele e recomputado pos-jogo (#200) e a regra
#244 proibe usa-lo como fonte de calibracao. Nao ha caminho de codigo para ele
aqui, e um teste guarda isso.
"""
import logging
import os
from typing import Any, Dict, List, NamedTuple, Optional

from backend.modeling.calibragem.curva import familia_do_mercado

logger = logging.getLogger("sportsbankzu.calibragem.repositorio")

DDL = """
CREATE TABLE IF NOT EXISTS calibragem_versoes (
    id                  BIGSERIAL PRIMARY KEY,
    criada_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    familia             TEXT NOT NULL,
    liga                TEXT NOT NULL DEFAULT '',
    versao              INTEGER NOT NULL,
    a                   DOUBLE PRECISION,
    b                   DOUBLE PRECISION,
    n_jogos             INTEGER NOT NULL DEFAULT 0,
    brier_validacao     DOUBLE PRECISION,
    origem              TEXT,
    status              TEXT NOT NULL,
    fator_encurtamento  DOUBLE PRECISION,
    motivo              TEXT
);
CREATE INDEX IF NOT EXISTS idx_calibragem_celula
    ON calibragem_versoes (familia, liga, versao DESC);
CREATE INDEX IF NOT EXISTS idx_calibragem_vigente
    ON calibragem_versoes (familia, liga) WHERE status = 'vigente';
"""


class Pick(NamedTuple):
    match_id: str
    familia: str
    liga: str
    p_raw: float
    y: int


def _conn():
    import psycopg2
    return psycopg2.connect(os.environ["DATABASE_URL"])


def garantir_tabela() -> bool:
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(DDL)
        return True
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] tabela nao garantida: %s", e)
        return False


def escolher_ultima_geracao(linhas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Uma linha por (match_id, market, selection): a ultima ANTES do kickoff.

    O ledger e append-only com varias geracoes por jogo. A que vale e a que o
    operador viu por ultimo, e ela tem de ser anterior ao apito — geracao
    posterior ao kickoff nao e prognostico, e o defeito do #200.
    """
    melhor: Dict[tuple, Dict[str, Any]] = {}
    for ln in linhas:
        kickoff = ln.get("kickoff_utc")
        publicado = ln.get("published_at")
        if kickoff is not None and publicado is not None and publicado >= kickoff:
            continue
        chave = (ln.get("match_id"), ln.get("market"), ln.get("selection"))
        atual = melhor.get(chave)
        if atual is None or (publicado is not None
                             and atual.get("published_at") is not None
                             and publicado > atual["published_at"]):
            melhor[chave] = ln
    return list(melhor.values())


def carregar_amostra(desde: Optional[str] = None) -> List[Pick]:
    """Picks publicados PRE-JOGO com desfecho, prontos para o estimador."""
    sql = """
        SELECT l.match_id, l.league_id, l.market, l.selection,
               l.raw_prob, l.published_at, l.kickoff_utc, o.outcome
          FROM prediction_ledger l
          JOIN ledger_outcomes o
            ON o.match_id  = l.match_id
           AND o.market    = l.market
           AND o.selection = l.selection
         WHERE l.raw_prob IS NOT NULL
           AND o.outcome IS NOT NULL
    """
    params: list = []
    if desde:
        sql += " AND l.published_at >= %s"
        params.append(desde)

    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        brutas = [
            {"match_id": r[0], "league_id": r[1] or "", "market": r[2],
             "selection": r[3], "raw_prob": float(r[4]), "published_at": r[5],
             "kickoff_utc": r[6], "outcome": r[7]}
            for r in cur.fetchall()
        ]

    saida: List[Pick] = []
    sem_familia = 0
    for ln in escolher_ultima_geracao(brutas):
        rotulo = f"{ln['market']} {ln['selection']}".strip()
        try:
            familia = familia_do_mercado(rotulo)
        except ValueError:
            sem_familia += 1
            continue
        saida.append(Pick(ln["match_id"], familia, ln["league_id"],
                          ln["raw_prob"], int(bool(int(ln["outcome"])))))
    if sem_familia:
        logger.warning("[calibragem] %d picks sem familia reconhecida", sem_familia)
    return saida
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_03_repositorio_amostra.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 6 testes.

- [ ] **Step 5: Criar a tabela no banco real e conferir a amostra**

Run:
```bash
PYTHONPATH=. PYTHONIOENCODING=utf-8 python -c "
from dotenv import load_dotenv; load_dotenv('.env')
from backend.modeling.calibragem.repositorio import garantir_tabela, carregar_amostra
print('tabela:', garantir_tabela())
a = carregar_amostra()
print('picks:', len(a), '| jogos:', len({p.match_id for p in a}))
from collections import Counter
print(Counter(p.familia for p in a).most_common())
"
```
Expected: `tabela: True`, e uma contagem de jogos **próxima de 220** — não de 1.042. Se o número de jogos vier igual ao de gerações, `escolher_ultima_geracao` não está sendo aplicada.

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/calibragem/repositorio.py tests/calibragem/test_03_repositorio_amostra.py
git commit -m "feat: tabela calibragem_versoes e leitura da amostra do ledger (#248)

Regra de contagem: uma linha por (jogo, mercado, selecao), a ultima geracao
ANTES do kickoff. Geracao posterior ao apito e descartada — e o defeito do
#200, e o ledger tambem o tem quando o cron recomputa.

Nenhum caminho de codigo para audit_results (regra #244), com teste."
```

---

## Task 4: `estimador.py` — o ajuste por célula

**Files:**
- Create: `backend/modeling/calibragem/estimador.py`
- Create: `tests/calibragem/test_04_estimador_ajuste.py`

**Interfaces:**
- Consumes: `curva.aplicar`, `repositorio.Pick`.
- Produces: `estimador.ajustar(picks: Sequence[Pick]) -> Optional[Tuple[float, float]]` — devolve `(a, b)` por máxima verossimilhança, ou `None` quando não converge ou a amostra é degenerada (todos os desfechos iguais).

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_04_estimador_ajuste.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 2 da spec — o estimador recupera parametros que ele mesmo gerou.

Se nao recupera o sintetico, nao recupera o real. Este e o controle negativo
do estimador, e vem antes de qualquer numero de producao.
"""
import random

import pytest

from backend.modeling.calibragem.curva import aplicar
from backend.modeling.calibragem.estimador import ajustar
from backend.modeling.calibragem.repositorio import Pick


def _sintetico(a, b, n=8000, semente=227):
    """Gera picks cujo desfecho segue EXATAMENTE a curva (a, b)."""
    rng = random.Random(semente)
    picks = []
    for i in range(n):
        p_raw = rng.uniform(0.05, 0.95)
        p_real = aplicar(p_raw, a, b)
        y = 1 if rng.random() < p_real else 0
        picks.append(Pick(f"jogo{i}", "Over/Under", "liga", p_raw, y))
    return picks


@pytest.mark.parametrize("a,b", [(0.0, 1.0), (0.45, 1.0), (0.0, 0.7), (0.3, 1.2), (-0.2, 0.9)])
def test_recupera_os_parametros_sinteticos(a, b):
    est = ajustar(_sintetico(a, b))
    assert est is not None
    a_est, b_est = est
    assert a_est == pytest.approx(a, abs=0.08), f"a: {a_est} vs {a}"
    assert b_est == pytest.approx(b, abs=0.10), f"b: {b_est} vs {b}"


def test_amostra_degenerada_devolve_none():
    """Todos os desfechos iguais: a verossimilhanca nao tem maximo finito."""
    picks = [Pick(f"j{i}", "BTTS", "liga", 0.5, 1) for i in range(100)]
    assert ajustar(picks) is None


def test_amostra_minuscula_devolve_none():
    assert ajustar([Pick("j1", "BTTS", "liga", 0.5, 1)]) is None
    assert ajustar([]) is None


def test_nao_usa_numpy_nem_scipy():
    """A Layer do Lambda ja falhou em silencio (B-014). Sem dependencia."""
    import pathlib
    fonte = pathlib.Path("backend/modeling/calibragem/estimador.py").read_text(encoding="utf-8")
    for proibido in ("numpy", "scipy", "sklearn", "pandas"):
        assert proibido not in fonte, proibido
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_04_estimador_ajuste.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.estimador'`

- [ ] **Step 3: Implementar o ajuste (IRLS com inversa 2×2 à mão)**

Create `backend/modeling/calibragem/estimador.py`:

```python
# -*- coding: utf-8 -*-
"""Ajuste de (a, b) por celula. Sem I/O e sem dependencia externa.

O modelo e regressao logistica com intercepto e UM regressor, logit(p_raw).
Com dois parametros, a matriz de informacao e 2x2 e a inversa se escreve a
mao — nao ha motivo para numpy/scipy, e a Layer do Lambda ja falhou em
silencio uma vez (B-014, NB2 de cartoes caindo para Poisson sem aviso).
"""
import logging
import math
from typing import Optional, Sequence, Tuple

from backend.modeling.calibragem.curva import _logit, _sigmoide

logger = logging.getLogger("sportsbankzu.calibragem.estimador")

_MAX_ITER = 50
_TOL = 1e-9
_RIDGE = 1e-6      # regularizacao minima: impede matriz singular em amostra rala


def ajustar(picks: Sequence) -> Optional[Tuple[float, float]]:
    """(a, b) por maxima verossimilhanca. None se degenerado ou nao converge."""
    if len(picks) < 2:
        return None
    ys = {p.y for p in picks}
    if len(ys) < 2:
        return None    # todos 0 ou todos 1: sem maximo finito

    xs = [_logit(p.p_raw) for p in picks]
    yv = [float(p.y) for p in picks]

    a, b = 0.0, 1.0
    for _ in range(_MAX_ITER):
        # Gradiente e Hessiana da log-verossimilhanca.
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, yv):
            mu = _sigmoide(a + b * x)
            r = y - mu
            w = mu * (1.0 - mu)
            g0 += r
            g1 += r * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        h00 += _RIDGE
        h11 += _RIDGE

        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-14:
            logger.info("[calibragem] Hessiana singular; ajuste abortado")
            return None

        # Passo de Newton: theta += H^-1 g, com H^-1 de uma 2x2 escrita a mao.
        da = (h11 * g0 - h01 * g1) / det
        db = (h00 * g1 - h01 * g0) / det
        a += da
        b += db

        if abs(da) < _TOL and abs(db) < _TOL:
            break
    else:
        logger.info("[calibragem] IRLS nao convergiu em %d iteracoes", _MAX_ITER)
        return None

    if not (math.isfinite(a) and math.isfinite(b)):
        return None
    return (a, b)
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_04_estimador_ajuste.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 8 testes.

Se algum caso paramétrico falhar por pouco, **não** afrouxar a tolerância — aumentar `n` no `_sintetico` e reconferir. Tolerância frouxa em controle negativo é a doença que este plano existe para evitar.

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/calibragem/estimador.py tests/calibragem/test_04_estimador_ajuste.py
git commit -m "feat: ajuste de (a,b) por celula, IRLS sem dependencia externa (#248)

Intercepto + um regressor: a Hessiana e 2x2 e a inversa e escrita a mao.
Sem numpy, scipy ou sklearn — a Layer do Lambda ja caiu em silencio (B-014).

Controle negativo: cinco pares (a,b) sinteticos recuperados dentro de 0,08 e
0,10. Amostra degenerada (todos os desfechos iguais) devolve None em vez de
divergir."
```

---

## Task 5: Encolhimento hierárquico com `n_efetivo` em jogos

Este é o detalhe que decide se o sistema aprende ou se engana sozinho.

**Files:**
- Modify: `backend/modeling/calibragem/estimador.py`
- Create: `tests/calibragem/test_05_encolhimento.py`

**Interfaces:**
- Consumes: `estimador.ajustar`.
- Produces:
  - `estimador.contar_jogos(picks) -> int`
  - `estimador.estimar_k(celulas: Dict[Any, Sequence]) -> Tuple[float, bool]` — devolve `(k, caiu_no_fixo)`
  - `estimador.encolher(theta_proprio, theta_pai, n_efetivo, k) -> Tuple[float, float]`
  - `estimador.ajustar_hierarquico(picks) -> Dict[Tuple[str, str], dict]` — chave `(familia, liga)`, valor `{"a", "b", "n_jogos", "origem", "k_fixo"}`. A célula global usa chave `("", "")`; a família usa `(familia, "")`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_05_encolhimento.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 3 da spec — `n_efetivo` conta JOGOS, nao picks.

Escanteios tem 7.299 picks em 220 jogos. `Over 2.5` e `BTTS` do mesmo jogo
dividem o mesmo placar: nao sao observacoes independentes. Contar picks daria
autonomia quase total a celula em cima de 220 jogos de informacao real.

E a mesma classe de erro do #196 (pareou desfechos de jogos diferentes), do
#243 (comparou odd em escala errada) e do #244 (leu calibracao em fonte
recomputada pos-jogo). Todos foram contagem indevida.
"""
import pytest

from backend.modeling.calibragem import K_FIXO
from backend.modeling.calibragem.estimador import contar_jogos, encolher
from backend.modeling.calibragem.repositorio import Pick


def test_conta_jogos_nao_picks():
    picks = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    assert contar_jogos(picks) == 1


def test_quarenta_picks_de_um_jogo_pesam_como_dois_picks_de_um_jogo():
    """O teste que guarda o detalhe. Mesmo jogo = mesmo peso."""
    um_jogo_40 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    um_jogo_2 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(2)]
    proprio, pai = (0.5, 1.0), (0.0, 1.0)
    assert encolher(proprio, pai, contar_jogos(um_jogo_40), K_FIXO) == \
           encolher(proprio, pai, contar_jogos(um_jogo_2), K_FIXO)


def test_sem_amostra_fica_no_pai():
    assert encolher((9.0, 9.0), (0.1, 0.8), 0, K_FIXO) == (0.1, 0.8)


def test_amostra_igual_a_k_fica_na_metade_do_caminho():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), K_FIXO, K_FIXO)
    assert a == pytest.approx(0.5)
    assert b == pytest.approx(1.0)


def test_amostra_enorme_ignora_o_pai():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), 100000, K_FIXO)
    assert a == pytest.approx(1.0, abs=0.001)
    assert b == pytest.approx(2.0, abs=0.001)


def test_k_cai_no_fixo_com_poucas_celulas():
    from backend.modeling.calibragem.estimador import estimar_k
    k, caiu = estimar_k({("Corners", ""): []})
    assert caiu is True
    assert k == K_FIXO
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_05_encolhimento.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ImportError: cannot import name 'contar_jogos'`

- [ ] **Step 3: Implementar o encolhimento**

Append to `backend/modeling/calibragem/estimador.py`:

```python
from collections import defaultdict
from typing import Any, Dict

from backend.modeling.calibragem import (
    K_FIXO, MIN_CELULAS_PARA_ESTIMAR_K, MIN_N_JOGOS,
)


def contar_jogos(picks: Sequence) -> int:
    """`n_efetivo` da spec. Picks do mesmo jogo dividem o mesmo placar."""
    return len({p.match_id for p in picks})


def encolher(theta_proprio: Tuple[float, float],
             theta_pai: Tuple[float, float],
             n_efetivo: int, k: float) -> Tuple[float, float]:
    """peso = n/(n+k); theta = peso*proprio + (1-peso)*pai."""
    peso = n_efetivo / (n_efetivo + k) if (n_efetivo + k) > 0 else 0.0
    return (
        peso * theta_proprio[0] + (1.0 - peso) * theta_pai[0],
        peso * theta_proprio[1] + (1.0 - peso) * theta_pai[1],
    )


def estimar_k(celulas: Dict[Any, Sequence]) -> Tuple[float, bool]:
    """k = variancia dentro / variancia entre celulas. (k, caiu_no_fixo)."""
    acima = {ch: pk for ch, pk in celulas.items()
             if contar_jogos(pk) >= MIN_N_JOGOS}
    if len(acima) < MIN_CELULAS_PARA_ESTIMAR_K:
        return (float(K_FIXO), True)

    ajustes, ns = [], []
    for pk in acima.values():
        est = ajustar(pk)
        if est is not None:
            ajustes.append(est[0])          # variancia medida sobre `a`
            ns.append(contar_jogos(pk))
    if len(ajustes) < MIN_CELULAS_PARA_ESTIMAR_K:
        return (float(K_FIXO), True)

    media = sum(ajustes) / len(ajustes)
    var_entre = sum((x - media) ** 2 for x in ajustes) / (len(ajustes) - 1)
    n_medio = sum(ns) / len(ns)
    # Variancia da estimativa de `a` cai com n; var_dentro ~ c/n_medio, e a
    # constante se cancela na razao. Aproximacao deliberada: o que importa e a
    # ordem de grandeza de k, e o piso duro de 20 jogos ja protege o resto.
    var_dentro = 1.0 / max(n_medio, 1.0)
    if var_entre <= 0:
        return (float(K_FIXO), True)
    k = var_dentro / var_entre * n_medio
    return (max(1.0, min(k, 500.0)), False)


def ajustar_hierarquico(picks: Sequence) -> Dict[Tuple[str, str], dict]:
    """Global -> familia -> liga, cada nivel encolhido para o pai."""
    por_familia: Dict[str, list] = defaultdict(list)
    por_celula: Dict[Tuple[str, str], list] = defaultdict(list)
    for p in picks:
        por_familia[p.familia].append(p)
        por_celula[(p.familia, p.liga)].append(p)

    k, caiu_no_fixo = estimar_k(por_celula)
    saida: Dict[Tuple[str, str], dict] = {}

    global_est = ajustar(picks) or (0.0, 1.0)
    saida[("", "")] = {"a": global_est[0], "b": global_est[1],
                       "n_jogos": contar_jogos(picks), "origem": "global",
                       "k_fixo": caiu_no_fixo}

    for familia, pk in por_familia.items():
        n = contar_jogos(pk)
        proprio = ajustar(pk) if n >= MIN_N_JOGOS else None
        theta = encolher(proprio, global_est, n, k) if proprio else global_est
        saida[(familia, "")] = {"a": theta[0], "b": theta[1], "n_jogos": n,
                                "origem": "familia" if proprio else "global",
                                "k_fixo": caiu_no_fixo}

    for (familia, liga), pk in por_celula.items():
        if not liga:
            continue
        pai = (saida[(familia, "")]["a"], saida[(familia, "")]["b"])
        n = contar_jogos(pk)
        proprio = ajustar(pk) if n >= MIN_N_JOGOS else None
        theta = encolher(proprio, pai, n, k) if proprio else pai
        saida[(familia, liga)] = {"a": theta[0], "b": theta[1], "n_jogos": n,
                                  "origem": "liga" if proprio else "familia",
                                  "k_fixo": caiu_no_fixo}
    return saida
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_05_encolhimento.py tests/calibragem/test_04_estimador_ajuste.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 14 testes.

- [ ] **Step 5: Rodar contra o ledger real e ler os números**

Run:
```bash
PYTHONPATH=. PYTHONIOENCODING=utf-8 python -c "
from dotenv import load_dotenv; load_dotenv('.env')
from backend.modeling.calibragem.repositorio import carregar_amostra
from backend.modeling.calibragem.estimador import ajustar_hierarquico
r = ajustar_hierarquico(carregar_amostra())
for ch in sorted(r, key=lambda c: -r[c]['n_jogos'])[:12]:
    v = r[ch]
    print(f'{str(ch):<34} a={v[\"a\"]:+.3f} b={v[\"b\"]:.3f} n={v[\"n_jogos\"]:>4} {v[\"origem\"]}')
"
```
Expected: `a` positivo na maioria das famílias — o motor publica abaixo da realidade, e o #244 mediu −10,2 pontos. `b` na vizinhança de 1. Célula de liga com `n < 20` tem de aparecer com `origem=familia`.

**Se `a` vier negativo em quase tudo, parar.** Ou o sinal está invertido em `curva.aplicar`, ou `carregar_amostra` trocou `raw_prob` por `calibrated_prob`.

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/calibragem/estimador.py tests/calibragem/test_05_encolhimento.py
git commit -m "feat: encolhimento hierarquico com n_efetivo em JOGOS (#248)

Global -> familia -> liga, cada nivel encolhido para o pai por n/(n+k).

O teste que importa: 40 picks de um jogo pesam exatamente como 2 picks do
mesmo jogo. Contar picks daria autonomia total a celula sobre 220 jogos de
informacao real — a mesma classe de erro do #196, #243 e #244."
```

---

## Task 6: Semente do backfill e `n_prior`

**Files:**
- Modify: `backend/modeling/calibragem/estimador.py`
- Modify: `backend/modeling/calibragem/repositorio.py`
- Create: `tests/calibragem/test_06_semente.py`

**Interfaces:**
- Consumes: `estimador.ajustar_hierarquico`, `estimador.encolher`.
- Produces:
  - `repositorio.carregar_semente_backfill(caminho: str) -> List[Pick]`
  - `estimador.medir_concordancia(semente, ledger) -> Tuple[float, int]` — `(concordancia, n_sobrepostos)`
  - `estimador.n_prior_da_concordancia(concordancia, n_sobrepostos) -> Tuple[int, str]` — `(n_prior, status)`
  - `estimador.aplicar_semente(ajuste_ledger, ajuste_semente, n_prior) -> Dict`

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_06_semente.py`:

```python
# -*- coding: utf-8 -*-
"""A semente do backfill entra como amostra, e o decaimento e a propria conta."""
import pytest

from backend.modeling.calibragem import (
    MIN_PICKS_PARA_VALIDAR_SEMENTE, N_PRIOR_NAO_VALIDADA, TETO_N_PRIOR,
)
from backend.modeling.calibragem.estimador import (
    aplicar_semente, medir_concordancia, n_prior_da_concordancia,
)
from backend.modeling.calibragem.repositorio import Pick


def _p(mid, raw):
    return Pick(mid, "Over/Under", "liga", raw, 1)


def test_concordancia_perfeita():
    a = [_p("m1", 0.60), _p("m2", 0.40)]
    b = [_p("m1", 0.60), _p("m2", 0.40)]
    c, n = medir_concordancia(a, b)
    assert n == 2 and c == pytest.approx(1.0)


def test_concordancia_conta_dentro_de_dois_pontos():
    a = [_p("m1", 0.60), _p("m2", 0.40)]
    b = [_p("m1", 0.615), _p("m2", 0.50)]      # o primeiro entra, o segundo nao
    c, n = medir_concordancia(a, b)
    assert n == 2 and c == pytest.approx(0.5)


def test_n_prior_escala_com_a_concordancia():
    assert n_prior_da_concordancia(1.0, 500)[0] == TETO_N_PRIOR
    assert n_prior_da_concordancia(0.5, 500)[0] == TETO_N_PRIOR // 2
    assert n_prior_da_concordancia(0.0, 500)[0] == 0


def test_sobreposicao_pequena_cai_no_valor_nao_validado():
    n, status = n_prior_da_concordancia(1.0, MIN_PICKS_PARA_VALIDAR_SEMENTE - 1)
    assert n == N_PRIOR_NAO_VALIDADA
    assert status == "semente_nao_validada"


def test_semente_domina_quando_o_ledger_e_pequeno():
    ledger = {("Over/Under", ""): {"a": 0.0, "b": 1.0, "n_jogos": 10, "origem": "familia", "k_fixo": True}}
    semente = {("Over/Under", ""): {"a": 1.0, "b": 1.0, "n_jogos": 8403, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Over/Under", "")]["a"] == pytest.approx(150 / 160, abs=0.001)


def test_ledger_domina_quando_cresce():
    """O decaimento e a propria aritmetica — nao ha segundo mecanismo."""
    ledger = {("Over/Under", ""): {"a": 0.0, "b": 1.0, "n_jogos": 3000, "origem": "familia", "k_fixo": False}}
    semente = {("Over/Under", ""): {"a": 1.0, "b": 1.0, "n_jogos": 8403, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Over/Under", "")]["a"] < 0.06


def test_celula_so_na_semente_sobrevive():
    ledger = {}
    semente = {("Cards", ""): {"a": 0.9, "b": 1.0, "n_jogos": 400, "origem": "semente", "k_fixo": True}}
    r = aplicar_semente(ledger, semente, n_prior=150)
    assert r[("Cards", "")]["a"] == pytest.approx(0.9)
    assert r[("Cards", "")]["origem"] == "semente"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_06_semente.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ImportError: cannot import name 'medir_concordancia'`

- [ ] **Step 3: Implementar a semente**

Append to `backend/modeling/calibragem/estimador.py`:

```python
from backend.modeling.calibragem import (
    MIN_PICKS_PARA_VALIDAR_SEMENTE, N_PRIOR_NAO_VALIDADA, TETO_N_PRIOR,
    TOLERANCIA_CONCORDANCIA,
)


def medir_concordancia(semente: Sequence, ledger: Sequence) -> Tuple[float, int]:
    """Fracao dos picks sobrepostos em que as duas fontes ficam a < 2 pontos.

    Sobreposicao e por (match_id, familia, liga, p_raw arredondado ao pick):
    usamos (match_id, familia, liga) porque o Pick nao carrega a selecao — o
    par e formado na ordem em que aparece dentro da chave.
    """
    from collections import defaultdict
    idx = defaultdict(list)
    for p in ledger:
        idx[(p.match_id, p.familia, p.liga)].append(p.p_raw)

    total = concordantes = 0
    for p in semente:
        candidatos = idx.get((p.match_id, p.familia, p.liga))
        if not candidatos:
            continue
        total += 1
        if min(abs(p.p_raw - q) for q in candidatos) < TOLERANCIA_CONCORDANCIA:
            concordantes += 1
    if total == 0:
        return (0.0, 0)
    return (concordantes / total, total)


def n_prior_da_concordancia(concordancia: float, n_sobrepostos: int) -> Tuple[int, str]:
    """(n_prior, status). Nada bloqueia: a semente entra de qualquer forma."""
    if n_sobrepostos < MIN_PICKS_PARA_VALIDAR_SEMENTE:
        return (N_PRIOR_NAO_VALIDADA, "semente_nao_validada")
    n = int(round(TETO_N_PRIOR * max(0.0, min(1.0, concordancia))))
    return (n, "semente_validada")


def aplicar_semente(ajuste_ledger: Dict[Tuple[str, str], dict],
                    ajuste_semente: Dict[Tuple[str, str], dict],
                    n_prior: int) -> Dict[Tuple[str, str], dict]:
    """theta = (n_ledger*ledger + n_prior*semente) / (n_ledger + n_prior)."""
    saida: Dict[Tuple[str, str], dict] = {}
    for chave in set(ajuste_ledger) | set(ajuste_semente):
        no_ledger = ajuste_ledger.get(chave)
        na_semente = ajuste_semente.get(chave)
        if no_ledger is None:
            saida[chave] = dict(na_semente, origem="semente")
            continue
        if na_semente is None or n_prior <= 0:
            saida[chave] = dict(no_ledger)
            continue
        n_l = no_ledger["n_jogos"]
        peso = n_l / (n_l + n_prior)
        saida[chave] = dict(
            no_ledger,
            a=peso * no_ledger["a"] + (1 - peso) * na_semente["a"],
            b=peso * no_ledger["b"] + (1 - peso) * na_semente["b"],
            origem=f"{no_ledger['origem']}+semente",
        )
    return saida
```

- [ ] **Step 4: Adicionar o leitor da semente ao repositório**

Append to `backend/modeling/calibragem/repositorio.py`:

```python
def carregar_semente_backfill(caminho: str) -> List[Pick]:
    """Le o artefato do backfill (#227) e devolve Picks no mesmo formato.

    O arquivo e um JSON com uma lista de picks reconstruidos. Ausente ou
    ilegivel devolve lista vazia — a semente e opcional por desenho, e o
    ciclo continua sem ela.
    """
    import json
    if not os.path.exists(caminho):
        logger.info("[calibragem] semente ausente em %s", caminho)
        return []
    try:
        dados = json.loads(open(caminho, encoding="utf-8").read())
    except Exception as e:                                   # noqa: BLE001
        logger.warning("[calibragem] semente ilegivel: %s", e)
        return []

    saida: List[Pick] = []
    for d in dados:
        rotulo = f"{d.get('market', '')} {d.get('selection', '')}".strip()
        try:
            familia = familia_do_mercado(rotulo)
        except ValueError:
            continue
        raw, y = d.get("raw_prob"), d.get("outcome")
        if raw is None or y is None:
            continue
        saida.append(Pick(d.get("match_id", ""), familia,
                          d.get("league_id") or "", float(raw),
                          int(bool(int(y)))))
    return saida
```

- [ ] **Step 5: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_06_semente.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 7 testes.

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/calibragem/ tests/calibragem/test_06_semente.py
git commit -m "feat: semente do backfill com n_prior medido pela concordancia (#248)

n_prior = 150 * concordancia, teto 150. Menos de 30 picks sobrepostos cai em
75 e sai marcado como semente_nao_validada. O backfill tem 8.403 jogos mas
entra valendo no maximo 150 — e uma reconstrucao, e o que ele reconstroi
nunca foi publicado a ninguem.

O decaimento e a propria aritmetica da media ponderada: nao ha segundo
mecanismo a manter em dia."
```

---

## Task 7: `governanca.py` — trava, piso e `b > 0`

**Files:**
- Create: `backend/modeling/calibragem/governanca.py`
- Create: `tests/calibragem/test_07_trava.py`

**Interfaces:**
- Consumes: `curva.distancia_maxima`.
- Produces: `governanca.avaliar_proposta(proposta: dict, vigente: dict, n_jogos: int) -> dict` — devolve `{"a", "b", "status", "fator_encurtamento", "motivo"}` com `status` em `adotada | encurtada | rejeitada | abaixo_do_piso | inalterada`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_07_trava.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 4 da spec — a trava encurta a proposta, nunca a rejeita."""
import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.curva import distancia_maxima
from backend.modeling.calibragem.governanca import avaliar_proposta

VIGENTE = {"a": 0.0, "b": 1.0}


def test_proposta_perto_e_adotada_inteira():
    r = avaliar_proposta({"a": 0.01, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "adotada"
    assert r["a"] == pytest.approx(0.01)
    assert r["fator_encurtamento"] is None


def test_proposta_longe_e_encurtada_ate_caber():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "encurtada"
    d = distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"])
    assert d <= PASSO_MAXIMO_PP + 1e-6, d
    assert 0.0 < r["fator_encurtamento"] < 1.0


def test_encurtamento_anda_na_direcao_da_proposta():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert 0.0 < r["a"] < 2.0


def test_abaixo_do_piso_nao_muda_nada():
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=MIN_N_JOGOS - 1)
    assert r["status"] == "abaixo_do_piso"
    assert (r["a"], r["b"]) == (VIGENTE["a"], VIGENTE["b"])


def test_b_nao_positivo_e_rejeitado():
    r = avaliar_proposta({"a": 0.01, "b": 0.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "rejeitada"
    assert "b" in r["motivo"]
    assert (r["a"], r["b"]) == (VIGENTE["a"], VIGENTE["b"])
    r2 = avaliar_proposta({"a": 0.01, "b": -0.5}, VIGENTE, n_jogos=100)
    assert r2["status"] == "rejeitada"


def test_proposta_identica_sai_como_inalterada():
    r = avaliar_proposta({"a": 0.0, "b": 1.0}, VIGENTE, n_jogos=100)
    assert r["status"] == "inalterada"


def test_limite_reduzido_aperta_a_trava():
    """Apos uma reversao o limite da celula cai pela metade (Task 8)."""
    r = avaliar_proposta({"a": 2.0, "b": 1.0}, VIGENTE, n_jogos=100,
                         limite=PASSO_MAXIMO_PP / 2)
    d = distancia_maxima(VIGENTE["a"], VIGENTE["b"], r["a"], r["b"])
    assert d <= PASSO_MAXIMO_PP / 2 + 1e-6
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_07_trava.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.governanca'`

- [ ] **Step 3: Implementar a governança**

Create `backend/modeling/calibragem/governanca.py`:

```python
# -*- coding: utf-8 -*-
"""Politica: quem PODE mudar, e quanto. Sem ajuste e sem I/O.

A trava e expressa em pontos de PROBABILIDADE, nao em `a` e `b`. Limitar os
parametros separadamente e dificil de raciocinar: o mesmo delta em `a` move
pouco no meio da escala e muito nas pontas.
"""
import logging
from typing import Optional

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.curva import distancia_maxima

logger = logging.getLogger("sportsbankzu.calibragem.governanca")

_ITER_BUSCA = 40


def avaliar_proposta(proposta: dict, vigente: dict, n_jogos: int,
                     limite: Optional[float] = None) -> dict:
    """Decide o que de fato passa a valer. Nunca levanta."""
    limite = PASSO_MAXIMO_PP if limite is None else limite
    a_v, b_v = float(vigente["a"]), float(vigente["b"])
    a_p, b_p = float(proposta["a"]), float(proposta["b"])

    def _mantem(status: str, motivo: str) -> dict:
        return {"a": a_v, "b": b_v, "status": status,
                "fator_encurtamento": None, "motivo": motivo}

    if n_jogos < MIN_N_JOGOS:
        return _mantem("abaixo_do_piso",
                       f"n_jogos={n_jogos} < {MIN_N_JOGOS} (#079)")

    if b_p <= 0:
        # b <= 0 inverteria a ordem das probabilidades, e a regra do corredor
        # (#246-a) decide por ordem — a correcao mudaria o corredor por efeito
        # colateral, sem ninguem decidir.
        return _mantem("rejeitada", f"b={b_p:.4f} nao positivo; ordem inverteria")

    if (a_p, b_p) == (a_v, b_v):
        return _mantem("inalterada", "proposta identica a vigente")

    if distancia_maxima(a_v, b_v, a_p, b_p) <= limite:
        return {"a": a_p, "b": b_p, "status": "adotada",
                "fator_encurtamento": None, "motivo": ""}

    # Encurta ao longo do segmento vigente->proposta. A distancia cresce de
    # forma monotona com t, entao bisseccao acha o maior t que cabe.
    baixo, alto = 0.0, 1.0
    for _ in range(_ITER_BUSCA):
        meio = (baixo + alto) / 2.0
        a_m = a_v + meio * (a_p - a_v)
        b_m = b_v + meio * (b_p - b_v)
        if distancia_maxima(a_v, b_v, a_m, b_m) <= limite:
            baixo = meio
        else:
            alto = meio
    a_f = a_v + baixo * (a_p - a_v)
    b_f = b_v + baixo * (b_p - b_v)
    return {"a": a_f, "b": b_f, "status": "encurtada",
            "fator_encurtamento": baixo,
            "motivo": f"passo limitado a {limite:.4f} de probabilidade"}
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_07_trava.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 7 testes.

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/calibragem/governanca.py tests/calibragem/test_07_trava.py
git commit -m "feat: trava de passo em pontos de probabilidade, piso e guarda de b (#248)

A trava e definida na SAIDA (max |curva_nova(p) - curva_vigente(p)| <= 0,02),
nao nos parametros: o mesmo delta em `a` move pouco no meio e muito nas
pontas. Proposta que ultrapassa e ENCURTADA por bisseccao, nunca rejeitada, e
o fator fica gravado.

b <= 0 e rejeitado: inverteria a ordem das probabilidades e mudaria o filtro
de corredor (#246-a) por efeito colateral."
```

---

## Task 8: Reversão fora da amostra e anti-oscilação

**Files:**
- Modify: `backend/modeling/calibragem/governanca.py`
- Create: `tests/calibragem/test_08_reversao.py`

**Interfaces:**
- Consumes: `curva.aplicar`.
- Produces:
  - `governanca.brier(pares: Sequence[Tuple[float, int]]) -> Optional[float]`
  - `governanca.avaliar_reversao(picks_servidos, vigente, anterior, reversoes_seguidas) -> dict` — devolve `{"acao", "motivo", "limite_proximo"}` com `acao` em `manter | reverter | congelar`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_08_reversao.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 5 da spec — reversao fora da amostra, e o anti-oscilacao.

Os jogos que uma versao avalia sao OS QUE ELA SERVIU: adotada no ciclo t,
publica; os jogos liquidados ate t+1 nunca fizeram parte do ajuste dela.
"""
import pytest

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.governanca import avaliar_reversao, brier
from backend.modeling.calibragem.repositorio import Pick

BOA = {"a": 0.45, "b": 1.0}      # sobe a probabilidade
RUIM = {"a": -0.90, "b": 1.0}    # derruba


def _servidos(n=60, p_raw=0.60, y=1):
    return [Pick(f"j{i}", "Over/Under", "l", p_raw, y if i % 4 else 0)
            for i in range(n)]


def test_brier_de_previsao_perfeita_e_zero():
    assert brier([(1.0, 1), (0.0, 0)]) == pytest.approx(0.0)


def test_brier_vazio_devolve_none():
    assert brier([]) is None


def test_vigente_melhor_mantem():
    r = avaliar_reversao(_servidos(), vigente=BOA, anterior=RUIM,
                         reversoes_seguidas=0)
    assert r["acao"] == "manter"


def test_vigente_pior_reverte():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=0)
    assert r["acao"] == "reverter"


def test_reversao_aperta_o_limite_do_proximo_ciclo():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=0)
    assert r["limite_proximo"] == pytest.approx(PASSO_MAXIMO_PP / 2)


def test_segunda_reversao_seguida_congela():
    r = avaliar_reversao(_servidos(), vigente=RUIM, anterior=BOA,
                         reversoes_seguidas=1)
    assert r["acao"] == "congelar"
    assert "revisao humana" in r["motivo"]


def test_janela_curta_nao_reverte():
    """Sem 20 jogos na janela, nao ha o que concluir (#079)."""
    r = avaliar_reversao(_servidos(n=MIN_N_JOGOS - 1), vigente=RUIM,
                         anterior=BOA, reversoes_seguidas=0)
    assert r["acao"] == "manter"
    assert "janela" in r["motivo"]


def test_conta_jogos_nao_picks_na_janela():
    """40 picks de UM jogo nao formam janela."""
    picks = [Pick("jogo1", "Over/Under", "l", 0.6, 1) for _ in range(40)]
    r = avaliar_reversao(picks, vigente=RUIM, anterior=BOA, reversoes_seguidas=0)
    assert r["acao"] == "manter"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_08_reversao.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ImportError: cannot import name 'avaliar_reversao'`

- [ ] **Step 3: Implementar a reversão**

Append to `backend/modeling/calibragem/governanca.py`:

```python
from typing import Sequence, Tuple

from backend.modeling.calibragem.curva import aplicar


def brier(pares: Sequence[Tuple[float, int]]):
    """Media de (p - y)^2. None se vazio."""
    if not pares:
        return None
    return sum((p - y) ** 2 for p, y in pares) / len(pares)


def avaliar_reversao(picks_servidos: Sequence, vigente: dict, anterior: dict,
                     reversoes_seguidas: int) -> dict:
    """Compara, NOS JOGOS QUE A VIGENTE SERVIU, vigente contra anterior.

    Reverte pelo PONTO, sem esperar o IC excluir zero. A assimetria justifica:
    reversao falsa volta para uma versao ja validada e custa quase nada;
    reversao que nao acontece deixa uma versao ruim publicando mais um ciclo.
    """
    n_jogos = len({p.match_id for p in picks_servidos})
    if n_jogos < MIN_N_JOGOS:
        return {"acao": "manter",
                "motivo": f"janela com {n_jogos} jogos < {MIN_N_JOGOS}",
                "limite_proximo": PASSO_MAXIMO_PP}

    b_vig = brier([(aplicar(p.p_raw, vigente["a"], vigente["b"]), p.y)
                   for p in picks_servidos])
    b_ant = brier([(aplicar(p.p_raw, anterior["a"], anterior["b"]), p.y)
                   for p in picks_servidos])
    if b_vig is None or b_ant is None or b_vig <= b_ant:
        return {"acao": "manter",
                "motivo": f"brier vigente {b_vig:.5f} <= anterior {b_ant:.5f}"
                          if b_vig is not None and b_ant is not None else "sem brier",
                "limite_proximo": PASSO_MAXIMO_PP}

    if reversoes_seguidas >= 1:
        logger.error(
            "[calibragem] celula CONGELADA apos 2 reversoes seguidas: "
            "brier vigente %.5f > anterior %.5f em %d jogos",
            b_vig, b_ant, n_jogos,
        )
        return {"acao": "congelar",
                "motivo": "duas reversoes seguidas; enviado para revisao humana",
                "limite_proximo": 0.0}

    return {"acao": "reverter",
            "motivo": f"brier vigente {b_vig:.5f} > anterior {b_ant:.5f} "
                      f"em {n_jogos} jogos",
            "limite_proximo": PASSO_MAXIMO_PP / 2}
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/ -q -p no:cacheprovider -o addopts=""`
Expected: PASS, todos os arquivos de `tests/calibragem/`.

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/calibragem/governanca.py tests/calibragem/test_08_reversao.py
git commit -m "feat: reversao fora da amostra e anti-oscilacao (#248)

Os jogos que uma versao avalia sao os que ela serviu — fora da amostra por
construcao, sem infraestrutura extra: o ledger ja grava o que foi publicado.
E a disciplina do pre-registro do #230-a aplicada por ciclo.

Reverte pelo ponto com >= 20 JOGOS na janela (nao picks). Apos uma reversao o
limite de passo da celula cai pela metade; duas seguidas congelam a celula e
emitem ERROR para revisao humana."
```

---

## Task 9: Escrita das versões e a auditoria por célula

**Files:**
- Modify: `backend/modeling/calibragem/repositorio.py`
- Create: `tests/calibragem/test_09_auditoria.py`

**Interfaces:**
- Consumes: a tabela `calibragem_versoes` da Task 3.
- Produces:
  - `repositorio.carregar_vigentes() -> Dict[Tuple[str, str], dict]` — `{(familia, liga): {"versao", "a", "b"}}`
  - `repositorio.carregar_parametros_para_curva() -> Dict[Tuple[str, str], Tuple[int, float, float]]`
  - `repositorio.gravar_ciclo(linhas: List[dict]) -> int`
  - `repositorio.contar_reversoes_seguidas(familia, liga) -> int`

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_09_auditoria.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 8 da spec — nada acontece em silencio.

O #247 achou um gate (odds_value_added < -0,015) que NUNCA disparou em 33
ligas e ninguem sabia. O #246 so encontrou o filtro de corredor porque
[CORRIDOR-DROPPED] vazou no log de um teste. Um sistema que muda o numero
sozinho e so registra quando muda e um sistema onde a inacao e invisivel.
"""
import pytest

from backend.modeling.calibragem.repositorio import montar_linha_auditoria

CELULAS = [("Over/Under", ""), ("Corners", ""), ("Corners", "mls"),
           ("Cards", ""), ("BTTS", ""), ("1X2", ""), ("Double Chance", "")]


def test_toda_celula_gera_linha_qualquer_que_seja_o_status():
    linhas = [
        montar_linha_auditoria(f, l, versao=3, resultado={
            "a": 0.1, "b": 1.0, "status": st, "fator_encurtamento": None,
            "motivo": "",
        }, n_jogos=50, origem="familia", brier=None)
        for (f, l), st in zip(CELULAS, [
            "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
            "inalterada", "revertida", "congelada"])
    ]
    assert len(linhas) == len(CELULAS)
    assert {ln["status"] for ln in linhas} == {
        "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
        "inalterada", "revertida", "congelada"}


def test_linha_inalterada_tambem_carrega_os_parametros():
    ln = montar_linha_auditoria("BTTS", "", versao=7, resultado={
        "a": 0.2, "b": 0.95, "status": "inalterada",
        "fator_encurtamento": None, "motivo": "proposta identica",
    }, n_jogos=31, origem="familia", brier=0.2134)
    assert ln["a"] == 0.2 and ln["b"] == 0.95
    assert ln["n_jogos"] == 31 and ln["brier_validacao"] == 0.2134
    assert ln["motivo"] == "proposta identica"


def test_encurtada_grava_o_fator():
    ln = montar_linha_auditoria("Corners", "", versao=2, resultado={
        "a": 0.05, "b": 1.0, "status": "encurtada",
        "fator_encurtamento": 0.31, "motivo": "passo limitado",
    }, n_jogos=220, origem="familia", brier=None)
    assert ln["fator_encurtamento"] == 0.31


def test_status_desconhecido_levanta():
    with pytest.raises(ValueError, match="status"):
        montar_linha_auditoria("BTTS", "", versao=1, resultado={
            "a": 0.0, "b": 1.0, "status": "mais_ou_menos",
            "fator_encurtamento": None, "motivo": "",
        }, n_jogos=50, origem="familia", brier=None)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_09_auditoria.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ImportError: cannot import name 'montar_linha_auditoria'`

- [ ] **Step 3: Implementar escrita e auditoria**

Append to `backend/modeling/calibragem/repositorio.py`:

```python
from backend.modeling.calibragem import VERSAO_LEGADO

STATUS_VALIDOS = {
    "vigente", "adotada", "encurtada", "rejeitada", "abaixo_do_piso",
    "inalterada", "revertida", "congelada",
}


def montar_linha_auditoria(familia: str, liga: str, versao: int,
                           resultado: dict, n_jogos: int, origem: str,
                           brier) -> Dict[str, Any]:
    """Uma linha por celula, em TODO ciclo — inclusive quando nada mudou."""
    status = resultado["status"]
    if status not in STATUS_VALIDOS:
        raise ValueError(f"status desconhecido: {status!r}")
    return {
        "familia": familia, "liga": liga, "versao": versao,
        "a": resultado["a"], "b": resultado["b"],
        "n_jogos": n_jogos, "brier_validacao": brier, "origem": origem,
        "status": status,
        "fator_encurtamento": resultado.get("fator_encurtamento"),
        "motivo": resultado.get("motivo", ""),
    }


def gravar_ciclo(linhas: List[Dict[str, Any]]) -> int:
    """Grava as linhas do ciclo e promove as adotadas a `vigente`."""
    if not linhas:
        return 0
    sql = """
        INSERT INTO calibragem_versoes
            (familia, liga, versao, a, b, n_jogos, brier_validacao,
             origem, status, fator_encurtamento, motivo)
        VALUES (%(familia)s, %(liga)s, %(versao)s, %(a)s, %(b)s, %(n_jogos)s,
                %(brier_validacao)s, %(origem)s, %(status)s,
                %(fator_encurtamento)s, %(motivo)s)
    """
    promove = """
        UPDATE calibragem_versoes SET status = 'substituida'
         WHERE familia = %s AND liga = %s AND status = 'vigente'
    """
    with _conn() as c, c.cursor() as cur:
        for ln in linhas:
            if ln["status"] in ("adotada", "encurtada"):
                cur.execute(promove, (ln["familia"], ln["liga"]))
                cur.execute(sql, dict(ln, status="vigente"))
                cur.execute(sql, ln)
            else:
                cur.execute(sql, ln)
    logger.info("[calibragem] ciclo gravou %d linhas de auditoria", len(linhas))
    return len(linhas)


def carregar_vigentes() -> Dict[tuple, Dict[str, Any]]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT familia, liga, versao, a, b FROM calibragem_versoes
             WHERE status = 'vigente'
        """)
        return {(r[0], r[1]): {"versao": r[2], "a": float(r[3]), "b": float(r[4])}
                for r in cur.fetchall()}


def carregar_parametros_para_curva() -> Dict[tuple, tuple]:
    """Formato que `curva.aplicar_versao` consome."""
    return {ch: (v["versao"], v["a"], v["b"])
            for ch, v in carregar_vigentes().items()}


def contar_reversoes_seguidas(familia: str, liga: str) -> int:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT status FROM calibragem_versoes
             WHERE familia = %s AND liga = %s
               AND status IN ('revertida', 'adotada', 'encurtada')
             ORDER BY id DESC LIMIT 5
        """, (familia, liga))
        seguidas = 0
        for (st,) in cur.fetchall():
            if st == "revertida":
                seguidas += 1
            else:
                break
        return seguidas
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_09_auditoria.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 4 testes.

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/calibragem/repositorio.py tests/calibragem/test_09_auditoria.py
git commit -m "feat: escrita de versoes e auditoria por celula (#248)

Uma linha por celula em TODO ciclo, inclusive `inalterada`. Status
desconhecido LEVANTA em vez de virar linha muda.

O #247 achou um gate que nunca disparou em 33 ligas sem ninguem saber; o #246
so encontrou o filtro de corredor porque um log vazou num teste. Inacao
invisivel e o modo de falha que este projeto ja teve duas vezes."
```

---

## Task 10: Re-derivação dos limiares (volume constante)

**Files:**
- Create: `backend/modeling/calibragem/limiares.py`
- Create: `tests/calibragem/test_10_limiares.py`

**Interfaces:**
- Consumes: `curva.aplicar`.
- Produces: `limiares.rederivar(picks_com_odd, parametros_antigos, parametros_novos, limiares_atuais) -> Dict[str, dict]` — por família, os quatro valores `safe_ev`, `neutro_ev`, `safe_edge`, `neutro_edge` que preservam a contagem por classe.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_10_limiares.py`:

```python
# -*- coding: utf-8 -*-
"""Teste 6 da spec — o volume publicado fica constante.

A classificacao usa prob RAW (proibicao 11), entao `safe_prob` e `neutro_prob`
nao se movem. O volume sobe por `ev` e `edge`, que consomem a corrigida:
medido, os picks de EV positivo vao de 13,8% para 25,2% (1,8x).
"""
import pytest

from backend.modeling.calibragem.limiares import contar_por_classe, rederivar


class P:
    def __init__(self, familia, p_raw, odd):
        self.familia, self.p_raw, self.odd = familia, p_raw, odd


ATUAIS = {"Over/Under": {"safe_ev": 0.06, "neutro_ev": 0.00,
                         "safe_edge": 0.05, "neutro_edge": 0.02}}
ANTIGO = {"Over/Under": {"a": 0.0, "b": 1.0}}
NOVO = {"Over/Under": {"a": 0.45, "b": 1.0}}     # sobe ~10 pontos


def _amostra(n=400):
    return [P("Over/Under", 0.30 + (i % 60) / 100.0, 1.70 + (i % 9) / 10.0)
            for i in range(n)]


def test_sem_rederivacao_o_volume_sobe():
    picks = _amostra()
    antes = contar_por_classe(picks, ANTIGO, ATUAIS)
    depois = contar_por_classe(picks, NOVO, ATUAIS)
    assert depois["Over/Under"]["neutro"] > antes["Over/Under"]["neutro"]


def test_rederivacao_devolve_o_volume_ao_que_era():
    picks = _amostra()
    antes = contar_por_classe(picks, ANTIGO, ATUAIS)
    novos = rederivar(picks, ANTIGO, NOVO, ATUAIS)
    depois = contar_por_classe(picks, NOVO, novos)
    for classe in ("safe", "neutro"):
        assert abs(depois["Over/Under"][classe] - antes["Over/Under"][classe]) <= 2, \
            (classe, antes, depois)


def test_familia_sem_odd_nao_move_limiar():
    """Cartoes tem 88,3% das linhas sem odd — nao ha volume a manter."""
    picks = [P("Cards", 0.60, None) for _ in range(50)]
    atuais = {"Cards": {"safe_ev": 0.06, "neutro_ev": 0.0,
                        "safe_edge": 0.05, "neutro_edge": 0.02}}
    novos = rederivar(picks, {"Cards": {"a": 0.0, "b": 1.0}},
                      {"Cards": {"a": 0.5, "b": 1.0}}, atuais)
    assert novos["Cards"] == atuais["Cards"]


def test_familia_ausente_da_amostra_e_preservada():
    novos = rederivar([], ANTIGO, NOVO, ATUAIS)
    assert novos["Over/Under"] == ATUAIS["Over/Under"]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_10_limiares.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.limiares'`

- [ ] **Step 3: Implementar a re-derivação**

Create `backend/modeling/calibragem/limiares.py`:

```python
# -*- coding: utf-8 -*-
"""Re-derivacao dos limiares de EV e edge, mantendo o volume constante.

A classificacao usa prob RAW (proibicao 11 do CLAUDE.md), entao `safe_prob` e
`neutro_prob` NAO se movem — o raw nao mudou. O volume sobe por `ev` e `edge`,
que consomem a probabilidade corrigida.

Curva e limiar mudam juntos, na mesma versao e na mesma linha de auditoria:
separa-los recria a convivencia de dois regimes que o #244 mediu.
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from backend.modeling.calibragem.curva import aplicar

logger = logging.getLogger("sportsbankzu.calibragem.limiares")

CAMPOS = ("safe_ev", "neutro_ev", "safe_edge", "neutro_edge")


def _ev_e_edge(p_corr: float, odd) -> tuple:
    if not odd or float(odd) <= 1.0:
        return (None, None)
    odd = float(odd)
    return (p_corr * odd - 1.0, p_corr - 1.0 / odd)


def contar_por_classe(picks: Sequence, parametros: Dict[str, dict],
                      limiares: Dict[str, dict]) -> Dict[str, Dict[str, int]]:
    """Quantos picks caem em cada classe, por familia."""
    saida: Dict[str, Dict[str, int]] = defaultdict(lambda: {"safe": 0, "neutro": 0})
    for pk in picks:
        par = parametros.get(pk.familia)
        lim = limiares.get(pk.familia)
        if not par or not lim:
            continue
        ev, edge = _ev_e_edge(aplicar(pk.p_raw, par["a"], par["b"]), pk.odd)
        if ev is None:
            continue
        if ev >= lim["safe_ev"] and edge >= lim["safe_edge"]:
            saida[pk.familia]["safe"] += 1
        elif ev >= lim["neutro_ev"] and edge >= lim["neutro_edge"]:
            saida[pk.familia]["neutro"] += 1
    return saida


def _quantil_que_preserva(valores: List[float], quantos: int):
    """O corte que deixa exatamente `quantos` valores acima ou iguais."""
    if quantos <= 0:
        return None
    ordenados = sorted(valores, reverse=True)
    if quantos >= len(ordenados):
        return ordenados[-1] if ordenados else None
    return ordenados[quantos - 1]


def rederivar(picks: Sequence, parametros_antigos: Dict[str, dict],
              parametros_novos: Dict[str, dict],
              limiares_atuais: Dict[str, dict]) -> Dict[str, dict]:
    """Os quatro valores por familia que reproduzem a contagem anterior."""
    alvo = contar_por_classe(picks, parametros_antigos, limiares_atuais)
    por_familia: Dict[str, list] = defaultdict(list)
    for pk in picks:
        por_familia[pk.familia].append(pk)

    saida: Dict[str, dict] = {}
    for familia, atual in limiares_atuais.items():
        pk_familia = por_familia.get(familia) or []
        par = parametros_novos.get(familia)
        if not par:
            saida[familia] = dict(atual)
            continue

        evs, edges = [], []
        for pk in pk_familia:
            ev, edge = _ev_e_edge(aplicar(pk.p_raw, par["a"], par["b"]), pk.odd)
            if ev is not None:
                evs.append(ev)
                edges.append(edge)

        if not evs:
            # Familia sem preco em quase nenhuma linha (cartoes: 88,3%). Nao ha
            # volume a manter constante — registra e nao mexe.
            logger.info("[calibragem] %s sem picks com odd; limiares inalterados",
                        familia)
            saida[familia] = dict(atual)
            continue

        n_safe = alvo.get(familia, {}).get("safe", 0)
        n_ate_neutro = n_safe + alvo.get(familia, {}).get("neutro", 0)
        novo = dict(atual)
        for campo, valores, quantos in (
            ("safe_ev", evs, n_safe), ("safe_edge", edges, n_safe),
            ("neutro_ev", evs, n_ate_neutro), ("neutro_edge", edges, n_ate_neutro),
        ):
            corte = _quantil_que_preserva(valores, quantos)
            if corte is not None:
                novo[campo] = round(corte, 4)
        saida[familia] = novo
    return saida
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest tests/calibragem/test_10_limiares.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 4 testes.

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/calibragem/limiares.py tests/calibragem/test_10_limiares.py
git commit -m "feat: re-derivacao dos limiares mantendo o volume constante (#248)

safe_prob e neutro_prob nao se movem (proibicao 11: classificacao usa raw). O
volume sobe por ev e edge — medido, EV positivo iria de 13,8% para 25,2%.

Casamento de quantil: os quatro valores que reproduzem a contagem por classe
anterior. Familia sem preco (cartoes, 88,3% sem odd) registra e nao mexe, em
vez de fingir que calculou."
```

---

## Task 11: O ciclo, o cache e o fallback marcado

**Files:**
- Create: `backend/modeling/calibragem/ciclo.py`
- Create: `tests/calibragem/test_11_ciclo.py`
- Modify: `backend/services/ev_classification.py` (passar `parametros` a `aplicar_versao`)
- Modify: `backend/cron_handler.py` (chamar o ciclo)

**Interfaces:**
- Consumes: todos os módulos anteriores.
- Produces:
  - `ciclo.executar(caminho_semente: Optional[str] = None) -> dict` — resumo `{"celulas", "adotadas", "encurtadas", "revertidas", "congeladas", "jogos"}`
  - `ciclo.parametros_vigentes() -> Tuple[Dict, str]` — `(parametros, procedencia)` com `procedencia` em `banco | snapshot | legado`

- [ ] **Step 1: Escrever os testes (vão falhar)**

Create `tests/calibragem/test_11_ciclo.py`:

```python
# -*- coding: utf-8 -*-
"""O ciclo e o fallback. Banco fora do ar NAO pode virar identidade."""
import pytest

from backend.modeling.calibragem import ciclo


def test_banco_fora_cai_no_legado_e_marca(monkeypatch):
    def explode():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {})
    parametros, procedencia = ciclo.parametros_vigentes()
    assert parametros == {}
    assert procedencia == "legado"


def test_banco_fora_usa_o_snapshot_quando_existe(monkeypatch):
    def explode():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {("Corners", ""): (3, 0.4, 1.0)})
    parametros, procedencia = ciclo.parametros_vigentes()
    assert parametros == {("Corners", ""): (3, 0.4, 1.0)}
    assert procedencia == "snapshot"


def test_nunca_devolve_identidade_por_falha(monkeypatch):
    """a=0,b=1 publicaria o raw de uma vez por causa de rede."""
    def explode():
        raise RuntimeError("timeout")
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", explode)
    monkeypatch.setattr(ciclo, "_SNAPSHOT", {})
    parametros, _ = ciclo.parametros_vigentes()
    assert all(v[1:] != (0.0, 1.0) for v in parametros.values())


def test_cache_evita_segunda_ida_ao_banco(monkeypatch):
    chamadas = {"n": 0}

    def conta():
        chamadas["n"] += 1
        return {("Corners", ""): (2, 0.3, 1.0)}
    monkeypatch.setattr(ciclo.repositorio, "carregar_parametros_para_curva", conta)
    ciclo.limpar_cache()
    ciclo.parametros_vigentes()
    ciclo.parametros_vigentes()
    assert chamadas["n"] == 1
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `python -m pytest tests/calibragem/test_11_ciclo.py -q -p no:cacheprovider -o addopts=""`
Expected: FAIL com `ModuleNotFoundError: No module named 'backend.modeling.calibragem.ciclo'`

- [ ] **Step 3: Implementar o ciclo**

Create `backend/modeling/calibragem/ciclo.py`:

```python
# -*- coding: utf-8 -*-
"""Orquestracao: carrega -> ajusta -> governa -> grava.

Serving: `parametros_vigentes()` com cache por TTL, no padrao do #231-a. Banco
fora do ar NUNCA vira identidade — publicar `raw` de repente seria mudar todo
numero de uma vez por causa de rede. Cai no snapshot empacotado; sem snapshot,
cai no legado (versao 0), e a procedencia sai marcada.
"""
import logging
import os
import time
from typing import Dict, Optional, Tuple

from backend.modeling.calibragem import (
    MIN_N_JOGOS, PASSO_MAXIMO_PP, VERSAO_LEGADO,
)
from backend.modeling.calibragem import estimador, governanca, limiares, repositorio

logger = logging.getLogger("sportsbankzu.calibragem.ciclo")

# Snapshot empacotado no deploy. Preenchido por `scripts/snapshot_calibragem.py`
# quando houver versoes vigentes; vazio significa "tudo na versao 0".
_SNAPSHOT: Dict[tuple, tuple] = {}

_CACHE: Dict[str, object] = {"parametros": None, "procedencia": None, "t": 0.0}


def _ttl() -> float:
    return float(os.getenv("CALIBRAGEM_TTL_S", "300"))


def limpar_cache() -> None:
    _CACHE.update({"parametros": None, "procedencia": None, "t": 0.0})


def parametros_vigentes() -> Tuple[Dict[tuple, tuple], str]:
    agora = time.time()
    ttl = _ttl()
    if _CACHE["parametros"] is not None and ttl > 0 and agora - _CACHE["t"] < ttl:
        return _CACHE["parametros"], _CACHE["procedencia"]
    try:
        parametros = repositorio.carregar_parametros_para_curva()
        procedencia = "banco"
    except Exception as e:                                   # noqa: BLE001
        if _SNAPSHOT:
            parametros, procedencia = dict(_SNAPSHOT), "snapshot"
        else:
            parametros, procedencia = {}, "legado"
        logger.error(
            "[calibragem] parametros do banco indisponiveis (%s); servindo de "
            "'%s' — o painel NAO caiu para identidade", e, procedencia,
        )
    _CACHE.update({"parametros": parametros, "procedencia": procedencia, "t": agora})
    return parametros, procedencia


def executar(caminho_semente: Optional[str] = None) -> dict:
    """Um ciclo completo. Nunca levanta: falha aberta, como o resto do cron."""
    resumo = {"celulas": 0, "adotadas": 0, "encurtadas": 0, "revertidas": 0,
              "congeladas": 0, "jogos": 0, "erro": None}
    try:
        repositorio.garantir_tabela()
        picks = repositorio.carregar_amostra()
        resumo["jogos"] = len({p.match_id for p in picks})

        ajuste = estimador.ajustar_hierarquico(picks)
        if caminho_semente:
            semente_picks = repositorio.carregar_semente_backfill(caminho_semente)
            if semente_picks:
                conc, n_sobrepostos = estimador.medir_concordancia(semente_picks, picks)
                n_prior, _status = estimador.n_prior_da_concordancia(conc, n_sobrepostos)
                ajuste = estimador.aplicar_semente(
                    ajuste, estimador.ajustar_hierarquico(semente_picks), n_prior)

        vigentes = repositorio.carregar_vigentes()
        por_celula = {}
        for p in picks:
            por_celula.setdefault((p.familia, p.liga), []).append(p)

        linhas = []
        for chave, proposta in ajuste.items():
            familia, liga = chave
            if not familia:
                continue
            resumo["celulas"] += 1
            vig = vigentes.get(chave) or {"versao": VERSAO_LEGADO, "a": 0.0, "b": 1.0}
            servidos = por_celula.get(chave, [])
            reversoes = repositorio.contar_reversoes_seguidas(familia, liga)

            rev = governanca.avaliar_reversao(
                servidos, {"a": vig["a"], "b": vig["b"]},
                {"a": vig["a"], "b": vig["b"]}, reversoes)
            limite = rev["limite_proximo"]

            if rev["acao"] == "congelar":
                resultado = {"a": vig["a"], "b": vig["b"], "status": "congelada",
                             "fator_encurtamento": None, "motivo": rev["motivo"]}
            elif rev["acao"] == "reverter":
                resumo["revertidas"] += 1
                resultado = {"a": vig["a"], "b": vig["b"], "status": "revertida",
                             "fator_encurtamento": None, "motivo": rev["motivo"]}
            else:
                resultado = governanca.avaliar_proposta(
                    proposta, {"a": vig["a"], "b": vig["b"]},
                    proposta["n_jogos"], limite=limite)
                if resultado["status"] == "adotada":
                    resumo["adotadas"] += 1
                elif resultado["status"] == "encurtada":
                    resumo["encurtadas"] += 1
            if resultado["status"] == "congelada":
                resumo["congeladas"] += 1

            linhas.append(repositorio.montar_linha_auditoria(
                familia, liga, vig["versao"] + 1, resultado,
                proposta["n_jogos"], proposta["origem"], None))

        repositorio.gravar_ciclo(linhas)
        limpar_cache()
        logger.info(
            "[CALIBRAGEM] ciclo: %d celulas, %d jogos | adotadas=%d encurtadas=%d "
            "revertidas=%d congeladas=%d",
            resumo["celulas"], resumo["jogos"], resumo["adotadas"],
            resumo["encurtadas"], resumo["revertidas"], resumo["congeladas"],
        )
    except Exception as e:                                   # noqa: BLE001
        resumo["erro"] = str(e)
        logger.error("[CALIBRAGEM] ciclo falhou: %s", e)
    return resumo
```

- [ ] **Step 4: Ligar o serving**

Modify `backend/services/ev_classification.py`, dentro de `_calibrar_com_detalhe`:

```python
    from backend.modeling.calibragem.ciclo import parametros_vigentes
    from backend.modeling.calibragem.curva import aplicar_versao
    parametros, procedencia = parametros_vigentes()
    detalhe = aplicar_versao(raw, market, league_id, regime, parametros)
    if procedencia != "banco":
        detalhe.tipo_banda = f"{detalhe.tipo_banda}|origem:{procedencia}"
    return detalhe
```

O sufixo em `tipo_banda` viaja até o `prediction_ledger` (campo `band_type`), então um período servido de snapshot fica visível na tabela — não só no log.

- [ ] **Step 5: Ligar o ciclo no cron**

Modify `backend/cron_handler.py`, depois do laço de jogos que chama `registrar_desfechos_do_jogo` (linha ~214), no mesmo nível do laço:

```python
    # #248: ciclo da camada de calibragem. Roda DEPOIS de registrar desfechos,
    # para consumir os jogos liquidados nesta execucao. Falha aberta.
    try:
        from backend.modeling.calibragem.ciclo import executar as _ciclo_calibragem
        _resumo_calibragem = _ciclo_calibragem(
            caminho_semente=os.getenv("CALIBRAGEM_SEMENTE_PATH"))
    except Exception as _e:                                  # noqa: BLE001
        logger.error("[#248] ciclo de calibragem falhou: %s", _e)
        _resumo_calibragem = {"erro": str(_e)}
```

- [ ] **Step 6: Rodar os testes e a suíte**

Run: `python -m pytest tests/calibragem/ -q -p no:cacheprovider -o addopts="" && python -m pytest -q -p no:cacheprovider -o addopts=""`
Expected: `tests/calibragem/` verde; suíte inteira em `1017 passed` mais os testes novos, 8 skipped.

- [ ] **Step 7: Commit**

```bash
git add backend/modeling/calibragem/ciclo.py tests/calibragem/test_11_ciclo.py backend/services/ev_classification.py backend/cron_handler.py
git commit -m "feat: ciclo de calibragem no cron e serving com fallback marcado (#248)

Banco fora do ar NUNCA vira identidade: cai no snapshot, e sem snapshot no
legado (versao 0). A procedencia viaja no `band_type` ate o ledger, entao um
periodo servido de snapshot fica visivel na tabela, nao so no log — o #238
mostrou o custo de fallback silencioso.

Cache por TTL no padrao do #231-a."
```

---

## Task 12: As três guardas finais

**Files:**
- Create: `tests/calibragem/test_12_guardas.py`

**Interfaces:**
- Consumes: todo o pacote.
- Produces: nada. É a rede de segurança dos invariantes que atravessam módulos.

- [ ] **Step 1: Escrever as guardas**

Create `tests/calibragem/test_12_guardas.py`:

```python
# -*- coding: utf-8 -*-
"""Testes 1b, 7 e 9 da spec — os invariantes que atravessam modulos."""
import pathlib

import pytest

from backend.modeling.calibragem.curva import aplicar
from backend.services.ev_classification import _filter_corridor_bets

PACOTE = pathlib.Path("backend/modeling/calibragem")


def test_9_nenhum_modulo_do_pacote_le_audit_results():
    """Regra #244: a fonte de calibracao e o ledger, nunca o audit."""
    ofensores = [f.name for f in PACOTE.glob("*.py")
                 if "audit_results" in f.read_text(encoding="utf-8")]
    assert not ofensores, ofensores


def test_1b_legado_so_tem_um_chamador():
    """Enquanto houver celula na versao 0 o legado vive — com UM chamador."""
    chamadores = [f.name for f in PACOTE.glob("*.py")
                  if f.name != "legado.py"
                  and "calibrar_legado" in f.read_text(encoding="utf-8")]
    assert chamadores == ["curva.py"], chamadores


def test_1b_legado_esta_marcado_como_congelado():
    fonte = (PACOTE / "legado.py").read_text(encoding="utf-8")
    assert "PROIBIDO EDITAR" in fonte


class _M:
    """Dublê minimo de MarketOutput para o filtro de corredor."""
    def __init__(self, market_type, selection, prob):
        self.market_type = market_type
        self.selection = selection
        self.calibrated_probability = prob
        self.raw_probability = prob


def test_7_a_curva_preserva_a_decisao_do_corredor():
    """A monotonicidade protege o #246-a: a correcao nao pode reordenar linhas.

    Numeros reais de Toronto x Nashville SC (09/09/2026), geracao 03:09.
    """
    brutos = {"Over 1.5": 0.810, "Under 2.5": 0.425, "Over 2.5": 0.575,
              "Under 3.5": 0.649, "Over 3.5": 0.351, "Under 4.5": 0.816}

    def decidir(probs):
        mercados = [_M("Over/Under", sel, p) for sel, p in probs.items()]
        sobreviventes = _filter_corridor_bets(mercados)
        return sorted(m.selection for m in sobreviventes)

    sem_camada = decidir(brutos)
    for a, b in ((0.45, 1.0), (0.0, 0.7), (0.3, 1.2), (-0.2, 0.9), (0.9, 1.5)):
        com_camada = decidir({s: aplicar(p, a, b) for s, p in brutos.items()})
        assert com_camada == sem_camada, (a, b, com_camada, sem_camada)


def test_7_qualquer_b_positivo_preserva_a_ordem():
    brutos = [0.05, 0.2, 0.351, 0.5, 0.649, 0.81, 0.95]
    for a, b in ((0.0, 0.1), (2.0, 3.0), (-1.5, 0.4)):
        corrigidos = [aplicar(p, a, b) for p in brutos]
        assert corrigidos == sorted(corrigidos), (a, b)
```

- [ ] **Step 2: Rodar as guardas**

Run: `python -m pytest tests/calibragem/test_12_guardas.py -q -p no:cacheprovider -o addopts=""`
Expected: PASS, 5 testes.

Se `test_7_a_curva_preserva_a_decisao_do_corredor` falhar, a curva está reordenando linhas — conferir se `b` positivo está sendo garantido em `governanca.avaliar_proposta`. Este teste é o que impede a camada de mudar o corredor por efeito colateral.

- [ ] **Step 3: Rodar a suíte inteira**

Run: `python -m pytest -q -p no:cacheprovider -o addopts=""`
Expected: `1017 passed` mais os testes de `tests/calibragem/`, 8 skipped, 0 failed.

- [ ] **Step 4: Prova empírica exigida pela proibição 14**

Run:
```bash
PYTHONPATH=. PYTHONIOENCODING=utf-8 python -c "
from dotenv import load_dotenv; load_dotenv('.env')
from backend.modeling.calibragem.repositorio import carregar_amostra
from backend.modeling.calibragem.estimador import ajustar_hierarquico
from backend.modeling.calibragem.curva import aplicar
from backend.modeling.calibragem.governanca import brier
import random
picks = carregar_amostra()
jogos = sorted({p.match_id for p in picks})
random.Random(227).shuffle(jogos)
corte = int(len(jogos) * 0.7)
treino_ids, teste_ids = set(jogos[:corte]), set(jogos[corte:])
treino = [p for p in picks if p.match_id in treino_ids]
teste  = [p for p in picks if p.match_id in teste_ids]
par = ajustar_hierarquico(treino)
sem = brier([(p.p_raw, p.y) for p in teste])
com = brier([(aplicar(p.p_raw, par.get((p.familia,p.liga), par[(p.familia,\"\")])['a'],
                      par.get((p.familia,p.liga), par[(p.familia,\"\")])['b']), p.y) for p in teste])
print(f'jogos treino={len(treino_ids)} teste={len(teste_ids)}')
print(f'Brier RAW na janela retida     = {sem:.5f}')
print(f'Brier com a camada             = {com:.5f}   delta {com-sem:+.5f}')
"
```
Expected: `delta` negativo. Registrar o número no `REGISTRO_CORRECOES.md` — é a prova antes/depois que a proibição 14 exige.

**Se o delta vier positivo, parar e não ligar a camada.** O critério de fracasso da spec pré-registra que a camada é abandonada, não ajustada.

- [ ] **Step 5: Escrever o registro e o índice**

Create a entrada `## 248` em `docs/REGISTRO_CORRECOES.md` no formato do repositório, com: o problema (−10,2 pontos medidos), as seis decisões da spec com a razão, os números do controle positivo (13.524 pares com igualdade exata), o delta de Brier do passo 4, e o critério de fracasso pré-registrado.

Adicionar a linha correspondente em `docs/INDICE_REGRAS.md` acima de `| 247 |`.

Adicionar a regra permanente em `docs/REGRAS_ATIVAS.md`: **`audit_results` é proibido como fonte de calibração; a fonte é `prediction_ledger` × `ledger_outcomes`, uma linha por (jogo, mercado, seleção), última geração antes do kickoff; `n_efetivo` conta jogos.**

- [ ] **Step 6: Espelhar, commitar e empurrar**

```bash
cd /c/painel_apostas/sportsbank-pro
cp sportsbankzu-pro/docs/REGISTRO_CORRECOES.md docs/
cp sportsbankzu-pro/docs/REGRAS_ATIVAS.md      docs/
cp sportsbankzu-pro/docs/INDICE_REGRAS.md      docs/
cp sportsbankzu-pro/CLAUDE.md                  .
cd sportsbankzu-pro
git add -A
git commit -m "feat: camada de calibragem aprendida completa (#248)

Substitui a deflacao fixa por (a, b) por familia que se ajusta a cada lote de
jogos liquidados, com trava de 2 pontos por ciclo, reversao fora da amostra e
uma linha de auditoria por celula em todo ciclo.

Guardas: a curva nao reordena linhas (o filtro de corredor decide identico,
#246-a); nenhum modulo le audit_results (#244); o legado tem um unico
chamador e esta marcado PROIBIDO EDITAR.

Prova empirica em janela retida por jogo: substituir esta linha pelo delta
de Brier impresso no passo 4 desta tarefa (ex.: \"Brier RAW 0.19xxx ->
camada 0.18xxx, delta -0.0xxx em NN jogos retidos\"). Commit sem o numero
medido viola a proibicao 14 do CLAUDE.md."
git push origin HEAD:main
```

---

## Auto-revisão do plano

**Cobertura da spec:** seção 3 (modelo) → Tasks 4-6; seção 3.1 (encolhimento) → Task 5; seção 3.2 (semente) → Task 6; seção 3.3 (guardas do estimador) → Tasks 4 e 7; seção 4 (arquitetura) → Tasks 1-3; seção 4.1 (persistência) → Tasks 3 e 9; seção 4.2 (contato) → Tasks 1, 2 e 11; seção 5.1 (trava) → Task 7; 5.2 (piso) → Task 7; 5.3 (reversão) → Task 8; 5.4 (auditoria) → Task 9; 5.5 (limiares) → Task 10; seção 6.1 (dia zero) → Tasks 1 e 2; 6.2 (contagem) → Task 3; 6.3 (falhas) → Tasks 10 e 11; seção 7 (testes 1-9) → distribuídos, com 1b, 7 e 9 na Task 12; seção 8 (critério de fracasso) → Task 12 passo 4.

**Lacuna consciente:** a seção 9 da spec (caminho de crescimento — isotônica quando o resíduo por banda mostrar padrão) **não tem tarefa**. É deliberado: o critério para atravessar essa porta é uma medição que só existe depois de vários ciclos rodando. Entra em plano próprio.

**Consistência de tipos:** `Pick` é definido na Task 3 e usado nas Tasks 4-8 e 11 com os mesmos cinco campos. `avaliar_proposta` devolve `{"a","b","status","fator_encurtamento","motivo"}` na Task 7 e é consumido com essas chaves na Task 11. `montar_linha_auditoria` recebe o dicionário de `avaliar_proposta` mais `n_jogos`, `origem` e `brier`, e é chamado assim na Task 11. `parametros_vigentes` devolve `Dict[(familia, liga) -> (versao, a, b)]`, o formato que `curva.aplicar_versao` consome desde a Task 2.
