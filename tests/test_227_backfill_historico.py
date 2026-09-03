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


# ── #227-b: inconclusivo nao e o mesmo que sem resolucao ─────────────────
def test_veredito_separa_falta_de_precisao_de_falta_de_resolucao():
    """O caso real: mercado com inclinacao 0.983 e IC [-0.06, 2.23].

    O IC cobre 0, mas cobre 1 tambem — o ponto esta em cima de 1. Chamar isso
    de "SEM RESOLUCAO" leu imprecisao como cegueira, e quase fez a casa de
    apostas passar por previsor que nao separa nada.
    """
    from backend.services.calibracao_slope import veredito

    mercado = {"inclinacao": 0.983, "n": 523, "abaixo_de_min_n": False,
               "ic95": [-0.06, 2.23], "difere_de_0": False, "difere_de_1": False}
    assert "INCONCLUSIVO" in veredito(mercado)

    # modelo: IC cobre 0 e EXCLUI 1 -> ai sim e evidencia contra resolucao
    modelo = {"inclinacao": -0.065, "n": 523, "abaixo_de_min_n": False,
              "ic95": [-0.39, 0.25], "difere_de_0": False, "difere_de_1": True}
    assert "SEM RESOLUCAO" in veredito(modelo)


# ── #227-b: modelo contra mercado, sem depender de variancia ─────────────
def _comparador():
    caminho = _RAIZ / "scripts" / "comparar_com_mercado.py"
    spec = importlib.util.spec_from_file_location("_cmp", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_brier_e_logloss_em_valores_conhecidos():
    cmp = _comparador()
    picks = [{"prob": 1.0, "outcome": 1}, {"prob": 0.0, "outcome": 0}]
    assert cmp._brier(picks, "prob") == 0.0
    assert cmp._logloss(picks, "prob") == pytest.approx(1.4e-5, abs=1e-4)

    meio = [{"prob": 0.5, "outcome": 1}, {"prob": 0.5, "outcome": 0}]
    assert cmp._brier(meio, "prob") == 0.25
    assert cmp._logloss(meio, "prob") == pytest.approx(0.6931, abs=1e-3)


def test_diferenca_emparelhada_acha_quem_tem_informacao():
    """No sintetico, o preco de GOLS sai do lambda verdadeiro e o de ESCANTEIOS
    e sorteado. A comparacao tem de apontar mercado nos gols e modelo nos
    escanteios — se apontar o mesmo lado nos dois, nao esta medindo nada.
    """
    cmp = _comparador()
    partidas = _gerador()(400, com_sinal=True, semente=227)
    todos = reconstruir(partidas, "sintetica")["picks"]
    picks = [{**p, "prob_modelo": p["prob"], "prob": p["prob_mercado"]}
             for p in todos if p["prob_mercado"] is not None]

    def dif(mercado):
        grupo = [p for p in picks if p["market"] == mercado]
        assert len(grupo) > 100, mercado
        return cmp._ic_da_diferenca(grupo, cmp._brier, reamostras=150)

    d_gols, lo_gols, _ = dif("Over 2.5 gols")
    assert lo_gols > 0, (
        f"preco de gols vem do lambda verdadeiro; o mercado tem de ganhar, "
        f"deu dif={d_gols:+.4f}"
    )

    d_esc, _, hi_esc = dif("Escanteios Over 8.5")
    assert hi_esc < 0, (
        f"preco de escanteios e sorteado; o modelo tem de ganhar, "
        f"deu dif={d_esc:+.4f}"
    )


def test_so_com_odd_deixa_modelo_e_mercado_no_mesmo_conjunto():
    """Medir o modelo em 7860 picks e o mercado em 4184 compara conjuntos, nao
    previsores."""
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}", odds_corners_over_95=1.77,
                     odds_corners_under_95=2.10) for i in range(40)]
    picks = reconstruir(linhas, "x")["picks"]
    com_odd = [p for p in picks if p["prob_mercado"] is not None]
    assert 0 < len(com_odd) < len(picks), "o recorte tem de ser um subconjunto real"
    assert all(p["mercado_metodo"] == "devig" for p in com_odd)


# ── #227-d: todas as ligas, uma linha por liga ───────────────────────────
def test_piso_e_por_celula_liga_x_mercado():
    """Misturar ligas com taxas-base diferentes num piso so inventaria skill."""
    cmp = _comparador()
    picks = (
        [{"league_id": "A", "market": "m", "outcome": 1}] * 9
        + [{"league_id": "A", "market": "m", "outcome": 0}]
        + [{"league_id": "B", "market": "m", "outcome": 0}] * 9
        + [{"league_id": "B", "market": "m", "outcome": 1}]
    )
    # taxa 0.9 em A e 0.1 em B -> piso por celula = 0.09; piso global seria 0.25
    assert cmp._piso(picks) == pytest.approx(0.09, abs=1e-9)


def test_skill_negativo_quando_pior_que_o_piso():
    cmp = _comparador()
    assert cmp._skill(0.24, 0.22) < 0
    assert cmp._skill(0.20, 0.22) > 0
    assert cmp._skill(None, 0.22) is None
    assert cmp._skill(0.20, 0.0) is None


def test_reconstruir_por_liga_nao_mistura_historicos():
    """O rastreador e por liga: um time da liga A nao pode ganhar forma com
    jogos da liga B so por ter o mesmo nome."""
    a = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}", gc=3, gf=3) for i in range(40)]
    b = [_linha(100 + i, f"T{i % 4}", f"T{(i + 1) % 4}", gc=0, gf=0) for i in range(40)]
    ra = reconstruir(a, "A")["picks"]
    rb = reconstruir(b, "B")["picks"]
    pa = next(p["prob"] for p in ra if p["market"] == "Over 2.5 gols")
    pb = next(p["prob"] for p in rb if p["market"] == "Over 2.5 gols")
    assert pa > pb, "liga com 6 gols por jogo tem de dar Over 2.5 mais provavel"


# ── #229: o ingenuo isola motor de insumo ────────────────────────────────
def test_todo_pick_tem_prob_ingenua_valida():
    linhas = [_linha(i, f"T{i % 4}", f"T{(i + 1) % 4}") for i in range(40)]
    picks = reconstruir(linhas, "x")["picks"]
    assert picks
    for p in picks:
        assert p["prob_ingenuo"] is not None, p["market"]
        assert 0.0 <= p["prob_ingenuo"] <= 1.0


def test_ingenuo_acha_o_sinal_plantado():
    """Se o Poisson direto nao achasse resolucao no controle positivo, ele nao
    serviria de referencia: 'empate com o motor' seria dois cegos empatando."""
    from backend.services.calibracao_slope import inclinacao_com_ic

    partidas = _gerador()(500, com_sinal=True, semente=227)
    picks = [{**p, "prob": p["prob_ingenuo"]}
             for p in reconstruir(partidas, "sintetica", familias=["gols"])["picks"]
             if p["market"] == "Over 2.5 gols" and p["prob_ingenuo"] is not None]
    assert len(picks) > 200
    r = inclinacao_com_ic(picks, reamostras=120)
    assert r["ic95"][0] > 0.15, f"ingenuo sem resolucao no positivo: {r['inclinacao']:.3f} {r['ic95']}"


def test_ingenuo_bate_o_piso_no_controle_positivo():
    cmp = _comparador()
    partidas = _gerador()(500, com_sinal=True, semente=227)
    picks = [{**p, "prob_modelo": p["prob"]}
             for p in reconstruir(partidas, "sintetica", familias=["gols"])["picks"]
             if p["market"] == "Over 2.5 gols"]
    piso = cmp._piso(picks)
    assert cmp._skill(cmp._brier(picks, "prob_ingenuo"), piso) > 0


def test_ingenuo_nao_inventa_sinal_no_controle_negativo():
    cmp = _comparador()
    partidas = _gerador()(500, com_sinal=False, semente=227)
    picks = [{**p, "prob_modelo": p["prob"]}
             for p in reconstruir(partidas, "sintetica", familias=["gols"])["picks"]
             if p["market"] == "Over 2.5 gols"]
    d, lo, hi = cmp._ic_par(picks, "prob_ingenuo", "prob_modelo", cmp._brier, 120)
    # os dois sao ruido aqui; a diferenca entre eles nao pode ser "significativa"
    # nos dois sentidos ao mesmo tempo — o que se exige e que o IC seja largo o
    # bastante para nao afirmar nada com certeza
    assert not (lo > 0 and hi > 0 and lo > 0.01), (lo, hi)
