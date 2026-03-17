"""
Corner Market Operational States and Promotion Logic

States: RESTRICTED → NEUTRAL → ACTIVE_GUARDED → ACTIVE
Initial deployment: All corners start as RESTRICTED (SHADOW/PILOT mode).

Promotion is escalonada (graduated), not binary:
- Hard blockers prevent any promotion beyond RESTRICTED
- Evidence score determines level for non-blocked markets
- Promotion happens per league and per line independently

Hard Blockers (force RESTRICTED):
- Artifact inexistent or invalid
- Training/output inconsistent
- Sample size below minimum operational floor
- Cannot derive line probabilities reliably
- Critical drift

Evidence Score (composite):
- Calibration (ECE)
- Brier / LogLoss
- Benchmark comparison (beats_baseline)
- Temporal stability
- Drift
- ROI theoretical (secondary)
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.modeling.corners import CORNER_LINES

logger = logging.getLogger("sportsbankzu.corners.operational_states")


class CornerOperationalState(str, Enum):
    RESTRICTED = "RESTRICTED"
    NEUTRAL = "NEUTRAL"
    ACTIVE_GUARDED = "ACTIVE_GUARDED"
    ACTIVE = "ACTIVE"


# ─── Hard Blocker Thresholds ───
MIN_SAMPLE_SIZE_FLOOR = 20  # absolute minimum to operate
MAX_CRITICAL_DRIFT = 0.20  # drift above this = blocked
MAX_BRIER_FOR_ANY_PROMOTION = 0.35  # brier above this = blocked

# ─── Evidence Score Thresholds ───
# Score is 0-100; higher = stronger evidence
NEUTRAL_MIN_SCORE = 25
ACTIVE_GUARDED_MIN_SCORE = 50
ACTIVE_MIN_SCORE = 70

# ─── Component Weights for Evidence Score ───
EVIDENCE_WEIGHTS = {
    "calibration": 25,     # max 25 points
    "accuracy": 25,        # max 25 points (Brier/LogLoss)
    "benchmark": 20,       # max 20 points (beats baselines)
    "stability": 15,       # max 15 points
    "roi": 10,             # max 10 points
    "drift": 5,            # max 5 points (penalty subtracted)
}


def _score_calibration(ece: float) -> float:
    """Score calibration (ECE). Lower ECE = higher score."""
    if ece <= 0.03:
        return 25.0
    if ece <= 0.06:
        return 20.0
    if ece <= 0.10:
        return 15.0
    if ece <= 0.15:
        return 10.0
    if ece <= 0.20:
        return 5.0
    return 0.0


def _score_accuracy(brier: float, logloss: float) -> float:
    """Score accuracy (Brier + LogLoss combined)."""
    # Brier component (max 15 points)
    if brier <= 0.15:
        brier_score = 15.0
    elif brier <= 0.20:
        brier_score = 12.0
    elif brier <= 0.25:
        brier_score = 8.0
    elif brier <= 0.30:
        brier_score = 4.0
    else:
        brier_score = 0.0

    # LogLoss component (max 10 points)
    if logloss <= 0.50:
        ll_score = 10.0
    elif logloss <= 0.60:
        ll_score = 7.0
    elif logloss <= 0.70:
        ll_score = 4.0
    else:
        ll_score = 0.0

    return brier_score + ll_score


def _score_benchmark(beats_league: bool, beats_team: bool, beats_secondary: bool) -> float:
    """Score benchmark comparison. Beating baselines = higher score."""
    score = 0.0
    if beats_league:
        score += 8.0
    if beats_team:
        score += 6.0
    if beats_secondary:
        score += 6.0
    return score


def _score_stability(stability_cv: float) -> float:
    """Score temporal stability. Lower CV = higher score."""
    if stability_cv <= 0.10:
        return 15.0
    if stability_cv <= 0.20:
        return 12.0
    if stability_cv <= 0.30:
        return 8.0
    if stability_cv <= 0.40:
        return 4.0
    return 0.0


def _score_roi(roi: float) -> float:
    """Score theoretical ROI. Positive = bonus points."""
    if roi >= 0.10:
        return 10.0
    if roi >= 0.05:
        return 7.0
    if roi >= 0.0:
        return 4.0
    return 0.0


def _penalty_drift(drift: float) -> float:
    """Drift penalty (subtracted from total score)."""
    if drift <= 0.03:
        return 0.0
    if drift <= 0.06:
        return 1.0
    if drift <= 0.10:
        return 3.0
    if drift <= 0.15:
        return 5.0
    return 5.0  # max penalty


def check_hard_blockers(
    metrics: Dict[str, Any],
    has_artifact: bool = True,
    training_consistent: bool = True,
) -> Tuple[bool, List[str]]:
    """Check hard blockers that force RESTRICTED.

    Returns (is_blocked, list_of_blocker_reasons).
    """
    blockers = []

    if not has_artifact:
        blockers.append("artifact_missing")

    if not training_consistent:
        blockers.append("training_inconsistent")

    sample_size = metrics.get("sample_size", 0)
    if sample_size < MIN_SAMPLE_SIZE_FLOOR:
        blockers.append(f"sample_size={sample_size} < {MIN_SAMPLE_SIZE_FLOOR}")

    drift = metrics.get("drift", 0.0)
    if drift > MAX_CRITICAL_DRIFT:
        blockers.append(f"critical_drift={drift:.4f} > {MAX_CRITICAL_DRIFT}")

    brier = metrics.get("brier", 1.0)
    if brier > MAX_BRIER_FOR_ANY_PROMOTION:
        blockers.append(f"brier={brier:.4f} > {MAX_BRIER_FOR_ANY_PROMOTION}")

    return len(blockers) > 0, blockers


def compute_evidence_score(
    metrics: Dict[str, Any],
    beats_league: bool = False,
    beats_team: bool = False,
    beats_secondary_baseline: bool = False,
) -> Dict[str, Any]:
    """Compute evidence score for a line in a league.

    Returns dict with total score and component breakdown.
    """
    ece = metrics.get("ece", 1.0)
    brier = metrics.get("brier", 1.0)
    logloss = metrics.get("logloss", 5.0)
    stability = metrics.get("stability", 1.0)
    roi = metrics.get("roi_theoretical", 0.0)
    drift = metrics.get("drift", 0.0)

    cal_score = _score_calibration(ece)
    acc_score = _score_accuracy(brier, logloss)
    bench_score = _score_benchmark(beats_league, beats_team, beats_secondary_baseline)
    stab_score = _score_stability(stability)
    roi_score = _score_roi(roi)
    drift_pen = _penalty_drift(drift)

    total = cal_score + acc_score + bench_score + stab_score + roi_score - drift_pen
    total = max(0.0, min(100.0, total))

    return {
        "total_score": round(total, 1),
        "calibration": round(cal_score, 1),
        "accuracy": round(acc_score, 1),
        "benchmark": round(bench_score, 1),
        "stability": round(stab_score, 1),
        "roi": round(roi_score, 1),
        "drift_penalty": round(drift_pen, 1),
    }


def determine_operational_state(
    metrics: Dict[str, Any],
    has_artifact: bool = True,
    training_consistent: bool = True,
    beats_league: bool = False,
    beats_team: bool = False,
    beats_secondary_baseline: bool = False,
    force_shadow: bool = True,  # Initial deployment flag
) -> Dict[str, Any]:
    """Determine operational state for a corner line in a league.

    Args:
        metrics: Champion model metrics for this line
        has_artifact: Whether valid artifact exists
        training_consistent: Whether training output is consistent
        beats_league/team/secondary: Benchmark comparison results
        force_shadow: If True, cap maximum state at NEUTRAL (SHADOW mode)

    Returns:
        Dict with operational_state, evidence_score, blockers, and reasoning.
    """
    # Check hard blockers first
    is_blocked, blockers = check_hard_blockers(metrics, has_artifact, training_consistent)

    if is_blocked:
        return {
            "operational_state": CornerOperationalState.RESTRICTED,
            "evidence_score": {"total_score": 0},
            "hard_blockers": blockers,
            "reasoning": f"Hard blocked: {', '.join(blockers)}",
            "force_shadow": force_shadow,
        }

    # Compute evidence score
    evidence = compute_evidence_score(
        metrics,
        beats_league=beats_league,
        beats_team=beats_team,
        beats_secondary_baseline=beats_secondary_baseline,
    )
    total_score = evidence["total_score"]

    # Determine state from score
    if total_score >= ACTIVE_MIN_SCORE:
        state = CornerOperationalState.ACTIVE
    elif total_score >= ACTIVE_GUARDED_MIN_SCORE:
        state = CornerOperationalState.ACTIVE_GUARDED
    elif total_score >= NEUTRAL_MIN_SCORE:
        state = CornerOperationalState.NEUTRAL
    else:
        state = CornerOperationalState.RESTRICTED

    # Apply shadow mode cap
    if force_shadow and state in (CornerOperationalState.ACTIVE, CornerOperationalState.ACTIVE_GUARDED):
        original_state = state
        state = CornerOperationalState.NEUTRAL
        reasoning = (
            f"Score={total_score:.1f} → {original_state.value}, "
            f"but capped to NEUTRAL (SHADOW mode active)"
        )
    else:
        reasoning = f"Score={total_score:.1f} → {state.value}"

    return {
        "operational_state": state,
        "evidence_score": evidence,
        "hard_blockers": [],
        "reasoning": reasoning,
        "force_shadow": force_shadow,
    }


def evaluate_all_lines(
    line_metrics: Dict[str, Dict[str, Any]],
    league_id: str = "",
    force_shadow: bool = True,
) -> Dict[str, Any]:
    """Evaluate operational states for all corner lines in a league.

    Args:
        line_metrics: {line_key: {champion model metrics + benchmark flags}}
        league_id: League identifier
        force_shadow: Whether to cap states at NEUTRAL

    Returns:
        Dict with per-line operational states and league summary.
    """
    results = {}

    for line in CORNER_LINES:
        line_key = f"over_{line}"
        metrics = line_metrics.get(line_key, {})

        # Extract benchmark flags from metrics
        beats_league = metrics.pop("beats_baseline_league", False)
        beats_team = metrics.pop("beats_baseline_team", False)
        beats_secondary = metrics.pop("beats_secondary_baseline", False)

        state_result = determine_operational_state(
            metrics=metrics,
            has_artifact=bool(metrics),
            training_consistent=metrics.get("status") != "training_failed",
            beats_league=beats_league,
            beats_team=beats_team,
            beats_secondary_baseline=beats_secondary,
            force_shadow=force_shadow,
        )
        state_result["league_id"] = league_id
        state_result["line"] = line
        results[line_key] = state_result

    # Summary
    states = [r["operational_state"] for r in results.values()]
    state_counts = {}
    for s in states:
        s_val = s.value if hasattr(s, "value") else s
        state_counts[s_val] = state_counts.get(s_val, 0) + 1

    return {
        "league_id": league_id,
        "lines": results,
        "state_distribution": state_counts,
        "force_shadow": force_shadow,
        "any_active": any(
            s in (CornerOperationalState.ACTIVE, CornerOperationalState.ACTIVE_GUARDED)
            for s in states
        ),
    }
