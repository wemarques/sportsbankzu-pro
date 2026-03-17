"""
Correlation Matrix & System Bets Eligibility (Layer 5)

Manages:
- Market correlation/redundancy detection within same game
- Eligibility rules for multiples and system bets
- Up to 2 selections per game with correlation control
- System bet structures (2de3, Trixie, Lucky 15)
- Break-even profitability filter
"""

import logging
from itertools import combinations
from typing import Dict, Any, List, Tuple, Optional, Set

from backend.models.market_output import MarketClassification, ReasonCode

logger = logging.getLogger("sportsbankzu.correlation")


# ─── Correlation Matrix ───
# Values: 0.0 = uncorrelated, 1.0 = identical/redundant
# Markets from the SAME game that are correlated

CORRELATION_MATRIX: Dict[frozenset, float] = {
    # HIGH correlation (>0.7) — BLOCK together
    frozenset(["1X2 Home", "DC 1X"]): 0.85,
    frozenset(["1X2 Away", "DC X2"]): 0.85,
    frozenset(["Under 3.5", "Under 4.5"]): 0.90,
    frozenset(["Over 2.5", "Over 3.5"]): 0.80,
    frozenset(["Over 3.5", "Over 4.5"]): 0.85,
    frozenset(["BTTS Yes", "Over 2.5"]): 0.55,   # moderate but allow

    # MODERATE correlation (0.3-0.7) — Allow with reduced stake
    frozenset(["1X2 Home", "Over 2.5"]): 0.35,
    frozenset(["1X2 Home", "BTTS Yes"]): 0.30,
    frozenset(["Over 2.5", "BTTS Yes"]): 0.50,
    frozenset(["Under 3.5", "DC 1X"]): 0.25,
    frozenset(["Under 4.5", "DC 1X"]): 0.20,

    # LOW correlation (<0.3) — Allow freely
    frozenset(["1X2 Home", "Corners Over 9.5"]): 0.10,
    frozenset(["1X2 Away", "Corners Over 9.5"]): 0.10,
    frozenset(["Over 2.5", "Corners Over 9.5"]): 0.15,
    frozenset(["BTTS Yes", "Corners Over 9.5"]): 0.15,
    frozenset(["Under 3.5", "Corners Over 9.5"]): 0.10,
}

# Explicitly redundant pairs — ALWAYS block together in multiples
REDUNDANT_PAIRS: Set[frozenset] = {
    frozenset(["1X2 Home", "DC 1X"]),       # DC 1X contains Home
    frozenset(["1X2 Away", "DC X2"]),        # DC X2 contains Away
    frozenset(["Under 3.5", "Under 4.5"]),   # nested
    frozenset(["Over 2.5", "Over 3.5"]),     # nested
    frozenset(["Over 3.5", "Over 4.5"]),     # nested
    frozenset(["1X2 Home", "1X2 Away"]),     # contradictory
    frozenset(["1X2 Home", "DC X2"]),        # contradictory
    frozenset(["BTTS Yes", "BTTS No"]),      # contradictory
    frozenset(["Over 2.5", "Under 2.5"]),    # contradictory
}

# Maximum correlation allowed for 2 picks in same game
MAX_CORRELATION_SAME_GAME = 0.60

# Maximum selections from same game in a multiple
MAX_SELECTIONS_PER_GAME = 2


def get_correlation(selection_a: str, selection_b: str) -> float:
    """Get correlation between two market selections.

    Returns correlation value (0-1).
    """
    # Normalize selections for lookup
    a = _normalize_selection(selection_a)
    b = _normalize_selection(selection_b)

    if a == b:
        return 1.0

    key = frozenset([a, b])

    if key in REDUNDANT_PAIRS:
        return 1.0

    return CORRELATION_MATRIX.get(key, 0.0)


def is_pair_allowed(selection_a: str, selection_b: str) -> Tuple[bool, float, str]:
    """Check if two selections from the same game can be combined.

    Returns (allowed, correlation, reason).
    """
    corr = get_correlation(selection_a, selection_b)

    a = _normalize_selection(selection_a)
    b = _normalize_selection(selection_b)

    if frozenset([a, b]) in REDUNDANT_PAIRS:
        return False, corr, "Redundant or contradictory markets"

    if corr > MAX_CORRELATION_SAME_GAME:
        return False, corr, f"Correlation too high ({corr:.2f} > {MAX_CORRELATION_SAME_GAME})"

    return True, corr, "OK"


def filter_eligible_for_multiples(
    markets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter markets that are eligible for inclusion in multiples.

    Criteria:
    - Classification: SAFE or NEUTRO_QUALIFICADO
    - Must have real odds
    - Must have sufficient data quality
    """
    eligible = []
    for m in markets:
        classification = m.get("classification", "NO_BET")
        if classification not in ("SAFE", "NEUTRO_QUALIFICADO"):
            continue
        if not m.get("odds_available", False):
            continue
        if m.get("data_quality_score", 0) < 0.3:
            continue
        eligible.append(m)
    return eligible


def select_picks_for_game(
    eligible_markets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Select up to MAX_SELECTIONS_PER_GAME picks from a single game.

    Rules:
    - Max 2 selections per game
    - Must not be redundant
    - Correlation must be below threshold
    - Prioritize by EV > classification > probability
    """
    if len(eligible_markets) <= 1:
        return eligible_markets

    # Sort by priority: SAFE first, then by EV desc
    def sort_key(m):
        cls_priority = {"SAFE": 2, "NEUTRO_QUALIFICADO": 1}.get(m.get("classification", ""), 0)
        ev = m.get("ev") or 0
        return (-cls_priority, -ev)

    sorted_markets = sorted(eligible_markets, key=sort_key)
    selected = [sorted_markets[0]]

    for m in sorted_markets[1:]:
        if len(selected) >= MAX_SELECTIONS_PER_GAME:
            break

        # Check correlation with all already selected
        can_add = True
        for s in selected:
            allowed, corr, reason = is_pair_allowed(
                m.get("selection", ""),
                s.get("selection", ""),
            )
            if not allowed:
                can_add = False
                break

        if can_add:
            selected.append(m)

    return selected


def build_multiples(
    all_game_picks: List[Dict[str, Any]],
    max_legs: int = 2,
) -> List[Dict[str, Any]]:
    """Build multiple bet combinations from selected picks across games.

    Applies:
    - Max 2 selections per game
    - Correlation check for same-game pairs
    - Exposure reduction for same-game pairs
    """
    multiples = []

    # Group by game
    by_game: Dict[str, List[Dict[str, Any]]] = {}
    for pick in all_game_picks:
        game_id = pick.get("match_id", "")
        by_game.setdefault(game_id, []).append(pick)

    # Build inter-game pairs
    game_ids = list(by_game.keys())
    for i, j in combinations(range(len(game_ids)), 2):
        picks_i = by_game[game_ids[i]]
        picks_j = by_game[game_ids[j]]

        for pi in picks_i:
            for pj in picks_j:
                odd_a = pi.get("book_odd") or pi.get("fair_odd") or 1.0
                odd_b = pj.get("book_odd") or pj.get("fair_odd") or 1.0
                combined_odd = odd_a * odd_b

                if combined_odd < 1.5:
                    continue

                multiples.append({
                    "type": "inter",
                    "legs": [pi, pj],
                    "combined_odd": round(combined_odd, 2),
                    "same_game": False,
                    "correlation": 0.0,
                    "exposure_haircut": 1.0,
                })

    # Build intra-game pairs (max 2 per game)
    for game_id, picks in by_game.items():
        if len(picks) < 2:
            continue

        for p1, p2 in combinations(picks, 2):
            allowed, corr, reason = is_pair_allowed(
                p1.get("selection", ""),
                p2.get("selection", ""),
            )
            if not allowed:
                continue

            odd_a = p1.get("book_odd") or p1.get("fair_odd") or 1.0
            odd_b = p2.get("book_odd") or p2.get("fair_odd") or 1.0
            combined_odd = odd_a * odd_b

            if combined_odd < 1.3:
                continue

            # Apply exposure haircut for same-game selections
            exposure_haircut = max(0.5, 1.0 - corr * 0.5)

            multiples.append({
                "type": "intra",
                "legs": [p1, p2],
                "combined_odd": round(combined_odd, 2),
                "same_game": True,
                "correlation": round(corr, 2),
                "exposure_haircut": round(exposure_haircut, 2),
                "risk_flags": [
                    f"same_game_correlation_{corr:.2f}",
                ],
            })

    # Sort: inter first, then intra; by combined odd desc
    multiples.sort(key=lambda x: (0 if x["type"] == "inter" else 1, -x["combined_odd"]))

    return multiples


def check_system_bet_viability(
    selections: List[Dict[str, Any]],
    system_type: str = "2de3",
    total_stake: float = 0.0,
) -> Dict[str, Any]:
    """Check if a system bet is viable (break-even filter).

    Returns viability info including expected return vs investment.
    """
    if system_type == "2de3" and len(selections) < 3:
        return {"viable": False, "reason": "Need at least 3 selections"}
    if system_type == "trixie" and len(selections) < 3:
        return {"viable": False, "reason": "Need at least 3 selections"}
    if system_type == "3de5" and len(selections) < 5:
        return {"viable": False, "reason": "Need at least 5 selections"}

    odds = [s.get("book_odd", 1.0) for s in selections]

    if system_type in ("2de3", "trixie"):
        # Calculate minimum return with 2 of 3 hits
        pairs = list(combinations(odds, 2))
        min_pair_return = min(o1 * o2 for o1, o2 in pairs)
        avg_pair_return = sum(o1 * o2 for o1, o2 in pairs) / len(pairs)

        lines = len(pairs) + (1 if system_type == "trixie" else 0)
        stake_per_line = total_stake / lines if lines > 0 and total_stake > 0 else 1.0

        break_even = total_stake > 0 and (min_pair_return * stake_per_line >= total_stake * 0.5)

        return {
            "viable": break_even,
            "reason": "" if break_even else f"Minimum 2-hit return too low ({min_pair_return:.2f}x)",
            "min_return_factor": round(min_pair_return, 2),
            "avg_return_factor": round(avg_pair_return, 2),
            "lines": lines,
        }

    # 3de5
    triples = list(combinations(odds, 3))
    min_triple = min(o1 * o2 * o3 for o1, o2, o3 in triples)
    lines = len(list(combinations(odds, 2)))
    stake_per_line = total_stake / lines if lines > 0 and total_stake > 0 else 1.0

    break_even = total_stake > 0 and (min_triple * stake_per_line >= total_stake * 0.3)

    return {
        "viable": break_even,
        "reason": "" if break_even else f"Minimum 3-hit return too low",
        "min_return_factor": round(min_triple, 2),
        "lines": lines,
    }


def _normalize_selection(selection: str) -> str:
    """Normalize selection name for correlation lookup."""
    s = selection.strip()

    # Map various formats to canonical names
    mappings = {
        "Home": "1X2 Home",
        "Draw": "1X2 Draw",
        "Away": "1X2 Away",
        "BTTS — SIM": "BTTS Yes",
        "BTTS — NÃO": "BTTS No",
        "BTTS Yes": "BTTS Yes",
        "BTTS No": "BTTS No",
    }

    if s in mappings:
        return mappings[s]

    # Handle "DC 1X (XXX/EMP)" format
    if s.startswith("DC 1X"):
        return "DC 1X"
    if s.startswith("DC X2"):
        return "DC X2"
    if s.startswith("DC 12"):
        return "DC 12"

    # Handle "Over X.Y gols" format
    if "Over" in s and "gols" in s:
        return s.replace(" gols", "")
    if "Under" in s and "gols" in s:
        return s.replace(" gols", "")

    # Handle corners
    if "Escanteios" in s:
        return s.replace("Escanteios ", "Corners ")

    return s
