import Link from "next/link";
import { comTermos } from "@/lib/copy";

/** #257 — primeiro consumidor de `comTermos` (fase 0, `lib/copy.ts`): um
 * template com `{term:<id>|<texto>}` vira texto com link embutido para o
 * glossário, sem o componente que chama precisar saber o formato. */
export function TextoComTermos({ texto }: { texto: string }) {
  return (
    <>
      {comTermos(texto).map((trecho, i) =>
        "termo" in trecho
          ? <Link key={i} href={`/glossario#${trecho.termo}`} className="sb-foco underline">{trecho.texto}</Link>
          : <span key={i}>{trecho.texto}</span>,
      )}
    </>
  );
}
