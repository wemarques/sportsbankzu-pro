# -*- coding: utf-8 -*-
"""#252-b - os outros consumidores de `calibrated_prob` aplicam #252 e #252-a.

`medir_inclinacao.py` e `grade_deflacao_por_familia.py` liam o ledger inteiro:
geracao pos-apito (#252) e a janela em que a coluna era a camada (#252-a). Os
filtros vivem em UM modulo, `scripts/amostra_ledger.py`; os tres scripts o
importam em vez de reimplementar (proibicao 5).
"""
import importlib.util
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
_UTC = timezone.utc


def _carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, _RAIZ / "scripts" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# kickoff 13/09 11:30 UTC
_JOGO = "2-bundesliga-Heidenheim-Holstein Kiel-1789299000.0"
_PRE = datetime(2026, 9, 10, 20, 0, tzinfo=_UTC)       # antes do apito e da janela
_POS = datetime(2026, 9, 14, 5, 0, tzinfo=_UTC)        # depois do apito
_OUTRO = "premier-league-A-B-1789900000.0"             # kickoff 20/09
_CONTAM = datetime(2026, 9, 12, 12, 0, tzinfo=_UTC)    # dentro da janela #252-a


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas

    def execute(self, sql, params=None):
        self.sql = sql

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


def test_medir_inclinacao_so_pre_apito_e_fora_da_janela(monkeypatch, capsys):
    M = _carregar("medir_inclinacao")
    # match_id, league_id, market, prob, outcome, published_at, kickoff_utc
    linhas = [
        (_JOGO, "x", "Over 2.5", 0.6, 1, _PRE, None),     # fica
        (_JOGO, "x", "Over 2.5", 0.6, 1, _POS, None),     # pos-apito
        (_OUTRO, "x", "Over 2.5", 0.6, 0, _CONTAM, None), # janela contaminada
    ]
    conn = _Conn(linhas)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setitem(sys.modules, "psycopg2",
                        types.SimpleNamespace(connect=lambda *a, **k: conn))
    picks = M._do_ledger("2026-09-03", "calibrated_prob")
    assert [p["match_id"] for p in picks] == [_JOGO]
    assert "l.published_at, l.kickoff_utc" in conn.cur.sql
    saida = capsys.readouterr().out
    assert "#252" in saida and "#252-a" in saida


def test_medir_inclinacao_raw_prob_nao_perde_a_janela(monkeypatch):
    M = _carregar("medir_inclinacao")
    conn = _Conn([(_OUTRO, "x", "Over 2.5", 0.6, 0, _CONTAM, None)])
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setitem(sys.modules, "psycopg2",
                        types.SimpleNamespace(connect=lambda *a, **k: conn))
    assert len(M._do_ledger("2026-09-03", "raw_prob")) == 1


def test_grade_deflacao_so_pre_apito_e_fora_da_janela(capsys):
    G = _carregar("grade_deflacao_por_familia")
    # match_id, market, selection, league_id, raw, calibrated, outcome, published_at, kickoff_utc
    conn = _Conn([
        (_JOGO, "Corners", "Over 9.5", "x", 0.6, 0.55, 1, _PRE, None),
        (_JOGO, "Corners", "Over 9.5", "x", 0.6, 0.55, 1, _POS, None),
        (_OUTRO, "Corners", "Over 9.5", "x", 0.6, 0.55, 0, _CONTAM, None),
    ])
    picks = G.carregar(conn)
    assert [p["match_id"] for p in picks] == [_JOGO]
    assert "l.published_at, l.kickoff_utc" in conn.cur.sql
    saida = capsys.readouterr().out
    assert "#252" in saida and "#252-a" in saida


def test_filtro_existe_em_um_modulo_so():
    C = _carregar("comparar_com_mercado")
    A = importlib.import_module("scripts.amostra_ledger")   # o MESMO objeto que C importou
    assert C._so_pre_jogo is A.so_pre_jogo
    assert C._kickoff_da_linha is A.kickoff_da_linha
    assert C._fora_da_janela_contaminada is A.fora_da_janela_contaminada
    assert C._JANELA_CONTAMINADA_251 == A.JANELA_CONTAMINADA_251
    for nome in ("comparar_com_mercado", "medir_inclinacao", "grade_deflacao_por_familia"):
        src = (_RAIZ / "scripts" / f"{nome}.py").read_text(encoding="utf-8")
        assert "fromtimestamp" not in src and "datetime(2026, 9, 10" not in src, nome
