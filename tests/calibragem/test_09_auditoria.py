# -*- coding: utf-8 -*-
"""Teste 8 da spec — nada acontece em silencio.

O #247 achou um gate (odds_value_added < -0,015) que NUNCA disparou em 33
ligas e ninguem sabia. O #246 so encontrou o filtro de corredor porque
[CORRIDOR-DROPPED] vazou no log de um teste. Um sistema que muda o numero
sozinho e so registra quando muda e um sistema onde a inacao e invisivel.
"""
import pytest

from backend.modeling.calibragem.repositorio import (
    carregar_anterior, montar_linha_auditoria,
)

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


# --- Correcao A: curva e limiar mudam juntos, na mesma linha de auditoria ---

def test_com_limiares_a_linha_carrega_os_quatro_valores():
    ln = montar_linha_auditoria("Over/Under", "", versao=4, resultado={
        "a": 0.1, "b": 1.0, "status": "adotada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None, limiares={
        "safe_ev": 0.02, "neutro_ev": 0.0,
        "safe_edge": 0.05, "neutro_edge": 0.01,
    })
    assert ln["safe_ev"] == 0.02
    assert ln["neutro_ev"] == 0.0
    assert ln["safe_edge"] == 0.05
    assert ln["neutro_edge"] == 0.01


def test_sem_limiares_os_quatro_saem_none():
    ln = montar_linha_auditoria("Over/Under", "", versao=4, resultado={
        "a": 0.1, "b": 1.0, "status": "adotada",
        "fator_encurtamento": None, "motivo": "",
    }, n_jogos=50, origem="familia", brier=None)
    assert ln["safe_ev"] is None
    assert ln["neutro_ev"] is None
    assert ln["safe_edge"] is None
    assert ln["neutro_edge"] is None


# --- Correcao B: `carregar_anterior` nao pode devolver o mesmo dict do
# vigente, ou `avaliar_reversao` nunca reverte (dois Briers sempre iguais). ---

def test_carregar_anterior_formato_com_dublê(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    class _CursorFalso:
        def __init__(self, linha):
            self._linha = linha

        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return self._linha

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _ConexaoFalsa:
        def __init__(self, linha):
            self._linha = linha

        def cursor(self):
            return _CursorFalso(self._linha)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(repo, "_conn",
                        lambda: _ConexaoFalsa((5, 0.12, 0.98)))
    anterior = repo.carregar_anterior("BTTS", "")
    assert anterior == {"versao": 5, "a": 0.12, "b": 0.98}


def test_carregar_anterior_devolve_none_quando_nao_existe(monkeypatch):
    import backend.modeling.calibragem.repositorio as repo

    class _CursorVazio:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _ConexaoVazia:
        def cursor(self):
            return _CursorVazio()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(repo, "_conn", lambda: _ConexaoVazia())
    assert repo.carregar_anterior("BTTS", "") is None
