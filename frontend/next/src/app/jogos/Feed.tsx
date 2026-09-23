"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getMatchesByLeague, numeroDeLotes } from "@/lib/api";
import { ACTIVE_LEAGUES, toBackendLeagueId, type Match } from "@/lib/leagues";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { mesclarLote, quantosEsqueletos } from "@/lib/lotesFeed";
import { lerFeedUrl, escreverFeedUrl, diaParaApi, diaISOOntem, diaISOHoje, chaveDoDia } from "@/lib/feedUrl";
import { getLedgerDia, type LedgerPick } from "@/lib/ledgerApi";
import { agruparPorJogo, toJogoViewOntem, resultadoDoLedger } from "@/lib/jogoViewOntem";
import { mesmoJogo } from "@/lib/ledgerCasamento";
import { useLeagueClassifications } from "@/hooks/useLeagueClassifications";
import { useMediaDasLigas } from "@/hooks/useMediaDasLigas";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useLivePolling } from "@/hooks/useLivePolling";
import { fmtHora, fmtDataCurta } from "@/lib/formato";
import { VAZIOS, CARIMBO, CARREGANDO } from "@/lib/copy";
import Link from "next/link";
import { DiaTabs } from "@/components/feed/DiaTabs";
import { LigaChips } from "@/components/feed/LigaChips";
import { CardJogo } from "@/components/feed/CardJogo";
import { EsqueletoCard } from "@/components/feed/EsqueletoCard";
import { ResumoDoDia } from "@/components/feed/ResumoDoDia";
import { Detalhe } from "@/components/detalhe/Detalhe";
import { EstadoVazio } from "@/components/marca/EstadoVazio";

/**
 * #261 — aba Hoje, jogo encerrado: o talão continua vindo do feed
 * (`/api/matches/fetch`); o desfecho vem do `/ledger/dia` do próprio dia,
 * casado por liga + kickoff + times (`mesmoJogo`, nunca por id cru — spec
 * emenda #261 §4.2). Sem pick casado ou sem `outcome` ainda, a view fica
 * como está (`ontem_sem_desfecho`); com desfecho pro mercado do talão, vira
 * `ontem` com a mesma faixa que a aba Ontem usa (`resultadoDoLedger`, mesma
 * função, sem duplicar).
 */
function aplicarDesfechosDeHoje(views: JogoView[], picks: LedgerPick[]): JogoView[] {
  return views.map((v) => {
    if (v.estado !== "ontem_sem_desfecho") return v;
    const picksDoJogo = picks.filter((p) => mesmoJogo(v, p));
    const resultado = resultadoDoLedger(v.talao, picksDoJogo);
    return resultado ? { ...v, estado: "ontem" as const, resultado } : v;
  });
}

export function Feed() {
  const router = useRouter();
  const params = useSearchParams();
  const url = useMemo(() => lerFeedUrl(params), [params]);
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const confianca = useLeagueClassifications();
  // #256 fix round 1 — UMA chamada a /ledger/agregado por feed, nao uma por card.
  const media = useMediaDasLigas();
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
  const [lotesLidos, setLotesLidos] = useState(0);
  const [mostrarProgresso, setMostrarProgresso] = useState(false);
  const timerProgresso = useRef<ReturnType<typeof setTimeout> | null>(null);
  // #262 fix round 2 — sinaliza "carga fria em andamento" (sem leitura boa ao
  // iniciar) para o esqueleto. Nao pode mais ler ultimoBom.current.length===0
  // porque a correcao do #254-b (ultimoBom.current sincronizado lote a lote)
  // faz esse comprimento virar >0 assim que o 1o lote com jogos chega, o que
  // esconderia o esqueleto/progresso antes do fim da carga (quebra §3).
  // Comeca true (fix round 1, item 2): o esqueleto tem que pintar na carga
  // fria inicial, antes de qualquer `set` ligado a `carregar`.
  const cargaFria = useRef(true);
  // #262 fix round 2, item A — leitura boa e POR DIA, nao um booleano global
  // (fix round 1 marcava `jaHouveRespostaCompleta` uma vez pra sessao
  // inteira: trocar de aba depois de um dia lido vazio herdava "leitura boa"
  // de outro dia e deixava a area em branco — sem esqueleto, sem "Nenhum
  // jogo" — durante toda a carga do dia novo). Um dia entra no set no fim de
  // uma carga completa sem erro; nunca sai.
  // #262 fix wave — chaveado pela data ISO do dia (chaveDoDia), nao pelo
  // rotulo da aba: "hoje" de uma carga e "hoje" apos a virada de dia BRT sem
  // refresh de pagina sao dias diferentes.
  const diasLidos = useRef(new Set<string>());

  const carregarOntem = useCallback(async (minha: number) => {
    const chave = chaveDoDia("ontem", new Date());
    cargaFria.current = !diasLidos.current.has(chave);
    setCarregando(true); setLotesLidos(0);
    setMostrarProgresso(false);
    if (timerProgresso.current) clearTimeout(timerProgresso.current);
    timerProgresso.current = setTimeout(() => { if (minha === geracao.current) setMostrarProgresso(true); }, 1500);
    const data = diaISOOntem(new Date());
    const r = await getLedgerDia(data);
    if (minha !== geracao.current) return;   // outra carga mais nova ja partiu
    if (r.ok === false) {
      setErro(true); setJogos(ultimoBom.current);
      setCarregando(false); if (timerProgresso.current) clearTimeout(timerProgresso.current); setMostrarProgresso(false);
      return;
    }
    const porJogo = agruparPorJogo(r.dados.picks);
    const views = Array.from(porJogo.entries()).map(([matchId, picksDoJogo]) => {
      const leagueId = picksDoJogo[0].league_id;
      const liga = ligas.find((l) => toBackendLeagueId(l.id) === leagueId);
      return toJogoViewOntem(matchId, liga?.id ?? leagueId, liga?.nome ?? leagueId, picksDoJogo);
    }).sort((a, b) => a.kickoffIso.localeCompare(b.kickoffIso));
    ultimoBom.current = views; setJogos(views); setResumoOntem(r.dados.resumo);
    setCarimbo(fmtHora(new Date().toISOString())); setErro(false);
    diasLidos.current.add(chave);
    setCarregando(false); if (timerProgresso.current) clearTimeout(timerProgresso.current); setMostrarProgresso(false);
  }, [ligas]);

  const carregar = useCallback(async () => {
    const minha = ++geracao.current;
    if (url.dia === "ontem") { await carregarOntem(minha); return; }
    const date = diaParaApi(url.dia);
    if (!date) { setJogos([]); setCarregando(false); return; }
    setCarregando(true); setLotesLidos(0);
    // #262 fix round 2, item A — leitura boa = este DIA especifico ja teve
    // uma carga completa sem erro (ver declaracao de diasLidos acima).
    // #262 fix wave — chave calculada uma vez no inicio da carga (chaveDoDia).
    const chave = chaveDoDia(url.dia, new Date());
    const temLeituraBoa = diasLidos.current.has(chave);
    cargaFria.current = !temLeituraBoa;
    // #262 fix round 1, item 1 — numeroDeLotes(ligas.length) calculado uma
    // vez aqui e usado para o clamp de `lidos` abaixo: getMatchesByLeague
    // chama onBatchReady de novo em cada retry de lote (api.ts), entao sem
    // o clamp `lidos` passa de numLotes e a frase vira "15 de 13 ligas lidas".
    const numLotes = numeroDeLotes(ligas.length);
    setMostrarProgresso(false);
    if (timerProgresso.current) clearTimeout(timerProgresso.current);
    timerProgresso.current = setTimeout(() => { if (minha === geracao.current) setMostrarProgresso(true); }, 1500);
    let acumulado: JogoView[] = temLeituraBoa ? ultimoBom.current : [];
    let lidos = 0;
    // #262 fix round 2, item D — flag propria pro "e o primeiro lote deste
    // carregamento", independente do clamp de `lidos` (Math.min): antes
    // usava `lidos === 1`, que dependia do valor clampado coincidir com 1.
    let primeiroLote = true;
    try {
      const res = await getMatchesByLeague(ligas.map((l) => l.id).join(","), date, (lote) => {
        if (minha !== geracao.current) return;
        lidos = Math.min(lidos + 1, numLotes); setLotesLidos(lidos);
        const ehPrimeiroLote = primeiroLote; primeiroLote = false;
        // #262 fix round 1, item 3 — hora de CHEGADA deste lote, nao a hora
        // em que o fetch comecou (que ficava cada vez mais velha a cada
        // lote, fazendo o carimbo "retroceder" perto do fim da carga).
        const agoraLote = new Date();
        const novas = deduplicateMatches((lote.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)))
          .map((m: Match) => toJogoView(m, agoraLote));
        // Sem leitura boa, a lista cresce lote a lote (spec §3, "por camadas"); com leitura boa,
        // a lista antiga fica na tela ate a carga terminar (troca sem piscar).
        if (!temLeituraBoa) {
          acumulado = mesclarLote(acumulado, novas); setJogos(acumulado);
          // #262 fix round 2 (achado ao medir o item A) — um lote com
          // `_error` nao e "uma leitura boa daquela liga" (principio do
          // ruling original do #254-b): commitar em ultimoBom.current mesmo
          // assim destruía o ultimo feed bom de OUTRO dia antes de saber se
          // a carga desta ia falhar (jogos.spec.ts "backend fora" — a lista
          // de hoje sumia ao trocar para amanha com erro, antes mesmo do
          // catch). So os lotes sem erro viram o novo "ultimo bom".
          if (!lote._error) { ultimoBom.current = acumulado; setCarimbo(fmtHora(agoraLote.toISOString())); }
        } else acumulado = mesclarLote(ehPrimeiroLote ? [] : acumulado, novas);
      });
      if (minha !== geracao.current) return;
      if (res._error) throw new Error(res._error.message);
      let views = acumulado;
      // #262 fix round 1, item 3 — hora de TERMINO da carga (pos-fetch); o
      // enriquecimento do ledger de hoje usa esta mesma hora, nunca o
      // instante pre-fetch.
      const fim = new Date();
      if (url.dia === "hoje" && views.some((v) => v.estado === "ontem_sem_desfecho")) {
        const rLedger = await getLedgerDia(diaISOHoje(fim));
        if (minha !== geracao.current) return;
        if (rLedger.ok) views = aplicarDesfechosDeHoje(views, rLedger.dados.picks);
      }
      ultimoBom.current = views; setJogos(views); setCarimbo(fmtHora(fim.toISOString())); setErro(false);
      diasLidos.current.add(chave);
    } catch {
      if (minha !== geracao.current) return;
      setErro(true); setJogos(ultimoBom.current);
    } finally {
      if (minha === geracao.current) { setCarregando(false); if (timerProgresso.current) clearTimeout(timerProgresso.current); setMostrarProgresso(false); }
    }
  }, [url.dia, ligas, carregarOntem]);

  useEffect(() => { carregar(); }, [carregar]);
  // #262 fix round 1, item (a) — o timer de 1,5s nao pode disparar apos o
  // desmonte (setState em componente desmontado).
  useEffect(() => () => { if (timerProgresso.current) clearTimeout(timerProgresso.current); }, []);
  // Polling pausa com a aba oculta (spec §3): so recarrega se a pagina esta visivel.
  const carregarSeVisivel = useCallback(() => (document.visibilityState === "visible" ? carregar() : Promise.resolve()), [carregar]);
  useLivePolling(carregarSeVisivel, { hasMatches: jogos.length > 0, hasLiveMatches: jogos.some((j) => j.estado === "em_jogo") });

  const ir = (mudanca: Partial<typeof url>, push = false) => {
    const href = escreverFeedUrl({ ...url, ...mudanca });
    push ? router.push(href) : router.replace(href);
  };
  const visiveis = url.liga === "todas" ? jogos : jogos.filter((j) => j.ligaId === url.liga || j.ligaId.endsWith(url.liga));
  // #262 — a aba Ontem e uma chamada so (o ledger do dia), sem progresso por
  // liga: numeroDeLotes(1), e a frase fica sempre "buscando", nunca "progresso".
  const numLotes = url.dia === "ontem" ? numeroDeLotes(1) : numeroDeLotes(ligas.length);
  const textoCarregando = url.dia === "ontem" || !mostrarProgresso
    ? CARREGANDO.buscando(url.dia)
    : CARREGANDO.progresso(url.dia, lotesLidos, numLotes);
  const aberto = visiveis.find((j) => j.id === url.jogo) ?? null;
  const painelRef = useRef<HTMLElement>(null);
  useEffect(() => { if (aberto) painelRef.current?.focus(); }, [aberto?.id]);

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-3 text-[var(--sb-texto)] lg:grid lg:grid-cols-[minmax(340px,1fr)_minmax(420px,1.2fr)] lg:gap-6">
      <div>
        {carimbo && <p className="tnum text-right text-[12px] text-[var(--sb-texto-apagado)]" data-carimbo>{CARIMBO.lidoAs(carimbo)}</p>}
        <DiaTabs dia={url.dia} onChange={(dia) => ir({ dia, jogo: null })} />
        <LigaChips ligas={ligas} ativa={url.liga} onChange={(liga) => ir({ liga, jogo: null })} />
        {url.dia === "ontem" && <ResumoDoDia resumo={resumoOntem} />}
        {erro && (
          <p className="my-2 text-[14px]" role="status">
            {VAZIOS.feedNaoCarregou(url.dia)} <button onClick={carregar} className="sb-foco underline">{VAZIOS.tentarDeNovo}</button>
            {carimbo && <span className="ml-2 text-[var(--sb-texto-apagado)]">{VAZIOS.carimbo(carimbo)}</span>}
          </p>
        )}
        {/* #262 fix round 2, item A — dia ja lido (nao carga fria): a mensagem de
            vazio fica na tela durante a recarga, sem sumir e sem esqueleto por
            cima; dia nunca lido: so aparece quando a carga termina, como antes. */}
        {visiveis.length === 0 && !erro && (!carregando || !cargaFria.current) && (
          <EstadoVazio>
            <p>
              {VAZIOS.diaSemJogos(fmtDataCurta(new Date().toISOString()))}{" "}
              <Link href={escreverFeedUrl({ ...url, dia: url.dia === "hoje" ? "amanha" : "hoje" })} replace className="sb-foco underline">{VAZIOS.proximoDia(url.dia === "hoje" ? "amanhã" : "hoje")}</Link>
            </p>
          </EstadoVazio>
        )}
        <div className="space-y-3 py-3" aria-busy={carregando}>
          {visiveis.map((j) => (
            <div key={j.id} data-liga={j.ligaId}>
              <CardJogo jogo={j} confianca={confianca.get(j.ligaId)} selecionado={j.id === url.jogo} media={media}
                hrefDetalhe={isMobile ? `/jogos/${encodeURIComponent(j.id)}` : escreverFeedUrl({ ...url, jogo: j.id })}
                onAbrir={isMobile ? undefined : (id) => ir({ jogo: id }, true)} />
            </div>
          ))}
          {carregando && cargaFria.current && (
            <div data-esqueleto>
              <p role="status" className="sr-only">{textoCarregando}</p>
              <div className="space-y-3">{Array.from({ length: quantosEsqueletos(numLotes - lotesLidos) }, (_, i) => <EsqueletoCard key={i} />)}</div>
              {mostrarProgresso && <p aria-hidden="true" className="mt-2 text-[13px] text-[var(--sb-texto-apagado)]" data-progresso>{textoCarregando}</p>}
            </div>
          )}
        </div>
      </div>
      {!isMobile && aberto && (
        <aside aria-label="detalhe do jogo" className="sticky top-[calc(56px+1rem)] self-start lg:max-h-[calc(100vh-56px-2rem)] lg:overflow-y-auto" ref={painelRef} tabIndex={-1}>
          <Detalhe jogo={aberto} confianca={confianca.get(aberto.ligaId)} />
        </aside>
      )}
    </div>
  );
}
