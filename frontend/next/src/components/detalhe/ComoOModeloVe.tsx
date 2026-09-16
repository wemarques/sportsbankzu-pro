"use client";
import { useEffect, useState } from "react";
import { getAiMatchAnalysis } from "@/lib/api";
/** Texto narrativo (contrato Mistral #082). Indisponivel → a secao SOME inteira (spec §5). */
export function ComoOModeloVe({ matchId }: { matchId: string }) {
  const [texto, setTexto] = useState<{ summary: string; key_points: string[] } | null>(null);
  useEffect(() => {
    let vivo = true;
    getAiMatchAnalysis(matchId).then((r) => { if (vivo && r && r.confidence > 0) setTexto({ summary: r.summary, key_points: r.key_points ?? [] }); }).catch(() => {});
    return () => { vivo = false; };
  }, [matchId]);
  if (!texto) return null;
  return (
    <section className="mt-6">
      <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Como o modelo vê o jogo</h3>
      <p className="mt-2 max-w-[70ch] text-[14px]">{texto.summary}</p>
      {texto.key_points.length > 0 && <ul className="mt-2 list-disc pl-5 text-[14px]">{texto.key_points.map((k) => <li key={k}>{k}</li>)}</ul>}
    </section>
  );
}
