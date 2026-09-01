"""#197 — duas regressões encontradas no red team do #195/#196.

1. `run_after_audit(audit_date=date_filter)` recebe o RÓTULO do cron
   ("today"/"yesterday"), não uma data. O #195 injetou isso num
   `DATE("timestamp") = %s`; o Postgres recusa, o except engolia, o snapshot
   voltava None e `persist_snapshot` nunca rodava — o snapshot noturno parou
   de ser gravado, em silêncio.

2. `_segment` pareava odds filtradas com desfechos NÃO filtrados
   (`outs[:len(odds)]`). Passava batido porque quase todo pick tinha odd; o
   #196 (book_odd só quando a odd é real) deixaria ~1/3 sem odd e o
   brier_implied viraria ruído.
"""
import json

import pytest

import backend.services.brier_service as bs


# ── 1. rótulo do cron não pode virar filtro ───────────────────────────

@pytest.mark.parametrize("rotulo", ["today", "yesterday", "week", "", None])
def test_rotulo_nao_vira_filtro_de_data(rotulo):
    assert bs._normalize_audit_date(rotulo) is None


def test_data_iso_continua_filtrando():
    assert bs._normalize_audit_date("2026-08-31") == "2026-08-31"


def _fake_conn(rows, sink):
    class Cur:
        def execute(self, sql, params=None):
            sink["sql"], sink["params"] = sql, params
            # espelha o Postgres: rótulo em coluna DATE explode
            if params and any(str(p) in ("today", "yesterday", "week") for p in params):
                raise Exception('invalid input syntax for type date: "%s"' % params[0])
        def fetchall(self):
            return rows
        def close(self):
            pass
    class Conn:
        def cursor(self):
            return Cur()
        def close(self):
            pass
    return Conn()


def _rows():
    pp = json.dumps({"prob": 0.60, "book_odd": 2.0})
    return [
        ("Under 2.5 gols", "Serie A", "hit", pp, "{}", "NEUTRO", "2026-08-30"),
        ("Over 2.5 gols", "Serie A", "miss", pp, "{}", "NEUTRO", "2026-08-30"),
    ]


def test_snapshot_sobrevive_ao_rotulo_do_cron(monkeypatch):
    """O caso exato do cron: run_after_audit(audit_date='yesterday')."""
    sink = {}
    monkeypatch.setattr(bs, "_conn", lambda: _fake_conn(_rows(), sink))
    snap = bs.calculate_snapshot(audit_date="yesterday")
    assert snap is not None, "o snapshot noturno voltou a ser calculado"
    assert snap["total_picks"] == 2
    assert sink["params"] == ()           # nenhum filtro aplicado
    # o SELECT sempre projeta DATE("timestamp") AS d; o que nao pode existir
    # e o filtro na clausula WHERE.
    where = sink["sql"].split("WHERE", 1)[1]
    assert "DATE(" not in where, where
    # o rótulo continua no retorno, para o histórico não perder a etiqueta
    assert snap["audit_date"] == "yesterday"


# ── 2. pareamento odds x desfechos ────────────────────────────────────

def test_brier_implied_pareia_o_pick_certo():
    """Dois picks com odd (ambos erraram) e dois sem odd (ambos acertaram).

    Com o pareamento antigo (`outs[:len(odds)]`) as odds dos picks 3 e 4 eram
    casadas com os desfechos dos picks 1 e 2 — resultado de outro jogo.
    """
    picks = [
        {"prob": 0.50, "out": 1, "odd": None},   # sem odd, acertou
        {"prob": 0.50, "out": 1, "odd": None},   # sem odd, acertou
        {"prob": 0.50, "out": 0, "odd": 2.0},    # com odd, errou
        {"prob": 0.50, "out": 0, "odd": 2.0},    # com odd, errou
    ]
    seg = bs._segment(picks)
    assert seg["n"] == 4 and seg["n_paired"] == 2
    # implied = 1/2.0 = 0.50 contra desfecho 0 -> (0.5-0)^2 = 0.25 nos dois
    assert seg["brier_implied"] == 0.25
    # pareamento antigo teria usado outs[:2] = [1, 1] -> (0.5-1)^2 = 0.25 tambem;
    # o que muda e o modelo pareado, que agora olha os mesmos picks:
    assert seg["brier_model_paired"] == 0.25
    assert seg["delta"] is None or seg["delta"] == 0


def test_delta_compara_o_mesmo_conjunto():
    """delta = casa - modelo nos MESMOS picks, não modelo-em-tudo vs casa-no-subconjunto."""
    picks = [
        {"prob": 0.90, "out": 1, "odd": None},   # sem odd, modelo brilha
        {"prob": 0.90, "out": 1, "odd": None},
        {"prob": 0.60, "out": 1, "odd": 4.0},    # com odd: modelo 0.16, casa 0.5625
        {"prob": 0.60, "out": 1, "odd": 4.0},
    ]
    seg = bs._segment(picks)
    assert seg["n_paired"] == 2
    assert seg["brier_model_paired"] == 0.16
    assert seg["brier_implied"] == 0.5625
    assert seg["delta"] == pytest.approx(0.4025, abs=1e-4)
    assert seg["model_beats_house"] is True
    # brier_model (todos os picks) e melhor que o pareado — e nao entra no delta
    assert seg["brier_model"] < seg["brier_model_paired"]


def test_sem_odds_suficientes_nao_inventa_comparacao():
    picks = [{"prob": 0.6, "out": 1, "odd": None} for _ in range(4)]
    picks.append({"prob": 0.6, "out": 1, "odd": 2.0})
    seg = bs._segment(picks)
    assert seg["brier_implied"] is None
    assert seg["delta"] is None
    assert seg["model_beats_house"] is None
