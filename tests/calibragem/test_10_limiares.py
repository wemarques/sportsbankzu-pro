# -*- coding: utf-8 -*-
"""Teste 6 da spec — o volume publicado fica constante.

A classificacao usa prob RAW (proibicao 11), entao `safe_prob` e `neutro_prob`
nao se movem. O volume sobe por `ev` e `edge`, que consomem a corrigida.

#248, Task 13 (composicao): a probabilidade corrigida e
`aplicar(p_legado, a, b)`, entao a referencia da versao 0 e `(a=0, b=1)` — e
sobre `p_legado` isso E o legado, EXATO. Antes da composicao este arquivo
precisava de `linha_base.linha_base()`, uma logistica que aproximava a curva
legada com 8,14pp a 15,47pp de erro; o volume de referencia saia da
aproximacao, nao da curva publicada. `linha_base.py` foi apagado.
"""
import pytest

from backend.modeling.calibragem.curva import aplicar, base_da_composicao
from backend.modeling.calibragem.limiares import contar_por_classe, rederivar

MERCADO = "Over 2.5"      # rotulo real do serving; ramo de meia banda (#165-e)


class P:
    """Dublê de `Pick` com os quatro campos que `limiares` de fato le."""

    def __init__(self, familia, p_raw, odd, p_legado):
        self.familia, self.p_raw, self.odd = familia, p_raw, odd
        self.p_legado = p_legado


ATUAIS = {"Over/Under": {"safe_ev": 0.06, "neutro_ev": 0.00,
                         "safe_edge": 0.05, "neutro_edge": 0.02}}

# A VERSAO 0, exata. Sobre `p_legado`, `aplicar(p, 0, 1) == p`, entao esta
# entrada reproduz `calibrar_legado` byte a byte — nao "aproximadamente", e
# e essa a diferenca que a Task 13 comprou.
VERSAO_ZERO = {"Over/Under": {"a": 0.0, "b": 1.0}}
NOVO = {"Over/Under": {"a": 0.45, "b": 1.0}}     # sobe ~10 pontos


def _amostra(n=400, familia="Over/Under", mercado=MERCADO):
    """`p_legado` MEDIDO, chamando o legado — nao um numero escolhido a dedo.

    O ponto do teste e o volume contra a curva que a versao 0 de fato
    publica; inventar `p_legado` mediria contra outra coisa.
    """
    saida = []
    for i in range(n):
        p_raw = 0.30 + (i % 60) / 100.0
        saida.append(P(familia, p_raw, 1.70 + (i % 9) / 10.0,
                       base_da_composicao(p_raw, mercado, "", "NORMAL")))
    return saida


def test_a_versao_zero_e_o_legado_exato():
    """A premissa de todo o resto, medida em vez de suposta."""
    for pk in _amostra(60):
        assert aplicar(pk.p_legado, 0.0, 1.0) == pytest.approx(
            pk.p_legado, abs=1e-12)


def test_o_legado_publica_abaixo_do_raw():
    """Se `p_legado == p_raw` a amostra nao exercita nada — o legado deflaciona."""
    amostra = _amostra(60)
    assert all(pk.p_legado < pk.p_raw for pk in amostra)


def test_sem_rederivacao_o_volume_sobe():
    picks = _amostra()
    antes = contar_por_classe(picks, VERSAO_ZERO, ATUAIS)["Over/Under"]
    depois = contar_por_classe(picks, NOVO, ATUAIS)["Over/Under"]
    # "Volume publicado" e o TOTAL, nao a faixa do meio: quando a probabilidade
    # sobe, picks migram de `neutro` para `safe` e outros entram em `neutro` por
    # baixo — os fluxos se cancelam e o balde intermediario pode empatar.
    assert sum(depois.values()) > sum(antes.values())


def test_rederivacao_devolve_o_volume_ao_que_era():
    picks = _amostra()
    antes = contar_por_classe(picks, VERSAO_ZERO, ATUAIS)
    novos = rederivar(picks, VERSAO_ZERO, NOVO, ATUAIS)
    depois = contar_por_classe(picks, NOVO, novos)
    for classe in ("safe", "neutro"):
        assert abs(depois["Over/Under"][classe] - antes["Over/Under"][classe]) <= 2, \
            (classe, antes, depois)


def test_familia_sem_odd_nao_move_limiar():
    """Cartoes tem 88,3% das linhas sem odd — nao ha volume a manter."""
    picks = [P("Cards", 0.60, None, 0.45) for _ in range(50)]
    atuais = {"Cards": {"safe_ev": 0.06, "neutro_ev": 0.0,
                        "safe_edge": 0.05, "neutro_edge": 0.02}}
    novos = rederivar(picks, {"Cards": {"a": 0.0, "b": 1.0}},
                      {"Cards": {"a": 0.5, "b": 1.0}}, atuais)
    assert novos["Cards"] == atuais["Cards"]


def test_familia_ausente_da_amostra_e_preservada():
    novos = rederivar([], VERSAO_ZERO, NOVO, ATUAIS)
    assert novos["Over/Under"] == ATUAIS["Over/Under"]


# ─── a referencia tem de ser o LEGADO, nao o `p_raw` ────────────────────────
#
# O C1 nasceu de medir contra a identidade. A composicao fecha essa porta por
# construcao — `(0, 1)` sobre `p_legado` E o legado — mas a porta reabre em
# silencio se alguem trocar `entrada_da_curva(pk)` por `pk.p_raw` dentro de
# `limiares`. Este teste mede o tamanho do erro que isso causaria.

def test_medir_sobre_p_raw_inflaria_a_referencia():
    """Numeros MEDIDOS nesta amostra (400 picks, mesma grade de p_raw/odd):

        familia (ramo)              volume contra o legado   contra p_raw
        Over/Under (meia banda)             242                  251
        Corners    (banda inteira)          209                  251

    Partindo de `p_raw`, a re-derivacao seguraria o volume de escanteios num
    patamar 20% acima do que o painel publicava na vespera — e o teste de
    volume constante continuaria verde, porque estaria preservando a coisa
    errada. E o C1 em miniatura.

    Nota de registro, medida antes de `linha_base.py` ser apagado: a
    aproximacao logistica que substituia o legado dava 194 para Over/Under —
    20% ABAIXO do legado verdadeiro (242). Ela errava para o outro lado, e
    tambem nao era a curva publicada. So a composicao acerta o numero.
    """
    class _ComoSeFosseRaw:
        def __init__(self, pk):
            self.familia, self.odd = pk.familia, pk.odd
            self.p_raw = self.p_legado = pk.p_raw

    atuais = dict(ATUAIS, Corners=dict(ATUAIS["Over/Under"]))
    versao_zero = dict(VERSAO_ZERO, Corners={"a": 0.0, "b": 1.0})
    picks = _amostra(familia="Corners", mercado="Escanteios Over 9.5")

    do_legado = sum(
        contar_por_classe(picks, versao_zero, atuais)["Corners"].values())
    do_raw = sum(contar_por_classe([_ComoSeFosseRaw(pk) for pk in picks],
                                   versao_zero, atuais)["Corners"].values())

    assert do_legado < do_raw, (do_legado, do_raw)
    assert do_raw / do_legado > 1.15, (do_legado, do_raw)
