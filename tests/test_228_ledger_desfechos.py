# -*- coding: utf-8 -*-
"""#228 - o ledger podia gravar picks, mas nunca poderia pontua-los.

Tres coisas faltavam, e nenhuma aparecia como erro:
  1. `garantir_tabelas()` nunca era chamado -> num banco novo o primeiro INSERT
     falha por tabela inexistente e a falha aberta engole em DEBUG.
  2. `registrar_desfecho()` nunca era chamado -> ledger_outcomes vazio, JOIN
     do medir_inclinacao devolve zero linhas.
  3. UNIQUE (match_id, market) com market = TIPO -> um desfecho por tipo, e
     Over 1.5 / Over 2.5 / Under 2.5 do mesmo jogo receberiam o mesmo resultado.
Estes testes rodam sem Postgres: a conexao e um dublê que grava o SQL.
"""
import inspect

import pytest

from backend.services import prediction_ledger as L


# ── dublê de conexao ─────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, dono, selecoes):
        self.dono, self._selecoes, self.rowcount = dono, selecoes, 1

    def execute(self, sql, params=None):
        self.dono.sql.append((" ".join(sql.split()), params))

    def fetchall(self):
        return list(self._selecoes)

    def close(self):
        pass


class _Conn:
    def __init__(self, selecoes=()):
        self.sql, self._selecoes, self.commits = [], selecoes, 0

    def cursor(self):
        return _Cursor(self, self._selecoes)

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.fixture
def ligado(monkeypatch):
    """Liga a flag e poe um psycopg2.extras de mentira no lugar do real.

    Sem isto o teste passaria ou falharia conforme a maquina tivesse psycopg2
    instalado — e a "falha aberta" do ledger transformaria o ImportError num
    `return 0` silencioso, igualzinho ao defeito que este arquivo existe para
    pegar. Ambiente nao pode decidir o resultado do teste.
    """
    import sys
    import types

    extras = types.ModuleType("psycopg2.extras")
    extras.Json = lambda v: v
    extras.execute_values = lambda cur, sql, valores: cur.execute(sql, valores)
    pacote = types.ModuleType("psycopg2")
    pacote.extras = extras
    monkeypatch.setitem(sys.modules, "psycopg2", pacote)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)

    monkeypatch.setenv("PREDICTION_LEDGER_ENABLED", "1")
    monkeypatch.setattr(L, "_tabelas_ok", False)
    yield
    monkeypatch.setattr(L, "_tabelas_ok", False)


_RESULTADO = {"home_goals": 2, "away_goals": 1, "total_goals": 3, "btts": True,
              "result_1x2": "1", "total_corners": 11, "total_cards": 4}


# ── 3. desfecho por selecao ──────────────────────────────────────────────
@pytest.mark.parametrize("market, selection, esperado", [
    ("Over/Under", "Over 2.5", 1),
    ("Over/Under", "Over 3.5", 0),
    ("Over/Under", "Under 3.5", 1),
    ("BTTS", "BTTS Yes", 1),
    ("Corners", "Corners Over 10.5", 1),
    ("Corners", "Corners Over 11.5", 0),
    ("Cards", "Over 3.5", 1),        # sem o prefixo viraria GOLS (3 > 3.5 = 0)
    ("Cards", "Over 4.5", 0),
    ("1X2", "Home", 1),              # "HOME" sozinho nao casa no avaliador
    ("1X2", "Draw", 0),
    ("1X2", "Away", 0),
    ("Double Chance", "DC 1X", 1),
    ("Double Chance", "DC X2", 0),
])
def test_desfecho_por_selecao(market, selection, esperado):
    assert L.desfecho_do_pick(market, selection, _RESULTADO) == esperado


def test_cards_sem_prefixo_seria_lido_como_gols():
    """A razao do prefixo: 'Over 3.5' com 3 gols e 4 cartoes."""
    from backend.routes.ai_analysis import _evaluate_pick_deterministic
    assert _evaluate_pick_deterministic({"mercado": "Over 3.5"}, _RESULTADO) is False
    assert L.desfecho_do_pick("Cards", "Over 3.5", _RESULTADO) == 1


def test_selecoes_do_mesmo_tipo_recebem_desfechos_diferentes(ligado, monkeypatch):
    """O defeito do UNIQUE (match_id, market): Over 1.5 e Over 3.5 do mesmo
    jogo tem desfechos opostos e os dois precisam existir."""
    conn = _Conn(selecoes=[("Over/Under", "Over 1.5"), ("Over/Under", "Over 3.5")])
    monkeypatch.setattr(L, "_conn", lambda: conn)
    monkeypatch.setattr(L, "garantir_tabelas", lambda: True)

    assert L.registrar_desfechos_do_jogo("jogo-1", _RESULTADO) == 2

    inserts = [(q, p) for q, p in conn.sql if q.startswith("INSERT INTO ledger_outcomes")]
    assert len(inserts) == 2
    por_selecao = {p[2]: p[3] for _, p in inserts}
    assert por_selecao == {"Over 1.5": 1, "Over 3.5": 0}
    assert all("ON CONFLICT (match_id, market, selection)" in q for q, _ in inserts)


def test_le_do_ledger_o_que_foi_publicado_e_nao_enumera(ligado, monkeypatch):
    conn = _Conn(selecoes=[])
    monkeypatch.setattr(L, "_conn", lambda: conn)
    monkeypatch.setattr(L, "garantir_tabelas", lambda: True)
    assert L.registrar_desfechos_do_jogo("jogo-sem-pick", _RESULTADO) == 0
    assert not any(q.startswith("INSERT") for q, _ in conn.sql)
    assert any("SELECT DISTINCT market" in q and "prediction_ledger" in q for q, _ in conn.sql)


# ── 1. tabelas garantidas uma vez ────────────────────────────────────────
def test_garantir_tabelas_roda_uma_vez_por_processo(ligado, monkeypatch):
    chamadas = []
    monkeypatch.setattr(L, "garantir_tabelas", lambda: chamadas.append(1) or True)
    monkeypatch.setattr(L, "_conn", lambda: _Conn())
    L.registrar_desfecho("j", "BTTS", 1, selection="BTTS Yes")
    L.registrar_desfecho("j", "BTTS", 1, selection="BTTS Yes")
    L.registrar([L.montar_linha(match_id="j", league_id="x", market="BTTS",
                                selection="BTTS Yes", raw_prob=0.5)])
    assert len(chamadas) == 1


def test_ddl_tem_selection_e_migracao_idempotente():
    assert "selection" in L._DDL_OUTCOMES
    assert "UNIQUE (match_id, market)" not in L._DDL_OUTCOMES
    assert any("ADD COLUMN IF NOT EXISTS selection" in d for d in L._DDL_OUTCOMES_MIGRACAO)
    assert any("ux_outcomes_selecao" in d and "(match_id, market, selection)" in d
               for d in L._DDL_OUTCOMES_MIGRACAO)


# ── 2. os ganchos existem ────────────────────────────────────────────────
def test_batch_audit_chama_o_registro_de_desfechos():
    from backend import cron_handler
    fonte = inspect.getsource(cron_handler._run_batch_audit)
    assert "registrar_desfechos_do_jogo" in fonte
    assert fonte.index("actual_result = {") < fonte.index("registrar_desfechos_do_jogo")


def test_medir_inclinacao_junta_por_selecao():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "medir_inclinacao.py").read_text(encoding="utf-8")
    assert "o.selection = COALESCE(l.selection, '')" in src


def test_desligado_nao_toca_no_banco(monkeypatch):
    monkeypatch.delenv("PREDICTION_LEDGER_ENABLED", raising=False)
    monkeypatch.setattr(L, "_conn", lambda: (_ for _ in ()).throw(AssertionError("nao devia conectar")))
    assert L.registrar_desfechos_do_jogo("j", _RESULTADO) == 0
    assert L.registrar_desfecho("j", "BTTS", 1, selection="BTTS Yes") is False
