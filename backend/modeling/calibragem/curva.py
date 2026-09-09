# -*- coding: utf-8 -*-
"""A curva de correcao: logit(p') = a + b*logit(p).

Matematica pura, sem I/O e sem dependencia externa. `a` e o deslocamento
sistematico (positivo = o motor publica abaixo da realidade); `b` e a
dispersao (b < 1 = o motor exagera nos extremos).
"""
import math
from typing import Optional

from backend.modeling.calibragem import VERSAO_LEGADO

# Prende p antes do logit. 1e-6 mantem logit em ~±13,8, longe de estourar em
# float, e a diferenca em probabilidade e invisivel no card (0,0001%).
_EPS = 1e-6

_FAMILIAS = (
    ("escanteios", "Corners"),
    ("cartoes", "Cards"),
    ("cartões", "Cards"),
    ("btts", "BTTS"),
    ("dc ", "Double Chance"),
    ("dupla chance", "Double Chance"),
    ("1x2", "1X2"),
    ("over ", "Over/Under"),
    ("under ", "Over/Under"),
)


def _prender(p: float) -> float:
    return min(max(float(p), _EPS), 1.0 - _EPS)


def _logit(p: float) -> float:
    p = _prender(p)
    return math.log(p / (1.0 - p))


def _sigmoide(x: float) -> float:
    # Forma estavel nos dois lados: evita overflow de exp(+x) para x grande.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def aplicar(p: float, a: float, b: float) -> float:
    """logit(p_corrigida) = a + b * logit(p). Monotona crescente se b > 0."""
    return _sigmoide(a + b * _logit(p))


def familia_do_mercado(market: str) -> str:
    """Familia a que o rotulo pertence. Levanta se nao reconhecer.

    Mercado novo tem de quebrar aqui em vez de cair numa familia por acaso —
    calibrar Handicap com a curva de 1X2 seria um erro invisivel.
    """
    m = (market or "").strip().lower()
    for prefixo, familia in _FAMILIAS:
        if prefixo in m:
            return familia
    raise ValueError(f"familia desconhecida para o mercado '{market}'")


def distancia_maxima(a1: float, b1: float, a2: float, b2: float,
                     passo: float = 0.001) -> float:
    """max |curva(p; a1,b1) - curva(p; a2,b2)| para p em [0,02; 0,98].

    Varredura em grade em vez de solucao analitica: a diferenca de duas
    sigmoides pode ter dois maximos locais, e a grade de 0,001 erra no maximo
    alguns milesimos de ponto — folgado para uma trava de 2 pontos.
    """
    pior = 0.0
    p = 0.02
    while p <= 0.98 + 1e-12:
        d = abs(aplicar(p, a1, b1) - aplicar(p, a2, b2))
        if d > pior:
            pior = d
        p += passo
    return pior


def aplicar_versao(raw: float, market: str, league_id: str, regime: str,
                   parametros: Optional[dict] = None):
    """Aplica a versao vigente da celula. Versao 0 delega ao legado.

    `parametros` e o mapa {(familia, liga): (versao, a, b)} lido pelo
    repositorio e passado pelo chamador. Ausente, ou celula ausente dele,
    significa versao 0 — o comportamento de hoje.
    """
    from backend.modeling.calibragem.legado import calibrar_legado

    if not parametros:
        return calibrar_legado(raw, market, league_id, regime)

    try:
        familia = familia_do_mercado(market)
    except ValueError:
        return calibrar_legado(raw, market, league_id, regime)

    chave = (familia, league_id or "")
    entrada = parametros.get(chave) or parametros.get((familia, ""))
    if not entrada or entrada[0] == VERSAO_LEGADO:
        return calibrar_legado(raw, market, league_id, regime)

    _versao, a, b = entrada
    detalhe = calibrar_legado(raw, market, league_id, regime)
    detalhe.final = aplicar(raw, a, b)
    detalhe.tipo_banda = f"curva-v{_versao}"
    return detalhe
