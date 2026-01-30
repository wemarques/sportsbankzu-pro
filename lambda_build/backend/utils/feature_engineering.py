from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

@dataclass
class MatchEvent:
    date: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int
    competition: str | None = None
    is_derby: bool = False
    is_final: bool = False
    is_relegation_battle: bool = False

def decay_weight(event_date: datetime, ref_date: datetime, half_life_days: int = 30) -> float:
    delta_days = max((ref_date - event_date).days, 0)
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (delta_days / float(half_life_days))

def calcular_lambda_com_decay(
    events: Iterable[MatchEvent],
    team: str,
    ref_date: datetime,
    is_home: bool,
    half_life_days: int = 30,
) -> float:
    weighted_goals = 0.0
    weighted_matches = 0.0
    for e in events:
        if team not in (e.home, e.away):
            continue
        weight = decay_weight(e.date, ref_date, half_life_days)
        if is_home and e.home != team:
            continue
        if not is_home and e.away != team:
            continue
        goals = e.home_goals if e.home == team else e.away_goals
        weighted_goals += goals * weight
        weighted_matches += weight
    if weighted_matches <= 0:
        return 0.0
    return weighted_goals / weighted_matches

def flag_volatilidade_contextual(event: MatchEvent) -> str:
    if event.is_final:
        return "ALTA"
    if event.is_derby or event.is_relegation_battle:
        return "ALTA"
    return "NORMAL"

def preparar_features(
    events: Iterable[MatchEvent],
    home: str,
    away: str,
    ref_date: datetime,
    half_life_days: int = 30,
) -> dict:
    lambda_home = calcular_lambda_com_decay(events, home, ref_date, True, half_life_days)
    lambda_away = calcular_lambda_com_decay(events, away, ref_date, False, half_life_days)
    return {
        "lambda_home_decay": round(lambda_home, 4),
        "lambda_away_decay": round(lambda_away, 4),
    }
