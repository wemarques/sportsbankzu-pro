# -*- coding: utf-8 -*-
"""#257 — GET /ledger/picks: linhas individuais resolvidas do periodo, para o
/desempenho calcular o retorno retroativo no cliente (stake nunca gravado no
ledger). `picks()` usa a MESMA janela e o MESMO filtro de `agregado()`
(_janela_periodo, _buscar_janela, classificar_familia) — o teste principal
prova que as duas contagens batem nos mesmos dublês."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ledger_leitura as L
from tests.test_256_resolvidos import _Conn, _linha

_UTC = timezone.utc
client = TestClient(app)


def test_len_picks_bate_com_acerto_resolvidos_do_agregado(monkeypatch):
    linhas = []
    base = datetime(2026, 9, 10, 12, 0, tzinfo=_UTC)
    for i in range(25):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(
            f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < 15 else 0, detail={"total_goals": 3},
        ))
    for i in range(25, 30):  # 5 picks sem desfecho — nao entram em picks()
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
                              kickoff - timedelta(hours=2), kickoff, outcome=None))
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    hoje = datetime(2026, 9, 20, tzinfo=_UTC)
    agregado = L.agregado("temporada", hoje=hoje)
    picks = L.picks("temporada", hoje=hoje)
    assert len(picks["picks"]) == agregado["acerto"]["resolvidos"] == 25
    assert all(p["outcome"] is not None for p in picks["picks"])


def test_picks_filtra_por_familia_e_liga_como_agregado(monkeypatch):
    k = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, league_id="mls"),
        _linha("m2", "Corners", "Over 6.5", 0.58, 1.75, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, league_id="premier-league"),
    ]
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    hoje = datetime(2026, 9, 20, tzinfo=_UTC)
    r = L.picks("temporada", familia="Over/Under", hoje=hoje)
    assert len(r["picks"]) == 1
    assert r["picks"][0]["match_id"] == "m1"
    r2 = L.picks("temporada", liga="premier-league", hoje=hoje)
    assert len(r2["picks"]) == 1
    assert r2["picks"][0]["match_id"] == "m2"


def test_rota_ledger_picks_registrada_e_ok(monkeypatch):
    monkeypatch.setattr(L, "picks", lambda periodo, familia=None, liga=None: {
        "periodo": periodo, "familia": familia, "liga": liga, "picks": [],
    })
    r = client.get("/ledger/picks", params={"periodo": "7d"})
    assert r.status_code == 200
    assert r.json()["periodo"] == "7d"
    assert "/ledger/picks" in app.openapi()["paths"]


def test_rota_ledger_picks_periodo_invalido_400(monkeypatch):
    def _falha(periodo, familia=None, liga=None):
        raise ValueError(f"periodo invalido: {periodo!r}")
    monkeypatch.setattr(L, "picks", _falha)
    r = client.get("/ledger/picks", params={"periodo": "1ano"})
    assert r.status_code == 400
