/**
 * Single source of truth for the user's bankroll (#190 — audit 2026-08-28: "banca dessincronizada").
 *
 * Before #190 there were two independent localStorage stores:
 *   - "sportsbankzu-bankroll"          → dashboard / Destaques do Dia (plain number)
 *   - "sportsbankzu_bankroll_settings" → Gestao de Banca via kelly.ts (JSON with bankroll)
 * Changing the bankroll on one screen never reflected on the other.
 *
 * This module makes "sportsbankzu-bankroll" the canonical value:
 *   - getBankroll() reads the canonical key and, when absent, migrates the legacy JSON value;
 *   - setBankroll() writes the canonical key, keeps the legacy JSON in sync and notifies
 *     every subscriber (same tab via CustomEvent, other tabs via the storage event);
 *   - useBankroll() is the reactive React hook on top of it.
 */

import { useSyncExternalStore } from "react";

const KEY = "sportsbankzu-bankroll";
const SETTINGS_KEY = "sportsbankzu_bankroll_settings";
const LOCAL_EVENT = "sbz:bankroll-change";

export const DEFAULT_BANKROLL = 1000;

function parsePositive(raw: unknown): number | null {
  const v = typeof raw === "string" ? parseFloat(raw) : typeof raw === "number" ? raw : NaN;
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function getBankroll(): number {
  if (typeof window === "undefined") return DEFAULT_BANKROLL;
  try {
    const canonical = parsePositive(localStorage.getItem(KEY));
    if (canonical !== null) return canonical;
    // Migration: older users may only have a bankroll inside the Gestao de Banca JSON.
    const rawSettings = localStorage.getItem(SETTINGS_KEY);
    if (rawSettings) {
      const legacy = parsePositive(JSON.parse(rawSettings)?.bankroll);
      if (legacy !== null) {
        localStorage.setItem(KEY, String(legacy));
        return legacy;
      }
    }
  } catch {
    /* localStorage unavailable or corrupted JSON — fall through to default */
  }
  return DEFAULT_BANKROLL;
}

export function setBankroll(value: number): void {
  if (typeof window === "undefined") return;
  const v = parsePositive(value);
  if (v === null) return;
  try {
    localStorage.setItem(KEY, String(v));
    // Keep the Gestao de Banca JSON coherent for any direct reader.
    const rawSettings = localStorage.getItem(SETTINGS_KEY);
    if (rawSettings) {
      const settings = JSON.parse(rawSettings);
      if (settings && typeof settings === "object" && settings.bankroll !== v) {
        settings.bankroll = v;
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
      }
    }
  } catch {
    /* no persistence — the event below still propagates the in-memory value */
  }
  try {
    window.dispatchEvent(new CustomEvent(LOCAL_EVENT, { detail: v }));
  } catch {
    /* noop */
  }
}

/** Subscribe to bankroll changes (same tab and cross-tab). Returns the unsubscribe. */
export function subscribeBankroll(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === null || e.key === KEY || e.key === SETTINGS_KEY) onChange();
  };
  const onLocal = () => onChange();
  window.addEventListener("storage", onStorage);
  window.addEventListener(LOCAL_EVENT, onLocal);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(LOCAL_EVENT, onLocal);
  };
}

/** Reactive hook: [bankroll, setBankroll] shared by every screen. */
export function useBankroll(): [number, (v: number) => void] {
  const value = useSyncExternalStore(subscribeBankroll, getBankroll, () => DEFAULT_BANKROLL);
  return [value, setBankroll];
}
