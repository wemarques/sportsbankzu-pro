# -*- coding: utf-8 -*-
"""#236 - um mapeador de odds para os dois produtores do record.

O ledger desde 07/09 mostrava Under 1.5 com ancora em 39% e Corners Under
11.5 em 7% DEPOIS do deploy do #230-g/h. `--hoje` provou que o todays-matches
manda a escada inteira (13/13 pendentes). O elo faltante era o segundo
produtor do record, `_fallback_todays_matches` (routes/fixtures.py), que
montava `odds` so com 1X2, 2.5, BTTS e tres overs. Agora os dois produtores
chamam `fixtures_service.odds_do_row`.
"""
import time
from unittest.mock import patch

import pandas as pd

from backend.services.fixtures_service import odds_do_row, build_records_from_matches

_LINHA = {
    "odds_ft_1": 1.91, "odds_ft_x": 3.75, "odds_ft_2": 3.5,
    "odds_ft_over05": 1.01, "odds_ft_under05": 17, "odds_ft_over15": 1.1, "odds_ft_under15": 6.12,
    "odds_ft_over25": 1.44, "odds_ft_under25": 2.44, "odds_ft_over35": 2.29, "odds_ft_under35": 1.61,
    "odds_ft_over45": 3.8, "odds_ft_under45": 1.21,
    "odds_btts_yes": 1.44, "odds_btts_no": 2.62,
    "odds_doublechance_1x": 1.25, "odds_doublechance_12": 0, "odds_doublechance_x2": 1.88,
    "odds_corners_over_75": 1.18, "odds_corners_under_75": 3.5, "odds_corners_over_95": 1.91,
    "odds_corners_under_95": 2.02, "odds_corners_over_115": 2.75, "odds_corners_under_115": 1.36,
}   # valores reais da varredura --hoje de 2026-09-07 (#235-a)


def test_mapeador_publica_a_escada_inteira_com_os_nomes_do_120():
    o = odds_do_row(_LINHA)
    assert (o["home"], o["draw"], o["away"]) == (1.91, 3.75, 3.5)
    assert o["under15"] == 6.12 and o["under45"] == 1.21 and o["over05"] == 1.01
    assert o["cornersUnder115"] == 1.36 and o["cornersOver75"] == 1.18
    assert o["dc_1x"] == 1.25 and o["dc_x2"] == 1.88
    assert o["dc_12"] is None                       # 0 = "sem odd" da FootyStats
    assert o["cornersOver85"] is None               # ausente na linha
    assert set(o) >= {"under05", "under35", "cornersUnder95", "bttsNo"}


def test_zero_nan_texto_e_um_viram_none_e_series_funciona():
    o = odds_do_row({"odds_ft_1": "abc", "odds_ft_x": float("nan"), "odds_ft_2": 1.0, "odds_ft_over25": "2.10"})
    assert o["home"] is None and o["draw"] is None and o["away"] is None
    assert o["over25"] == 2.10
    assert odds_do_row(pd.Series(_LINHA))["under15"] == 6.12


def test_record_principal_usa_o_mapeador():
    ts = int(time.time()) + 3600
    liga = {"average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
            "average_cards_per_match": 4.9, "matches_completed": 25}
    rec = build_records_from_matches(
        league_id="championship", matches=pd.DataFrame([{"timestamp": ts}]), teams=None,
        league_df=pd.DataFrame([liga]),
        _rows_override=[{"id": 1, "home_team_name": "Casa", "away_team_name": "Fora",
                         "date_unix": ts, "timestamp": ts, "status": "incomplete", **_LINHA}],
        date_filter="today")[0]
    assert rec["odds"] == odds_do_row(_LINHA)


def test_complemento_todays_matches_publica_os_mesmos_pares():
    """O segundo produtor — o que estava jogando os unders fora."""
    from backend.routes import fixtures as R
    from backend.main import date_range
    ini, _ = date_range("2026-09-07")
    linha = {"id": 77, "competition_id": 5, "home_name": "Casa FC", "away_name": "Fora FC",
             "status": "incomplete", "date_unix": int(ini.timestamp()) + 6 * 3600, **_LINHA}
    with patch.object(R.footstats, "get_todays_matches", return_value={"success": True, "data": [linha]}):
        recs = R._fallback_todays_matches("championship", {"country": "England", "name": "Championship"},
                                          "2026-09-07", season_id=5)
    assert len(recs) == 1 and recs[0]["id"] == "championship-todays-77"
    odds = recs[0]["odds"]
    assert odds["under15"] == 6.12 and odds["cornersUnder115"] == 1.36 and odds["dc_1x"] == 1.25
    assert odds == odds_do_row(_LINHA)
    # e a ancora fecha por par nas duas familias que estavam em digito unico
    from backend.services.prediction_ledger import prob_mercado_do_pick
    assert prob_mercado_do_pick("Over/Under", "Under 1.5", odds)["mercado_metodo"] == "devig"
    assert prob_mercado_do_pick("Corners", "Corners Under 11.5", odds)["mercado_metodo"] == "devig"
