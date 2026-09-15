# -*- coding: utf-8 -*-
"""Simulacao multi-ciclo da camada #248 com o codigo de PRODUCAO (#253/#253-a).

Roda `ciclo.planejar` real, grava pelo MESMO plano de
`repositorio.operacoes_de_gravacao` numa lista em memoria e rele pelas MESMAS
funcoes puras do historico. Nao e teste; e o laboratorio que os testes usam.
"""
import itertools
from datetime import datetime, timedelta, timezone

from backend.modeling.calibragem import ciclo, repositorio
from backend.modeling.calibragem.repositorio import Pick

UTC = timezone.utc
T1 = datetime(2026, 9, 10, 23, 0, tzinfo=UTC)


def vigentes_de(historico):
    return {(r["familia"], r["liga"]): {"versao": r["versao"], "a": r["a"],
                                        "b": r["b"], "criada_em": r["criada_em"]}
            for r in historico if r["status"] == "vigente"}


def gravar_em_memoria(historico, linhas, agora, ids):
    """Executa o plano de `repositorio.operacoes_de_gravacao` sobre uma lista."""
    for op, ln in repositorio.operacoes_de_gravacao(linhas):
        if op == "promover":
            for r in historico:
                if (r["familia"], r["liga"], r["status"]) == (ln["familia"], ln["liga"], "vigente"):
                    r["status"] = "substituida"
            historico.append(dict(ln, status="vigente", criada_em=agora, id=next(ids)))
        historico.append(dict(ln, criada_em=agora, id=next(ids)))


def simular(ciclos, proposta_do_ciclo, *, familia="Over/Under", ligas=("",),
            jogos_por_liga_por_ciclo=5, y_periodico=5, historico=None,
            celulas_do_ajuste=None):
    """`proposta_do_ciclo(k, celula) -> {"a", "b"}`. Uma entrada no ajuste por
    celula de `celulas_do_ajuste` (padrao: a celula-familia e as das ligas).
    Picks de cada ciclo sao publicados 4h antes dele (entre dois crons)."""
    historico = [] if historico is None else historico
    picks, trilha = [], []
    ids = itertools.count(max((r["id"] for r in historico), default=0) + 1)
    jogo = itertools.count()
    celulas = celulas_do_ajuste or sorted({(familia, "")} | {(familia, l) for l in ligas})
    for k in range(1, ciclos + 1):
        agora = T1 + timedelta(hours=8 * (k - 1))
        if k > 1:
            for liga in ligas:
                for _ in range(jogos_por_liga_por_ciclo):
                    i = next(jogo)
                    picks.append(Pick(f"j{i}", familia, liga, 0.6,
                                      1 if i % y_periodico else 0, None, "",
                                      agora - timedelta(hours=4), 0.6))
        ajuste = {c: dict(proposta_do_ciclo(k, c), n_jogos=100, origem="familia",
                          k_fixo=False) for c in celulas}
        plano = ciclo.planejar(picks, ajuste, vigentes_de(historico), historico=historico)
        gravar_em_memoria(historico, ciclo.linhas_do_plano(plano), agora, ids)
        trilha.append({"k": k, "plano": plano, "vigentes": vigentes_de(historico),
                       "ancoras": repositorio.ancoras_do_historico(historico),
                       "picks": list(picks), "historico": [dict(r) for r in historico]})
    return trilha


def status(passo, celula):
    return passo["plano"]["decisoes"][celula]["resultado"]["status"]


def motivo(passo, celula):
    return passo["plano"]["decisoes"][celula]["resultado"]["motivo"]
