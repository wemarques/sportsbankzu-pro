import Link from "next/link";
import type { JogoView } from "@/lib/jogoView";
import { fraseOrigem } from "@/lib/copy";
export function DeOndeVemONumero({ jogo, nJogos }: { jogo: JogoView; nJogos: number | null }) {
  const frase = fraseOrigem(jogo.origem, jogo.casa, jogo.fora, jogo.ligaNome);
  if (!frase && nJogos == null) return null;
  return (
    <section className="mt-6 text-[14px]">
      <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">De onde vem o número</h3>
      {frase && <p className="mt-2 max-w-[70ch]">{frase}</p>}
      {nJogos != null && <p className="mt-1 text-[var(--sb-texto-apagado)]">{nJogos} jogos medidos — <Link href="/desempenho" className="sb-foco underline">ver calibração</Link></p>}
    </section>
  );
}
