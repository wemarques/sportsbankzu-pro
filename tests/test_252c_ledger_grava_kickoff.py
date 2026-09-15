# -*- coding: utf-8 -*-
"""#252-c - o ledger grava `kickoff_utc`, com UMA regra de resolucao.

`linhas_do_bundle` nunca passava `kickoff_utc` a `montar_linha`: a coluna era
nula em 100% das linhas e todo filtro pre-apito ficava inerte (#252). O record
carrega `datetime` ISO com fuso (medido: igual ao sufixo epoch do id em 79/79
records reais); na falta dele, o sufixo. A resolucao vive em
`prediction_ledger.kickoff_da_linha`, importada pelos scripts e pela camada.
"""
from datetime import datetime, timezone
from pathlib import Path

from backend.services import prediction_ledger as L
from backend.models.market_output import (
    MarketClassification, MarketOutput, MatchMarketBundle,
)

_UTC = timezone.utc
_RAIZ = Path(__file__).resolve().parents[1]
_ID = "2-bundesliga-Heidenheim-Holstein Kiel-1789299000.0"
_KICK = datetime(2026, 9, 13, 11, 30, tzinfo=_UTC)


def _bundle(match_id):
    return MatchMarketBundle(
        match_id=match_id, home_team="A", away_team="B", league_id="x",
        data_quality_score=0.5,
        markets=[MarketOutput(market_type="BTTS", selection="BTTS Yes",
                              raw_probability=0.55, calibrated_probability=0.52,
                              classification=MarketClassification.NEUTRO, reason_codes=[])],
    )


def test_kickoff_do_record_le_o_datetime_iso():
    assert L.kickoff_do_record({"datetime": "2026-09-13T11:30:00Z"}, "sem-epoch") == _KICK


def test_kickoff_do_record_cai_no_sufixo_sem_datetime():
    assert L.kickoff_do_record({}, _ID) == _KICK
    assert L.kickoff_do_record({"datetime": "lixo"}, _ID) == _KICK


def test_datetime_sem_fuso_nao_e_adivinhado():
    assert L.kickoff_do_record({"datetime": "2026-09-13T11:30:00"}, "liga-todays-99") is None


def test_kickoff_da_linha_prefere_gravado_e_recusa_todays_e_epoch_implausivel():
    gravado = datetime(2026, 9, 13, 12, 0, tzinfo=_UTC)
    assert L.kickoff_da_linha(_ID, gravado) == gravado
    assert L.kickoff_da_linha(_ID, None) == _KICK
    assert L.kickoff_da_linha("premier-league-todays-12345", None) is None
    assert L.kickoff_da_linha("liga-casa-fora-12345", None) is None


def test_linhas_do_bundle_grava_kickoff_utc():
    linhas = L.linhas_do_bundle(_bundle(_ID), {"id": _ID, "datetime": "2026-09-13T11:30:00Z"}, {})
    assert linhas and all(l["kickoff_utc"] == _KICK for l in linhas)


def test_kickoff_utc_nao_entra_no_hash():
    """Gravar o kickoff nao pode criar geracao nova do mesmo prognostico."""
    com = L.linhas_do_bundle(_bundle(_ID), {"id": _ID, "datetime": "2026-09-13T11:30:00Z"}, {})[0]
    sem = L.montar_linha(**{k: com[k] for k in (
        "match_id", "league_id", "market", "selection", "raw_prob", "iso_prob",
        "calibrated_prob", "band_type", "book_odd", "odd_source", "overround", "ev",
        "classification", "stake", "reason_codes", "governance", "inputs",
        "prob_mercado", "mercado_metodo", "odd_par", "margem_pp", "frescor",
        "published_prob", "prob_source")})
    assert sem["kickoff_utc"] is None and sem["payload_hash"] == com["payload_hash"]


def test_uma_implementacao_so():
    import importlib
    import sys
    sys.path.insert(0, str(_RAIZ))
    A = importlib.import_module("scripts.amostra_ledger")
    from backend.modeling.calibragem import repositorio as R
    assert A.kickoff_da_linha is L.kickoff_da_linha
    assert R.kickoff_da_linha is L.kickoff_da_linha
    for caminho in ("scripts/amostra_ledger.py", "backend/modeling/calibragem/repositorio.py"):
        assert "fromtimestamp" not in (_RAIZ / caminho).read_text(encoding="utf-8"), caminho
