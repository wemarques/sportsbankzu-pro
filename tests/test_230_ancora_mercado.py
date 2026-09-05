# -*- coding: utf-8 -*-
"""#230 - a ancora de mercado gravada ao lado da probabilidade publicada.

Decisao de produto (Welligton, 2026-09-03): ancorar a probabilidade no mercado
de-vigado (#219) e usar o modelo como ajuste minimo ou nenhum. Antes de trocar
a fonte, o ledger passa a gravar as duas — publicada e de mercado — no mesmo
instante, para que a troca seja decidida por medicao nos MESMOS picks
(comparar_com_mercado.py --ledger), nao por confianca.
"""
import pytest

from backend.services import prediction_ledger as L
from backend.models.market_output import (
    MarketClassification, MarketOutput, MatchMarketBundle, ReasonCode,
)

# `odds` do record depois do enriquecimento #120 — nomes medidos em
# routes/fixtures.py, nao inventados.
_ODDS = {
    "home": 2.10, "draw": 3.40, "away": 3.50,
    "over25": 1.90, "under25": 1.95, "over35": 3.10, "under35": 1.38,
    "bttsYes": 1.80, "bttsNo": 2.00,
    "cornersOver95": 1.85, "cornersUnder95": 1.95,
    "cards_over_3.5": 1.75, "cards_under_3.5": 2.05,
}


# ── o par, por familia, com os nomes reais ───────────────────────────────
@pytest.mark.parametrize("market, selection, propria, par", [
    ("Over/Under", "Over 2.5", 1.90, 1.95),
    ("Over/Under", "Under 2.5", 1.95, 1.90),
    ("Over/Under", "Over 3.5", 3.10, 1.38),
    ("BTTS", "BTTS Yes", 1.80, 2.00),
    ("Corners", "Corners Over 9.5", 1.85, 1.95),
    ("Corners", "Corners Under 9.5", 1.95, 1.85),
    ("Cards", "Over 3.5", 1.75, 2.05),
    ("Cards", "Under 3.5", 2.05, 1.75),
    ("1X2", "Home", 2.10, None),          # tres pernas: sem par de duas
    ("Over/Under", "Over 4.5", None, None),  # linha sem odd no record
])
def test_par_de_odds_usa_os_nomes_reais(market, selection, propria, par):
    assert L.par_de_odds(market, selection, _ODDS) == (propria, par)


def test_cards_over_35_nao_e_confundido_com_gols():
    """Mesmo rotulo 'Over 3.5', dicionarios diferentes. Se o par vier de
    `over35`/`under35`, a ancora de cartoes seria a de gols."""
    assert L.par_de_odds("Cards", "Over 3.5", _ODDS) == (1.75, 2.05)
    assert L.par_de_odds("Over/Under", "Over 3.5", _ODDS) == (3.10, 1.38)


# ── a probabilidade de mercado e o metodo ────────────────────────────────
def test_com_par_usa_devig_e_marca_frescor():
    r = L.prob_mercado_do_pick("Over/Under", "Over 2.5", _ODDS)
    assert r["mercado_metodo"] == "devig"
    assert r["odd_par"] == 1.95
    assert 0.49 < r["prob_mercado"] < 0.52          # par quase simetrico ~ 50%
    assert r["prob_mercado"] < 1 / 1.90, "de-vig tem de tirar margem"
    assert r["margem_pp"] is not None and r["frescor"] == "ok"


def test_so_a_propria_perna_e_implicita():
    """#230-e: com o trio completo o 1X2 vira devig3; a implicita fica para
    quando so a propria perna existe."""
    r = L.prob_mercado_do_pick("1X2", "Home", {"home": 2.10})
    assert r["mercado_metodo"] == "implicita"
    assert r["prob_mercado"] == pytest.approx(1 / 2.10, abs=1e-6)
    assert r["odd_par"] is None


def test_sem_odd_nao_inventa():
    r = L.prob_mercado_do_pick("Over/Under", "Over 4.5", _ODDS)
    assert r == {"prob_mercado": None, "mercado_metodo": "sem_odd",
                 "odd_par": None, "margem_pp": None, "frescor": None}
    assert L.prob_mercado_do_pick("BTTS", "BTTS Yes", None)["mercado_metodo"] == "sem_odd"


def test_odd_igual_a_um_e_ausencia():
    """Odd 1.0 nao e preco (#225-a)."""
    r = L.prob_mercado_do_pick("BTTS", "BTTS Yes", {"bttsYes": 1.0, "bttsNo": 2.0})
    assert r["mercado_metodo"] == "sem_odd"


def test_margem_podre_fica_marcada_no_frescor():
    """O detector do #219: par com margem fora de mercado nao e descartado,
    e rotulado — quem le o ledger decide."""
    r = L.prob_mercado_do_pick("Over/Under", "Over 2.5", {"over25": 1.30, "under25": 1.30})
    assert r["mercado_metodo"] == "devig"
    assert r["frescor"] != "ok"


# ── a linha do ledger carrega a ancora ───────────────────────────────────
def _bundle():
    return MatchMarketBundle(
        match_id="m1", home_team="A", away_team="B", league_id="championship",
        data_quality_score=0.6,
        markets=[
            MarketOutput(market_type="Over/Under", selection="Over 2.5",
                         raw_probability=0.61, calibrated_probability=0.55,
                         book_odd=1.90, classification=MarketClassification.NEUTRO,
                         reason_codes=[]),
            MarketOutput(market_type="Corners", selection="Corners Over 9.5",
                         raw_probability=0.58, calibrated_probability=0.52,
                         book_odd=1.85, classification=MarketClassification.NO_BET,
                         reason_codes=[ReasonCode.CORNER_ENGINE_NO_BET]),
            MarketOutput(market_type="Cards", selection="Over 4.5",
                         raw_probability=0.40, calibrated_probability=0.38,
                         classification=MarketClassification.NO_BET, reason_codes=[]),
        ],
    )


def test_linhas_gravam_publicada_e_mercado_lado_a_lado():
    linhas = L.linhas_do_bundle(_bundle(), {"id": "m1", "odds": _ODDS}, {})
    por_sel = {l["selection"]: l for l in linhas}

    ou = por_sel["Over 2.5"]
    assert ou["calibrated_prob"] == 0.55                  # a publicada, intacta
    assert ou["mercado_metodo"] == "devig" and ou["odd_par"] == 1.95
    assert 0.49 < ou["prob_mercado"] < 0.52

    esc = por_sel["Corners Over 9.5"]
    assert esc["mercado_metodo"] == "devig" and esc["odd_par"] == 1.95

    cart = por_sel["Over 4.5"]                            # sem odd de cartao 4.5
    assert cart["mercado_metodo"] == "sem_odd" and cart["prob_mercado"] is None


def test_sem_odds_no_record_nao_quebra():
    linhas = L.linhas_do_bundle(_bundle(), {"id": "m1"}, {})
    assert len(linhas) == 3
    assert all(l["mercado_metodo"] == "sem_odd" for l in linhas)


def test_odd_que_mexeu_e_revisao_nova():
    """O hash inclui a odd do par: preco novo = informacao nova = linha nova.
    Preco igual = mesmo prognostico = nada gravado (#218)."""
    a = L.linhas_do_bundle(_bundle(), {"id": "m1", "odds": _ODDS}, {})[0]
    b = L.linhas_do_bundle(_bundle(), {"id": "m1", "odds": {**_ODDS, "under25": 2.05}}, {})[0]
    c = L.linhas_do_bundle(_bundle(), {"id": "m1", "odds": dict(_ODDS)}, {})[0]
    assert a["payload_hash"] != b["payload_hash"]
    assert a["payload_hash"] == c["payload_hash"]


def test_ddl_e_migracao_tem_as_colunas():
    for col in ("prob_mercado", "mercado_metodo", "odd_par", "margem_pp", "frescor"):
        assert col in L._DDL_LEDGER
        assert col in L._COLUNAS
        assert any(f"ADD COLUMN IF NOT EXISTS {col}" in d for d in L._DDL_LEDGER_MIGRACAO)


def test_comparador_le_do_ledger_por_selecao():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "comparar_com_mercado.py").read_text(encoding="utf-8")
    assert "l.prob_mercado" in src and "o.selection = COALESCE(l.selection, '')" in src
    assert "--ledger" in src


# ── #230-a: DSN vazio e erro, nao localhost ──────────────────────────────
def test_dsn_vazio_da_erro_claro_e_nao_tenta_localhost(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL nao esta definida"):
        L.dsn_obrigatorio()
    monkeypatch.setenv("DATABASE_URL", "   ")
    with pytest.raises(RuntimeError):
        L.dsn_obrigatorio()
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    assert L.dsn_obrigatorio() == "postgresql://u:p@h:5432/db"


def test_scripts_nao_conectam_com_dsn_vazio():
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    for nome in ("medir_inclinacao.py", "comparar_com_mercado.py"):
        src = (raiz / nome).read_text(encoding="utf-8")
        assert 'psycopg2.connect(os.environ.get("DATABASE_URL", ""))' not in src, nome
        assert "dsn_obrigatorio()" in src, nome


# ── #230-e: 1X2 em tres pernas, Dupla Chance a partir delas ──────────────
def test_1x2_usa_devig_de_tres_pernas():
    r = L.prob_mercado_do_pick("1X2", "Home", _ODDS)
    assert r["mercado_metodo"] == "devig3"
    assert r["prob_mercado"] == pytest.approx(0.4558, abs=2e-3)   # Shin([2.10,3.40,3.50])[0]
    assert r["prob_mercado"] < 1 / 2.10, "tres pernas de-vigadas somam 1; 1/odd somava 1.056"
    assert r["frescor"] == "ok" and r["margem_pp"] == pytest.approx(5.6, abs=0.1)

    soma = sum(L.prob_mercado_do_pick("1X2", s, _ODDS)["prob_mercado"]
               for s in ("Home", "Draw", "Away"))
    assert soma == pytest.approx(1.0, abs=5e-6)     # tres arredondamentos a 6 casas


def test_dupla_chance_e_a_soma_de_duas_pernas_de_vigadas():
    p1, px, p2 = (L.prob_mercado_do_pick("1X2", s, _ODDS)["prob_mercado"]
                  for s in ("Home", "Draw", "Away"))
    for sel, esperado in (("DC 1X", p1 + px), ("DC 12", p1 + p2), ("DC X2", px + p2)):
        r = L.prob_mercado_do_pick("Double Chance", sel, _ODDS)
        assert r["mercado_metodo"] == "devig3"
        assert r["prob_mercado"] == pytest.approx(esperado, abs=5e-6), sel   # arredondamento


def test_sem_o_trio_1x2_cai_para_a_propria_odd():
    so_dc = {"dc_1x": 1.35}
    r = L.prob_mercado_do_pick("Double Chance", "DC 1X", so_dc)
    assert (r["mercado_metodo"], r["prob_mercado"]) == ("implicita", pytest.approx(1 / 1.35, abs=1e-6))
    so_home = {"home": 2.10}
    r = L.prob_mercado_do_pick("1X2", "Home", so_home)
    assert r["mercado_metodo"] == "implicita"
    assert L.prob_mercado_do_pick("Double Chance", "DC 12", {})["mercado_metodo"] == "sem_odd"


def test_linhas_de_dc_agora_tem_ancora():
    b = MatchMarketBundle(
        match_id="m2", home_team="A", away_team="B", league_id="x", data_quality_score=0.5,
        markets=[MarketOutput(market_type="Double Chance", selection="DC 1X",
                              raw_probability=0.7, calibrated_probability=0.66,
                              classification=MarketClassification.NEUTRO, reason_codes=[])],
    )
    l = L.linhas_do_bundle(b, {"id": "m2", "odds": _ODDS}, {})[0]
    assert l["mercado_metodo"] == "devig3" and 0.7 < l["prob_mercado"] < 0.76


def test_comparador_so_devigados_por_padrao_e_mostra_jogos():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "comparar_com_mercado.py").read_text(encoding="utf-8")
    assert "mercado_metodo IN ('devig', 'devig3')" in src
    assert "--incluir-implicita" in src
    assert "MIN_JOGOS_LIGA" in src and "def _jogos(" in src
