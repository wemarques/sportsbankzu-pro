# -*- coding: utf-8 -*-
"""A curva de dois parametros: identidade, monotonicidade, bordas, versao 0."""
import json
import math
import pathlib

import pytest

from backend.modeling.calibragem import VERSAO_LEGADO
from backend.modeling.calibragem.curva import (
    aplicar, aplicar_versao, distancia_maxima, familia_do_mercado,
)
from backend.modeling.calibragem.legado import calibrar_legado

FIXTURE_DOURADA = (
    pathlib.Path(__file__).parent / "fixtures" / "golden_legado.json"
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


# ─── aplicar_versao — os 4 ramos do sentinela (rodada de correcao 1, #248-r1) ───
#
# O primeiro passe desta task so exercitava `aplicar`, `distancia_maxima` e
# `familia_do_mercado` de forma direta -- `aplicar_versao`, que e o sentinela
# e a funcao central da tarefa, so era tocada indiretamente por um teste
# pre-existente que nunca passa `parametros` (so o ramo trivial). Os 4 testes
# abaixo cobrem cada ramo da funcao.

def test_aplicar_versao_sem_parametros_delega_ao_legado():
    """Ramo 1: parametros ausente (None) ou vazio ({}) -> pass-through."""
    esperado = calibrar_legado(0.62, "Over 2.5", "championship", "NORMAL")
    for parametros in (None, {}):
        d = aplicar_versao(0.62, "Over 2.5", "championship", "NORMAL", parametros)
        assert d.final == esperado.final
        assert d.tipo_banda == esperado.tipo_banda


def test_aplicar_versao_familia_desconhecida_delega_ao_legado():
    """Ramo 2: familia_do_mercado levanta -> aplicar_versao NAO propaga,
    delega ao legado. `parametros` nao-vazio para provar que o motivo da
    delegacao e a familia desconhecida, nao a ausencia de parametros."""
    market = "Handicap Asiatico -1.5"
    parametros = {("1X2", ""): (1, 0.1, 0.9)}
    esperado = calibrar_legado(0.62, market, "championship", "NORMAL")
    d = aplicar_versao(0.62, market, "championship", "NORMAL", parametros)
    assert d.final == esperado.final


def test_aplicar_versao_celula_ausente_do_mapa_delega_ao_legado():
    """Ramo 3a: familia reconhecida, mas nem (familia, liga) nem (familia, "")
    estao no mapa -> delega ao legado."""
    parametros = {("BTTS", ""): (1, 0.1, 0.9)}  # so cobre BTTS, nao Over/Under
    esperado = calibrar_legado(0.62, "Over 2.5", "championship", "NORMAL")
    d = aplicar_versao(0.62, "Over 2.5", "championship", "NORMAL", parametros)
    assert d.final == esperado.final


def test_aplicar_versao_celula_na_versao_zero_delega_ao_legado():
    """Ramo 3b: a celula existe no mapa mas esta marcada VERSAO_LEGADO ->
    mesmo com entrada presente, delega ao legado (a=1.0 nem sequer e
    aplicado -- se fosse, o resultado bateria com `aplicar`, nao com
    `calibrar_legado`)."""
    parametros = {("Over/Under", "championship"): (VERSAO_LEGADO, 99.0, 99.0)}
    esperado = calibrar_legado(0.62, "Over 2.5", "championship", "NORMAL")
    d = aplicar_versao(0.62, "Over 2.5", "championship", "NORMAL", parametros)
    assert d.final == esperado.final


def test_aplicar_versao_fallback_para_chave_sem_liga():
    """Ramo 3c: nao ha entrada para (familia, liga), mas ha para
    (familia, "") -- o fallback generico entra e A CURVA E APLICADA (versao
    != 0), provando que o fallback nao e apenas alcancado mas tambem usado."""
    a, b = 0.2, 0.9
    parametros = {("Over/Under", ""): (7, a, b)}
    d = aplicar_versao(0.62, "Over 2.5", "outra-liga-sem-entrada", "NORMAL", parametros)
    assert d.final == pytest.approx(aplicar(0.62, a, b), abs=1e-12)
    assert d.tipo_banda == "curva-v7"


def test_aplicar_versao_com_celula_real_aplica_a_curva():
    """Ramo 4: o caso que a Task 11 aciona em producao. Celula com versao
    real -> aplica a curva de 2 parametros, muta `detalhe.final` e escreve
    `tipo_banda`. `final` tem de bater com `aplicar(raw, a, b)` calculado a
    parte, nao so ser "diferente do legado" -- um erro na ordem da tupla
    (versao, a, b), na mutacao ou na chave de fallback passaria despercebido
    numa asserção so de "mudou"."""
    raw = 0.4123
    versao, a, b = 3, 0.18, 0.82
    parametros = {("Over/Under", "championship"): (versao, a, b)}
    d = aplicar_versao(raw, "Over 2.5", "championship", "NORMAL", parametros)

    esperado_final = aplicar(raw, a, b)
    assert d.final == pytest.approx(esperado_final, abs=1e-12)
    assert d.tipo_banda == f"curva-v{versao}"
    # a mutacao ocorreu sobre o DetalheCalibracao do legado (iso/banda/etc
    # continuam vindo do isotonico+deflacao -- so final e tipo_banda mudam)
    legado_puro = calibrar_legado(raw, "Over 2.5", "championship", "NORMAL")
    assert d.iso == legado_puro.iso
    assert d.raw == legado_puro.raw
    assert d.final != legado_puro.final


# ─── caminho real de producao reproduz a fixture dourada (#248-r1, achado 2) ───
#
# `test_01_legado_controle_positivo.py` chama `calibrar_legado` DIRETO --
# nao prova que o caminho de producao (`ev_classification._calibrar_com_
# detalhe` -> `curva.aplicar_versao` -> `legado.calibrar_legado`) continua
# exato. Sem `parametros`, `aplicar_versao` e pass-through (ramo 1 acima),
# mas isso e raciocinio, nao evidencia; este teste roda a MESMA fixture
# dourada pelo caminho de producao real e exige a mesma igualdade exata.

def test_calibrar_com_detalhe_reproduz_a_fixture_dourada_via_aplicar_versao():
    from backend.services.ev_classification import _calibrar_com_detalhe

    casos = json.loads(FIXTURE_DOURADA.read_text(encoding="utf-8"))
    divergentes = []
    for c in casos:
        d = _calibrar_com_detalhe(c["raw"], c["market"], c["league_id"], c["regime"])
        if d.final != c["final"]:
            divergentes.append((c["market"], c["league_id"], c["raw"],
                                c["final"], d.final))
    assert not divergentes, f"{len(divergentes)} divergencias: {divergentes[:5]}"
