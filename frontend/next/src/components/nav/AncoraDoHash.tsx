"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";

/** #257 — o corpo chega por streaming RSC e o navegador nao rola para o fragmento sozinho
 * (medido: scrollY fica 0 em /glossario#stake). Rola ao montar, ao trocar de rota e ao mudar o hash
 * na mesma rota; respeita scroll-margin-top do alvo. */
export function AncoraDoHash() {
  const pathname = usePathname();
  useEffect(() => {
    const rolar = () => {
      const id = window.location.hash.slice(1);
      if (!id) return;
      document.getElementById(id)?.scrollIntoView({ block: "start" });
    };
    rolar();
    window.addEventListener("hashchange", rolar);
    return () => window.removeEventListener("hashchange", rolar);
  }, [pathname]);
  return null;
}
