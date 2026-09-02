"""#220 - a inclinacao de calibracao recupera o que deve recuperar."""
import math
import random
import pytest

from backend.services.calibracao_slope import (
    ajustar_logistica, inclinacao, inclinacao_com_ic, benjamini_hochberg,
    por_celula, veredito, _logit, MIN_N,
)


def _amostra(f_outcome, n=600, semente=7, liga="L", mercado="M", lo=.15, hi=.90):
    rng = random.Random(semente)
    return [
        {"prob": (p := rng.uniform(lo, hi)),
         "outcome": 1 if rng.random() < f_outcome(p) else 0,
         "match_id": f"m{i // 3}", "league_id": liga, "market": mercado}
        for i in range(n)
    ]


# ── recuperacao ─────────────────────────────────────────────────────────
def test_modelo_bem_calibrado_da_inclinacao_perto_de_1():
    r = inclinacao_com_ic(_amostra(lambda p: p), reamostras=300)
    assert r["inclinacao"] == pytest.approx(1.0, abs=0.25)
    assert r["ic95"][0] <= 1.0 <= r["ic95"][1]
    assert r["difere_de_1"] is False


def test_modelo_sem_resolucao_da_inclinacao_perto_de_0():
    """Realidade constante: a previsao varia, o desfecho nao."""
    r = inclinacao_com_ic(_amostra(lambda p: 0.72, lo=.5), reamostras=300)
    assert abs(r["inclinacao"]) < 0.35
    assert r["difere_de_0"] is False       # nao da para afirmar que ha resolucao
    assert "SEM RESOLUCAO" in veredito(r)


def test_modelo_invertido_da_inclinacao_negativa():
    """O caso da rodada: INFO 82%, VALOR DETECTADO 33%."""
    r = inclinacao_com_ic(_amostra(lambda p: 1.0 - p), reamostras=300)
    assert r["inclinacao"] < 0
    assert "INVERTIDA" in veredito(r) or "SEM RESOLUCAO" in veredito(r)


def test_previsoes_extremas_demais():
    """Previsao varia muito mais que a realidade -> 0 < b < 1."""
    r = inclinacao_com_ic(_amostra(lambda p: 0.5 + 0.25 * (p - 0.5)), reamostras=300)
    assert 0.0 < r["inclinacao"] < 0.85


# ── bootstrap por bloco ─────────────────────────────────────────────────
def test_bootstrap_agrupa_por_jogo():
    picks = _amostra(lambda p: p, n=300)
    r = inclinacao_com_ic(picks, reamostras=200)
    assert r["jogos"] == 100          # 300 picks / 3 por jogo
    assert r["n"] == 300


def test_ic_por_bloco_e_mais_largo_que_por_pick():
    """Se reamostrar pick a pick, o IC estreita artificialmente."""
    picks = _amostra(lambda p: p, n=300)
    bloco = inclinacao_com_ic(picks, reamostras=400)
    soltos = [{**p, "match_id": f"solto{i}"} for i, p in enumerate(picks)]
    ind = inclinacao_com_ic(soltos, reamostras=400)
    larg_bloco = bloco["ic95"][1] - bloco["ic95"][0]
    larg_ind = ind["ic95"][1] - ind["ic95"][0]
    assert larg_bloco > larg_ind


# ── Benjamini-Hochberg ──────────────────────────────────────────────────
def test_bh_rejeita_os_pequenos_e_segura_o_resto():
    assert benjamini_hochberg([0.001, 0.02, 0.04, 0.30, 0.90]) == [True, True, False, False, False]


def test_bh_com_tudo_alto_nao_rejeita_nada():
    assert benjamini_hochberg([0.4, 0.5, 0.9]) == [False, False, False]


def test_bh_vazio():
    assert benjamini_hochberg([]) == []


# ── bordas ──────────────────────────────────────────────────────────────
def test_desfecho_constante_nao_tem_inclinacao():
    assert inclinacao([{"prob": 0.6, "outcome": 1, "match_id": "a"}] * 40) is None
    assert inclinacao([{"prob": 0.6, "outcome": 0, "match_id": "a"}] * 40) is None


def test_amostra_minuscula_e_marcada():
    r = inclinacao(_amostra(lambda p: p, n=12))
    assert r is None or r["abaixo_de_min_n"] is True


def test_logit_nao_explode_nas_bordas():
    assert math.isfinite(_logit(0.0)) and math.isfinite(_logit(1.0))


def test_separacao_completa_devolve_none_em_vez_de_numero_gigante():
    """Todo p=1 acerta e todo p=0 erra: a MV nao existe, a inclinacao diverge.

    Devolver um numero enorme seria pior que devolver nada — quem lesse o
    relatorio concluiria que o modelo tem resolucao altissima quando o que
    houve foi amostra degenerada.
    """
    picks = [{"prob": 0.0, "outcome": 0, "match_id": f"m{i}"} for i in range(20)]
    picks += [{"prob": 1.0, "outcome": 1, "match_id": f"n{i}"} for i in range(20)]
    assert inclinacao(picks) is None


def test_bordas_com_sobreposicao_funcionam():
    picks = [{"prob": 0.02, "outcome": i % 5 == 0, "match_id": f"m{i}"} for i in range(40)]
    picks += [{"prob": 0.98, "outcome": i % 5 != 0, "match_id": f"n{i}"} for i in range(40)]
    r = inclinacao(picks)
    assert r is not None and r["inclinacao"] > 0


def test_entrada_vazia():
    assert inclinacao([]) is None
    assert inclinacao_com_ic([]) is None
    assert ajustar_logistica([], []) is None


# ── por celula ──────────────────────────────────────────────────────────
def test_por_celula_separa_liga_e_mercado_e_ordena():
    picks = (_amostra(lambda p: p, n=300, liga="championship", mercado="Cards")
             + _amostra(lambda p: 0.7, n=300, semente=9, liga="serie-b",
                        mercado="Corners", lo=.5))
    linhas = por_celula(picks, reamostras=150)
    assert len(linhas) == 2
    assert linhas[0]["inclinacao"] <= linhas[1]["inclinacao"]
    assert {(l["liga"], l["mercado"]) for l in linhas} == {
        ("championship", "Cards"), ("serie-b", "Corners")}
