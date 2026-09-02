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
