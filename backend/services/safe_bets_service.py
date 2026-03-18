"""
Safe Bets Engine — 3-Layer Filtering Service

Layer 1: League DNA — categorize league profile and filter eligible markets
Layer 2: Risk Semaphore — block high-risk matches (prediction_risk > 0.65)
Layer 3: Strategy Algorithms — cross-validate league + team stats

Strategies:
  A. Under Defensivo Conservador (Under 3.5)
  B. BTTS NO (Ambos Marcam: Não)
  C. Safe Corners (best line via v2 engine, bidirectional Over/Under)
  D. Timing Markets (Gols 2º Tempo)
"""

import logging
from typing import Dict, Any, List, Optional

from backend.config.league_dna import (
    get_league_dna,
    get_enabled_markets,
    classify_league_dna,
    LeagueDNA,
)
from backend.models.safe_bets import (
    SafeBetTag,
    RiskLevel,
    StrategyResult,
    SafeBetsResult,
    SafeBetsMatchInput,
    LeagueSeasonStats,
    TeamSafeBetsStats,
)

logger = logging.getLogger("sportsbankzu.safe_bets")

# =============================================================================
# Constants / Thresholds
# =============================================================================

RISK_THRESHOLD = 0.65  # prediction_risk > 65% => NO_BET

# Strategy A: Under Defensivo Conservador
UNDER35_LEAGUE_AVG_THRESHOLD = 2.60
UNDER35_CONCEDED_AVG_THRESHOLD = 1.10

# Strategy B: BTTS NO
BTTS_NO_LEAGUE_BTTS_THRESHOLD = 45.0  # %
BTTS_NO_HOME_CS_THRESHOLD = 50.0      # % clean sheet home
BTTS_NO_AWAY_FTS_THRESHOLD = 40.0     # % failed to score away

# Strategy C: Safe Corners
CORNERS_LEAGUE_AVG_THRESHOLD = 10.2
CORNERS_TEAM_COMBINED_THRESHOLD = 10.5
CORNERS_HT_THRESHOLD = 4.5            # 1st half corners combined

# Strategy D: Timing Markets (2nd Half Goals)
TIMING_2H_COMBINED_THRESHOLD = 88.0   # % combined 2nd half goal probability


# =============================================================================
# Layer 1: League DNA
# =============================================================================

def _evaluate_layer1(
    league_id: str,
    league_stats: Optional[LeagueSeasonStats] = None,
) -> Dict[str, Any]:
    """Evaluate Layer 1 — League DNA categorization.

    Returns dict with:
      - category: DEFENSIVE | BALANCED | OFFENSIVE
      - is_aggressive: bool
      - markets_enabled: list of eligible strategies
      - source: 'static' or 'dynamic'
    """
    dna = get_league_dna(league_id)

    # If we have live season stats, prefer dynamic classification
    if league_stats and league_stats.seasonAVG_overall is not None:
        cards_avg = league_stats.cardsAVG_overall or (dna.avg_cards if dna else 0.0)
        category, is_aggressive = classify_league_dna(
            league_stats.seasonAVG_overall,
            cards_avg,
        )
        # Determine enabled markets dynamically
        markets = []
        if category == "DEFENSIVE":
            markets = ["UNDER_35", "BTTS_NO"]
        elif category == "OFFENSIVE":
            markets = ["SAFE_CORNERS", "TIMING_2H"]
        else:
            markets = ["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"]

        # Check feature flags from API
        goal_timing_disabled = bool(league_stats.goalTimingDisabled)
        corners_disabled = bool(league_stats.corner_disabled)
        if goal_timing_disabled and "TIMING_2H" in markets:
            markets.remove("TIMING_2H")
        if corners_disabled and "SAFE_CORNERS" in markets:
            markets.remove("SAFE_CORNERS")

        return {
            "category": category,
            "is_aggressive": is_aggressive,
            "markets_enabled": markets,
            "source": "dynamic",
            "season_avg_goals": league_stats.seasonAVG_overall,
            "cards_avg": cards_avg,
            "goal_timing_disabled": goal_timing_disabled,
            "corners_disabled": corners_disabled,
        }

    # Fallback to static DNA
    if dna:
        return {
            "category": dna.category,
            "is_aggressive": dna.is_aggressive,
            "markets_enabled": list(dna.markets_enabled),
            "source": "static",
            "season_avg_goals": dna.avg_goals,
            "cards_avg": dna.avg_cards,
            "goal_timing_disabled": dna.goal_timing_disabled,
            "corners_disabled": dna.corners_disabled,
        }

    # Unknown league — allow all
    logger.warning(f"[Layer1] Unknown league '{league_id}', allowing all markets")
    return {
        "category": "BALANCED",
        "is_aggressive": False,
        "markets_enabled": ["UNDER_35", "BTTS_NO", "SAFE_CORNERS", "TIMING_2H"],
        "source": "fallback",
        "season_avg_goals": None,
        "cards_avg": None,
        "goal_timing_disabled": False,
        "corners_disabled": False,
    }


# =============================================================================
# Layer 2: Risk Semaphore ("Feature Killer")
# =============================================================================

def _evaluate_layer2(
    match_input: SafeBetsMatchInput,
) -> Dict[str, Any]:
    """Evaluate Layer 2 — Risk semaphore.

    If prediction_risk > RISK_THRESHOLD (0.65), the match is blocked for
    goals/BTTS markets (indicates volatile scoring patterns).

    Returns dict with:
      - blocked: bool
      - risk_score: float
      - reason: str
    """
    risk = match_input.prediction_risk

    # Also check team-level risk
    home_risk = None
    away_risk = None
    if match_input.home_stats:
        home_risk = match_input.home_stats.predictionRisk or match_input.home_stats.riskNum
    if match_input.away_stats:
        away_risk = match_input.away_stats.predictionRisk or match_input.away_stats.riskNum

    # Use the highest risk among match, home, away
    risks = [r for r in [risk, home_risk, away_risk] if r is not None]
    if not risks:
        return {
            "blocked": False,
            "risk_score": 0.0,
            "reason": "No risk data available — proceeding with caution",
        }

    max_risk = max(risks)

    if max_risk > RISK_THRESHOLD:
        return {
            "blocked": True,
            "risk_score": max_risk,
            "reason": f"prediction_risk={max_risk:.2f} > {RISK_THRESHOLD} — match blocked for goals/BTTS",
        }

    return {
        "blocked": False,
        "risk_score": max_risk,
        "reason": f"prediction_risk={max_risk:.2f} — within acceptable range",
    }


# =============================================================================
# Layer 3: Strategy Algorithms
# =============================================================================

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely coerce to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _strategy_under35(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> StrategyResult:
    """Strategy A: Under Defensivo Conservador — Under 3.5 Gols.

    Validation:
      - Liga seasonAVG_overall < 2.60
      - Mandante seasonConcededAVG < 1.10
      - Visitante seasonConcededAVG < 1.10
    """
    reasons = []
    passed = True

    # League average check
    league_avg = _safe_float(league_stats.seasonAVG_overall if league_stats else None)
    if league_avg <= 0:
        return StrategyResult(
            strategy="UNDER_35", tag=SafeBetTag.UNDER_35, passed=False,
            reason="No league average data available", market_label="Under 3.5 Gols",
        )

    if league_avg >= UNDER35_LEAGUE_AVG_THRESHOLD:
        passed = False
        reasons.append(f"Liga AVG={league_avg:.2f} >= {UNDER35_LEAGUE_AVG_THRESHOLD}")

    # Home conceded check
    home_conceded = _safe_float(
        home_stats.seasonConcededAVG_overall if home_stats else None,
        default=-1,
    )
    if home_conceded < 0:
        # Try home-specific conceded
        home_conceded = _safe_float(
            home_stats.seasonConcededAVG_home if home_stats else None,
            default=-1,
        )
    if home_conceded < 0:
        passed = False
        reasons.append("Missing home conceded data")
    elif home_conceded >= UNDER35_CONCEDED_AVG_THRESHOLD:
        passed = False
        reasons.append(f"Home conceded={home_conceded:.2f} >= {UNDER35_CONCEDED_AVG_THRESHOLD}")

    # Away conceded check
    away_conceded = _safe_float(
        away_stats.seasonConcededAVG_overall if away_stats else None,
        default=-1,
    )
    if away_conceded < 0:
        away_conceded = _safe_float(
            away_stats.seasonConcededAVG_away if away_stats else None,
            default=-1,
        )
    if away_conceded < 0:
        passed = False
        reasons.append("Missing away conceded data")
    elif away_conceded >= UNDER35_CONCEDED_AVG_THRESHOLD:
        passed = False
        reasons.append(f"Away conceded={away_conceded:.2f} >= {UNDER35_CONCEDED_AVG_THRESHOLD}")

    # Confidence: inversely proportional to league avg and conceded
    confidence = None
    if passed and league_avg > 0:
        ratio = (UNDER35_LEAGUE_AVG_THRESHOLD - league_avg) / UNDER35_LEAGUE_AVG_THRESHOLD
        confidence = min(95.0, max(60.0, 70.0 + ratio * 100))

    return StrategyResult(
        strategy="UNDER_35",
        tag=SafeBetTag.UNDER_35,
        passed=passed,
        confidence=confidence,
        reason=" | ".join(reasons) if reasons else "All criteria met",
        market_label="Under 3.5 Gols",
        details={
            "league_avg": league_avg,
            "home_conceded": home_conceded if home_conceded >= 0 else None,
            "away_conceded": away_conceded if away_conceded >= 0 else None,
            "thresholds": {
                "league_avg": UNDER35_LEAGUE_AVG_THRESHOLD,
                "conceded_avg": UNDER35_CONCEDED_AVG_THRESHOLD,
            },
        },
    )


def _strategy_btts_no(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> StrategyResult:
    """Strategy B: BTTS NO (Ambos Marcam: Não).

    Validation:
      - Liga seasonBTTSPercentage < 45%
      - Mandante seasonCSPercentage_home (Clean Sheet) > 50%
      - Visitante seasonFTSPercentage_away (Failed to Score) > 40%
    """
    reasons = []
    passed = True

    # League BTTS check
    league_btts = _safe_float(league_stats.seasonBTTSPercentage if league_stats else None)
    if league_btts <= 0:
        return StrategyResult(
            strategy="BTTS_NO", tag=SafeBetTag.BTTS_NO, passed=False,
            reason="No league BTTS data available", market_label="BTTS Não",
        )

    if league_btts >= BTTS_NO_LEAGUE_BTTS_THRESHOLD:
        passed = False
        reasons.append(f"Liga BTTS={league_btts:.1f}% >= {BTTS_NO_LEAGUE_BTTS_THRESHOLD}%")

    # Home clean sheet check
    home_cs = _safe_float(
        home_stats.seasonCSPercentage_home if home_stats else None,
        default=-1,
    )
    if home_cs < 0:
        home_cs = _safe_float(
            home_stats.seasonCSPercentage_overall if home_stats else None,
            default=-1,
        )
    if home_cs < 0:
        passed = False
        reasons.append("Missing home clean sheet data")
    elif home_cs <= BTTS_NO_HOME_CS_THRESHOLD:
        passed = False
        reasons.append(f"Home CS={home_cs:.1f}% <= {BTTS_NO_HOME_CS_THRESHOLD}%")

    # Away failed to score check
    away_fts = _safe_float(
        away_stats.seasonFTSPercentage_away if away_stats else None,
        default=-1,
    )
    if away_fts < 0:
        away_fts = _safe_float(
            away_stats.seasonFTSPercentage_overall if away_stats else None,
            default=-1,
        )
    if away_fts < 0:
        passed = False
        reasons.append("Missing away FTS data")
    elif away_fts <= BTTS_NO_AWAY_FTS_THRESHOLD:
        passed = False
        reasons.append(f"Away FTS={away_fts:.1f}% <= {BTTS_NO_AWAY_FTS_THRESHOLD}%")

    confidence = None
    if passed and home_cs > 0 and away_fts > 0:
        confidence = min(95.0, (home_cs + away_fts) / 2.0)

    return StrategyResult(
        strategy="BTTS_NO",
        tag=SafeBetTag.BTTS_NO,
        passed=passed,
        confidence=confidence,
        reason=" | ".join(reasons) if reasons else "All criteria met",
        market_label="BTTS Não",
        details={
            "league_btts": league_btts,
            "home_clean_sheet_pct": home_cs if home_cs >= 0 else None,
            "away_fts_pct": away_fts if away_fts >= 0 else None,
            "thresholds": {
                "league_btts": BTTS_NO_LEAGUE_BTTS_THRESHOLD,
                "home_cs": BTTS_NO_HOME_CS_THRESHOLD,
                "away_fts": BTTS_NO_AWAY_FTS_THRESHOLD,
            },
        },
    )


def _strategy_safe_corners(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> List[StrategyResult]:
    """Strategy C: Safe Corners — best line from v2 engine (bidirectional).

    Uses the Corners Engine v2 price ladder to select the best Over or Under
    line instead of hardcoding Over 9.5. Falls back to combined-average
    heuristic when the v2 engine is not available.

    Validation:
      - v2 path: engine selects best line/side with edge > 0
      - fallback: Liga cornersAVG_overall > 10.2, combined > 10.5
      - HT: (corners_fh_avg_home + corners_fh_avg_away) > 4.5
    """
    results = []

    # --- Try v2 engine for best line selection ---
    v2_result = _try_corners_v2(league_stats, home_stats, away_stats)
    if v2_result is not None:
        results.append(v2_result)
    else:
        # --- Fallback: combined-average heuristic (v1-style) ---
        results.append(_corners_fallback_heuristic(league_stats, home_stats, away_stats))

    # HT Corners check (independent of v2)
    home_fh = _safe_float(home_stats.corners_fh_avg if home_stats else None)
    away_fh = _safe_float(away_stats.corners_fh_avg if away_stats else None)

    fh_combined = home_fh + away_fh
    if fh_combined > CORNERS_HT_THRESHOLD:
        results.append(StrategyResult(
            strategy="SAFE_CORNERS_HT",
            tag=SafeBetTag.SAFE_CORNERS_HT,
            passed=True,
            confidence=min(90.0, max(60.0, fh_combined / CORNERS_HT_THRESHOLD * 70)),
            reason=f"1st half corners combined={fh_combined:.1f} > {CORNERS_HT_THRESHOLD}",
            market_label="Over 4.5 Escanteios HT",
            details={
                "home_fh_corners": home_fh,
                "away_fh_corners": away_fh,
                "combined": fh_combined,
                "threshold": CORNERS_HT_THRESHOLD,
            },
        ))

    return results


def _try_corners_v2(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> Optional[StrategyResult]:
    """Attempt to use Corners Engine v2 to find the best corner line.

    Returns a StrategyResult if the v2 engine produces a viable market,
    or None if the engine is unavailable / data insufficient.
    """
    try:
        from backend.modeling.corners.predictor import predict_corners

        home_dict = home_stats.model_dump() if home_stats and hasattr(home_stats, "model_dump") else (
            home_stats.dict() if home_stats and hasattr(home_stats, "dict") else {}
        )
        away_dict = away_stats.model_dump() if away_stats and hasattr(away_stats, "model_dump") else (
            away_stats.dict() if away_stats and hasattr(away_stats, "dict") else {}
        )
        league_dict = league_stats.model_dump() if league_stats and hasattr(league_stats, "model_dump") else (
            league_stats.dict() if league_stats and hasattr(league_stats, "dict") else {}
        )

        v2 = predict_corners(
            home_stats=home_dict,
            away_stats=away_dict,
            league_stats=league_dict,
        )

        if not v2 or v2.get("governance_state") == "RESTRICTED":
            return None

        best = v2.get("best_market")
        if not best or best.get("recommendation") == "NO_BET":
            return None

        side = best.get("side", "over")
        line = best.get("line", 9.5)
        edge = best.get("quality_adjusted_edge", best.get("edge", 0.0))
        prob = best.get("probability", 0.5)

        if edge <= 0:
            return None

        side_label = "Over" if side == "over" else "Under"
        market_label = f"{side_label} {line} Escanteios"
        confidence = min(95.0, max(60.0, 50.0 + edge * 500))

        return StrategyResult(
            strategy="SAFE_CORNERS",
            tag=SafeBetTag.SAFE_CORNERS,
            passed=True,
            confidence=confidence,
            reason=f"v2 engine: {side_label} {line} (edge={edge:.3f}, prob={prob:.3f})",
            market_label=market_label,
            details={
                "engine_version": v2.get("engine_version", "2.0.0"),
                "side": side,
                "line": line,
                "edge": round(edge, 4),
                "probability": round(prob, 4),
                "projected_corners_ft": v2.get("expected_total_corners_ft"),
                "governance_state": v2.get("governance_state"),
                "data_quality_tier": v2.get("data_quality_tier"),
            },
        )

    except Exception as e:
        logger.debug(f"[SafeBets] Corners v2 engine unavailable: {e}")
        return None


def _corners_fallback_heuristic(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> StrategyResult:
    """Fallback heuristic when v2 engine is not available.

    Selects the best Over or Under line based on combined corner averages.
    """
    league_corners = _safe_float(league_stats.cornersAVG_overall if league_stats else None)

    home_corners = _safe_float(home_stats.cornersAVG_home if home_stats else None)
    if home_corners <= 0:
        home_corners = _safe_float(home_stats.cornersAVG_overall if home_stats else None)
    away_corners = _safe_float(away_stats.cornersAVG_away if away_stats else None)
    if away_corners <= 0:
        away_corners = _safe_float(away_stats.cornersAVG_overall if away_stats else None)

    combined = home_corners + away_corners
    reasons = []
    passed = True

    if league_corners <= 0:
        passed = False
        reasons.append("No league corners data available")
    elif league_corners <= CORNERS_LEAGUE_AVG_THRESHOLD:
        passed = False
        reasons.append(f"Liga corners={league_corners:.1f} <= {CORNERS_LEAGUE_AVG_THRESHOLD}")

    if combined <= 0:
        passed = False
        reasons.append("No team corners data available")
    elif combined <= CORNERS_TEAM_COMBINED_THRESHOLD:
        passed = False
        reasons.append(f"Combined corners={combined:.1f} <= {CORNERS_TEAM_COMBINED_THRESHOLD}")

    # Determine best side/line from combined average
    if combined > 0:
        # Pick the line closest to but below the combined average for Over,
        # or closest to but above for Under, whichever has more margin
        candidate_lines = [8.5, 9.5, 10.5, 11.5]
        best_side = "Over"
        best_line = 9.5

        for line in candidate_lines:
            if combined > line + 1.0:
                best_line = line
                best_side = "Over"
            elif combined < line - 1.0:
                best_line = line
                best_side = "Under"
                break

        market_label = f"{best_side} {best_line} Escanteios"
    else:
        market_label = "Over 9.5 Escanteios"

    confidence = None
    if passed:
        ratio = (combined - CORNERS_TEAM_COMBINED_THRESHOLD) / CORNERS_TEAM_COMBINED_THRESHOLD
        confidence = min(95.0, max(60.0, 70.0 + ratio * 100))

    return StrategyResult(
        strategy="SAFE_CORNERS",
        tag=SafeBetTag.SAFE_CORNERS,
        passed=passed,
        confidence=confidence,
        reason=" | ".join(reasons) if reasons else "All criteria met",
        market_label=market_label,
        details={
            "engine_version": "1.0-fallback",
            "league_corners_avg": league_corners,
            "home_corners_avg": home_corners,
            "away_corners_avg": away_corners,
            "combined": combined,
            "thresholds": {
                "league_avg": CORNERS_LEAGUE_AVG_THRESHOLD,
                "combined": CORNERS_TEAM_COMBINED_THRESHOLD,
            },
        },
    )


def _strategy_timing_2h(
    league_stats: Optional[LeagueSeasonStats],
    home_stats: Optional[TeamSafeBetsStats],
    away_stats: Optional[TeamSafeBetsStats],
) -> StrategyResult:
    """Strategy D: Timing Markets — Over 0.5 Gols no 2º Tempo.

    Validation:
      - Combined % of over05_2hg_percentage or half_with_most_goals_is_2h > 88%
    """
    # Collect 2nd half percentage from multiple sources
    pcts = []

    # League level
    if league_stats:
        val = _safe_float(league_stats.over05_2hg_percentage)
        if val > 0:
            pcts.append(val)
        val2 = _safe_float(league_stats.half_with_most_goals_is_2h_percentage_overall)
        if val2 > 0:
            pcts.append(val2)

    # Team level
    for stats in [home_stats, away_stats]:
        if stats:
            val = _safe_float(stats.over05_2hg_percentage)
            if val > 0:
                pcts.append(val)
            val2 = _safe_float(stats.half_with_most_goals_is_2h_percentage_overall)
            if val2 > 0:
                pcts.append(val2)

    if not pcts:
        return StrategyResult(
            strategy="TIMING_2H",
            tag=SafeBetTag.TIMING_2H,
            passed=False,
            reason="No 2nd half goal timing data available",
            market_label="Over 0.5 Gols 2T",
        )

    # Use average of available percentages as the combined metric
    combined_pct = sum(pcts) / len(pcts)
    passed = combined_pct > TIMING_2H_COMBINED_THRESHOLD

    return StrategyResult(
        strategy="TIMING_2H",
        tag=SafeBetTag.TIMING_2H,
        passed=passed,
        confidence=min(95.0, combined_pct) if passed else None,
        reason=f"Combined 2H%={combined_pct:.1f}% {'>' if passed else '<='} {TIMING_2H_COMBINED_THRESHOLD}%",
        market_label="Over 0.5 Gols 2T",
        details={
            "percentages_found": pcts,
            "combined_avg": combined_pct,
            "threshold": TIMING_2H_COMBINED_THRESHOLD,
        },
    )


# =============================================================================
# Main Engine
# =============================================================================

def evaluate_safe_bets(match_input: SafeBetsMatchInput) -> SafeBetsResult:
    """Run the full 3-layer Safe Bets evaluation for a single match.

    Returns a SafeBetsResult with tags, risk level, and strategy details.
    """
    result = SafeBetsResult(
        match_id=match_input.match_id,
        league_id=match_input.league_id,
        home_team=match_input.home_team,
        away_team=match_input.away_team,
    )

    # ─── Layer 1: League DNA ───
    layer1 = _evaluate_layer1(match_input.league_id, match_input.league_stats)
    result.layer1_dna = layer1
    enabled_markets = layer1["markets_enabled"]

    logger.info(
        f"[SafeBets] {match_input.home_team} vs {match_input.away_team} | "
        f"League={match_input.league_id} | DNA={layer1['category']} | "
        f"Markets={enabled_markets}"
    )

    # ─── Layer 2: Risk Semaphore ───
    layer2 = _evaluate_layer2(match_input)
    result.layer2_risk = layer2

    if layer2["blocked"]:
        result.blocked = True
        result.block_reason = layer2["reason"]
        result.risk_level = RiskLevel.NO_BET
        result.tags = [SafeBetTag.NO_BET]
        logger.warning(
            f"[SafeBets] BLOCKED: {match_input.home_team} vs {match_input.away_team} | "
            f"{layer2['reason']}"
        )
        return result

    # ─── Layer 3: Strategy Algorithms ───
    strategies: List[StrategyResult] = []
    passed_tags: List[SafeBetTag] = []

    # Strategy A: Under 3.5
    if "UNDER_35" in enabled_markets:
        res_a = _strategy_under35(
            match_input.league_stats,
            match_input.home_stats,
            match_input.away_stats,
        )
        strategies.append(res_a)
        if res_a.passed:
            passed_tags.append(SafeBetTag.UNDER_35)

    # Strategy B: BTTS NO
    if "BTTS_NO" in enabled_markets:
        res_b = _strategy_btts_no(
            match_input.league_stats,
            match_input.home_stats,
            match_input.away_stats,
        )
        strategies.append(res_b)
        if res_b.passed:
            passed_tags.append(SafeBetTag.BTTS_NO)

    # Strategy C: Safe Corners (may return 2 results: FT + HT)
    if "SAFE_CORNERS" in enabled_markets:
        corner_results = _strategy_safe_corners(
            match_input.league_stats,
            match_input.home_stats,
            match_input.away_stats,
        )
        strategies.extend(corner_results)
        for cr in corner_results:
            if cr.passed:
                passed_tags.append(cr.tag)

    # Strategy D: Timing 2H
    if "TIMING_2H" in enabled_markets:
        # Check if goal timing is disabled
        if not layer1.get("goal_timing_disabled"):
            res_d = _strategy_timing_2h(
                match_input.league_stats,
                match_input.home_stats,
                match_input.away_stats,
            )
            strategies.append(res_d)
            if res_d.passed:
                passed_tags.append(SafeBetTag.TIMING_2H)

    result.layer3_strategies = strategies
    result.tags = passed_tags if passed_tags else [SafeBetTag.NO_BET]

    # Determine risk level
    if passed_tags:
        result.risk_level = RiskLevel.SAFE
    else:
        result.risk_level = RiskLevel.MODERATE

    logger.info(
        f"[SafeBets] RESULT: {match_input.home_team} vs {match_input.away_team} | "
        f"Tags={[t.value for t in result.tags]} | Risk={result.risk_level.value}"
    )

    return result


def evaluate_batch(matches: List[SafeBetsMatchInput]) -> List[SafeBetsResult]:
    """Evaluate safe bets for a batch of matches."""
    return [evaluate_safe_bets(m) for m in matches]
