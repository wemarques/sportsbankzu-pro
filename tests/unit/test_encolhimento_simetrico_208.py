# -*- coding: utf-8 -*-
"""#208 - encolhimento de amostra pequena nos DOIS lados da conta.

Ate aqui a regressao a media so agia abaixo de 5 jogos, com peso gp/5, e so no
ataque. A defesa do adversario entrava crua com um jogo ou com trinta.

Medido em producao em 01/09/2026, com a rodada inteira (17 jogos), comparando o
1X2 recalculado do lambda contra o 1X2 do card (que vem de odds_implied):

    Championship  (3 rodadas jogadas) .... modelo 14,0pp abaixo do mercado na casa
    League One    (3 rodadas jogadas) .... modelo 13,5pp abaixo do mercado na casa
    Brasileirao B (24 rodadas) ...........  -4,9pp
    Colombia      (25 rodadas) ...........  -0,7pp

Com amostra o modelo acompanha o mercado. Sem amostra ele pende para o
visitante. O limiar sobe para 8 jogos e passa a valer para ataque e defesa;
acima do limiar nada muda.
"""
import importlib
import backend.modeling.lambda_calculator as lc


def test_peso_zera_com_amostra_vazia():
    assert lc._peso_amostra(0) == 0.0


def test_contagem_ausente_nao_encolhe():
    """Ausencia de informacao nao e informacao de ausencia.

    A FootyStats nem sempre devolve games_played. Encolher para o baseline nesse
    caso apagaria o time inteiro - seria trocar um vies por um apagamento.
    """
    assert lc._peso_amostra(None) == 1.0
    assert lc._peso_amostra("") == 1.0


def test_peso_e_linear_ate_o_limiar():
    assert lc._peso_amostra(3) == 3 / 8
    assert lc._peso_amostra(4) == 4 / 8


def test_amostra_cheia_nao_encolhe():
    """Onde o modelo ja acompanha o mercado, nada muda."""
    for jogos in (8, 12, 24, 25, 38):
        assert lc._peso_amostra(jogos) == 1.0, jogos


def test_limiar_e_configuravel(monkeypatch):
    monkeypatch.setenv("LAMBDA_SHRINK_MIN_GAMES", "5")
    m = importlib.reload(lc)
    try:
        assert m.JOGOS_AMOSTRA_CHEIA == 5
        assert m._peso_amostra(5) == 1.0
    finally:
        monkeypatch.delenv("LAMBDA_SHRINK_MIN_GAMES", raising=False)
        importlib.reload(lc)


def test_recorte_usa_o_lado_certo():
    dados = {"games_played_home": 3, "games_played_away": 9, "games_played": 12}
    assert lc._jogos_do_recorte(dados, em_casa=True) == 3
    assert lc._jogos_do_recorte(dados, em_casa=False) == 9


def test_recorte_cai_para_o_total_quando_o_lado_falta():
    assert lc._jogos_do_recorte({"games_played": 11}, em_casa=True) == 11


def _times(gols_casa, sofridos_fora, jogos):
    """Mandante artilheiro contra visitante que 'nao sofre gol' em 3 jogos."""
    casa = {
        "goals_scored_avg_home": gols_casa, "goals_scored_avg_overall": gols_casa,
        "games_played_home": jogos, "games_played": jogos,
    }
    fora = {
        "goals_conceded_avg_away": sofridos_fora,
        "goals_conceded_avg_overall": sofridos_fora,
        "games_played_away": jogos, "games_played": jogos,
    }
    return casa, fora


def _liga():
    return {
        "average_goals_per_match": 2.60,
        "avg_goals_scored_by_home_teams": 1.45,
        "avg_goals_scored_by_away_teams": 1.15,
    }


def test_defesa_de_amostra_minima_deixa_de_inflar_o_lambda():
    """O caso que a rodada de 01/09 expos, no sentido do mandante.

    Visitante com 3 jogos e 0,20 gol sofrido fora e ruido, nao muralha. Sem o
    #208 esse numero entrava cru e derrubava a defesa relativa.
    """
    casa, fora = _times(gols_casa=1.60, sofridos_fora=0.20, jogos=3)
    lam_pouco = lc.calcular_lambda_dinamico(casa, fora, _liga(), regime="NORMAL", is_home=True)

    casa30, fora30 = _times(gols_casa=1.60, sofridos_fora=0.20, jogos=30)
    lam_muito = lc.calcular_lambda_dinamico(casa30, fora30, _liga(), regime="NORMAL", is_home=True)

    # com 3 jogos o lambda tem de ficar mais perto do baseline da liga (1,45)
    assert lam_pouco > lam_muito, (lam_pouco, lam_muito)
    assert abs(lam_pouco - 1.45) < abs(lam_muito - 1.45)


def test_amostra_cheia_nao_muda_o_resultado(monkeypatch):
    """Regressao: o regime que funciona hoje nao pode se mexer."""
    casa, fora = _times(gols_casa=1.60, sofridos_fora=1.10, jogos=24)
    com_208 = lc.calcular_lambda_dinamico(casa, fora, _liga(), regime="NORMAL", is_home=True)

    # neutraliza o encolhimento e confere que o valor e o mesmo
    monkeypatch.setattr(lc, "_peso_amostra", lambda _j: 1.0)
    sem_encolher = lc.calcular_lambda_dinamico(casa, fora, _liga(), regime="NORMAL", is_home=True)
    assert abs(com_208 - sem_encolher) < 1e-9


def test_lambda_continua_dentro_dos_limites():
    casa, fora = _times(gols_casa=4.0, sofridos_fora=0.05, jogos=1)
    lam = lc.calcular_lambda_dinamico(casa, fora, _liga(), regime="NORMAL", is_home=True)
    assert lc.LAMBDA_MIN <= lam <= lc.LAMBDA_MAX
