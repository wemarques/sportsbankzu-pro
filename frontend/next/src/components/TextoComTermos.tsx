import Link from "next/link";
import { comTermos } from "@/lib/copy";
import { TERMOS } from "@/lib/glossarioTermos";

/** #257 — primeiro consumidor de `comTermos` (fase 0, `lib/copy.ts`): um
 * template com `{term:<id>|<texto>}` vira texto com link embutido para o
 * glossário, sem o componente que chama precisar saber o formato. */
export function TextoComTermos({ texto }: { texto: string }) {
  const obterTituloTermo = (id: string): string => {
    const termo = TERMOS.find((t) => t.id === id);
    return termo?.titulo || id;
  };

  return (
    <>
      {comTermos(texto).map((trecho, i) => {
        if ("termo" in trecho) {
          const titulo = obterTituloTermo(trecho.termo);
          const ariaLabel = `${trecho.texto} — o que é ${titulo}`;
          return (
            <Link
              key={i}
              href={`/glossario#${trecho.termo}`}
              className="sb-foco underline"
              aria-label={ariaLabel}
              title={ariaLabel}
            >
              {trecho.texto}
            </Link>
          );
        }
        return <span key={i}>{trecho.texto}</span>;
      })}
    </>
  );
}
