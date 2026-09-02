"""#218 - o ledger imutavel: so insere, guarda as entradas, e falha aberto."""
import json
import pytest

from backend.services import prediction_ledger as L
from backend.models.market_output import (
    MarketOutput, MatchMarketBundle, MarketClassification, ReasonCode,
)


@pytest.fixture(autouse=True)
def _ledger_desligado(monkeypatch):
    monkeypatch.delenv("PREDICTION_LEDGER_ENABLED", raising=False)


def _linha(**kw):
    base = dict(match_id="m1", league_id="championship", market="Corners",
                selection="Corners Over 9.5", raw_prob=0.80,
                calibrated_prob=0.72, book_odd=2.10)
    base.update(kw)
    return L.montar_linha(**base)


# ── hash de conteudo ────────────────────────────────────────────────────
def test_mesmo_conteudo_mesmo_hash():
    assert _linha()["payload_hash"] == _linha()["payload_hash"]


def test_qualquer_numero_diferente_muda_o_hash():
    a = _linha()
    for campo, valor in [("raw_prob", 0.81), ("calibrated_prob", 0.71),
                         ("book_odd", 2.11), ("league_id", "league-one")]:
        assert _linha(**{campo: valor})["payload_hash"] != a["payload_hash"], campo


def test_hash_ignora_o_carimbo_de_tempo():
    """Senao o ledger viraria log de requisicao: /fixtures e chamado o dia todo."""
    a = _linha()
    assert "published_at" not in a


# ── entradas ────────────────────────────────────────────────────────────
def test_linha_carrega_as_entradas_que_explicam_o_numero():
    bundle = MatchMarketBundle(
        match_id="m9", home_team="A", away_team="B",
        league_id="championship", data_quality_score=0.61,
        markets=[MarketOutput(
            market_type="Corners", selection="Corners Over 9.5",
            raw_probability=0.80, calibrated_probability=0.72,
            iso_probability=0.80, deflation_band_type="inteira",
            classification=MarketClassification.NO_BET,
            reason_codes=[ReasonCode.CORNER_ENGINE_NO_BET],
        )],
    )
    stats = {"lambdaHome": 1.4, "lambdaAway": 1.1, "cardsLambda": 4.7,
             "homeMatchesPlayed": 24, "awayMatchesPlayed": 25,
             "dataAgeHours": 6.5}
    linhas = L.linhas_do_bundle(bundle, {"id": "m9"}, stats)
    assert len(linhas) == 1
    e = linhas[0]["inputs"]
    assert e["lambda_home"] == 1.4 and e["lambda_away"] == 1.1
    assert e["cards_lambda"] == 4.7
    assert e["home_matches"] == 24 and e["away_matches"] == 25
    assert e["data_age_hours"] == 6.5
    assert e["data_quality_score"] == 0.61
    # os dois passos da calibracao entram separados (#216)
    assert linhas[0]["iso_prob"] == 0.80
    assert linhas[0]["calibrated_prob"] == 0.72
    assert linhas[0]["band_type"] == "inteira"
    assert linhas[0]["reason_codes"] == ["CORNER_ENGINE_NO_BET"]


def test_veto_do_217_vai_para_a_governanca():
    m = MarketOutput(market_type="Corners", selection="Corners Over 9.5",
                     raw_probability=0.8, calibrated_probability=0.7)
    m.corner_veto = {"noBet": True, "reason": "restricted_market", "scope": "family"}
    bundle = MatchMarketBundle(match_id="m1", home_team="A", away_team="B",
                               league_id="championship", markets=[m])
    linhas = L.linhas_do_bundle(bundle)
    assert linhas[0]["governance"]["veto"]["reason"] == "restricted_market"


# ── falha aberta e flag ─────────────────────────────────────────────────
def test_desligado_nao_grava_nada():
    assert L.ledger_habilitado() is False
    assert L.registrar([_linha()]) == 0


def test_ligado_sem_banco_falha_aberto(monkeypatch):
    """Sem DATABASE_URL valido a escrita falha — e nao pode propagar."""
    monkeypatch.setenv("PREDICTION_LEDGER_ENABLED", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/nao_existe")
    assert L.registrar([_linha()]) == 0
    assert L.registrar_desfecho("m1", "Corners", 1) is False
    assert L.garantir_tabelas() is False


def test_lote_vazio():
    assert L.registrar([]) == 0


# ── serializavel ────────────────────────────────────────────────────────
def test_linha_e_serializavel_em_json():
    json.dumps(_linha(), default=str)


# ── ausencia de UPDATE/DELETE no modulo ─────────────────────────────────
def test_o_modulo_nao_contem_update_nem_delete():
    """Append-only nao e uma promessa no README, e uma propriedade do codigo."""
    import inspect
    fonte = inspect.getsource(L).upper()
    corpo = fonte.split('"""', 2)[-1]          # ignora o docstring do modulo
    assert "UPDATE PREDICTION_LEDGER" not in corpo
    assert "DELETE FROM" not in corpo
    assert "DO UPDATE" not in corpo
