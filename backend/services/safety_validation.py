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
        try:
            from backend.services.reliability_tracker import tracker
            tracker.track("complementares_bloqueados", len(blocked))
        except Exception:
            pass

    return [p for idx, p in enumerate(predictions) if idx not in blocked]


# ─── Audit Action Filtering (#099) ───────────────────────────────────────────

_ACOES_PROIBIDAS = [
    {
        "pattern": r"lambda.*multiplier|lambda.*ajust|lambda_home_mult|lambda_away_mult",
        "regra": "#082",
        "motivo": "Mistral é narrativa — não ajusta parâmetros do pipeline",
    },
    {
        "pattern": r"calibration.*retrain|recalibr.*isotonic|isotonic.*recalibr",
        "regra": "#079",
        "motivo": "Requer MIN_N_BRIER=20 jogos para recalibração",
        "min_jogos": 20,
    },
    {
        "pattern": r"ajustar.*threshold|threshold.*ajust|recalibrar.*threshold|safe_prob.*ajust",
        "regra": "#042",
        "motivo": "Thresholds só podem ser alterados com backtesting documentado",
    },
    {
        "pattern": r"safe.*recalibr|safe.*acur[aá]cia.*ajust|reativar.*safe",
        "regra": "#043",
        "motivo": "Circuit breaker ativo — requer 3 auditorias com accuracy >50%",
    },
]


def filtrar_acoes_por_regras(
    acoes: list, n_jogos: int = 0
) -> Dict[str, list]:
    """Filter audit recommended actions against operational rules (#099).

    Returns {"acoes_validas": [...], "acoes_bloqueadas": [...]}.
    """
    validas: list = []
    bloqueadas: list = []

    for acao in acoes:
        texto = acao if isinstance(acao, str) else str(acao.get("reason", acao.get("parameter", acao)))
        texto_lower = texto.lower()

        hit = False
        for regra in _ACOES_PROIBIDAS:
            if not re.search(regra["pattern"], texto_lower):
                continue
            # Check min_jogos condition
            if "min_jogos" in regra and n_jogos >= regra["min_jogos"]:
                continue  # enough data, allow
            bloqueadas.append({
                "acao_original": texto,
                "regra_violada": regra["regra"],
                "motivo": regra["motivo"],
            })
            hit = True
            break

        if not hit:
            validas.append(acao)

    if bloqueadas:
        logger.warning(
            f"[SAFETY] {len(bloqueadas)} ação(ões) de auditoria bloqueada(s) por regras operacionais"
        )
        try:
            from backend.services.reliability_tracker import tracker
            tracker.track("acoes_bloqueadas", len(bloqueadas))
        except Exception:
            pass

    return {"acoes_validas": validas, "acoes_bloqueadas": bloqueadas}


def filtrar_corrections_por_regras(
    corrections: list, n_jogos: int = 0
) -> Dict[str, list]:
    """Filter correction objects (with parameter/reason fields) against rules (#099)."""
    validas: list = []
    bloqueadas: list = []

    for c in corrections:
        param = str(c.get("parameter", "")).lower()
        reason = str(c.get("reason", "")).lower()
        combined = f"{param} {reason}"

        hit = False
        for regra in _ACOES_PROIBIDAS:
            if not re.search(regra["pattern"], combined):
                continue
            if "min_jogos" in regra and n_jogos >= regra["min_jogos"]:
                continue
            bloqueadas.append({
                "acao_original": f"{c.get('parameter','')}: {c.get('current_value','')} → {c.get('suggested_value','')}",
                "regra_violada": regra["regra"],
                "motivo": regra["motivo"],
            })
            hit = True
            break

        if not hit:
            validas.append(c)

    if bloqueadas:
        logger.warning(
            f"[SAFETY] {len(bloqueadas)} correção(ões) bloqueada(s) por regras operacionais"
        )

    return {"acoes_validas": validas, "acoes_bloqueadas": bloqueadas}
