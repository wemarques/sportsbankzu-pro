"""
Serviço de combinadas (duplas) intra e inter jogos.

- Intra-game: dois mercados do MESMO jogo combinados (e.g. BTTS + Over 2.5)
- Inter-game: mercados de JOGOS DIFERENTES combinados (qualquer par SAFE/NEUTRO_Q)

Updated #119: eligibility, corridor, correlation, cap, diversity, anchor.
"""
import re
from itertools import combinations
from typing import Dict, Any, List, Tuple
from backend.services.util_service import team_name

# Status priority: higher = more reliable
_STATUS_PRIORITY = {"SAFE": 2, "SAFE*": 2, "NEUTRO_QUALIFICADO": 1, "NEUTRO": 1, "ALERTA": 0, "NO_BET": -1}

# (#119) Only these classifications are eligible for multiples (rule #028)
_ELIGIBLE_FOR_MULTIPLES = {"SAFE", "NEUTRO_QUALIFICADO"}

# Market pairs that are logically INCOMPATIBLE within the same game
_INTRA_INCOMPATIBLE_PAIRS = {
    frozenset(["Over 2.5 gols", "Under 2.5 gols"]),
    frozenset(["Over 3.5 gols", "Under 3.5 gols"]),
    frozenset(["Over 1.5 gols", "Under 1.5 gols"]),
    frozenset(["Over 4.5 gols", "Under 4.5 gols"]),
    frozenset(["BTTS — SIM", "BTTS — NÃO"]),
    frozenset(["DC 1X", "DC X2"]),
    frozenset(["Under 3.5 gols", "Under 4.5 gols"]),
    frozenset(["Over 2.5 gols", "Over 3.5 gols"]),
    frozenset(["Over 3.5 gols", "Over 4.5 gols"]),
}

# (#119) Cross-market correlation pairs — intra-game combinations to block
_CORRELATED_INTRA_TYPES = {
    frozenset(["over_under_gols", "over_under_escanteios"]),
    frozenset(["over_under_gols", "btts"]),
    frozenset(["over_under_gols", "1x2"]),
    frozenset(["over_under_gols", "dc"]),
}

MAX_SELECTIONS_PER_GAME = 2
MAX_APPEARANCES_PER_PICK = 3       # #119 item 4
MAX_SAME_MARKET_TYPE_PAIR = 2      # #119 item 5


def _leg(jogo: Dict[str, Any], merc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jogo": f"{team_name(jogo.get('homeTeam', ''))} x {team_name(jogo.get('awayTeam', ''))}",
        "homeTeam": team_name(jogo.get("homeTeam", "")),
        "awayTeam": team_name(jogo.get("awayTeam", "")),
        "leagueId": jogo.get("leagueId", ""),
        "leagueName": jogo.get("leagueName", ""),
        "datetime": jogo.get("datetime", ""),
        "fixture_id": jogo.get("id", ""),
        "mercado": merc.get("mercado", ""),
        "status": merc.get("status", ""),
        "classification": merc.get("classification", merc.get("status", "")),
        "prob_min": merc.get("prob_min", 0),
        "prob_max": merc.get("prob_max", 0),
        "probability": (merc.get("calibrated_probability") or merc.get("raw_probability")
                        or (merc.get("prob_max", 0) / 100.0 if merc.get("prob_max", 0) > 1 else 0)),
        "odd_minima": float(merc.get("odd_minima") or merc.get("book_odd") or 1.0),
        "is_anchor": False,
    }


def _odd_combinada(legs: List[Dict[str, Any]]) -> float:
    result = 1.0
    for leg in legs:
        result *= leg["odd_minima"]
    return round(result, 2)


def _prob_combinada(legs: List[Dict[str, Any]]) -> Tuple[int, int]:
    prob_min = 1.0
    prob_max = 1.0
    for leg in legs:
        prob_min *= (leg["prob_min"] / 100.0)
        prob_max *= (leg["prob_max"] / 100.0)
    return (round(prob_min * 100, 1), round(prob_max * 100, 1))


def _status_combinada(legs: List[Dict[str, Any]]) -> str:
    statuses = [leg["status"].upper() for leg in legs]
    if all(s in ("SAFE", "SAFE*") for s in statuses):
        return "SAFE"
    if any(s in ("SAFE", "SAFE*") for s in statuses) and all(s in ("SAFE", "SAFE*", "NEUTRO", "NEUTRO_QUALIFICADO") for s in statuses):
        return "MISTA"
    return "NEUTRO"


def _valid_mercado(m: Dict[str, Any]) -> bool:
    """Return True if market is eligible for multiples (#119: SAFE + NEUTRO_QUALIFICADO only)."""
    classification = (m.get("classification") or "").upper().replace(" ", "_")
    status = (m.get("status") or "").upper().replace(" ", "_")

    if classification == "NO_BET" or status == "NO_BET":
        return False

    effective = classification if classification else status
    if effective not in _ELIGIBLE_FOR_MULTIPLES:
        return False

    odd = m.get("odd_minima") or m.get("book_odd") or 0
    if float(odd) < 1.01:
        return False

    if m.get("odds_available") is False and "book_odd" in m:
        return False

    return True


# ── Market type extraction (#119) ──────────────────────────────────

def _get_market_type(market_name: str) -> str:
    ml = market_name.lower()
    if "escanteio" in ml or "corner" in ml:
        if "over" in ml or "under" in ml:
            return "over_under_escanteios"
        return "escanteios"
    if "cart" in ml or "card" in ml:
        if "over" in ml or "under" in ml:
            return "over_under_cartoes"
        return "cartoes"
    if "btts" in ml or "ambas" in ml:
        return "btts"
    if any(x in ml for x in ["over", "under", "mais", "menos"]):
        return "over_under_gols"
    if "1x2" in ml or ml in ("casa", "empate", "fora", "home", "draw", "away"):
        return "1x2"
    if "dc" in ml or "dupla chance" in ml or "double chance" in ml:
        return "dc"
    return ml


# ── Corridor detection (#119 / #037 expanded) ─────────────────────

_CORRIDOR_PATTERN = re.compile(r"^(.*?)\s*(over|under)\s+(\d+\.?\d*)", re.IGNORECASE)

def _is_corridor_bet(market_a: str, market_b: str) -> bool:
    """Detect corridor: Over X.5 + Under (X+1).5 of the same market type."""
    ma = _CORRIDOR_PATTERN.search(market_a)
    mb = _CORRIDOR_PATTERN.search(market_b)
    if not ma or not mb:
        return False
    if ma.group(1).strip().lower() != mb.group(1).strip().lower():
        return False
    if ma.group(2).lower() == mb.group(2).lower():
        return False
    over_line = float(ma.group(3)) if ma.group(2).lower() == "over" else float(mb.group(3))
    under_line = float(ma.group(3)) if ma.group(2).lower() == "under" else float(mb.group(3))
    return abs(under_line - over_line - 1.0) < 0.01


# ── Intra-game correlation (#119 item 2) ──────────────────────────

def _are_correlated_intra(market_a: str, market_b: str) -> bool:
    """Check if two markets are correlated within the same game."""
    pair = frozenset([_get_market_type(market_a), _get_market_type(market_b)])
    return pair in _CORRELATED_INTRA_TYPES


# ── Correlation matrix check ──────────────────────────────────────

def _check_correlation(m1_name: str, m2_name: str) -> Tuple[bool, float]:
    try:
        from backend.services.correlation_matrix import is_pair_allowed
        allowed, corr, reason = is_pair_allowed(m1_name, m2_name)
        return allowed, corr
    except ImportError:
        pair = frozenset([m1_name, m2_name])
        return pair not in _INTRA_INCOMPATIBLE_PAIRS, 0.0


# ── Post-processing filters (#119 items 4-6) ─────────────────────

def _pick_identifier(leg: Dict[str, Any]) -> str:
    return f"{leg.get('fixture_id', '')}:{leg.get('mercado', '')}"


def _apply_appearance_cap(duplas: List[Dict], max_per_pick: int = MAX_APPEARANCES_PER_PICK) -> List[Dict]:
    """Remove duplas that exceed the appearance cap for any pick."""
    counts: Dict[str, int] = {}
    filtered = []
    for d in duplas:
        ids = [_pick_identifier(d["leg1"]), _pick_identifier(d["leg2"])]
        if any(counts.get(pid, 0) >= max_per_pick for pid in ids):
            continue
        filtered.append(d)
        for pid in ids:
            counts[pid] = counts.get(pid, 0) + 1
    return filtered


def _apply_market_diversity(duplas: List[Dict], max_same: int = MAX_SAME_MARKET_TYPE_PAIR) -> List[Dict]:
    """Limit duplas with the same pair of market types."""
    type_pair_count: Dict[Tuple[str, str], int] = {}
    filtered = []
    for d in duplas:
        types = tuple(sorted([
            _get_market_type(d["leg1"].get("mercado", "")),
            _get_market_type(d["leg2"].get("mercado", "")),
        ]))
        if type_pair_count.get(types, 0) >= max_same:
            continue
        filtered.append(d)
        type_pair_count[types] = type_pair_count.get(types, 0) + 1
    return filtered


def _mark_anchor(dupla: Dict) -> Dict:
    """Mark the leg with highest probability as the anchor."""
    p1 = dupla["leg1"].get("probability", 0) or 0
    p2 = dupla["leg2"].get("probability", 0) or 0
    dupla["leg1"]["is_anchor"] = p1 >= p2
    dupla["leg2"]["is_anchor"] = p2 > p1
    return dupla


# ── Generators ────────────────────────────────────────────────────

def gerar_duplas_intra(
    jogos: List[Dict[str, Any]],
    min_odd_combinada: float = 1.5,
    limite: int = 8,
) -> List[Dict[str, Any]]:
    """Intra-game doubles: two markets from the SAME game."""
    result: List[Dict[str, Any]] = []

    for jogo in jogos:
        mercados = jogo.get("mercados") or []
        eligible = [m for m in mercados if _valid_mercado(m)]
        if len(eligible) < 2:
            continue

        for m1, m2 in combinations(eligible, 2):
            name1 = m1["mercado"]
            name2 = m2["mercado"]

            # Incompatible pairs
            if frozenset([name1, name2]) in _INTRA_INCOMPATIBLE_PAIRS:
                continue
            # Corridor (#037 expanded #119)
            if _is_corridor_bet(name1, name2):
                continue
            # Cross-market correlation (#119 item 2)
            if _are_correlated_intra(name1, name2):
                continue
            # Correlation matrix (Layer 5)
            allowed, corr = _check_correlation(name1, name2)
            if not allowed:
                continue

            legs = [_leg(jogo, m1), _leg(jogo, m2)]
            odd_comb = _odd_combinada(legs)
            if odd_comb < min_odd_combinada:
                continue

            prob_min, prob_max = _prob_combinada(legs)
            combo: Dict[str, Any] = {
                "tipo": "intra",
                "leg1": legs[0],
                "leg2": legs[1],
                "odd_combinada": odd_comb,
                "prob_combinada_min": prob_min,
                "prob_combinada_max": prob_max,
                "status_combinada": _status_combinada(legs),
            }
            if corr > 0.2:
                combo["correlation"] = round(corr, 2)
                combo["exposure_haircut"] = round(max(0.5, 1.0 - corr * 0.5), 2)
            result.append(combo)

    result.sort(key=lambda x: (-_STATUS_PRIORITY.get(x["status_combinada"], 0), -x["odd_combinada"]))
    result = [_mark_anchor(d) for d in result]
    return result[:limite]


def gerar_duplas_inter(
    jogos: List[Dict[str, Any]],
    min_odd_combinada: float = 1.8,
    limite: int = 10,
) -> List[Dict[str, Any]]:
    """Inter-game doubles: one market from each different game."""
    jogo_mercados: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    for jogo in jogos:
        mercados = jogo.get("mercados") or []
        eligible = [m for m in mercados if _valid_mercado(m)]
        if eligible:
            jogo_mercados.append((jogo, eligible))

    result: List[Dict[str, Any]] = []

    for (jogo1, merc1_list), (jogo2, merc2_list) in combinations(jogo_mercados, 2):
        for m1 in merc1_list:
            for m2 in merc2_list:
                legs = [_leg(jogo1, m1), _leg(jogo2, m2)]
                odd_comb = _odd_combinada(legs)
                if odd_comb < min_odd_combinada:
                    continue

                prob_min, prob_max = _prob_combinada(legs)
                result.append({
                    "tipo": "inter",
                    "leg1": legs[0],
                    "leg2": legs[1],
                    "odd_combinada": odd_comb,
                    "prob_combinada_min": prob_min,
                    "prob_combinada_max": prob_max,
                    "status_combinada": _status_combinada(legs),
                })

    # Sort by status priority then probability
    result.sort(key=lambda x: (-_STATUS_PRIORITY.get(x["status_combinada"], 0), -x["prob_combinada_min"]))
    # Apply post-processing filters (#119 items 4-6)
    result = _apply_appearance_cap(result)
    result = _apply_market_diversity(result)
    result = [_mark_anchor(d) for d in result]
    return result[:limite]


def gerar_combinadas(
    jogos: List[Dict[str, Any]],
    tipos: List[str] = None,
    min_status: str = "NEUTRO",  # kept for API compat, ignored internally (#119)
    limite_intra: int = 8,
    limite_inter: int = 10,
) -> Dict[str, Any]:
    """Entry point: returns both intra and inter doubles for a list of matches."""
    if tipos is None:
        tipos = ["intra", "inter"]

    intra = gerar_duplas_intra(jogos, limite=limite_intra) if "intra" in tipos else []
    inter = gerar_duplas_inter(jogos, limite=limite_inter) if "inter" in tipos else []

    return {
        "intra": intra,
        "inter": inter,
        "total_intra": len(intra),
        "total_inter": len(inter),
        "total_jogos": len(jogos),
    }
