# -*- coding: utf-8 -*-
"""#230-g - o par de escanteios estava no payload; o mapper jogava fora.

A FootyStats manda over E under de 7.5 a 11.5 (99% de 605 finalizadas, #226-c).
O record publicava quatro overs. Sem under nao ha par; sem par nao ha de-vig;
a ancora de escanteios ficava em 8 de 357 linhas. Eu cheguei a escrever que
seria preciso "outra fonte" — nao era. Este teste monta um record de verdade
(mesmo caminho do contrato #223) a partir de uma linha com a escada inteira.
"""
import time

import pandas as pd

from backend.services.fixtures_service import build_records_from_matches
from backend.services import prediction_ledger as L


def _record(linha_extra):
    ts = int(time.time()) + 3600
    liga = {"average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
            "average_cards_per_match": 4.9, "average_fouls_per_match": 22.0,
            "average_shots_per_match": 24.0, "matches_completed": 25}
    return build_records_from_matches(
        league_id="championship",
        matches=pd.DataFrame([{"timestamp": ts}]), teams=None,
        league_df=pd.DataFrame([liga]),
        _rows_override=[{
            "id": 1, "home_team_name": "Casa FC", "away_team_name": "Fora FC",
            "date_unix": ts, "timestamp": ts, "status": "incomplete", **linha_extra,
        }],
        date_filter="today",
    )[0]


_ESCADA = {"odds_corners_over_75": 1.24, "odds_corners_under_75": 3.55,
           "odds_corners_over_85": 1.42, "odds_corners_under_85": 2.60,
           "odds_corners_over_95": 1.77, "odds_corners_under_95": 1.95,
           "odds_corners_over_105": 2.07, "odds_corners_under_105": 1.65,
           "odds_corners_over_115": 2.63, "odds_corners_under_115": 1.41}


def test_record_publica_a_escada_inteira_de_escanteios():
    odds = _record(_ESCADA)["odds"]
    for linha in ("75", "85", "95", "105", "115"):
        assert odds.get(f"cornersOver{linha}"), linha
        assert odds.get(f"cornersUnder{linha}"), linha
    assert odds["cornersUnder95"] == 1.95 and odds["cornersOver75"] == 1.24


def test_com_o_par_a_ancora_de_escanteios_vira_devig():
    odds = _record(_ESCADA)["odds"]
    r = L.prob_mercado_do_pick("Corners", "Corners Over 9.5", odds)
    assert r["mercado_metodo"] == "devig"
    assert r["odd_par"] == 1.95
    assert r["prob_mercado"] < 1 / 1.77            # margem retirada
    r_u = L.prob_mercado_do_pick("Corners", "Corners Under 9.5", odds)
    assert r_u["mercado_metodo"] == "devig"
    assert r["prob_mercado"] + r_u["prob_mercado"] == pytest_approx_one()


def pytest_approx_one():
    import pytest
    return pytest.approx(1.0, abs=5e-6)


def test_sem_under_no_payload_continua_implicita_nao_inventa():
    so_over = {k: v for k, v in _ESCADA.items() if "over" in k}
    odds = _record(so_over)["odds"]
    assert odds.get("cornersUnder95") is None
    assert L.prob_mercado_do_pick("Corners", "Corners Over 9.5", odds)["mercado_metodo"] == "implicita"


# ── #230-h: gols, 1X2 e DC com os nomes reais da FootyStats ─────────────
_GOLS_1X2_DC = {
    "odds_ft_1": 1.95, "odds_ft_x": 3.60, "odds_ft_2": 3.70,
    "odds_ft_over05": 1.03, "odds_ft_under05": 9.50,
    "odds_ft_over15": 1.22, "odds_ft_under15": 3.54,
    "odds_ft_over25": 1.80, "odds_ft_under25": 1.90,
    "odds_ft_over35": 2.99, "odds_ft_under35": 1.30,
    "odds_ft_over45": 5.85, "odds_ft_under45": 1.10,
    "odds_doublechance_1x": 1.25, "odds_doublechance_12": 1.28, "odds_doublechance_x2": 1.83,
}


def test_record_publica_1x2_pelos_nomes_reais():
    """odds_ft_home_team_win nao existe; a rota #225-a mediu 0% por isso."""
    odds = _record(_GOLS_1X2_DC)["odds"]
    assert (odds["home"], odds["draw"], odds["away"]) == (1.95, 3.60, 3.70)


def test_record_publica_a_escada_inteira_de_gols_e_a_dc():
    odds = _record(_GOLS_1X2_DC)["odds"]
    for k, v in (("over05", 1.03), ("under05", 9.50), ("under15", 3.54),
                 ("under35", 1.30), ("under45", 1.10),
                 ("dc_1x", 1.25), ("dc_12", 1.28), ("dc_x2", 1.83)):
        assert odds.get(k) == v, k


def test_com_os_pares_toda_linha_de_gols_vira_devig_e_1x2_vira_devig3():
    odds = _record(_GOLS_1X2_DC)["odds"]
    for linha in ("0.5", "1.5", "2.5", "3.5", "4.5"):
        r = L.prob_mercado_do_pick("Over/Under", f"Under {linha}", odds)
        assert r["mercado_metodo"] == "devig", linha
    assert L.prob_mercado_do_pick("1X2", "Draw", odds)["mercado_metodo"] == "devig3"
    assert L.prob_mercado_do_pick("Double Chance", "DC X2", odds)["mercado_metodo"] == "devig3"
