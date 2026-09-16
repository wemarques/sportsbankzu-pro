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
