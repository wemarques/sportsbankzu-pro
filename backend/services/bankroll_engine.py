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
        # Floor: se Kelly dá 0 ou negativo, usar mínimo 0.5% da banca
        if adjusted <= 0:
            adjusted = bankroll * VIAVEL_FLOOR_PCT
        # Haircuts
        haircut = calculate_haircut(market_output, reason_codes)
        adjusted *= haircut
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

    # 2. EV deflacionado
    ev = prob * book_odd - 1.0  # EV como decimal (-0.10 = -10%)

    # 3. Bloqueio por EV
    if ev < tier["ev_bloqueio"]:
        return {
            "stake": 0.0, "stake_pct": 0.0,
            "stake_reason": f"ev_{ev:.2%}_below_{tier['ev_bloqueio']:.0%}",
            "mode": "oportunidade", "desconto_ev": 0, "custo_por_100": 0,
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
