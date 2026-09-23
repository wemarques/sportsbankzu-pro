"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fonteMarca } from "@/components/marca/fonteMarca";
import { MonogramaSBZ } from "@/components/marca/MonogramaSBZ";
import { fmtDataPorExtenso, proximaMeiaNoiteBrt } from "@/lib/formato";
import { MARCA } from "@/lib/copy";

/** #262 — barra fixa de 56 px em todas as rotas: marca + data do operador (BRT).
 * O carimbo de leitura NAO mora aqui (spec §1): e da rota.
 * Data e so-cliente (#262 fix wave): a rota e pre-renderizada no build e a data ficaria
 * velha no primeiro paint. Enquanto `agora` e null, renderiza um placeholder de largura
 * fixa para nao deslocar a barra; o timer de virada de meia-noite so roda apos o mount. */
export function Cabecalho() {
  const [agora, setAgora] = useState<Date | null>(null);
  useEffect(() => { setAgora(new Date()); }, []);
  useEffect(() => {
    if (!agora) return;
    const t = setTimeout(() => setAgora(new Date()), proximaMeiaNoiteBrt(agora).getTime() - agora.getTime() + 1000);
    return () => clearTimeout(t);
  }, [agora]);
  return (
    <header role="banner" className="fixed inset-x-0 top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--sb-linha)] bg-[var(--sb-painel)] px-4">
      <Link href="/jogos" aria-label={MARCA.ariaLink} className="sb-foco flex items-center gap-2 no-underline">
        <MonogramaSBZ tamanho={22} />
        <span className={`${fonteMarca.className} text-[22px] font-bold leading-none tracking-tight text-[var(--sb-texto)]`}>{MARCA.parte1}<span className="text-[var(--sb-marca)]">{MARCA.parte2}</span></span>
      </Link>
      {agora ? (
        <span className="hidden text-[14px] text-[var(--sb-texto-apagado)] sm:block">{fmtDataPorExtenso(agora)}</span>
      ) : (
        <span aria-hidden="true" className="hidden sm:block w-[180px]" />
      )}
    </header>
  );
}
