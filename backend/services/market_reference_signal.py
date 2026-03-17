"""
Market Reference Signal — structural governance layer per league + market.

Computes a structural quality signal (SAFE / NEUTRO / RESTRITO) for each
market type in a given league, independent of individual pick classification.
This signal acts as a ceiling on pick classification (e.g., a RESTRITO market
cannot produce a SAFE pick).

Sources:
- 1X2 / Double Chance: league classification from ML pipeline (ML_ACTIVE / POISSON / DEACTIVATED)
- Over/Under / BTTS: market model metadata (beats_poisson flag)
- Corners: NEUTRO by default (no dedicated validation pipeline yet)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sportsbankzu.market_reference_signal")

# Valid signal values
SAFE = "SAFE"
NEUTRO = "NEUTRO"
RESTRITO = "RESTRITO"

# Market type normalization mapping
_MARKET_CATEGORY_MAP = {
    "1X2": "1X2",
    "Over/Under": "Over/Under",
    "BTTS": "BTTS",
    "Double Chance": "Double Chance",
    "Corners": "Corners",
}


def _get_1x2_signal(league_id: str) -> Dict[str, str]:
    """Compute market_reference_signal for 1X2 based on ML pipeline status.

    Returns dict with signal, reason, source.
    """
    try:
        from backend.ml.predictor import _load_models, is_ml_available

        if is_ml_available(league_id):
            return {
                "signal": SAFE,
                "reason": "ML ensemble active (Brier < 0.60)",
                "source": "league_classification",
            }

        # ML not available — check why
        bundle = _load_models(league_id)
        if bundle is None:
            return {
                "signal": RESTRITO,
                "reason": "No ML model available for league",
                "source": "league_classification",
            }

        meta = bundle.get("metadata", {})
        if meta.get("ml_deactivated"):
            return {
                "signal": RESTRITO,
                "reason": "ML explicitly deactivated (Brier >= 0.63)",
                "source": "league_classification",
            }

        val_brier = meta.get("validation_brier")
        if val_brier is not None and val_brier >= 0.60:
            return {
                "signal": NEUTRO,
                "reason": f"Poisson fallback (Brier={val_brier:.4f} >= 0.60)",
                "source": "league_classification",
            }

        # Market efficiency gating
        return {
            "signal": NEUTRO,
            "reason": "ML suppressed (market efficiency gating)",
            "source": "league_classification",
        }

    except Exception as e:
        logger.debug(f"[MRS] Could not determine 1X2 signal for {league_id}: {e}")
        return {
            "signal": NEUTRO,
            "reason": "Could not determine ML status",
            "source": "fallback_default",
        }


def _get_market_model_signal(league_id: str, market_key: str) -> Dict[str, str]:
    """Compute market_reference_signal for Over/Under or BTTS markets.

    Uses market_models metadata to check beats_poisson flag.
    """
    try:
        from backend.ml.market_models import predict_market

        # predict_market returns None if model doesn't beat Poisson
        # We don't need actual features — just check if model exists and beats Poisson
        # by inspecting model metadata directly
        from backend.ml.market_models import _MODELS_DIR
        import json
        from pathlib import Path

        # Check multiple locations
        candidates = [
            _MODELS_DIR / league_id,
            Path("/tmp/.ml_models") / league_id,
        ]

        for model_dir in candidates:
            summary_path = model_dir / "market_models_summary.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    summary = json.load(f)
                markets = summary.get("markets", {})
                if market_key in markets:
                    info = markets[market_key]
                    if info.get("status") == "success" and info.get("beats_poisson"):
                        return {
                            "signal": SAFE,
                            "reason": f"Dedicated ML model beats Poisson ({market_key})",
                            "source": "market_model",
                        }
                    elif info.get("status") == "success":
                        return {
                            "signal": NEUTRO,
                            "reason": f"ML model exists but does not beat Poisson ({market_key})",
                            "source": "market_model",
                        }
                    elif info.get("status") == "error":
                        return {
                            "signal": RESTRITO,
                            "reason": f"Market model training failed ({market_key})",
                            "source": "market_model",
                        }

        # No market model found — Poisson fallback
        return {
            "signal": NEUTRO,
            "reason": f"No dedicated market model — Poisson fallback ({market_key})",
            "source": "fallback_default",
        }

    except Exception as e:
        logger.debug(f"[MRS] Could not determine {market_key} signal for {league_id}: {e}")
        return {
            "signal": NEUTRO,
            "reason": f"Could not determine market model status ({market_key})",
            "source": "fallback_default",
        }


def get_market_reference_signal(
    league_id: str,
    market_type: str,
) -> Dict[str, str]:
    """Compute the market_reference_signal for a given league + market type.

    Args:
        league_id: League identifier (e.g., "1625", "4759")
        market_type: Market category ("1X2", "Over/Under", "BTTS", "Double Chance", "Corners")

    Returns:
        Dict with keys: signal, reason, source
    """
    category = _normalize_market_category(market_type)

    if category == "1X2":
        return _get_1x2_signal(league_id)

    if category == "Double Chance":
        # Double Chance inherits from 1X2
        result = _get_1x2_signal(league_id)
        result["reason"] = f"Herda do 1X2: {result['reason']}"
        return result

    if category == "Over/Under":
        # Check over25 as representative for Over/Under
        return _get_market_model_signal(league_id, "over25")

    if category == "BTTS":
        return _get_market_model_signal(league_id, "btts")

    if category == "Corners":
        # Corners: NEUTRO by default, no dedicated validation pipeline
        return {
            "signal": NEUTRO,
            "reason": "Corners sem pipeline de validacao dedicado (v1)",
            "source": "fallback_default",
        }

    # Unknown market type
    return {
        "signal": NEUTRO,
        "reason": f"Unknown market type: {market_type}",
        "source": "fallback_default",
    }


def _normalize_market_category(market_type: str) -> str:
    """Normalize market type string to category."""
    if market_type in _MARKET_CATEGORY_MAP:
        return market_type

    mt = market_type.lower()
    if "corner" in mt or "escanteio" in mt:
        return "Corners"
    if "1x2" in mt or "home" in mt or "draw" in mt or "away" in mt:
        return "1X2"
    if "over" in mt or "under" in mt:
        return "Over/Under"
    if "btts" in mt:
        return "BTTS"
    if "double" in mt or "dc " in mt.lower():
        return "Double Chance"
    return "1X2"


def apply_signal_capping(
    mercados: List[Dict[str, Any]],
    league_id: str,
) -> List[Dict[str, Any]]:
    """Apply market_reference_signal capping to a list of mercados.

    For each mercado:
    1. Computes the market_reference_signal
    2. Stores rawClassification (original status)
    3. Applies capping: signal limits the ceiling of the pick status
    4. Sets finalClassification and wasCappedByMarketSignal

    Returns the same list, mutated in-place with new fields.
    """
    # Cache signals per market category to avoid repeated lookups
    signal_cache: Dict[str, Dict[str, str]] = {}

    for mercado in mercados:
        market_name = mercado.get("mercado", "")
        category = _detect_market_category(market_name)

        # Get or compute signal
        if category not in signal_cache:
            signal_cache[category] = get_market_reference_signal(league_id, category)
        sig = signal_cache[category]

        raw_status = mercado.get("status", "NEUTRO")
        # Normalize SAFE* to SAFE for comparison
        raw_normalized = "SAFE" if raw_status.startswith("SAFE") else raw_status

        # Store raw classification
        mercado["rawClassification"] = raw_status
        mercado["marketReferenceSignal"] = sig["signal"]
        mercado["marketReferenceReason"] = sig["reason"]
        mercado["marketReferenceSource"] = sig["source"]

        # Apply capping
        final_status = raw_status
        was_capped = False

        if sig["signal"] == RESTRITO:
            # RESTRITO: block SAFE, allow NEUTRO at most
            if raw_normalized == "SAFE":
                final_status = "NEUTRO"
                was_capped = True
        elif sig["signal"] == NEUTRO:
            # NEUTRO: cap at NEUTRO
            if raw_normalized == "SAFE":
                final_status = "NEUTRO"
                was_capped = True

        # SAFE signal: no capping needed

        mercado["status"] = final_status
        mercado["finalClassification"] = final_status
        mercado["wasCappedByMarketSignal"] = was_capped

        if was_capped:
            logger.info(
                f"[MRS] Capped {market_name} in {league_id}: "
                f"{raw_status} -> {final_status} (signal={sig['signal']})"
            )

    return mercados


def _detect_market_category(market_name: str) -> str:
    """Detect market category from a mercado name string."""
    name = market_name.lower()
    if "over" in name or "under" in name:
        if "escanteio" in name or "corner" in name:
            return "Corners"
        return "Over/Under"
    if "btts" in name:
        return "BTTS"
    if "dc " in name or "double" in name:
        return "Double Chance"
    if "1x2" in name:
        return "1X2"
    # Default to 1X2 for unrecognized
    return "1X2"
