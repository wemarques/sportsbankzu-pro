# -*- coding: utf-8 -*-
"""#215 - a contagem empirica como terceira opiniao sobre o calibrador.

A pergunta aberta desde o #200: os .pkl treinados sobre o audit_results vazado
ajudam ou atrapalham? Era opiniao. A FootyStats entrega a distribuicao empirica
por linha - quantos por cento dos jogos daqueles dois times passaram de cada
linha. Isso e contagem, nao modelo.

O caso que motivou (Londrina x Juventude, 01/09/2026, cartoes):

    linha        empirico   crua    calibrada
    Over 2.5       82%      74,7%     59,9%     calibrador AFASTOU 22pp
    Under 4.5      54%      60,9%     52-54%    calibrador aproximou

E o defeito de entrada que o mesmo jogo expos: a FootyStats publica Londrina
2,45 e Juventude 2,27; o sistema calculava 2,46 e 1,88. O Londrina bateu por
acaso - o fallback historico media so os jogos de UM lado, e o Londrina em casa
faz quase o que faz no geral. O Juventude nao.
"""
import backend.services.comparador_ancora as ca


def jogo(mercados, stats=None, casa="Londrina", fora="Juventude"):
    return {"leagueId": "brasileirao-serie-b", "homeTeam": {"name": casa},
            "awayTeam": {"name": fora}, "stats": stats or {}, "mercados": mercados}


def mercado(nome, crua, calib):
    return {"mercado": nome, "raw_probability": crua, "calibrated_probability": calib}


# ── leitura do nome do mercado ───────────────────────────────────────

def test_reconhece_a_linha_do_mercado():
    assert ca._linha_do_mercado("Escanteios Over 8.5") == ("corners", "over", 8.5)
    assert ca._linha_do_mercado("Cartoes Under 4.5") == ("cards", "under", 4.5)
    assert ca._linha_do_mercado("Cartões Over 2.5") == ("cards", "over", 2.5)


def test_ignora_mercado_sem_ancora_possivel():
    assert ca._linha_do_mercado("Over 2.5 gols") is None
    assert ca._linha_do_mercado("BTTS — SIM") is None


def test_monta_a_chave_da_ancora():
    st = {"over25_cards_percentage": 82, "over85_corners_percentage": 92}
    assert ca._ancora(st, "cards", 2.5) == 82
    assert ca._ancora(st, "corners", 8.5) == 92
    assert ca._ancora(st, "cards", 3.5) is None


# ── o caso real ──────────────────────────────────────────────────────

def test_reproduz_o_caso_de_01_09():
    j = jogo(
        [mercado("Cartoes Over 2.5", 0.747, 0.599),
         mercado("Cartoes Under 4.5", 0.609, 0.530)],
        {"over25_cards_percentage": 82, "over45_cards_percentage": 46},
    )
    c = ca.comparar([j])
    assert len(c.linhas) == 2
    over, under = c.linhas
    assert round(over.erro_cru) == -7          # 74,7 contra 82
    assert round(over.erro_calibrado) == -22   # 59,9 contra 82  <- afastou
    # Under 4.5: a ancora e o complemento do Over 4.5
    assert under.empirico == 54
    assert abs(under.erro_calibrado) < abs(under.erro_cru)   # aqui aproximou


def test_under_usa_o_complemento_da_ancora():
    j = jogo([mercado("Cartoes Under 4.5", 0.60, 0.53)], {"over45_cards_percentage": 46})
    assert ca.comparar([j]).linhas[0].empirico == 54


def test_veredito_quando_o_calibrador_afasta():
    j = jogo([mercado("Cartoes Over 2.5", 0.80, 0.55)], {"over25_cards_percentage": 82})
    assert "AFASTA" in ca.comparar([j]).veredito()


def test_veredito_quando_o_calibrador_aproxima():
    j = jogo([mercado("Cartoes Over 2.5", 0.95, 0.83)], {"over25_cards_percentage": 82})
    assert "APROXIMA" in ca.comparar([j]).veredito()


def test_conta_mercados_sem_ancora():
    j = jogo([mercado("Cartoes Over 9.5", 0.5, 0.5)], {"over25_cards_percentage": 82})
    c = ca.comparar([j])
    assert c.linhas == [] and c.sem_ancora == 1


def test_resumo_agrega_vies_e_erro_absoluto():
    js = [jogo([mercado("Cartoes Over 2.5", 0.80, 0.60)], {"over25_cards_percentage": 82}, casa=f"C{i}")
          for i in range(4)]
    r = ca.comparar(js).resumo()
    assert r["linhas"] == 4
    assert r["crua"]["vies_medio"] == -2.0
    assert r["calibrada"]["vies_medio"] == -22.0
    assert r["calibrada"]["erro_absoluto_medio"] == 22.0


def test_amostra_vazia_nao_da_veredito():
    assert "insuficiente" in ca.comparar([]).veredito()


def test_mercado_sem_probabilidade_nao_quebra():
    j = jogo([{"mercado": "Cartoes Over 2.5"}], {"over25_cards_percentage": 82})
    l = ca.comparar([j]).linhas[0]
    assert l.crua is None and l.erro_cru is None
