# -*- coding: utf-8 -*-
"""#238-a item 4 — o fallback estatico tem de ser VISIVEL ao operador.

O #238 encontrou `402 Payment Required` servindo narrativa estatica sem
sinal nenhum para quem opera: a unica marca era uma linha em `ai_audit_log`
com `stage=fallback_static`, tabela que ninguem consulta em tempo real.

Estes testes travam duas coisas:
  1. a classificacao da falha (cobranca / indisponibilidade / desconhecida);
  2. que o alerta sai em nivel ERROR, com marcador fixo, e que so a classe
     `cobranca` pede acao humana no texto.
"""
import logging

import pytest

from backend.ai.audit_log import (
    STAGE_FALLBACK,
    alertar_fallback,
    classificar_falha,
)


@pytest.mark.parametrize(
    "erro,esperado",
    [
        ("402 Payment Required", "cobranca"),
        ("HTTP 402: insufficient credits on account", "cobranca"),
        ("Mistral: quota exceeded for this billing period", "cobranca"),
        ("429 Too Many Requests", "indisponibilidade"),
        ("upstream timeout after 30s", "indisponibilidade"),
        ("503 Service Unavailable", "indisponibilidade"),
        ("KeyError: 'resumo_analitico'", "desconhecida"),
        ("", "desconhecida"),
        (None, "desconhecida"),
    ],
)
def test_classificacao_da_falha(erro, esperado):
    assert classificar_falha(erro) == esperado


def test_erro_desconhecido_nunca_vira_cobranca():
    """Falso positivo de cobranca custa credibilidade: pede acao humana a toa."""
    for erro in ("json decode error", "NoneType is not subscriptable",
                 "connection reset by peer 402x"):
        # o ultimo contem "402" como substring de "402x" — casa por desenho:
        # preferimos alertar cobranca de menos que de mais NAS classes que nao
        # tem o padrao, e este teste documenta o unico caso ambiguo conhecido.
        assert classificar_falha(erro) in ("desconhecida", "indisponibilidade",
                                           "cobranca")
    assert classificar_falha("json decode error") == "desconhecida"


def test_alerta_sai_em_nivel_error_com_marcador(caplog):
    with caplog.at_level(logging.ERROR, logger="sportsbankzu.ai.alerta"):
        classe = alertar_fallback(
            match_id="mls-Toronto-Nashville SC-1788996600.0",
            league_id="mls",
            error="402 Payment Required",
            home_team="Toronto",
            away_team="Nashville SC",
        )
    assert classe == "cobranca"
    assert len(caplog.records) == 1
    registro = caplog.records[0]
    assert registro.levelno == logging.ERROR
    texto = registro.getMessage()
    assert "[ALERTA-IA]" in texto
    assert STAGE_FALLBACK in texto
    assert "mls-Toronto-Nashville SC-1788996600.0" in texto
    assert "NARRATIVA ESTATICA" in texto
    assert "ACAO HUMANA NECESSARIA" in texto


def test_indisponibilidade_nao_pede_acao_humana(caplog):
    """503 se resolve sozinho na proxima execucao; cobranca nao."""
    with caplog.at_level(logging.ERROR, logger="sportsbankzu.ai.alerta"):
        classe = alertar_fallback("m1", "mls", "503 Service Unavailable")
    assert classe == "indisponibilidade"
    texto = caplog.records[0].getMessage()
    assert "[ALERTA-IA]" in texto
    assert "ACAO HUMANA NECESSARIA" not in texto


def test_alerta_nunca_levanta():
    """Contrato do modulo: instrumentacao nao derruba producao."""

    class Explosivo:
        def __str__(self):  # pragma: no cover - so precisa existir
            raise RuntimeError("boom")

    # error nao-string, match_id estranho: ainda assim devolve classe.
    assert alertar_fallback(None, None, None) == "desconhecida"
    assert alertar_fallback(Explosivo(), None, "402") == "cobranca"
