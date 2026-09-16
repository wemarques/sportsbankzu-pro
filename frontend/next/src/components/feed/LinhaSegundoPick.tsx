import type { PickView } from "@/lib/jogoView";
import { fmtDelta, fmtOdd, fmtPct } from "@/lib/formato";

export function LinhaSegundoPick({ pick }: { pick: PickView }) {
  const preco = pick.bookOdd != null ? `paga ${fmtOdd(pick.bookOdd)} (${fmtDelta(pick.bookOdd - pick.fairOdd)})` : `a partir de ${fmtOdd(pick.fairOdd)}`;
  return (
    <p className="flex justify-between gap-3 text-[14px]">
      <span>{pick.mercado}</span>
      <span className="tnum">{fmtPct(pick.prob01)} em 100, {preco}</span>
    </p>
  );
}
