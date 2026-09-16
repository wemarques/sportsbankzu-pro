import type { PickView } from "@/lib/jogoView";
import { frequencia, linhaPreco, VAZIOS } from "@/lib/copy";
import { BotaoCopiar } from "@/components/feed/BotaoCopiar";

/**
 * O pick recomendado — o unico objeto amarelo da tela (spec §4.1). Dentro
 * dele so `tinta-do-talao` e `tinta-apoiada`; `confianca` nunca entra (1,7:1).
 */
export function Talao({ pick, futuro, preJogo }: { pick: PickView; futuro: boolean; preJogo: boolean }) {
  const preco = linhaPreco(pick.bookOdd, pick.fairOdd, futuro);
  return (
    <section className="sb-talao relative my-3 rounded-[var(--sb-raio-talao)] bg-[var(--sb-talao)] px-4 pb-3 pt-4 text-[var(--sb-tinta-do-talao)]"
      aria-label="pick recomendado">
      <h3 className="font-[family-name:var(--font-slab)] text-[28px] font-bold leading-[1.05]">{pick.mercado}</h3>
      <p className="mt-1 text-[14px] text-[var(--sb-tinta-apoiada)]">{frequencia(pick.prob01)}</p>
      <div className="my-3 border-t border-dashed border-[var(--sb-tinta-apoiada)]" aria-hidden="true" />
      <p className="tnum text-[14px] font-semibold" data-estado={preco.abaixo ? "abaixo" : preco.semPreco ? "sem-preco" : "acima"}>
        {preco.abaixo ? "↓ " : ""}{preco.texto}
        {preJogo && <span className="ml-2 font-normal text-[var(--sb-tinta-apoiada)]">{VAZIOS.recomendacaoPreJogo}</span>}
      </p>
      {!preco.semPreco && pick.bookOdd != null && (
        <div className="mt-2 flex justify-end"><BotaoCopiar odd={pick.bookOdd} /></div>
      )}
    </section>
  );
}
