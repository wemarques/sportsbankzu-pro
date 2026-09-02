"""#221 - a contagem de jogos da liga chega ao consumidor.

Tres camadas, tres nomes, nenhum acordo:
  produtor  routes/fixtures.py:334   -> coluna `matches_completed`
  portador  fixtures_service.py:1076 -> nao carregava a chave
  consumidor data_governance.py:113  -> pedia `matchesCompleted`/`matches_played`
"""
import pytest

from backend.services import data_governance as dg
from backend.services.fixtures_service import _contagem_de_jogos_habilitada


# ── consumidor tolerante a nome ─────────────────────────────────────────
@pytest.mark.parametrize("chave", [
    "matchesCompleted", "matches_completed", "matches_played",
    "matchesPlayed", "games_played",
])
def test_todos_os_nomes_do_produtor_sao_aceitos(chave):
    assert dg._jogos_disputados({chave: 25}) == 25
    assert dg.season_data_state({chave: 25}) == dg.ESTADO_TEMPORADA_OK
    assert dg.detect_early_season({chave: 25}) is False


def test_o_nome_que_o_produtor_usa_de_fato():
    """routes/fixtures.py monta a coluna em snake_case. Era este o buraco."""
    assert dg._jogos_disputados({"matches_completed": 25}) == 25


@pytest.mark.parametrize("valor,esperado", [
    (25, 25), ("25", 25), (25.0, 25), (0, 0),
    (None, None), ("vinte", None), (-3, None),
])
def test_conversao_e_lixo(valor, esperado):
    assert dg._jogos_disputados({"matches_completed": valor}) == esperado


# ── o efeito que motivou o patch ────────────────────────────────────────
def test_rodada_25_deixa_de_ser_inicio_de_temporada():
    """O defeito em uma linha: 25 rodadas jogadas, EARLY_SEASON disparando."""
    assert dg.detect_early_season({"matches_completed": 25}) is False


def test_liga_realmente_no_inicio_continua_marcada():
    assert dg.detect_early_season({"matches_completed": 3}) is True


def test_ausencia_continua_sendo_desconhecido():
    """#221 nao revoga o #217: sem contagem, o estado ainda e UNKNOWN."""
    assert dg.season_data_state({}) == dg.ESTADO_TEMPORADA_DESCONHECIDO
    assert dg.season_data_state({"avg_goals": 2.5}) == dg.ESTADO_TEMPORADA_DESCONHECIDO


# ── nota de qualidade ───────────────────────────────────────────────────
def test_contagem_eleva_a_nota_de_qualidade():
    """A maturidade de temporada nunca somava seus pontos."""
    com = dg.calculate_data_quality_score({}, {}, {"matches_completed": 25})
    sem = dg.calculate_data_quality_score({}, {}, {})
    assert com > sem


def test_nota_usa_o_mesmo_leitor_dos_outros():
    """Antes, esta funcao tinha a sua propria lista de nomes. Agora e uma so."""
    a = dg.calculate_data_quality_score({}, {}, {"matches_completed": 25})
    b = dg.calculate_data_quality_score({}, {}, {"matchesCompleted": 25})
    c = dg.calculate_data_quality_score({}, {}, {"games_played": 25})
    assert a == b == c


# ── interruptor ─────────────────────────────────────────────────────────
def test_ligado_por_padrao(monkeypatch):
    """Ao contrario dos outros patches: aqui o estado atual e que e o errado."""
    monkeypatch.delenv("LEAGUE_MATCH_COUNT_ENABLED", raising=False)
    assert _contagem_de_jogos_habilitada() is True


@pytest.mark.parametrize("v", ["0", "false", "no", "off", "OFF"])
def test_rollback_de_uma_variavel(monkeypatch, v):
    monkeypatch.setenv("LEAGUE_MATCH_COUNT_ENABLED", v)
    assert _contagem_de_jogos_habilitada() is False


@pytest.mark.parametrize("v", ["1", "true", "on", ""])
def test_qualquer_outro_valor_mantem_ligado(monkeypatch, v):
    monkeypatch.setenv("LEAGUE_MATCH_COUNT_ENABLED", v)
    assert _contagem_de_jogos_habilitada() is True


# ── #221-a: a quarta camada ─────────────────────────────────────────────
# O #221 corrigiu o portador (`league_avgs`), e com isso a contagem passou a
# chegar ao predict_corners e ao predict_cards, que ja recebiam
# `league_stats=league_avgs`. Mas o consumidor que decide o EARLY_SEASON le
# `match_data.get("league_stats")` (ev_classification.py:884) — e o record
# NUNCA teve essa chave. Medido antes do #221-a: com e sem a contagem, o
# payload saia igual, com DATA_MISSING e EARLY_SEASON_FALLBACK nos dois.
import time

import pandas as pd

from backend.services.fixtures_service import build_records_from_matches

_BASE_LIGA = {
    "average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
    "average_cards_per_match": 4.9, "average_fouls_per_match": 22.0,
    "average_shots_per_match": 24.0,
}


def _monta(league_df):
    ts = int(time.time()) + 3600
    return build_records_from_matches(
        league_id="championship",
        matches=pd.DataFrame([{"timestamp": ts}]), teams=None,
        league_df=league_df,
        _rows_override=[{"id": 1, "home_team_name": "Casa FC",
                         "away_team_name": "Fora FC", "date_unix": ts,
                         "timestamp": ts, "status": "incomplete"}],
        date_filter="today",
    )[0]


def _codigos(record):
    return {c for m in record["mercados"] for c in (m.get("reason_codes") or [])}


def test_o_record_publica_league_stats():
    """A chave que ev_classification.py:884 le. Sem ela o #221 nao tem efeito."""
    r = _monta(pd.DataFrame([{**_BASE_LIGA, "matches_completed": 25}]))
    assert "league_stats" in r
    assert r["league_stats"]["matches_completed"] == 25


def test_com_contagem_o_early_season_some():
    r = _monta(pd.DataFrame([{**_BASE_LIGA, "matches_completed": 25}]))
    cods = _codigos(r)
    assert "EARLY_SEASON_FALLBACK" not in cods
    assert "DATA_MISSING" not in cods


def test_sem_contagem_o_estado_continua_desconhecido():
    """O #221 nao revoga o #217: sem dado, o rotulo de ausencia permanece."""
    cods = _codigos(_monta(pd.DataFrame([_BASE_LIGA])))
    assert "DATA_MISSING" in cods and "EARLY_SEASON_FALLBACK" in cods


def test_rollback_desliga_o_efeito_de_ponta_a_ponta(monkeypatch):
    """LEAGUE_MATCH_COUNT_ENABLED=0 devolve o comportamento antigo."""
    monkeypatch.setenv("LEAGUE_MATCH_COUNT_ENABLED", "0")
    cods = _codigos(_monta(pd.DataFrame([{**_BASE_LIGA, "matches_completed": 25}])))
    assert "DATA_MISSING" in cods and "EARLY_SEASON_FALLBACK" in cods
