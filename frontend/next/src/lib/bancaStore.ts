/**
 * #254 — banca com estado INDEFINIDO (spec §5). O store antigo (`bankrollStore.ts`)
 * presume 1000; um usuario novo nao pode ver "R$ 25" nascido de uma banca
 * presumida. Mesma chave do store antigo: a banca definida aqui vale la.
 */
import { useSyncExternalStore } from "react";
import { calcQuarterKelly } from "@/components/BankrollCard";

const KEY = "sportsbankzu-bankroll";
const EVENTO = "sbz:bankroll-change";

function positivo(raw: unknown): number | null {
  const v = typeof raw === "string" ? parseFloat(raw) : typeof raw === "number" ? raw : NaN;
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function getBanca(): number | null {
  if (typeof window === "undefined") return null;
  try {
    return positivo(localStorage.getItem(KEY));
  } catch {
    return null;
  }
}

export function setBanca(v: number): "ok" | "invalida" {
  const val = positivo(v);
  if (val === null) return "invalida";
  try {
    localStorage.setItem(KEY, String(val));
  } catch {
    /* sem persistencia: o evento abaixo ainda propaga o valor em memoria */
  }
  try {
    window.dispatchEvent(new CustomEvent(EVENTO, { detail: val }));
  } catch {
    /* noop */
  }
  return "ok";
}

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => { if (e.key === null || e.key === KEY) onChange(); };
  window.addEventListener("storage", onStorage);
  window.addEventListener(EVENTO, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(EVENTO, onChange);
  };
}

export function useBanca(): [number | null, (v: number) => "ok" | "invalida"] {
  const valor = useSyncExternalStore(subscribe, getBanca, () => null);
  return [valor, setBanca];
}

/** Stake em reais. A formula e a do BankrollCard (Quarter Kelly com caps) — nao duplicar. */
export function calcStake(prob01: number, odd: number, banca: number, classification?: string): number {
  return calcQuarterKelly(prob01, odd, banca, classification).stake;
}
