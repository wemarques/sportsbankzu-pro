"""Lightweight reliability metrics tracker (#101).

Counts safety/robustness/consistency events in-memory.
Reset on Lambda cold start — acceptable for dashboard that shows trends, not totals.
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger("sportsbankzu.reliability")


class ReliabilityTracker:
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._durations: list[float] = []
        self._picks_per_match: list[int] = []
        self._started_at = datetime.utcnow().isoformat()

    def track(self, event: str, count: int = 1):
        self._counters[event] += count

    def track_duration(self, duration_ms: float):
        self._durations.append(duration_ms)
        if len(self._durations) > 500:
            self._durations = self._durations[-500:]

    def track_picks_per_match(self, n: int):
        self._picks_per_match.append(n)
        if len(self._picks_per_match) > 500:
            self._picks_per_match = self._picks_per_match[-500:]

    def get_stats(self) -> dict:
        dur = {}
        if self._durations:
            s = sorted(self._durations)
            dur = {
                "avg_duration_ms": round(statistics.mean(s), 1),
                "p95_duration_ms": round(s[int(len(s) * 0.95)] if len(s) >= 20 else s[-1], 1),
                "cv_duration": round(statistics.stdev(s) / statistics.mean(s), 3) if len(s) > 1 else 0,
            }
        ppm = {}
        if self._picks_per_match:
            ppm = {
                "picks_por_jogo_avg": round(statistics.mean(self._picks_per_match), 1),
                "picks_por_jogo_cv": round(
                    statistics.stdev(self._picks_per_match) / statistics.mean(self._picks_per_match), 3
                ) if len(self._picks_per_match) > 1 else 0,
            }
        return {
            **dict(self._counters),
            **dur,
            **ppm,
            "started_at": self._started_at,
        }


# Singleton — reset on cold start
tracker = ReliabilityTracker()
