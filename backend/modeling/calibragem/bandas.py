# -*- coding: utf-8 -*-
"""Primitivas de deflação por banda + por liga — módulo normal, não congelado.

Estas funções e constantes NÃO pertencem só à versão 0 (`legado.py`). Elas são
compartilhadas por múltiplos subsistemas que não passam por
`calibragem.curva.aplicar_versao` e continuam vivos independente do destino da
camada aprendida:

- o braço shadow do #179/#240 (`_band_deflation_v179_shadow`,
  `apply_probability_deflation_with_shadow`, em `ev_classification.py`);
- o gate SAFE por liga (#052/#185, `_is_safe_enabled` em `ev_classification.py`);
- o threshold calibrado por liga (#055, `_get_calibrated_threshold` em
  `ev_classification.py`);
- o diagnóstico de banda 50-60% em `backend/routes/health.py`.

Ao contrário de `legado.py`, este módulo NÃO é deletável quando a versão 0
sair de uso — sua vida útil é independente da migração para a camada
aprendida. `legado.py` importa daqui o que `calibrar_legado` precisa; não
duplica.
"""

# ── Probability deflation by band + per-league (#105) ──────────────────
# Based on Brier #104 (379 picks): model overconfident at 70%+ bands.
# Replaces uniform 15% concept (#043) with progressive deflation.

_LEAGUE_DEFLATION = {
    "brasileirao-serie-a": 0.90,  # Δ=-0.075, Acc=46% (N=24)
    "league-two": 0.95,           # Δ=-0.013, Acc=48% (N=23)
}


def _league_deflation_factor(league_id: str) -> float:
    """#189-e: resolve o alias (#185) ANTES do lookup no dicionário estático.

    O fluxo do dashboard passa ids de frontend ('brazil-serie-a'); o
    dicionário é chaveado pelo id canônico ('brasileirao-serie-a').
    Sem esta resolução, o fator 0.90 do Brasileirão nunca era aplicado.
    """
    if not league_id:
        return 1.0
    lid = _canonical_league(league_id) or league_id
    return _LEAGUE_DEFLATION.get(lid, 1.0)


# #189-a: nós da deflação contínua. Cada nó ancora o valor da antiga banda
# no PONTO MÉDIO da banda (a banda [0.60, 0.70) valia 0.15 → nó em 0.65);
# entre nós a deflação é interpolada linearmente. Isso elimina as
# descontinuidades das fronteiras de banda do #105, onde um pick de raw
# 60.0% exibia prob/EV PIORES que um de 59.9% (quedas de até 4pp em
# 0.70/0.80) — violação de monotonicidade confirmada numericamente na
# auditoria de 2026-08-29.
# O nó de 0.55 usa 0.05 (era 0.12): promoção da recalibração #179 — o
# UNBLOCK_REPORT mostrou a banda 50-60% subconfiante em -12.7pp
# (previsto 54.8%, real 67.5%, N=1796), gap ≈ exatamente a deflação de
# 0.12 então aplicada.
# Monotonicidade de p*(1-d(p)): d'(p) máximo = 1.0 (trecho 0.55→0.65);
# f'(p) = 1 - d - p*d' >= 1 - 0.15 - 0.65 = 0.20 > 0 em todo o domínio.
_DEFLATION_KNOTS = [
    (0.45, 0.10),
    (0.55, 0.05),  # #179 promovido (era 0.12 na banda 50-60%)
    (0.65, 0.15),
    (0.75, 0.20),
    (0.85, 0.25),
]


def _band_deflation(prob: float, knots=None) -> float:
    """Deflação progressiva CONTÍNUA por interpolação linear entre nós (#189-a).

    Substitui a função-degrau do #105 (não-monotônica nas fronteiras).
    Fora dos nós extremos, o valor é constante (0.10 abaixo de 0.45;
    0.25 acima de 0.85).

    `knots` existe para o braço shadow do #179/#240 usar a MESMA matemática
    com nós diferentes — o que deve divergir entre live e shadow é o nó, não
    a interpolação. Omitido, usa os nós de produção.
    """
    knots = knots if knots is not None else _DEFLATION_KNOTS
    if prob <= knots[0][0]:
        return knots[0][1]
    if prob >= knots[-1][0]:
        return knots[-1][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if prob <= x1:
            t = (prob - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return knots[-1][1]  # inalcançável; segurança


def apply_probability_deflation(prob: float, league_id: str = "") -> float:
    """Apply progressive band deflation + per-league factor (#105).

    Args:
        prob: Model probability (0-1)
        league_id: League slug for per-league adjustment

    Returns:
        Deflated probability, floored at 0.05.
    """
    deflation = _band_deflation(prob)
    deflated = prob * (1.0 - deflation)

    # Per-league factor (never below 0.85) — alias-aware (#189-e)
    if league_id:
        factor = _league_deflation_factor(league_id)
        deflated *= max(factor, 0.85)

    return max(deflated, 0.05)


def _canonical_league(league_id: str | None) -> str | None:
    """Resolve a league_id to its canonical backend form before any corrections
    lookup (#185).

    Callers may pass frontend aliases (e.g. 'brazil-serie-a') or mixed case.
    The corrections/calibration DB is keyed by the canonical id
    (e.g. 'brasileirao-serie-a'), so a raw lookup silently misses and falls back
    to defaults — invisibly disabling SAFE and per-league thresholds for that
    league. Resolving the alias here closes that gap.
    """
    if not league_id:
        return None
    lid = league_id.strip().lower()
    try:
        from backend.config.leagues_config import LEAGUE_ID_ALIASES
        return LEAGUE_ID_ALIASES.get(lid, lid)
    except Exception:
        return lid
