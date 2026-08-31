"""#190 — contrato do /live-scores: IDs canônicos e carimbo de observação.

Antes desta versão o campo `id` do overlay ora carregava o ID do FootyStats
(caminho normal), ora o fixture id do API-Football (caminho de fallback). O
cliente comparava `footystatsId === id` — comparação que nunca batia — e caía
sempre no casamento por nome ("CA Osasuna" vs "Osasuna").

Também não havia como saber a idade do minuto: uma resposta servida do cache de
resiliência (até 5 min) entrava no cliente como se tivesse acabado de ser
observada, e o relógio ancorava errado.
"""
import time

import backend.routes.fixtures as fixtures_mod


class _FakeFootyStats:
    """Devolve um jogo ao vivo no formato do todays-matches."""

    def __init__(self, payload):
        self._payload = payload

    def get_live_scores(self):
        return self._payload

    def get_match_live_details(self, match_id):
        # Cenario real: o /match individual falha ou vem sem sucesso. Antes do
        # #190 isso derrubava a rota inteira (detail_candidate=None
        # desreferenciado no log de diagnostico).
        return {"success": False}


class _FakeAFC:
    """API-Football configurado, mas sem jogos ao vivo (sem enrichment)."""

    is_configured = False

    def get_live_fixtures(self):
        return []


def _live_payload():
    # Kickoff 50 min atras: a rota promove "incomplete" a "live" pela janela
    # de bola rolando (0..120 min).
    kickoff = int(time.time()) - 50 * 60
    return {
        "success": True,
        "data": [
            {
                "id": 8545083,
                "home_name": "CA Osasuna",
                "away_name": "Getafe CF",
                "status": "incomplete",
                "homeGoalCount": 1,
                "awayGoalCount": 0,
                "date_unix": kickoff,
            }
        ],
    }


def _call(monkeypatch, afc=None):
    monkeypatch.setattr(fixtures_mod, "footstats", _FakeFootyStats(_live_payload()))
    monkeypatch.setattr(fixtures_mod, "_afc", afc or _FakeAFC())
    return fixtures_mod.live_scores()


def test_resposta_carrega_relogio_do_servidor(monkeypatch):
    resp = _call(monkeypatch)
    assert isinstance(resp.get("serverTimeUnix"), int)
    assert resp["nextUpdate"] == fixtures_mod._LIVE_NEXT_UPDATE


def test_registro_expoe_ids_nomeados_e_observacao(monkeypatch):
    resp = _call(monkeypatch)
    assert resp["matches"], "o jogo ao vivo deveria sair no overlay"
    rec = resp["matches"][0]

    # IDs canônicos: quem casa registro não precisa mais adivinhar a origem do `id`.
    assert "footystatsId" in rec and "apiFootballId" in rec
    assert rec["footystatsId"] == 8545083
    assert rec["apiFootballId"] is None
    # `id` permanece por compatibilidade com clientes antigos.
    assert rec["id"] == rec["footystatsId"]

    # Carimbo de observação, coerente com o relógio do servidor.
    assert isinstance(rec["observedAtUnix"], int)
    assert 0 <= resp["serverTimeUnix"] - rec["observedAtUnix"] <= 5

    # Sem API-Football, o minuto é estimativa pelo kickoff — e diz isso.
    assert rec["minuteSource"] == "kickoff_estimate"


def test_overlay_do_api_football_guarda_o_fixture_id(monkeypatch):
    """Quando o API-Football enriquece o registro, o fixture id fica gravado."""

    class _AFCComJogo:
        is_configured = True

        def get_live_fixtures(self):
            return [
                {
                    "fixture": {"id": 1570358},
                    "teams": {
                        "home": {"name": "Osasuna"},
                        "away": {"name": "Getafe"},
                    },
                }
            ]

        def _team_names_match(self, a, b):
            return b.lower() in a.lower() or a.lower() in b.lower()

        def _normalize_team_name(self, n):
            return n.lower()

        def extract_live_data(self, fx):
            return {
                "goals_home": 1,
                "goals_away": 0,
                "halftime_home": 1,
                "halftime_away": 0,
                "minute": 49,
                "status": "2H",
                "fixture_id": 1570358,
                "home_corners": 2,
                "away_corners": 1,
            }

        def get_fixture_statistics(self, fixture_id, ttl_minutes=5):
            return []

    resp = _call(monkeypatch, afc=_AFCComJogo())
    rec = resp["matches"][0]
    assert rec["apiFootballId"] == 1570358
    assert rec["footystatsId"] == 8545083
    # Minuto veio do API-Football → a observação foi recarimbada.
    assert rec["minute"] == 49
    assert rec["period"] == "2T"
    assert rec["minuteSource"] == "api_football"
    assert isinstance(rec["observedAtUnix"], int)


def test_match_detail_com_falha_nao_derruba_o_overlay(monkeypatch):
    """Regressao: uma chamada /match ruim nao pode zerar o overlay inteiro.

    O log de diagnostico lia `detail_candidate.home` antes do guard, entao
    quando o /match falhava a AttributeError subia ate o except da rota e a
    resposta virava cache/vazio — placar e tempo congelados para todo mundo.
    """

    class _FootyStatsComDetalheQuebrado(_FakeFootyStats):
        def get_match_live_details(self, match_id):
            raise RuntimeError("500 do provedor")

    monkeypatch.setattr(
        fixtures_mod, "footstats", _FootyStatsComDetalheQuebrado(_live_payload())
    )
    monkeypatch.setattr(fixtures_mod, "_afc", _FakeAFC())
    resp = fixtures_mod.live_scores()
    assert len(resp["matches"]) == 1
    assert resp["matches"][0]["footystatsId"] == 8545083
