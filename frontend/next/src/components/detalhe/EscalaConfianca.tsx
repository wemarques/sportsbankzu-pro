import { fmtPct } from "@/lib/formato";
export function EscalaConfianca({ prob01, margem, nJogos, liga }: { prob01: number; margem: [number, number] | null; nJogos: number | null; liga: string }) {
  const p = fmtPct(prob01);
  const frase = margem && nJogos != null
    ? `${p} em cada 100, com margem de ${fmtPct(margem[0])} a ${fmtPct(margem[1])}, em ${nJogos} jogos medidos da ${liga}`
    : nJogos != null
      ? `${p} em cada 100 na ${liga}, em ${nJogos} jogos medidos`
      : `${p} em cada 100 na ${liga}`;
  return (
    <figure>
      <div role="img" aria-label={frase} className="relative my-3 h-8">
        <div className="absolute inset-x-0 top-[14px] h-[2px] bg-[var(--sb-linha)]" />
        {[0, 25, 50, 75, 100].map((t) => <div key={t} className="absolute top-[9px] h-3 w-px bg-[var(--sb-linha)]" style={{ left: `${t}%` }} />)}
        {margem && <div className="absolute top-3 h-[6px] rounded-[3px] bg-[var(--sb-confianca)]" style={{ left: `${margem[0] * 100}%`, width: `${(margem[1] - margem[0]) * 100}%` }} />}
        <div className="absolute top-1 h-[22px] w-[2px] bg-[var(--sb-texto)]" style={{ left: `${prob01 * 100}%` }} />
      </div>
      <div className="tnum flex justify-between text-[13px]" aria-hidden="true">
        <span className="text-[var(--sb-texto-apagado)]">0</span>
        <span className="text-[var(--sb-texto-apagado)]">50</span>
        <span className="text-[var(--sb-texto-apagado)]">100</span>
      </div>
      <figcaption className="mt-1 text-[14px]">{frase}</figcaption>
    </figure>
  );
}
