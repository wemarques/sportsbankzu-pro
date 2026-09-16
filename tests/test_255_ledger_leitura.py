# -*- coding: utf-8 -*-
"""#255 — `backend/services/ledger_leitura.py`: leitura pura do ledger.

Dublê de conexao no padrao de `tests/test_252b_consumidores_do_ledger.py`:
uma classe `_Cursor`/`_Conn` que devolve linhas fixas para `execute`/
`fetchall`, sem tocar rede. `ledger_leitura._conn` e substituida direto —
mais simples que interceptar `psycopg2.connect` global, e nao ha guarda
autouse fora de `tests/calibragem/` proibindo o real (por isso a
substituicao explicita e obrigatoria em CADA teste que chama `dia`/`agregado`).
"""
from datetime import datetime, timedelta, timezone

import pytest

from backend.services import ledger_leitura as L

_UTC = timezone.utc


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._linhas

    def close(self):
        pass


class _Conn:
    def __init__(self, linhas):
        self.cur = _Cursor(linhas)

    def cursor(self):
        return self.cur

    def close(self):
        pass


def _linha(match_id, market, selection, prob, book_odd, classification,
          published_at, kickoff_utc, outcome=None, detail=None,
          league_id="premier-league"):
    return (match_id, league_id, market, selection, prob, book_odd,
            classification, published_at, kickoff_utc, outcome, detail)


# Um jogo com kickoff em 14/09, duas geracoes (so a ultima pre-kickoff conta).
_M1 = "premier-league-A-B-1789344000.0"          # 2026-09-14
_K1 = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
# Corners NEUTRO_QUALIFICADO no mesmo jogo — conta e aparece.
_M2 = "premier-league-C-D-1789344000.0"
# BTTS NEUTRO — aparece na lista, nao conta no resumo.
_M3 = "premier-league-E-F-1789344000.0"
# 1X2 NO_BET — nunca aparece (cortado na propria consulta).
_M4 = "premier-league-G-H-1789344000.0"
# Publicado APOS o kickoff (#252) — sumiu mesmo sem NO_BET.
_M5 = "premier-league-I-J-1789344000.0"
_K5 = datetime(2026, 9, 14, 18, 0, tzinfo=_UTC)


def _linhas_do_dia():
    return [
        # M1: geracao antiga (perde) + geracao nova (vence)
        _linha(_M1, "Over/Under", "Over 2.5", 0.62, 1.75, "SAFE",
              datetime(2026, 9, 12, 9, 0, tzinfo=_UTC), _K1),
        _linha(_M1, "Over/Under", "Over 2.5", 0.58, 1.80, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), _K1,
              outcome=1, detail={"total_goals": 3}),
        _linha(_M2, "Corners", "Corners Over 6.5", 0.60, None, "NEUTRO_QUALIFICADO",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1,
              outcome=0, detail={"total_corners": 5}),
        _linha(_M3, "BTTS", "BTTS Yes", 0.55, 1.90, "NEUTRO",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1,
              outcome=1, detail={"btts": True}),
        _linha(_M4, "1X2", "Home", 0.70, 1.20, "NO_BET",
              datetime(2026, 9, 14, 9, 0, tzinfo=_UTC), _K1),
        _linha(_M5, "Cards", "Over 3.5", 0.60, 1.80, "SAFE",
              datetime(2026, 9, 14, 19, 0, tzinfo=_UTC), _K5),  # pos-kickoff
    ]


def test_dia_lista_a_ultima_geracao_pre_kickoff(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    por_match = {p["match_id"]: p for p in r["picks"]}
    assert por_match[_M1]["published_prob"] == 0.58          # a geracao NOVA
    assert por_match[_M1]["fair_odd"] == round(1 / 0.58, 2)
    assert por_match[_M1]["detail"] == "3 gols"


def test_dia_no_bet_nunca_aparece(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M4 not in {p["match_id"] for p in r["picks"]}


def test_dia_pos_kickoff_some_242(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M5 not in {p["match_id"] for p in r["picks"]}


def test_dia_neutro_aparece_mas_nao_conta(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    assert _M3 in {p["match_id"] for p in r["picks"]}          # listado
    # resumo so conta SAFE/NEUTRO_QUALIFICADO: M1 (SAFE) + M2 (NQ) = 2
    assert r["resumo"]["picks"] == 2


def test_dia_resumo_acertos_e_jogos(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_do_dia()))
    r = L.dia("2026-09-14")
    # M1 outcome=1 (acerto), M2 outcome=0 (erro) — os dois contados
    assert r["resumo"]["acertos"] == 1
    assert r["resumo"]["jogos"] == 2


def test_dia_data_invalida_levanta_value_error(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn([]))
    with pytest.raises(ValueError):
        L.dia("14-09-2026")


def test_detalhe_textual_por_familia():
    assert L._detalhe_textual("Corners", {"total_corners": 8}) == "8 escanteios"
    assert L._detalhe_textual("Cards", {"total_cards": 4}) == "4 cartões"
    assert L._detalhe_textual("Over/Under", {"total_goals": 3}) == "3 gols"
    assert L._detalhe_textual("BTTS", {"btts": True}) == "ambos marcaram"
    assert L._detalhe_textual("BTTS", {"btts": False}) == "só um marcou (ou nenhum)"
    assert L._detalhe_textual("Corners", None) is None
    assert L._detalhe_textual("Corners", {}) is None


def _linhas_agregado(n_jogos, acertos):
    """`n_jogos` picks Over/Under distintos, `acertos` deles com outcome=1."""
    base = datetime(2026, 9, 5, 12, 0, tzinfo=_UTC)
    out = []
    for i in range(n_jogos):
        mid = f"premier-league-T{i}-U{i}-{1788000000 + i * 10000}.0"
        kickoff = base + timedelta(hours=i)
        out.append(_linha(
            mid, "Over/Under", "Over 2.5", 0.55 + (i % 10) * 0.01, 1.80, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < acertos else 0, detail={"total_goals": 3},
        ))
    return out


def test_agregado_abaixo_do_piso_vem_null(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(10, 6)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["amostra_curta"] is True
    assert r["brier"] is None
    assert r["buckets"] is None
    assert r["acerto"]["jogos"] == 10


def test_agregado_acima_do_piso_calcula(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(25, 15)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["amostra_curta"] is False
    assert r["brier"] is not None
    assert r["buckets"] is not None
    assert len(r["buckets"]) == 10
    assert sum(b["n"] for b in r["buckets"]) == 25


def test_agregado_retorno_e_sempre_null_com_motivo(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn(_linhas_agregado(25, 15)))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["retorno"] == {
        "valor": None, "pct_banca": None,
        "motivo": "stake_nao_gravado_no_ledger",
    }


def test_agregado_periodo_invalido_levanta_value_error(monkeypatch):
    monkeypatch.setattr(L, "_conn", lambda: _Conn([]))
    with pytest.raises(ValueError):
        L.agregado("1ano")


def test_agregado_filtra_por_familia_e_liga(monkeypatch):
    linhas = _linhas_agregado(25, 15)  # todos premier-league, Over/Under
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r_familia_errada = L.agregado("temporada", familia="Corners",
                                  hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r_familia_errada["acerto"]["picks"] == 0
    r_liga_certa = L.agregado("temporada", liga="premier-league",
                              hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r_liga_certa["acerto"]["jogos"] == 25
