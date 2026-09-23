import { fonteMarca } from "@/components/marca/fonteMarca";

/** #262 — monograma "SBZ" (spec §4): teal sobre tinta, canto 4 px. So versao escura. */
export function MonogramaSBZ({ tamanho = 24, decorativo = true, apagado = false }: { tamanho?: number; decorativo?: boolean; apagado?: boolean }) {
  const cor = apagado ? "var(--sb-texto-apagado)" : "var(--sb-marca)";
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 64 64" aria-hidden={decorativo ? "true" : undefined} role={decorativo ? undefined : "img"} className={fonteMarca.className}>
      {!decorativo && <title>sportsbankzu</title>}
      <rect width="64" height="64" rx="10" fill="var(--sb-tinta)" />
      <text x="32" y="43" textAnchor="middle" fontSize="30" fontWeight="700" letterSpacing="1" fill={cor}>SBZ</text>
    </svg>
  );
}
