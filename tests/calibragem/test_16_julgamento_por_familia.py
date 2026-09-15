# -*- coding: utf-8 -*-
"""#253-a - o julgamento e POR FAMILIA, somando as ligas.

No #253 a janela era por celula de liga e nenhuma das 20 ligas juntava 20
jogos em 10 ciclos. Aqui: 5 ligas com 1 jogo por ciclo cada juntam 20 jogos
da familia no ciclo 5 — cada liga sozinha teria 4.
"""
from datetime import timedelta

from backend.modeling.calibragem import MIN_N_JOGOS, TETO_DERIVA_PP
from backend.modeling.calibragem import ciclo, governanca
from backend.modeling.calibragem.curva import distancia_maxima
from backend.modeling.calibragem.repositorio import Pick

from tests.calibragem.simulacao import T1, motivo, simular, status

F = "Over/Under"
LIGAS = ("l1", "l2", "l3", "l4", "l5")
CELULAS = [(F, "")] + [(F, l) for l in LIGAS]
TOL = 0.002


def _alternando(a1, a2):
    return lambda k, celula: {"a": a1 if k % 2 else a2, "b": 1.0}


def _simular(ciclos, proposta, **kw):
    return simular(ciclos, proposta, familia=F, ligas=LIGAS,
                   jogos_por_liga_por_ciclo=1, **kw)


# ─── a curva e a ancora de cada pick ─────────────────────────────────────────

def test_pick_e_pontuado_pela_liga_e_cai_na_familia_antes_da_liga_existir():
    t_fam, t_liga = T1, T1 + timedelta(hours=8)
    vigencia = {(F, ""): [(t_fam, 0.1, 1.0)], (F, "l1"): [(t_liga, 0.3, 1.0)]}
    antes = Pick("a", F, "l1", 0.6, 1, publicado_em=t_fam + timedelta(hours=1), p_legado=0.6)
    depois = antes._replace(match_id="b", publicado_em=t_liga + timedelta(hours=1))
    outra = antes._replace(match_id="c", liga="l9", publicado_em=t_liga + timedelta(hours=1))
    assert governanca.curva_servida_do_pick(vigencia, antes) == (0.1, 1.0)
    assert governanca.curva_servida_do_pick(vigencia, depois) == (0.3, 1.0)
    assert governanca.curva_servida_do_pick(vigencia, outra) == (0.1, 1.0)
    cedo = antes._replace(publicado_em=t_fam - timedelta(hours=1))
    assert governanca.curva_servida_do_pick(vigencia, cedo) == (0.0, 1.0)


def test_ancora_do_pick_e_a_da_liga_senao_familia_senao_legado():
    ancoras = {(F, ""): {"a": 0.1, "b": 1.0, "desde": T1},
               (F, "l1"): {"a": 0.2, "b": 1.0, "desde": T1}}
    assert governanca.ancora_do_pick(ancoras, F, "l1") == (0.2, 1.0)
    assert governanca.ancora_do_pick(ancoras, F, "l9") == (0.1, 1.0)
    assert governanca.ancora_do_pick({}, F, "l1") == (0.0, 1.0)


# ─── Etapa 5: as redes disparam somando as ligas ─────────────────────────────

def test_etapa5_familia_reverte_no_ciclo_5_todas_as_celulas():
    trilha = _simular(5, _alternando(-0.05, -0.07))
    quinto = trilha[4]
    assert {c: status(quinto, c) for c in CELULAS} == {c: "revertida" for c in CELULAS}, \
        motivo(quinto, (F, ""))
    assert "20 jogos" in motivo(quinto, (F, "l1"))
    assert all((v["a"], v["b"]) == (0.0, 1.0) for v in quinto["vigentes"].values())

    # Controle: a janela de UMA liga, no mesmo ciclo, tinha 4 jogos.
    so_l1 = [p for p in quinto["picks"] if p.liga == "l1"]
    assert len({p.match_id for p in so_l1}) == 4 < MIN_N_JOGOS


def test_etapa5_familia_ancora_quando_a_servida_ganha():
    trilha = _simular(5, _alternando(0.05, 0.07))
    quinto = trilha[4]
    assert {c: status(quinto, c) for c in CELULAS} == {c: "ancorada" for c in CELULAS}


def test_etapa5_duas_reversoes_da_familia_congelam_todas():
    trilha = _simular(10, _alternando(-0.05, -0.07))
    assert status(trilha[4], (F, "l3")) == "revertida"
    assert {c: status(trilha[8], c) for c in CELULAS} == {c: "congelada" for c in CELULAS}
    assert {c: status(trilha[9], c) for c in CELULAS} == {c: "congelada" for c in CELULAS}


def test_celula_vigente_fora_do_ajuste_tambem_reverte():
    """l5 entra no ajuste so nos dois primeiros ciclos (fica vigente) e depois
    some da amostra do ajuste; o veredito da familia ainda tem de alcanca-la."""
    base = _simular(2, _alternando(-0.05, -0.07))
    historico = base[-1]["historico"]
    assert (F, "l5") in base[-1]["vigentes"]
    sem_l5 = [c for c in CELULAS if c != (F, "l5")]
    # continua do ciclo 3 em diante, com o mesmo historico e sem l5 no ajuste
    trilha = simular(3, _alternando(-0.05, -0.07), familia=F, ligas=LIGAS,
                     jogos_por_liga_por_ciclo=2, historico=historico,
                     celulas_do_ajuste=sem_l5)
    fim = trilha[-1]
    decisoes = fim["plano"]["decisoes"]
    if status(fim, (F, "")) == "revertida":
        assert (F, "l5") in decisoes and status(fim, (F, "l5")) == "revertida"
        assert decisoes[(F, "l5")]["origem"] == "julgamento-familia"
        assert (fim["vigentes"][(F, "l5")]["a"], fim["vigentes"][(F, "l5")]["b"]) == (0.0, 1.0)
    else:
        raise AssertionError(f"familia nao reverteu: {motivo(fim, (F, ''))}")


def test_teto_por_celula_continua_em_todo_ciclo():
    trilha = _simular(8, lambda k, c: {"a": 1.5, "b": 1.0}, y_periodico=10 ** 9)
    for passo in trilha:
        for celula, vig in passo["vigentes"].items():
            anc = passo["ancoras"][celula]
            assert distancia_maxima(vig["a"], vig["b"], anc["a"], anc["b"]) <= TETO_DERIVA_PP + TOL


def test_janela_da_familia_sem_historico_e_vazia():
    assert ciclo.desde_da_familia({}, F, [(F, "l1")]) is None
