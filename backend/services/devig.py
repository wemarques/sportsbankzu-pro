"""Remocao de margem das odds (#219).

Por que existe
--------------
`backtesting.py:317` diz, no proprio codigo: "Implied probability = 1/odd (no
overround normalization)". Ou seja, todo EV e todo Brier relativo do sistema
comparam a probabilidade do modelo com 1/odd, que NAO e uma probabilidade —
soma mais que 1. O modelo pode estar perdendo para a margem da casa e nao para
a probabilidade real, e do jeito que esta nao da para saber qual dos dois.

Tres metodos, de proposito
--------------------------
O proporcional e o mais conhecido e o pior para vies favorito-azarao: divide a
margem em proporcao ao preco e por isso desconta demais do favorito. Medido nas
odds reais do Londrina x Juventude, proporcional e Shin divergem 0,74pp no
favorito com a margem podre de 17,8% e 0,47pp com a margem sadia de 7,0% da
bet365 (numeros do teste test_219_devig.py, nao estimativa). E pouco, mas e
sistematico e sempre no mesmo sentido — e num EV apertado o sinal muda.

Shin (1992) modela a margem como protecao da casa contra apostador informado e
e o padrao para 1X2. O metodo de potencia e o terceiro ponto de vista. Os tres
ficam calculaveis para que o ledger (#218) guarde os tres e a escolha vire
medicao em vez de preferencia.

A margem tambem e um detector
-----------------------------
Casa seria opera entre ~2% (Pinnacle) e ~8% (Ladbrokes). Margem de 17,8%
nao e uma casa cara, e uma odd velha — provavelmente a de abertura. Entao a
margem serve para duas coisas ao mesmo tempo: remover o vies e denunciar a
fonte podre. `odds_utilizaveis` e esse gate.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("sportsbankzu.devig")

# Faixa de margem de mercado, em pontos percentuais. Mesma do #214.
MARGEM_MINIMA_PP = float(os.getenv("DEVIG_MARGEM_MIN_PP", "1.0"))
MARGEM_MAXIMA_PP = float(os.getenv("DEVIG_MARGEM_MAX_PP", "12.0"))

METODO_PADRAO = os.getenv("DEVIG_METODO", "shin").strip().lower()


def devig_habilitado() -> bool:
    """Enquanto desligado, nada muda no numero publicado (#219 em sombra)."""
    return os.getenv("DEVIG_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def _implicitas(odds: Sequence[float]) -> Optional[List[float]]:
    try:
        vals = [float(o) for o in odds]
    except (TypeError, ValueError):
        return None
    if len(vals) < 2 or any(v <= 1.0 for v in vals):
        return None
    return [1.0 / v for v in vals]


def margem_pp(odds: Sequence[float]) -> Optional[float]:
    """Sobrerredondo em pontos percentuais. None se alguma odd for invalida."""
    imp = _implicitas(odds)
    if imp is None:
        return None
    return (sum(imp) - 1.0) * 100.0


def odds_utilizaveis(odds: Sequence[float]) -> Tuple[bool, Optional[float], str]:
    """Gate de frescor por margem. Devolve (ok, margem_pp, motivo)."""
    m = margem_pp(odds)
    if m is None:
        return False, None, "odd_invalida"
    if m < MARGEM_MINIMA_PP:
        return False, m, "margem_abaixo_do_possivel"
    if m > MARGEM_MAXIMA_PP:
        return False, m, "margem_fora_de_mercado"
    return True, m, "ok"


# ── metodos ─────────────────────────────────────────────────────────────

def devig_proporcional(odds: Sequence[float]) -> Optional[List[float]]:
    """Divide a margem em proporcao ao preco. Desconta demais do favorito."""
    imp = _implicitas(odds)
    if imp is None:
        return None
    total = sum(imp)
    return [p / total for p in imp]


def devig_shin(odds: Sequence[float], tol: float = 1e-10,
               max_iter: int = 200) -> Optional[List[float]]:
    """Shin (1992). z = fracao de aposta informada; bissecao em z."""
    imp = _implicitas(odds)
    if imp is None:
        return None
    total = sum(imp)
    if total <= 1.0:
        return devig_proporcional(odds)

    def probs(z: float) -> List[float]:
        if z <= 0:
            return [p / total for p in imp]
        out = []
        for pi in imp:
            raiz = math.sqrt(z * z + 4.0 * (1.0 - z) * pi * pi / total)
            out.append((raiz - z) / (2.0 * (1.0 - z)))
        return out

    lo, hi = 0.0, 0.99
    for _ in range(max_iter):
        meio = (lo + hi) / 2.0
        s = sum(probs(meio))
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = meio
        else:
            hi = meio
    p = probs((lo + hi) / 2.0)
    s = sum(p)
    return [x / s for x in p] if s > 0 else None


def devig_potencia(odds: Sequence[float], tol: float = 1e-10,
                   max_iter: int = 200) -> Optional[List[float]]:
    """p_i = pi_i ** k, com k resolvido por bissecao para somar 1."""
    imp = _implicitas(odds)
    if imp is None:
        return None
    if sum(imp) <= 1.0:
        return devig_proporcional(odds)
    lo, hi = 1.0, 10.0
    for _ in range(max_iter):
        k = (lo + hi) / 2.0
        s = sum(p ** k for p in imp)
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2.0
    p = [x ** k for x in imp]
    s = sum(p)
    return [x / s for x in p] if s > 0 else None


_METODOS = {
    "proporcional": devig_proporcional,
    "shin": devig_shin,
    "potencia": devig_potencia,
}


def devig(odds: Sequence[float], metodo: Optional[str] = None) -> Optional[List[float]]:
    fn = _METODOS.get((metodo or METODO_PADRAO).lower(), devig_shin)
    return fn(odds)


def todos_os_metodos(odds: Sequence[float]) -> Dict[str, Optional[List[float]]]:
    """Os tres, para o ledger guardar e a escolha virar medicao."""
    return {nome: fn(odds) for nome, fn in _METODOS.items()}


def prob_justa(odds: Sequence[float], indice: int,
               metodo: Optional[str] = None) -> Optional[float]:
    """Probabilidade de mercado sem margem para UMA das pernas."""
    p = devig(odds, metodo)
    if p is None or not (0 <= indice < len(p)):
        return None
    return p[indice]
