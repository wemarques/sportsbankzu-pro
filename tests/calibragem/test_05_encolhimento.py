# -*- coding: utf-8 -*-
"""Teste 3 da spec — `n_efetivo` conta JOGOS, nao picks.

Escanteios tem 1.974 picks em 220 jogos. `Over 2.5` e `BTTS` do mesmo jogo
dividem o mesmo placar: nao sao observacoes independentes. Contar picks daria
autonomia quase total a celula em cima de 220 jogos de informacao real.

E a mesma classe de erro do #196 (pareou desfechos de jogos diferentes), do
#243 (comparou odd em escala errada) e do #244 (leu calibracao em fonte
recomputada pos-jogo). Todos foram contagem indevida.
"""
import pytest

from backend.modeling.calibragem import K_FIXO
from backend.modeling.calibragem.estimador import contar_jogos, encolher
from backend.modeling.calibragem.repositorio import Pick


def test_conta_jogos_nao_picks():
    picks = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    assert contar_jogos(picks) == 1


def test_quarenta_picks_de_um_jogo_pesam_como_dois_picks_de_um_jogo():
    """O teste que guarda o detalhe. Mesmo jogo = mesmo peso."""
    um_jogo_40 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(40)]
    um_jogo_2 = [Pick("jogo1", "Corners", "l", 0.5, 1) for _ in range(2)]
    proprio, pai = (0.5, 1.0), (0.0, 1.0)
    assert encolher(proprio, pai, contar_jogos(um_jogo_40), K_FIXO) == \
           encolher(proprio, pai, contar_jogos(um_jogo_2), K_FIXO)


def test_sem_amostra_fica_no_pai():
    assert encolher((9.0, 9.0), (0.1, 0.8), 0, K_FIXO) == (0.1, 0.8)


def test_amostra_igual_a_k_fica_na_metade_do_caminho():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), K_FIXO, K_FIXO)
    assert a == pytest.approx(0.5)
    assert b == pytest.approx(1.0)


def test_amostra_enorme_ignora_o_pai():
    a, b = encolher((1.0, 2.0), (0.0, 0.0), 100000, K_FIXO)
    assert a == pytest.approx(1.0, abs=0.001)
    assert b == pytest.approx(2.0, abs=0.001)


def test_k_cai_no_fixo_com_poucas_celulas():
    from backend.modeling.calibragem.estimador import estimar_k
    k, caiu = estimar_k({("Corners", ""): []})
    assert caiu is True
    assert k == K_FIXO


# ---------------------------------------------------------------------------
# Rodada de correcao 1: `ajustar_hierarquico` costura `contar_jogos`,
# `encolher` e `estimar_k`, mas nenhum teste acima exercitava a fiacao em si
# -- so a execucao manual contra o ledger no passo 5, que nao vira regressao.
# Os testes abaixo usam picks sinteticos (sem banco) para travar a ordem
# familia->liga, o fallback por piso, o fallback por `ajustar`==None, as
# chaves da saida e a propagacao de `k_fixo`.
# ---------------------------------------------------------------------------
from backend.modeling.calibragem import MIN_N_JOGOS
from backend.modeling.calibragem.estimador import ajustar, ajustar_hierarquico


def _picks(prefixo, familia, liga, especificacoes):
    """Um pick por jogo: `match_id` distinto em cada posicao da lista, para
    que `contar_jogos` conte exatamente `len(especificacoes)` jogos nesta
    celula -- a mesma garantia que `test_conta_jogos_nao_picks` cobre para
    `contar_jogos` isolado vale aqui na montagem do cenario."""
    # `p_legado=p` (legado = identidade) mantem estes cenarios sinteticos
    # exercitando so a fiacao do encolhimento, sem a curva legada no meio.
    return [Pick(f"{prefixo}{i}", familia, liga, p, y, p_legado=p)
            for i, (p, y) in enumerate(especificacoes)]


def _mistas(n, ps=(0.2, 0.4, 0.6, 0.8), ruido_a_cada=4):
    """`n` jogos com `p_raw` variado e `y` proximo do que `p_raw` sugere, com
    ruido periodico -- suficiente para o Newton convergir sem separacao
    perfeita (ver Task 4: xs identicos ou y perfeitamente separado deixam a
    Hessiana mal-condicionada)."""
    especificacoes = []
    for i in range(n):
        p = ps[i % len(ps)]
        y = 1 if p >= 0.5 else 0
        if i % ruido_a_cada == 0:
            y = 1 - y
        especificacoes.append((p, y))
    return especificacoes


def test_liga_encolhe_para_familia_nao_para_global():
    """Item 1 da rodada de correcao. Familia e global tem de divergir
    claramente no cenario, e o resultado da liga tem de cair entre a
    estimativa propria dela e a da familia -- nunca perto do global.

    A celula alvo e ('F1', 'biga'): a familia F1 (biga + otherliga) puxa
    para um vies positivo; a familia F2, bem maior, puxa o global para o
    lado oposto. Por convexidade, `encolher` so pode devolver um valor fora
    do intervalo [proprio, pai] se o `pai` usado nao foi o declarado -- e e
    exatamente isso que o teste verifica ao provar que o global fica fora
    desse intervalo nas duas coordenadas.
    """
    biga_spec = []
    ps = [0.15, 0.25, 0.35, 0.45, 0.55]
    for i in range(25):
        p = ps[i % len(ps)]
        y = 1 if (i % 3 != 0) else 0     # desfecho bem acima do que `p` sugere
        biga_spec.append((p, y))
    biga = _picks("f1_biga_", "F1", "biga", biga_spec)

    otherliga_spec = []
    ps2 = [0.2, 0.4, 0.6, 0.8]
    for i in range(22):
        p = ps2[i % len(ps2)]
        y = 1 if p >= 0.5 else 0
        if i % 5 == 0:
            y = 1 - y
        otherliga_spec.append((p, y))
    otherliga = _picks("f1_other_", "F1", "otherliga", otherliga_spec)

    f2_spec = []
    ps3 = [0.3, 0.5, 0.7, 0.9]
    for i in range(60):
        p = ps3[i % len(ps3)]
        y = 0 if (i % 3 != 0) else 1     # vies sistematico oposto, amostra grande
        f2_spec.append((p, y))
    f2 = _picks("f2_", "F2", "ligaF2", f2_spec)

    picks = biga + otherliga + f2
    saida = ajustar_hierarquico(picks)

    proprio = ajustar(biga)
    familia = (saida[("F1", "")]["a"], saida[("F1", "")]["b"])
    globalv = (saida[("", "")]["a"], saida[("", "")]["b"])
    liga = (saida[("F1", "biga")]["a"], saida[("F1", "biga")]["b"])

    # Cenario discriminante: familia e global tem de divergir claramente.
    assert abs(familia[0] - globalv[0]) > 0.2
    assert abs(familia[1] - globalv[1]) > 0.2

    for eixo in (0, 1):
        lo, hi = sorted((proprio[eixo], familia[eixo]))
        assert lo - 1e-9 <= liga[eixo] <= hi + 1e-9, (
            f"eixo {eixo}: liga={liga[eixo]} fora de [proprio, familia]"
            f"=[{lo}, {hi}]"
        )
        # O global fica fora desse intervalo neste cenario -- se a liga
        # tivesse usado global como pai, a asserção acima já teria falhado;
        # esta reforça que a separação é real, não coincidência de escala.
        assert not (lo - 1e-9 <= globalv[eixo] <= hi + 1e-9)

    # Confirmacao numerica exata: a liga e a combinacao convexa de proprio e
    # familia (o no ja computado na saida), com o `k` que o cenario forca.
    assert saida[("F1", "biga")]["k_fixo"] is True
    esperado = encolher(proprio, familia, contar_jogos(biga), K_FIXO)
    assert liga[0] == pytest.approx(esperado[0])
    assert liga[1] == pytest.approx(esperado[1])


def test_liga_abaixo_do_piso_usa_familia():
    """Item 2 (metade liga). Liga com n<20 sai com (a, b) IDENTICO ao no da
    familia (sem `encolher` -- o pai puro) e origem='familia'."""
    pequena = _picks("fa_small_", "FA", "small", _mistas(10))
    grande = _picks("fa_big_", "FA", "big", _mistas(25))
    saida = ajustar_hierarquico(pequena + grande)

    assert contar_jogos(pequena) < MIN_N_JOGOS
    assert saida[("FA", "small")]["origem"] == "familia"
    assert saida[("FA", "small")]["a"] == saida[("FA", "")]["a"]
    assert saida[("FA", "small")]["b"] == saida[("FA", "")]["b"]


def test_familia_abaixo_do_piso_usa_global():
    """Item 2 (metade familia). Familia com n<20 sai com (a, b) IDENTICO ao
    no global e origem='global'."""
    picks = _picks("fb_", "FB", "somente", _mistas(12))
    saida = ajustar_hierarquico(picks)

    assert contar_jogos(picks) < MIN_N_JOGOS
    assert saida[("FB", "")]["origem"] == "global"
    assert saida[("FB", "")]["a"] == saida[("", "")]["a"]
    assert saida[("FB", "")]["b"] == saida[("", "")]["b"]


def test_liga_degenerada_acima_do_piso_cai_no_pai_sem_inventar_ab():
    """Item 3 (liga). n>=20 nao basta: se `ajustar` devolve None (amostra
    degenerada -- todos os desfechos iguais), a celula tem de herdar o pai
    (familia) exatamente, nao gravar um (a, b) inventado pelo Newton."""
    degenerada = _picks("fc_alldeg_", "FC", "alldeg", [(0.5, 1)] * 25)
    normal = _picks("fc_normal_", "FC", "normal", _mistas(25, ruido_a_cada=3))
    saida = ajustar_hierarquico(degenerada + normal)

    assert contar_jogos(degenerada) >= MIN_N_JOGOS   # acima do piso...
    assert ajustar(degenerada) is None               # ...mas degenerada
    assert saida[("FC", "alldeg")]["origem"] == "familia"
    assert saida[("FC", "alldeg")]["a"] == saida[("FC", "")]["a"]
    assert saida[("FC", "alldeg")]["b"] == saida[("FC", "")]["b"]


def test_familia_degenerada_acima_do_piso_cai_no_pai_sem_inventar_ab():
    """Item 3 (familia). Mesma logica um nivel acima: familia com n>=20 mas
    degenerada herda o global exatamente, origem='global'."""
    picks = _picks("fd_", "FD", "onlyliga", [(0.5, 1)] * 25)
    saida = ajustar_hierarquico(picks)

    assert contar_jogos(picks) >= MIN_N_JOGOS
    assert ajustar(picks) is None
    assert saida[("FD", "")]["origem"] == "global"
    assert saida[("FD", "")]["a"] == saida[("", "")]["a"]
    assert saida[("FD", "")]["b"] == saida[("", "")]["b"]


def test_chaves_globais_e_por_familia_nao_sao_sobrescritas_pelo_laco_de_liga():
    """Item 4. A celula global e ("", ""); existe uma entrada (familia, "")
    por familia presente nos picks; e o laco das ligas -- que so grava
    chaves com liga != "" -- nao sobrescreve nenhuma das duas."""
    picks = (_picks("g1a_", "G1", "liga1", _mistas(22))
             + _picks("g1b_", "G1", "liga2", _mistas(22))
             + _picks("g2_", "G2", "liga3", _mistas(22)))
    saida = ajustar_hierarquico(picks)

    assert set(saida.keys()) == {
        ("", ""), ("G1", ""), ("G2", ""),
        ("G1", "liga1"), ("G1", "liga2"), ("G2", "liga3"),
    }
    assert saida[("", "")]["origem"] == "global"
    # As entradas por familia so podem vir do laco de familia -- se o laco
    # de liga as tivesse sobrescrito, a origem seria 'liga'.
    assert saida[("G1", "")]["origem"] in ("familia", "global")
    assert saida[("G2", "")]["origem"] in ("familia", "global")


def test_k_fixo_propaga_para_toda_celula_com_menos_de_cinco_celulas():
    """Item 5. Com menos de `MIN_CELULAS_PARA_ESTIMAR_K` celulas (familia,
    liga) acima do piso, `estimar_k` cai no fixo e TODA celula da saida --
    global, familia e liga, qualquer que seja a origem dela -- carrega
    k_fixo=True."""
    picks = (_picks("h1_", "H1", "l1", _mistas(22))
             + _picks("h2_", "H2", "l2", _mistas(22))
             + _picks("h3_", "H3", "l3", _mistas(22)))
    saida = ajustar_hierarquico(picks)

    assert len(saida) == 7   # global + 3 familias + 3 ligas: so 3 celulas
    assert all(v["k_fixo"] is True for v in saida.values())
