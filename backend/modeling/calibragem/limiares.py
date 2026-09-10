# -*- coding: utf-8 -*-
"""Re-derivacao dos limiares de EV e edge, mantendo o volume constante.

A classificacao usa prob RAW (proibicao 11 do CLAUDE.md), entao `safe_prob` e
`neutro_prob` NAO se movem — o raw nao mudou. O volume sobe por `ev` e `edge`,
que consomem a probabilidade corrigida.

Curva e limiar mudam juntos, na mesma versao e na mesma linha de auditoria:
separa-los recria a convivencia de dois regimes que o #244 mediu.
"""
import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from backend.modeling.calibragem.curva import aplicar

logger = logging.getLogger("sportsbankzu.calibragem.limiares")

CAMPOS = ("safe_ev", "neutro_ev", "safe_edge", "neutro_edge")


def _arredondar_para_baixo(x: float, casas: int = 4) -> float:
    """round(x, 4) pode arredondar PARA CIMA, passando do valor cru do corte.

    O corte e sempre um valor real presente em `evs`/`edges` (o k-esimo da
    ordenacao). Com dados discretos ha clusters de empates exatos nesse valor
    (visto empiricamente: 5 picks empatados em 0.12149539... arredondado para
    0.1215 os excluiu todos do `>=`, porque 0.1215 > 0.12149539...). Arredondar
    sempre para baixo mantem o cluster do corte incluido; o preco e, quando a
    faixa entre o corte cru e o arredondado cruza outro valor real, incluir
    alguns picks a mais — e exatamente a folga de ate 2 que o teste aceita.
    """
    fator = 10 ** casas
    return math.floor(x * fator) / fator


def _ev_e_edge(p_corr: float, odd) -> tuple:
    if not odd or float(odd) <= 1.0:
        return (None, None)
    odd = float(odd)
    return (p_corr * odd - 1.0, p_corr - 1.0 / odd)


def contar_por_classe(picks: Sequence, parametros: Dict[str, dict],
                      limiares: Dict[str, dict]) -> Dict[str, Dict[str, int]]:
    """Quantos picks caem em cada classe, por familia."""
    saida: Dict[str, Dict[str, int]] = defaultdict(lambda: {"safe": 0, "neutro": 0})
    for pk in picks:
        par = parametros.get(pk.familia)
        lim = limiares.get(pk.familia)
        if not par or not lim:
            continue
        ev, edge = _ev_e_edge(aplicar(pk.p_raw, par["a"], par["b"]), pk.odd)
        if ev is None:
            continue
        if ev >= lim["safe_ev"] and edge >= lim["safe_edge"]:
            saida[pk.familia]["safe"] += 1
        elif ev >= lim["neutro_ev"] and edge >= lim["neutro_edge"]:
            saida[pk.familia]["neutro"] += 1
    return saida


def _quantil_que_preserva(valores: List[float], quantos: int):
    """O corte que deixa exatamente `quantos` valores acima ou iguais."""
    if quantos <= 0:
        return None
    ordenados = sorted(valores, reverse=True)
    if quantos >= len(ordenados):
        return ordenados[-1] if ordenados else None
    return ordenados[quantos - 1]


def rederivar(picks: Sequence, parametros_antigos: Dict[str, dict],
              parametros_novos: Dict[str, dict],
              limiares_atuais: Dict[str, dict]) -> Dict[str, dict]:
    """Os quatro valores por familia que reproduzem a contagem anterior."""
    alvo = contar_por_classe(picks, parametros_antigos, limiares_atuais)
    por_familia: Dict[str, list] = defaultdict(list)
    for pk in picks:
        por_familia[pk.familia].append(pk)

    saida: Dict[str, dict] = {}
    for familia, atual in limiares_atuais.items():
        pk_familia = por_familia.get(familia) or []
        par = parametros_novos.get(familia)
        if not par:
            saida[familia] = dict(atual)
            continue

        evs, edges = [], []
        for pk in pk_familia:
            ev, edge = _ev_e_edge(aplicar(pk.p_raw, par["a"], par["b"]), pk.odd)
            if ev is not None:
                evs.append(ev)
                edges.append(edge)

        if not evs:
            # Familia sem preco em quase nenhuma linha (cartoes: 88,3%). Nao ha
            # volume a manter constante — registra e nao mexe.
            logger.info("[calibragem] %s sem picks com odd; limiares inalterados",
                        familia)
            saida[familia] = dict(atual)
            continue

        n_safe = alvo.get(familia, {}).get("safe", 0)
        n_ate_neutro = n_safe + alvo.get(familia, {}).get("neutro", 0)
        novo = dict(atual)
        for prefixo, quantos in (("safe", n_safe), ("neutro", n_ate_neutro)):
            ev_cutoff = _quantil_que_preserva(evs, quantos)
            if ev_cutoff is None:
                continue
            # O edge nao compartilha a ordenacao do ev entre picks de odds
            # distintas (ev = odd*p-1, edge = p-1/odd pesam odd de jeitos
            # diferentes) -- um quantil independente de edge intersecta com
            # o conjunto por ev e FICA ABAIXO do alvo (visto empiricamente:
            # 222 de 230 no teste 6). O edge_cutoff tem de ser amarrado ao
            # MESMO conjunto que passou no corte de ev (o minimo de edge
            # dentro dele), senao a condicao conjunta (ev AND edge) nao
            # preserva a contagem por classe.
            indices_no_corte = [i for i, ev in enumerate(evs) if ev >= ev_cutoff]
            if not indices_no_corte:
                continue
            edge_cutoff = min(edges[i] for i in indices_no_corte)
            novo[f"{prefixo}_ev"] = _arredondar_para_baixo(ev_cutoff)
            novo[f"{prefixo}_edge"] = _arredondar_para_baixo(edge_cutoff)
        saida[familia] = novo
    return saida
