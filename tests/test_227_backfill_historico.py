# -*- coding: utf-8 -*-
"""#227 - reconstrucao de picks historicos, com escanteios no escopo.

O que estes testes protegem, em ordem de importancia:

1. **Vazamento temporal.** A probabilidade da partida N nao pode depender do
   que aconteceu na partida N. E a unica forma de o instrumento mentir para
   melhor, e mentira para melhor nao aparece como erro.
2. **O instrumento discrimina.** Controle positivo (gols dirigidos por forca de
   time) tem de dar inclinacao longe de zero; controle negativo (gols
   sorteados) tem de encostar em zero. Sem isso, "SEM RESOLUCAO em tudo" seria
   indistinguivel de um backfill quebrado — e um instrumento que so sabe dizer
   uma coisa nao esta medindo nada.
3. **Ausencia nao vira zero** na leitura da linha crua (#201/#208/#217/#225-b).
"""
import importlib.util
import pathlib

import pytest

from backend.services.backfill_historico import (
    RastreadorHistorico, estado_da_liga, extrair_partida, reconstruir,
)

_RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _gerador():
    caminho = _RAIZ / "scripts" / "backfill_historico.py"
    spec = importlib.util.spec_from_file_location("_bf", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.partidas_sinteticas


def _linha(i, casa, fora, gc=1, gf=1, **extra):
    d = {
        "id": i, "status": "complete", "date_unix": 1_700_000_000 + i * 86_400,
        "homeTeam": casa, "awayTeam": fora,
        "homeGoalCount": gc, "awayGoalCount": gf,
        "team_a_corners": 6, "team_b_corners": 4, "totalCornerCount": 10,
        "team_a_yellow_cards": 2, "team_b_yellow_cards": 2,
        "team_a_shots": 12, "team_b_shots": 10,
        "team_a_possession": 52, "team_b_possession": 48,
        "team_a_xg": 1.4, "team_b_xg": 1.1,
    }
    d.update(extra)
    return d


# ── 1. vazamento temporal ────────────────────────────────────────────────
def test_o_desfecho_da_partida_nao_entra_na_propria_previsao():
    """Mesma historia, ultimo jogo com placar diferente: prob TEM de ser igual.

    Se o rastreador registrasse a partida antes de montar o estado, o placar
    dela entraria na media e a previsao "acertaria" sozinha.
    """
    base = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}", gc=1, gf=1) for i in range(40)]
    a = base + [_linha(99, "T0", "T1", gc=0, gf=0)]
    b = base + [_linha(99, "T0", "T1", gc=5, gf=4)]

    pa = {p["market"]: p["prob"] for p in reconstruir(a, "x")["picks"] if p["match_id"] == 99}
    pb = {p["market"]: p["prob"] for p in reconstruir(b, "x")["picks"] if p["match_id"] == 99}

    assert pa and pa.keys() == pb.keys()
    assert pa == pb, "o placar da propria partida vazou para a previsao dela"


def test_o_desfecho_muda_o_outcome_e_so_ele():
    a = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}") for i in range(40)]
    a += [_linha(99, "T0", "T1", gc=0, gf=0)]
    b = a[:-1] + [_linha(99, "T0", "T1", gc=5, gf=4)]
    da = {p["market"]: p["outcome"] for p in reconstruir(a, "x")["picks"] if p["match_id"] == 99}
    db = {p["market"]: p["outcome"] for p in reconstruir(b, "x")["picks"] if p["match_id"] == 99}
    assert da["Over 2.5 gols"] == 0 and db["Over 2.5 gols"] == 1
    assert da["BTTS Yes"] == 0 and db["BTTS Yes"] == 1


def test_min_jogos_e_respeitado():
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}") for i in range(40)]
    r = reconstruir(linhas, "x", min_jogos=10)
    usados = {p["match_id"] for p in r["picks"]}
    assert usados and min(usados) >= 18, "pick com historico abaixo do minimo"
    assert r["resumo"]["puladas_por_amostra"] > 0


# ── 2. o instrumento discrimina ──────────────────────────────────────────
@pytest.mark.parametrize("com_sinal, espera_resolucao", [(True, True), (False, False)])
def test_controle_positivo_e_negativo(com_sinal, espera_resolucao):
    from backend.services.calibracao_slope import inclinacao_com_ic

    partidas = _gerador()(500, com_sinal=com_sinal, semente=227)
    picks = [p for p in reconstruir(partidas, "sintetica", familias=["gols"])["picks"]
             if p["market"] == "Over 2.5 gols"]
    assert len(picks) > 200

    r = inclinacao_com_ic(picks, reamostras=120)
    ic_baixo, ic_alto = r["ic95"]
    if espera_resolucao:
        assert ic_baixo > 0.15, (
            f"gols dirigidos por forca de time deveriam mostrar resolucao, "
            f"deu incl={r['inclinacao']:.3f} IC=[{ic_baixo:.2f}, {ic_alto:.2f}]"
        )
    else:
        assert ic_baixo <= 0 <= ic_alto, (
            f"gols sorteados nao tem resolucao para achar, mas o IC excluiu "
            f"zero: incl={r['inclinacao']:.3f} IC=[{ic_baixo:.2f}, {ic_alto:.2f}] "
            f"— o backfill esta inventando sinal"
        )


# ── 3. leitura da linha crua ─────────────────────────────────────────────
def test_menos_um_e_ausencia_e_zero_e_resultado():
    p = extrair_partida(_linha(1, "A", "B", gc=0, gf=0,
                               team_a_corners=-1, team_b_corners=-1,
                               totalCornerCount=-1, team_a_yellow_cards=0,
                               team_b_yellow_cards=0))
    assert p["gols_casa"] == 0.0 and p["gols_fora"] == 0.0     # 0 e resultado
    assert p["escanteios_total"] is None                        # -1 e ausencia
    assert p["cartoes_total"] == 0.0                            # 0 cartoes tambem


def test_total_de_escanteios_cai_para_a_soma_quando_o_direto_falta():
    p = extrair_partida(_linha(1, "A", "B", totalCornerCount=None))
    assert p["escanteios_total"] == 10.0


def test_sem_desfecho_de_escanteio_nao_gera_pick_de_escanteio():
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}",
                     totalCornerCount=None, team_a_corners=None, team_b_corners=None)
              for i in range(40)]
    r = reconstruir(linhas, "x")
    assert r["resumo"]["por_familia"]["escanteios"] == 0
    assert r["resumo"]["por_familia"]["gols"] > 0, "gols nao dependem de escanteio"


def test_partida_nao_finalizada_e_ignorada():
    assert extrair_partida(_linha(1, "A", "B", status="incomplete")) is None


def test_sem_gols_nao_ha_partida():
    assert extrair_partida(_linha(1, "A", "B", homeGoalCount=None)) is None


# ── escanteios no escopo, com EV ─────────────────────────────────────────
def test_escanteios_recebem_prob_e_ev_quando_ha_odd():
    """O #226-b mediu contagem e odd de escanteios em 100%. Antes disso a
    familia estava fora do backfill por um nome errado, nao por falta de dado."""
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}", odds_corners_over_95=1.77)
              for i in range(40)]
    esc = [p for p in reconstruir(linhas, "x")["picks"]
           if p["market"] == "Escanteios Over 9.5"]
    assert esc
    p = esc[0]
    assert p["odd"] == 1.77
    assert p["ev"] == pytest.approx(p["prob"] * 1.77 - 1.0, abs=1e-6)
    assert p["outcome"] == 1                       # 10 escanteios > 9.5


def test_odd_invalida_nao_vira_ev():
    """Odd 1.0 ou 0 nao e preco — e campo vazio com outro disfarce (#225-a)."""
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}",
                     odds_ft_over25=1.0, odds_ft_over35=0) for i in range(40)]
    picks = {p["market"]: p for p in reconstruir(linhas, "x")["picks"]}
    assert picks["Over 2.5 gols"]["odd"] is None
    assert picks["Over 2.5 gols"]["ev"] is None
    assert picks["Over 3.5 gols"]["odd"] is None


# ── rastreador e liga ────────────────────────────────────────────────────
def test_media_de_zero_observacoes_e_none_nao_zero():
    """Media de nada nao e zero. Devolver 0 planta ausencia como informacao."""
    r = RastreadorHistorico()
    assert r.media("ninguem", "gols_pro") is None
    r.registrar(extrair_partida(_linha(1, "A", "B", gc=2, gf=0)))
    assert r.media("A", "gols_pro") == 2.0
    assert r.media("A", "gols_pro", em_casa=False) is None      # nunca jogou fora


def test_liga_vazia_nao_inventa_media():
    assert estado_da_liga([]) == {}


def test_formato_e_o_que_medir_inclinacao_consome():
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}") for i in range(40)]
    p = reconstruir(linhas, "championship")["picks"][0]
    for campo in ("prob", "outcome", "match_id", "league_id", "market"):
        assert campo in p, campo
    assert 0.0 <= p["prob"] <= 1.0
    assert p["outcome"] in (0, 1)
    assert p["league_id"] == "championship"


# ── #227-a: a probabilidade do mercado como referencia ───────────────────
def test_mercado_com_par_over_under_usa_devig():
    from backend.services.backfill_historico import prob_do_mercado

    p, metodo = prob_do_mercado(
        {"odds_ft_over25": 1.90, "odds_ft_under25": 1.90}, "odds_ft_over25")
    assert metodo == "devig"
    assert p == pytest.approx(0.5, abs=0.02), "par simetrico devigado da 50%"
    assert p < 1 / 1.90 + 1e-9, "de-vig tem de tirar margem, nao adicionar"


def test_mercado_so_com_a_perna_over_e_marcado_como_implicita():
    from backend.services.backfill_historico import prob_do_mercado

    p, metodo = prob_do_mercado({"odds_ft_over25": 2.00}, "odds_ft_over25")
    assert (p, metodo) == (0.5, "implicita")


def test_mercado_sem_preco_utilizavel():
    from backend.services.backfill_historico import prob_do_mercado

    assert prob_do_mercado({}, "odds_ft_over25") == (None, "sem_odd")
    assert prob_do_mercado({"odds_ft_over25": 1.0}, "odds_ft_over25") == (None, "sem_odd")


def test_a_casa_de_apostas_tem_resolucao_no_controle_positivo():
    """Referencia do instrumento: se nem o mercado marca resolucao, o problema
    nao esta no modelo.

    Com precos derivados do lambda que gerou o jogo, a inclinacao do mercado
    tem de ficar perto de 1. E isto tambem calibra o PODER do teste: mostra que
    n desta ordem detecta inclinacao 1 com folga, entao "zero" nos dados reais
    nao e falta de amostra para achar sinal forte.
    """
    from backend.services.calibracao_slope import inclinacao_com_ic

    partidas = _gerador()(500, com_sinal=True, semente=227)
    picks = [p for p in reconstruir(partidas, "sintetica", familias=["gols"])["picks"]
             if p["market"] == "Over 2.5 gols" and p["prob_mercado"] is not None]
    assert len(picks) > 200

    r = inclinacao_com_ic([{**p, "prob": p["prob_mercado"]} for p in picks],
                          reamostras=120)
    ic_baixo, ic_alto = r["ic95"]
    assert ic_baixo > 0.5, (
        f"preco derivado do lambda verdadeiro tem de mostrar resolucao clara, "
        f"deu incl={r['inclinacao']:.3f} IC=[{ic_baixo:.2f}, {ic_alto:.2f}]"
    )
