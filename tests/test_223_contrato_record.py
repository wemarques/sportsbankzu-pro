# -*- coding: utf-8 -*-
"""#223 - o contrato do record: ler uma chave nao prova que ela chega.

O defeito que este teste torna impossivel
-----------------------------------------
`dict.get("X")` devolve None em silencio. E isso que permite olhar o consumidor,
ver a chave sendo lida, e concluir que o dado chega — sem inspecionar quem o
escreve. Quatro casos em uma semana, nas duas direcoes:

    le sem que escrevam .... #221 (`league_stats`), #216 (4a coluna),
                             #218 (6 das 10 entradas do ledger vinham nulas)
    escreve sem que leiam ... #217 (`no_bet`), #189-f (odds de escanteios)

O #222 proibiu concluir sem prova, e proibicao e prosa. Este teste e a prova.

Medido no momento em que o contrato foi ligado
----------------------------------------------
    29 chaves lidas | 173 escritas | 9 bloqueios

Dos 9: tres eram falso positivo (nome legado lido so como fallback encadeado,
`match_data.get("awayTeam", match_data.get("away_team", ""))`) e o varredor
passou a reconhece-los. Os seis restantes eram todos do ledger do #218:

    homeMatchesPlayed/awayMatchesPlayed -> o nome real e matchesPlayed_home/_away
    leagueMatchesCompleted              -> vive em league_stats, nao em stats
    cardsLambda / expectedTotalCorners  -> nao existem em lugar nenhum
    dataAgeHours                        -> nao existe; lacuna real, deixada fora

Depois da correcao: 6 de 10 entradas nulas -> 2 de 14, e as duas restantes tem
a chave presente (ficam nulas so sem dados de time no cenario sintetico).
"""
import pytest

from backend.config import contrato_record as cr


def test_nenhuma_chave_lida_sem_produtor():
    """O teste que teria pego #216, #218 e #221 sozinho.

    Se falhar: um consumidor le uma chave que nenhum produtor escreve. Ou o
    produtor nao a publica, ou o nome esta errado. Nao 'conserte' declarando em
    OPCIONAIS sem antes verificar qual dos dois e — a lista existe para
    registrar decisao, nao para calar o teste.
    """
    bloqueia = cr.verificar()["bloqueia"]
    assert not bloqueia, "\n".join(bloqueia)


def test_o_contrato_esta_lendo_alguma_coisa():
    """Guarda contra o proprio gate morrer em silencio.

    Se a lista de consumidores quebrar (arquivo renomeado, regex furada), o
    contrato passaria a nao ler nada e o teste acima ficaria verde para sempre —
    exatamente a forma de defeito que ele existe para pegar.
    """
    r = cr.resumo()
    assert r["lidas"] >= 20, r
    assert r["escritas"] >= 100, r


def test_cenarios_de_referencia_montam_records_de_verdade():
    """Sem record real, o contrato compararia leitura contra uma fixture."""
    records = list(cr._cenarios())
    assert len(records) >= 3
    for rec in records:
        assert rec.get("stats"), "cenario sem stats nao serve de referencia"
        assert "league_stats" in rec


def test_fallback_encadeado_nao_conta_como_leitura_primaria():
    """`x.get("A", x.get("B"))`: cobrar B geraria falso positivo."""
    fb = cr.chaves_de_fallback()
    assert {"home_team", "away_team", "match_id"} <= fb


def test_opcional_precisa_de_motivo_escrito():
    for chave, motivo in cr.OPCIONAIS.items():
        assert motivo and len(motivo) > 15, f"{chave} declarada sem motivo util"


def test_avisos_nao_bloqueiam_mas_existem():
    """`avisa` sinaliza contrato desatualizado sem derrubar o build."""
    assert isinstance(cr.verificar()["avisa"], list)


# ── o defeito concreto que o contrato encontrou ─────────────────────────

def test_ledger_grava_as_entradas_que_prometeu():
    """#218 lia seis chaves que nao existiam. Este teste trava a correcao."""
    import time
    import pandas as pd
    from backend.services.fixtures_service import build_records_from_matches
    from backend.services.prediction_ledger import linhas_do_bundle
    from backend.models.market_output import MarketOutput, MatchMarketBundle

    ts = int(time.time()) + 3600
    rec = build_records_from_matches(
        league_id="championship",
        matches=pd.DataFrame([{"timestamp": ts}]), teams=None,
        league_df=pd.DataFrame([{
            "average_goals_per_match": 2.65, "average_corners_per_match": 10.2,
            "average_cards_per_match": 4.9, "average_fouls_per_match": 22.0,
            "average_shots_per_match": 24.0, "matches_completed": 25,
        }]),
        _rows_override=[{"id": 1, "home_team_name": "Casa FC",
                         "away_team_name": "Fora FC", "date_unix": ts,
                         "timestamp": ts, "status": "incomplete"}],
        date_filter="today",
    )[0]
    bundle = MatchMarketBundle(
        match_id="m1", home_team="Casa FC", away_team="Fora FC",
        league_id="championship", data_quality_score=0.6,
        markets=[MarketOutput(market_type="Corners", selection="Corners Over 9.5",
                              raw_probability=0.8, calibrated_probability=0.7)],
    )
    e = linhas_do_bundle(bundle, rec, rec["stats"])[0]["inputs"]
    # os lambdas e a contagem da liga TEM de vir preenchidos
    assert e["lambda_home"] and e["lambda_away"] and e["lambda_total"]
    assert e["league_matches_completed"] == 25
    assert e["cards_league_avg"] == 4.9 and e["corners_league_avg"] == 10.2
    # e as chaves que nao existiam nao voltam com nome de medida
    assert "cards_lambda" not in e and "data_age_hours" not in e
