import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { fraseConfianca } from "@/lib/confiancaLiga";
import { useMediaDasLigas } from "@/hooks/useMediaDasLigas";

export function LinhaConfianca({ confianca, ligaNome }: { confianca: LeagueConfidence | null; ligaNome: string }) {
  const media = useMediaDasLigas();
  const f = fraseConfianca(confianca, ligaNome, media);
  if (f.semBase || f.numero == null) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{f.texto}</p>;
  const [antes, depois] = f.texto.split(String(f.numero));
  return (
    <p className="text-[13px]">
      {antes}<span className="tnum font-semibold text-[var(--sb-confianca)]">{f.numero}</span>{depois}
    </p>
  );
}
