"use client";
import type { Dia } from "@/lib/feedUrl";
const ROTULO: Record<Dia, string> = { ontem: "Ontem", hoje: "Hoje", amanha: "Amanhã" };
export function DiaTabs({ dia, onChange }: { dia: Dia; onChange: (d: Dia) => void }) {
  return (
    <div role="tablist" aria-label="dia" className="flex gap-1 border-b border-[var(--sb-linha)]">
      {(["ontem", "hoje", "amanha"] as Dia[]).map((d) => (
        <button key={d} role="tab" aria-selected={d === dia} onClick={() => onChange(d)}
          className="sb-foco px-3 py-2 text-[14px] aria-selected:border-b-2 aria-selected:border-[var(--sb-texto)] aria-selected:font-semibold">
          {ROTULO[d]}
        </button>
      ))}
    </div>
  );
}
