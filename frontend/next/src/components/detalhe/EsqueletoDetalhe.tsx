/** #262 — esqueleto do detalhe (spec §3): decorativo; usado enquanto /jogos/[id] busca o jogo. */
export function EsqueletoDetalhe() {
  return (
    <div aria-hidden="true" className="sb-card space-y-3 p-4">
      <div className="sb-esqueleto h-[22px] w-[60%]" />
      <div className="sb-esqueleto h-[72px] w-full" />
      <div className="sb-esqueleto h-[14px] w-[80%]" />
      <div className="sb-esqueleto h-[120px] w-full" />
    </div>
  );
}
