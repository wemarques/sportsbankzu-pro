# -*- coding: utf-8 -*-
"""#238-a — a narrativa so pode citar a probabilidade PUBLICADA.

Caso real que motivou a camada (Toronto x Nashville SC, 2026-09-09, MLS):

    "...o cenario de gols tende a ser equilibrado (lambda fora 1.76, over 2.5
     em 57.5% dos jogos). Escanteios com potencial moderado (media conjunta de
     10.34, over 8.5 em 67.9%)."

O card exibia SO `Escanteios Over 6.5` (59%) e `Cartoes Over 2.5` (60%). Os
57.5% sao a probabilidade RAW de Over 2.5 gols — o proprio prompt a entrega
rotulada `(raw)` na secao de estatisticas — e o mercado nem aparecia na tela.
`validate_output` devolvia `ok=True`: o padrao de gols exigia a palavra "gols"
logo apos o numero e o de escanteios exigia "Escanteios" logo antes, entao
duas mencoes de mercado num paragrafo nao casavam com nada, e nada nunca
comparava o NUMERO citado com o publicado.
"""
import pytest

from backend.ai.mistral_contract import ApprovedPick, validate_output


TEXTO_REAL = (
    "Toronto apresenta baixa eficiencia ofensiva em casa (xG 1.37, media de 1.23 "
    "gols esperados) e alta vulnerabilidade defensiva (xG sofrido 1.45). Nashville, "
    "com forma recente solida (4 vitorias nos ultimos 5 jogos) e clean sheet de 48%, "
    "tem maior probabilidade de vitoria fora, mas o cenario de gols tende a ser "
    "equilibrado (lambda fora 1.76, over 2.5 em 57.5% dos jogos). Escanteios com "
    "potencial moderado (media conjunta de 10.34, over 8.5 em 67.9%)."
)

CARD = [
    ApprovedPick(market="Escanteios Over 6.5", classification="NEUTRO",
                 prob_deflated_pct=59, odd=0, ev_pct=0),
    ApprovedPick(market="Cartoes Over 2.5", classification="NEUTRO",
                 prob_deflated_pct=60, odd=0, ev_pct=0),
]


def _violacoes(texto, aprovados):
    return validate_output(texto, aprovados)["violations"]


def test_mencao_nua_de_linha_e_detectada():
    """'over 2.5' sem a palavra 'gols' colada passava batido."""
    v = _violacoes(TEXTO_REAL, CARD)
    assert any("over 2.5" in x.lower() for x in v), v


def test_probabilidade_raw_citada_e_reportada_com_o_numero():
    """A violacao tem de nomear o numero citado, senao nao da para auditar."""
    v = _violacoes(TEXTO_REAL, CARD)
    numericas = [x for x in v if "nao e a publicada" in x]
    assert numericas, v
    assert any("57.5" in x for x in numericas), numericas
    assert any("67.9" in x for x in numericas), numericas


def test_percentual_publicado_nao_gera_violacao():
    """Citar exatamente o que o card mostra e o comportamento correto."""
    texto = ("Escanteios Over 6.5 aparece com 59% apos deflacao e Cartoes Over 2.5 "
             "com 60%. Nenhum outro mercado foi aprovado.")
    assert _violacoes(texto, CARD) == []


def test_tolerancia_de_um_ponto_absorve_arredondamento():
    """O card exibe int(p*100); 59,4% publicado vira '59%' na tela."""
    texto = "Escanteios Over 6.5 com 59.4%."
    assert _violacoes(texto, CARD) == []
    texto_longe = "Escanteios Over 6.5 com 74.4%."
    assert any("nao e a publicada" in x for x in _violacoes(texto_longe, CARD))


def test_percentual_solto_nao_e_tocado():
    """'clean sheet de 48%' nao esta colado a mercado nenhum — nao e violacao."""
    texto = ("Nashville tem clean sheet de 48% e venceu 80% dos jogos fora. "
             "Escanteios Over 6.5 com 59%.")
    v = _violacoes(texto, CARD)
    assert not any("48" in x or "80" in x for x in v), v


def test_percentual_longe_da_mencao_nao_e_atribuido():
    """A janela e curta de proposito: numero a 40+ caracteres nao e daquele mercado."""
    texto = ("Escanteios Over 6.5 com 59%. " + "x" * 60 + " a liga converte 71% das vezes.")
    v = _violacoes(texto, CARD)
    assert not any("71" in x for x in v), v


def test_sem_picks_aprovados_qualquer_numero_de_mercado_e_violacao():
    """pipeline_picks vazio (o caso real): nada pode ser citado com numero."""
    v = _violacoes(TEXTO_REAL, [])
    assert any("57.5" in x for x in v), v
    assert any("nenhuma" in x for x in v), v


def test_mencao_com_familia_colada_continua_casando():
    """O padrao novo nao pode transformar mercado aprovado em falso positivo."""
    aprovado = [ApprovedPick(market="Escanteios Over 8.5", classification="NEUTRO",
                             prob_deflated_pct=67, odd=0, ev_pct=0)]
    texto = "Escanteios Over 8.5 com 67%."
    assert _violacoes(texto, aprovado) == []
