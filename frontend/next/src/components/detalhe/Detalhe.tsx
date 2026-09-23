import { useEffect, useState } from "react";
import type { JogoView } from "@/lib/jogoView";
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { getLedgerAgregado } from "@/lib/ledgerApi";
import { Talao } from "@/components/feed/Talao";
import { EscalaConfianca } from "@/components/detalhe/EscalaConfianca";
import { TabelaMercados } from "@/components/detalhe/TabelaMercados";
import { ComoOModeloVe } from "@/components/detalhe/ComoOModeloVe";
import { DeOndeVemONumero } from "@/components/detalhe/DeOndeVemONumero";
import { fmtDataCurta, fmtHora } from "@/lib/formato";

export function Detalhe({ jogo, confianca }: { jogo: JogoView; confianca: LeagueConfidence | null }) {
  const [nJogosLedger, setNJogosLedger] = useState<number | null>(null);
  useEffect(() => {
    let vivo = true;
    getLedgerAgregado("temporada", undefined, jogo.ligaId).then((r) => {
      if (vivo && r.ok) setNJogosLedger(r.dados.por_liga[jogo.ligaId]?.n_jogos ?? null);
    }).catch(() => {});
    return () => { vivo = false; };
  }, [jogo.ligaId]);

  return (
    <div className="sb-card p-4">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="font-[family-name:var(--font-slab)] text-[22px] font-semibold">{jogo.casa} × {jogo.fora}</h2>
        <span className="tnum text-[13px] text-[var(--sb-texto-apagado)]">{jogo.ligaNome}, {fmtDataCurta(jogo.kickoffIso)}, {fmtHora(jogo.kickoffIso)}</span>
      </header>
      {jogo.talao && <Talao pick={jogo.talao} futuro={jogo.estado === "amanha_sem_preco"} preJogo={jogo.estado === "em_jogo"} />}
      {jogo.talao && (
        <section className="mt-4">
          <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Confiança nesta liga</h3>
          <EscalaConfianca prob01={jogo.talao.prob01} margem={null} nJogos={nJogosLedger} liga={jogo.ligaNome} />
        </section>
      )}
      <section className="mt-6">
        <h3 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">Todos os mercados avaliados ({jogo.totalAvaliados})</h3>
        <div className="overflow-x-auto"><TabelaMercados mercados={jogo.mercados} /></div>
      </section>
      <ComoOModeloVe matchId={jogo.id} />
      <DeOndeVemONumero jogo={jogo} nJogos={nJogosLedger} />
    </div>
  );
}
