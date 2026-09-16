import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { fraseConfianca } from "@/lib/confiancaLiga";

/** #256 fix round 1 — `media` chega por prop (buscada UMA vez pelo pai, ver
 * `Feed.tsx`/`Detalhe.tsx`); antes cada card chamava `useMediaDasLigas()` e
 * disparava um fetch identico por card (N cards = N requisicoes a
 * `/ledger/agregado`). `media` opcional com default `null` preserva o piso
 * documentado (`PISO_SEM_DADO` em `confiancaLiga.ts`) para quem nao passa. */
export function LinhaConfianca({ confianca, ligaNome, media = null }: { confianca: LeagueConfidence | null; ligaNome: string; media?: number | null }) {
  const f = fraseConfianca(confianca, ligaNome, media);
  if (f.semBase || f.numero == null) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{f.texto}</p>;
  const [antes, depois] = f.texto.split(String(f.numero));
  return (
    <p className="text-[13px]">
      {antes}<span className="tnum font-semibold text-[var(--sb-confianca)]">{f.numero}</span>{depois}
    </p>
  );
}
