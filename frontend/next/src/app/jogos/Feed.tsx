"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getMatchesByLeague } from "@/lib/api";
import { ACTIVE_LEAGUES, toBackendLeagueId, type Match } from "@/lib/leagues";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { lerFeedUrl, escreverFeedUrl, diaParaApi, diaISOOntem, type Dia } from "@/lib/feedUrl";
import { getLedgerDia } from "@/lib/ledgerApi";
import { agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import { useLeagueClassifications } from "@/hooks/useLeagueClassifications";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useLivePolling } from "@/hooks/useLivePolling";
import { fmtHora, fmtDataCurta } from "@/lib/formato";
import { VAZIOS } from "@/lib/copy";
import Link from "next/link";
import { DiaTabs } from "@/components/feed/DiaTabs";
import { LigaChips } from "@/components/feed/LigaChips";
import { CardJogo } from "@/components/feed/CardJogo";
import { ResumoDoDia } from "@/components/feed/ResumoDoDia";
import { Detalhe } from "@/components/detalhe/Detalhe";

export function Feed() {
  const router = useRouter();
  const params = useSearchParams();
  const url = useMemo(() => lerFeedUrl(params), [params]);
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const confianca = useLeagueClassifications();
  // #254-b: id do chip/URL no slug curto do backend (ex. "mls"), nao no id
  // prefixado do frontend (ex. "usa-mls") — e o que o filtro `.endsWith`
  // abaixo e o teste e2e esperam. Decisao minha: o snippet do brief usava
  // `l.id` puro, o que quebra o clique no chip de liga (ver relatorio).
  const ligas = useMemo(() => ACTIVE_LEAGUES().map((l) => ({ id: toBackendLeagueId(l.id), nome: l.name })), []);

  const [jogos, setJogos] = useState<JogoView[]>([]);
  const [carimbo, setCarimbo] = useState<string | null>(null);   // hora do ultimo feed bom
  const [erro, setErro] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [resumoOntem, setResumoOntem] = useState<{ picks: number; acertos: number; jogos: number; resolvidos: number } | null>(null);
  const ultimoBom = useRef<JogoView[]>([]);
  const geracao = useRef(0);

  const carregarOntem = useCallback(async (minha: number) => {
    setCarregando(true);
    const data = diaISOOntem(new Date());
    const r = await getLedgerDia(data);
    if (minha !== geracao.current) return;   // outra carga mais nova ja partiu
    if (r.ok === false) { setErro(true); setJogos(ultimoBom.current); setCarregando(false); return; }
    const porJogo = agruparPorJogo(r.dados.picks);
    const views = Array.from(porJogo.entries()).map(([matchId, picksDoJogo]) => {
      const leagueId = picksDoJogo[0].league_id;
      const liga = ligas.find((l) => toBackendLeagueId(l.id) === leagueId);
      return toJogoViewOntem(matchId, liga?.id ?? leagueId, liga?.nome ?? leagueId, picksDoJogo);
    }).sort((a, b) => a.kickoffIso.localeCompare(b.kickoffIso));
    ultimoBom.current = views; setJogos(views); setResumoOntem(r.dados.resumo);
    setCarimbo(fmtHora(new Date().toISOString())); setErro(false); setCarregando(false);
  }, [ligas]);

  const carregar = useCallback(async () => {
    const minha = ++geracao.current;
    if (url.dia === "ontem") { await carregarOntem(minha); return; }
    const date = diaParaApi(url.dia);
    if (!date) { setJogos([]); setCarregando(false); return; }
    setCarregando(true);
    try {
      const res = await getMatchesByLeague(ligas.map((l) => l.id).join(","), date);
      if (minha !== geracao.current) return;   // outra carga mais nova ja partiu: esta e obsoleta
      if (res._error) throw new Error(res._error.message);
      const agora = new Date();
      const views = deduplicateMatches((res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)))
        .map((m: Match) => toJogoView(m, agora))
        .sort((a, b) => Number(b.estado === "em_jogo") - Number(a.estado === "em_jogo") || a.kickoffIso.localeCompare(b.kickoffIso));
      ultimoBom.current = views; setJogos(views); setCarimbo(fmtHora(agora.toISOString())); setErro(false);
    } catch {
      if (minha !== geracao.current) return;
      setErro(true); setJogos(ultimoBom.current);
    } finally { if (minha === geracao.current) setCarregando(false); }
  }, [url.dia, ligas, carregarOntem]);

  useEffect(() => { carregar(); }, [carregar]);
  // Polling pausa com a aba oculta (spec §3): so recarrega se a pagina esta visivel.
  const carregarSeVisivel = useCallback(() => (document.visibilityState === "visible" ? carregar() : Promise.resolve()), [carregar]);
  useLivePolling(carregarSeVisivel, { hasMatches: jogos.length > 0, hasLiveMatches: jogos.some((j) => j.estado === "em_jogo") });

  const ir = (mudanca: Partial<typeof url>, push = false) => {
    const href = escreverFeedUrl({ ...url, ...mudanca });
    push ? router.push(href) : router.replace(href);
  };
  const visiveis = url.liga === "todas" ? jogos : jogos.filter((j) => j.ligaId === url.liga || j.ligaId.endsWith(url.liga));
  const aberto = visiveis.find((j) => j.id === url.jogo) ?? null;
  const painelRef = useRef<HTMLElement>(null);
  useEffect(() => { if (aberto) painelRef.current?.focus(); }, [aberto?.id]);

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-3 text-[var(--sb-texto)] lg:grid lg:grid-cols-[minmax(340px,1fr)_minmax(420px,1.2fr)] lg:gap-6">
      <div>
        <DiaTabs dia={url.dia} onChange={(dia) => ir({ dia, jogo: null })} />
        <LigaChips ligas={ligas} ativa={url.liga} onChange={(liga) => ir({ liga, jogo: null })} />
        {url.dia === "ontem" && <ResumoDoDia resumo={resumoOntem} />}
        {erro && (
          <p className="my-2 text-[14px]" role="status">
            {VAZIOS.feedNaoCarregou(url.dia)} <button onClick={carregar} className="sb-foco underline">{VAZIOS.tentarDeNovo}</button>
            {carimbo && <span className="ml-2 text-[var(--sb-texto-apagado)]">{VAZIOS.carimbo(carimbo)}</span>}
          </p>
        )}
        {!carregando && visiveis.length === 0 && !erro && (
          <p className="my-6 text-[14px] text-[var(--sb-texto-apagado)]">
            {VAZIOS.diaSemJogos(fmtDataCurta(new Date().toISOString()))}{" "}
            <Link href={escreverFeedUrl({ ...url, dia: url.dia === "hoje" ? "amanha" : "hoje" })} replace className="sb-foco underline">{VAZIOS.proximoDia(url.dia === "hoje" ? "amanhã" : "hoje")}</Link>
          </p>
        )}
        <div className="space-y-3 py-3">
          {visiveis.map((j) => (
            <div key={j.id} data-liga={j.ligaId}>
              <CardJogo jogo={j} confianca={confianca.get(j.ligaId)} selecionado={j.id === url.jogo}
                hrefDetalhe={isMobile ? `/jogos/${encodeURIComponent(j.id)}` : escreverFeedUrl({ ...url, jogo: j.id })}
                onAbrir={isMobile ? undefined : (id) => ir({ jogo: id }, true)} />
            </div>
          ))}
        </div>
      </div>
      {!isMobile && aberto && (
        <aside aria-label="detalhe do jogo" className="sticky top-4 self-start" ref={painelRef} tabIndex={-1}>
          <Detalhe jogo={aberto} confianca={confianca.get(aberto.ligaId)} />
        </aside>
      )}
    </div>
  );
}
