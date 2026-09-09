# -*- coding: utf-8 -*-
"""CONGELADO — a pilha de deflacao anterior a camada aprendida.

PROIBIDO EDITAR. Este modulo existe por um motivo unico: ser a versao 0, para
que o deploy da camada nao mude nenhum numero publicado (spec, secao 6.1).
Cada celula que sai da versao 0 deixa de chama-lo. Quando nenhuma celula
referenciar mais a versao 0, este arquivo e APAGADO — o teste 1b guarda essa
transicao.

Unico chamador permitido: `calibragem.curva.aplicar_versao`.

#248 (correcao pos-revisao): as primitivas de deflacao por banda/liga
(`_band_deflation`, `_league_deflation_factor`, `_canonical_league`,
`_LEAGUE_DEFLATION`, `_DEFLATION_KNOTS`, `apply_probability_deflation`) NAO
moram mais aqui — foram para `calibragem/bandas.py`, modulo normal, porque
tem chamadores permanentes fora da versao 0 (braco shadow #240, gate SAFE
#052/#185, threshold #055, `health.py`). Manter essas primitivas neste
arquivo tornava a promessa do paragrafo acima falsa: o modulo nunca ficaria
sem referencia. Este arquivo agora so contem `calibrar_legado`, que e o
unico codigo que de fato so serve a versao 0.
"""

import logging

from backend.modeling.calibrator import calibrate_prob
from backend.modeling.calibragem.bandas import (
    _band_deflation,
    _league_deflation_factor,
    _canonical_league,
    _LEAGUE_DEFLATION,
    apply_probability_deflation,
)

# Mesmo nome de namespace usado historicamente por `ev_classification.py`
# (`sportsbankzu.ev_classification`) — preserva o grep de producao por
# GOLS-TRACE/CALIB-TRACE e a elevacao de nivel por namespace `sportsbankzu`
# feita em `backend/main.py` (#164/#204). `logging.getLogger` devolve o MESMO
# objeto logger para o mesmo nome, entao isto nao e uma logica nova — e o
# logger existente, so obtido a partir de outro modulo.
logger = logging.getLogger("sportsbankzu.ev_classification")


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
    # `ev_classification.py` faz das primitivas de `bandas`.
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
