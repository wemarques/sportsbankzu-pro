# -*- coding: utf-8 -*-
"""#233 - classificacao em valor + confianca na ancora (item 3 do passo 4).

Com a fonte trocada, a classificacao do #028/#042 (raw do modelo contra
safe_prob, EV do modelo x odd) deixa de descrever o que e publicado. Refeita
em dois eixos com os MESMOS limiares: valor (EV/edge contra o consenso,
#232) e confianca (de onde veio a publicada e em que estado, #219). So a
ancora de mercado fresca sustenta SAFE/NQ; taxa-base, modelo sem referencia
e odd velha param em NEUTRO, rotulados. Circuit breaker de SAFE (#043) e
shadow (#129c) continuam valendo.
"""
import copy

import pytest

from backend.models.market_output import (
    MarketClassification as MC, MarketOutput, MatchMarketBundle, ReasonCode as RC,
)
from backend.services import ancora_mercado as A
from backend.services import ev_classification as EVC
from backend.services.ev_classification import evaluate_match_markets


@pytest.fixture(autouse=True)
def _ligada(monkeypatch, tmp_path):
    monkeypatch.setenv(A.FLAG, "mercado")
    monkeypatch.setenv("TAXAS_BASE_PATH", str(tmp_path / "nao.json"))
    monkeypatch.setattr(EVC, "_is_safe_enabled", lambda lid: True)   # sem circuit breaker por padrao
    # #242 - os limiares tem de ser os DOCUMENTADOS nos comentarios deste
    # arquivo, nao os que a RDS tiver no momento. `_get_thresholds` consulta
    # a calibracao por liga (#055, via get_lambda_corrections) e a tabela
    # `thresholds` do audit: numa maquina com DATABASE_URL, `safe_prob` de
    # Over/Under vinha 0.60 em vez de 0.75 e `m3` virava SAFE — a suite
    # falhava por ORDEM (o cache do #231-a segura a leitura por 300 s), e o
    # teste sozinho passava. Aqui o objeto medido e a LOGICA de
    # classificacao; qual limiar esta vivo e outra pergunta.
    from backend.modeling import lambda_calculator as LC
    LC.limpar_cache_correcoes()
    monkeypatch.setattr(LC, "get_lambda_corrections", lambda league: {})
    monkeypatch.setattr(EVC, "_get_thresholds",
                        lambda cat, league_id=None: dict(EVC.DEFAULT_THRESHOLDS[cat]))
    A.limpar_cache_taxas()
    yield
    LC.limpar_cache_correcoes()
    A.limpar_cache_taxas()


def _mo(market, selection, prob, odd=None, quality=0.8):
    m = MarketOutput(market_type=market, selection=selection, raw_probability=prob,
                     calibrated_probability=prob, book_odd=odd, data_quality_score=quality,
                     classification=MC.SAFE)                 # o que o modelo dizia
    m.compute_display(); m.compute_ev()
    return m


def _bundle(*ms):
    return MatchMarketBundle(match_id="1", home_team="A", away_team="B", league_id="championship", markets=list(ms))


def _cons(chave, p, n=5):
    return {chave: {"p_justa": p, "n_casas": n, "odd_mediana": 1.9, "odd_max": 2.0}}


# par FootyStats Over/Under 1.5: 1.25/4.20 -> publicada 0.781 (>= safe_prob 0.75 e neutro 0.60)
_ODDS_O15 = {"over15": 1.25, "under15": 4.20}


def _pub(m):
    return m.calibrated_probability


def test_safe_exige_ancora_fresca_e_valor_contra_consenso():
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    b = _bundle(m)
    A.aplicar_ancora(b, {"odds": _ODDS_O15, "odds_consenso": _cons("over15", 0.86)})
    assert m.prob_source == "mercado" and _pub(m) >= 0.75
    assert m.ev == pytest.approx(0.86 * 1.25 - 1, abs=1e-4)      # +7,5% contra consenso
    assert m.classification == MC.SAFE
    assert RC.ANCHOR_MARKET in m.reason_codes and RC.POSITIVE_EV in m.reason_codes
    assert b.eligible_for_multiples is True


def test_circuit_breaker_de_safe_continua_valendo(monkeypatch):
    monkeypatch.setattr(EVC, "_is_safe_enabled", lambda lid: False)
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    A.aplicar_ancora(_bundle(m), {"odds": _ODDS_O15, "odds_consenso": _cons("over15", 0.86)})
    assert m.classification == MC.NEUTRO_QUALIFICADO
    assert RC.SAFE_CIRCUIT_BREAKER in m.reason_codes


def test_ev_negativo_contra_consenso_e_no_bet_mesmo_com_probabilidade_alta():
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    A.aplicar_ancora(_bundle(m), {"odds": _ODDS_O15, "odds_consenso": _cons("over15", 0.74)})
    assert _pub(m) >= 0.75 and m.ev < 0
    assert m.classification == MC.NO_BET and RC.NEGATIVE_EV in m.reason_codes


def test_sem_consenso_no_maximo_neutro_informativo():
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    b = _bundle(m)
    A.aplicar_ancora(b, {"odds": _ODDS_O15})
    assert m.ev is None
    assert m.classification == MC.NEUTRO
    assert RC.NO_VALUE_REFERENCE in m.reason_codes and RC.ANCHOR_MARKET in m.reason_codes
    assert b.eligible_for_multiples is False


def test_ev_floor_e_ev_suspeito_seguem_os_mesmos_numeros():
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    A.aplicar_ancora(_bundle(m), {"odds": _ODDS_O15, "odds_consenso": _cons("over15", 0.805)})
    assert 0 <= m.ev < EVC.EV_FLOOR
    assert m.classification == MC.NO_BET and RC.EV_FLOOR_DROP in m.reason_codes

    m2 = _mo("Over/Under", "Over 4.5", 0.10, 9.0)
    A.aplicar_ancora(_bundle(m2), {"odds": {"over45": 9.0, "under45": 1.08},
                                   "odds_consenso": _cons("over45", 0.20)})
    assert m2.ev is None and RC.SUSPICIOUS_EV in m2.reason_codes        # 0.2*9-1 = +80% > 40%
    assert m2.classification == MC.NO_BET                                # p ~0.10 < neutro_prob


def test_odd_velha_taxa_base_e_modelo_param_em_neutro_rotulados(monkeypatch, tmp_path):
    import json
    art = tmp_path / "t.json"
    art.write_text(json.dumps({"min_n": 30, "celulas": {"*": {"Cards|Over 1.5": {"taxa": 0.91, "n": 500}}}}))
    monkeypatch.setenv("TAXAS_BASE_PATH", str(art)); A.limpar_cache_taxas()

    velha = _mo("Over/Under", "Over 1.5", 0.60, 1.25)          # margem 25 pp: fora de mercado (#219)
    taxa = _mo("Cards", "Over 1.5", 0.68, 1.10)
    modelo = _mo("Corners", "Corners Over 11.5", 0.70, 2.63)  # so uma perna: implicita nao ancora
    b = _bundle(velha, taxa, modelo)
    A.aplicar_ancora(b, {"odds": {"over15": 1.10, "under15": 3.54, "cornersOver115": 2.63},
                         "odds_consenso": {**_cons("over15", 0.95), **_cons("cards_over_1.5", 0.95),
                                           **_cons("cornersOver115", 0.45)}})
    assert velha.ancora_referencia["frescor"] == "margem_fora_de_mercado"
    assert velha.classification == MC.NEUTRO and RC.ANCHOR_STALE in velha.reason_codes
    assert taxa.prob_source == "taxa_base" and taxa.classification == MC.NEUTRO
    assert RC.BASE_RATE_ONLY in taxa.reason_codes and taxa.ev > 0
    assert modelo.prob_source == "modelo_sem_referencia" and modelo.classification == MC.NEUTRO
    assert RC.MODEL_ONLY in modelo.reason_codes
    assert b.eligible_for_multiples is False                  # nenhum SAFE/NQ sem ancora fresca


def test_neutro_qualificado_so_com_ancora_fresca_e_valor():
    # Over/Under neutro_prob 0.60: par 1.60/2.30 -> publicada ~0.585 < 0.60 -> NO_BET por prob
    m = _mo("Over/Under", "Over 2.5", 0.55, 1.60)
    A.aplicar_ancora(_bundle(m), {"odds": {"over25": 1.60, "under25": 2.30},
                                  "odds_consenso": _cons("over25", 0.66)})
    assert m.classification == MC.NO_BET
    # par 1.45/2.70 -> publicada ~0.65 >= 0.60; ev 0.72*1.45-1 = +4.4% < min_ev 5% -> NEUTRO, nao NQ
    m2 = _mo("Over/Under", "Over 2.5", 0.55, 1.45)
    A.aplicar_ancora(_bundle(m2), {"odds": {"over25": 1.45, "under25": 2.70},
                                   "odds_consenso": _cons("over25", 0.72)})
    assert m2.classification == MC.NEUTRO
    # ev 0.74*1.45-1 = +7.3%, edge 0.74-0.69 = +5% -> NQ
    m3 = _mo("Over/Under", "Over 2.5", 0.55, 1.45)
    A.aplicar_ancora(_bundle(m3), {"odds": {"over25": 1.45, "under25": 2.70},
                                   "odds_consenso": _cons("over25", 0.74)})
    assert m3.classification == MC.NEUTRO_QUALIFICADO


def test_flag_desligada_nao_reclassifica(monkeypatch):
    monkeypatch.delenv(A.FLAG)
    m = _mo("Over/Under", "Over 1.5", 0.60, 1.25)
    A.aplicar_ancora(_bundle(m), {"odds": _ODDS_O15, "odds_consenso": _cons("over15", 0.86)})
    assert m.classification == MC.SAFE and m.reason_codes == []


# ── ponta a ponta: insights e elegibilidade seguem a classificacao nova ──
def test_ponta_a_ponta_insights_e_elegibilidade_seguem_a_reclassificacao():
    from tests.test_231_prob_source import _MATCH
    cons = {"over15": {"p_justa": 0.80, "n_casas": 5}, "under35": {"p_justa": 0.60, "n_casas": 5}}
    md = copy.deepcopy(_MATCH); md["odds_consenso"] = cons
    b = evaluate_match_markets(md, league_id="championship")
    por = {(m.market_type, m.selection): m for m in b.markets}
    o15 = por[("Over/Under", "Over 1.5")]
    assert o15.ev == pytest.approx(0.80 * 1.22 - 1, abs=1e-4) and o15.ev < 0
    assert o15.classification == MC.NO_BET
    # insight de rejeicao fala do consenso, nao da deflacao
    ins = {i["market"]: i for i in b.rejected_insights}
    assert any("consenso" in i["reason"] for i in ins.values())
    assert b.eligible_for_multiples == any(
        m.classification in (MC.SAFE, MC.NEUTRO_QUALIFICADO) and m.odds_available for m in b.markets)
