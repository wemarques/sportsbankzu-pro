# -*- coding: utf-8 -*-
"""#207 - um cliente FootyStats por processo, e instrumentacao do /lastx.

`_fetch_lastx_for_team` criava um FootyStatsClient NOVO a cada chamada. No
Championship sao 16 (8 jogos x 2 times), e cada __init__ roda _init_db(): abre
o SQLite do /tmp, CREATE TABLE IF NOT EXISTS, commit. Com os 3 workers do #115
em paralelo, sao 16 transacoes de ESCRITA disputando o mesmo arquivo, alem das
escritas legitimas do cache.

Medido em producao (Function URL, 1 liga por pedido):
  0 jogos ..... 1,8-2,9s      7 jogos (league-one) .... 30,0s
  1 jogo ...... 6,0s          8 jogos (championship) .. 35,2s / 37,6s
Ou seja ~4,5s por jogo, MESMO com o paralelismo de 3 vias do #115 ligado - e
uma chamada isolada de /lastx custa ~1,8s. A conta so fecha com contencao.
"""
import backend.services.footstats_client as fc


def test_cliente_compartilhado_e_a_mesma_instancia(monkeypatch):
    monkeypatch.setattr(fc, "_shared_client", None)
    a = fc.get_shared_client()
    b = fc.get_shared_client()
    assert a is b
    assert isinstance(a, fc.FootyStatsClient)


def test_cliente_compartilhado_e_thread_safe(monkeypatch):
    import threading
    monkeypatch.setattr(fc, "_shared_client", None)
    vistos = []
    barreira = threading.Barrier(8)

    def _corre():
        barreira.wait()
        vistos.append(fc.get_shared_client())

    ts = [threading.Thread(target=_corre) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    assert len(vistos) == 8
    assert len(set(id(c) for c in vistos)) == 1, "mais de uma instancia criada"


def test_fetch_lastx_usa_o_cliente_compartilhado(monkeypatch):
    """O ponto do patch: 16 chamadas nao podem virar 16 instancias."""
    import backend.services.fixtures_service as fs

    monkeypatch.setattr(fc, "_shared_client", None)
    criadas = {"n": 0}
    orig = fc.FootyStatsClient.__init__

    def _conta(self, *a, **k):
        criadas["n"] += 1
        orig(self, *a, **k)

    monkeypatch.setattr(fc.FootyStatsClient, "__init__", _conta)
    monkeypatch.setattr(
        fc.FootyStatsClient, "get_team_lastx", lambda self, tid, **k: {"success": True, "data": []}
    )

    for team_id in range(1, 17):
        fs._fetch_lastx_for_team(team_id)

    assert criadas["n"] == 1, f"criou {criadas['n']} clientes em 16 chamadas"


def test_log_de_custo_do_lastx_sai_uma_vez_por_liga(caplog):
    import logging
    import backend.services.fixtures_service as fs

    with caplog.at_level(logging.INFO, logger="sportsbankzu"):
        fs._log_lastx_stats("championship", 8, {"buscas": 16, "ms_total": 28800.0, "ms_pior": 3100.0, "memo": 0})

    linhas = [r.message for r in caplog.records if "#207 lastx" in r.message]
    assert len(linhas) == 1
    assert "championship" in linhas[0]
    assert "16 times buscados" in linhas[0]
    assert "1800ms" in linhas[0]        # media


def test_log_nao_sai_quando_nada_foi_buscado(caplog):
    import logging
    import backend.services.fixtures_service as fs

    with caplog.at_level(logging.INFO, logger="sportsbankzu"):
        fs._log_lastx_stats("mls", 0, {"buscas": 0, "ms_total": 0.0, "ms_pior": 0.0, "memo": 0})

    assert not [r for r in caplog.records if "#207 lastx" in r.message]
