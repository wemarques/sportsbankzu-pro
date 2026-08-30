/**
 * Pick ledger (#192): freezes the published prognosis per match so a page refresh
 * can never change it after kickoff.
 *
 * Root causes of the instability (audit follow-up 2026-08-30, e.g. Real Madrid x
 * Malaga: "Under 4.5 gols" pre-match became "Under 9.5 escanteios" after FT):
 *   1. Post-match recompute — FootyStats stats/odds change once the game ends, so
 *      re-running the pipeline yields different picks (backend already skips
 *      calibration/ML for finished games, but raw inputs still shift).
 *   2. Intermittent odds enrichment — API-Football fan-out batches fail randomly
 *      (HTTP_ERROR); a refresh without odds reclassifies markets differently than
 *      the previous refresh that had them.
 *
 * Strategy (client-side, source-agnostic):
 *   - While a match has NOT started: snapshot its picks; only replace the snapshot
 *     when the new fetch is at least as rich in odds (never downgrade to an
 *     odds-less recompute caused by an enrichment failure).
 *   - Once the match started (live/finished or kickoff time passed): always render
 *     the frozen snapshot; the fresh recompute is discarded for display.
 *
 * The ledger lives in localStorage ("sportsbankzu-pick-ledger"), keyed by
 * home|away|date (stable across sources and refetches), pruned to 14 days.
 */

import type { Match, MatchPrediction, RejectedInsight } from "./leagues";

const LEDGER_KEY = "sportsbankzu-pick-ledger";
const MAX_AGE_DAYS = 14;
const MAX_ENTRIES = 600;

export type FrozenReason = "kickoff" | "degraded";

interface LedgerEntry {
  savedAt: string;
  kickoff: string;
  predictions: MatchPrediction[];
  rejectedInsights?: RejectedInsight[];
  oddsCount: number;
}

type Ledger = Record<string, LedgerEntry>;

function normName(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

/** Stable key across refetches and sources: teams + calendar date. */
export function ledgerKey(m: Match): string {
  const date = (m.datetime ?? "").slice(0, 10);
  return `${normName(m.homeTeam?.name ?? "")}|${normName(m.awayTeam?.name ?? "")}|${date}`;
}

function loadLedger(): Ledger {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(LEDGER_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Ledger) : {};
  } catch {
    return {};
  }
}

function saveLedger(ledger: Ledger): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LEDGER_KEY, JSON.stringify(ledger));
  } catch {
    /* quota exceeded or unavailable — freezing degrades gracefully to live data */
  }
}

function prune(ledger: Ledger): Ledger {
  const cutoff = Date.now() - MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
  let entries = Object.entries(ledger).filter(([, e]) => {
    const t = Date.parse(e.savedAt);
    return Number.isFinite(t) && t >= cutoff;
  });
  if (entries.length > MAX_ENTRIES) {
    entries = entries
      .sort((a, b) => Date.parse(b[1].savedAt) - Date.parse(a[1].savedAt))
      .slice(0, MAX_ENTRIES);
  }
  return Object.fromEntries(entries);
}

function oddsCount(predictions: MatchPrediction[] | undefined): number {
  return (predictions ?? []).filter((p) => p.odds_available || (p.book_odd ?? 0) > 1).length;
}

function hasStarted(m: Match): boolean {
  if (m.status === "live" || m.status === "finished") return true;
  const kickoff = Date.parse(m.datetime ?? "");
  return Number.isFinite(kickoff) && Date.now() >= kickoff;
}

/**
 * Apply the ledger to a freshly fetched match. Returns the match to render:
 * either the fresh one (and the snapshot is created/refreshed) or the frozen one.
 * In-memory batching: callers pass a shared ledger via begin/commit so a full
 * fetch of ~50 matches does one localStorage read and one write.
 */
export function applyPickLedger(m: Match, ledger: Ledger): Match {
  if (typeof window === "undefined") return m;
  if (!m.predictions || !Array.isArray(m.predictions)) return m;
  const key = ledgerKey(m);
  const entry = ledger[key];
  const started = hasStarted(m);

  if (!started) {
    const freshOdds = oddsCount(m.predictions);
    if (!entry || freshOdds >= entry.oddsCount) {
      // Fresh data is at least as rich — it becomes the new snapshot.
      ledger[key] = {
        savedAt: new Date().toISOString(),
        kickoff: m.datetime ?? "",
        predictions: m.predictions,
        rejectedInsights: m.rejectedInsights,
        oddsCount: freshOdds,
      };
      return m;
    }
    // Degraded recompute (odds enrichment failed this refresh) — keep showing the snapshot.
    return {
      ...m,
      predictions: entry.predictions,
      rejectedInsights: entry.rejectedInsights ?? m.rejectedInsights,
      picksFrozen: "degraded",
      picksFrozenAt: entry.savedAt,
    };
  }

  // Match started: the published prognosis is immutable from here on.
  if (entry) {
    return {
      ...m,
      predictions: entry.predictions,
      rejectedInsights: entry.rejectedInsights ?? m.rejectedInsights,
      picksFrozen: "kickoff",
      picksFrozenAt: entry.savedAt,
    };
  }
  // First time we ever see this match and it already started: freeze what we have now.
  ledger[key] = {
    savedAt: new Date().toISOString(),
    kickoff: m.datetime ?? "",
    predictions: m.predictions,
    rejectedInsights: m.rejectedInsights,
    oddsCount: oddsCount(m.predictions),
  };
  return { ...m, picksFrozen: "kickoff", picksFrozenAt: ledger[key].savedAt };
}

/** Read the ledger once for a batch of matches. */
export function beginLedgerBatch(): Ledger {
  return loadLedger();
}

/** Persist the (possibly mutated) ledger after a batch, pruned. */
export function commitLedgerBatch(ledger: Ledger): void {
  saveLedger(prune(ledger));
}

/** Convenience: apply to a whole list with a single read/write. */
export function applyPickLedgerToAll(matches: Match[]): Match[] {
  if (typeof window === "undefined") return matches;
  const ledger = beginLedgerBatch();
  const out = matches.map((m) => applyPickLedger(m, ledger));
  commitLedgerBatch(ledger);
  return out;
}
