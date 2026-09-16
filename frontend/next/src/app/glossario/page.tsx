import Link from "next/link";
import { TERMOS } from "@/lib/glossarioTermos";
import { VAZIOS } from "@/lib/copy";

export const metadata = { title: "Glossário — SportsBankZU Pro" };

export default function GlossarioPage() {
  return (
    <main className="mx-auto max-w-[720px] px-4 py-8 text-[var(--sb-texto)]">
      <h1 className="font-[family-name:var(--font-slab)] text-[28px] font-bold">Glossário</h1>
      <p className="text-[14px]">
        <Link href="/jogos" className="sb-foco underline">
          {VAZIOS.verFeedDeHoje}
        </Link>
      </p>
      <dl className="mt-6 space-y-6">
        {TERMOS.map((t) => (
          <div key={t.id} id={t.id} className="scroll-mt-4 border-t border-[var(--sb-linha)] pt-4">
            <dt className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{t.titulo}</dt>
            <dd className="mt-1 max-w-[70ch] text-[14px]">{t.explicacao}</dd>
            <dd className="tnum mt-1 max-w-[70ch] text-[14px] text-[var(--sb-texto-apagado)]">{t.exemplo}</dd>
          </div>
        ))}
      </dl>
    </main>
  );
}
