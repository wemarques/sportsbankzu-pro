import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { fraseConfianca } from "@/lib/confiancaLiga";

export function LinhaConfianca({ confianca, ligaNome }: { confianca: LeagueConfidence | null; ligaNome: string }) {
  const f = fraseConfianca(confianca, ligaNome);
  if (f.semBase || f.numero == null) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{f.texto}</p>;
  const [antes, depois] = f.texto.split(String(f.numero));
  return (
    <p className="text-[13px]">
      {antes}<span className="tnum font-semibold text-[var(--sb-confianca)]">{f.numero}</span>{depois}
    </p>
  );
}
