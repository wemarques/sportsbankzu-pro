import { CARREGANDO } from "@/lib/copy";

/** #262 — esqueleto do desempenho (spec §3): decorativo; so o role="status" ao lado anuncia. */
export function EsqueletoDesempenho() {
  return (
    <div>
      <p role="status" className="sr-only">{CARREGANDO.desempenho}</p>
      <div aria-hidden="true" className="space-y-3">
        <div className="sb-card h-[48px] p-4" />
        <div className="sb-card h-[120px] p-4" />
        <div className="sb-card h-[160px] p-4" />
      </div>
    </div>
  );
}
