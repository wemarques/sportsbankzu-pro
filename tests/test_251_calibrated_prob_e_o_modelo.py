# -*- coding: utf-8 -*-
"""#251 - `prediction_ledger.calibrated_prob` e a probabilidade DO MODELO.

A camada de calibragem aprendida (#248) COMPOE sobre o legado: quando uma
celula serve uma versao real, `curva.aplicar_versao` sobrescreve
`detalhe.final` com `sigmoide(a + b*logit(legado))`. O valor do legado — que e
a saida do modelo — morria ali. Como `_prob_do_modelo` so lia
`model_probability` sob `PROB_SOURCE=mercado`, com o padrao `modelo` o ledger
gravava a SAIDA DA CAMADA em `calibrated_prob` — exatamente a serie que o gate
#230 mede (`comparar_com_mercado.py --campo calibrated_prob`).

Tres garantias:

  1. camada ATIVA  -> `calibrated_prob` == legado, `published_prob` == composto,
     e os dois DIFERENTES entre si;
  2. camada INATIVA -> `calibrated_prob` == `published_prob` == legado
     (comportamento identico ao de antes do #251);
  3. `PROB_SOURCE=mercado` -> `calibrated_prob` continua o modelo (agora o
     PRE-camada) e `published_prob` a ancora.
"""
import copy

import pytest

import backend.modeling.calibragem.ciclo as C
from backend.modeling.calibragem.curva import aplicar
from backend.modeling.calibragem.legado import calibrar_legado
from backend.services import ancora_mercado as A
from backend.services import prediction_ledger as L
from backend.services.ev_classification import (
    _calibrar_com_detalhe, evaluate_match_markets,
)

_A, _B = 0.12, 0.98
_FAMILIAS = ("Over/Under", "BTTS", "Corners", "Cards", "1X2", "Double Chance")
_PARAMS = {(f, ""): (7, _A, _B) for f in _FAMILIAS}

_ODDS = {
    "home": 1.95, "draw": 3.60, "away": 3.70,
    "over25": 1.80, "under25": 1.90, "over15": 1.22, "under15": 3.54,
    "bttsYes": 1.75, "bttsNo": 2.00,
    "cornersOver95": 1.77, "cornersUnder95": 1.95, "cornersOver115": 2.63,
}
_MATCH = {
    "id": "999250", "homeTeam": "Casa FC", "awayTeam": "Fora FC",
    "stats": {"lambdaHome": 1.55, "lambdaAway": 1.15, "lambdaTotal": 2.70,
              "homeWinProb": 47.0, "drawProb": 26.0, "awayWinProb": 27.0,
              "homeCornersPerMatch": 5.6, "awayCornersPerMatch": 4.9,
              "leagueAvgCorners": 10.2,
              "homeCardsPerMatch": 2.1, "awayCardsPerMatch": 2.4,
              "leagueAvgCards": 4.6,
              "matchesPlayed_home": 18, "matchesPlayed_away": 18},
    "league_stats": {"matches_completed": 200, "average_goals_per_match": 2.65,
                     "average_corners_per_match": 10.2,
                     "average_cards_per_match": 4.6},
    "odds": {**_ODDS, "over05": 1.03, "under05": 9.50, "over35": 2.99,
             "under35": 1.30, "over45": 5.85, "under45": 1.10,
             "dc_1x": 1.25, "dc_12": 1.28, "dc_x2": 1.83,
             "cornersOver75": 1.24, "cornersUnder75": 3.55,
             "cornersUnder115": 1.41},
}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch, tmp_path):
    monkeypatch.delenv(A.FLAG, raising=False)
    monkeypatch.setenv("TAXAS_BASE_PATH", str(tmp_path / "inexistente.json"))
    A.limpar_cache_taxas()
    yield
    A.limpar_cache_taxas()


def _camada(monkeypatch, parametros):
    monkeypatch.setattr(C, "parametros_vigentes",
                        lambda: (parametros, "banco"), raising=False)


def _linhas(match=None):
    md = copy.deepcopy(match or _MATCH)
    bundle = evaluate_match_markets(copy.deepcopy(md), league_id="championship")
    return L.linhas_do_bundle(bundle, md, md["stats"])


# ── 1. o detalhe carrega o valor pre-camada ──────────────────────────────
def test_detalhe_guarda_o_legado_antes_de_compor(monkeypatch):
    _camada(monkeypatch, _PARAMS)
    d = _calibrar_com_detalhe(0.62, "Over 2.5", "championship", "NORMAL")
    legado = calibrar_legado(0.62, "Over 2.5", "championship", "NORMAL").final
    assert d.modelo == pytest.approx(legado, abs=1e-12)
    assert d.final == pytest.approx(aplicar(legado, _A, _B), abs=1e-12)
    assert d.modelo != pytest.approx(d.final, abs=1e-9)


def test_sem_camada_o_detalhe_tem_modelo_igual_a_final(monkeypatch):
    _camada(monkeypatch, {})
    d = _calibrar_com_detalhe(0.62, "Over 2.5", "championship", "NORMAL")
    assert d.modelo == d.final
    assert d.final == calibrar_legado(0.62, "Over 2.5", "championship",
                                      "NORMAL").final


# ── 2. o ledger: camada ativa separa as duas colunas ─────────────────────
def test_camada_ativa_separa_calibrated_de_published(monkeypatch):
    _camada(monkeypatch, _PARAMS)
    linhas = [l for l in _linhas()
              if l["calibrated_prob"] is not None and l["published_prob"] is not None]
    assert len(linhas) >= 10
    # published == a composicao do que foi gravado em calibrated_prob
    for l in linhas:
        assert l["published_prob"] == pytest.approx(
            aplicar(l["calibrated_prob"], _A, _B), abs=1e-9), l["selection"]
    # e os dois sao DIFERENTES: com (a, b) != (0, 1) a camada move o numero
    assert all(abs(l["published_prob"] - l["calibrated_prob"]) > 1e-6
               for l in linhas)


def test_camada_inativa_nao_muda_nada(monkeypatch):
    _camada(monkeypatch, {})
    linhas = [l for l in _linhas() if l["calibrated_prob"] is not None]
    assert len(linhas) >= 10
    assert all(l["published_prob"] == l["calibrated_prob"] for l in linhas)
    assert all(l["prob_source"] == "modelo" for l in linhas)


def test_versao_legado_explicita_tambem_nao_muda_nada(monkeypatch):
    from backend.modeling.calibragem import VERSAO_LEGADO
    _camada(monkeypatch, {(f, ""): (VERSAO_LEGADO, 0.5, 0.5) for f in _FAMILIAS})
    linhas = [l for l in _linhas() if l["calibrated_prob"] is not None]
    assert linhas and all(l["published_prob"] == l["calibrated_prob"]
                          for l in linhas)


# ── 3. a flag do #231 continua valendo, e sobre o valor PRE-camada ───────
def test_ancora_nao_sobrescreve_o_modelo_pre_camada(monkeypatch):
    _camada(monkeypatch, _PARAMS)
    sem_flag = {(l["market"], l["selection"]): l["calibrated_prob"]
                for l in _linhas()}
    monkeypatch.setenv(A.FLAG, "mercado")
    com_flag = _linhas()
    assert com_flag and any(l["prob_source"] == "mercado" for l in com_flag)
    for l in com_flag:
        chave = (l["market"], l["selection"])
        if chave not in sem_flag or sem_flag[chave] is None:
            continue
        # calibrated_prob e o MESMO modelo pre-camada, com ou sem a flag;
        # so `published_prob` muda para a ancora.
        assert l["calibrated_prob"] == pytest.approx(sem_flag[chave], abs=1e-12), chave
        if l["prob_source"] == "mercado":
            assert l["published_prob"] != pytest.approx(l["calibrated_prob"],
                                                        abs=1e-9), chave


# ── borda: pick que nunca passou por `_calibrar_com_detalhe` ─────────────
def test_pick_sem_model_probability_cai_na_publicada():
    from backend.models.market_output import MarketOutput
    m = MarketOutput(market_type="BTTS", selection="BTTS Yes",
                     raw_probability=0.60, calibrated_probability=0.55)
    assert m.model_probability is None
    assert L._prob_do_modelo(m) == 0.55
