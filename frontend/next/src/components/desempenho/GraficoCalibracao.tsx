import type { LedgerBucket } from "@/lib/ledgerApi";
import { fmtPct } from "@/lib/formato";

/** Dispersao pt-BR: eixo x = probabilidade dita, eixo y = frequencia real,
 * diagonal tracejada = calibracao perfeita. Sem biblioteca de grafico — SVG
 * puro, mesmo espirito de EscalaConfianca.tsx (plano 1). */
export function GraficoCalibracao({ buckets }: { buckets: LedgerBucket[] | null }) {
  if (!buckets) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">amostra curta</p>;
  const pontos = buckets.filter(
    (b): b is { prob_media: number; freq_real: number; n: number } => b.n > 0 && b.prob_media != null && b.freq_real != null,
  );
  if (pontos.length === 0) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">amostra curta</p>;

  const W = 260, H = 260, PAD = 24;
  const x = (v: number) => PAD + v * (W - 2 * PAD);
  const y = (v: number) => H - PAD - v * (H - 2 * PAD);
  const pior = pontos.reduce((acc, b) => {
    const d = Math.abs(b.prob_media - b.freq_real);
    return d > acc.d ? { b, d } : acc;
  }, { b: pontos[0], d: -1 });
  const frase = `quando o painel disse ${fmtPct(pior.b.prob_media)}, aconteceu ${fmtPct(pior.b.freq_real)} em cada 100`;

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`Calibração: ${frase}`}>
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--sb-linha)" strokeDasharray="4 4" />
        {pontos.map((b) => (
          <circle key={b.prob_media} cx={x(b.prob_media)} cy={y(b.freq_real)}
            r={3 + Math.min(6, b.n / 10)} className="fill-[var(--sb-confianca)]" />
        ))}
      </svg>
      <figcaption className="mt-1 text-[14px]">{frase}</figcaption>
      <table className="sr-only">
        <caption>Calibração por faixa de probabilidade</caption>
        <thead><tr><th scope="col">probabilidade média</th><th scope="col">frequência real</th><th scope="col">jogos</th></tr></thead>
        <tbody>{pontos.map((b) => (
          <tr key={b.prob_media}><td>{fmtPct(b.prob_media)}</td><td>{fmtPct(b.freq_real)}</td><td>{b.n}</td></tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
