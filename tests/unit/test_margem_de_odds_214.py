# -*- coding: utf-8 -*-
"""#214 - margem fora da faixa de mercado denuncia odd velha ou errada.

Medido em 01/09/2026, Londrina x Juventude. O card trazia:

    1X2 .............. 2,88 / 2,70 / 2,17   margem 17,8%
    Over/Under 2.5 ... 2,17 / 1,55          margem 10,6%
    BTTS ............. 1,90 / 1,80          margem  8,2%

A bet365 pagava 3,75 / 2,87 / 2,20 no mesmo momento - margem de 7,0%. Nao
existe casa seria operando a 17,8% no 1X2.

O que torna o diagnostico preciso: os outros mercados do MESMO payload estao em
faixa normal. Nao e a fonte inteira quebrada, e o 1X2 desatualizado.

E o efeito e o que importa: com a odd errada de 2,88, o EV do mandante pela
probabilidade do modelo (33,7%) dava -3,1%. Com a odd real de 3,75, +26,2%.
Mesma probabilidade, sinal invertido pela odd.
"""
import backend.services.auditor_premissas as ap


def jogo(odds, liga="brasileirao-serie-b"):
    return {"leagueId": liga, "homeTeam": {"name": "Londrina"},
            "awayTeam": {"name": "Juventude"}, "stats": {}, "mercados": [], "odds": odds}


def _viol(j):
    rel = ap.auditar([j], premissas=[ap.premissa_odds_com_margem_plausivel])
    return rel.violacoes


def test_calculo_da_margem():
    assert round(ap._margem([2.88, 2.70, 2.17]), 1) == 17.8
    assert round(ap._margem([3.75, 2.87, 2.20]), 1) == 7.0
    assert round(ap._margem([2.17, 1.55]), 1) == 10.6


def test_margem_ignora_odd_invalida():
    assert ap._margem([2.0, 1.0]) is None      # odd 1.00 nao existe
    assert ap._margem([2.0, None]) is None
    assert ap._margem([2.0, "x"]) is None


def test_acusa_o_caso_real():
    v = _viol(jogo({"home": 2.88, "draw": 2.70, "away": 2.17}))
    assert len(v) == 1
    assert v[0].severidade == ap.SEV_ALTO
    assert "17.8%" in v[0].observado
    assert "1X2" in v[0].detalhe


def test_nao_acusa_as_odds_reais_da_bet365():
    assert _viol(jogo({"home": 3.75, "draw": 2.87, "away": 2.20})) == []


def test_margem_negativa_ou_baixa_demais_e_critica():
    """Soma abaixo de 100% seria arbitragem garantida - odd corrompida."""
    v = _viol(jogo({"home": 4.0, "draw": 4.0, "away": 4.0}))   # margem -25%
    assert v and v[0].severidade == ap.SEV_CRITICO


def test_examina_cada_familia_separadamente():
    """O achado so foi preciso porque os outros mercados estavam saos."""
    v = _viol(jogo({
        "home": 2.88, "draw": 2.70, "away": 2.17,   # 17,8% -> acusa
        "over25": 2.17, "under25": 1.55,            # 10,6% -> passa
        "bttsYes": 1.90, "bttsNo": 1.80,            #  8,2% -> passa
    }))
    assert len(v) == 1 and "1X2" in v[0].detalhe


def test_familia_incompleta_e_ignorada():
    assert _viol(jogo({"home": 2.88, "draw": 2.70})) == []


def test_jogo_sem_odds_e_ignorado():
    assert _viol(jogo({})) == []


def test_premissa_esta_no_conjunto_padrao():
    assert ap.premissa_odds_com_margem_plausivel in ap.PREMISSAS
