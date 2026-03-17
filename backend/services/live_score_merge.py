"""
Centralized live score merge logic.

Resolves the final score for a live match from multiple data sources
using a priority-based approach with safety guards.

Source priority (highest to lowest):
1. API-Football (real-time, most reliable for live matches)
2. FootyStats /match detail endpoint (30s cache, individual match)
3. FootyStats todays-matches endpoint (5min cache, bulk listing)
4. Fallback 0-0 (only when no source has data)

Rules:
- A higher-priority source always wins UNLESS it reports fewer total
  goals than a lower-priority source that already ran (monotonic guard).
- Monotonic guard: total goals can only stay the same or increase across
  successive merge steps within the same polling cycle.
- If all sources return None/missing, fall back to 0-0.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sportsbankzu.live_score_merge")


# Source priority constants (lower number = higher priority)
SOURCE_TODAYS_MATCHES = "todays_matches"
SOURCE_MATCH_DETAIL = "match_detail"
SOURCE_API_FOOTBALL = "api_football"
SOURCE_FALLBACK = "fallback_0_0"

# Priority ordering (lower = better)
_SOURCE_PRIORITY = {
    SOURCE_API_FOOTBALL: 1,
    SOURCE_MATCH_DETAIL: 2,
    SOURCE_TODAYS_MATCHES: 3,
    SOURCE_FALLBACK: 99,
}


@dataclass
class ScoreCandidate:
    """A score reading from a single data source."""
    home: Optional[int] = None
    away: Optional[int] = None
    source: str = SOURCE_FALLBACK
    has_data: bool = False

    @property
    def total(self) -> int:
        return (self.home or 0) + (self.away or 0)

    @property
    def is_valid(self) -> bool:
        return self.home is not None and self.away is not None


@dataclass
class MergeResult:
    """Result of merging multiple score candidates."""
    home: int = 0
    away: int = 0
    source: str = SOURCE_FALLBACK
    conflict_detected: bool = False
    conflict_detail: str = ""
    candidates_seen: List[str] = field(default_factory=list)
    stale_ignored: bool = False

    @property
    def total(self) -> int:
        return self.home + self.away


def merge_live_scores(
    todays: Optional[ScoreCandidate] = None,
    detail: Optional[ScoreCandidate] = None,
    api_football: Optional[ScoreCandidate] = None,
    match_label: str = "",
) -> MergeResult:
    """Merge score candidates from multiple sources into a single authoritative score.

    Applies priority-based resolution with a monotonic guard:
    scores can only increase (or stay the same) as higher-priority
    sources are applied.

    Args:
        todays: Score from FootyStats todays-matches (lowest priority)
        detail: Score from FootyStats /match detail endpoint
        api_football: Score from API-Football (highest priority)
        match_label: Human-readable match label for logging

    Returns:
        MergeResult with final score, source, and diagnostics
    """
    result = MergeResult()

    # Collect candidates in priority order (lowest priority first, so
    # higher-priority sources overwrite)
    candidates: List[ScoreCandidate] = []
    if todays and todays.is_valid:
        todays.source = todays.source or SOURCE_TODAYS_MATCHES
        candidates.append(todays)
    if detail and detail.is_valid:
        detail.source = detail.source or SOURCE_MATCH_DETAIL
        candidates.append(detail)
    if api_football and api_football.is_valid:
        api_football.source = api_football.source or SOURCE_API_FOOTBALL
        candidates.append(api_football)

    result.candidates_seen = [c.source for c in candidates]

    if not candidates:
        # No valid data from any source → fallback 0-0
        result.source = SOURCE_FALLBACK
        logger.info(f"[merge] {match_label}: no score data from any source, using 0-0")
        return result

    # Apply candidates from lowest to highest priority.
    # Each step enforces the monotonic guard.
    current_total = -1

    for candidate in candidates:
        c_total = candidate.total
        c_priority = _SOURCE_PRIORITY.get(candidate.source, 50)

        if c_total >= current_total:
            # Higher or equal total → accept
            result.home = candidate.home
            result.away = candidate.away
            result.source = candidate.source
            current_total = c_total
        else:
            # Higher-priority source reports FEWER goals → conflict
            result.conflict_detected = True
            result.stale_ignored = True
            conflict_msg = (
                f"{candidate.source} reports {candidate.home}-{candidate.away} "
                f"(total={c_total}) but current best is "
                f"{result.home}-{result.away} (total={current_total}) "
                f"from {result.source}"
            )
            result.conflict_detail = conflict_msg
            logger.warning(f"[merge] {match_label}: CONFLICT — {conflict_msg}")

            # Exception: if the higher-priority source has a STRICTLY higher
            # priority rating AND same total but different distribution
            # (e.g., detail=1-0 vs todays=0-1), trust the higher-priority source.
            cur_priority = _SOURCE_PRIORITY.get(result.source, 50)
            if c_total == current_total and c_priority < cur_priority:
                result.home = candidate.home
                result.away = candidate.away
                result.source = candidate.source
                result.stale_ignored = False
                logger.info(
                    f"[merge] {match_label}: lateral conflict resolved by priority — "
                    f"using {candidate.source} ({candidate.home}-{candidate.away})"
                )

    if result.conflict_detected:
        logger.info(
            f"[merge] {match_label}: final={result.home}-{result.away} "
            f"source={result.source} conflict={result.conflict_detail}"
        )
    else:
        logger.debug(
            f"[merge] {match_label}: final={result.home}-{result.away} source={result.source}"
        )

    return result
