# -*- coding: utf-8 -*-
"""#255 — contrato HTTP de `/ledger/dia` e `/ledger/agregado`.

A logica de consulta ja e testada em `test_255_ledger_leitura.py` com dublê
de conexão; aqui so o roteamento — substitui `ledger_leitura.dia`/`agregado`
por funcoes fake (nenhuma delas toca banco).
"""
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ledger_leitura

client = TestClient(app)


def test_dia_ok(monkeypatch):
    monkeypatch.setattr(ledger_leitura, "dia", lambda data: {"data": data, "picks": []})
    r = client.get("/ledger/dia", params={"data": "2026-09-14"})
    assert r.status_code == 200
    assert r.json()["data"] == "2026-09-14"


def test_dia_data_invalida_400(monkeypatch):
    def _falha(data):
        raise ValueError(f"data invalida: {data!r}")
    monkeypatch.setattr(ledger_leitura, "dia", _falha)
    r = client.get("/ledger/dia", params={"data": "lixo"})
    assert r.status_code == 400


def test_dia_falha_de_banco_503(monkeypatch):
    def _falha(data):
        raise RuntimeError("DATABASE_URL nao esta definida")
    monkeypatch.setattr(ledger_leitura, "dia", _falha)
    r = client.get("/ledger/dia", params={"data": "2026-09-14"})
    assert r.status_code == 503


def test_dia_sem_parametro_e_422_do_fastapi():
    r = client.get("/ledger/dia")
    assert r.status_code == 422        # Query(...) obrigatorio — validacao do FastAPI


def test_agregado_ok_com_filtros(monkeypatch):
    recebido = {}

    def _fake(periodo, familia=None, liga=None):
        recebido.update(periodo=periodo, familia=familia, liga=liga)
        return {"periodo": periodo, "familia": familia, "liga": liga}

    monkeypatch.setattr(ledger_leitura, "agregado", _fake)
    r = client.get("/ledger/agregado", params={
        "periodo": "7d", "familia": "Corners", "liga": "premier-league",
    })
    assert r.status_code == 200
    assert recebido == {"periodo": "7d", "familia": "Corners", "liga": "premier-league"}


def test_agregado_periodo_padrao_30d(monkeypatch):
    recebido = {}

    def _fake(periodo, familia=None, liga=None):
        recebido["periodo"] = periodo
        return {}

    monkeypatch.setattr(ledger_leitura, "agregado", _fake)
    client.get("/ledger/agregado")
    assert recebido["periodo"] == "30d"


def test_agregado_periodo_invalido_400(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise ValueError(f"periodo invalido: {periodo!r}")
    monkeypatch.setattr(ledger_leitura, "agregado", _falha)
    r = client.get("/ledger/agregado", params={"periodo": "1ano"})
    assert r.status_code == 400


def test_agregado_falha_de_banco_503(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise RuntimeError("conexao recusada")
    monkeypatch.setattr(ledger_leitura, "agregado", _falha)
    r = client.get("/ledger/agregado")
    assert r.status_code == 503


def test_rotas_registradas_no_app():
    paths = {r.path for r in app.routes}
    assert "/ledger/dia" in paths
    assert "/ledger/agregado" in paths
