"""
Bankroll Engine (Layer 4)

Server-side bankroll management:
- Quarter Kelly as default
- Stake policies by classification
- Caps per bet/game/day/market
- Haircut adjustments for quality/uncertainty
- Only generates stakes when real odds are confirmed
"""

import logging
import math
import os
from typing import Dict, Any, List, Optional

from backend.models.market_output import MarketClassification, ReasonCode

logger = logging.getLogger("sportsbankzu.bankroll")


# ─── Kelly Configuration ───
KELLY_FRACTION = 0.25  # Quarter Kelly default

# ─── Stake Policy by Classification ───
STAKE_MULTIPLIER = {
    MarketClassification.SAFE: 1.0,
    MarketClassification.NEUTRO_QUALIFICADO: 0.60,
    MarketClassification.NEUTRO: 0.30,  # VIÁVEL — Quarter Kelly reduzido (#148)
    MarketClassification.NO_BET: 0.0,
}

# ─── Cap por classificação (#148) ───
MAX_STAKE_PCT_BY_CLASS = {
    MarketClassification.SAFE: 0.05,                  # 5%
    MarketClassification.NEUTRO_QUALIFICADO: 0.05,    # 5%
    MarketClassification.NEUTRO: 0.02,                # 2% — VIÁVEL mais conservador
    MarketClassification.NO_BET: 0.0,
}

# Floor mínimo para VIÁVEL quando Kelly retorna <= 0 mas prob >= 50% (#148)
# #171: configurable via env var. Default reduced 0.005 → 0.001 (0.5% → 0.1%)
# during P0 investigation. Forcing a stake when Kelly returns 0 is dangerous
# when model calibration is suspect. Set VIAVEL_FLOOR_PCT=0 to disable entirely.
VIAVEL_FLOOR_PCT = float(os.getenv("VIAVEL_FLOOR_PCT", "0.001"))
VIAVEL_MIN_PROB = 0.50

# ─── Caps ───
MAX_STAKE_PER_BET_PCT = 0.05      # 5% of bankroll max per single bet
MAX_STAKE_PER_GAME_PCT = 0.08     # 8% of bankroll max per game (all markets)
MAX_STAKE_PER_DAY_PCT = 0.30      # 30% of bankroll max per day
MAX_STAKE_PER_MARKET_PCT = 0.15   # 15% of bankroll max per market type

# ─── Haircut factors ───
HAIRCUT_LOW_QUALITY = 0.15        # -15% when data quality < 0.4
HAIRCUT_EARLY_SEASON = 0.20       # -20% for early season
HAIRCUT_LINEUP_UNCERTAIN = 0.10   # -10% when lineup not confirmed
HAIRCUT_INJURIES = 0.10           # -10% when relevant injuries
HAIRCUT_HIGH_CORRELATION = 0.15   # -15% when picks are correlated
HAIRCUT_VOLATILE_MARKET = 0.10    # -10% for volatile markets

# ─── ECE Haircut (#171 FASE 2C) ───
# When league ECE exceeds threshold, reduce Kelly stake proportionally.
# ECE = 0.08 means model is 8% overconfident → haircut reduces stake.
# Linear interpolation between threshold and ceiling.
ECE_HAIRCUT_THRESHOLD = float(os.getenv("ECE_HAIRCUT_THRESHOLD", "0.06"))
ECE_HAIRCUT_MAX = float(os.getenv("ECE_HAIRCUT_MAX", "0.25"))
ECE_HAIRCUT_CEILING = float(os.getenv("ECE_HAIRCUT_CEILING", "0.12"))

# ─── OddsVal Haircut (#171 FASE 2B) ───
# OddsVal < 0 means the model is less calibrated than the market's implied
# odds. Haircut scales linearly to MAX as OddsVal approaches FLOOR.
ODDSVAL_HAIRCUT_FLOOR = float(os.getenv("ODDSVAL_HAIRCUT_FLOOR", "-0.02"))
HAIRCUT_NEGATIVE_ODDSVAL_MAX = float(os.getenv("HAIRCUT_NEGATIVE_ODDSVAL_MAX", "0.30"))

# ─── Market Family Exposure Caps (#171 FASE 2D) ───
# Prevent any single market family from dominating daily exposure.
# Triggered the #171 incident: corners family stake/day went from 1.20%
# to 7.11% after #170-A (5.93× growth) — this cap keeps it ≤ 5%.
MAX_FAMILY_STAKE_DAY_PCT = {
    "corners": float(os.getenv("MAX_CORNER_STAKE_DAY_PCT", "0.05")),
    "cards":   float(os.getenv("MAX_CARDS_STAKE_DAY_PCT",  "0.05")),
    "goals":   float(os.getenv("MAX_GOALS_STAKE_DAY_PCT",  "0.10")),
    "1x2":     float(os.getenv("MAX_1X2_STAKE_DAY_PCT",    "0.10")),
}
DEFAULT_FAMILY_CAP_PCT = 0.10

# ─── Daily Loss Circuit Breaker (#171 FASE 2A) ───
# When today's cumulative loss exceeds this fraction of starting bankroll,
# block all new picks. Prevents bad-luck-streak spirals like the #171 incident.
DAILY_LOSS_BREAKER_PCT = float(os.getenv("DAILY_LOSS_BREAKER_PCT", "0.15"))

# ─── Modo Oportunidade (#149) ───
OPORTUNIDADE_TIERS = {
    MarketClassification.SAFE: {
        "stake_base_pct": 0.03,
        "cap_max_pct": 0.05,
        "ev_bloqueio": -0.05,
    },
    MarketClassification.NEUTRO_QUALIFICADO: {
        "stake_base_pct": 0.02,
        "cap_max_pct": 0.04,
        "ev_bloqueio": -0.10,
    },
    MarketClassification.NEUTRO: {
        "stake_base_pct": 0.01,
        "cap_max_pct": 0.02,
        "ev_bloqueio": -0.15,
    },
    MarketClassification.NO_BET: {
        "stake_base_pct": 0.00,
        "cap_max_pct": 0.00,
        "ev_bloqueio": 999,
    },
}

OPORT_BONUS_FATOR = 0.3     # multiplicador excesso confiança
OPORT_BONUS_MAX = 0.02      # teto bônus +2%
OPORT_DESCONTO_PISO = 0.50  # mínimo 50% do stake quando EV negativo


def kelly_stake(
    probability: float,
    odd: float,
    bankroll: float,
    kelly_fraction: float = KELLY_FRACTION,
) -> float:
    """Calculate Kelly stake.

    Args:
        probability: True win probability (0-1)
        odd: Decimal odd
        bankroll: Total bankroll
        kelly_fraction: Kelly multiplier (0.25 = quarter Kelly)

    Returns:
        Recommended stake in currency units
    """
    if odd <= 1.0 or probability <= 0 or probability >= 1.0:
        return 0.0

    b = odd - 1.0
    q = 1.0 - probability
    f = (probability * b - q) / b

    if f <= 0:
        return 0.0

    stake = bankroll * f * kelly_fraction
    return max(0, stake)


def ece_haircut_factor(ece: Optional[float]) -> float:
    """#171 FASE 2C: ECE-based haircut (0.75-1.0).

    ECE ≤ THRESHOLD → 1.0 (no haircut).
    ECE ≥ CEILING → 1.0 - ECE_HAIRCUT_MAX (max reduction).
    Otherwise: linear interpolation.
    None → 1.0 (neutro fallback when calibration data isn't propagated).
    """
    if ece is None or ece <= ECE_HAIRCUT_THRESHOLD:
        return 1.0
    if ece >= ECE_HAIRCUT_CEILING:
        return 1.0 - ECE_HAIRCUT_MAX
    span = ECE_HAIRCUT_CEILING - ECE_HAIRCUT_THRESHOLD
    if span <= 0:
        return 1.0 - ECE_HAIRCUT_MAX
    ratio = (ece - ECE_HAIRCUT_THRESHOLD) / span
    return 1.0 - (ratio * ECE_HAIRCUT_MAX)


def oddsval_haircut_factor(odds_val: Optional[float]) -> float:
    """#171 FASE 2B: OddsVal-based haircut (0.70-1.0).

    OddsVal ≥ 0 → 1.0 (model adds value vs market).
    OddsVal ≤ FLOOR → 1.0 - HAIRCUT_NEGATIVE_ODDSVAL_MAX.
    Otherwise: linear interpolation.
    None → 1.0 (neutro fallback).
    """
    if odds_val is None or odds_val >= 0:
        return 1.0
    if odds_val <= ODDSVAL_HAIRCUT_FLOOR:
        return 1.0 - HAIRCUT_NEGATIVE_ODDSVAL_MAX
    if ODDSVAL_HAIRCUT_FLOOR == 0:
        return 1.0
    ratio = odds_val / ODDSVAL_HAIRCUT_FLOOR  # both negative → positive ratio in [0,1]
    return 1.0 - (ratio * HAIRCUT_NEGATIVE_ODDSVAL_MAX)


def calculate_haircut(
    market_output: Dict[str, Any],
    reason_codes: List[str],
) -> float:
    """Calculate total haircut multiplier (0-1, where 1 = no haircut).

    Multiple haircuts stack multiplicatively.
    """
    multiplier = 1.0

    quality = market_output.get("data_quality_score", 1.0)
    if quality < 0.4:
        multiplier *= (1.0 - HAIRCUT_LOW_QUALITY)

    if "EARLY_SEASON_FALLBACK" in reason_codes:
        multiplier *= (1.0 - HAIRCUT_EARLY_SEASON)

    if "LINEUP_UNCERTAINTY" in reason_codes:
        multiplier *= (1.0 - HAIRCUT_LINEUP_UNCERTAIN)

    if "HIGH_MARKET_CORRELATION" in reason_codes:
        multiplier *= (1.0 - HAIRCUT_HIGH_CORRELATION)

    if "VOLATILE_MARKET" in reason_codes:
        multiplier *= (1.0 - HAIRCUT_VOLATILE_MARKET)

    return max(0.0, multiplier)


def compute_stake(
    market_output: Dict[str, Any],
    bankroll: float,
    kelly_fraction: float = KELLY_FRACTION,
) -> Dict[str, Any]:
    """Compute stake for a single market output.

    Returns stake info dict. Returns stake=0 if odds not available
    or classification doesn't warrant a stake.
    """
    classification = market_output.get("classification", "NO_BET")
    odds_available = market_output.get("odds_available", False)
    book_odd = market_output.get("book_odd")
    prob = market_output.get("calibrated_probability") or market_output.get("raw_probability")
    reason_codes = market_output.get("reason_codes", [])

    # No stake without real odds
    if not odds_available or not book_odd or book_odd <= 1.0:
        return {
            "stake": 0.0,
            "stake_reason": "no_real_odds",
            "kelly_raw": 0.0,
            "haircut": 1.0,
        }

    # #189-e: gate por familia — cartoes informativo, escanteios so extremas
    _allowed, _fam = family_stake_allowed(_gate_market_label(market_output))
    if not _allowed:
        return {
            "stake": 0.0,
            "stake_reason": f"family_gate_{_fam}",
            "kelly_raw": 0.0,
            "haircut": 1.0,
        }

    # No stake for NO_BET or plain NEUTRO
    try:
        cls = MarketClassification(classification)
    except ValueError:
        cls = MarketClassification.NO_BET

    multiplier = STAKE_MULTIPLIER.get(cls, 0.0)
    if multiplier <= 0:
        return {
            "stake": 0.0,
            "stake_reason": f"classification_{classification}",
            "kelly_raw": 0.0,
            "haircut": 1.0,
        }

    if not prob or prob <= 0:
        return {
            "stake": 0.0,
            "stake_reason": "no_probability",
            "kelly_raw": 0.0,
            "haircut": 1.0,
        }

    # #171 FASE 2: ECE + OddsVal haircuts. league_ece / league_odds_val are
    # not yet populated by the upstream pipeline; both functions return 1.0
    # when None (neutro fallback). Once propagation is wired, these gates
    # automatically activate for high-ECE / negative-OddsVal leagues.
    ece_factor = ece_haircut_factor(market_output.get("league_ece"))
    oddsval_factor = oddsval_haircut_factor(market_output.get("league_odds_val"))

    # ─── Branch VIÁVEL (#148) ───
    if cls == MarketClassification.NEUTRO:
        if prob < VIAVEL_MIN_PROB:
            return {
                "stake": 0.0,
                "stake_reason": "viavel_prob_below_50",
                "kelly_raw": 0.0,
                "haircut": 1.0,
            }
        raw_kelly = kelly_stake(prob, book_odd, bankroll, kelly_fraction)
        adjusted = raw_kelly * multiplier
        # #189-d: Floor condicionado a EV >= 0. Kelly <= 0 ocorre exatamente
        # quando EV < 0 na odd atual — apostar o floor nesse caso é apostar
        # com valor esperado negativo (auditoria 2026-08-29: NEUTRO 52% @
        # odd 1.51 recebia stake com EV -21%). Em vez de stake, o pick vira
        # ordem-limite: "aguarde odd >= min_odd" (min_odd = fair = 1/prob).
        ev_now = prob * book_odd - 1.0
        if adjusted <= 0:
            if ev_now >= 0:
                # EV == 0 (odd exatamente na fair): floor mantido (#148)
                adjusted = bankroll * VIAVEL_FLOOR_PCT
            else:
                return {
                    "stake": 0.0,
                    "stake_reason": "await_min_odd",
                    "kelly_raw": 0.0,
                    "haircut": 1.0,
                    "min_odd": round(1.0 / prob, 2),
                    "ev": round(ev_now, 4),
                }
        # Haircuts
        haircut = calculate_haircut(market_output, reason_codes)
        adjusted *= haircut
        adjusted *= ece_factor       # #171 FASE 2C
        adjusted *= oddsval_factor   # #171 FASE 2B
        # Cap 2%
        cap_pct = MAX_STAKE_PCT_BY_CLASS[cls]
        max_cap = bankroll * cap_pct
        capped = min(adjusted, max_cap)
        final_stake = round(max(0, capped), 2)
        pct = final_stake / bankroll if bankroll > 0 else 0.0
        return {
            "stake": final_stake,
            "stake_reason": "quarter_kelly_viavel",
            "kelly_raw": round(raw_kelly, 2),
            "haircut": round(haircut, 3),
            "ece_factor": round(ece_factor, 3),         # #171 FASE 2C
            "oddsval_factor": round(oddsval_factor, 3), # #171 FASE 2B
            "capped": capped < adjusted,
            "classification_multiplier": multiplier,
            "pct": round(pct, 4),
        }

    # Calculate Kelly
    raw_kelly = kelly_stake(prob, book_odd, bankroll, kelly_fraction)

    # Apply classification multiplier
    adjusted = raw_kelly * multiplier

    # Apply haircut
    haircut = calculate_haircut(market_output, reason_codes)
    adjusted *= haircut
    adjusted *= ece_factor       # #171 FASE 2C
    adjusted *= oddsval_factor   # #171 FASE 2B

    # Apply per-bet cap (por classificação #148, fallback MAX_STAKE_PER_BET_PCT)
    cap_pct = MAX_STAKE_PCT_BY_CLASS.get(cls, MAX_STAKE_PER_BET_PCT)
    max_per_bet = bankroll * cap_pct
    capped = min(adjusted, max_per_bet)

    # Round to 2 decimal places
    final_stake = round(max(0, capped), 2)

    return {
        "stake": final_stake,
        "stake_reason": "kelly_calculated",
        "kelly_raw": round(raw_kelly, 2),
        "haircut": round(haircut, 3),
        "ece_factor": round(ece_factor, 3),         # #171 FASE 2C
        "oddsval_factor": round(oddsval_factor, 3), # #171 FASE 2B
        "capped": capped < adjusted,
        "classification_multiplier": multiplier,
    }


def compute_stake_oportunidade(
    market_output: Dict[str, Any],
    bankroll: float,
    market_threshold: float = 0.50,
) -> Dict[str, Any]:
    """Compute stake no modo Oportunidade (#149).

    Stake baseado no tier da classificação, com desconto por EV negativo
    e bônus por excesso de confiança acima do threshold.
    """
    classification = market_output.get("classification", "NO_BET")
    book_odd = market_output.get("book_odd")
    prob = market_output.get("calibrated_probability") or market_output.get("raw_probability")

    try:
        cls = MarketClassification(classification)
    except ValueError:
        cls = MarketClassification.NO_BET

    tier = OPORTUNIDADE_TIERS.get(cls, OPORTUNIDADE_TIERS[MarketClassification.NO_BET])

    # 1. Piso absoluto 50%
    if not prob or prob < 0.50:
        return {
            "stake": 0.0, "stake_pct": 0.0, "stake_reason": "prob_below_50",
            "mode": "oportunidade", "desconto_ev": 1.0, "custo_por_100": 0,
        }

    # 1b. Sem odds reais → não calcular stake (#149 fix)
    if not book_odd or book_odd <= 1.0:
        return {
            "stake": 0.0, "stake_pct": 0.0, "stake_reason": "no_real_odds",
            "mode": "oportunidade", "desconto_ev": 1.0, "custo_por_100": 0,
        }

    # #189-e: gate por familia
    _allowed, _fam = family_stake_allowed(_gate_market_label(market_output))
    if not _allowed:
        return {
            "stake": 0.0, "stake_pct": 0.0,
            "stake_reason": f"family_gate_{_fam}",
            "mode": "oportunidade", "desconto_ev": 1.0, "custo_por_100": 0,
        }

    # 2. EV deflacionado
    ev = prob * book_odd - 1.0  # EV como decimal (-0.10 = -10%)

    # 3. #189-d: EV negativo → sem stake em NENHUM modo. O antigo "desconto
    # por EV negativo" apostava com valor esperado negativo (custo/R$100
    # exibido não muda o sinal do EV). O pick vira ordem-limite: aguarde
    # a odd atingir a fair (1/prob). Substitui também o ev_bloqueio
    # negativo dos tiers para este caso.
    if ev < 0:
        return {
            "stake": 0.0, "stake_pct": 0.0,
            "stake_reason": "await_min_odd",
            "mode": "oportunidade", "desconto_ev": 0, "custo_por_100": 0,
            "min_odd": round(1.0 / prob, 2),
            "ev": round(ev, 4),
        }

    # 4. Stake base
    stake_pct = tier["stake_base_pct"]

    # 5. Bônus excesso confiança (saturado)
    excesso = max(0, prob - market_threshold)
    bonus = min(excesso * OPORT_BONUS_FATOR, OPORT_BONUS_MAX)
    stake_pct += bonus

    # 6. Desconto EV negativo
    desconto = 1.0
    if ev < 0:
        desconto = max(OPORT_DESCONTO_PISO, 1.0 + ev)
        stake_pct *= desconto

    # 7. Cap
    stake_pct = min(stake_pct, tier["cap_max_pct"])

    # 8. Valor final
    stake_valor = round(bankroll * stake_pct, 2)
    custo_por_100 = round((-ev) * 100, 2) if ev < 0 else 0

    return {
        "stake": stake_valor,
        "stake_pct": round(stake_pct, 4),
        "stake_reason": "oportunidade",
        "mode": "oportunidade",
        "ev": round(ev, 4),
        "desconto_ev": round(desconto, 2),
        "custo_por_100": custo_por_100,
        "cap_aplicado": stake_pct >= tier["cap_max_pct"],
    }


def apply_game_cap(
    stakes: List[Dict[str, Any]],
    bankroll: float,
) -> List[Dict[str, Any]]:
    """Apply per-game cap: total stake across all markets in same game <= 8% bankroll."""
    max_game = bankroll * MAX_STAKE_PER_GAME_PCT
    total = sum(s.get("stake", 0) for s in stakes)

    if total <= max_game:
        return stakes

    # Scale down proportionally
    scale = max_game / total
    for s in stakes:
        s["stake"] = round(s["stake"] * scale, 2)
        s["game_capped"] = True

    return stakes


def apply_daily_cap(
    all_stakes: List[Dict[str, Any]],
    bankroll: float,
) -> List[Dict[str, Any]]:
    """Apply daily cap: total stakes across all games <= 30% bankroll."""
    max_daily = bankroll * MAX_STAKE_PER_DAY_PCT
    total = sum(s.get("stake", 0) for s in all_stakes)

    if total <= max_daily:
        return all_stakes

    scale = max_daily / total
    for s in all_stakes:
        s["stake"] = round(s["stake"] * scale, 2)
        s["daily_capped"] = True

    return all_stakes


# ─── #189-e: Gate de stake por FAMÍLIA de mercado ───
# Base: decomposição de 5.505 picks auditados (29-30/08/2026):
#   gols/BTTS  → Δ Brier vs mercado POSITIVO em toda liga onde opera
#   cartões    → Δ ≈ -0,2% uniforme no mundo todo (modelo = consenso - vig)
#   escanteios → edge só em linhas extremas (Over >= 10.5 / Under <= 9.5)
# Cartões ficam INFORMATIVOS (pick visível, stake 0) até a re-medição
# pós #189-b + fator de árbitro (janela de 60 dias). Vale para TODAS as
# ligas — o Brasileirão A permanece ativo sob esta mesma política.
FAMILY_STAKE_POLICY = {
    "goals": "full",
    "1x2": "full",
    "corners": "extreme_lines",
    "cards": "none",
}
CORNER_EXTREME_OVER_MIN = 10.5
CORNER_EXTREME_UNDER_MAX = 9.5


def family_stake_allowed(market_label: str) -> "tuple[bool, str]":
    """(permitido, familia) para o rótulo de mercado dado (#189-e)."""
    import re
    fam = _market_family(market_label)
    policy = FAMILY_STAKE_POLICY.get(fam, "full")
    if policy == "full":
        return True, fam
    if policy == "none":
        return False, fam
    # extreme_lines (escanteios)
    m = re.search(r"(over|under)\s*(\d+\.?\d*)", (market_label or "").lower())
    if not m:
        return False, fam
    line = float(m.group(2))
    if m.group(1) == "over" and line >= CORNER_EXTREME_OVER_MIN:
        return True, fam
    if m.group(1) == "under" and line <= CORNER_EXTREME_UNDER_MAX:
        return True, fam
    return False, fam


def _gate_market_label(market_output: Dict[str, Any]) -> str:
    return (market_output.get("market_type") or market_output.get("selection")
            or market_output.get("mercado") or market_output.get("display_label") or "")


def _market_family(market_type: str) -> str:
    """#171 FASE 2D: classify market_type into a family for exposure capping."""
    mt = (market_type or "").lower()
    if "corner" in mt or "escante" in mt:
        return "corners"
    if "card" in mt or "cart" in mt or "booking" in mt:
        return "cards"
    if any(k in mt for k in ("over", "under", "btts", "gol", "ambas")):
        return "goals"
    if "1x2" in mt or "result" in mt or "double" in mt or "dc" in mt or "winner" in mt:
        return "1x2"
    return mt or "unknown"


def market_family(market_type: str) -> str:
    """#180: public wrapper of _market_family for cross-module reuse."""
    return _market_family(market_type)


def apply_family_cap(
    all_stakes: List[Dict[str, Any]],
    bankroll: float,
) -> List[Dict[str, Any]]:
    """#171 FASE 2D: per-market-family daily exposure cap.

    Groups stakes by family (corners / cards / goals / 1x2). If a family's
    total exceeds its daily cap, scales every stake in that family
    proportionally. MUST be called BEFORE apply_daily_cap so the daily
    30% budget reflects already-capped family totals.

    Mitigates the #171 trigger pattern: a single market family (corners)
    consuming disproportionate exposure after a hyperparameter shift.
    """
    from collections import defaultdict

    family_totals: dict = defaultdict(float)
    family_items: dict = defaultdict(list)

    for s in all_stakes:
        family = _market_family(s.get("market_type", "unknown"))
        family_totals[family] += s.get("stake", 0)
        family_items[family].append(s)

    for family, total in family_totals.items():
        cap_pct = MAX_FAMILY_STAKE_DAY_PCT.get(family, DEFAULT_FAMILY_CAP_PCT)
        max_family = bankroll * cap_pct
        if total > max_family and total > 0:
            scale = max_family / total
            for s in family_items[family]:
                s["stake"] = round(s["stake"] * scale, 2)
                s["family_capped"] = True
                s["family_cap_scale"] = round(scale, 3)
                s["family"] = family
            logger.warning(
                "[bankroll] Family '%s' capped: %.2f -> %.2f (scale=%.3f, cap=%.0f%%)",
                family, total, max_family, scale, cap_pct * 100,
            )

    return all_stakes


def check_daily_loss_breaker(
    daily_pnl: float,
    bankroll: float,
) -> bool:
    """#171 FASE 2A: daily-loss circuit breaker.

    Returns True if today's accumulated loss exceeds the configured
    threshold of starting bankroll. Caller (frontend / decision route)
    must respect the signal — backend doesn't know real bankroll state,
    so this function is pure logic on values supplied by the caller.

    Args:
        daily_pnl: Today's P&L (negative = loss).
        bankroll: Starting bankroll for the day.

    Returns:
        True if breaker tripped (block new bets); False otherwise.
    """
    if bankroll <= 0:
        return True  # defensive: zero/negative bankroll = block
    loss_pct = abs(min(0.0, daily_pnl)) / bankroll
    if loss_pct >= DAILY_LOSS_BREAKER_PCT:
        logger.warning(
            "[bankroll] CIRCUIT BREAKER tripped: daily loss %.1f%% >= %.0f%% threshold",
            loss_pct * 100, DAILY_LOSS_BREAKER_PCT * 100,
        )
        return True
    return False
