# -*- coding: utf-8 -*-
"""#253 - governanca por ancora: a janela enche, o teto segura, a rede dispara.

Etapa 5 do CLAUDE.md: rede de seguranca que nunca disparou em teste nao conta.
Os cenarios multi-ciclo abaixo rodam o `ciclo.planejar` REAL, gravam pelo
MESMO plano de operacoes de `repositorio.gravar_ciclo` (em memoria) e releem
o historico pelas MESMAS funcoes puras que o ciclo usa em producao.

Formato de producao que motivou a regra (Corners/familia, 09-10 -> 09-13):
10 ciclos seguidos `encurtada`, a de 0,05 a 0,63, janela sempre vazia.
"""
import itertools
from datetime import datetime, timedelta, timezone

import pytest

from backend.modeling.calibragem import (
    MIN_N_JOGOS, PASSO_MAXIMO_PP, TETO_DERIVA_PP,
)
from backend.modeling.calibragem import ciclo, governanca, repositorio
from backend.modeling.calibragem.curva import distancia_maxima
from backend.modeling.calibragem.repositorio import Pick

UTC = timezone.utc
T1 = datetime(2026, 9, 10, 23, 0, tzinfo=UTC)
CELULA = ("Over/Under", "")
TOL = 0.002          # grade de `distancia_maxima` (passo 0,001)


# ─── funcoes puras do historico ──────────────────────────────────────────────

def _ln(status, a, b, criada_em, id_, familia="Over/Under", liga=""):
    return {"id": id_, "familia": familia, "liga": liga, "status": status,
            "a": a, "b": b, "criada_em": criada_em}


def test_ancora_sem_historico_nao_existe():
    assert repositorio.ancoras_do_historico([]) == {}


def test_ancora_sem_validacao_e_o_legado_desde_a_primeira_linha():
    h = [_ln("encurtada", 0.1, 1.0, T1, 1), _ln("vigente", 0.1, 1.0, T1, 2),
         _ln("encurtada", 0.2, 1.0, T1 + timedelta(hours=8), 3)]
    anc = repositorio.ancoras_do_historico(h)[CELULA]
    assert (anc["a"], anc["b"], anc["desde"]) == (0.0, 1.0, T1)


def test_ancora_e_a_ultima_ancorada_ou_revertida():
    t2, t3 = T1 + timedelta(hours=8), T1 + timedelta(hours=16)
    h = [_ln("encurtada", 0.1, 1.0, T1, 1),
         _ln("revertida", 0.0, 1.0, t2, 2),
         _ln("ancorada", 0.05, 1.02, t3, 3)]
    anc = repositorio.ancoras_do_historico(h)[CELULA]
    assert (anc["a"], anc["b"], anc["desde"]) == (0.05, 1.02, t3)


def test_curva_servida_e_a_vigente_no_instante_da_publicacao():
    t2 = T1 + timedelta(hours=8)
    h = [_ln("substituida", 0.1, 1.0, T1, 1), _ln("vigente", 0.2, 1.0, t2, 2),
         _ln("encurtada", 0.9, 1.0, t2, 3)]         # decisao, nao vigencia
    vig = repositorio.vigencia_do_historico(h)[CELULA]
    assert governanca.curva_servida(vig, T1 - timedelta(hours=1)) == (0.0, 1.0)
    assert governanca.curva_servida(vig, T1) == (0.0, 1.0)          # estrito
    assert governanca.curva_servida(vig, T1 + timedelta(hours=1)) == (0.1, 1.0)
    assert governanca.curva_servida(vig, t2 + timedelta(hours=1)) == (0.2, 1.0)


@pytest.mark.parametrize("sequencia,esperado", [
    ([], 0),
    (["revertida"], 1),
    (["revertida", "adotada", "encurtada", "revertida"], 2),   # movimento NAO zera
    (["revertida", "ancorada"], 0),                             # validacao zera
    (["ancorada", "revertida", "inalterada", "congelada"], 1),
])
def test_reversoes_seguidas_so_ancorada_zera(sequencia, esperado):
    h = [_ln(st, 0.0, 1.0, T1 + timedelta(hours=i), i + 1)
         for i, st in enumerate(sequencia)]
    assert repositorio.reversoes_seguidas_do_historico(h, *CELULA) == esperado


def test_ultimo_status_ignora_escrituracao_e_enxerga_ancorada():
    h = [_ln("congelada", 0, 1, T1, 1), _ln("ancorada", 0, 1, T1, 2),
         _ln("vigente", 0, 1, T1, 3), _ln("substituida", 0, 1, T1, 4)]
    assert repositorio.ultimo_status_do_historico(h, *CELULA) == "ancorada"
    assert repositorio.ultimo_status_do_historico([], *CELULA) is None


def test_operacoes_de_gravacao_promovem_so_o_conjunto_de_promocao():
    linhas = [{"familia": "F", "liga": "", "status": st}
              for st in ("adotada", "encurtada", "revertida", "ancorada",
                         "inalterada", "congelada")]
    ops = repositorio.operacoes_de_gravacao(linhas)
    promovidos = [op[1]["status"] for op in ops if op[0] == "promover"]
    assert promovidos == ["adotada", "encurtada", "revertida"]


# ─── teto de deriva ──────────────────────────────────────────────────────────

ZERO = {"a": 0.0, "b": 1.0}


def test_teto_segura_a_proposta_mesmo_dentro_da_trava_por_ciclo():
    vig = {"a": 0.13, "b": 1.0}             # ~3,2pp da ancora
    assert distancia_maxima(0.0, 1.0, vig["a"], vig["b"]) < TETO_DERIVA_PP
    r = governanca.avaliar_proposta({"a": 0.5, "b": 1.0}, vig, 100, ancora=ZERO)
    assert r["status"] == "encurtada"
    assert distancia_maxima(0.0, 1.0, r["a"], r["b"]) <= TETO_DERIVA_PP + TOL
    assert distancia_maxima(vig["a"], vig["b"], r["a"], r["b"]) <= PASSO_MAXIMO_PP + TOL


def test_no_teto_nao_ha_versao_nova():
    vig = {"a": 0.0, "b": 1.0}
    r1 = governanca.avaliar_proposta({"a": 2.0, "b": 1.0}, vig, 100, ancora=ZERO)
    r2 = governanca.avaliar_proposta({"a": 2.0, "b": 1.0}, r1, 100, ancora=ZERO)
    r3 = governanca.avaliar_proposta({"a": 2.0, "b": 1.0}, r2, 100, ancora=ZERO)
    assert r3["status"] == "inalterada" and "teto de deriva" in r3["motivo"]
    assert (r3["a"], r3["b"]) == (r2["a"], r2["b"])


# ─── simulacao multi-ciclo com o codigo real ─────────────────────────────────

def _vigentes(historico):
    return {(r["familia"], r["liga"]): {"versao": r["versao"], "a": r["a"],
                                        "b": r["b"], "criada_em": r["criada_em"]}
            for r in historico if r["status"] == "vigente"}


def _gravar_em_memoria(historico, linhas, agora, ids):
    """Executa o plano de `repositorio.operacoes_de_gravacao` sobre uma lista."""
    for op, ln in repositorio.operacoes_de_gravacao(linhas):
        if op == "promover":
            for r in historico:
                if (r["familia"], r["liga"], r["status"]) == (ln["familia"], ln["liga"], "vigente"):
                    r["status"] = "substituida"
            historico.append(dict(ln, status="vigente", criada_em=agora, id=next(ids)))
        historico.append(dict(ln, criada_em=agora, id=next(ids)))


def _simular(ciclos, proposta_do_ciclo, picks_por_ciclo=5, y_periodico=5):
    historico, picks, ids, trilha = [], [], itertools.count(1), []
    jogo = itertools.count()
    for k in range(1, ciclos + 1):
        agora = T1 + timedelta(hours=8 * (k - 1))
        if k > 1:
            for _ in range(picks_por_ciclo):
                i = next(jogo)
                picks.append(Pick(f"j{i}", "Over/Under", "", 0.6,
                                  1 if i % y_periodico else 0, None, "",
                                  agora - timedelta(hours=4), 0.6))
        prop = dict(proposta_do_ciclo(k), n_jogos=100, origem="familia", k_fixo=False)
        vigentes = _vigentes(historico)
        plano = ciclo.planejar(picks, {CELULA: prop}, vigentes, historico=historico)
        linhas = ciclo.linhas_do_plano(plano)
        _gravar_em_memoria(historico, linhas, agora, ids)
        vig = _vigentes(historico).get(CELULA, {"a": 0.0, "b": 1.0, "criada_em": None})
        anc = repositorio.ancoras_do_historico(historico)[CELULA]
        trilha.append({"k": k, "status": plano["decisoes"][CELULA]["resultado"]["status"],
                       "motivo": plano["decisoes"][CELULA]["resultado"]["motivo"],
                       "vig": (vig["a"], vig["b"]), "criada_em": vig["criada_em"],
                       "anc": (anc["a"], anc["b"]), "picks": list(picks)})
    return trilha


def _dist(p, q):
    return distancia_maxima(p[0], p[1], q[0], q[1])


def test_etapa5_teto_segura_o_formato_de_producao_em_10_ciclos():
    """Proposta distante todo ciclo, janela sem jogos (o 09-10 -> 09-13)."""
    trilha = _simular(10, lambda k: {"a": 1.5, "b": 1.0}, picks_por_ciclo=0)
    for passo in trilha:
        assert _dist(passo["vig"], passo["anc"]) <= TETO_DERIVA_PP + TOL, passo
    assert [p["status"] for p in trilha[:2]] == ["encurtada", "encurtada"]
    assert all(p["status"] == "inalterada" for p in trilha[2:]), [p["status"] for p in trilha]

    # Controle: a governanca SEM ancora, os mesmos 10 ciclos.
    vig = dict(ZERO)
    for _ in range(10):
        r = governanca.avaliar_proposta({"a": 1.5, "b": 1.0}, vig, 100)
        vig = {"a": r["a"], "b": r["b"]}
    assert distancia_maxima(0.0, 1.0, vig["a"], vig["b"]) > 0.15


def _alternando(a1, a2):
    return lambda k: {"a": a1 if k % 2 else a2, "b": 1.0}


def test_etapa5_reversao_dispara_com_versoes_girando_todo_ciclo():
    """Curva servida PIOR (a < 0 com frequencia 0,8 > 0,6). A versao troca
    todo ciclo; a janela da ancora chega a 20 jogos no ciclo 5 e reverte."""
    trilha = _simular(5, _alternando(-0.05, -0.07))
    assert [p["status"] for p in trilha[:4]] == ["adotada"] * 4
    assert trilha[4]["status"] == "revertida", trilha[4]["motivo"]
    assert trilha[4]["vig"] == (0.0, 1.0)
    assert "20 jogos" in trilha[4]["motivo"]

    # Controle: a janela antiga (criada_em da VIGENTE) tinha 5 jogos no ciclo 5.
    antes_do_5 = trilha[3]
    antiga = ciclo.janela_de_reversao(trilha[4]["picks"], antes_do_5["criada_em"])
    assert len({p.match_id for p in antiga}) == 5 < MIN_N_JOGOS


def test_etapa5_ancora_avanca_quando_a_curva_servida_ganha():
    """Curva servida MELHOR: `ancorada` no ciclo 5, e dali o teto e medido a
    partir da nova ancora — a curva pode passar de 4pp do legado."""
    melhor = _alternando(0.05, 0.07)
    trilha = _simular(9, lambda k: melhor(k) if k <= 5 else {"a": 0.6, "b": 1.0})
    assert trilha[4]["status"] == "ancorada", trilha[4]["motivo"]
    assert trilha[4]["anc"] == trilha[3]["vig"]
    fim = trilha[-1]
    assert _dist(fim["vig"], fim["anc"]) <= TETO_DERIVA_PP + TOL
    assert _dist(fim["vig"], (0.0, 1.0)) > TETO_DERIVA_PP


def test_etapa5_duas_reversoes_seguidas_congelam_e_o_congelamento_fica():
    trilha = _simular(10, _alternando(-0.05, -0.07))
    status = [p["status"] for p in trilha]
    assert status[4] == "revertida"
    assert status[8] == "congelada", status
    assert status[9] == "congelada", status
