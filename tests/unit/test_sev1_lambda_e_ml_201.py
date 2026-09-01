"""#201 — os dois Sev 1 do laudo de QA.

1. LAMBDA: dupla contagem de mando. `goals_scored_avg_home` (só jogos em casa)
   e `goals_conceded_avg_away` (só jogos fora) eram normalizados contra
   `average_goals_per_match / 2` (média GERAL). Numerador com vantagem de mando,
   denominador sem — mando contado duas vezes.

   Documentação do League Season Stats confirma o baseline correto:
       seasonAVG_home  "Média de gols marcados por mandantes"
       seasonAVG_away  "Média de gols marcados por visitantes"

2. ML SERVING SKEW: as features `*_avg_r5` eram preenchidas com lambdaHome/
   lambdaAway em vez da média empírica dos últimos jogos usada no treino, e
   colapsavam em dois números repetidos — zerando as interações aprendidas.
"""
import inspect

import pytest

from backend.modeling.lambda_calculator import calcular_lambda_dinamico, _num


LIGA = {
    "average_goals_per_match": 2.65,          # 1.50 + 1.15
    "avg_goals_scored_by_home_teams": 1.50,   # seasonAVG_home
    "avg_goals_scored_by_away_teams": 1.15,   # seasonAVG_away
}
LIGA_SEM_SPLIT = {"average_goals_per_match": 2.65}


def _medio_casa():
    return {"goals_scored_avg_home": 1.50, "goals_scored_avg_overall": 1.325, "games_played_home": 10}


def _medio_fora():
    return {"goals_scored_avg_away": 1.15, "goals_conceded_avg_away": 1.50,
            "goals_scored_avg_overall": 1.325, "games_played_away": 10}


# ── 1. lambda ────────────────────────────────────────────────────────

def test_time_medio_em_casa_recebe_o_baseline_de_casa():
    """Dois times médios: λ casa tem de ser seasonAVG_home, não 1.698."""
    lam = calcular_lambda_dinamico(_medio_casa(), _medio_fora(), LIGA, "NORMAL", is_home=True)
    assert lam == pytest.approx(1.50, abs=0.02), f"esperado ~1.50, veio {lam}"


def test_time_medio_fora_recebe_o_baseline_de_fora():
    visitante = {"goals_scored_avg_away": 1.15, "goals_scored_avg_overall": 1.325, "games_played_away": 10}
    mandante = {"goals_conceded_avg_home": 1.15, "goals_scored_avg_overall": 1.325, "games_played_home": 10}
    lam = calcular_lambda_dinamico(visitante, mandante, LIGA, "NORMAL", is_home=False)
    assert lam == pytest.approx(1.15, abs=0.02), f"esperado ~1.15, veio {lam}"


def test_razao_casa_fora_deixa_de_ser_quadratica():
    """A assinatura do bug: razão 1.70 (= 1.30²) em vez de 1.30."""
    lh = calcular_lambda_dinamico(_medio_casa(), _medio_fora(), LIGA, "NORMAL", is_home=True)
    visitante = {"goals_scored_avg_away": 1.15, "goals_scored_avg_overall": 1.325, "games_played_away": 10}
    mandante = {"goals_conceded_avg_home": 1.15, "goals_scored_avg_overall": 1.325, "games_played_home": 10}
    la = calcular_lambda_dinamico(visitante, mandante, LIGA, "NORMAL", is_home=False)
    assert lh / la == pytest.approx(1.30, abs=0.05), f"razão {lh/la:.2f} — 1.70 seria o bug"


def test_sem_seasonAVG_cai_no_comportamento_anterior_sem_inventar_split():
    """Liga sem o campo: fallback é o baseline geral, não um split chutado."""
    lam = calcular_lambda_dinamico(_medio_casa(), _medio_fora(), LIGA_SEM_SPLIT, "NORMAL", is_home=True)
    assert lam == pytest.approx(1.698, abs=0.03), "sem o campo, mantém o comportamento antigo"


def test_baseline_absurdo_e_ignorado():
    liga_ruim = dict(LIGA, avg_goals_scored_by_home_teams=9.9, avg_goals_scored_by_away_teams=0.01)
    lam = calcular_lambda_dinamico(_medio_casa(), _medio_fora(), liga_ruim, "NORMAL", is_home=True)
    assert lam < 3.0, "baseline fora da faixa plausível não pode passar"


# ── 1b. chave presente com None (padrão #078v) ───────────────────────

def test_chave_com_none_nao_derruba():
    """FootyStats devolve a chave com null para time sem jogo no recorte.

    `.get(k, default)` não usa o default nesse caso — antes levantava TypeError
    em `if gols_temp <= 0`.
    """
    time = {"goals_scored_avg_home": None, "goals_scored_avg_overall": None,
            "goals_scored_avg_last_5": None, "games_played_home": None}
    lam = calcular_lambda_dinamico(time, _medio_fora(), LIGA, "NORMAL", is_home=True)
    assert lam == pytest.approx(1.50, abs=0.05)


@pytest.mark.parametrize("v,esperado", [(None, None), ("", None), ("abc", None),
                                        (float("nan"), None), (0, None), ("1.5", 1.5), (2, 2.0)])
def test_num_normaliza(v, esperado):
    got = _num(v)
    if esperado is None:
        assert got is None or got == 0.0
    else:
        assert got == esperado


def test_regressao_usa_jogos_do_recorte():
    """2 jogos em casa (10 no total) tem de regredir para a média da liga."""
    src = inspect.getsource(calcular_lambda_dinamico)
    assert "games_played_home" in src and "games_played_away" in src
    time = {"goals_scored_avg_home": 3.0, "goals_scored_avg_overall": 1.5,
            "games_played": 10, "games_played_home": 2}
    lam = calcular_lambda_dinamico(time, _medio_fora(), LIGA, "NORMAL", is_home=True)
    sem_regressao = 3.0
    assert lam < sem_regressao * 0.85, f"λ={lam} — deveria estar regredido"


# ── 2. ML serving skew ───────────────────────────────────────────────

def _fx_src():
    import backend.services.fixtures_service as fx
    return inspect.getsource(fx)


def test_serving_nao_espelha_mais_o_poisson():
    src = _fx_src()
    for proibido in (
        '"home_goals_conceded_avg_r5": record["stats"].get("lambdaAway"',
        '"away_goals_conceded_avg_r5": record["stats"].get("lambdaHome"',
    ):
        assert proibido not in src, f"ainda espelha o Poisson: {proibido}"


def test_serving_usa_a_serie_empirica():
    src = _fx_src()
    assert '"home_goals_scored_avg_r5": float(_h_sc)' in src
    assert '"home_goals_conceded_avg_r5": float(_h_cd)' in src


def test_ml_e_pulado_sem_serie_real():
    """Sem r5 real o ensemble nao roda — cai no Poisson, que ja e o fallback."""
    src = _fx_src()
    assert "_r5_ok and is_ml_available(league_id)" in src


def test_lastx_coleta_a_serie_de_sofridos():
    src = _fx_src()
    assert "conceded_list.append(away_g)" in src
    assert "conceded_list.append(home_g)" in src
    assert '"goals_against_last5"' in src
