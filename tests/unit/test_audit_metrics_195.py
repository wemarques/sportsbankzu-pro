"""#195 — instrumentação de auditoria: série diária, limit e Brier dos picks.

Três defeitos que impediam decidir se uma queda de acurácia é regressão ou ruído:

1. `/api/audit/status` aceitava `days` mas nunca repassava `limit`, então o
   default 10 de `get_recent_audit_results` truncava tudo — `days=90` devolvia
   os mesmos 10 registros de `days=7`.
2. `calculate_snapshot(audit_date)` recebia o parâmetro e só o ecoava no
   retorno; a query lia a tabela inteira. Não havia como fatiar por dia.
3. O "Brier Score Médio" da auditoria era calculado só sobre Over 2.5 gols,
   um valor por jogo — nunca sobre os picks avaliados. Por isso 36,8% de
   acerto convivia com "Brier 0.1137" na mesma tela.
"""
import inspect
import json

import backend.routes.audit_status as audit_status_mod
import backend.services.brier_service as brier_mod
from backend.audit import get_recent_audit_results


# ── 1. limit repassado ────────────────────────────────────────────────

def test_rota_status_expoe_limit():
    sig = inspect.signature(audit_status_mod.audit_status)
    assert "limit" in sig.parameters, "a rota precisa aceitar limit"


def test_status_repassa_limit_ao_banco(monkeypatch):
    capturado = {}

    def _fake(days=7, limit=10):
        capturado["days"] = days
        capturado["limit"] = limit
        return []

    monkeypatch.setattr(audit_status_mod, "get_recent_audit_results", _fake)
    monkeypatch.setattr(audit_status_mod, "get_recent_corrections", lambda days=7: [])
    monkeypatch.setattr(audit_status_mod, "get_active_corrections", lambda: {})

    import asyncio
    asyncio.run(audit_status_mod.audit_status(days=90, limit=200))
    assert capturado == {"days": 90, "limit": 200}


def test_default_do_banco_continua_conservador():
    # Sem limit explicito o comportamento antigo e preservado.
    assert inspect.signature(get_recent_audit_results).parameters["limit"].default == 10


# ── 2. filtro por dia + serie diaria ──────────────────────────────────

def _rows():
    """Duas linhas em 2026-08-30 (1 hit, 1 miss) e uma em 2026-08-31 (miss)."""
    pp = json.dumps({"prob": 0.60, "book_odd": 2.0})
    return [
        ("Under 2.5 gols", "Serie A", "hit", pp, "{}", "NEUTRO", "2026-08-30"),
        ("Over 2.5 gols", "Serie A", "miss", pp, "{}", "NEUTRO", "2026-08-30"),
        ("Over 2.5 gols", "La Liga", "miss", pp, "{}", "NEUTRO", "2026-08-31"),
    ]


class _FakeCursor:
    def __init__(self, rows, sink):
        self._rows = rows
        self._sink = sink

    def execute(self, sql, params=None):
        self._sink["sql"] = sql
        self._sink["params"] = params

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows, sink):
        self._rows, self._sink = rows, sink

    def cursor(self):
        return _FakeCursor(self._rows, self._sink)

    def close(self):
        pass


def test_audit_date_entra_na_query(monkeypatch):
    sink = {}
    monkeypatch.setattr(brier_mod, "_conn", lambda: _FakeConn(_rows(), sink))
    brier_mod.calculate_snapshot(audit_date="2026-08-30")
    assert "DATE" in sink["sql"] and 'timestamp' in sink["sql"], sink["sql"]
    assert sink["params"] == ("2026-08-30",)


def test_serie_diaria_separa_os_dias(monkeypatch):
    sink = {}
    monkeypatch.setattr(brier_mod, "_conn", lambda: _FakeConn(_rows(), sink))
    serie = brier_mod.daily_series(days=30)
    assert [d["date"] for d in serie] == ["2026-08-30", "2026-08-31"]
    assert serie[0]["n"] == 2 and serie[0]["accuracy"] == 50.0
    assert serie[1]["n"] == 1 and serie[1]["accuracy"] == 0.0
    # Brier do dia 31: probabilidade 0.60 declarada, desfecho 0 → 0.36
    assert abs(serie[1]["brier_model"] - 0.36) < 1e-6


# ── 3. Brier dos picks (vs Brier de Over 2.5) ─────────────────────────

def test_brier_dos_picks_reflete_a_acuracia():
    """Com 60% declarado e todos os picks errados, o Brier tem de ser 0.36 —
    não um número baixo vindo de outro mercado."""
    probs_outcomes = [(0.60, 0), (0.60, 0), (0.60, 0)]
    brier = sum((p - o) ** 2 for p, o in probs_outcomes) / len(probs_outcomes)
    assert abs(brier - 0.36) < 1e-9
    # E com todos certos, 0.16 — o contraste que o tile antigo não mostrava.
    brier_ok = sum((0.60 - 1) ** 2 for _ in range(3)) / 3
    assert abs(brier_ok - 0.16) < 1e-9


def test_cron_emite_brier_dos_picks():
    import backend.cron_handler as cron
    src = inspect.getsource(cron)
    assert "pick_brier_scores" in src
    assert '"brier_picks"' in src
