import { CARREGANDO } from "@/lib/copy";

/** #262 — esqueleto do desempenho (spec §3, fix round 1 item 4): blocos
 * `.sb-esqueleto` dentro de cada `.sb-card`, como no `EsqueletoCard` — nao
 * cards vazios sem nenhum bloco. So o role="status" ao lado anuncia. */
export function EsqueletoDesempenho() {
  return (
    <div>
      <p role="status" className="sr-only">{CARREGANDO.desempenho}</p>
      <div aria-hidden="true" className="space-y-3">
        <div className="sb-card space-y-3 p-4">
          <div className="sb-esqueleto h-[18px] w-[40%]" />
        </div>
        <div className="sb-card space-y-3 p-4">
          <div className="sb-esqueleto h-[18px] w-[30%]" />
          <div className="sb-esqueleto h-[14px] w-[90%]" />
          <div className="sb-esqueleto h-[14px] w-[70%]" />
          <div className="sb-esqueleto h-[14px] w-[50%]" />
        </div>
        <div className="sb-card space-y-3 p-4">
          <div className="sb-esqueleto h-[18px] w-[30%]" />
          <div className="sb-esqueleto h-[14px] w-[90%]" />
          <div className="sb-esqueleto h-[14px] w-[75%]" />
          <div className="sb-esqueleto h-[14px] w-[60%]" />
          <div className="sb-esqueleto h-[14px] w-[40%]" />
        </div>
      </div>
    </div>
  );
}
