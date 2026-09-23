/** #262 — card-esqueleto (spec §3): decorativo; so o role="status" da lista anuncia. */
export function EsqueletoCard() {
  return (
    <div aria-hidden="true" className="sb-card space-y-3 p-4">
      <div className="sb-esqueleto h-[18px] w-[55%]" />
      <div className="sb-esqueleto h-[72px] w-full" />
      <div className="sb-esqueleto h-[14px] w-[70%]" />
      <div className="sb-esqueleto h-[14px] w-[45%]" />
    </div>
  );
}
