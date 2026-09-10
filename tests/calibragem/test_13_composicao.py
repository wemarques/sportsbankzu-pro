# -*- coding: utf-8 -*-
"""O CONTROLE POSITIVO do desenho novo (#248, Task 13).

A camada aprende o residuo SOBRE o legado:

    p_corrigida = sigmoide(a + b * logit(legado(p_raw)))

Logo `(a=0, b=1)` **e** a versao 0 — por construcao, nao por aproximacao.
Este arquivo prova exatamente isso e mais nada:

  1. `aplicar_versao(p, mercado, liga, regime, {celula: (versao, 0, 1)})`
     devolve o MESMO `final` que `calibrar_legado(p, ...)`, com erro < 1e-9,
     varrendo a grade inteira da fixture dourada (13.524 pares);
  2. a trava de 2pp e exata no primeiro ciclo, partindo de `(0, 1)`;
  3. o rotulo do legado que o repositorio reconstroi a partir do ledger bate
     com o que o serving de fato passa a `_calibrar_com_detalhe`.

O que este arquivo SUBSTITUI: `test_13_linha_base.py`, que travava a tabela
de erro de uma logistica ajustada ao legado (8,14pp a 15,47pp, com piso
teorico de 5,89pp/9,35pp). O erro nao foi reduzido — ele sumiu, e
`linha_base.py` foi apagado.
"""
import json
import pathlib

import pytest

from backend.modeling.calibragem import PASSO_MAXIMO_PP, VERSAO_LEGADO
from backend.modeling.calibragem.curva import (
    aplicar, aplicar_versao, distancia_maxima, familia_do_mercado,
)
from backend.modeling.calibragem.governanca import avaliar_proposta
from backend.modeling.calibragem.legado import calibrar_legado
from backend.modeling.calibragem.repositorio import rotulo_do_legado

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "golden_legado.json"

# A versao gravada; qualquer numero != VERSAO_LEGADO serve. O que importa e
# que a celula NAO caia no ramo de delegacao: o `final` tem de sair da
# COMPOSICAO e ainda assim reproduzir o legado.
VERSAO_REAL = 3

# O limite do controle positivo. `aplicar(x, 0, 1)` e
# `sigmoide(logit(x))`: matematicamente a identidade, numericamente uma
# ida-e-volta em float64. 1e-9 e ~7 ordens de grandeza acima do residuo
# observado e 7 ordens ABAIXO da trava de 2pp — nao esconde nada.
TOLERANCIA = 1e-9


@pytest.fixture(scope="module")
def casos():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_a_grade_da_fixture_cobre_mercados_ligas_e_regimes(casos):
    """Sem esta asserção o controle positivo poderia estar varrendo um caso
    so e ninguem notaria."""
    assert len({c["market"] for c in casos}) >= 8
    assert len({c["league_id"] for c in casos}) >= 3
    assert len({c["regime"] for c in casos}) >= 1
    assert len({c["tipo_banda"] for c in casos}) == 3


def test_a_versao_zero_por_construcao_reproduz_o_legado(casos):
    """O CONTROLE POSITIVO. Com `(a, b) = (0, 1)` e uma versao REAL gravada,
    `aplicar_versao` percorre o ramo da composicao (nao o de delegacao) e
    ainda assim devolve o legado.

    Se este teste falhar, a promessa central do #248 caiu: o dia zero da
    camada deixaria de publicar o que se publicava na vespera.
    """
    pior = 0.0
    onde = None
    for c in casos:
        familia = familia_do_mercado(c["market"])
        parametros = {(familia, c["league_id"]): (VERSAO_REAL, 0.0, 1.0)}
        composto = aplicar_versao(c["raw"], c["market"], c["league_id"],
                                  c["regime"], parametros)
        esperado = calibrar_legado(c["raw"], c["market"], c["league_id"],
                                   c["regime"])
        d = abs(composto.final - esperado.final)
        if d > pior:
            pior, onde = d, (c["market"], c["league_id"], c["raw"])
        # a composicao ocorreu de verdade — nao foi delegacao disfarcada
        assert composto.tipo_banda == f"curva-v{VERSAO_REAL}"
    assert pior < TOLERANCIA, (
        f"maior divergencia {pior:.3e} em {onde} — (a=0, b=1) deixou de ser "
        "a versao 0 por construcao")


def test_o_ramo_da_composicao_e_mesmo_diferente_do_de_delegacao(casos):
    """Controle negativo do teste acima: com um `(a, b)` que nao e (0, 1), o
    mesmo caminho TEM de divergir do legado. Sem isto, um `aplicar_versao`
    que sempre delegasse passaria no controle positivo."""
    divergiu = 0
    for c in casos[:500]:
        familia = familia_do_mercado(c["market"])
        parametros = {(familia, c["league_id"]): (VERSAO_REAL, 0.30, 1.0)}
        composto = aplicar_versao(c["raw"], c["market"], c["league_id"],
                                  c["regime"], parametros)
        if abs(composto.final - c["final"]) > 1e-6:
            divergiu += 1
    assert divergiu > 400, divergiu


def test_a_versao_zero_declarada_continua_delegando(casos):
    """O outro ramo: celula marcada `VERSAO_LEGADO` no mapa nem chega a
    compor — e o `final` e o do legado, exato (igualdade, nao tolerancia)."""
    for c in casos[:300]:
        familia = familia_do_mercado(c["market"])
        parametros = {(familia, c["league_id"]): (VERSAO_LEGADO, 9.0, 9.0)}
        d = aplicar_versao(c["raw"], c["market"], c["league_id"], c["regime"],
                           parametros)
        assert d.final == c["final"]


# ─── a trava de 2pp, exata desde o primeiro ciclo ───────────────────────────

def test_a_trava_e_exata_no_primeiro_ciclo():
    """A referencia do primeiro ciclo e `(0, 1)`, que E a curva publicada.

    Antes da composicao esta comparacao era contra a identidade (erro de ate
    24,50pp) ou contra uma logistica aproximada (8,14 a 15,47pp): a trava
    dizia "andei 1,4pp" enquanto a probabilidade publicada andava 24pp. Aqui
    a distancia medida e a distancia real, e a proposta encurtada respeita o
    limite de verdade.
    """
    vigente = {"a": 0.0, "b": 1.0}          # a versao 0, sem aproximacao
    for proposta in ({"a": 0.45, "b": 1.0}, {"a": 2.0, "b": 1.0},
                     {"a": -0.9, "b": 0.7}, {"a": 0.0, "b": 1.6}):
        r = avaliar_proposta(proposta, vigente, n_jogos=100)
        assert r["status"] in ("adotada", "encurtada"), r
        andou = distancia_maxima(0.0, 1.0, r["a"], r["b"])
        assert andou <= PASSO_MAXIMO_PP + 1e-6, (proposta, andou)


def test_o_movimento_medido_e_o_movimento_publicado():
    """A trava mede em `(a, b)`; o painel publica `aplicar(legado(p), a, b)`.

    A composicao faz as duas coisas coincidirem: o maior deslocamento REAL
    da probabilidade publicada (varrendo `p_legado` na faixa de saida do
    legado) nunca passa do que `distancia_maxima` reportou. Antes, com a
    referencia aproximada, o movimento real de escanteios chegava a 16,95pp
    contra uma trava de 2pp.
    """
    vigente = {"a": 0.0, "b": 1.0}
    r = avaliar_proposta({"a": 2.0, "b": 1.4}, vigente, n_jogos=100)
    assert r["status"] == "encurtada"

    pior = 0.0
    p = 0.05                       # piso do legado (`max(result, 0.05)`)
    while p <= 0.86:               # teto do legado (satura em 0,8575)
        antes = aplicar(p, 0.0, 1.0)          # = p, a versao 0
        depois = aplicar(p, r["a"], r["b"])
        pior = max(pior, abs(depois - antes))
        p += 0.005
    assert pior <= PASSO_MAXIMO_PP + 1e-6, pior


# ─── o rotulo do legado reconstruido do ledger ──────────────────────────────
#
# `carregar_amostra` tem o par (market, selection) em INGLES e precisa do
# rotulo de EXIBICAO que o serving usa, porque o rotulo escolhe o modelo
# isotonico E o ramo da banda. Errar aqui poe a familia inteira na banda
# errada, em silencio.

# Os 6 `market` e as formas de `selection` que o `prediction_ledger` de fato
# guarda hoje (44 pares distintos, consultados na RDS em 2026-09-10).
PARES_REAIS_DO_LEDGER = {
    ("1X2", "Home"): "1X2_home",
    ("1X2", "Draw"): "1X2_draw",
    ("1X2", "Away"): "1X2_away",
    ("BTTS", "BTTS Yes"): "BTTS",
    ("Over/Under", "Over 1.5"): "Over 1.5",
    ("Over/Under", "Over 2.5"): "Over 2.5",
    ("Over/Under", "Under 3.5"): "Under 3.5",
    ("Over/Under", "Under 4.5"): "Under 4.5",
    ("Double Chance", "DC 1X"): "Double Chance 1X",
    ("Double Chance", "DC 12"): "Double Chance 12",
    ("Double Chance", "DC X2"): "Double Chance X2",
    ("Corners", "Corners Over 4.5"): "Escanteios Over 4.5",
    ("Corners", "Corners Over 9.5"): "Escanteios Over 9.5",
    ("Corners", "Corners Under 11.5"): "Escanteios Under 11.5",
    ("Cards", "Over 1.5"): "Cartoes Over 1.5",
    ("Cards", "Over 3.5"): "Cartoes Over 3.5",
    ("Cards", "Under 5.5"): "Cartoes Under 5.5",
}


@pytest.mark.parametrize("par,esperado", sorted(PARES_REAIS_DO_LEDGER.items()))
def test_rotulo_do_legado_reproduz_o_rotulo_do_serving(par, esperado):
    assert rotulo_do_legado(*par) == esperado


@pytest.mark.parametrize("par", sorted(PARES_REAIS_DO_LEDGER))
def test_o_rotulo_reconstruido_cai_no_mesmo_ramo_de_banda(par):
    """A consequencia que importa: o ramo da deflacao. `Cards | Over 3.5`
    cru cairia na MEIA banda (comeca com "over "); com o prefixo `Cartoes`
    cai na banda INTEIRA, que e o que a producao serve.
    """
    from backend.modeling.calibragem.repositorio import REGIME_DA_AMOSTRA

    esperado_por_familia = {
        "1X2": "inteira", "BTTS": "meia-btts", "Over/Under": "meia",
        "Double Chance": "inteira", "Corners": "inteira", "Cards": "inteira",
    }
    rotulo = rotulo_do_legado(*par)
    d = calibrar_legado(0.62, rotulo, "premier-league", REGIME_DA_AMOSTRA)
    assert d.tipo_banda == esperado_por_familia[par[0]], (par, rotulo,
                                                          d.tipo_banda)


def test_o_rotulo_cru_do_ledger_cairia_na_banda_errada():
    """Por que a conversao existe, medido. Sem ela, cartoes viriam da meia
    banda (o ramo de gols) e escanteios do rotulo `Corners ...`, que acerta
    o ramo por acaso mas erra o modelo isotonico."""
    from backend.modeling.calibragem.repositorio import REGIME_DA_AMOSTRA

    cru = calibrar_legado(0.62, "Over 3.5", "premier-league", REGIME_DA_AMOSTRA)
    certo = calibrar_legado(0.62, "Cartoes Over 3.5", "premier-league",
                            REGIME_DA_AMOSTRA)
    assert cru.tipo_banda == "meia"
    assert certo.tipo_banda == "inteira"
    assert cru.final != certo.final


@pytest.mark.parametrize("par", sorted(PARES_REAIS_DO_LEDGER))
def test_a_conversao_preserva_a_familia(par):
    """O rotulo convertido tem de resolver a MESMA familia que o par cru —
    senao o estimador aprende numa celula e o serving publica noutra."""
    from backend.modeling.calibragem.repositorio import classificar_familia

    assert (familia_do_mercado(rotulo_do_legado(*par))
            == classificar_familia(*par))


def test_market_desconhecido_devolve_none_em_vez_de_palpite():
    """Nao ha rotulo aproximado aceitavel: `p_legado` da banda errada
    envenena a curva da familia. O chamador descarta e loga."""
    assert rotulo_do_legado("Handicap Asiatico", "-1.5 Home") is None
    assert rotulo_do_legado("", "Over 2.5") is None
