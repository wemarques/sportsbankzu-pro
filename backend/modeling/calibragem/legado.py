# -*- coding: utf-8 -*-
"""CONGELADO — a pilha de deflacao anterior a camada aprendida.

PROIBIDO EDITAR. Este modulo existe por um motivo unico: ser a versao 0, para
que o deploy da camada nao mude nenhum numero publicado (spec, secao 6.1).
Cada celula que sai da versao 0 deixa de chama-lo. Quando nenhuma celula
referenciar mais a versao 0, este arquivo e APAGADO — o teste 1b guarda essa
transicao.

Unico chamador permitido: `calibragem.curva.aplicar_versao`.
"""

import logging

from backend.modeling.calibrator import calibrate_prob

# Mesmo nome de namespace usado historicamente por `ev_classification.py`
# (`sportsbankzu.ev_classification`) — preserva o grep de producao por
# GOLS-TRACE/CALIB-TRACE e a elevacao de nivel por namespace `sportsbankzu`
# feita em `backend/main.py` (#164/#204). `logging.getLogger` devolve o MESMO
# objeto logger para o mesmo nome, entao isto nao e uma logica nova — e o
# logger existente, so obtido a partir de outro modulo.
logger = logging.getLogger("sportsbankzu.ev_classification")


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


def calibrar_legado(raw: float, market: str, league_id: str, regime: str) -> "DetalheCalibracao":
    """Calibrate via Isotonic model then apply band+league deflation (#105, #113, #152, #165).

    #161: Under-2.5 extra penalty (#113) is now redundant when the lambda itself
    is already deflated at the poisson-matrix level (#156: `_DEFAULT_OU_DEFLATION`
    or per-league `lambda_multiplier`). Stacking both produced ~19% cumulative
    penalty for Under 2.5, zeroing EV on most books and suppressing gols picks.
    The #113 x0.90 now only applies if neither global default nor per-league
    OU deflation is active — i.e., only in the legacy no-deflation path.

    #165: O/U half-band when lambda is already deflated at the Poisson layer.
    #105 bands (10-25%) were calibrated with `_DEFAULT_OU_DEFLATION = 1.0`.
    #156 set the default to 0.90 without re-calibrating bands, creating a
    double-penalty: lambda x0.90 THEN full band. Mirrors #152 BTTS logic.
    Full band remains as fallback if #156 is ever reverted (ou_defl == 1.0).

    #216: devolve o DETALHE em vez de so o numero final. `_calibrate_and_deflate`
    segue existindo como fachada para quem so quer o float.
    """
    from backend.modeling.poisson_matrix import (
        _DEFAULT_OU_DEFLATION, _get_league_deflation,
    )
    # Import tardio: `DetalheCalibracao` continua definido em
    # `ev_classification.py` (nao foi movida — ver docstring do modulo) e
    # importa-la no topo criaria um ciclo com o import de volta que
    # `ev_classification.py` faz destas funcoes de deflacao.
    from backend.services.ev_classification import DetalheCalibracao
    calibrated = calibrate_prob(raw, market, league_id, regime)
    # BTTS: lambda already deflated per-league in poisson_matrix (btts_multiplier).
    # Applying full band deflation on top causes double-penalty (~64% -> ~44%).
    # #152: halve band deflation for BTTS to prevent excessive cumulative deflation.
    deflation_band = _band_deflation(calibrated)
    per_league_factor = _league_deflation_factor(league_id) if league_id else 1.0  # alias-aware (#189-e)
    ou_defl = 1.0
    if market.upper() == "BTTS":
        tipo_banda = "meia-btts"
        half_deflation = deflation_band / 2.0
        result = calibrated * (1.0 - half_deflation)
        # Per-league factor still applies
        if league_id:
            result *= max(per_league_factor, 0.85)
        result = max(result, 0.05)
    else:
        # #165-e: unconditional half-band for O/U markets. Product decision:
        # #105 bands were calibrated before Dixon-Coles, per-league calibration,
        # and xG blend. In production, 18/22 leagues have `lambda_multiplier: 1.0`
        # in the DB (no lambda-level deflation) so the #165-d gate was inert —
        # gols picks closed while BTTS kept its #152 half-band. Mirrors BTTS
        # treatment until Brier recalibration justifies re-tightening.
        # 1X2/DC/Corners/Cards remain on full band (legacy #105 path).
        is_ou_market = market.lower().startswith(("over ", "under "))
        if is_ou_market:
            tipo_banda = "meia"
            result = calibrated * (1.0 - deflation_band / 2.0)
            if league_id:
                result *= max(per_league_factor, 0.85)
            result = max(result, 0.05)
            ou_defl, _, _ = _get_league_deflation(league_id)
            logger.info(
                "[OU-HALFBAND] league=%s market=%s band=%.3f->%.3f ou_defl=%.2f",
                league_id or "-", market, deflation_band, deflation_band/2, ou_defl,
            )
        else:
            # Full band: 1X2, DC, Corners, Cards (legacy #105 path)
            tipo_banda = "inteira"
            result = apply_probability_deflation(calibrated, league_id)
    # Under 2.5 extra deflation (#113) — skipped when lambda-level OU deflation
    # is already active (#156/#161). The `_LEAGUE_DEFLATION` static dict only
    # covers serie-a/league-two; DB-calibrated leagues (lambda_multiplier from
    # calibration DB) apply at the lambda layer in poisson_matrix, so they
    # are covered indirectly by the `_DEFAULT_OU_DEFLATION < 1.0` gate below.
    # Kill-switch signal: if Lambda Error Medio > 1.0 in next audit, revisit.
    extra_under_applied = False
    if "under" in market.lower() and "2.5" in market:
        if _DEFAULT_OU_DEFLATION >= 1.0 and (_canonical_league(league_id) or league_id) not in _LEAGUE_DEFLATION:
            # Legacy path: no lambda-level deflation -> apply #113 safety penalty.
            result *= 0.90
            extra_under_applied = True
    # Hook 1: raw -> isotonico -> fatores de deflacao -> final.
    # #216: o hook cobria SO gols e BTTS. Cartoes, escanteios, 1X2 e Double
    # Chance passavam pelo mesmo caminho e nao deixavam rastro nenhum - e sao
    # justamente os que levam banda INTEIRA, ou seja, o corte maior. O prefixo
    # GOLS-TRACE e preservado para gols/BTTS porque o REGRAS_ATIVAS documenta o
    # grep por ele; as demais familias saem como CALIB-TRACE. Os dois carregam
    # `calib_iso=`, entao um unico grep por `calib_iso` pega todas as familias.
    _e_gols = market.lower().startswith(("over ", "under ")) or market.upper() == "BTTS"
    logger.info(
        "[%s] league=%s market=%s raw=%.4f calib_iso=%.4f "
        "band=%.2f tipo=%s per_league=%.2f default_ou=%.2f under25_extra=%s final=%.4f",
        "GOLS-TRACE" if _e_gols else "CALIB-TRACE",
        league_id or "-", market, raw, calibrated,
        deflation_band, tipo_banda, per_league_factor, _DEFAULT_OU_DEFLATION,
        extra_under_applied, result,
    )
    return DetalheCalibracao(
        raw=raw, iso=calibrated, banda=deflation_band, tipo_banda=tipo_banda,
        per_league=per_league_factor, ou_defl=ou_defl,
        under25_extra=extra_under_applied, final=result,
    )
