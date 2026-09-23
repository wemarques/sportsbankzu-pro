import type { ReactNode } from "react";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";

/** #262 — moldura de estado vazio (spec §4): monograma apagado e decorativo acima do texto existente. */
export function EstadoVazio({ children }: { children: ReactNode }) {
  return (
    <div className="my-6 grid justify-items-center gap-2 text-center text-[14px] text-[var(--sb-texto-apagado)]">
      <MonogramaSBZ tamanho={48} apagado />
      {children}
    </div>
  );
}
