"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getLedgerAgregado, getLedgerDia } from "@/lib/ledgerApi";
import { getMatchesByLeague } from "@/lib/api";
import { normalizeMatch, deduplicateMatches } from "@/lib/normalizeMatch";
import { toJogoView, type JogoView } from "@/lib/jogoView";
import { agruparPorJogo, toJogoViewOntem } from "@/lib/jogoViewOntem";
import { diaISOOntem } from "@/lib/feedUrl";
import { ACTIVE_LEAGUES, toBackendLeagueId, type Match } from "@/lib/leagues";
import { fraseAcertoHero, HERO } from "@/lib/copy";
import { CardJogo } from "@/components/feed/CardJogo";
import { fonteMarca } from "@/components/marca/fonteMarca";

const MIN_N_HERO = 20; // mesmo piso do backend, MIN_N_BRIER (#079)

export function Hero() {
  const [frase, setFrase] = useState<string | null>(null);
  const [jogoProva, setJogoProva] = useState<JogoView | null>(null);
  const [semProva, setSemProva] = useState(false);

  useEffect(() => {
    let vivo = true;
    const ligas = ACTIVE_LEAGUES().map((l) => ({ id: toBackendLeagueId(l.id), nome: l.name }));

    getLedgerAgregado("30d").then((r) => {
      if (!vivo || !r.ok) return;
      const { acertos, jogos, resolvidos } = r.dados.acerto;
      setFrase(fraseAcertoHero(acertos, resolvidos, jogos, MIN_N_HERO));
    }).catch(() => {});

    // #258: ledger de ontem dispara em PARALELO com o feed de hoje — nao mais
    // sequencial apos hoje falhar/esvaziar, o que deixava ate ~7s sem
    // nenhuma prova no hero. Hoje sempre vence quando produz talao (a
    // qualquer momento, mesmo depois de ontem ja mostrado); ontem so entra
    // como ponte se hoje nao respondeu com talao ate 1s; sem nenhum dos
    // dois ate 2s, mostra a frase de ausencia (spec do dono, #258).
    let mostrado: "nenhum" | "ontem" | "hoje" = "nenhum";
    let ontemResolvido = false;
    let ontemAchado: JogoView | null = null;

    getLedgerDia(diaISOOntem(new Date())).then((rOntem) => {
      if (!vivo) return;
      ontemResolvido = true;
      if (!rOntem.ok) return;
      const porJogo = agruparPorJogo(rOntem.dados.picks);
      for (const [matchId, picksDoJogo] of Array.from(porJogo)) {
        const leagueId = picksDoJogo[0].league_id;
        const liga = ligas.find((l) => l.id === leagueId);
        const view = toJogoViewOntem(matchId, liga?.id ?? leagueId, liga?.nome ?? leagueId, picksDoJogo);
        if (view.estado === "ontem" && view.talao) { ontemAchado = view; break; }
      }
    }).catch(() => { if (vivo) ontemResolvido = true; });

    getMatchesByLeague(ligas.map((l) => l.id).join(","), "today").then((res) => {
      if (!vivo) return;
      const agora = new Date();
      const views = deduplicateMatches(
        (res.matches ?? []).map((m, i) => normalizeMatch(m, (m as { leagueId?: string }).leagueId ?? "", i)),
      ).map((m: Match) => toJogoView(m, agora));
      // spec §5: o talão-prova é o de MAIOR edge de hoje; empate, maior chance
      const doHoje = views.filter((v) => v.talao)
        .sort((a, b) => (b.talao!.edge ?? -Infinity) - (a.talao!.edge ?? -Infinity) || b.talao!.prob01 - a.talao!.prob01)[0];
      if (doHoje) {
        mostrado = "hoje";
        setSemProva(false);
        setJogoProva(doHoje);
      }
      // hoje sem talao: nao mexe no que ja esta na tela (ontem pode ter
      // aparecido ou vir a aparecer pelo timer de 1s) nem antecipa a
      // ausencia — quem decide a ausencia e o timer de 2s.
    }).catch(() => {});

    const t1 = setTimeout(() => {
      if (!vivo || mostrado === "hoje") return;
      if (ontemResolvido && ontemAchado) {
        mostrado = "ontem";
        setJogoProva(ontemAchado);
      }
    }, 1000);
    const t2 = setTimeout(() => {
      if (!vivo || mostrado !== "nenhum") return;
      setSemProva(true);
    }, 2000);

    return () => { vivo = false; clearTimeout(t1); clearTimeout(t2); };
  }, []);

  return (
    <section className="mx-auto flex min-h-screen max-w-[720px] flex-col items-center justify-center gap-6 px-4 text-center text-[var(--sb-texto)]">
      <h1 className={`${fonteMarca.className} text-[36px] font-bold leading-tight`}>
        {HERO.headlineLinha1}
        <br />{HERO.headlineLinha2}
      </h1>
      {frase && <p className="tnum text-[16px] text-[var(--sb-texto-apagado)]">{frase}</p>}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/jogos" className="sb-foco rounded-[var(--sb-raio-painel)] border border-[var(--sb-texto)] px-5 py-2.5 text-[16px] font-semibold">
          {HERO.ctaJogos}
        </Link>
        <Link href="/login" className="sb-foco text-[14px] underline">{HERO.ctaEntrar}</Link>
        <Link href="/register" className="sb-foco text-[14px] underline">{HERO.ctaCriarConta}</Link>
      </div>
      {jogoProva && (
        <div className="w-full max-w-[420px] text-left">
          <CardJogo jogo={jogoProva} confianca={null} selecionado={false}
            hrefDetalhe={`/jogos/${encodeURIComponent(jogoProva.id)}`} media={null} />
        </div>
      )}
      {!jogoProva && semProva && <p className="text-[13px] text-[var(--sb-texto-apagado)]">{HERO.semTalao}</p>}
    </section>
  );
}
