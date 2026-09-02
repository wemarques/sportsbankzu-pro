"""
Data Governance Service (Layer 1)

Responsibilities:
- Calculate data_quality_score per match
- Detect early season / insufficient data
- Check odds availability
- Normalize data from FootyStats and API-Football
"""

import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger("sportsbankzu.governance")


# Minimum number of matches played in season for reliable modeling
MIN_MATCHES_RELIABLE = 5
MIN_MATCHES_FULL_CONFIDENCE = 10


def calculate_data_quality_score(
    stats: Dict[str, Any],
    odds: Dict[str, Any],
    league_stats: Optional[Dict[str, Any]] = None,
) -> float:
    """Calculate a 0-1 quality score for match data.

    Factors:
    - Availability of key stats fields (lambdas, probs, xG)
    - Availability of real odds
    - Season maturity (early season penalty)
    - Data completeness
    """
    score = 0.0
    max_score = 0.0

    # 1. Core probabilities available (weight: 25%)
    max_score += 25
    prob_fields = ["homeWinProb", "drawProb", "awayWinProb", "over25Prob", "bttsProb"]
    available = sum(1 for f in prob_fields if _has_value(stats.get(f)))
    score += 25 * (available / len(prob_fields))

    # 2. Lambda / xG available (weight: 15%)
    max_score += 15
    lambda_fields = ["lambdaHome", "lambdaAway"]
    xg_fields = ["homeXG", "awayXG"]
    lambda_avail = sum(1 for f in lambda_fields if _has_value(stats.get(f)))
    xg_avail = sum(1 for f in xg_fields if _has_value(stats.get(f)))
    score += 15 * max(lambda_avail / 2, xg_avail / 2)

    # 3. Odds available (weight: 25%)
    max_score += 25
    odds_fields = ["home", "draw", "away", "over25", "bttsYes"]
    odds_avail = sum(1 for f in odds_fields if _has_value(odds.get(f)))
    score += 25 * (odds_avail / len(odds_fields))

    # 4. Under/BTTS/Corner probs (weight: 15%)
    max_score += 15
    extra_fields = ["under35Prob", "under45Prob", "cornerOver85Prob", "cornerOver95Prob"]
    extra_avail = sum(1 for f in extra_fields if _has_value(stats.get(f)))
    score += 15 * (extra_avail / len(extra_fields))

    # 5. Corner odds (weight: 10%)
    max_score += 10
    corner_odds = ["cornersOver85", "cornersOver95", "cornersOver105"]
    corner_avail = sum(1 for f in corner_odds if _has_value(odds.get(f)))
    score += 10 * (corner_avail / len(corner_odds))

    # 6. Season maturity (weight: 10%)
    max_score += 10
    if league_stats:
        matches_played = league_stats.get("matchesCompleted") or league_stats.get("matches_played", 0)
        if matches_played and int(matches_played) >= MIN_MATCHES_FULL_CONFIDENCE:
            score += 10
        elif matches_played and int(matches_played) >= MIN_MATCHES_RELIABLE:
            score += 5
        # else: 0 for early season

    normalized = score / max_score if max_score > 0 else 0.0
    return round(min(1.0, max(0.0, normalized)), 3)


# #217: "nao sei quantos jogos foram" e "foram poucos jogos" sao estados
# diferentes e ate agora eram o mesmo. O `mp is None -> True` fazia o
# EARLY_SEASON_FALLBACK disparar na rodada 24 nao porque a contagem era
# baixa, mas porque o campo nao chegava. E a mesma forma que o #208
# corrigiu no lambda: ausencia de informacao nao e informacao de ausencia.
#
# A mudanca aqui e de ROTULO, nao de numero: por padrao o estado
# desconhecido continua contando como inicio de temporada, para nao mexer
# no corte de stake de um site em producao sem medicao. Ligar
# EARLY_SEASON_REQUIRES_COUNT=1 faz o desconhecido parar de encolher a
# aposta - so depois que o ledger (#218) tiver linhas para comparar.
ESTADO_TEMPORADA_OK = "OK"
ESTADO_TEMPORADA_INICIO = "EARLY"
ESTADO_TEMPORADA_DESCONHECIDO = "UNKNOWN"


def _exige_contagem_explicita() -> bool:
    return os.getenv("EARLY_SEASON_REQUIRES_COUNT", "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _jogos_disputados(
    league_stats: Optional[Dict[str, Any]] = None,
    matches_played: Optional[int] = None,
) -> Optional[int]:
    mp = matches_played
    if mp is None and league_stats:
        mp = league_stats.get("matchesCompleted") or league_stats.get("matches_played")
    if mp is None:
        return None
    try:
        return int(mp)
    except (TypeError, ValueError):
        return None


def season_data_state(
    league_stats: Optional[Dict[str, Any]] = None,
    matches_played: Optional[int] = None,
) -> str:
    """#217 - qual dos tres estados a liga esta, sem colapsar dois deles."""
    mp = _jogos_disputados(league_stats, matches_played)
    if mp is None:
        return ESTADO_TEMPORADA_DESCONHECIDO
    return ESTADO_TEMPORADA_INICIO if mp < MIN_MATCHES_RELIABLE else ESTADO_TEMPORADA_OK


def detect_early_season(
    league_stats: Optional[Dict[str, Any]] = None,
    matches_played: Optional[int] = None,
) -> bool:
    """Detect if we're in early season with insufficient data.

    #217: o estado DESCONHECIDO continua respondendo True por padrao (nenhuma
    mudanca de numero em producao) e passa a responder False quando
    EARLY_SEASON_REQUIRES_COUNT=1. Quem precisa saber QUAL dos dois motivos
    chama `season_data_state`.
    """
    estado = season_data_state(league_stats, matches_played)
    if estado == ESTADO_TEMPORADA_DESCONHECIDO:
        return not _exige_contagem_explicita()
    return estado == ESTADO_TEMPORADA_INICIO


def check_odds_availability(
    odds: Dict[str, Any],
    market_type: str,
) -> bool:
    """Check if real odds are available for a specific market."""
    market_odds_map = {
        "1X2": ["home", "draw", "away"],
        "Over 2.5": ["over25"],
        "Over 3.5": ["over35"],
        "Over 4.5": ["over45"],
        "Under 2.5": ["under25"],
        "Under 3.5": ["over35"],  # derived from over
        "Under 4.5": ["over45"],  # derived from over
        "BTTS": ["bttsYes"],
        "BTTS No": ["bttsNo"],
        "Double Chance": ["home", "draw", "away"],  # derived from 1X2
        "Corners Over 8.5": ["cornersOver85"],
        "Corners Over 9.5": ["cornersOver95"],
        "Corners Over 10.5": ["cornersOver105"],
    }

    fields = market_odds_map.get(market_type, [])
    return all(_has_value(odds.get(f)) for f in fields)


def get_source_flags(
    has_footystats: bool = False,
    has_api_football: bool = False,
) -> List[str]:
    """Return source flags for data provenance."""
    flags = []
    if has_footystats:
        flags.append("footystats")
    if has_api_football:
        flags.append("api_football")
    return flags


def _has_value(val: Any) -> bool:
    """Check if a value is present and meaningful."""
    if val is None:
        return False
    try:
        v = float(val)
        return v > 0
    except (ValueError, TypeError):
        return False
