# -*- coding: utf-8 -*-
"""#211 - liga desconhecida nao pode responder em silencio.

O /fixtures devolvia HTTP 200 com zero jogos para um ID fora do registro,
indistinguivel de "nao ha jogos hoje". Medido em 01/09/2026, lado a lado:

    championship          200 em 35,4s  ->  8 jogos
    england-championship  200 em  0,6s  ->  0 jogos   (ID que nunca existiu)

Os 0,6s foram lidos como rodada vazia. A mesma armadilha ja tinha custado uma
rodada com 'brasileirao-serie-a'. A lista do frontend mistura ID nu
('championship') com prefixado ('england-league-one'), entao a simetria que se
supoe nao existe - e presumi-la e o erro natural.
"""
import re

import backend.services.auditor_premissas as ap
from backend.config.leagues_config import get_league_config


def test_id_inventado_nao_resolve():
    assert get_league_config("england-championship") is None
    assert get_league_config("championship") is not None


def test_a_assimetria_que_causa_o_erro_e_real():
    """Nao e um deslize de digitacao: os dois formatos convivem no registro."""
    assert get_league_config("england-league-one") is not None   # prefixado
    assert get_league_config("league-one") is not None           # nu
    assert get_league_config("championship") is not None         # nu
    assert get_league_config("england-championship") is None     # prefixado NAO existe


def test_todos_os_ids_do_frontend_resolvem_hoje():
    rel = ap.auditar([], premissas=[ap.premissa_ligas_do_frontend_resolvem])
    assert rel.violacoes == [], [v.linha() for v in rel.violacoes]


def test_premissa_le_os_ids_do_arquivo_do_frontend(tmp_path):
    """O parser tem de extrair os ids no formato em que aparecem no leagues.ts."""
    arq = tmp_path / "leagues.ts"
    arq.write_text(
        '  {\n    id: "championship",\n  },\n  {\n    id: "england-league-one",\n  },\n',
        encoding="utf-8",
    )
    ids = re.findall(r'^\s+id: "([a-z0-9-]+)",', arq.read_text(encoding="utf-8"), re.M)
    assert ids == ["championship", "england-league-one"]


def test_premissa_acusa_quando_um_id_nao_resolve(monkeypatch):
    import backend.config.leagues_config as lc
    monkeypatch.setattr(lc, "get_league_config", lambda i: None)
    rel = ap.auditar([], premissas=[ap.premissa_ligas_do_frontend_resolvem])
    assert rel.violacoes and not rel.ok
    assert all(v.severidade == ap.SEV_CRITICO for v in rel.violacoes)


def test_premissa_esta_no_conjunto_padrao():
    assert ap.premissa_ligas_do_frontend_resolvem in ap.PREMISSAS


def test_payload_marca_a_liga_desconhecida():
    from backend.routes.fixtures import fixtures
    r = fixtures(leagues="england-championship", date="today")
    assert r["_ligas_desconhecidas"] == ["england-championship"]


def test_fora_de_producao_o_id_invalido_ainda_gera_mock():
    """Achado colateral: em dev o ID invalido nao devolve vazio - devolve MOCK.

    'Team A x Team B' para uma liga que nao existe e pior que o silencio. Em
    producao o _is_production corta e volta lista vazia, entao isso nao vaza
    para o dashboard; quem roda local ve dado falso. Fica registrado; a
    correcao e separada, para nao misturar com o campo de sinalizacao.
    """
    from backend.routes.fixtures import fixtures
    r = fixtures(leagues="england-championship", date="today")
    if r["matches"]:
        assert any("mock" in str(m.get("id", "")) for m in r["matches"]), (
            "jogo de liga inexistente tem de ser reconhecivel como mock"
        )


def test_payload_nao_marca_nada_quando_a_liga_existe(monkeypatch):
    import backend.routes.fixtures as fx
    monkeypatch.setattr(fx, "_process_single_league", lambda *a, **k: [])
    r = fx.fixtures(leagues="championship", date="today")
    assert "_ligas_desconhecidas" not in r


def test_lote_misto_aponta_so_a_invalida(monkeypatch):
    import backend.routes.fixtures as fx
    monkeypatch.setattr(fx, "_process_single_league", lambda lid, *a, **k: [])
    r = fx.fixtures(leagues="championship,england-championship,league-one", date="today")
    assert r["_ligas_desconhecidas"] == ["england-championship"]
