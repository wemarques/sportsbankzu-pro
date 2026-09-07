# -*- coding: utf-8 -*-
"""#232 - EV contra o preco justo de consenso entre casas (item 2 do passo 4).

Com a ancora do #231, prob x odd da mesma fonte e o de-vig ao contrario: EV
<= 0 por construcao. O preco justo independente e a mediana dos de-vigs por
casa na resposta inteira do /odds da API-Football (#120), que o
enriquecimento ja busca e de que so usava a primeira casa. Sem consenso de
pelo menos MIN_CASAS_CONSENSO casas, nao ha EV — e o motivo fica no payload.
"""
import copy

import pytest

from backend.models.market_output import MarketClassification, MarketOutput, MatchMarketBundle
from backend.services import ancora_mercado as A
from backend.services import consenso_odds as C
from backend.services.devig import devig


def _bet(name, values, bid=1):
    return {"id": bid, "name": name, "values": [{"value": v, "odd": str(o)} for v, o in values]}


def _casa(nome, over25, under25, home=None, draw=None, away=None, dc_1x=None, esc=None):
    bets = [_bet("Goals Over/Under", [("Over 2.5", over25), ("Under 2.5", under25)])]
    if home:
        bets.append(_bet("Match Winner", [("Home", home), ("Draw", draw), ("Away", away)], 2))
    if dc_1x:
        bets.append(_bet("Double Chance", [("Home/Draw", dc_1x)], 3))
    if esc:
        bets.append(_bet("Corners Over Under", [("Over 9.5", esc[0]), ("Under 9.5", esc[1])], 4))
    return {"name": nome, "bets": bets}


# O consenso pende para o Over (4 de 5 casas pagam menos no Over): p_justa
# do Over 2.5 fica acima de 0,5, diferente do par simetrico da FootyStats
# (1.90/1.90) usado como ancora nos testes abaixo — e isso que separa "EV
# contra consenso" de "prob x odd da mesma fonte".
_CASAS = [
    _casa("Bet365", 1.80, 2.00, 1.95, 3.60, 3.70, 1.25, (1.80, 1.95)),
    _casa("Pinnacle", 1.83, 2.02, 2.00, 3.55, 3.60),
    _casa("Unibet", 1.78, 2.05, 1.92, 3.60, 3.80),
    _casa("Betfair", 2.05, 1.80, 1.98, 3.50, 3.75),
    _casa("1xBet", 1.85, 1.97, 1.96, 3.65, 3.65),
]
_RESPOSTA = [{"bookmakers": _CASAS[:3]}, {"bookmakers": _CASAS[3:] + [_CASAS[0]]}]  # pagina 2 repete a Bet365


# ── o consenso ───────────────────────────────────────────────────────────
def test_consenso_e_mediana_dos_devigs_por_casa_uma_casa_uma_vez():
    c = C.consenso_por_selecao(_RESPOSTA)
    o25 = c["over25"]
    assert o25["n_casas"] == 5                      # Bet365 repetida na pagina 2 conta uma vez
    esperado = sorted(devig([a, b])[0] for a, b in
                      [(1.80, 2.00), (1.83, 2.02), (1.78, 2.05), (2.05, 1.80), (1.85, 1.97)])[2]
    assert o25["p_justa"] == pytest.approx(esperado, abs=1e-6)
    assert o25["odd_max"] == 2.05 and o25["casa_max"] == "Betfair"
    assert o25["odd_mediana"] == 1.83
    assert o25["p_justa"] > 0.5
    assert c["under25"]["n_casas"] == 5
    assert c["over25"]["p_justa"] + c["under25"]["p_justa"] == pytest.approx(1.0, abs=2e-3)


def test_1x2_por_trio_e_dc_por_soma_e_escanteios_so_onde_ha_par():
    c = C.consenso_por_selecao(_RESPOSTA)
    assert c["home"]["n_casas"] == 5 and c["draw"]["n_casas"] == 5
    assert c["home"]["p_justa"] + c["draw"]["p_justa"] + c["away"]["p_justa"] == pytest.approx(1.0, abs=5e-3)
    assert c["dc_1x"]["n_casas"] == 1               # so a Bet365 cota DC
    assert c["cornersOver95"]["n_casas"] == 1
    assert "cornersOver85" not in c


def test_casa_sem_par_nao_entra_e_resposta_vazia_da_vazio():
    so_over = {"name": "Solta", "bets": [_bet("Goals Over/Under", [("Over 2.5", 1.90)])]}
    assert C.consenso_por_selecao([{"bookmakers": [so_over]}]) == {}
    assert C.consenso_por_selecao(None) == {} and C.consenso_por_selecao([]) == {}


@pytest.mark.parametrize("market, selection, chave", [
    ("Over/Under", "Over 2.5", "over25"), ("Over/Under", "Under 1.5", "under15"),
    ("BTTS", "BTTS Yes", "bttsYes"), ("BTTS", "BTTS No", "bttsNo"),
    ("Corners", "Corners Over 9.5", "cornersOver95"), ("Corners", "Corners Under 10.5", "cornersUnder105"),
    ("Cards", "Over 3.5", "cards_over_3.5"), ("Cards", "Under 1.5", "cards_under_1.5"),
    ("1X2", "Home", "home"), ("1X2", "Draw", "draw"),
    ("Double Chance", "DC 1X", "dc_1x"), ("Double Chance", "DC X2", "dc_x2"),
    ("Outro", "?", None),
])
def test_chave_da_selecao_espelha_o_record(market, selection, chave):
    assert C.chave_da_selecao(market, selection) == chave


# ── o EV ─────────────────────────────────────────────────────────────────
def test_ev_contra_consenso_e_os_motivos_de_nao_haver():
    cons = {"p_justa": 0.52, "n_casas": 5, "odd_mediana": 1.83, "odd_max": 2.05}
    r = C.ev_contra_consenso(2.05, cons)
    assert r["ev"] == pytest.approx(0.52 * 2.05 - 1, abs=1e-4)
    assert r["edge"] == pytest.approx(0.52 - 1 / 2.05, abs=1e-4)
    assert r["referencia"]["fonte"] == "consenso" and r["referencia"]["n_casas"] == 5
    assert C.ev_contra_consenso(None, cons)["referencia"]["motivo"] == "sem_odd"
    assert C.ev_contra_consenso(2.05, None)["referencia"]["motivo"] == "sem_consenso"
    r2 = C.ev_contra_consenso(2.05, {**cons, "n_casas": 2})
    assert r2["ev"] is None and r2["referencia"]["motivo"] == "poucas_casas"


# ── no bundle, com a flag ────────────────────────────────────────────────
_ODDS = {"over25": 1.90, "under25": 1.90, "bttsYes": 1.75, "bttsNo": 2.00, "home": 1.95, "draw": 3.60, "away": 3.70}


def _mo(market, selection, prob, odd=None):
    m = MarketOutput(market_type=market, selection=selection, raw_probability=prob + 0.05,
                     calibrated_probability=prob, book_odd=odd, classification=MarketClassification.NEUTRO)
    m.compute_display(); m.compute_ev()
    return m


def _bundle():
    return MatchMarketBundle(match_id="1", home_team="A", away_team="B", league_id="championship", markets=[
        _mo("Over/Under", "Over 2.5", 0.50, 1.90),
        _mo("BTTS", "BTTS Yes", 0.52, 1.75),          # sem consenso na resposta
        _mo("Cards", "Over 1.5", 0.68),                # sem odd
    ])


@pytest.fixture(autouse=True)
def _limpo(monkeypatch, tmp_path):
    monkeypatch.delenv(A.FLAG, raising=False)
    monkeypatch.setenv("TAXAS_BASE_PATH", str(tmp_path / "nao.json"))
    A.limpar_cache_taxas()
    yield
    A.limpar_cache_taxas()


def test_flag_desligada_ev_continua_o_do_modelo():
    b = _bundle()
    antes = [m.to_legacy_mercado() for m in b.markets]
    A.aplicar_ancora(b, {"odds": _ODDS, "odds_consenso": C.consenso_por_selecao(_RESPOSTA)})
    assert [m.to_legacy_mercado() for m in b.markets] == antes
    assert antes[0]["ev"] == pytest.approx(0.5 * 1.90 - 1, abs=1e-4)
    assert "ev_referencia" not in antes[0]


def test_flag_ligada_ev_e_contra_o_consenso_nunca_contra_a_propria_fonte(monkeypatch):
    monkeypatch.setenv(A.FLAG, "mercado")
    b = _bundle()
    cons = C.consenso_por_selecao(_RESPOSTA)
    A.aplicar_ancora(b, {"odds": _ODDS, "odds_consenso": cons})
    por = {m.selection: m for m in b.markets}
    o25 = por["Over 2.5"]
    assert o25.prob_source == "mercado"
    # a publicada e o de-vig do par da FootyStats (1.90/1.90 -> 0.5); com a
    # odd da mesma fonte o EV seria 0.5*1.90-1 = -0.05, o de-vig ao contrario
    assert o25.calibrated_probability == pytest.approx(0.5, abs=1e-6)
    assert o25.ev == pytest.approx(cons["over25"]["p_justa"] * 1.90 - 1, abs=1e-4)
    assert o25.ev != pytest.approx(-0.05, abs=1e-4)
    assert o25.ev_referencia["fonte"] == "consenso" and o25.ev_referencia["n_casas"] == 5
    d = o25.to_legacy_mercado()
    assert d["ev_referencia"]["fonte"] == "consenso" and d["ev"] == o25.ev
    # BTTS: ancora existe (par FootyStats), mas nao ha consenso -> sem EV, com motivo
    btts = por["BTTS Yes"]
    assert btts.prob_source == "mercado" and btts.ev is None
    assert btts.ev_referencia == {"fonte": None, "motivo": "sem_consenso"}
    # sem odd: sem EV, motivo sem_odd, e a fonte da prob e a de sempre
    c15 = por["Over 1.5"]
    assert c15.ev is None and c15.ev_referencia["motivo"] == "sem_odd"
    assert c15.prob_source == "modelo_sem_referencia"


def test_flag_ligada_sem_consenso_no_jogo_todo_ev_fica_none_com_motivo(monkeypatch):
    monkeypatch.setenv(A.FLAG, "mercado")
    b = _bundle()
    A.aplicar_ancora(b, {"odds": _ODDS})
    assert all(m.ev is None for m in b.markets)
    assert {m.ev_referencia["motivo"] for m in b.markets} == {"sem_consenso", "sem_odd"}


# ── o enriquecimento guarda o consenso so com a flag ─────────────────────
class _AFC:
    is_configured = True

    def __init__(self, resposta, best):
        self.resposta, self.best = resposta, best

    def get_odds(self, af_id, ttl_minutes=0):
        return self.resposta

    def extract_best_odds(self, af_odds, league_id=""):
        return dict(self.best)


def _rec(odds):
    return {"id": "1", "apiFootballFixtureId": 77, "leagueId": "championship",
            "homeTeam": {"name": "A"}, "odds": dict(odds)}


def test_enriquecimento_guarda_consenso_so_com_a_flag_e_enfileira_uma_vez(monkeypatch):
    from backend.routes import fixtures as R
    monkeypatch.setattr(R, "_afc", _AFC(_RESPOSTA, {"over_25": 1.90, "under_25": 1.90, "btts_yes": 1.8}))

    rec = _rec({"over25": 1.90, "under25": 1.90})           # bttsYes vai ser preenchida
    saida = R._enrich_odds_from_api_football([rec])
    assert "odds_consenso" not in rec                        # flag desligada: payload de sempre
    assert saida == [rec] and rec["odds"]["bttsYes"] == 1.8

    monkeypatch.setenv(A.FLAG, "mercado")
    rec = _rec({"over25": 1.90, "under25": 1.90})
    saida = R._enrich_odds_from_api_football([rec])
    assert rec["odds_consenso"]["over25"]["n_casas"] == 5
    assert len(saida) == 1 and saida[0] is rec               # consenso + odd nova: UMA entrada

    rec2 = _rec({"over25": 1.90, "under25": 1.90, "bttsYes": 1.75})   # nada a preencher
    saida = R._enrich_odds_from_api_football([rec2])
    assert saida == [rec2] and "odds_consenso" in rec2       # so o consenso ja reclassifica
