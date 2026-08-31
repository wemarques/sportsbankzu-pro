"use client";

import { useEffect, useState } from "react";

/**
 * Tique compartilhado para o relógio ao vivo.
 *
 * O minuto exibido é interpolado por `getLiveClock` a partir de `Date.now()`,
 * então a UI precisa re-renderizar entre um poll e outro. Antes isso era feito
 * com `setAllMatches(prev => [...prev])` a cada 30s — uma escrita de estado
 * inteira só para forçar render. Aqui um único `setInterval` global alimenta
 * todos os assinantes e pausa quando a aba fica oculta.
 */

const TICK_MS = 10_000;

const subscribers = new Set<(now: number) => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function broadcast() {
  const now = Date.now();
  subscribers.forEach((fn) => fn(now));
}

function ensureTimer() {
  if (timer != null) return;
  timer = setInterval(() => {
    if (typeof document !== "undefined" && document.hidden) return;
    broadcast();
  }, TICK_MS);
}

function maybeStopTimer() {
  if (subscribers.size === 0 && timer != null) {
    clearInterval(timer);
    timer = null;
  }
}

/**
 * Devolve um timestamp que avança a cada TICK_MS enquanto `enabled` for true.
 * Ao voltar de uma aba oculta, atualiza imediatamente.
 */
export function useLiveTick(enabled: boolean = true): number {
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    if (!enabled) return;

    const onTick = (n: number) => setNow(n);
    subscribers.add(onTick);
    ensureTimer();

    const onVisibility = () => {
      if (!document.hidden) setNow(Date.now());
    };
    document.addEventListener("visibilitychange", onVisibility);

    // Sincroniza no momento da inscrição.
    setNow(Date.now());

    return () => {
      subscribers.delete(onTick);
      document.removeEventListener("visibilitychange", onVisibility);
      maybeStopTimer();
    };
  }, [enabled]);

  return now;
}
