import { useEffect, useRef, useCallback, useState } from "react";

/**
 * Adaptive polling hook for live score updates.
 *
 * Polls at `liveIntervalMs` when live matches exist, `idleIntervalMs` otherwise.
 * Pauses when the browser tab is hidden (Page Visibility API) to save bandwidth.
 *
 * Based on FootyStats API analysis:
 * - API has ~1min cache on todays-matches (live-scores uses 1min TTL)
 * - 30s polling catches updates as soon as the cache refreshes
 * - 120s when no live matches avoids unnecessary requests
 */
export function useLivePolling(
  fetchFn: () => Promise<void>,
  opts: {
    hasMatches: boolean;
    hasLiveMatches: boolean;
    liveIntervalMs?: number;
    idleIntervalMs?: number;
  },
) {
  const {
    hasMatches,
    hasLiveMatches,
    liveIntervalMs = 30_000,
    idleIntervalMs = 120_000,
  } = opts;

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const wrappedFetch = useCallback(async () => {
    await fetchFn();
    setLastUpdated(new Date());
  }, [fetchFn]);

  useEffect(() => {
    if (!hasMatches) return;

    const pollMs = hasLiveMatches ? liveIntervalMs : idleIntervalMs;

    function startPolling() {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = setInterval(wrappedFetch, pollMs);
    }

    function stopPolling() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    function handleVisibilityChange() {
      if (document.hidden) {
        stopPolling();
      } else {
        // Fetch immediately when tab becomes visible again
        wrappedFetch();
        startPolling();
      }
    }

    startPolling();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [hasMatches, hasLiveMatches, liveIntervalMs, idleIntervalMs, wrappedFetch]);

  return { lastUpdated };
}
