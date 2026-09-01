# -*- coding: utf-8 -*-
"""#204 - os modulos de modelo estavam mudos no CloudWatch.

12 modulos usam `getLogger(__name__)`, o que os coloca na arvore `backend.*`.
O #164 elevou o nivel apenas de `sportsbankzu`, entao esses ficaram herdando o
root da Lambda (WARNING) e todo `logger.info` sumia — inclusive a linha
`Base Lado:` que existia justamente para verificar o #201.

O default continua WARNING (comportamento identico ao de hoje). LOG_LEVEL_MODELOS
liga a arvore quando for preciso investigar.
"""
import importlib
import logging


def _reload_main(monkeypatch, valor, em_lambda=True):
    if valor is None:
        monkeypatch.delenv("LOG_LEVEL_MODELOS", raising=False)
    else:
        monkeypatch.setenv("LOG_LEVEL_MODELOS", valor)
    if em_lambda:
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "sportsbank-pro-backend")
    else:
        monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    import backend.main as m
    return importlib.reload(m)


def test_default_na_lambda_nao_muda_nada(monkeypatch):
    _reload_main(monkeypatch, None, em_lambda=True)
    assert logging.getLogger("backend").level == logging.WARNING


def test_default_fora_da_lambda_preserva_o_local(monkeypatch):
    """#204b - fixar WARNING apagaria logs que o dev local ja via.

    Na Lambda o basicConfig e no-op (root em WARNING) e o default WARNING e
    inocuo. Fora dela o basicConfig funciona e poe o root em INFO, entao o
    default tem de herdar _LOG_LEVEL em vez de rebaixar a arvore.
    """
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    _reload_main(monkeypatch, None, em_lambda=False)
    assert logging.getLogger("backend").level == logging.INFO
    assert logging.getLogger("backend.modeling.lambda_calculator").isEnabledFor(logging.INFO)


def test_env_liga_a_arvore_backend(monkeypatch):
    _reload_main(monkeypatch, "INFO")
    assert logging.getLogger("backend").level == logging.INFO
    # o modulo do lambda herda o nivel, e nao so o pai
    assert logging.getLogger("backend.modeling.lambda_calculator").isEnabledFor(logging.INFO)


def test_nao_afeta_o_namespace_proprio(monkeypatch):
    _reload_main(monkeypatch, "WARNING")
    assert logging.getLogger("sportsbankzu").level == logging.INFO


def test_lambda_calculator_esta_mesmo_na_arvore_backend():
    import backend.modeling.lambda_calculator as lc
    assert lc.logger.name.startswith("backend."), lc.logger.name
