"use client";
import { useEffect, useState } from "react";
import { getLedgerAgregado } from "@/lib/ledgerApi";

/** #256 — acerto medio de TODAS as ligas na temporada, do ledger (fonte
 * unica). `null` enquanto carrega ou se falhar — quem le decide o piso.
 * Denominador e `resolvidos` (picks com outcome != null), nao `picks`
 * (inclui nao resolvidos) — mesmo denominador usado em todo o resto do
 * ledger (ver `frontend/next/src/lib/ledgerApi.ts`). */
export function useMediaDasLigas(): number | null {
  const [media, setMedia] = useState<number | null>(null);
  useEffect(() => {
    let vivo = true;
    getLedgerAgregado("temporada").then((r) => {
      if (!vivo || !r.ok) return;
      const { resolvidos, acertos } = r.dados.acerto;
      if (resolvidos > 0) setMedia(Number((acertos / resolvidos).toFixed(4)));
    }).catch(() => {});
    return () => { vivo = false; };
  }, []);
  return media;
}
