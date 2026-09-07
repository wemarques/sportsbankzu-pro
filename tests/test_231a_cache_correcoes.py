# -*- coding: utf-8 -*-
"""#231-a - o banco de correcoes era aberto 48 vezes por jogo.

Medido com contador em backend.audit.get_active_corrections:
  evaluate_match_markets x3 (1 liga) ........ 144 conexoes -> 1
  calcular_lambda_jogo x100 (backfill) ...... 200 conexoes -> 0 (depois da 1a)
Com DATABASE_URL no .env, o backfill de 22 ligas virou 31 mil conexoes a RDS
e parecia travado (CPU 0%). Correcoes so mudam quando o calibrador roda;
cache por liga com TTL.
"""
import copy

import pytest

import backend.audit as audit
from backend.modeling import lambda_calculator as LC


@pytest.fixture(autouse=True)
def _cache_limpo(monkeypatch):
    monkeypatch.delenv("LAMBDA_CORRECTIONS_TTL_S", raising=False)
    LC.limpar_cache_correcoes()
    yield
    LC.limpar_cache_correcoes()


def _contador(monkeypatch, resposta=None, erro=None):
    n = {"chamadas": 0}

    def _fake(league=None):
        n["chamadas"] += 1
        if erro:
            raise erro
        return dict(resposta or {})
    monkeypatch.setattr(audit, "get_active_corrections", _fake)
    return n


def test_uma_conexao_por_liga_dentro_do_ttl(monkeypatch):
    n = _contador(monkeypatch, {"home_advantage_gamma": {"value": 1.05}})
    for _ in range(50):
        assert LC.get_lambda_corrections("championship")["home_advantage_gamma"]["value"] == 1.05
    assert n["chamadas"] == 1
    LC.get_lambda_corrections("la-liga")
    assert n["chamadas"] == 2                      # liga diferente, leitura nova


def test_ttl_zero_desliga_o_cache(monkeypatch):
    monkeypatch.setenv("LAMBDA_CORRECTIONS_TTL_S", "0")
    n = _contador(monkeypatch)
    for _ in range(5):
        LC.get_lambda_corrections("championship")
    assert n["chamadas"] == 5


def test_ttl_expirado_releh(monkeypatch):
    n = _contador(monkeypatch)
    relogio = {"t": 1000.0}
    monkeypatch.setattr(LC.time, "monotonic", lambda: relogio["t"])
    LC.get_lambda_corrections("championship")
    relogio["t"] += 299
    LC.get_lambda_corrections("championship")
    assert n["chamadas"] == 1
    relogio["t"] += 2
    LC.get_lambda_corrections("championship")
    assert n["chamadas"] == 2


def test_falha_do_banco_tambem_e_cacheada_e_devolve_vazio(monkeypatch):
    n = _contador(monkeypatch, erro=RuntimeError("banco fora"))
    for _ in range(10):
        assert LC.get_lambda_corrections("championship") == {}
    assert n["chamadas"] == 1                      # uma tentativa por liga por TTL


def test_quem_le_nao_altera_o_cache(monkeypatch):
    _contador(monkeypatch, {"lambda_home_multiplier": {"value": 1.1}})
    a = LC.get_lambda_corrections("championship")
    a["lambda_home_multiplier"]["value"] = 9.9
    a["novo"] = 1
    b = LC.get_lambda_corrections("championship")
    assert "novo" not in b


def test_pipeline_abre_o_banco_uma_vez_por_liga(monkeypatch):
    """A medicao que motivou o fix, como teste: 3 jogos, 1 leitura."""
    from backend.services.ev_classification import evaluate_match_markets
    from tests.test_231_prob_source import _MATCH
    n = _contador(monkeypatch)
    for _ in range(3):
        evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    assert n["chamadas"] == 1
