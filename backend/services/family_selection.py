"""#180 — Family pick selection.

After classify_market() runs on every pick, group by market family
(reusing #171's _market_family logic) and mark the strongest pick
per family as family_winner=True. Other picks keep all data but
display can hide them by default.
"""
import os
from typing import List, Dict
from backend.services.bankroll_engine import market_family


_CLASSIFICATION_RANK = {
    "SAFE": 4,
    "NEUTRO_QUALIFICADO": 3,
    "NEUTRO": 2,
    "INFORMATIVO": 1,
    "NO_BET": 0,
}


def _flag_enabled() -> bool:
    return os.getenv("ENABLE_FAMILY_SELECTION_180", "true").lower() == "true"


def _band_preference(prob) -> int:
    """After #179 promotes, 60-70% will be the sweet band.
    Until then, 50-60% is sub-confident (-12.7pp); 80%+ is over-confident (+7.2pp).
    Rank: 60-70% > 50-60% ≈ 70-80% > 80%+ > <50%.
    """
    if prob is None:
        return 0
    try:
        p = float(prob)
    except (TypeError, ValueError):
        return 0
    if 0.60 <= p < 0.70:
        return 3
    if 0.50 <= p < 0.60:
        return 2
    if 0.70 <= p < 0.80:
        return 2
    if p >= 0.80:
        return 1
    return 0


def _pick_score(p: Dict) -> tuple:
    """Higher tuple = better. Order: classification, EV, delta_brier, band."""
    cls = p.get("classification") or p.get("status") or ""
    cls_rank = _CLASSIFICATION_RANK.get(str(cls).upper(), 0)
    ev = p.get("ev_pct") if p.get("ev_pct") is not None else p.get("ev")
    try:
        ev = float(ev) if ev is not None else -999.0
    except (TypeError, ValueError):
        ev = -999.0
    delta = p.get("delta_brier") or 0.0
    try:
        delta = float(delta)
    except (TypeError, ValueError):
        delta = 0.0
    prob = p.get("prob_central")
    if prob is None:
        prob_min = p.get("prob_min")
        prob_max = p.get("prob_max")
        if prob_min is not None and prob_max is not None:
            try:
                pmin = float(prob_min)
                pmax = float(prob_max)
                avg = (pmin + pmax) / 2.0
                prob = avg / 100.0 if max(pmin, pmax) > 1 else avg
            except (TypeError, ValueError):
                prob = None
    band_score = _band_preference(prob)
    return (cls_rank, ev, delta, band_score)


def select_family_winners(picks: List[Dict]) -> List[Dict]:
    """Annotate each pick with `family` and `family_winner` (bool).

    When ENABLE_FAMILY_SELECTION_180=false: every pick gets family_winner=True
    (effectively disables the feature). family is still annotated for telemetry.

    Mutates list in place AND returns it (fluent style).
    """
    by_family: Dict[str, List[Dict]] = {}
    for p in picks:
        market = p.get("mercado") or p.get("market") or p.get("market_type") or ""
        fam = market_family(market)
        p["family"] = fam
        by_family.setdefault(fam, []).append(p)

    if not _flag_enabled():
        for p in picks:
            p["family_winner"] = True
        return picks

    for fam, fam_picks in by_family.items():
        if fam == "unknown" or len(fam_picks) == 1:
            for p in fam_picks:
                p["family_winner"] = True
            continue
        fam_picks.sort(key=_pick_score, reverse=True)
        for i, p in enumerate(fam_picks):
            p["family_winner"] = (i == 0)

    return picks
