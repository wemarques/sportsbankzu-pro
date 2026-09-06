# -*- coding: utf-8 -*-
"""#231 - fonte da probabilidade publicada atras da flag PROB_SOURCE.

Item 1 do passo 4 da regra #230. A flag nasce desligada; ligada, a publicada
de cada selecao com par de-vigado passa a ser a `prob_mercado` que o ledger
ja grava (#230), a selecao sem preco cai para a taxa-base ROTULADA e, sem
taxa-base, o modelo fica rotulado como sem referencia. Tres garantias que
estes testes fecham:

  1. flag desligada -> payload legado byte a byte identico e ledger igual;
  2. flag ligada    -> so a probabilidade e o rotulo mudam; classificacao nao;
  3. o ledger continua gravando o MODELO em calibrated_prob (e a publicada em
     published_prob), senao ligar a flag apagaria a medicao que a autoriza.
"""
import copy
import json

import pytest

from backend.models.market_output import (
    MarketClassification, MarketOutput, MatchMarketBundle,
)
from backend.services import ancora_mercado as A
from backend.services import prediction_ledger as L
from backend.services.ev_classification import evaluate_match_markets

_ODDS = {
    "home": 1.95, "draw": 3.60, "away": 3.70,
    "over25": 1.80, "under25": 1.90, "over15": 1.22, "under15": 3.54,
    "bttsYes": 1.75, "bttsNo": 2.00,
    "cornersOver95": 1.77, "cornersUnder95": 1.95,
    "cornersOver115": 2.63,                       # so uma perna: implicita
}


def _mo(market, selection, prob, odd=None, cls=MarketClassification.NEUTRO):
    m = MarketOutput(market_type=market, selection=selection, raw_probability=prob + 0.05,
                     calibrated_probability=prob, book_odd=odd, classification=cls)
    m.compute_display()
    m.compute_ev()
    return m


def _bundle():
    return MatchMarketBundle(
        match_id="1", home_team="A", away_team="B", league_id="championship",
        markets=[
            _mo("Over/Under", "Over 2.5", 0.50, 1.80, MarketClassification.SAFE),
            _mo("BTTS", "BTTS Yes", 0.52, 1.75),
            _mo("Corners", "Corners Over 9.5", 0.55, 1.77),
            _mo("Corners", "Corners Over 11.5", 0.35, 2.63),   # sem par
            _mo("Cards", "Over 1.5", 0.68),                     # sem preco nenhum
            _mo("Double Chance", "DC 1X", 0.60),
        ],
    )


@pytest.fixture(autouse=True)
def _sem_artefato(monkeypatch, tmp_path):
    monkeypatch.delenv(A.FLAG, raising=False)
    monkeypatch.setenv("TAXAS_BASE_PATH", str(tmp_path / "inexistente.json"))
    A.limpar_cache_taxas()
    yield
    A.limpar_cache_taxas()


# ── 1. desligada: nada muda ──────────────────────────────────────────────
def test_flag_desligada_e_o_padrao_e_nao_toca_no_bundle():
    assert A.fonte_configurada() == "modelo" and not A.ancora_ligada()
    b = _bundle()
    antes = [m.to_legacy_mercado() for m in b.markets]
    assert A.aplicar_ancora(b, {"odds": _ODDS}) == {
        "mercado": 0, "taxa_base": 0, "modelo_sem_referencia": 0}
    depois = [m.to_legacy_mercado() for m in b.markets]
    assert antes == depois
    assert all("prob_source" not in d and "model_probability" not in d for d in depois)


def test_valor_desconhecido_da_flag_e_modelo(monkeypatch):
    monkeypatch.setenv(A.FLAG, "banana")
    assert A.fonte_configurada() == "modelo"


def test_ledger_com_flag_desligada_grava_published_igual_a_calibrated():
    linhas = L.linhas_do_bundle(_bundle(), {"odds": _ODDS}, {})
    assert linhas and all(l["published_prob"] == l["calibrated_prob"] for l in linhas)
    assert all(l["prob_source"] == "modelo" for l in linhas)


# ── 2. ligada: a troca, selecao a selecao ────────────────────────────────
def test_ligada_troca_so_quem_tem_par_devigado(monkeypatch):
    monkeypatch.setenv(A.FLAG, "mercado")
    b = _bundle()
    contagem = A.aplicar_ancora(b, {"odds": _ODDS})
    assert contagem == {"mercado": 4, "taxa_base": 0, "modelo_sem_referencia": 2}
    por = {m.selection: m for m in b.markets}

    o25 = por["Over 2.5"]
    esperado = L.prob_mercado_do_pick("Over/Under", "Over 2.5", _ODDS)["prob_mercado"]
    assert o25.prob_source == "mercado"
    assert o25.calibrated_probability == pytest.approx(esperado, abs=1e-6)
    assert o25.model_probability == 0.50                   # modelo preservado
    assert o25.fair_odd == round(1 / esperado, 2)          # display recomputado
    assert o25.ev is None and o25.edge is None             # item 2 redefine
    assert o25.classification == MarketClassification.SAFE  # item 3 redefine
    assert o25.odds_available is True                      # a odd continua la

    assert por["DC 1X"].prob_source == "mercado"           # devig3 do trio

    # so uma perna -> implicita NAO serve de ancora -> sem taxa-base -> modelo
    o115 = por["Corners Over 11.5"]
    assert o115.prob_source == "modelo_sem_referencia"
    assert o115.calibrated_probability == 0.35 and o115.model_probability == 0.35
    assert o115.ev is not None                              # EV do modelo fica

    c15 = por["Over 1.5"]
    assert c15.prob_source == "modelo_sem_referencia" and c15.calibrated_probability == 0.68


def test_legado_carrega_a_fonte_so_com_flag_ligada(monkeypatch):
    monkeypatch.setenv(A.FLAG, "mercado")
    b = _bundle()
    A.aplicar_ancora(b, {"odds": _ODDS})
    d = b.markets[0].to_legacy_mercado()
    assert d["prob_source"] == "mercado" and d["model_probability"] == 0.5
    assert d["calibrated_probability"] != 0.5


# ── taxa-base: rotulada, hierarquica, com minimo de n ────────────────────
def _artefato(tmp_path, celulas, min_n=30):
    caminho = tmp_path / "taxas.json"
    caminho.write_text(json.dumps({"min_n": min_n, "celulas": celulas}), encoding="utf-8")
    return str(caminho)


def test_sem_preco_cai_para_a_taxa_base_da_liga_e_rotula(monkeypatch, tmp_path):
    monkeypatch.setenv(A.FLAG, "mercado")
    monkeypatch.setenv("TAXAS_BASE_PATH", _artefato(tmp_path, {
        "championship": {"Cards|Over 1.5": {"taxa": 0.91, "n": 400}},
        "*": {"Cards|Over 1.5": {"taxa": 0.88, "n": 5000},
              "Corners|Corners Over 11.5": {"taxa": 0.33, "n": 900}},
    }))
    A.limpar_cache_taxas()
    b = _bundle()
    contagem = A.aplicar_ancora(b, {"odds": _ODDS})
    assert contagem == {"mercado": 4, "taxa_base": 2, "modelo_sem_referencia": 0}
    por = {m.selection: m for m in b.markets}
    assert por["Over 1.5"].prob_source == "taxa_base"
    assert por["Over 1.5"].calibrated_probability == 0.91          # liga antes de *
    assert por["Over 1.5"].model_probability == 0.68
    assert por["Corners Over 11.5"].calibrated_probability == 0.33  # so no *
    assert por["Corners Over 11.5"].prob_source == "taxa_base"


def test_taxa_base_ignora_celula_abaixo_do_minimo(tmp_path, monkeypatch):
    monkeypatch.setenv("TAXAS_BASE_PATH", _artefato(tmp_path, {
        "championship": {"Cards|Over 1.5": {"taxa": 1.0, "n": 4}},
        "*": {"Cards|Over 1.5": {"taxa": 0.88, "n": 31}},
    }))
    A.limpar_cache_taxas()
    assert A.taxa_base("championship", "Cards", "Over 1.5") == {"taxa": 0.88, "n": 31, "nivel": "*"}
    assert A.taxa_base("championship", "Cards", "Over 2.5") is None


def test_artefato_ausente_ou_quebrado_nao_derruba(tmp_path, monkeypatch):
    assert A.taxa_base("championship", "Cards", "Over 1.5") is None
    quebrado = tmp_path / "q.json"
    quebrado.write_text("{nao e json", encoding="utf-8")
    monkeypatch.setenv("TAXAS_BASE_PATH", str(quebrado))
    A.limpar_cache_taxas()
    assert A.taxa_base("championship", "Cards", "Over 1.5") is None


# ── 3. o ledger nao perde o modelo ───────────────────────────────────────
def test_ledger_grava_modelo_em_calibrated_e_ancora_em_published(monkeypatch):
    monkeypatch.setenv(A.FLAG, "mercado")
    b = _bundle()
    A.aplicar_ancora(b, {"odds": _ODDS})
    linhas = {l["selection"]: l for l in L.linhas_do_bundle(b, {"odds": _ODDS}, {})}
    o25 = linhas["Over 2.5"]
    assert o25["calibrated_prob"] == 0.50
    assert o25["published_prob"] == o25["prob_mercado"]     # a mesma ancora
    assert o25["prob_source"] == "mercado"
    c15 = linhas["Over 1.5"]
    assert c15["calibrated_prob"] == c15["published_prob"] == 0.68
    assert c15["prob_source"] == "modelo_sem_referencia"
    for col in ("published_prob", "prob_source"):
        assert col in L._COLUNAS
        assert any(col in ddl for ddl in L._DDL_LEDGER_MIGRACAO)


def test_trocar_a_fonte_e_uma_revisao_no_hash():
    a = L.montar_linha(match_id="1", league_id="x", market="BTTS", selection="BTTS Yes",
                       calibrated_prob=0.5, published_prob=0.5, prob_source="modelo")
    b = L.montar_linha(match_id="1", league_id="x", market="BTTS", selection="BTTS Yes",
                       calibrated_prob=0.5, published_prob=0.55, prob_source="mercado")
    assert a["payload_hash"] != b["payload_hash"]


# ── ponta a ponta: evaluate_match_markets com um match_data real ─────────
_MATCH = {
    "id": "999001", "homeTeam": "Casa FC", "awayTeam": "Fora FC",
    "stats": {"lambdaHome": 1.55, "lambdaAway": 1.15, "lambdaTotal": 2.70,
              "homeWinProb": 47.0, "drawProb": 26.0, "awayWinProb": 27.0,
              "homeCornersPerMatch": 5.6, "awayCornersPerMatch": 4.9, "leagueAvgCorners": 10.2,
              "homeCardsPerMatch": 2.1, "awayCardsPerMatch": 2.4, "leagueAvgCards": 4.6,
              "matchesPlayed_home": 18, "matchesPlayed_away": 18},
    "league_stats": {"matches_completed": 200, "average_goals_per_match": 2.65,
                     "average_corners_per_match": 10.2, "average_cards_per_match": 4.6},
    "odds": {**_ODDS, "over05": 1.03, "under05": 9.50, "over35": 2.99, "under35": 1.30,
             "over45": 5.85, "under45": 1.10, "dc_1x": 1.25, "dc_12": 1.28, "dc_x2": 1.83,
             "cornersOver75": 1.24, "cornersUnder75": 3.55, "cornersUnder115": 1.41},
}


def test_ponta_a_ponta_flag_desligada_versus_ligada(monkeypatch):
    monkeypatch.delenv(A.FLAG, raising=False)
    b0 = evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    monkeypatch.setenv(A.FLAG, "mercado")
    b1 = evaluate_match_markets(copy.deepcopy(_MATCH), league_id="championship")
    assert len(b0.markets) == len(b1.markets) >= 10
    assert all(m.prob_source is None for m in b0.markets)
    fontes = {m.prob_source for m in b1.markets}
    assert fontes == {"mercado", "modelo_sem_referencia"}
    for m0, m1 in zip(b0.markets, b1.markets):
        assert (m0.market_type, m0.selection) == (m1.market_type, m1.selection)
        assert m1.model_probability == m0.calibrated_probability
        assert m1.classification == m0.classification          # item 3 ainda nao
        if m1.prob_source == "mercado":
            ref = L.prob_mercado_do_pick(m1.market_type, m1.selection, _MATCH["odds"])
            assert ref["mercado_metodo"] in A.METODOS_JUSTOS
            assert m1.calibrated_probability == pytest.approx(ref["prob_mercado"], abs=1e-6)
            assert m1.ev is None
        else:
            assert m1.calibrated_probability == m0.calibrated_probability
    # o ledger, nos dois casos, mede o modelo
    led = L.linhas_do_bundle(b1, _MATCH, _MATCH["stats"])
    assert all(l["calibrated_prob"] == m0.calibrated_probability
               for l, m0 in zip(led, b0.markets))
