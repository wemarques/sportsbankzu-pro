import type { LedgerSegmento } from "@/lib/ledgerApi";
import { fmtPct } from "@/lib/formato";

/** #256 — coluna "acerto" usa `resolvidos` (picks individuais com desfecho),
 * NUNCA `n_jogos` (partidas distintas) — o mesmo motivo do `acerto` de topo
 * de `Painel.tsx`: mais de um pick pode acertar na mesma partida, e
 * `acertos/n_jogos` pode passar de 100%. */
export function TabelaSegmentos({ titulo, linhas }: { titulo: string; linhas: Record<string, LedgerSegmento> }) {
  const entradas = Object.entries(linhas).filter(([, s]) => s.picks > 0);
  if (entradas.length === 0) return null;
  return (
    <table className="w-full text-[14px]">
      <caption className="mb-1 text-left font-[family-name:var(--font-slab)] text-[18px] font-semibold">{titulo}</caption>
      <thead><tr className="text-left text-[13px] text-[var(--sb-texto-apagado)]">
        <th scope="col" className="py-1 font-normal">nome</th>
        <th scope="col" className="py-1 text-right font-normal">picks</th>
        <th scope="col" className="py-1 text-right font-normal">acerto</th>
        <th scope="col" className="py-1 text-right font-normal">Brier (menor é melhor)</th>
      </tr></thead>
      <tbody>{entradas.map(([nome, s]) => (
        <tr key={nome} className="border-t border-[var(--sb-linha)]">
          <td className="py-2">{nome}</td>
          <td className="tnum py-2 text-right">{s.picks}</td>
          <td className="tnum py-2 text-right">{s.resolvidos > 0 ? `${fmtPct(s.acertos / s.resolvidos)}%` : "amostra curta"}</td>
          <td className="tnum py-2 text-right">{s.brier != null ? s.brier.toFixed(4) : "amostra curta"}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}
