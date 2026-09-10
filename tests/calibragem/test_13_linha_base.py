# -*- coding: utf-8 -*-
"""C1 — a linha de base da versao 0.

A versao 0 NAO e a identidade: ela delega a `calibrar_legado`. Estes testes
travam (a) a cobertura de familias, (b) o ajuste em si, e (c) a tabela de
erro maximo publicada na docstring de `linha_base.py` — para que ela nao
envelheca em silencio se alguem mexer no legado.
"""
import pytest

from backend.modeling.calibragem import linha_base as LB
from backend.modeling.calibragem.curva import _FAMILIAS, aplicar
from backend.modeling.calibragem.legado import calibrar_legado


def test_toda_familia_conhecida_tem_mercado_representativo():
    """Familia que `curva._FAMILIAS` resolve mas `MERCADO_REPRESENTATIVO` nao
    cobre vira celula rejeitada no ciclo (sem referencia para a trava). O
    par tem de andar junto."""
    familias = {f for _, f in _FAMILIAS}
    assert familias == set(LB.MERCADO_REPRESENTATIVO), (
        familias.symmetric_difference(LB.MERCADO_REPRESENTATIVO))


def test_familia_desconhecida_levanta():
    with pytest.raises(ValueError, match="mercado representativo"):
        LB.ajustar_ao_legado("Handicap")


def test_o_mercado_representativo_de_ou_nao_e_under_2_5():
    """"Under 2.5" e o unico rotulo que carrega o extra do #113. Ele e
    caminho morto hoje, mas a linha de base nao pode depender de um ramo que
    a producao nao exercita."""
    assert "under 2.5" not in LB.MERCADO_REPRESENTATIVO["Over/Under"].lower()


# Erro maximo MEDIDO por familia, em pontos de probabilidade. Publicado na
# docstring de `linha_base.py`. Duas formas distintas so: meia banda (O/U,
# BTTS) e banda inteira (as outras quatro).
ERRO_MEDIDO_PP = {
    "Over/Under": 8.14, "BTTS": 8.14,
    "Corners": 15.47, "Cards": 15.47,
    "1X2": 15.47, "Double Chance": 15.47,
}


@pytest.mark.parametrize("familia,esperado", sorted(ERRO_MEDIDO_PP.items()))
def test_erro_maximo_da_aproximacao_bate_com_o_documentado(familia, esperado):
    a, b = LB.ajustar_ao_legado(familia)
    medido = LB.erro_maximo(familia, a, b) * 100
    assert medido == pytest.approx(esperado, abs=0.02), (
        f"{familia}: docstring de linha_base.py diz {esperado}pp, medido "
        f"{medido:.2f}pp. Se o legado mudou, atualize a tabela; se nao, "
        "alguem mexeu no ajuste.")


@pytest.mark.parametrize("familia", sorted(ERRO_MEDIDO_PP))
def test_a_linha_de_base_fica_mais_perto_do_legado_que_a_identidade(familia):
    """O criterio que justifica a correcao. A aproximacao NAO chega aos 2pp
    da trava (ver docstring de `linha_base.py`), mas erra menos que a
    referencia que substitui — que e o ponto do C1."""
    a, b = LB.ajustar_ao_legado(familia)
    mercado = LB.MERCADO_REPRESENTATIVO[familia]
    erro_base = erro_identidade = 0.0
    p = 0.02
    while p <= 0.98 + 1e-12:
        alvo = calibrar_legado(p, mercado, "", "NORMAL").final
        erro_base = max(erro_base, abs(aplicar(p, a, b) - alvo))
        erro_identidade = max(erro_identidade, abs(p - alvo))
        p += 0.01
    assert erro_base < erro_identidade, (erro_base, erro_identidade)


def test_o_ajuste_e_deterministico_e_cacheado():
    LB.limpar_cache()
    primeiro = LB.linha_base("Corners")
    segundo = LB.linha_base("Corners")
    assert primeiro == segundo
    assert primeiro == LB.ajustar_ao_legado("Corners")
    LB.limpar_cache()
    assert LB.linha_base("Corners") == primeiro
