# -*- coding: utf-8 -*-
"""#213 - placar de jogo em andamento tem de ser observado, nao presumido.

Medido em 01/09/2026, as 20h20 UTC: o dashboard exibia 15 de 15 jogos de
Championship e League One como 0-0 aos 80 minutos, enquanto /live-scores
devolvia lista vazia.

Com a media de 2,5 gols do Championship, P(0-0 aos 80') = 10,8% por jogo.
Para 15 jogos, 1 em 300 trilhoes. Nao era resultado; era falta de dado.

Mecanismo: a linha de `league-matches` traz homeGoalCount=0 enquanto a partida
nao termina. O sistema promove o jogo a 'live' pelo relogio (o kickoff passou) e
le aquele 0 como placar. O guard que ja existia so cobria campo AUSENTE - com o
campo presente valendo 0, ele nao dispara.
"""
import time

import pandas as pd

import backend.services.auditor_premissas as ap
from backend.services.fixtures_service import build_records_from_matches


def _linha(status_bruto, gols_casa, gols_fora, minutos_atras=80):
    ts = int(time.time()) - minutos_atras * 60
    return {
        "id": 1, "home_team_name": "Casa FC", "away_team_name": "Fora FC",
        "date_unix": ts, "timestamp": ts,
        "status": status_bruto,
        "homeGoalCount": gols_casa, "awayGoalCount": gols_fora,
    }


def _monta(linha):
    # `matches` so e usado para descobrir a coluna de data; com _rows_override o
    # conteudo nao importa, mas o DataFrame precisa existir.
    return build_records_from_matches(
        league_id="championship",
        matches=pd.DataFrame([{"timestamp": linha["date_unix"]}]),
        teams=None,
        _rows_override=[linha],
        date_filter="today",
    )


def test_zero_a_zero_de_jogo_promovido_vira_nulo():
    """O caso real: status bruto 'incomplete', promovido a live pelo relogio."""
    recs = _monta(_linha("incomplete", 0, 0))
    assert recs, "o jogo tem de continuar aparecendo"
    assert recs[0]["status"] == "live"
    assert recs[0]["score"] is None, "0-0 presumido nao pode virar placar"


def test_placar_com_gol_e_preservado():
    """Se a linha traz gol, e informacao de verdade - nao se joga fora."""
    recs = _monta(_linha("incomplete", 2, 1))
    assert recs[0]["score"] == {"home": 2, "away": 1}


def test_zero_a_zero_de_jogo_que_a_api_diz_estar_ao_vivo_e_mantido():
    """Quando a FONTE diz 'live', o 0-0 dela e observacao. Nao mexemos."""
    recs = _monta(_linha("live", 0, 0))
    assert recs[0]["status"] == "live"
    assert recs[0]["score"] == {"home": 0, "away": 0}


def test_jogo_encerrado_com_zero_a_zero_e_mantido():
    """0-0 de jogo terminado e resultado legitimo."""
    recs = _monta(_linha("complete", 0, 0, minutos_atras=200))
    assert recs[0]["status"] == "finished"
    assert recs[0]["score"] == {"home": 0, "away": 0}


# ── a premissa que teria pego isso sozinha ───────────────────────────

def _jogo_vivo(casa, fora, minuto=80, gols=(0, 0)):
    return {
        "leagueId": "championship", "status": "live", "minute": minuto,
        "homeTeam": {"name": casa}, "awayTeam": {"name": fora},
        "score": {"home": gols[0], "away": gols[1]},
        "stats": {}, "mercados": [],
    }


def test_premissa_acusa_a_rodada_toda_zerada():
    rodada = [_jogo_vivo(f"C{i}", f"F{i}") for i in range(15)]
    rel = ap.auditar(rodada, premissas=[ap.premissa_placar_ao_vivo_e_observado])
    assert rel.violacoes and rel.violacoes[0].severidade == ap.SEV_CRITICO
    assert "15 jogos ao vivo" in rel.violacoes[0].jogo


def test_premissa_nao_acusa_quando_ha_gol():
    rodada = [_jogo_vivo(f"C{i}", f"F{i}") for i in range(14)] + [_jogo_vivo("X", "Y", gols=(1, 0))]
    rel = ap.auditar(rodada, premissas=[ap.premissa_placar_ao_vivo_e_observado])
    assert rel.violacoes == []


def test_premissa_ignora_o_inicio_do_jogo():
    """Aos 10 minutos, todo mundo 0-0 e o esperado."""
    rodada = [_jogo_vivo(f"C{i}", f"F{i}", minuto=10) for i in range(15)]
    rel = ap.auditar(rodada, premissas=[ap.premissa_placar_ao_vivo_e_observado])
    assert rel.violacoes == []


def test_premissa_ignora_amostra_pequena():
    rodada = [_jogo_vivo(f"C{i}", f"F{i}") for i in range(3)]
    rel = ap.auditar(rodada, premissas=[ap.premissa_placar_ao_vivo_e_observado])
    assert rel.violacoes == []


def test_premissa_esta_no_conjunto_padrao():
    assert ap.premissa_placar_ao_vivo_e_observado in ap.PREMISSAS
