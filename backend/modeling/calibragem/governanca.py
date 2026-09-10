# -*- coding: utf-8 -*-
"""Politica: quem PODE mudar, e quanto. Sem ajuste e sem I/O.

A trava e expressa em pontos de PROBABILIDADE, nao em `a` e `b`. Limitar os
parametros separadamente e dificil de raciocinar: o mesmo delta em `a` move
pouco no meio da escala e muito nas pontas.
"""
import logging
from typing import Optional

from backend.modeling.calibragem import MIN_N_JOGOS, PASSO_MAXIMO_PP
from backend.modeling.calibragem.curva import distancia_maxima

logger = logging.getLogger("sportsbankzu.calibragem.governanca")

_ITER_BUSCA = 40


def avaliar_proposta(proposta: dict, vigente: dict, n_jogos: int,
                     limite: Optional[float] = None) -> dict:
    """Decide o que de fato passa a valer. Nunca levanta."""
    limite = PASSO_MAXIMO_PP if limite is None else limite
    a_v, b_v = float(vigente["a"]), float(vigente["b"])
    a_p, b_p = float(proposta["a"]), float(proposta["b"])

    def _mantem(status: str, motivo: str) -> dict:
        return {"a": a_v, "b": b_v, "status": status,
                "fator_encurtamento": None, "motivo": motivo}

    if n_jogos < MIN_N_JOGOS:
        return _mantem("abaixo_do_piso",
                       f"n_jogos={n_jogos} < {MIN_N_JOGOS} (#079)")

    if b_p <= 0:
        # b <= 0 inverteria a ordem das probabilidades, e a regra do corredor
        # (#246-a) decide por ordem — a correcao mudaria o corredor por efeito
        # colateral, sem ninguem decidir.
        return _mantem("rejeitada", f"b={b_p:.4f} nao positivo; ordem inverteria")

    if (a_p, b_p) == (a_v, b_v):
        return _mantem("inalterada", "proposta identica a vigente")

    if distancia_maxima(a_v, b_v, a_p, b_p) <= limite:
        return {"a": a_p, "b": b_p, "status": "adotada",
                "fator_encurtamento": None, "motivo": ""}

    # Encurta ao longo do segmento vigente->proposta. A distancia cresce de
    # forma monotona com t, entao bisseccao acha o maior t que cabe.
    baixo, alto = 0.0, 1.0
    for _ in range(_ITER_BUSCA):
        meio = (baixo + alto) / 2.0
        a_m = a_v + meio * (a_p - a_v)
        b_m = b_v + meio * (b_p - b_v)
        if distancia_maxima(a_v, b_v, a_m, b_m) <= limite:
            baixo = meio
        else:
            alto = meio
    a_f = a_v + baixo * (a_p - a_v)
    b_f = b_v + baixo * (b_p - b_v)
    return {"a": a_f, "b": b_f, "status": "encurtada",
            "fator_encurtamento": baixo,
            "motivo": f"passo limitado a {limite:.4f} de probabilidade"}
