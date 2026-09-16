# -*- coding: utf-8 -*-
"""#256 — `_resumo`/`_segmento`/`agregado()['acerto']` ganham `resolvidos`
(picks individuais com outcome != null), porque `acertos/jogos` nao e uma
fracao valida: `jogos` conta partidas distintas, `acertos` conta PICKS
individuais corretos, e mais de um pick pode acertar no mesmo jogo (medido em
producao 2026-09-16: picks=73, acertos=38, jogos=37 — 38 > 37 e correto, nao
um bug de dado). `resolvidos` e o denominador que NUNCA fica menor que
`acertos`, por construcao.
"""
from datetime import datetime, timedelta, timezone

from backend.services import ledger_leitura as L

_UTC = timezone.utc


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas

    def execute(self, sql, params=None):
        pass

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


def test_dois_picks_no_mesmo_jogo_acertando_nao_estoura_100_por_cento(monkeypatch):
    """acertos=2, jogos=1 (o caso real de producao, em miniatura) —
    acertos/jogos daria 200%; acertos/resolvidos da 100%, o numero valido."""
    k = datetime(2026, 9, 14, 20, 0, tzinfo=_UTC)
    linhas = [
        _linha("m1", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, detail={"total_goals": 3}),
        _linha("m1", "Corners", "Over 6.5", 0.58, 1.75, "SAFE",
              datetime(2026, 9, 14, 10, 0, tzinfo=_UTC), k, outcome=1, detail={"total_corners": 8}),
    ]
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r = L.dia("2026-09-14")
    assert r["resumo"] == {"picks": 2, "acertos": 2, "jogos": 1, "resolvidos": 2}


def test_segmento_e_agregado_carregam_resolvidos(monkeypatch):
    linhas = []
    base = datetime(2026, 9, 10, 12, 0, tzinfo=_UTC)
    for i in range(25):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(
            f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
            kickoff - timedelta(hours=2), kickoff,
            outcome=1 if i < 15 else 0, detail={"total_goals": 3},
        ))
    # 5 picks nunca resolvidos (outcome None) — contam em `picks`, NAO em `resolvidos`.
    for i in range(25, 30):
        kickoff = base + timedelta(hours=i)
        linhas.append(_linha(f"m{i}", "Over/Under", "Over 2.5", 0.6, 1.8, "SAFE",
                              kickoff - timedelta(hours=2), kickoff, outcome=None))
    monkeypatch.setattr(L, "_conn", lambda: _Conn(linhas))
    r = L.agregado("temporada", hoje=datetime(2026, 9, 20, tzinfo=_UTC))
    assert r["acerto"]["picks"] == 30
    assert r["acerto"]["resolvidos"] == 25
    assert r["acerto"]["acertos"] == 15
    assert r["acerto"]["jogos"] == 25
    # por_familia e por_liga tambem carregam o campo (repasse de _segmento).
    assert r["por_familia"]["Over/Under"]["resolvidos"] == 25
