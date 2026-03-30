"""Safety hard constraints for market predictions (#098).

Validates mathematical integrity BEFORE sending to frontend.
If complementary markets (Over/Under on same line) sum > 105%,
the pick with lower EV is blocked.
"""

import logging
import re
from typing import List, Dict, Set

logger = logging.getLogger("sportsbankzu.safety")

# Regex pairs for complementary markets (order: pattern_a, pattern_b)
_COMPLEMENTARY_PAIRS = [
    (r"under\s*(\d+\.?\d*)\s*gol", r"over\s*(\d+\.?\d*)\s*gol"),
    (r"escanteios?\s*under\s*(\d+\.?\d*)", r"escanteios?\s*over\s*(\d+\.?\d*)"),
    (r"cart(?:oes|ões)?\s*under\s*(\d+\.?\d*)", r"cart(?:oes|ões)?\s*over\s*(\d+\.?\d*)"),
    (r"btts\s*sim", r"btts\s*n[aã]o"),
]

_MAX_COMPLEMENTARY_SUM = 105  # 5% tolerance for rounding


def _sao_complementares(m1: str, m2: str) -> bool:
    """Check if two markets are complementary (Over/Under on same line)."""
    for pat_a, pat_b in _COMPLEMENTARY_PAIRS:
        # Forward: m1=A, m2=B
        ma = re.search(pat_a, m1)
        mb = re.search(pat_b, m2)
        if ma and mb:
            la = ma.group(1) if ma.lastindex else ""
            lb = mb.group(1) if mb.lastindex else ""
            if la == lb or not la or not lb:
                return True
        # Reverse: m1=B, m2=A
        ma2 = re.search(pat_b, m1)
        mb2 = re.search(pat_a, m2)
        if ma2 and mb2:
            la2 = ma2.group(1) if ma2.lastindex else ""
            lb2 = mb2.group(1) if mb2.lastindex else ""
            if la2 == lb2 or not la2 or not lb2:
                return True
    return False


def validar_mercados_complementares(predictions: List[Dict]) -> List[Dict]:
    """Block picks where complementary probabilities sum > 105%.

    Keeps the pick with higher EV, removes the other.
    This is a hard constraint — blocked picks are NOT shown to the user.
    """
    if not predictions or len(predictions) < 2:
        return predictions

    blocked: Set[int] = set()

    for i, p1 in enumerate(predictions):
        if i in blocked:
            continue
        m1 = (p1.get("mercado") or "").lower()
        prob1 = p1.get("prob_max", 0) or 0

        for j, p2 in enumerate(predictions):
            if j <= i or j in blocked:
                continue
            m2 = (p2.get("mercado") or "").lower()
            prob2 = p2.get("prob_max", 0) or 0

            if not _sao_complementares(m1, m2):
                continue

            soma = prob1 + prob2
            if soma <= _MAX_COMPLEMENTARY_SUM:
                continue

            ev1 = p1.get("ev", 0) or 0
            ev2 = p2.get("ev", 0) or 0

            if ev1 >= ev2:
                blocked.add(j)
                logger.error(
                    f"[SAFETY] Complementares somam {soma:.0f}%%: "
                    f"{p1.get('mercado')} ({prob1}%%) + {p2.get('mercado')} ({prob2}%%). "
                    f"Bloqueado: {p2.get('mercado')} (EV menor)"
                )
            else:
                blocked.add(i)
                logger.error(
                    f"[SAFETY] Complementares somam {soma:.0f}%%: "
                    f"{p1.get('mercado')} ({prob1}%%) + {p2.get('mercado')} ({prob2}%%). "
                    f"Bloqueado: {p1.get('mercado')} (EV menor)"
                )
                break  # p1 blocked, exit inner loop

    if blocked:
        logger.warning(f"[SAFETY] {len(blocked)} pick(s) bloqueado(s) por inconsistência complementar")

    return [p for idx, p in enumerate(predictions) if idx not in blocked]
