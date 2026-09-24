import type { ReactNode } from "react";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";

/** #262 — moldura de estado vazio (spec §4): monograma apagado e decorativo acima do texto existente. */
export function EstadoVazio({ children, tamanho = 48 }: { children: ReactNode; tamanho?: 48 | 32 }) {
  // 48 px em vazio de pagina inteira; 32 px em bloco vazio dentro de pagina povoada (decisao do dono, #262 pos-approve).
  return (
    <div className="my-6 grid justify-items-center gap-2 text-center text-[14px] text-[var(--sb-texto-apagado)]">
      <MonogramaSBZ tamanho={tamanho} apagado />
      {children}
    </div>
  );
}
