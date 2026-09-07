# -*- coding: utf-8 -*-
"""#237 - o DataMapper descartava a escada de odds antes de o record ler.

Depois do deploy do #236 a cobertura por produtor mostrou 81 linhas, todas do
produtor principal (league-matches), com Under 1.5 em 5/14 e Corners Under
11.5 em 1/9. O caminho principal passa cada linha por
DataMapper.matches_to_df, que reconstroi o dict com uma lista fixa de chaves:
odds_ft_under15/35/45, odds_doublechance_* e odds_corners_under_* nao
estavam nela. O teste do #230-g/h usava _rows_override, que pula o mapper —
por isso passou enquanto a producao descartava.
"""
import time

import pandas as pd

from backend.services.data_mapper import DataMapper
from backend.services.fixtures_service import build_records_from_matches, odds_do_row
from backend.services.prediction_ledger import prob_mercado_do_pick
from tests.test_236_odds_do_row import _LINHA


def _raw(ts):
    return {"id": 1, "date_unix": ts, "status": "incomplete", "home_name": "Casa", "away_name": "Fora",
            "competition_id": 5, **_LINHA}


def test_matches_to_df_preserva_a_escada_inteira():
    df = DataMapper.matches_to_df([_raw(int(time.time()) + 3600)])
    for k in ("odds_ft_under15", "odds_ft_under45", "odds_ft_over05", "odds_doublechance_1x",
              "odds_corners_under_95", "odds_corners_under_115", "odds_corners_over_75"):
        assert k in df.columns, k
    assert float(df.iloc[0]["odds_ft_under15"]) == 6.12
    assert float(df.iloc[0]["odds_corners_under_115"]) == 1.36


def test_caminho_principal_sem_rows_override_publica_os_pares():
    """O caminho REAL: linha crua -> DataMapper -> DataFrame -> record."""
    ts = int(time.time()) + 3600
    df = DataMapper.matches_to_df([_raw(ts)])
    liga = {"average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
            "average_cards_per_match": 4.9, "matches_completed": 25}
    recs = build_records_from_matches(league_id="championship", matches=df, teams=None,
                                      league_df=pd.DataFrame([liga]), date_filter="today")
    assert len(recs) == 1
    odds = recs[0]["odds"]
    assert odds["under15"] == 6.12 and odds["under45"] == 1.21 and odds["over05"] == 1.01
    assert odds["cornersUnder115"] == 1.36 and odds["cornersOver75"] == 1.18
    assert odds["dc_1x"] == 1.25 and odds["dc_12"] is None
    assert (odds["home"], odds["draw"], odds["away"]) == (1.91, 3.75, 3.5)
    assert prob_mercado_do_pick("Over/Under", "Under 1.5", odds)["mercado_metodo"] == "devig"
    assert prob_mercado_do_pick("Corners", "Corners Under 11.5", odds)["mercado_metodo"] == "devig"
    assert prob_mercado_do_pick("Double Chance", "DC 1X", odds)["mercado_metodo"] == "devig3"


def test_manifesto_declara_os_campos_novos_como_consumidos():
    import backend.config.footystats_manifest as mf
    for k in ("odds_ft_under15", "odds_corners_under_95", "odds_doublechance_1x"):
        assert mf.CAMPOS[k][0] == mf.CONSUMIDO
    assert mf.verificar()["bloqueia"] == []
