"use client";
import { useState } from "react";
import { COPIAR } from "@/lib/copy";

/** Copia so o numero da odd; confirma ou avisa no MESMO slot (sem layout shift). */
export function BotaoCopiar({ odd, sobre = "talao" }: { odd: number; sobre?: "talao" | "painel" }) {
  const [estado, setEstado] = useState<"parado" | "ok" | "falhou">("parado");
  async function copiar() {
    try {
      await navigator.clipboard.writeText(String(odd));
      setEstado("ok");
    } catch {
      setEstado("falhou");
    }
    setTimeout(() => setEstado("parado"), 2500);
  }
  return (
    <span className="inline-flex min-h-[28px] items-center gap-2 text-[14px]">
      {estado === "ok" && <span aria-live="polite">{COPIAR.ok(odd)}</span>}
      {estado === "falhou" && <span aria-live="polite" className="text-[var(--sb-contra-texto)]">{COPIAR.falhou}</span>}
      {estado === "parado" && (
        <button type="button" onClick={copiar} aria-label={COPIAR.rotulo(odd)}
          className={`sb-foco rounded-[4px] border px-2 py-0.5 text-[13px] ${sobre === "talao"
            ? "border-[var(--sb-tinta-apoiada)] text-[var(--sb-tinta-do-talao)]"
            : "border-[var(--sb-linha)] text-[var(--sb-texto)]"}`}>
          copiar
        </button>
      )}
    </span>
  );
}
