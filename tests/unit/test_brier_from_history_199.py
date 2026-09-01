"""#199 — /metrics/brier passa a servir o último snapshot gravado.

Recalcular tudo a cada carregamento do dashboard lia `audit_results` inteira e
segmentava por liga, mercado, banda, classificação e liga×mercado. Entre dois
batches o resultado é idêntico — era trabalho jogado fora, e passou a estourar
o timeout de 15s da rota do front (503 reproduzível em 4 tentativas, 15,2s,
enquanto /metrics/brier/daily respondia em 3,4s).

O ponto delicado: as colunas soltas de `brier_history` NÃO guardam
`model_beats_house_ci` (que o ReliabilityCard lê) nem os campos do #197.
Servir o card a partir delas quebraria a tela — por isso o payload inteiro vai
para uma coluna JSONB.
"""
import json
from datetime import datetime, timedelta

import backend.services.brier_service as bs


SNAP = {
    "total_picks": 5915,
    "n": 5915,
    "accuracy": 73.8,
    "brier_model": 0.2167,
    "brier_model_paired": 0.2170,
    "brier_implied": 0.2293,
    "n_paired": 5844,
    "delta": 0.0126,
    "model_beats_house": True,
    "model_beats_house_ci": {"beats_bool": True, "delta": 0.01262, "p_value": 0.00074, "n": 5844},
    "by_league": {}, "by_market": {}, "by_band": {}, "by_classification": {},
    "audit_date": "2026-08-31",
}


def _conn_returning(row, sink=None):
    class Cur:
        def execute(self, sql, params=None):
            if sink is not None:
                sink.setdefault("sqls", []).append(sql)
                sink.setdefault("params", []).append(params)
        def fetchone(self):
            return row
        def fetchall(self):
            return []
        def close(self):
            pass
    class Conn:
        def cursor(self):
            return Cur()
        def commit(self):
            pass
        def close(self):
            pass
    return Conn()


def test_snapshot_do_historico_preserva_o_ci_que_o_card_le(monkeypatch):
    ts = datetime.utcnow() - timedelta(minutes=95)
    monkeypatch.setattr(bs, "_conn", lambda: _conn_returning((json.dumps(SNAP), ts)))
    snap = bs.latest_snapshot()
    assert snap is not None
    # o campo que quebraria o ReliabilityCard se viesse das colunas soltas
    assert snap["model_beats_house_ci"]["p_value"] == 0.00074
    # e os campos do #197, que tambem nao tem coluna propria
    assert snap["n_paired"] == 5844
    assert snap["brier_model_paired"] == 0.2170


def test_idade_vai_explicita_no_payload(monkeypatch):
    ts = datetime.utcnow() - timedelta(minutes=95)
    monkeypatch.setattr(bs, "_conn", lambda: _conn_returning((json.dumps(SNAP), ts)))
    snap = bs.latest_snapshot()
    assert snap["_fromHistory"] is True
    assert 94 <= snap["_ageMinutes"] <= 96, snap["_ageMinutes"]
    assert snap["_snapshotAt"]


def test_sem_snapshot_gravado_devolve_none(monkeypatch):
    """Primeira execucao pos-deploy: a rota tem de cair no recalculo."""
    monkeypatch.setattr(bs, "_conn", lambda: _conn_returning(None))
    assert bs.latest_snapshot() is None
    monkeypatch.setattr(bs, "_conn", lambda: _conn_returning((None, datetime.utcnow())))
    assert bs.latest_snapshot() is None


def test_falha_de_banco_nao_derruba_a_rota(monkeypatch):
    def _boom():
        raise Exception("connection refused")
    monkeypatch.setattr(bs, "_conn", _boom)
    assert bs.latest_snapshot() is None


def test_persist_grava_o_payload_completo(monkeypatch):
    sink = {}
    monkeypatch.setattr(bs, "_conn", lambda: _conn_returning(None, sink))
    monkeypatch.setattr(bs, "_ensure_table", lambda: None)
    assert bs.persist_snapshot(SNAP, new_picks=12) is True
    insert = [q for q in sink["sqls"] if "INSERT INTO brier_history" in q][0]
    assert "snapshot" in insert
    params = sink["params"][sink["sqls"].index(insert)]
    gravado = json.loads(params[-1])
    assert gravado["model_beats_house_ci"]["p_value"] == 0.00074
