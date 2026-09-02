"""#225-a - a rota de diagnostico responde UMA pergunta: as odds historicas
do league-matches vem preenchidas? Instrumento descartavel, mas enquanto
existir precisa nao mentir."""
import pytest
from fastapi import HTTPException

import backend.routes.debug as dbg


class _FSC:
    """Cliente falso — a rota nao pode depender de rede para ser testada."""
    def __init__(self, jogos):
        self._jogos = jogos
    def resolve_season_ids(self, *a, **k):
        return [(9999, "Championship")]
    def get_all_league_matches(self, sid, **k):
        return {"success": True, "data": self._jogos}


def _jogo(status="complete", odd=None, **extra):
    j = {
        "status": status, "date_unix": 1788300000,
        "homeGoalCount": 2, "awayGoalCount": 1,
        "team_a_yellow_cards": 2, "team_b_yellow_cards": 3,
        "home_team_corner_count": 6, "away_team_corner_count": 4,
    }
    for c in ("odds_ft_home_team_win", "odds_ft_draw", "odds_ft_away_team_win",
              "odds_ft_over25", "odds_btts_yes"):
        j[c] = odd
    j.update(extra)
    return j


@pytest.fixture
def _sem_chave(monkeypatch):
    monkeypatch.setenv("ODDS_DEBUG_KEY", "segredo")


def _rodar(monkeypatch, jogos, **kw):
    monkeypatch.setattr(dbg, "_get_fsc", lambda: _FSC(jogos))
    return dbg.historico_odds(x_debug_key="segredo", **kw)


# ── autenticacao ────────────────────────────────────────────────────────
def test_exige_a_chave_de_debug(_sem_chave, monkeypatch):
    monkeypatch.setattr(dbg, "_get_fsc", lambda: _FSC([_jogo()]))
    with pytest.raises(HTTPException) as e:
        dbg.historico_odds(x_debug_key=None)
    assert e.value.status_code == 401


def test_sem_chave_configurada_recusa(monkeypatch):
    monkeypatch.setenv("ODDS_DEBUG_KEY", "")
    with pytest.raises(HTTPException) as e:
        dbg.historico_odds(x_debug_key="qualquer")
    assert e.value.status_code == 503


def test_liga_desconhecida(_sem_chave):
    with pytest.raises(HTTPException) as e:
        dbg.historico_odds(league_id="liga-que-nao-existe", x_debug_key="segredo")
    assert e.value.status_code == 404


# ── o veredito ──────────────────────────────────────────────────────────
def test_odds_preenchidas(_sem_chave, monkeypatch):
    r = _rodar(monkeypatch, [_jogo(odd=2.10) for _ in range(10)])
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["pct"] == 100.0
    assert "PREENCHIDAS" in r["veredito"]


def test_odds_ausentes(_sem_chave, monkeypatch):
    r = _rodar(monkeypatch, [_jogo(odd=None) for _ in range(10)])
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["pct"] == 0.0
    assert "AUSENTES" in r["veredito"]


def test_zero_e_ausente_nao_preenchido(_sem_chave, monkeypatch):
    """Odd 0 ou 1.0 nao e preco — e campo vazio com outro disfarce."""
    r = _rodar(monkeypatch, [_jogo(odd=0) for _ in range(5)] + [_jogo(odd=1.0) for _ in range(5)])
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["preenchidos"] == 0


def test_cobertura_parcial_nao_vira_veredito_positivo(_sem_chave, monkeypatch):
    r = _rodar(monkeypatch, [_jogo(odd=2.1) for _ in range(3)] + [_jogo(odd=None) for _ in range(7)])
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["pct"] == 30.0
    assert "AUSENTES" in r["veredito"]


# ── so jogos finalizados ────────────────────────────────────────────────
def test_jogo_futuro_nao_conta_na_cobertura():
    """Odd de jogo que ainda vai acontecer nao prova nada sobre o historico —
    e o historico e o que o backfill vai usar."""
    import os
    os.environ["ODDS_DEBUG_KEY"] = "segredo"
    jogos = [_jogo(status="incomplete", odd=2.1) for _ in range(9)] + [_jogo(status="complete", odd=None)]
    import backend.routes.debug as d
    d._get_fsc = lambda: _FSC(jogos)
    r = d.historico_odds(x_debug_key="segredo")
    assert r["finalizados"] == 1
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["total"] == 1
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["preenchidos"] == 0


# ── amostra ─────────────────────────────────────────────────────────────
def test_amostra_traz_estatistica_por_jogo(_sem_chave, monkeypatch):
    r = _rodar(monkeypatch, [_jogo(odd=2.1) for _ in range(10)], n=3)
    assert len(r["amostra"]) == 3
    a = r["amostra"][0]
    for c in ("date_unix", "homeGoalCount", "team_a_yellow_cards", "home_team_corner_count"):
        assert c in a, c


def test_n_e_limitado(_sem_chave, monkeypatch):
    jogos = [_jogo(odd=2.1) for _ in range(50)]
    assert len(_rodar(monkeypatch, jogos, n=999)["amostra"]) == 20
    assert len(_rodar(monkeypatch, jogos, n=0)["amostra"]) == 1


def test_lista_as_chaves_odds_que_existem(_sem_chave, monkeypatch):
    """Se o nome for outro, a lista denuncia em vez de devolver tudo nulo."""
    j = _jogo(odd=None)
    j["odds_1x2_home"] = 2.5
    r = _rodar(monkeypatch, [j])
    assert "odds_1x2_home" in r["amostra"][0]["chaves_odds_presentes"]


def test_temporada_sem_jogos_nao_divide_por_zero(_sem_chave, monkeypatch):
    r = _rodar(monkeypatch, [])
    assert r["finalizados"] == 0
    assert r["cobertura_odds"]["odds_ft_home_team_win"]["pct"] == 0.0
