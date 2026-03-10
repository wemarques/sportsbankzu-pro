"""
Serviço de combinadas (duplas) intra e inter jogos.

- Intra-game: dois mercados do MESMO jogo combinados (e.g. BTTS + Over 2.5)
- Inter-game: mercados de JOGOS DIFERENTES combinados (qualquer par SAFE/NEUTRO)
"""
from itertools import combinations
from typing import Dict, Any, List, Tuple
from backend.services.util_service import team_name

# Status priority: higher = more reliable
_STATUS_PRIORITY = {"SAFE": 2, "SAFE*": 2, "NEUTRO": 1, "ALERTA": 0}

# Market pairs that are logically INCOMPATIBLE within the same game (would cancel odds)
_INTRA_INCOMPATIBLE_PAIRS = {
    frozenset(["Over 2.5 gols", "Under 2.5 gols"]),
    frozenset(["Over 3.5 gols", "Under 3.5 gols"]),
    frozenset(["Over 1.5 gols", "Under 1.5 gols"]),
    frozenset(["Over 4.5 gols", "Under 4.5 gols"]),
    frozenset(["BTTS — SIM", "BTTS — NÃO"]),
    frozenset(["DC 1X", "DC X2"]),
}


def _leg(jogo: Dict[str, Any], merc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jogo": f"{team_name(jogo.get('homeTeam', ''))} x {team_name(jogo.get('awayTeam', ''))}",
        "homeTeam": team_name(jogo.get("homeTeam", "")),
        "awayTeam": team_name(jogo.get("awayTeam", "")),
        "leagueId": jogo.get("leagueId", ""),
        "leagueName": jogo.get("leagueName", ""),
        "datetime": jogo.get("datetime", ""),
        "mercado": merc.get("mercado", ""),
        "status": merc.get("status", ""),
        "prob_min": merc.get("prob_min", 0),
        "prob_max": merc.get("prob_max", 0),
        "odd_minima": float(merc.get("odd_minima") or 1.0),
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
    if any(s in ("SAFE", "SAFE*") for s in statuses) and all(s in ("SAFE", "SAFE*", "NEUTRO") for s in statuses):
        return "MISTA"
    return "NEUTRO"


def _valid_mercado(m: Dict[str, Any], min_status: str = "NEUTRO") -> bool:
    """Return True if mercado passes minimum status and has a valid odd."""
    status = (m.get("status") or "").upper()
    priority = _STATUS_PRIORITY.get(status, -1)
    min_priority = _STATUS_PRIORITY.get(min_status.upper(), 1)
    if priority < min_priority:
        return False
    odd = m.get("odd_minima") or 0
    return float(odd) >= 1.01


def gerar_duplas_intra(
    jogos: List[Dict[str, Any]],
    min_status: str = "NEUTRO",
    min_odd_combinada: float = 1.5,
    limite: int = 8,
) -> List[Dict[str, Any]]:
    """
    Gera duplas INTRA-GAME: dois mercados do MESMO jogo.

    Exige que ambos os mercados sejam SAFE ou NEUTRO (configurável via min_status).
    Exclui pares incompatíveis (Over/Under do mesmo limiar, BTTS sim/não).
    """
    result: List[Dict[str, Any]] = []

    for jogo in jogos:
        mercados = jogo.get("mercados") or []
        elegíveis = [m for m in mercados if _valid_mercado(m, min_status)]
        if len(elegíveis) < 2:
            continue

        for m1, m2 in combinations(elegíveis, 2):
            pair = frozenset([m1["mercado"], m2["mercado"]])
            if pair in _INTRA_INCOMPATIBLE_PAIRS:
                continue

            legs = [_leg(jogo, m1), _leg(jogo, m2)]
            odd_comb = _odd_combinada(legs)
            if odd_comb < min_odd_combinada:
                continue

            prob_min, prob_max = _prob_combinada(legs)
            result.append({
                "tipo": "intra",
                "leg1": legs[0],
                "leg2": legs[1],
                "odd_combinada": odd_comb,
                "prob_combinada_min": prob_min,
                "prob_combinada_max": prob_max,
                "status_combinada": _status_combinada(legs),
            })

    result.sort(key=lambda x: (-_STATUS_PRIORITY.get(x["status_combinada"], 0), -x["odd_combinada"]))
    return result[:limite]


def gerar_duplas_inter(
    jogos: List[Dict[str, Any]],
    min_status: str = "NEUTRO",
    min_odd_combinada: float = 1.8,
    limite: int = 8,
) -> List[Dict[str, Any]]:
    """
    Gera duplas INTER-GAME: um mercado de cada jogo diferente.

    Usa todos os mercados elegíveis de cada jogo (não só o mercado_principal),
    gerando todos os pares de jogos x pares de mercados.
    Prioriza SAFE+SAFE > MISTA > NEUTRO+NEUTRO.
    """
    # Pre-index eligible markets per game
    jogo_mercados: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    for jogo in jogos:
        mercados = jogo.get("mercados") or []
        elegíveis = [m for m in mercados if _valid_mercado(m, min_status)]
        if elegíveis:
            jogo_mercados.append((jogo, elegíveis))

    result: List[Dict[str, Any]] = []

    for (jogo1, merc1_list), (jogo2, merc2_list) in combinations(jogo_mercados, 2):
        for m1 in merc1_list:
            for m2 in merc2_list:
                legs = [_leg(jogo1, m1), _leg(jogo2, m2)]
                odd_comb = _odd_combinada(legs)
                if odd_comb < min_odd_combinada:
                    continue

                prob_min, prob_max = _prob_combinada(legs)
                status_comb = _status_combinada(legs)
                result.append({
                    "tipo": "inter",
                    "leg1": legs[0],
                    "leg2": legs[1],
                    "odd_combinada": odd_comb,
                    "prob_combinada_min": prob_min,
                    "prob_combinada_max": prob_max,
                    "status_combinada": status_comb,
                })

    # Sort: SAFE first, then by highest combined probability
    result.sort(key=lambda x: (-_STATUS_PRIORITY.get(x["status_combinada"], 0), -x["prob_combinada_min"]))
    return result[:limite]


def gerar_combinadas(
    jogos: List[Dict[str, Any]],
    tipos: List[str] = None,  # ["intra", "inter"] or subset
    min_status: str = "NEUTRO",
    limite_intra: int = 8,
    limite_inter: int = 8,
) -> Dict[str, Any]:
    """
    Entry point: returns both intra and inter doubles for a list of matches.
    """
    if tipos is None:
        tipos = ["intra", "inter"]

    intra = gerar_duplas_intra(jogos, min_status=min_status, limite=limite_intra) if "intra" in tipos else []
    inter = gerar_duplas_inter(jogos, min_status=min_status, limite=limite_inter) if "inter" in tipos else []

    return {
        "intra": intra,
        "inter": inter,
        "total_intra": len(intra),
        "total_inter": len(inter),
        "total_jogos": len(jogos),
    }
