# -*- coding: utf-8 -*-
"""#256 — `dia(data)` e o dia-calendario do operador (America/Sao_Paulo, UTC-3 fixo):
janela [data 03:00Z, data+1 03:00Z). Antes era o dia UTC e um jogo de 22:07 BRT
caia no dia seguinte. Mesmos doubles de tests/test_256_resolvidos.py."""
from datetime import datetime, timedelta, timezone

import backend.services.ledger_leitura as L
from tests.test_256_resolvidos import _Conn, _linha

_UTC = timezone.utc


def _um_pick(kickoff):
    return [_linha("m1", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
                   kickoff - timedelta(hours=10), kickoff, outcome=1, detail={"total_goals": 3})]


def test_jogo_das_22h07_brt_pertence_ao_dia_brt_e_nao_ao_dia_utc(monkeypatch):
    k = datetime(2026, 9, 14, 1, 7, tzinfo=_UTC)          # 13/09 22:07 BRT
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_um_pick(k)))
    assert [p["match_id"] for p in L.dia("2026-09-13")["picks"]] == ["m1"]
    assert L.dia("2026-09-14")["picks"] == []


def test_limites_da_janela_brt(monkeypatch):
    dentro = datetime(2026, 9, 14, 3, 0, tzinfo=_UTC)     # 14/09 00:00 BRT — primeiro instante do dia
    fora = datetime(2026, 9, 15, 3, 0, tzinfo=_UTC)       # 15/09 00:00 BRT — ja e o dia seguinte
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_um_pick(dentro)))
    assert len(L.dia("2026-09-14")["picks"]) == 1
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_um_pick(fora)))
    assert L.dia("2026-09-14")["picks"] == []


def test_acumulados_semana_e_mes_seguem_o_mesmo_relogio(monkeypatch):
    k = datetime(2026, 9, 14, 1, 7, tzinfo=_UTC)          # 13/09 BRT
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_um_pick(k)))
    r = L.dia("2026-09-13")
    assert r["resumo"]["picks"] == 1
    assert r["semana"]["Over/Under"]["picks"] == 1 and r["mes"]["Over/Under"]["picks"] == 1
