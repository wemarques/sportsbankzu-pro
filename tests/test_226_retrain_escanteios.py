# -*- coding: utf-8 -*-
"""#226 - o retrain semanal de escanteios nunca coletou uma partida.

`_run_retrain_corners` importava `footstats_client.get_league_matches` (metodo
de classe, nao funcao de modulo) e `leagues_config.SUPPORTED_LEAGUES` (nome
inexistente — e `LEAGUES_CONFIG`), os dois dentro do mesmo `try/except
ImportError`. Toda segunda-feira o job registrava "footstats_client not
available" e devolvia `skipped`, com o modulo presente o tempo inteiro.

Estes testes travam as tres pontas: os nomes existem, a coleta devolve
partidas, e o pipeline treina de ponta a ponta.
"""
import os

import pytest

from backend.cron_handler import coletar_partidas_escanteios


# ── os nomes que nao existiam ────────────────────────────────────────────
def test_o_nome_que_o_job_importava_continua_nao_existindo():
    """Guarda contra alguem 'consertar' voltando ao import antigo."""
    import backend.config.leagues_config as lc
    import backend.services.footstats_client as fc

    assert not hasattr(lc, "SUPPORTED_LEAGUES"), (
        "se este nome passar a existir, revise coletar_partidas_escanteios"
    )
    assert not hasattr(fc, "get_league_matches"), (
        "get_league_matches e metodo de FootyStatsClient, nao funcao de modulo"
    )


def test_os_nomes_certos_existem():
    from backend.config.leagues_config import LEAGUES_CONFIG
    from backend.services.footstats_client import FootyStatsClient

    assert len(LEAGUES_CONFIG) >= 20
    assert hasattr(FootyStatsClient, "get_all_league_matches")
    assert hasattr(FootyStatsClient, "resolve_season_ids")


# ── a coleta, sem rede ───────────────────────────────────────────────────
class _ClienteDuble:
    """Cliente minimo com a MESMA assinatura da FootyStatsClient real."""

    def __init__(self, temporadas=((1001, "Season A"),), partidas=None):
        self._temporadas = list(temporadas)
        self._partidas = partidas if partidas is not None else [{"id": 1}, {"id": 2}]
        self.chamadas = []

    def resolve_season_ids(self, country, league_name, alt_names=None, n_seasons=3):
        self.chamadas.append(("resolve", country, league_name, n_seasons))
        return self._temporadas[:n_seasons]

    def get_all_league_matches(self, season_id, max_per_page=1000, max_pages=10):
        self.chamadas.append(("matches", season_id))
        return {"data": list(self._partidas)}


_LIGAS = [{"id": "championship", "country": "England", "name": "Championship"}]


def test_coleta_devolve_partidas_por_liga():
    cliente = _ClienteDuble()
    out = coletar_partidas_escanteios(cliente=cliente, ligas=_LIGAS, n_temporadas=1)
    assert out == {"championship": [{"id": 1}, {"id": 2}]}
    assert ("matches", 1001) in cliente.chamadas


def test_coleta_concatena_temporadas():
    cliente = _ClienteDuble(temporadas=((1001, "A"), (1002, "B")))
    out = coletar_partidas_escanteios(cliente=cliente, ligas=_LIGAS, n_temporadas=2)
    assert len(out["championship"]) == 4


def test_liga_sem_temporada_nao_derruba_as_outras():
    class _Vazio(_ClienteDuble):
        def resolve_season_ids(self, *a, **k):
            return []

    assert coletar_partidas_escanteios(cliente=_Vazio(), ligas=_LIGAS) == {}


def test_excecao_de_uma_liga_nao_derruba_a_coleta():
    class _Explode(_ClienteDuble):
        def get_all_league_matches(self, *a, **k):
            raise RuntimeError("429")

    ligas = _LIGAS + [{"id": "outra", "country": "Spain", "name": "La Liga"}]
    cliente = _Explode()
    assert coletar_partidas_escanteios(cliente=cliente, ligas=ligas) == {}


def test_liga_sem_id_e_ignorada():
    cliente = _ClienteDuble()
    assert coletar_partidas_escanteios(cliente=cliente, ligas=[{"country": "X"}]) == {}


def test_slug_serve_de_id_e_zero_nao_vira_ausencia():
    """`liga.get("id", liga.get("slug"))` morria com `id` presente-e-nulo."""
    cliente = _ClienteDuble()
    out = coletar_partidas_escanteios(
        cliente=cliente,
        ligas=[{"id": None, "slug": "championship", "country": "England", "name": "Championship"}],
    )
    assert "championship" in out


# ── o pipeline treina ────────────────────────────────────────────────────
def _carregar_gerador():
    """`liga_sintetica` mora no script executavel; carregado por caminho para
    nao transformar `scripts/` em pacote (o `packages = find:` do setup.cfg o
    empacotaria junto com o backend)."""
    import importlib.util
    import pathlib

    caminho = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "retreinar_escanteios.py"
    spec = importlib.util.spec_from_file_location("_retreinar_escanteios", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.liga_sintetica


def test_retrain_treina_ponta_a_ponta(tmp_path, monkeypatch):
    """Antes do #226 este caminho nunca chegou a rodar em lugar nenhum."""
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    import importlib

    from backend.modeling.corners import artifacts, ml_regression
    importlib.reload(artifacts)
    importlib.reload(ml_regression)
    from backend.modeling.corners import retrain as mod_retrain
    importlib.reload(mod_retrain)

    liga_sintetica = _carregar_gerador()

    resumo = mod_retrain.retrain_league(
        liga_sintetica(200), "sintetica",
        {"average_corners_per_match": 10.2}, force_shadow=True,
    )

    assert resumo["status"] == "completed"
    assert resumo["n_valid_corners"] == 200
    assert resumo["n_features"] > 0
    assert resumo["training_results"]["negative_binomial"] == "trained"
    assert (tmp_path / ".corner_artifacts" / "corner_model_registry.json").exists()
    assert (tmp_path / ".corner_models" / "sintetica" / "corner_regressor.pkl").exists()

    importlib.reload(artifacts)
    importlib.reload(ml_regression)
    importlib.reload(mod_retrain)


# ── o diretorio gravavel ─────────────────────────────────────────────────
def test_raiz_de_dados_respeita_precedencia(monkeypatch):
    from backend.utils import caminhos

    monkeypatch.setenv("DATA_ROOT", "/x")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "f")
    assert str(caminhos.raiz_de_dados()) == "/x"

    monkeypatch.delenv("DATA_ROOT")
    assert str(caminhos.raiz_de_dados()) == "/tmp", (
        "na Lambda o diretorio do pacote e somente leitura — o mkdir do retrain "
        "levantaria OSError"
    )

    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME")
    assert str(caminhos.raiz_de_dados()) == "."


# ── #226-c: o nome real do total direto ──────────────────────────────────
def test_total_direto_vem_de_totalCornerCount():
    """`totalCorners` e `total_corners` nao existem na linha de partida.

    Medido: em 605 finalizadas da championship, `totalCornerCount` e
    `team_a + team_b` concordam em 605/605 — por isso a promocao e neutra.
    """
    from backend.modeling.corners.retrain import _extract_total_corners

    # nome real presente: usa o total direto
    assert _extract_total_corners({"totalCornerCount": 13,
                                   "team_a_corners": 10, "team_b_corners": 3}) == 13.0
    # ausente: cai na soma, como antes
    assert _extract_total_corners({"team_a_corners": 10, "team_b_corners": 3}) == 13.0
    # presente valendo None: nao trava a cadeia (#225-c)
    assert _extract_total_corners({"totalCornerCount": None,
                                   "team_a_corners": 10, "team_b_corners": 3}) == 13.0
    # -1 e o "sem dado" da FootyStats
    assert _extract_total_corners({"totalCornerCount": -1,
                                   "team_a_corners": -1, "team_b_corners": -1}) == 0.0
