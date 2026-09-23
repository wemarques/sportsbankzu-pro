"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useBanca } from "@/lib/bancaStore";
import { getLedgerAgregado, getLedgerPicks, type LedgerAgregado } from "@/lib/ledgerApi";
import { retornoRetroativo } from "@/lib/retornoRetroativo";
import { lerDesempenhoUrl, escreverDesempenhoUrl, periodoPorExtenso, type Periodo } from "@/lib/desempenhoUrl";
import { ACTIVE_LEAGUES } from "@/lib/leagues";
import { fmtPct, fmtReais, fmtHora } from "@/lib/formato";
import { fraseAcerto, DESEMPENHO, CARIMBO } from "@/lib/copy";
import { TabelaSegmentos } from "@/components/desempenho/TabelaSegmentos";
import { GraficoCalibracao } from "@/components/desempenho/GraficoCalibracao";
import { EsqueletoDesempenho } from "@/app/desempenho/EsqueletoDesempenho";

const ROTULO: Record<Periodo, string> = { "7d": "7 dias", "30d": "30 dias", temporada: "Temporada" };

function BlocoRetorno({ periodo, familia, liga }: { periodo: Periodo; familia: string | null; liga: string | null }) {
  const [banca] = useBanca();
  const [retorno, setRetorno] = useState<{ valor: number; pctBanca: number; n: number } | null>(null);
  const [semPicks, setSemPicks] = useState(false);
  const geracao = useRef(0);

  useEffect(() => {
    if (banca == null) { setRetorno(null); setSemPicks(false); return; }
    const minha = ++geracao.current;
    getLedgerPicks(periodo, familia ?? undefined, liga ?? undefined).then((r) => {
      if (minha !== geracao.current) return;   // outra carga mais nova ja partiu (mesma guarda de Feed.tsx)
      if (!r.ok) { setRetorno(null); setSemPicks(false); return; }
      const calculo = retornoRetroativo(r.dados.picks, banca);
      if (calculo.n === 0) { setRetorno(null); setSemPicks(true); return; }
      setSemPicks(false);
      setRetorno(calculo);
    });
  }, [periodo, familia, liga, banca]);

  if (banca == null) {
    return (
      <p className="text-[14px] text-[var(--sb-texto-apagado)]">
        {DESEMPENHO.definaBanca}{" "}
        <Link href="/banca" className="sb-foco underline">definir banca</Link>
      </p>
    );
  }
  if (semPicks) return <p className="text-[14px] text-[var(--sb-texto-apagado)]">{DESEMPENHO.retornoSemPicks}</p>;
  if (!retorno) return null;
  return (
    <p className="tnum text-[16px]">
      {fmtReais(retorno.valor)} ({fmtPct(retorno.pctBanca)}%) — {DESEMPENHO.retornoNaBancaAtual} ({retorno.n} picks com preço)
    </p>
  );
}

export function Painel() {
  const router = useRouter();
  const params = useSearchParams();
  const url = useMemo(() => lerDesempenhoUrl(params), [params]);
  const [dados, setDados] = useState<LedgerAgregado | null>(null);
  const [erro, setErro] = useState(false);
  const [carimbo, setCarimbo] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    getLedgerAgregado(url.periodo, url.familia ?? undefined, url.liga ?? undefined).then((r) => {
      if (!vivo) return;
      if (!r.ok) { setErro(true); return; }
      setErro(false); setDados(r.dados); setCarimbo(fmtHora(new Date().toISOString()));
    });
    return () => { vivo = false; };
  }, [url.periodo, url.familia, url.liga]);

  const ir = (mudanca: Partial<typeof url>) => router.replace(escreverDesempenhoUrl({ ...url, ...mudanca }));

  if (erro) return <p className="p-4 text-[14px]">Os dados de desempenho não carregaram.</p>;
  if (!dados) return <div className="mx-auto max-w-[900px] px-4 py-6"><EsqueletoDesempenho /></div>;

  // #256: nunca dividir por resolvidos == 0 — jogos == 0 implica resolvidos
  // == 0 (jogos so existe entre picks resolvidos), checar resolvidos e o
  // mais direto (a condicao que a divisao de fraseAcerto depende).
  const semPicksFechados = dados.acerto.resolvidos === 0;
  const periodoMaior: Periodo = url.periodo === "7d" ? "30d" : "temporada";

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 text-[var(--sb-texto)]">
      {carimbo && <p className="tnum text-right text-[12px] text-[var(--sb-texto-apagado)]" data-carimbo>{CARIMBO.lidoAs(carimbo)}</p>}
      <h1 className="font-[family-name:var(--font-slab)] text-[28px] font-bold">Desempenho</h1>
      <div role="tablist" aria-label="período" className="mt-3 flex gap-1 border-b border-[var(--sb-linha)]">
        {(["7d", "30d", "temporada"] as Periodo[]).map((p) => (
          <button key={p} role="tab" aria-selected={p === url.periodo} onClick={() => ir({ periodo: p })}
            className="sb-foco px-3 py-2 text-[14px] aria-selected:border-b-2 aria-selected:border-[var(--sb-texto)] aria-selected:font-semibold">
            {ROTULO[p]}
          </button>
        ))}
        <span className="tnum ml-2 self-center text-[13px] text-[var(--sb-texto-apagado)]">
          {periodoPorExtenso(url.periodo, new Date())}
        </span>
      </div>

      {semPicksFechados ? (
        <p className="my-6 text-[14px] text-[var(--sb-texto-apagado)]">
          {DESEMPENHO.semPicksFechados} —{" "}
          <Link href={escreverDesempenhoUrl({ ...url, periodo: periodoMaior })} className="sb-foco underline">
            ver {periodoMaior === "30d" ? "30 dias" : "a temporada"}
          </Link>
        </p>
      ) : (
        <>
          <section className="mt-6">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloAcerto}</h2>
            <p className="tnum text-[16px]">{fraseAcerto(dados.acerto.acertos, dados.acerto.resolvidos, dados.acerto.jogos)}</p>
          </section>

          <section className="mt-4">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloRetorno}</h2>
            <BlocoRetorno periodo={url.periodo} familia={url.familia} liga={url.liga} />
          </section>

          <section className="mt-6"><div className="overflow-x-auto"><TabelaSegmentos titulo="Por família" linhas={dados.por_familia} /></div></section>

          <section className="mt-6">
            <h2 className="font-[family-name:var(--font-slab)] text-[18px] font-semibold">{DESEMPENHO.tituloCalibracao}</h2>
            <GraficoCalibracao buckets={dados.buckets} />
          </section>

          <section className="mt-6">
            <div className="overflow-x-auto"><TabelaSegmentos titulo="Por liga" linhas={dados.por_liga} /></div>
          </section>
        </>
      )}

      <div className="mt-6 flex flex-wrap gap-2 text-[13px]">
        {ACTIVE_LEAGUES().map((l) => (
          <button key={l.id} aria-pressed={url.liga === l.id} onClick={() => ir({ liga: url.liga === l.id ? null : l.id })}
            className="sb-foco rounded-full border border-[var(--sb-linha)] px-3 py-1 aria-pressed:border-[var(--sb-texto)]">
            {l.name}
          </button>
        ))}
      </div>
    </div>
  );
}
