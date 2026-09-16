"use client";
import Link from "next/link";
import type { JogoView } from "@/lib/jogoView";
import type { LeagueConfidence } from "@/hooks/useLeagueClassifications";
import { Talao } from "@/components/feed/Talao";
import { LinhaStake } from "@/components/feed/LinhaStake";
import { LinhaConfianca } from "@/components/feed/LinhaConfianca";
import { LinhaSegundoPick } from "@/components/feed/LinhaSegundoPick";
import { LinhaAvaliados } from "@/components/feed/LinhaAvaliados";
import { avaliados, direcao, resultadoOntem, VAZIOS } from "@/lib/copy";
import { fmtLigaHora } from "@/lib/formato";

interface Props { jogo: JogoView; confianca: LeagueConfidence | null; selecionado: boolean; onAbrir?: (id: string) => void; hrefDetalhe: string; }

/** Nao calcula nada: le `jogo.estado` e escolhe o que mostrar (spec §4.2). */
export function CardJogo({ jogo, confianca, selecionado, onAbrir, hrefDetalhe }: Props) {
  const topo = jogo.aoVivo
    ? `${jogo.aoVivo.periodo ?? ""}${jogo.aoVivo.minuto != null ? `, ${jogo.aoVivo.minuto}'` : ""}${jogo.aoVivo.placar ? ` ${jogo.aoVivo.placar}` : ""}`.trim()
    : fmtLigaHora(jogo.ligaNome, jogo.kickoffIso);
  const corpo = (() => {
    switch (jogo.estado) {
      case "nada":
        return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{avaliados(jogo.totalAvaliados, 0)}</p>;
      case "direcao":
        return (
          <>
            <p className="text-[16px]">{direcao(jogo.direcao!.mercado, jogo.direcao!.prob01)}</p>
            <LinhaConfianca confianca={confianca} ligaNome={jogo.ligaNome} />
            <LinhaAvaliados total={jogo.totalAvaliados} valem={0} href={`${hrefDetalhe}#mercados`} />
          </>
        );
      default: {
        const t = jogo.talao;
        if (!t) return <p className="text-[13px] text-[var(--sb-texto-apagado)]">{avaliados(jogo.totalAvaliados, 0)}</p>;
        return (
          <>
            <Talao pick={t} futuro={jogo.estado === "amanha_sem_preco"} preJogo={jogo.estado === "em_jogo"} />
            {jogo.estado === "ontem" && jogo.resultado && (
              <p className={jogo.resultado.acertou ? "text-[14px]" : "text-[14px] text-[var(--sb-contra-texto)]"}>
                {resultadoOntem(jogo.resultado.acertou, jogo.resultado.detalhe)}
              </p>
            )}
            {jogo.estado === "ontem_sem_desfecho" && <p className="text-[13px] text-[var(--sb-texto-apagado)]">{VAZIOS.resultadoPendente}</p>}
            {(jogo.estado === "vale" || jogo.estado === "em_jogo") && <LinhaStake pick={t} />}
            <LinhaConfianca confianca={confianca} ligaNome={jogo.ligaNome} />
            {jogo.segundo && <LinhaSegundoPick pick={jogo.segundo} />}
            <LinhaAvaliados total={jogo.totalAvaliados} valem={jogo.totalValem} href={`${hrefDetalhe}#mercados`} />
          </>
        );
      }
    }
  })();
  return (
    <article data-estado={jogo.estado} data-selecionado={selecionado}
      className="space-y-2 rounded-[var(--sb-raio-painel)] border border-[var(--sb-linha)] bg-[var(--sb-painel)] p-4 hover:bg-[var(--sb-hover)] data-[selecionado=true]:border-[var(--sb-texto)]">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">
          <Link href={hrefDetalhe} onClick={(e) => { if (onAbrir) { e.preventDefault(); onAbrir(jogo.id); } }} className="sb-foco">
            {jogo.casa} × {jogo.fora}
          </Link>
        </h2>
        <span className="tnum text-[13px] text-[var(--sb-texto-apagado)]">{topo}</span>
      </header>
      {corpo}
    </article>
  );
}
